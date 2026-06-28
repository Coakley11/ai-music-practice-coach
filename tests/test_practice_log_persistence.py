"""Practice log persistence merge and round-trip tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from practice_log_persistence import _merge_logs, load_practice_logs, save_practice_logs
from practice_log_state import migrate_practice_log_entry


class TestPracticeLogPersistence(unittest.TestCase):
    def test_same_session_id_newer_updated_at_wins(self) -> None:
        older = migrate_practice_log_entry(
            {
                "session_id": "abc-123",
                "date": "2026-06-01",
                "active_song": "A",
                "duration_minutes": 10,
                "updated_at": "2026-06-01T10:00:00+00:00",
            }
        )
        newer = migrate_practice_log_entry(
            {
                "session_id": "abc-123",
                "date": "2026-06-01",
                "active_song": "A",
                "duration_minutes": 25,
                "updated_at": "2026-06-02T10:00:00+00:00",
            }
        )
        merged = _merge_logs([older], [newer])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].get("duration_minutes"), 25)

    def test_different_session_ids_union(self) -> None:
        a = migrate_practice_log_entry({"session_id": "dev-a", "date": "2026-06-01", "active_song": "A", "duration_minutes": 10})
        b = migrate_practice_log_entry({"session_id": "dev-b", "date": "2026-06-02", "active_song": "B", "duration_minutes": 15})
        merged = _merge_logs([a], [b])
        self.assertEqual(len(merged), 2)

    def test_legacy_entries_migrated_before_merge(self) -> None:
        legacy = {"date": "2026-06-19", "song": "Autumn Leaves", "minutes": 30}
        merged = _merge_logs([legacy], [dict(legacy)])
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0].get("session_id"))

    def test_local_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "practice_history.json"

            def _fake_path():
                return path

            with patch("practice_log_persistence._local_path", _fake_path):
                with patch("studio_history_cloud.cloud_enabled", return_value=False):
                    entry = migrate_practice_log_entry(
                        {
                            "session_id": "round-trip-1",
                            "date": "2026-06-20",
                            "active_song": "Test Song",
                            "duration_minutes": 22,
                            "updated_at": "2026-06-20T12:00:00+00:00",
                        }
                    )
                    save_practice_logs([entry], st=None)
                    self.assertTrue(path.exists())
                    loaded = load_practice_logs(st=None)
                    self.assertEqual(len(loaded), 1)
                    self.assertEqual(loaded[0].get("duration_minutes"), 22)


if __name__ == "__main__":
    unittest.main()

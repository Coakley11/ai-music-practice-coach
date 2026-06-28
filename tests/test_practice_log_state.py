"""Canonical practice log state API tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from practice_log_state import (
    add_practice_log_entry,
    compute_practice_log_summary,
    delete_practice_log_entry,
    deterministic_session_id,
    filter_practice_log_entries,
    migrate_practice_log_entry,
    normalize_practice_log_entries,
    update_practice_log_entry,
)


class TestPracticeLogMigration(unittest.TestCase):
    def test_legacy_migration_creates_session_id_and_fields(self) -> None:
        legacy = {
            "date": "2026-06-01",
            "song": "Autumn Leaves",
            "minutes": 25,
            "practice": "Worked chorus transitions",
            "rating": 8,
            "mode": "Song Work",
        }
        out = migrate_practice_log_entry(legacy)
        self.assertTrue(out.get("session_id"))
        self.assertEqual(out.get("duration_minutes"), 25)
        self.assertEqual(out.get("notes"), "Worked chorus transitions")
        self.assertEqual(out.get("active_song"), "Autumn Leaves")
        self.assertIn("created_at", out)
        self.assertIn("updated_at", out)
        self.assertEqual(out.get("practice_type"), "song practice")

    def test_deterministic_session_id_stable(self) -> None:
        entry = {"date": "2026-06-01", "song": "A", "minutes": 10, "practice": "x", "rating": 5, "mode": "Other"}
        self.assertEqual(deterministic_session_id(entry), deterministic_session_id(dict(entry)))


class TestPracticeLogCrud(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = Path(self._tmpdir.name) / "practice_history.json"
        self._patch = patch("practice_log_persistence._local_path", lambda *, st=None: self._path)
        self._patch_ws = patch("practice_log_persistence._resolve_workspace_id", lambda *, st=None: "daniel")
        self._patch_cloud = patch("practice_log_persistence._load_cloud_logs", lambda *, st=None: [])
        self._patch.start()
        self._patch_ws.start()
        self._patch_cloud.start()
        self.session: dict = {}

    def tearDown(self) -> None:
        self._patch.stop()
        self._patch_ws.stop()
        self._patch_cloud.stop()
        self._tmpdir.cleanup()

    def test_add_entry_creates_canonical_fields(self) -> None:
        entry = add_practice_log_entry(
            self.session,
            {
                "active_song": "Perfect",
                "instrument": "Piano",
                "duration_minutes": 20,
                "notes": "Chorus work",
                "what_was_hard": "Timing at bar 9",
                "next_step": "Loop chorus slowly",
            },
        )
        self.assertEqual(entry.get("active_song"), "Perfect")
        self.assertEqual(entry.get("what_was_hard"), "Timing at bar 9")
        self.assertIn("session_id", entry)

    def test_update_bumps_updated_at(self) -> None:
        from unittest.mock import patch

        entry = add_practice_log_entry(self.session, {"active_song": "Song A", "duration_minutes": 15})
        before = entry.get("updated_at")
        with patch("practice_log_state._utc_now_iso", return_value="2099-01-02T00:00:00+00:00"):
            updated = update_practice_log_entry(
                self.session,
                str(entry["session_id"]),
                {"notes": "Updated notes"},
            )
        self.assertEqual(updated.get("notes"), "Updated notes")
        self.assertNotEqual(updated.get("updated_at"), before)

    def test_delete_hides_entry(self) -> None:
        entry = add_practice_log_entry(self.session, {"active_song": "Delete Me", "duration_minutes": 10})
        sid = str(entry["session_id"])
        self.assertTrue(delete_practice_log_entry(self.session, sid))
        visible = normalize_practice_log_entries(
            [e for e in (self.session.get("practice_log_entries") or [])]
        )
        self.assertFalse(any(e.get("session_id") == sid for e in visible))


class TestPracticeLogFilterSummary(unittest.TestCase):
    def _sample_entries(self) -> list[dict]:
        today = date.today().isoformat()
        old = (date.today() - timedelta(days=40)).isoformat()
        return normalize_practice_log_entries(
            [
                migrate_practice_log_entry(
                    {
                        "session_id": "s1",
                        "date": today,
                        "active_song": "Autumn Leaves",
                        "instrument": "Tenor Sax",
                        "duration_minutes": 30,
                        "focus_area": "timing/rhythm",
                        "practice_type": "song practice",
                        "what_was_hard": "rush the bridge",
                    }
                ),
                migrate_practice_log_entry(
                    {
                        "session_id": "s2",
                        "date": old,
                        "active_song": "Blue Bossa",
                        "instrument": "Piano",
                        "duration_minutes": 20,
                        "focus_area": "chords",
                        "practice_type": "song practice",
                    }
                ),
            ]
        )

    def test_filter_by_instrument_and_focus(self) -> None:
        entries = self._sample_entries()
        filtered = filter_practice_log_entries(
            entries,
            {"instrument": "Tenor Sax", "focus_area": "timing/rhythm", "window_days": 14},
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].get("active_song"), "Autumn Leaves")

    def test_summary_computes_top_song_and_focus(self) -> None:
        entries = self._sample_entries()
        summary = compute_practice_log_summary(entries, window_days=14)
        self.assertGreaterEqual(summary.get("session_count", 0), 1)
        self.assertIn("Autumn Leaves", summary.get("most_practiced_songs") or [])
        self.assertIn("timing/rhythm", summary.get("most_common_focus_areas") or [])


if __name__ == "__main__":
    unittest.main()

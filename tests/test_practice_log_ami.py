"""Practice log AMI payload tests."""

from __future__ import annotations

import unittest

from practice_log_ami import build_practice_log_ami_payload
from practice_log_state import migrate_practice_log_entry


class TestPracticeLogAmiPayload(unittest.TestCase):
    def _entries(self) -> list[dict]:
        return [
            migrate_practice_log_entry(
                {
                    "session_id": "ami-1",
                    "date": "2026-06-25",
                    "active_song": "Autumn Leaves",
                    "duration_minutes": 30,
                    "focus_area": "timing/rhythm",
                    "what_was_hard": "bridge timing",
                    "next_step": "loop bridge at 70%",
                    "updated_at": "2026-06-25T18:00:00+00:00",
                }
            ),
            migrate_practice_log_entry(
                {
                    "session_id": "ami-2",
                    "date": "2026-06-24",
                    "active_song": "Autumn Leaves",
                    "duration_minutes": 20,
                    "what_was_hard": "bridge timing",
                    "updated_at": "2026-06-24T18:00:00+00:00",
                }
            ),
        ]

    def test_payload_has_summary_and_recent_sessions(self) -> None:
        payload = build_practice_log_ami_payload({}, entries=self._entries(), window_days=14)
        self.assertIn("practice_log_summary", payload)
        summary = payload["practice_log_summary"]
        self.assertGreater(summary.get("session_count", 0), 0)
        self.assertTrue(payload.get("recent_sessions"))
        self.assertIn("Autumn Leaves", summary.get("most_practiced_songs") or [])

    def test_repeated_challenges_from_what_was_hard(self) -> None:
        payload = build_practice_log_ami_payload({}, entries=self._entries(), window_days=14)
        challenges = payload["practice_log_summary"].get("repeated_challenges") or []
        self.assertTrue(any("bridge" in str(c).lower() for c in challenges))

    def test_last_session_summary_is_newest(self) -> None:
        payload = build_practice_log_ami_payload({}, entries=self._entries(), window_days=14)
        last = payload["practice_log_summary"].get("last_session_summary") or {}
        self.assertEqual(last.get("session_id"), "ami-1")


if __name__ == "__main__":
    unittest.main()

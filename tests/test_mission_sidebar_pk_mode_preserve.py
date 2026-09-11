"""Unit: Mission Backing sidebar PK must not coerce Cm → C major."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class MissionSidebarKeyNormalizeTests(unittest.TestCase):
    def test_mission_backing_preserves_cm(self) -> None:
        from songs.key_state import normalize_sidebar_display_key

        session = {
            "studio_page": "backing",
            "selected_song": {"key": "D", "title": "Trial Song"},
            "original_key": "D",
        }
        ctx = SimpleNamespace(source="mission", key="D")
        with patch("backing_context.get_backing_context", return_value=ctx):
            self.assertEqual(normalize_sidebar_display_key(session, "Cm"), "Cm")
            self.assertEqual(normalize_sidebar_display_key(session, "C#m"), "C#m")

    def test_ordinary_path_still_coerces_to_song_mode(self) -> None:
        from songs.key_state import normalize_sidebar_display_key

        session = {
            "studio_page": "practice",
            "selected_song": {"key": "D", "title": "Trial Song"},
            "original_key": "D",
        }
        with patch("backing_context.get_backing_context", return_value=None):
            # Major song: Cm coerces to C (same pitch class, major mode).
            self.assertEqual(normalize_sidebar_display_key(session, "Cm"), "C")

    def test_mission_backing_prefers_live_cm_over_custom_sticky_d(self) -> None:
        from backing_musical_state import _resolve_creative_practice_concert_key

        session = {
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_song_source": "Custom progression",
            "practice_key_by_source": {
                "custom::961fc261-36fb-406b-ba76-a07056fe9dd4": "D",
            },
            "active_catalog_pick_key": "custom::961fc261-36fb-406b-ba76-a07056fe9dd4",
        }
        creative = SimpleNamespace(
            source="mission",
            active_song_id="custom::961fc261-36fb-406b-ba76-a07056fe9dd4",
            key="D",
            concert_key="D",
        )
        practice = _resolve_creative_practice_concert_key(
            session, creative=creative, major_jam=False
        )
        self.assertEqual(practice, "Cm")


if __name__ == "__main__":
    unittest.main()

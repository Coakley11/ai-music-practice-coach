"""Reboot-style authoritative workspace restore."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state
from practice_key_mode import MODE_FIXED, family_option_id
from practice_tools_ui import PRACTICE_ACTIVE_TOOL_KEY
from practice_workspace_persistence import (
    PRACTICE_TIME_PITCH_VIEW_KEY,
    PRACTICE_WORKSPACE_STATE_KEY,
    TIME_PITCH_VIEW_TONE_SUSTAIN,
)


class TestRebootWorkspaceRestore(unittest.TestCase):
    def _full_blob(self) -> dict:
        return {
            "music_workspace_state": {
                "studio_page": "creative",
                "workspace_revision": 42,
                "practice_workspace_state": {
                    "selected_practice_tool": "coach",
                    "time_pitch_view": TIME_PITCH_VIEW_TONE_SUSTAIN,
                },
            },
            "studio_nav_state": {"studio_page": "creative"},
            "core": {
                "studio_page": "practice",
                "instrument": "Saxophone",
                "level": "Advanced",
                "focus": "Tone",
                "practice_focus_section": "Verse",
                "pick_key": "pk::test::song",
            },
            "session": {
                "practice_key_mode": MODE_FIXED,
                "fixed_practice_key_family_id": family_option_id("Eb", "C"),
                "fixed_practice_key": "Eb",
                "fixed_practice_key_family_spelling": "flat",
            },
            "practice_state": {
                "practice_focus_section": "Verse",
                "practice_minutes": 50,
            },
        }

    def test_authoritative_restore_page_song_and_musician_context(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "practice", "instrument": "Piano", "level": "Beginner"}
        apply_music_disk_state(
            st,
            self._full_blob(),
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        ss = st.session_state
        self.assertEqual(ss.get("studio_page"), "creative")
        self.assertEqual(ss.get("instrument"), "Saxophone")
        self.assertEqual(ss.get("level"), "Advanced")
        self.assertEqual(ss.get("focus"), "Tone")
        self.assertEqual(ss.get("practice_focus_section"), "Verse")

    def test_authoritative_restore_practice_tool_and_time_pitch(self) -> None:
        st = MagicMock()
        st.session_state = {PRACTICE_ACTIVE_TOOL_KEY: ""}
        apply_music_disk_state(
            st,
            self._full_blob(),
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        ss = st.session_state
        self.assertEqual(ss.get(PRACTICE_ACTIVE_TOOL_KEY), "coach")
        self.assertEqual(ss.get(PRACTICE_TIME_PITCH_VIEW_KEY), TIME_PITCH_VIEW_TONE_SUSTAIN)
        ws = ss.get(PRACTICE_WORKSPACE_STATE_KEY)
        self.assertIsInstance(ws, dict)
        self.assertEqual(ws.get("selected_practice_tool"), "coach")

    def test_authoritative_restore_eb_family(self) -> None:
        st = MagicMock()
        st.session_state = {}
        apply_music_disk_state(
            st,
            self._full_blob(),
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        ss = st.session_state
        self.assertEqual(ss.get("fixed_practice_key_family_id"), "Eb|C")
        self.assertEqual(ss.get("fixed_practice_key"), "Eb")
        self.assertEqual(ss.get("fixed_practice_key_family_spelling"), "flat")

    def test_init_practice_skips_defaults_during_hydration(self) -> None:
        from studio_page_state import init_practice_page_state

        ss = {
            "_music_workspace_hydration_started": True,
            PRACTICE_ACTIVE_TOOL_KEY: "coach",
        }
        init_practice_page_state(ss)
        self.assertEqual(ss.get(PRACTICE_ACTIVE_TOOL_KEY), "coach")


if __name__ == "__main__":
    unittest.main()

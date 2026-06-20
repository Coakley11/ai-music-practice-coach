"""Custom Progression — set active song, draft key isolation, cloud restore."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from active_song_state import (
    ACTIVE_SONG_STATE_KEY,
    apply_cloud_active_song_state_if_allowed,
    gather_active_song_context,
)
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    commit_home_sections,
    default_active_progression,
    display_entries_for_section,
    entries_chord_tiles_html,
    ensure_all_cpl_sections,
    ensure_original_structure,
    set_original_key_center,
    written_home_key,
)
from songs.music_source import (
    SOURCE_CUSTOM,
    commit_custom_active_song,
    custom_selected_song_record,
    is_custom_progression,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class TestCplSetActiveSong(unittest.TestCase):
    def _draft_with_chords(self) -> dict:
        active = default_active_progression()
        active["name"] = "My Progression"
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        home = ensure_all_cpl_sections(active["original_sections"])
        home["Verse"] = [
            {"chord": "C", "bars": 1},
            {"chord": "Am", "bars": 1},
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        return commit_home_sections(active, home)

    def test_chord_tiles_render_from_draft_home_key(self) -> None:
        active = self._draft_with_chords()
        preview = written_home_key(active)
        display = display_entries_for_section(active, preview, "Verse")
        html = entries_chord_tiles_html(display, time_signature="4/4")
        self.assertEqual(len(display), 4)
        self.assertIn(">C<", html)
        self.assertIn(">Am<", html)

    def test_draft_key_change_does_not_require_global_display_key(self) -> None:
        active = self._draft_with_chords()
        session = {"display_key": "G", CPL_ACTIVE_KEY: active}
        active = set_original_key_center(active, "D")
        session[CPL_ACTIVE_KEY] = active
        self.assertEqual(session["display_key"], "G")
        self.assertEqual(written_home_key(active), "D")

    def test_commit_custom_active_song_updates_global_state(self) -> None:
        active = self._draft_with_chords()
        st = SimpleNamespace(session_state={
            "display_key": "G",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            CPL_ACTIVE_KEY: active,
        })

        with patch("songs.state.persist_music_local_state"):
            commit_custom_active_song(
                st,
                active,
                invalidate_backing=lambda _st: None,
            )

        ss = st.session_state
        self.assertTrue(is_custom_progression(ss))
        self.assertEqual(ss["display_key"], "C")
        selected = ss[SELECTED_SONG_STATE_KEY]
        self.assertEqual(selected["title"], "My Progression")
        self.assertEqual(selected["key"], "C")
        self.assertTrue(str(ss[ACTIVE_CATALOG_PICK_KEY]).startswith("custom::"))
        meta = ss[ACTIVE_SONG_STATE_KEY]
        self.assertEqual(meta["music_source"], SOURCE_CUSTOM)
        self.assertEqual(meta["custom_progression_name"], "My Progression")
        self.assertEqual(meta["custom_home_key"], "C")

    def test_gather_context_reports_custom_source(self) -> None:
        active = self._draft_with_chords()
        session = {
            "active_music_source": SOURCE_CUSTOM,
            CPL_ACTIVE_KEY: active,
            "display_key": "C",
        }
        ctx = gather_active_song_context(session)
        self.assertEqual(ctx["music_source"], SOURCE_CUSTOM)
        self.assertEqual(ctx["selected_song"]["title"], "My Progression")
        self.assertEqual(ctx["display_key"], "C")

    def test_cloud_restore_custom_progression_source(self) -> None:
        active = self._draft_with_chords()
        cloud = {
            "session": {
                "active_music_source": SOURCE_CUSTOM,
                "cpl_active_progression": active,
            },
            "active_song_state": {
                "music_source": SOURCE_CUSTOM,
                "display_key": "C",
                "custom_progression_name": "My Progression",
                "custom_home_key": "C",
            },
        }
        session: dict = {"display_key": "G"}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(session, cloud))
        self.assertEqual(session["active_music_source"], SOURCE_CUSTOM)
        self.assertEqual(session["display_key"], "C")
        self.assertEqual(session[SELECTED_SONG_STATE_KEY]["title"], "My Progression")
        self.assertEqual(session[ACTIVE_SONG_STATE_KEY]["music_source"], SOURCE_CUSTOM)

    def test_custom_selected_song_record_shape(self) -> None:
        active = self._draft_with_chords()
        record = custom_selected_song_record(active)
        self.assertEqual(record["title"], "My Progression")
        self.assertEqual(record["key"], "C")
        self.assertTrue(record["is_custom"])


if __name__ == "__main__":
    unittest.main()

"""Reliability commit 1 — page, song identity, musician context restore."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state
from practice_key_mode import MODE_FIXED
from practice_state import PRACTICE_RESTORED_KEY, prepare_practice_page
from studio_nav_state import bootstrap_studio_page_session


class TestStudioPageBootstrap(unittest.TestCase):
    def test_pending_hydration_uses_blob_page_not_practice(self) -> None:
        ss = {
            "_suite_last_cloud_fetch_payload": {
                "music_workspace_state": {"studio_page": "creative"},
            }
        }
        page = bootstrap_studio_page_session(ss)
        self.assertEqual(page, "creative")
        self.assertEqual(ss.get("studio_page"), "creative")

    def test_empty_confirmed_may_default_practice(self) -> None:
        ss = {"_music_workspace_empty_confirmed": True}
        page = bootstrap_studio_page_session(ss, default="practice")
        self.assertEqual(page, "practice")

    def test_hydrated_uses_canonical_nav(self) -> None:
        ss = {
            "_music_workspace_blob_hydrated": True,
            "studio_nav_state": {"studio_page": "backing"},
        }
        page = bootstrap_studio_page_session(ss)
        self.assertEqual(page, "backing")
        self.assertEqual(ss.get("studio_page"), "backing")


class TestApplyMusicDiskStateMusicianContext(unittest.TestCase):
    def test_non_practice_page_and_saxophone_survive_apply(self) -> None:
        st = MagicMock()
        st.session_state = {}
        blob = {
            "music_workspace_state": {"studio_page": "creative"},
            "studio_nav_state": {"studio_page": "creative"},
            "core": {
                "studio_page": "practice",
                "instrument": "Saxophone",
                "level": "Advanced",
                "focus": "Tone",
                "practice_focus_section": "Verse",
                "display_key": "G",
            },
            "session": {
                "practice_key_mode": MODE_FIXED,
                "fixed_practice_key_family_id": "C major/A minor",
            },
            "practice_state": {
                "practice_focus_section": "Verse",
                "practice_minutes": 45,
            },
        }
        apply_music_disk_state(
            st,
            blob,
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
        self.assertEqual(ss.get("practice_key_mode"), MODE_FIXED)
        self.assertEqual(ss.get("fixed_practice_key_family_id"), "C|A")

    def test_practice_filters_not_clobbered_after_restore(self) -> None:
        ss = {
            PRACTICE_RESTORED_KEY: True,
            "practice_state": {
                "practice_focus_section": "Chorus",
                "practice_minutes": 55,
                "practice_groove_style": "Bossa nova",
            },
            "practice_focus_section": "Intro",
        }
        prepare_practice_page(ss)
        self.assertEqual(ss.get("practice_focus_section"), "Chorus")
        self.assertEqual(ss.get("practice_minutes"), 55)


class TestDeferDefaultSong(unittest.TestCase):
    def test_defer_without_apply_does_not_set_pick_key(self) -> None:
        from active_song_workspace_restore import should_defer_default_master_song_init
        from songs.state import ensure_master_song_initialized

        ss = {
            "_suite_last_cloud_fetch_payload": {
                "core": {"pick_key": "Pop::NonDefault — Artist"},
            }
        }
        self.assertTrue(should_defer_default_master_song_init(ss))
        st = MagicMock()
        st.session_state = ss
        ensure_master_song_initialized(
            st,
            all_records=[{"genre": "Pop", "title": "Say", "artist": "X"}],
            song_library={"Pop": {"Say": {}}},
            song_picker_catalog={"Pop": {"Say — X": {}}},
        )
        self.assertFalse(str(st.session_state.get("active_catalog_pick_key") or "").endswith("Say"))


if __name__ == "__main__":
    unittest.main()

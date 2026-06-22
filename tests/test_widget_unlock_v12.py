"""Tests for music-state-write-gate-v13 — contested writes + reboot guards."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_restore_phase import complete_music_restore_phase, workspace_is_truly_empty
from music_state_writes import WriteOrigin, guarded_session_set, may_write_contested
from songs.music_source import (
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    cpl_session_is_active,
    custom_progression_is_active,
    reconcile_music_picker_source_widget,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, sync_matching_song_dropdown_before_widget


class TestCatalogChoiceEscape(unittest.TestCase):
    def test_user_catalog_choice_overrides_custom_pick_key(self) -> None:
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "active_music_source": "custom_progression",
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        self.assertFalse(custom_progression_is_active(ss))
        self.assertFalse(cpl_session_is_active(ss))

    def test_reconcile_respects_catalog_user_choice(self) -> None:
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "active_music_source": "custom_progression",
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
        }
        complete_music_restore_phase(ss)
        self.assertTrue(reconcile_music_picker_source_widget(ss))
        self.assertEqual(ss["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)
        self.assertTrue(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY))


class TestContestedWriteGate(unittest.TestCase):
    def test_user_writes_always_allowed_after_phase(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: "pop::Stay — Kid"}
        complete_music_restore_phase(ss)
        self.assertTrue(may_write_contested(ss, WriteOrigin.USER, ACTIVE_CATALOG_PICK_KEY))

    def test_default_stamp_blocked_after_phase(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: "pop::Man in the Mirror — Michael Jackson"}
        complete_music_restore_phase(ss)
        self.assertFalse(may_write_contested(ss, WriteOrigin.DEFAULT_STAMP, ACTIVE_CATALOG_PICK_KEY))

    def test_guarded_set_blocks_canonical_overwrite(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: "pop::Man in the Mirror — Michael Jackson"}
        complete_music_restore_phase(ss)
        ok = guarded_session_set(
            ss,
            ACTIVE_CATALOG_PICK_KEY,
            "pop::Stay — Kid",
            origin=WriteOrigin.CANONICAL,
            writer="test",
        )
        self.assertFalse(ok)
        self.assertIn("Man in the Mirror", ss[ACTIVE_CATALOG_PICK_KEY])


class TestWorkspaceEmptyGuard(unittest.TestCase):
    def test_sync_attempted_without_restore_is_not_empty(self) -> None:
        ss = {"_suite_workspace_sync_attempted": True}
        self.assertFalse(workspace_is_truly_empty(ss))

    def test_ephemeral_default_stay_is_empty(self) -> None:
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "pop::Stay — Kid",
            "_music_default_song_ephemeral": True,
        }
        self.assertTrue(workspace_is_truly_empty(ss))


class TestDropdownSyncPreservesLivePick(unittest.TestCase):
    def test_live_pick_injected_when_filtered_out(self) -> None:
        from song_catalog import format_pick_key

        mirror_pk = format_pick_key("pop", "Man in the Mirror — Michael Jackson")
        stay_pk = format_pick_key("pop", "Stay — The Kid LAROI & Justin Bieber")
        ss = {
            ACTIVE_CATALOG_PICK_KEY: mirror_pk,
            "matching_song_dropdown": stay_pk,
        }
        catalog = {
            "pop": {
                "Man in the Mirror — Michael Jackson": {
                    "title": "Man in the Mirror",
                    "artist": "Michael Jackson",
                    "key": "G",
                },
                "Stay — The Kid LAROI & Justin Bieber": {
                    "title": "Stay",
                    "artist": "The Kid LAROI & Justin Bieber",
                    "key": "C",
                },
            }
        }
        options = [stay_pk]
        st = MagicMock()
        st.session_state = ss
        active = sync_matching_song_dropdown_before_widget(
            st,
            options,
            stay_pk,
            song_picker_catalog=catalog,
        )
        self.assertEqual(active, mirror_pk)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], mirror_pk)
        self.assertEqual(options[0], mirror_pk)


class TestActiveSongDirtyPreserve(unittest.TestCase):
    def test_song_edit_save_does_not_clear_dirty(self) -> None:
        from active_song_state import ACTIVE_SONG_DIRTY_KEY, mark_active_song_local_edit
        from music_persistent_state import _clear_canonical_dirty_after_save

        ss: dict = {}
        mark_active_song_local_edit(ss)
        _clear_canonical_dirty_after_save(ss, reason="song_edit")
        self.assertTrue(ss.get(ACTIVE_SONG_DIRTY_KEY))


if __name__ == "__main__":
    unittest.main()

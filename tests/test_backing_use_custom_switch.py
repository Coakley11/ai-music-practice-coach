"""Explicit "Use Custom Progression Backing": real saved Custom only, Composition never altered."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from composition_session_state import COMPOSER_LIBRARY_KEY
from custom_progression_lab import CPL_SAVED_KEY
from songs import music_source as ms

FM = {"id": "fm-1", "name": "Fm Custom", "original_key_center": "Fm", "bpm": 90,
      "original_sections": {"Verse": [{"chord": "Fm", "bars": 1}, {"chord": "Db", "bars": 1}]}}


def _st(**state):
    return SimpleNamespace(session_state=dict(state), rerun=lambda: None)


class TestWhichCustomSongIsOffered(unittest.TestCase):
    def test_only_a_real_saved_record_qualifies(self) -> None:
        ss = {CPL_SAVED_KEY: {"Fm Custom": FM}, ms.LAST_CUSTOM_STATE_KEY: {"active": {"id": "fm-1", "name": "Fm Custom"}}}
        self.assertEqual(ms.last_custom_song_for_backing_switch(ss)["bpm"], 90)

    def test_memory_naming_an_unsaved_or_deleted_song_is_refused(self) -> None:
        ss = {CPL_SAVED_KEY: {}, ms.LAST_CUSTOM_STATE_KEY: {"active": {"id": "x", "name": "Ghost"}}}
        self.assertIsNone(ms.last_custom_song_for_backing_switch(ss))

    def test_no_memory_means_nothing_is_invented(self) -> None:
        self.assertIsNone(ms.last_custom_song_for_backing_switch({CPL_SAVED_KEY: {"Fm Custom": FM}}))

    def test_a_record_without_chords_is_refused(self) -> None:
        empty = dict(FM, original_sections={"Verse": []})
        ss = {CPL_SAVED_KEY: {"Fm Custom": empty}, ms.LAST_CUSTOM_STATE_KEY: {"active": {"id": "fm-1", "name": "Fm Custom"}}}
        self.assertIsNone(ms.last_custom_song_for_backing_switch(ss))


class TestSwitchGuards(unittest.TestCase):
    def test_no_valid_custom_changes_nothing(self) -> None:
        st = _st(**{CPL_SAVED_KEY: {}})
        before = copy.deepcopy(st.session_state)
        with mock.patch.object(ms, "on_song_picker_source_change") as handler:
            self.assertEqual(ms.switch_backing_source_to_custom(st, invalidate_backing=lambda *a, **k: None), "no_custom")
        handler.assert_not_called()
        self.assertEqual(st.session_state, before)

    def test_switch_goes_through_the_songs_source_handler(self) -> None:
        st = _st(**{CPL_SAVED_KEY: {"Fm Custom": FM}, ms.LAST_CUSTOM_STATE_KEY: {"active": {"id": "fm-1", "name": "Fm Custom"}}})
        with mock.patch.object(ms, "on_song_picker_source_change") as handler:
            self.assertEqual(ms.switch_backing_source_to_custom(st, invalidate_backing=lambda *a, **k: None), "switched")
        handler.assert_called_once()
        self.assertEqual(st.session_state[ms.SONG_PICKER_ACTIVE_SOURCE_KEY], ms.SONG_PICKER_SOURCE_CUSTOM)


class TestCompositionIsProtected(unittest.TestCase):
    DOC = {"id": "c-1", "title": "Live Check Song", "key": "E", "form": {"section_order": []}}

    def test_unsaved_edit_is_saved_and_the_document_is_untouched(self) -> None:
        edited = dict(self.DOC, title="Live Check Song (edited)")
        saved = {}
        ss = {COMPOSER_LIBRARY_KEY: {"c-1": dict(self.DOC)}}
        with mock.patch("composition_session_state.get_active_document", return_value=edited), \
             mock.patch("composition_session_state.save_document_to_library",
                        side_effect=lambda s, d, **k: saved.update(d)) as save:
            self.assertTrue(ms.protect_composition_before_source_switch(ss))
        save.assert_called_once()
        self.assertEqual(saved["title"], "Live Check Song (edited)")
        self.assertEqual(edited["title"], "Live Check Song (edited)")

    def test_already_saved_document_is_not_rewritten(self) -> None:
        ss = {COMPOSER_LIBRARY_KEY: {"c-1": dict(self.DOC)}}
        with mock.patch("composition_session_state.get_active_document", return_value=dict(self.DOC)), \
             mock.patch("composition_session_state.save_document_to_library") as save:
            self.assertFalse(ms.protect_composition_before_source_switch(ss))
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()

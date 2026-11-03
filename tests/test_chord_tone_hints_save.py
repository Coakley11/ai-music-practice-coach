"""The Chord Tone Hints choice is saved the moment the Practice checkbox changes.

It used to wait for the end-of-run autosave; a run cut short by the next click (or
a reload right after the click) skipped that save, and under load the choice came
back the other way after a reload.
"""
from __future__ import annotations

import unittest
from unittest import mock

import streamlit as st

import music_persistent_state
import streamlit_music_practice_app as app
from chord_tone_hints import CHORD_TONE_HINTS_KEY


class TestHintsChoiceSavedAtOnce(unittest.TestCase):
    def _toggle(self, on: bool) -> mock.MagicMock:
        st.session_state[app.PRACTICE_TONE_HINTS_WIDGET_KEY] = on
        with mock.patch.object(music_persistent_state, "force_save_music_state", return_value=True) as save:
            app._on_chord_tone_hints_change(app.PRACTICE_TONE_HINTS_WIDGET_KEY)
        return save

    def test_practice_checkbox_on_and_off_save_immediately(self) -> None:
        for on in (True, False, True):
            save = self._toggle(on)
            self.assertIs(st.session_state[CHORD_TONE_HINTS_KEY], on)
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("reason"), "chord_tone_hints")

    def test_a_failed_save_never_breaks_the_toggle(self) -> None:
        st.session_state[app.PRACTICE_TONE_HINTS_WIDGET_KEY] = True
        with mock.patch.object(music_persistent_state, "force_save_music_state", side_effect=OSError("disk")):
            app._on_chord_tone_hints_change(app.PRACTICE_TONE_HINTS_WIDGET_KEY)
        self.assertIs(st.session_state[CHORD_TONE_HINTS_KEY], True)

    def test_the_saved_state_carries_the_choice(self) -> None:
        st.session_state[CHORD_TONE_HINTS_KEY] = True
        state = music_persistent_state.build_music_disk_state(st)
        self.assertIs((state.get("session") or {}).get(CHORD_TONE_HINTS_KEY), True)


def tearDownModule() -> None:
    """Importing the app runs it once in bare mode; leave no session state or cached
    cloud config to later test files."""
    try:
        st.session_state.clear()
    except Exception:
        pass
    from suite_storage_config import reset_cloud_config_cache

    reset_cloud_config_cache()

"""The Backing player carries the "Chord Tone Hints" switch in its header; the old
Backing checkbox is gone; the Practice chart keeps its checkbox."""
from __future__ import annotations

import inspect
import unittest

import streamlit as st

import streamlit_music_practice_app as app


def _player(**kw) -> str:
    return app.live_follow_along_component_html(
        b"", [], "<div class='lead-grid'></div>", audio_url="/app/static/x.wav", **kw
    )


class TestPlayerSwitch(unittest.TestCase):
    def test_switch_in_the_player_header(self) -> None:
        html_ = _player(chord_tone_hints_switch=True)
        head = html_[html_.index("live-player-head"): html_.index("<audio id=\"live-audio\"")]
        self.assertIn("Live Follow-Along Player", head)
        self.assertIn("cth-switch", head)
        self.assertIn(">Chord Tone Hints<", head)

    def test_no_switch_when_not_asked(self) -> None:  # Karaoke
        self.assertNotIn("cth-switch", _player(chord_tone_hints_switch=False))

    def test_same_markup_whatever_the_choice(self) -> None:
        """The switch's state lives in the browser, so the player's HTML never changes with it
        (a changed HTML re-creates the player and stops the music)."""
        st.session_state["chord_tone_hints_on"] = True
        on = _player(chord_tone_hints_switch=True)
        st.session_state["chord_tone_hints_on"] = False
        off = _player(chord_tone_hints_switch=True)
        self.assertEqual(on, off)

    def test_backing_checkbox_removed_practice_kept(self) -> None:
        src = inspect.getsource(app)
        self.assertNotIn("BACKING_TONE_HINTS_WIDGET_KEY", src)
        self.assertIn("_chord_tone_hints_checkbox(PRACTICE_TONE_HINTS_WIDGET_KEY)", src)
        self.assertIn("_sync_chord_tone_hints_from_switch()", src)


def tearDownModule() -> None:
    try:
        st.session_state.clear()
    except Exception:
        pass
    from suite_storage_config import reset_cloud_config_cache

    reset_cloud_config_cache()

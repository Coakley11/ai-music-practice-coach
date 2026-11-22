"""A setting changed while the music plays: playing stays playing, with the new selection.

Measured on a8857bb7 (390 px, isolated data, ordinary Voice, Trial Song playing): the Groove chosen while it played
was kept (no transport Stop, the list usable, the follow held), but the installed take no longer matched the
selection, so the player unmounted and nothing built the new take: silence, the card at "starting" for 30 s+, the
singing panel gone, the server transport still "playing". Only a Play press built takes outside Key Cycling.
"""
from __future__ import annotations

import unittest
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


class PlayingStaysPlaying(unittest.TestCase):
    def test_the_change_marks_a_rebuild_only_while_playing_and_not_for_key_cycling(self) -> None:
        i = APP.index("def _on_backing_filter_change() -> None:")
        body = APP[i:APP.index("\ndef _sync_canonical_practice_after_edit", i)]
        j = body.index('note_playback_settings_changed(st.session_state, reason="backing_filter")')
        k = body.index('st.session_state["_backing_rebuild_while_playing"] = True')
        self.assertLess(j, k)
        self.assertIn('if transport_intent(st.session_state) == "playing" and not _rb_kc_on(st.session_state):', body[j:k])

    def test_the_generate_decision_builds_and_plays_the_new_take(self) -> None:
        i = APP.index("_rebuild_while_playing = bool(")
        block = APP[i:i + 700]
        for cond in ('st.session_state.pop("_backing_rebuild_while_playing", False)',
                     "playback_allowed(st.session_state)",
                     'transport_intent(st.session_state) == "playing"',
                     "not _backing_audio_ready",       # a change that matched the installed take rebuilds nothing
                     "backing_chords"):
            self.assertIn(cond, block)
        decision = APP[APP.index("_play_needs_generate = bool(", i):][:400]
        self.assertIn("or _rebuild_while_playing", decision)
        # the existing generate path then plays it
        self.assertIn("if _play_needs_generate or _karaoke_auto_gen or _cycle_continue_play:\n"
                      "                    st.session_state[BACKING_AUTOPLAY] = True", APP)


if __name__ == "__main__":
    unittest.main()

"""Karaoke display: switching the Lead Sheet during a set must not replace the player.

Measured in the browser (scripts/_accept_karaoke_display.py): before these changes every switch
replaced the performance iframe - the chart was only built with the sheet open, the fold was baked
into the HTML, and opening the sheet armed the normal Backing handoff, which mounted a second
player - so the music stopped or restarted. These pin each cause.
"""
from __future__ import annotations

import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


class TheSwitchChangesNoHTML(unittest.TestCase):
    def test_the_chart_is_built_during_a_set_whatever_the_switch_says(self):
        self.assertIn("if _leadsheet_open or _karaoke_needs_surface:", SRC)

    def test_the_fold_markup_does_not_depend_on_the_switch(self):
        start = SRC.index("_karaoke_hide_chart = bool(")
        block = SRC[start:start + 200]
        self.assertIn("_karaoke_needs_surface", block)
        self.assertNotIn("_leadsheet_open", block)

    def test_the_switch_is_published_beside_the_component(self):
        self.assertIn('class="ks-ls-state" data-ls-open=', SRC)
        self.assertIn("function leadSheetOpenOnPage()", SRC)

    def test_no_handoff_and_no_second_player_during_a_set(self):
        self.assertIn("if open_ and not _in_karaoke_set and not st.session_state.get(\"_backing_transport_user_stopped\"):", SRC)
        start = SRC.index("_sheet_taking_over = bool(")
        self.assertIn("and not _karaoke_needs_surface", SRC[start:start + 200])


class FollowRules(unittest.TestCase):
    def test_lyrics_register_below_the_lead_sheet(self):
        self.assertIn('id: "karaoke-lyrics", priority: 5', SRC)
        self.assertNotIn('id: "lead-sheet", priority: 10, frame: fe, transport: false', SRC)

    def test_sheet_open_follows_chords_closed_follows_lyrics_no_lyrics_follows_chords(self):
        start = SRC.index("function karaokeFollowTarget()")
        body = SRC[start:start + 500]
        self.assertIn("if (chartIsPrimary() || leadSheetOpenOnPage()) return chord;", body)
        self.assertIn(".karaoke-lp-lyric-line.active", body)

    def test_no_timer_of_its_own(self):
        start = SRC.index("function followHeld()")
        self.assertIn("window.top.__lsFollow", SRC[start:start + 300])


if __name__ == "__main__":
    unittest.main()

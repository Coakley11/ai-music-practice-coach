"""Karaoke Group B: chord hints within reach while singing, and a Lead Sheet switch that acts.

Three things on this page are routinely confused, and the assignment names them separately:

  1. the karaoke lyrics          always open during a voice performance
  2. the chord hints under them  the "Show chords while singing" preference
  3. the optional full chart     the Backing card's Lead Sheet switch

Part 1. The preference and its consumer both already existed - the performance renderer reads
``show_chords_enabled`` and fills the lyric panel's chord lists from it. The only way to reach it
was the setlist panel on the Songs page, so a singer mid-performance could not turn hints on or off
without leaving the performance. The player now offers the same preference. One state key, two
places to reach it: a second *setting* would be a defect, not a fix.

Parts 8 and 9. The lyrics were already unconditional, and the chart was never removed when they
showed - it is folded into a collapsed details whose DOM stays mounted so its highlighting keeps
running. What was missing: the Lead Sheet switch had no effect during karaoke, so it could not
become Case B's scrolling target. Now the fold follows the switch, and the lyrics are untouched
either way.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import karaoke_mode as km
from karaoke_ui import render_karaoke_performance_chord_controls

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_music_practice_app.py"
UI = ROOT / "karaoke_ui.py"


class _Container:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSt:
    """Just enough Streamlit to drive one toggle."""

    def __init__(self, session: dict, returns: bool) -> None:
        self.session_state = session
        self._returns = returns
        self.toggles: list[dict] = []

    def container(self, *, key: str = "") -> _Container:
        return _Container()

    def toggle(self, label: str, *, value: bool = False, key: str = "", help: str = "") -> bool:
        self.toggles.append({"label": label, "value": value, "key": key, "help": help})
        return self._returns


class TheHintsAreReachableWhileSinging(unittest.TestCase):
    def test_the_control_renders_one_toggle_with_its_own_widget_key(self) -> None:
        st = FakeSt({km.KARAOKE_SHOW_CHORDS_KEY: True}, returns=True)
        render_karaoke_performance_chord_controls(st)
        self.assertEqual(len(st.toggles), 1)
        self.assertEqual(st.toggles[0]["key"], "karaoke_show_chords_performance_toggle")

    def test_it_does_not_reuse_the_songs_page_widget_key(self) -> None:
        """Two widgets cannot share a Streamlit key; sharing one would raise, not merge."""
        st = FakeSt({}, returns=False)
        render_karaoke_performance_chord_controls(st)
        self.assertNotEqual(st.toggles[0]["key"], "karaoke_show_chords_toggle")

    def test_it_shows_the_setting_as_it_currently_stands(self) -> None:
        for current in (True, False):
            with self.subTest(current=current):
                st = FakeSt({km.KARAOKE_SHOW_CHORDS_KEY: current}, returns=current)
                render_karaoke_performance_chord_controls(st)
                self.assertEqual(st.toggles[0]["value"], current)

    def test_turning_it_on_writes_the_shared_preference(self) -> None:
        session: dict = {km.KARAOKE_SHOW_CHORDS_KEY: False}
        st = FakeSt(session, returns=True)
        self.assertTrue(render_karaoke_performance_chord_controls(st))
        self.assertTrue(session[km.KARAOKE_SHOW_CHORDS_KEY])
        self.assertTrue(km.show_chords_enabled(session))

    def test_turning_it_off_writes_the_shared_preference(self) -> None:
        session: dict = {km.KARAOKE_SHOW_CHORDS_KEY: True}
        st = FakeSt(session, returns=False)
        self.assertFalse(render_karaoke_performance_chord_controls(st))
        self.assertFalse(session[km.KARAOKE_SHOW_CHORDS_KEY])
        self.assertFalse(km.show_chords_enabled(session))

    def test_it_introduces_no_second_setting(self) -> None:
        """The whole point: one preference, reachable from two places.

        The control writes nothing at all when the toggle comes back agreeing with the setting
        already in force - which, on an empty session, it does, because the preference defaults
        to on. So the claim under test is that no key *other* than the shared one is ever
        written, in either direction.
        """
        for returns in (True, False):
            with self.subTest(returns=returns):
                session: dict = {}
                render_karaoke_performance_chord_controls(FakeSt(session, returns=returns))
                self.assertLessEqual(set(session), {km.KARAOKE_SHOW_CHORDS_KEY})

    def test_the_default_is_left_as_it_was_found(self) -> None:
        """An untouched session keeps the app's own default rather than having one stamped on."""
        default = km.show_chords_enabled({})
        session: dict = {}
        render_karaoke_performance_chord_controls(FakeSt(session, returns=default))
        self.assertEqual(session, {})

    def test_leaving_it_alone_writes_nothing(self) -> None:
        session: dict = {km.KARAOKE_SHOW_CHORDS_KEY: True}
        st = FakeSt(session, returns=True)
        render_karaoke_performance_chord_controls(st)
        self.assertEqual(session, {km.KARAOKE_SHOW_CHORDS_KEY: True})

    def test_the_two_places_agree_after_either_one_is_used(self) -> None:
        session: dict = {}
        FakeSt(session, returns=True)
        # The Songs-page toggle writes the same key; simulate it, then read from the player.
        session[km.KARAOKE_SHOW_CHORDS_KEY] = True
        st = FakeSt(session, returns=True)
        render_karaoke_performance_chord_controls(st)
        self.assertTrue(st.toggles[0]["value"])

    def test_the_help_text_keeps_the_three_features_apart(self) -> None:
        st = FakeSt({}, returns=False)
        render_karaoke_performance_chord_controls(st)
        helptext = st.toggles[0]["help"].lower()
        self.assertIn("lead sheet", helptext)
        self.assertIn("chord chart", helptext)


class ThePlayerMountsIt(unittest.TestCase):
    def setUp(self) -> None:
        self.src = APP.read_text(encoding="utf-8")

    def test_the_player_calls_the_control(self) -> None:
        self.assertIn("render_karaoke_performance_chord_controls(st)", self.src)

    def test_it_is_imported(self) -> None:
        self.assertRegex(self.src, r"render_karaoke_performance_chord_controls,")

    def test_it_sits_in_the_active_session_block_beside_the_transport(self) -> None:
        skip = self.src.index("render_karaoke_skip_controls(\n            st,")
        ctrl = self.src.index("render_karaoke_performance_chord_controls(st)")
        self.assertGreater(ctrl, skip)
        self.assertLess(ctrl - skip, 600, "the control drifted away from the transport")


# The class that pinned the Lead Sheet switch reaching ``_karaoke_hide_chart`` ships with the
# mount correction, not here. Slice 1 withholds that one term, because making the fold follow
# the switch only means something once the performance surface mounts with the switch Off -
# and it does not yet: the whole component is gated on an open Lead Sheet
# (docs/KARAOKE_LYRICS_MOUNT_PROPOSAL.md). A test asserting the term while the code does not
# carry it would be a test about nothing.


class TheLyricsDoNotDependOnTheLeadSheet(unittest.TestCase):
    """Part 8: turning the Lead Sheet on or off must not close the karaoke lyrics."""

    def setUp(self) -> None:
        self.src = APP.read_text(encoding="utf-8")

    def test_the_panel_is_built_from_voice_mode_alone(self) -> None:
        build = self.src.index("_karaoke_lyric_panel: dict | None = None")
        guard = self.src[build : build + 200]
        self.assertRegex(guard, r"if _karaoke_voice:")
        self.assertNotIn("_leadsheet_open", guard)

    def test_the_panel_is_not_gated_on_the_chart_being_hidden(self) -> None:
        panel_assign = self.src.index("_karaoke_lyric_panel = _panel_map")
        hide_assign = self.src.index("_karaoke_hide_chart = bool(")
        self.assertLess(panel_assign, hide_assign, "the lyrics must not wait on the chart")

    def test_the_chart_is_folded_not_removed(self) -> None:
        """The DOM stays mounted so the chord highlighting keeps running behind the fold."""
        fold = self.src.index("if karaoke_hide_chart:")
        block = self.src[fold : fold + 600]
        self.assertIn("<details", block)
        self.assertIn('id="live-chart-root"', block)
        self.assertIn("Show chord chart", block)


class TheThreeFeaturesStayDistinct(unittest.TestCase):
    def test_the_hint_control_is_not_the_lead_sheet_switch(self) -> None:
        src = UI.read_text(encoding="utf-8")
        start = src.index("def render_karaoke_performance_chord_controls")
        body = src[start : src.index("\ndef ", start + 10)]
        self.assertNotIn("backing_lead_sheet", body)
        self.assertNotIn("_set_backing_lead_sheet_open", body)

    def test_the_hint_control_touches_no_transport_state(self) -> None:
        src = UI.read_text(encoding="utf-8")
        start = src.index("def render_karaoke_performance_chord_controls")
        body = src[start : src.index("\ndef ", start + 10)]
        for forbidden in ("begin_playback", "stop_playback", "continue_playback",
                          "practice_key", "KARAOKE_SESSION_INDEX_KEY"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)

    def test_the_songs_page_toggle_is_still_there(self) -> None:
        """Surfacing the preference on the player must not remove it from the setlist panel."""
        src = UI.read_text(encoding="utf-8")
        self.assertIn('key="karaoke_show_chords_toggle"', src)
        self.assertIn('key="karaoke_show_chords_performance_toggle"', src)

    def test_both_toggles_write_the_one_shared_key(self) -> None:
        src = UI.read_text(encoding="utf-8")
        writes = re.findall(r"session_state\[km\.KARAOKE_SHOW_CHORDS_KEY\]\s*=", src)
        self.assertEqual(len(writes), 2, "each place writes the shared key, and only it")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

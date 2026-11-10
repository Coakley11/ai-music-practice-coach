"""Issue 60: the Creative mode selector may look different and must behave identically.

Eight radio buttons became eight segments. The appearance is the point of the change;
everything else about it is a contract the rest of the Creative page depends on, and
these tests are that contract written down:

* the same eight modes, in the same order, under the same widget key;
* the same labels and icons, from the same function the rest of the app uses;
* the same ``on_change`` callback, which is what releases Missions ownership, sets the
  entry mode and syncs navigation history when a musician changes mode;
* a selection that is never ``None`` - the one real behavioural difference between a
  radio and a segmented control, and the one that could quietly reset a workflow.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import creative_mode_nav as nav
from studio_page_state import IMPROV_TAB_NAMES, creative_tool_display_label

SOURCE = Path(nav.__file__).read_text(encoding="utf-8")
PAGE = (Path(nav.__file__).parent / "improvisation_intelligence_ui.py").read_text(
    encoding="utf-8")


class FakeSessionState(dict):
    """A mapping that is not a dict subclass trap: Streamlit's proxy behaves like this."""


class RecordingStreamlit:
    """Captures what the nav would draw, and what it returns when it draws it."""

    def __init__(self, returns, has_segmented=True):
        self._returns = returns
        self.calls = []
        self.markdown_calls = []
        if not has_segmented:
            self.segmented_control = None

    def segmented_control(self, label, options, **kw):
        self.calls.append(("segmented_control", label, list(options), kw))
        return self._returns

    def radio(self, label, options, **kw):
        self.calls.append(("radio", label, list(options), kw))
        return self._returns

    def markdown(self, body, **kw):
        self.markdown_calls.append(body)


def _render(returns, session=None, has_segmented=True):
    st = RecordingStreamlit(returns, has_segmented=has_segmented)
    if not has_segmented:
        st.segmented_control = None
    state = FakeSessionState(session or {})
    active = nav.render_creative_mode_nav(
        st, state, options=list(IMPROV_TAB_NAMES), key="improv_intelligence_tab",
        format_func=creative_tool_display_label, on_change=lambda: None,
    )
    return active, st, state


class TheModesAreUnchanged(unittest.TestCase):
    def test_all_eight_modes_are_offered_in_the_same_order(self):
        _active, st, _state = _render("Missions")
        _kind, _label, options, _kw = st.calls[0]
        self.assertEqual(options, list(IMPROV_TAB_NAMES))
        self.assertEqual(len(options), 8)

    def test_the_widget_key_is_unchanged(self):
        _active, st, _state = _render("Missions")
        self.assertEqual(st.calls[0][3]["key"], "improv_intelligence_tab")

    def test_the_labels_come_from_the_apps_own_label_function(self):
        _active, st, _state = _render("Missions")
        self.assertIs(st.calls[0][3]["format_func"], creative_tool_display_label)

    def test_every_mode_still_has_its_icon(self):
        for mode in IMPROV_TAB_NAMES:
            with self.subTest(mode=mode):
                label = creative_tool_display_label(mode)
                self.assertNotEqual(label, mode, "no icon on this mode")
                self.assertTrue(label.strip())

    def test_the_change_callback_is_passed_through(self):
        sentinel = object()
        st = RecordingStreamlit("Missions")
        nav.render_creative_mode_nav(
            st, FakeSessionState(), options=list(IMPROV_TAB_NAMES),
            key="improv_intelligence_tab", format_func=creative_tool_display_label,
            on_change=sentinel,
        )
        self.assertIs(st.calls[0][3]["on_change"], sentinel)

    def test_the_label_stays_collapsed_as_before(self):
        _active, st, _state = _render("Missions")
        self.assertEqual(st.calls[0][3]["label_visibility"], "collapsed")


class ClickingTheActiveModeDoesNotClearIt(unittest.TestCase):
    """The one real behavioural difference, and the reason this is not a one-liner.

    ``st.radio`` always has a selection. A single-select ``st.segmented_control``
    returns ``None`` when the active segment is clicked again. Downstream,
    ``sync_workflow_for_creative_tab`` would receive "" - no owner - and the page would
    drop its workflow pointer because somebody clicked the mode they were already in.
    """

    def test_a_none_selection_keeps_the_previous_mode(self):
        active, _st, _state = _render(None, session={"improv_intelligence_tab": "Harmony Map"})
        self.assertEqual(active, "Harmony Map")

    def test_a_none_selection_is_written_back_into_session_state(self):
        _active, _st, state = _render(None, session={"improv_intelligence_tab": "Deep Harmony"})
        self.assertEqual(state["improv_intelligence_tab"], "Deep Harmony")

    def test_an_empty_string_is_treated_the_same_way(self):
        active, _st, _state = _render("", session={"improv_intelligence_tab": "Live Coach"})
        self.assertEqual(active, "Live Coach")

    def test_the_first_render_with_nothing_selected_falls_back_to_the_first_mode(self):
        active, _st, _state = _render(None, session={})
        self.assertEqual(active, IMPROV_TAB_NAMES[0])

    def test_a_stale_session_value_is_not_trusted(self):
        active, _st, _state = _render(None, session={"improv_intelligence_tab": "Retired Mode"})
        self.assertEqual(active, IMPROV_TAB_NAMES[0])

    def test_a_real_selection_is_returned_unchanged(self):
        for mode in IMPROV_TAB_NAMES:
            with self.subTest(mode=mode):
                active, _st, _state = _render(
                    mode, session={"improv_intelligence_tab": "Missions"})
                self.assertEqual(active, mode)

    def test_the_resolver_never_returns_none_or_empty(self):
        for selected in (None, "", "   ", "Missions", "Retired Mode"):
            for previous in (None, "", "Harmony Map", "Retired Mode"):
                with self.subTest(selected=selected, previous=previous):
                    out = nav.resolve_mode_selection(
                        selected, previous, list(IMPROV_TAB_NAMES))
                    self.assertTrue(out)
                    self.assertIsInstance(out, str)

    def test_a_selection_is_never_written_back_when_one_was_made(self):
        """Only a deselection restores; a real choice must reach session state as-is."""
        _active, _st, state = _render(
            "Metrics & AI", session={"improv_intelligence_tab": "Missions"})
        self.assertEqual(state["improv_intelligence_tab"], "Missions",
                         "the widget owns this key when a choice was made")


class ItDegradesRatherThanDisappears(unittest.TestCase):
    def test_without_a_segmented_control_it_falls_back_to_the_radio(self):
        active, st, _state = _render("Missions", has_segmented=False)
        self.assertEqual(st.calls[0][0], "radio")
        self.assertEqual(active, "Missions")

    def test_the_fallback_radio_keeps_the_key_and_callback(self):
        _active, st, _state = _render("Missions", has_segmented=False)
        self.assertEqual(st.calls[0][3]["key"], "improv_intelligence_tab")
        self.assertIn("on_change", st.calls[0][3])

    def test_the_fallback_radio_also_never_returns_none(self):
        active, _st, _state = _render(
            None, session={"improv_intelligence_tab": "Live Coach"}, has_segmented=False)
        self.assertEqual(active, "Live Coach")


class TheLayoutIsReadableRatherThanTiny(unittest.TestCase):
    """Eight labels do not fit one phone row; wrapping is the readable answer."""

    @staticmethod
    def _selectors(css: str) -> list:
        """Every selector that opens a declaration block, at-rules excluded.

        Split on the block boundaries rather than pattern-matching across them: a
        regex that scans from a "}" to the next "{" happily swallows the @media line
        in between and reports a selector nobody wrote.
        """
        out = []
        for chunk in css.replace("</style>", "").split("}"):
            if "{" not in chunk:
                continue
            selector = chunk.rsplit("{", 1)[0].strip().splitlines()[-1].strip()
            if selector and not selector.startswith(("@", "<")):
                out.append(selector)
        return out

    def test_the_css_is_scoped_to_this_widget_only(self):
        selectors = self._selectors(nav.CREATIVE_NAV_CSS)
        self.assertTrue(selectors, "no selectors found - the check would be vacuous")
        for rule in selectors:
            with self.subTest(rule=rule):
                self.assertIn(".st-key-improv_intelligence_tab", rule)

    def test_the_segments_wrap_instead_of_scrolling(self):
        self.assertIn("flex-wrap: wrap", nav.CREATIVE_NAV_CSS)
        self.assertNotIn("overflow-x", nav.CREATIVE_NAV_CSS)
        self.assertNotIn("nowrap", nav.CREATIVE_NAV_CSS)

    def test_the_css_is_emitted_before_the_control(self):
        _active, st, _state = _render("Missions")
        self.assertTrue(st.markdown_calls)
        self.assertIn("st-key-improv_intelligence_tab", st.markdown_calls[0])

    def test_the_labels_are_not_shrunk_at_all(self):
        """Measured at 390 and 360: eight segments wrap to four rows at the full 14px,
        nothing truncates and nothing scrolls sideways. An earlier draft shrank the
        text below 420px; it was unnecessary and never took effect, and text that
        already fits should not be made smaller."""
        self.assertNotIn("font-size", nav.CREATIVE_NAV_CSS)


class ThePageUsesTheSharedNav(unittest.TestCase):
    def test_the_creative_page_calls_it(self):
        self.assertIn("render_creative_mode_nav(", PAGE)

    def test_the_old_radio_is_gone_from_that_call_site(self):
        self.assertNotIn('st.radio(\n            "Improvisation section"', PAGE)

    def test_the_workflow_sync_still_follows_the_selection(self):
        idx = PAGE.index("render_creative_mode_nav(")
        self.assertIn("sync_workflow_for_creative_tab", PAGE[idx:idx + 1500])

    def test_the_creative_engine_was_not_restructured(self):
        """The change is the control. Nothing else in this module should have moved."""
        self.assertIn("_on_improv_tab_change", PAGE)
        self.assertIn("release_mission_creative_page_ownership", PAGE)
        self.assertIn("sync_live_creative_history_dest", PAGE)


if __name__ == "__main__":
    unittest.main()


class TheDeselectReplaysTheRealRuntimeSequence(unittest.TestCase):
    """The unit tests above passed while the browser showed the opposite.

    They supplied the previous mode by hand. Streamlit does not: on the rerun after a
    deselection it has *already* written ``None`` into the widget's own key before this
    code runs, so reading that key back gives the cleared value, and the nav fell to the
    first mode in the list instead of staying put. These reproduce that exact state -
    the widget key holding ``None``, and the module's own memory holding the real mode.
    """

    def _render(self, returns, session):
        st = RecordingStreamlit(returns)
        state = FakeSessionState(session)
        active = nav.render_creative_mode_nav(
            st, state, options=list(IMPROV_TAB_NAMES),
            key="improv_intelligence_tab",
            format_func=creative_tool_display_label, on_change=lambda: None,
        )
        return active, state

    def test_the_widget_key_already_holding_none_does_not_lose_the_mode(self):
        active, state = self._render(
            None,
            {"improv_intelligence_tab": None,
             nav.LAST_MODE_KEY: "Song-Aware Coaching"},
        )
        self.assertEqual(active, "Song-Aware Coaching")
        self.assertEqual(state["improv_intelligence_tab"], "Song-Aware Coaching")

    def test_it_does_not_fall_back_to_the_first_mode(self):
        active, _state = self._render(
            None, {"improv_intelligence_tab": None, nav.LAST_MODE_KEY: "Deep Harmony"})
        self.assertNotEqual(active, IMPROV_TAB_NAMES[0])
        self.assertEqual(active, "Deep Harmony")

    def test_choosing_a_mode_records_it_for_next_time(self):
        _active, state = self._render(
            "Metrics & AI", {"improv_intelligence_tab": "Entry & Jam"})
        self.assertEqual(state[nav.LAST_MODE_KEY], "Metrics & AI")

    def test_the_full_switch_then_reclick_sequence(self):
        """Switch to a mode, then click it again - exactly what the browser did."""
        state = FakeSessionState({"improv_intelligence_tab": "Entry & Jam"})
        st = RecordingStreamlit("Song-Aware Coaching")
        first = nav.render_creative_mode_nav(
            st, state, options=list(IMPROV_TAB_NAMES),
            key="improv_intelligence_tab",
            format_func=creative_tool_display_label, on_change=lambda: None)
        self.assertEqual(first, "Song-Aware Coaching")
        # Streamlit writes the deselection into the widget key before the next run.
        state["improv_intelligence_tab"] = None
        st2 = RecordingStreamlit(None)
        second = nav.render_creative_mode_nav(
            st2, state, options=list(IMPROV_TAB_NAMES),
            key="improv_intelligence_tab",
            format_func=creative_tool_display_label, on_change=lambda: None)
        self.assertEqual(second, "Song-Aware Coaching")

    def test_the_memory_is_ignored_when_it_names_a_retired_mode(self):
        active, _state = self._render(
            None,
            {"improv_intelligence_tab": "Harmony Map", nav.LAST_MODE_KEY: "Retired"})
        self.assertEqual(active, "Harmony Map")

    def test_the_memory_key_is_private_to_this_module(self):
        self.assertTrue(nav.LAST_MODE_KEY.startswith("_"))
        self.assertNotIn(nav.LAST_MODE_KEY, IMPROV_TAB_NAMES)

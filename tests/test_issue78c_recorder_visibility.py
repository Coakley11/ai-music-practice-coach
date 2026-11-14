"""Issue 78C - the Record control must be visible, not merely present in the DOM.

The recorder is mounted inside the per-layer expander, which is collapsed exactly while the layer is
empty. A hidden iframe has no layout, so ``document.body.scrollHeight`` reads 0; the component
published ``0 + 4`` and Streamlit sized the frame at four pixels. Opening the expander is pure
client-side DOM, so no further render arrived and nothing re-measured: the frame stayed four pixels
tall, showing the top sliver of a red button and hiding the control, the count-in label and every
error message the component can produce.

These tests pin the contract that prevents it. Whether the pixels really land on screen is measured
by ``scripts/_accept_issue78c_visibility.py`` in a browser - that is the only place it can be
measured, and the lesson of this defect is that a bounding box inside the iframe is not evidence.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from multitrack_takes import (  # noqa: E402
    AUTO_OPEN_DECIDED_KEY,
    AUTO_OPEN_SLOT_KEY,
    auto_open_slot,
)

COMPONENT = (ROOT / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
SLOTS = ["guitar", "sax / winds", "extra layer"]


class TheFrameNeverCollapses(unittest.TestCase):
    def test_a_minimum_height_is_published(self) -> None:
        self.assertIn("const MIN_FRAME_H = 52;", COMPONENT)
        self.assertIn("Math.max(MIN_FRAME_H, lastSentHeight)", COMPONENT)

    def test_a_zero_measurement_is_not_treated_as_a_height(self) -> None:
        block = COMPONENT[COMPONENT.index("function measuredHeight()"):COMPONENT.index("function setHeight()")]
        self.assertIn("if (raw <= 0) return null;", block)

    def test_the_floor_is_at_least_a_touch_target(self) -> None:
        match = re.search(r"const MIN_FRAME_H = (\d+);", COMPONENT)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 44, "a shorter frame is not tappable")

    def test_the_height_is_only_published_when_it_changes(self) -> None:
        block = COMPONENT[COMPONENT.index("function setHeight()"):COMPONENT.index("function stopHeightPoll()")]
        self.assertIn("if (next === lastSentHeight) return;", block)

    def test_the_component_rewatches_when_it_becomes_visible(self) -> None:
        self.assertIn("new ResizeObserver(() => setHeight()).observe(document.body)", COMPONENT)
        self.assertIn('window.addEventListener("resize", setHeight)', COMPONENT)
        self.assertIn('document.addEventListener("visibilitychange", setHeight)', COMPONENT)

    def test_there_is_a_fallback_for_browsers_without_resizeobserver(self) -> None:
        self.assertIn("function startHeightPoll()", COMPONENT)
        self.assertIn("setInterval(", COMPONENT)

    def test_the_fallback_stops_itself(self) -> None:
        # A permanent 500 ms timer in every layer's iframe would be a cost with no end.
        block = COMPONENT[COMPONENT.index("function startHeightPoll()"):COMPONENT.index("function watchHeight()")]
        self.assertIn("stopHeightPoll()", block)
        self.assertIn("ticks > 40", block)

    def test_each_render_rearms_the_watch(self) -> None:
        # A layer can be collapsed and reopened later, and the reopening sends no render either.
        listener = COMPONENT[COMPONENT.index('event.data.type !== "streamlit:render"'):]
        self.assertIn("startHeightPoll();", listener[:400])

    def test_the_watch_is_started_at_init(self) -> None:
        tail = COMPONENT[COMPONENT.index('send("streamlit:componentReady"'):]
        self.assertIn("setHeight();", tail)
        self.assertIn("watchHeight();", tail)

    def test_the_record_button_is_in_the_static_html(self) -> None:
        # It always was, which is why a collapsed frame showed a red sliver rather than nothing:
        # the button needs no JavaScript to exist, only a frame tall enough to show it.
        self.assertIn('<button id="rec" type="button"', COMPONENT)

    def test_nothing_about_capture_or_scheduling_changed(self) -> None:
        for anchor in (
            'new AudioWorkletNode(c, "mission-capture"',
            "const lead = 0.25;",
            "const musicStart = countInStart + countInSec;",
            "s.start(musicStart + entry.asset.startDelay, offset);",
            "monitors_expected: r.monitorsExpected",
        ):
            self.assertIn(anchor, COMPONENT, anchor)


class AMicrophoneFailureStaysOnScreenAndMakesSense(unittest.TestCase):
    """The explanation must survive the next render, and be actionable."""

    def test_the_failure_is_remembered_across_renders(self) -> None:
        self.assertIn("let lastMicError", COMPONENT)
        self.assertIn('if (lastMicError) { status(lastMicError); return; }', COMPONENT)

    def test_it_is_cleared_once_recording_really_starts(self) -> None:
        self.assertIn('lastMicError = "";', COMPONENT)

    def test_the_common_failures_are_named_in_plain_words(self) -> None:
        block = COMPONENT[COMPONENT.index("function micFailureMessage"):COMPONENT.index("async function start()")]
        for name in ("NotAllowedError", "SecurityError", "NotFoundError", "NotReadableError"):
            self.assertIn(name, block)
        self.assertIn("navigator.mediaDevices", block)

    def test_every_failure_offers_the_truthful_alternative(self) -> None:
        block = COMPONENT[COMPONENT.index("function micFailureMessage"):COMPONENT.index("async function start()")]
        # Upload really is available on this surface, so it is an honest alternative to offer.
        self.assertEqual(block.count("Upload above"), 5)

    def test_an_unknown_failure_still_reports_its_detail(self) -> None:
        block = COMPONENT[COMPONENT.index("function micFailureMessage"):COMPONENT.index("async function start()")]
        self.assertIn("could not be started: \" + detail", block)

    def test_no_raw_exception_is_shown_as_the_whole_message(self) -> None:
        self.assertNotIn('status("Microphone unavailable: " + e)', COMPONENT)


class OneEmptyLayerOpensSoTheControlIsFound(unittest.TestCase):
    def test_the_first_empty_layer_is_chosen(self) -> None:
        state: dict = {"mt_tracks": {}}
        self.assertEqual(auto_open_slot(state, SLOTS), "guitar")

    def test_nothing_opens_when_every_layer_is_recorded(self) -> None:
        state: dict = {"mt_tracks": {s: b"x" for s in SLOTS}}
        self.assertEqual(auto_open_slot(state, SLOTS), "")

    def test_only_one_layer_is_chosen(self) -> None:
        # Opening every empty layer would make the phone page enormous.
        state: dict = {"mt_tracks": {}}
        chosen = {auto_open_slot(state, SLOTS) for _ in SLOTS}
        self.assertEqual(chosen, {"guitar"})

    def test_the_layer_stays_open_across_reruns_while_the_project_is_empty(self) -> None:
        # Streamlit re-applies `expanded` on EVERY rerun. Deciding once and then returning ""
        # meant the second render passed expanded=False and the layer the musician had just been
        # given closed itself - the acceptance caught it as a tap timing out on a vanishing
        # control, with open:false recorded a moment later.
        state: dict = {"mt_tracks": {}}
        self.assertEqual(auto_open_slot(state, SLOTS), "guitar")
        self.assertEqual(auto_open_slot(state, SLOTS), "guitar")
        self.assertEqual(auto_open_slot(state, SLOTS), "guitar")
        self.assertEqual(state[AUTO_OPEN_SLOT_KEY], "guitar")

    def test_it_stops_as_soon_as_any_layer_holds_a_take(self) -> None:
        # Then the musician is working and knows where the controls are; nothing should fight
        # their own collapses.
        state: dict = {"mt_tracks": {"guitar": b"x"}}
        self.assertEqual(auto_open_slot(state, SLOTS), "")
        self.assertTrue(state[AUTO_OPEN_DECIDED_KEY])

    def test_a_missing_or_odd_track_map_does_not_crash(self) -> None:
        for state in ({}, {"mt_tracks": None}, {"mt_tracks": []}):
            self.assertIsInstance(auto_open_slot(dict(state), SLOTS), str)

    def test_no_slots_means_nothing_to_open(self) -> None:
        self.assertEqual(auto_open_slot({"mt_tracks": {}}, []), "")

    def test_the_page_uses_the_rule_for_the_layer_expander(self) -> None:
        self.assertIn("from multitrack_takes import auto_open_slot", APP)
        self.assertIn("_mt_auto_open = auto_open_slot(st.session_state, MT_SLOTS)", APP)
        self.assertIn('st.expander(f"Layer controls — {slot}", expanded=_slot_expanded)', APP)

    def test_a_recorded_layer_still_opens_as_it_always_did(self) -> None:
        self.assertIn("_slot_expanded = _slot_ready or (slot == _mt_auto_open", APP)


class TheHarnessMeasuresWhatAHumanSees(unittest.TestCase):
    """The defect survived 52/52 and 65/65 because the old gates could not see clipping."""

    def test_the_acceptance_measures_the_iframe_not_its_contents(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("f.getBoundingClientRect()", harness)
        self.assertIn("document.elementFromPoint(px, py)", harness)
        self.assertIn("button_inside_frame", harness)
        self.assertIn("status_inside_frame", harness)

    def test_the_acceptance_uses_real_pointer_input(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        # Real pointer input for the page, and a real TOUCH tap through the frame for the control.
        # Locator.tap dispatches a touch event and additionally runs the browser's own
        # actionability checks - visible, stable, able to receive the event - which is a stronger
        # guarantee than computing a point and hoping, and it raises when the control is not usable.
        self.assertIn("page.mouse.click(", harness)
        self.assertIn("loc.tap(timeout=", harness)
        self.assertIn("frame_locator(frame_selector(slot))", harness)
        # No programmatic element.click() as evidence that a control works: that is precisely what
        # certified a four-pixel recorder.
        self.assertNotIn("getElementById('rec').click()", harness)

    def test_the_acceptance_asks_the_browser_whether_the_button_is_visible(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("def button_is_visible_to_playwright", harness)
        self.assertIn("loc.is_visible(timeout=", harness)

    def test_the_screenshots_use_page_coordinates(self) -> None:
        # getBoundingClientRect is viewport-relative and screenshot clips are page-relative, so
        # without the scroll offset the evidence photographs the wrong part of the page.
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn('window.scrollX, y: window.scrollY', harness)
        self.assertIn('float(scroll["y"])', harness)

    def test_the_acceptance_requires_a_touchable_height(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("MIN_TOUCH_PX", harness)

    def test_the_acceptance_judges_the_microphone_message_not_just_its_length(self) -> None:
        # The run before this one reported PASS for "the recorder explains the microphone being
        # denied" while the component was showing its READY text, and PASS for "unavailable" while
        # it was showing "TypeError: Cannot read properties of undefined". Both passed because the
        # gate asked `bool(said.strip())`.
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("def mic_message_verdict", harness)
        self.assertIn("ok_msg, why = mic_message_verdict(label, said)", harness)
        self.assertNotIn("bool(said.strip()), said[:120]", harness)

    def test_the_acceptance_exercises_the_whole_take_lifecycle(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        for gate in ("Discard take can be pressed", "discarding really removes the take",
                     "a second take can be recorded after a discard", "Save layer can be pressed",
                     "the layer is saved and says so"):
            self.assertIn(gate, harness)

    def test_the_acceptance_measures_sideways_overflow_on_a_fresh_load(self) -> None:
        # Resizing one page from 1400 to 390 to 360 leaves components sized for the width they were
        # first laid out at, which invented a 7 px overhang at 360 px that a page loaded at 360 px
        # does not have. A phone loads at its own width, so that is where the gate belongs.
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("def horizontal_overflow", harness)
        self.assertIn("def fresh_width_checks", harness)
        self.assertIn("nothing is clipped off the side", harness)

    def test_a_known_pre_existing_failure_is_reported_not_hidden(self) -> None:
        # Discard take does not remove the take - on dev f3d33016 as much as here. Dropping the
        # gate would hide a real defect; letting it fail this slice would blame it on Issue 78C.
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("KNOWN_PREEXISTING", harness)
        self.assertIn("[390px] discarding really removes the take", harness)
        # The gate must still be evaluated, and the run's verdict must ignore only known entries.
        self.assertIn("real = sorted(n for n, ok in GATES.items()", harness)
        self.assertIn("return 0 if not real else 1", harness)

    def test_the_acceptance_checks_missions_copy_of_the_component(self) -> None:
        harness = (ROOT / "scripts" / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        self.assertIn("def mission_recorder_frame", harness)
        # It gates when Mission is reached, and when it cannot be reached it says so instead of
        # either failing for an unrelated reason or quietly implying it was checked.
        self.assertIn("Mission's recorder still mounts and is visible", harness)
        self.assertIn("was NOT reached in the browser this run", harness)


class TheMicrophoneMessageRulesRejectWhatReachedTheMusician(unittest.TestCase):
    """The two strings the previous acceptance run passed, and the ones that replaced them."""

    @staticmethod
    def _verdict(label: str, text: str):
        scripts = ROOT / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_i78c_rules", scripts / "_accept_issue78c_visibility.py"
        )
        # The harness reads sys.argv and imports Playwright at module scope, so the rule is lifted
        # out of the source rather than imported. Keeping the two in step is what the test above is
        # for.
        src = (scripts / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")
        start = src.index("READY_TEXT_MARKERS")
        end = src.index("def horizontal_overflow")
        ns: dict = {"low": lambda x: (x or "").lower()}
        exec(compile(src[start:end], "mic_rules", "exec"), ns)  # noqa: S102
        del spec
        return ns["mic_message_verdict"](label, text)

    def test_the_ready_text_is_not_an_explanation(self) -> None:
        ok, why = self._verdict(
            "denied",
            "Record starts a 4-beat count-in and your other layer together with your take, "
            "on one clock.",
        )
        self.assertFalse(ok)
        self.assertIn("READY", why)

    def test_a_stack_trace_is_not_an_explanation(self) -> None:
        ok, why = self._verdict(
            "unavailable",
            "Microphone unavailable: TypeError: Cannot read properties of undefined "
            "(reading 'getSupportedConstraints')",
        )
        self.assertFalse(ok)
        self.assertIn("stack trace", why)

    def test_silence_is_not_an_explanation(self) -> None:
        ok, _ = self._verdict("denied", "   ")
        self.assertFalse(ok)

    def test_a_message_with_no_alternative_is_rejected(self) -> None:
        ok, why = self._verdict("denied", "Microphone permission was refused.")
        self.assertFalse(ok)
        self.assertIn("alternative", why)

    def test_the_real_messages_pass(self) -> None:
        for label, text in (
            ("denied",
             "Microphone permission was refused, so nothing can be recorded. Allow microphone "
             "access for this site in your browser settings and press Record again - or add this "
             "layer with Upload above."),
            ("unavailable",
             "This browser will not give the page a microphone. Recording needs a recent Chrome, "
             "Safari or Firefox over https - you can still add this layer with Upload above."),
        ):
            ok, why = self._verdict(label, text)
            self.assertTrue(ok, f"{label}: {why}")


if __name__ == "__main__":
    unittest.main()

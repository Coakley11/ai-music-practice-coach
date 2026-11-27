"""Propose, Preview, Accept, Save/Reopen, Undo and Restore - for both editing scopes.

Each step is checked on its own, and separately for an entire-section edit and a single-pass
edit, because the promise differs: an entire-section edit may change everything, a pass edit
may change exactly one pass and must leave the others identical through the whole cycle -
including after the document has been saved and reopened.

The accepted melody is the thing being protected. A proposal that reaches it before the
musician accepts is the failure these are written to catch.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import composition_melody_passes as mp
from composition_document import (
    apply_melody_events,
    new_composition_document,
    ordered_sections,
    section_by_id,
)
from composition_melody_engine import build_concept_events
from composition_melody_repeats import expand_melody_events_by_repeats
from composition_melody_shape import propose_melody_refinement, timeline_span
from composition_preview import generate_preview_wav

FOUR = ["D", "Bm", "G", "A"]
EIGHT = FOUR + FOUR
BPM = 96


def refine(rid: str):
    return lambda evs: propose_melody_refinement(evs, rid, key="D").get("events") or evs


def built() -> tuple[dict, str]:
    doc = new_composition_document(title="Scope lifecycle")
    doc["global"]["bpm"] = BPM
    doc["global"]["time_signature"] = "4/4"
    doc["global"]["key_center"] = "D"
    sec = ordered_sections(doc)[0]
    sec["chords"] = [{"chord": c, "beats": 4} for c in EIGHT]
    sid = str(sec["id"])
    tiled = expand_melody_events_by_repeats(
        build_concept_events("direct_line", FOUR, key="D", meter="4/4"), 2
    )
    apply_melody_events(doc, sid, tiled)
    return doc, sid


def accepted(doc: dict, sid: str) -> list[dict]:
    sec = section_by_id(doc, sid)
    return list((sec.get("melody") or {}).get("events") or [])


def shape(events, index) -> list[tuple]:
    return [
        (round(float(e.get("beat") or 0), 4), str(e.get("pitch")), float(e.get("duration_beats") or 0))
        for e in mp.events_in_pass(events, index)
    ]


def reopened(doc: dict) -> dict:
    """What a Save followed by a Reopen gives back: the document through JSON."""
    return json.loads(json.dumps(doc))


class TestProposingDoesNotTouchTheAcceptedMelody(unittest.TestCase):
    def test_an_entire_section_proposal_leaves_it_alone(self) -> None:
        doc, sid = built()
        before = copy.deepcopy(accepted(doc, sid))
        mp.apply_to_scope(accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ENTIRE)
        self.assertEqual(accepted(doc, sid), before)

    def test_a_pass_proposal_leaves_it_alone(self) -> None:
        doc, sid = built()
        before = copy.deepcopy(accepted(doc, sid))
        mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        self.assertEqual(accepted(doc, sid), before)

    def test_a_copy_proposal_leaves_it_alone(self) -> None:
        doc, sid = built()
        before = copy.deepcopy(accepted(doc, sid))
        mp.copy_pass(accepted(doc, sid), 0, [1], chords=EIGHT, key="D", meter="4/4")
        self.assertEqual(accepted(doc, sid), before)

    def test_a_restore_proposal_leaves_it_alone(self) -> None:
        doc, sid = built()
        edited = mp.apply_to_scope(
            accepted(doc, sid), refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        before = copy.deepcopy(accepted(doc, sid))
        mp.restore_pass(edited, accepted(doc, sid), 1)
        self.assertEqual(accepted(doc, sid), before)


class TestPreviewing(unittest.TestCase):
    """Preview plays the proposal; it must not install it."""

    def _preview(self, doc, sid, events):
        return generate_preview_wav(
            doc,
            section_id=sid,
            loops=1,
            include_melody=True,
            melody_override=list(events),
            chord_override=EIGHT,
        )

    def test_an_entire_section_proposal_can_be_heard(self) -> None:
        doc, sid = built()
        prop = mp.apply_to_scope(accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ENTIRE)
        self.assertTrue(self._preview(doc, sid, prop))

    def test_a_pass_proposal_can_be_heard(self) -> None:
        doc, sid = built()
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        self.assertTrue(self._preview(doc, sid, prop))

    def test_previewing_does_not_install_the_proposal(self) -> None:
        doc, sid = built()
        before = copy.deepcopy(accepted(doc, sid))
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        self._preview(doc, sid, prop)
        self.assertEqual(accepted(doc, sid), before)

    def test_the_preview_is_as_long_as_the_section(self) -> None:
        """A pass edit must not shorten what you hear."""
        doc, sid = built()
        full = self._preview(doc, sid, accepted(doc, sid))
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        edited = self._preview(doc, sid, prop)
        self.assertAlmostEqual(len(edited), len(full), delta=len(full) * 0.05)


class TestAcceptingThenSavingAndReopening(unittest.TestCase):
    def test_an_entire_section_edit_survives_the_round_trip(self) -> None:
        doc, sid = built()
        prop = mp.apply_to_scope(accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ENTIRE)
        apply_melody_events(doc, sid, prop, replace=True)
        self.assertEqual(accepted(reopened(doc), sid), accepted(doc, sid))

    def test_a_pass_edit_survives_the_round_trip(self) -> None:
        doc, sid = built()
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, prop, replace=True)
        back = accepted(reopened(doc), sid)
        self.assertEqual(back, accepted(doc, sid))

    def test_the_untouched_pass_is_identical_after_reopening(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, prop, replace=True)
        back = accepted(reopened(doc), sid)
        self.assertEqual(shape(back, 0), shape(original, 0))
        self.assertNotEqual(shape(back, 1), shape(original, 1))

    def test_the_section_keeps_its_length_through_the_round_trip(self) -> None:
        doc, sid = built()
        for scope, idx in ((mp.SCOPE_ENTIRE, 0), (mp.SCOPE_ONE_PASS, 1)):
            fresh, fsid = built()
            span = timeline_span(accepted(fresh, fsid))
            prop = mp.apply_to_scope(
                accepted(fresh, fsid), refine("simplify"), scope=scope, pass_index=idx
            )
            apply_melody_events(fresh, fsid, prop, replace=True)
            with self.subTest(scope=scope):
                self.assertAlmostEqual(
                    timeline_span(accepted(reopened(fresh), fsid)), span, places=2
                )

    def test_rests_survive_the_round_trip(self) -> None:
        doc, sid = built()
        with_rest = expand_melody_events_by_repeats(
            [
                {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 3.0, "is_rest": False},
                {"pitch": "rest", "midi": None, "beat": 3.0, "duration_beats": 1.0,
                 "is_rest": True},
                {"pitch": "A4", "midi": 69, "beat": 4.0, "duration_beats": 12.0,
                 "is_rest": False},
            ],
            2,
        )
        apply_melody_events(doc, sid, with_rest, replace=True)
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, prop, replace=True)
        back = accepted(reopened(doc), sid)
        self.assertTrue(any(e.get("is_rest") for e in mp.events_in_pass(back, 0)))
        self.assertTrue(any(e.get("is_rest") for e in mp.events_in_pass(back, 1)))


class TestUndoingAnAcceptedEdit(unittest.TestCase):
    """Undo is "put back what was accepted before", for either scope."""

    def test_an_entire_section_edit_can_be_undone(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        prop = mp.apply_to_scope(accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ENTIRE)
        apply_melody_events(doc, sid, prop, replace=True)
        apply_melody_events(doc, sid, original, replace=True)
        self.assertEqual(shape(accepted(doc, sid), 0), shape(original, 0))
        self.assertEqual(shape(accepted(doc, sid), 1), shape(original, 1))

    def test_a_pass_edit_can_be_undone(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, prop, replace=True)
        apply_melody_events(doc, sid, original, replace=True)
        self.assertEqual(accepted(doc, sid), original)

    def test_undo_after_a_reopen_still_works(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        prop = mp.apply_to_scope(
            accepted(doc, sid), refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=0
        )
        apply_melody_events(doc, sid, prop, replace=True)
        fresh = reopened(doc)
        apply_melody_events(fresh, sid, original, replace=True)
        self.assertEqual(shape(accepted(fresh, sid), 0), shape(original, 0))


class TestRestoringOnePassInTheLifecycle(unittest.TestCase):
    def test_restoring_pass_two_keeps_accepted_work_on_pass_one(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))

        first = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0
        )
        apply_melody_events(doc, sid, first, replace=True)
        after_pass_one = copy.deepcopy(accepted(doc, sid))

        second = mp.apply_to_scope(
            accepted(doc, sid), refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, second, replace=True)

        back = mp.restore_pass(accepted(doc, sid), original, 1)
        apply_melody_events(doc, sid, back, replace=True)

        self.assertEqual(shape(accepted(doc, sid), 0), shape(after_pass_one, 0))
        self.assertEqual(shape(accepted(doc, sid), 1), shape(original, 1))

    def test_a_restored_pass_survives_save_and_reopen(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        edited = mp.apply_to_scope(
            accepted(doc, sid), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        apply_melody_events(doc, sid, edited, replace=True)
        back = mp.restore_pass(accepted(doc, sid), original, 1)
        apply_melody_events(doc, sid, back, replace=True)
        self.assertEqual(shape(accepted(reopened(doc), sid), 1), shape(original, 1))

    def test_the_section_is_never_left_looking_truncated(self) -> None:
        doc, sid = built()
        original = copy.deepcopy(accepted(doc, sid))
        for rid, _label, _why in [("simplify", "", ""), ("energetic", "", "")]:
            fresh, fsid = built()
            prop = mp.apply_to_scope(
                accepted(fresh, fsid), refine(rid), scope=mp.SCOPE_ONE_PASS, pass_index=1
            )
            apply_melody_events(fresh, fsid, prop, replace=True)
            report = mp.coverage_report(accepted(reopened(fresh), fsid), EIGHT, meter="4/4")
            with self.subTest(refinement=rid):
                self.assertNotEqual(report["verdict"], "truncated", report["message"])
        self.assertTrue(original)


if __name__ == "__main__":
    unittest.main()

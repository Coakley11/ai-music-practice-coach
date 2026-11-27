"""Entire Section versus One Pass editing.

The thing being pinned is a promise to the musician: an edit does what the visible scope says
it does, and nothing else. A pass edit must leave every other pass exactly as it was - not
"close enough", byte-identical - and the section must keep its length either way, because the
chords define that length and the melody does not get to change it.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import composition_melody_passes as mp
from composition_melody_engine import build_concept_events
from composition_melody_repeats import EDIT_SCOPE_ALL, expand_melody_events_by_repeats
from composition_melody_shape import MELODY_REFINEMENTS, propose_melody_refinement, timeline_span

FOUR_BARS = ["D", "Bm", "G", "A"]
#: The second pass borrows different harmony, which is where a blindly copied phrase goes wrong.
EIGHT_BARS_VARIED = ["D", "Bm", "G", "A", "D", "F#m", "Bm", "E"]


def one_pass() -> list[dict]:
    return build_concept_events("direct_line", FOUR_BARS, key="D", meter="4/4")


def tiled(n: int = 2) -> list[dict]:
    return expand_melody_events_by_repeats(one_pass(), n)


def shape(events, index) -> list[tuple]:
    """A pass's content as plain comparable values."""
    return [
        (round(float(e.get("beat") or 0), 4), str(e.get("pitch")), float(e.get("duration_beats") or 0))
        for e in mp.events_in_pass(events, index)
    ]


def refine(rid: str):
    return lambda evs: propose_melody_refinement(evs, rid, key="D").get("events") or evs


class TestFindingThePasses(unittest.TestCase):
    def test_a_melody_that_does_not_repeat_is_one_pass(self) -> None:
        self.assertEqual(mp.pass_count(one_pass()), 1)

    def test_tiled_melodies_report_their_passes(self) -> None:
        for n in (2, 3, 4):
            with self.subTest(passes=n):
                self.assertEqual(mp.pass_count(tiled(n)), n)

    def test_each_pass_is_the_same_length(self) -> None:
        evs = tiled(4)
        self.assertAlmostEqual(mp.pass_span_beats(evs), 16.0, places=2)
        self.assertAlmostEqual(timeline_span(evs), 64.0, places=2)

    def test_the_passes_tile_the_section_without_gap_or_overlap(self) -> None:
        evs = tiled(4)
        bounds = [mp.pass_bounds(evs, i) for i in range(4)]
        self.assertEqual(bounds[0][0], 0.0)
        for a, b in zip(bounds, bounds[1:]):
            self.assertAlmostEqual(a[1], b[0], places=3)
        self.assertAlmostEqual(bounds[-1][1], timeline_span(evs), places=2)

    def test_every_event_belongs_to_exactly_one_pass(self) -> None:
        evs = tiled(3)
        counted = sum(len(mp.events_in_pass(evs, i)) for i in range(3))
        self.assertEqual(counted, len(evs))

    def test_an_index_past_the_end_has_no_events(self) -> None:
        self.assertEqual(mp.events_in_pass(tiled(2), 5), [])


class TestTheScopeIsVisible(unittest.TestCase):
    """A scope the musician cannot read is a scope they cannot trust."""

    def test_entire_section_is_the_default(self) -> None:
        self.assertEqual(mp.SCOPE_ENTIRE, "entire_section")
        self.assertEqual(mp.LEGACY_SCOPE[mp.SCOPE_ENTIRE], EDIT_SCOPE_ALL)

    def test_the_caption_names_the_pass_and_the_total(self) -> None:
        said = mp.scope_caption(mp.SCOPE_ONE_PASS, 1, 2)
        self.assertIn("pass 2 of 2", said)
        self.assertIn("other passes stay", said)

    def test_the_caption_says_how_many_passes_a_section_edit_covers(self) -> None:
        self.assertIn("all 3 passes", mp.scope_caption(mp.SCOPE_ENTIRE, 0, 3))

    def test_a_single_pass_section_does_not_talk_about_passes(self) -> None:
        self.assertNotIn("pass", mp.scope_caption(mp.SCOPE_ENTIRE, 0, 1).lower())

    def test_both_scopes_have_a_label(self) -> None:
        for scope in (mp.SCOPE_ENTIRE, mp.SCOPE_ONE_PASS):
            self.assertTrue(mp.SCOPE_LABELS.get(scope))


class TestEntireSectionEditing(unittest.TestCase):
    def test_it_reaches_every_pass(self) -> None:
        evs = tiled(2)
        out = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ENTIRE)
        self.assertLess(len(out), len(evs))

    def test_it_keeps_the_section_length(self) -> None:
        evs = tiled(2)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = mp.apply_to_scope(evs, refine(rid), scope=mp.SCOPE_ENTIRE)
            with self.subTest(refinement=rid):
                self.assertGreaterEqual(timeline_span(out), timeline_span(evs) - 0.01)


class TestOnePassEditing(unittest.TestCase):
    def test_editing_a_later_pass_leaves_the_earlier_one_identical(self) -> None:
        evs = tiled(2)
        before = shape(evs, 0)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = mp.apply_to_scope(evs, refine(rid), scope=mp.SCOPE_ONE_PASS, pass_index=1)
            with self.subTest(refinement=rid):
                self.assertEqual(shape(out, 0), before, "a pass-2 edit changed pass 1")

    def test_editing_the_first_pass_leaves_the_later_ones_identical(self) -> None:
        evs = tiled(3)
        before = [shape(evs, i) for i in (1, 2)]
        out = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0)
        self.assertEqual([shape(out, i) for i in (1, 2)], before)

    def test_only_the_selected_pass_changes_at_all(self) -> None:
        evs = tiled(4)
        out = mp.apply_to_scope(evs, refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=2)
        for i in (0, 1, 3):
            with self.subTest(pass_index=i):
                self.assertEqual(shape(out, i), shape(evs, i))
        self.assertNotEqual(shape(out, 2), shape(evs, 2))

    def test_the_section_keeps_its_length(self) -> None:
        evs = tiled(2)
        for rid, _label, _why in MELODY_REFINEMENTS:
            for idx in (0, 1):
                out = mp.apply_to_scope(evs, refine(rid), scope=mp.SCOPE_ONE_PASS, pass_index=idx)
                with self.subTest(refinement=rid, pass_index=idx):
                    self.assertAlmostEqual(timeline_span(out), timeline_span(evs), places=2)

    def test_nothing_spills_into_the_next_pass(self) -> None:
        evs = tiled(2)
        _lo, hi = mp.pass_bounds(evs, 0)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = mp.apply_to_scope(evs, refine(rid), scope=mp.SCOPE_ONE_PASS, pass_index=0)
            for ev in mp.events_in_pass(out, 0):
                end = float(ev.get("beat") or 0) + float(ev.get("duration_beats") or 0)
                with self.subTest(refinement=rid):
                    self.assertLessEqual(end, hi + 0.01, "a pass-1 note ran into pass 2")

    def test_the_transform_sees_the_pass_from_beat_zero(self) -> None:
        """"Shorten the first note" has to mean this pass's first note."""
        seen: list[float] = []

        def spy(evs):
            seen.append(min(float(e.get("beat") or 0) for e in evs))
            return evs

        mp.apply_to_scope(tiled(2), spy, scope=mp.SCOPE_ONE_PASS, pass_index=1)
        self.assertEqual(seen, [0.0])

    def test_the_edited_pass_keeps_its_markers(self) -> None:
        out = mp.apply_to_scope(tiled(2), refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1)
        for ev in mp.events_in_pass(out, 1):
            self.assertEqual(int(ev.get("pass_index")), 1)
            self.assertEqual(int(ev.get("repeat_index")), 1)

    def test_a_pass_that_is_not_there_is_left_alone(self) -> None:
        evs = tiled(2)
        out = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=7)
        self.assertEqual([shape(out, i) for i in (0, 1)], [shape(evs, i) for i in (0, 1)])

    def test_one_pass_on_a_section_that_does_not_repeat_edits_it(self) -> None:
        """With a single pass the two scopes mean the same thing; neither may do nothing."""
        evs = one_pass()
        out = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0)
        self.assertLess(len(out), len(evs))


class TestCopyingAPass(unittest.TestCase):
    def test_a_copy_makes_the_target_sound_like_the_source(self) -> None:
        evs = tiled(2)
        edited = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0)
        out, _changes = mp.copy_pass(edited, 0, [1], chords=FOUR_BARS * 2, key="D")
        self.assertEqual(
            [p for _b, p, _d in shape(out, 1)], [p for _b, p, _d in shape(out, 0)]
        )

    def test_a_copy_keeps_the_rhythm_of_the_source(self) -> None:
        out, _ = mp.copy_pass(tiled(2), 0, [1], chords=FOUR_BARS * 2, key="D")
        self.assertEqual(
            [d for _b, _p, d in shape(out, 1)], [d for _b, _p, d in shape(out, 0)]
        )

    def test_a_copy_does_not_change_the_section_length(self) -> None:
        evs = tiled(2)
        out, _ = mp.copy_pass(evs, 0, [1], chords=FOUR_BARS * 2, key="D")
        self.assertAlmostEqual(timeline_span(out), timeline_span(evs), places=2)

    def test_only_the_named_targets_receive_the_copy(self) -> None:
        evs = tiled(4)
        edited = mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0)
        out, _ = mp.copy_pass(edited, 0, [2], chords=FOUR_BARS * 4, key="D")
        self.assertEqual(shape(out, 1), shape(edited, 1))
        self.assertEqual(shape(out, 3), shape(edited, 3))
        self.assertEqual(
            [p for _b, p, _d in shape(out, 2)], [p for _b, p, _d in shape(out, 0)]
        )

    def test_copying_to_itself_does_nothing(self) -> None:
        evs = tiled(2)
        out, changes = mp.copy_pass(evs, 0, [0], chords=FOUR_BARS * 2, key="D")
        self.assertEqual(changes, [])
        self.assertEqual([shape(out, i) for i in (0, 1)], [shape(evs, i) for i in (0, 1)])

    def test_a_variation_lands_instead_of_an_identical_copy(self) -> None:
        """Repeat it, but not identically - the same phrase one refinement different."""
        evs = tiled(2)
        out, _ = mp.copy_pass(
            evs, 0, [1], chords=FOUR_BARS * 2, key="D", variation=refine("simplify")
        )
        self.assertNotEqual(
            [p for _b, p, _d in shape(out, 1)], [p for _b, p, _d in shape(out, 0)]
        )
        self.assertAlmostEqual(timeline_span(out), timeline_span(evs), places=2)

    def test_a_section_with_one_pass_has_nothing_to_copy_into(self) -> None:
        evs = one_pass()
        out, changes = mp.copy_pass(evs, 0, None, chords=FOUR_BARS, key="D")
        self.assertEqual(changes, [])
        self.assertEqual(len(out), len(evs))


class TestCopiedNotesMeetTheNewHarmony(unittest.TestCase):
    """A phrase copied onto different chords must not be left clashing - nor flattened."""

    def _with_clash(self) -> list[dict]:
        # B flat is outside D major and outside every chord in the progression: a real clash,
        # not a colour note. Held a full beat, so it is heard as one.
        rows = [
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 2.0, "is_rest": False,
             "pass_index": 0, "repeat_index": 0},
            {"pitch": "Bb4", "midi": 70, "beat": 2.0, "duration_beats": 2.0, "is_rest": False,
             "pass_index": 0, "repeat_index": 0},
        ]
        return rows

    def test_a_long_out_of_key_note_over_a_chord_is_reported(self) -> None:
        found = mp.pass_clashes(self._with_clash(), ["D", "D"], key="D", meter="4/4")
        self.assertEqual([f["pitch"] for f in found], ["Bb4"])

    def test_a_short_chromatic_note_is_left_alone(self) -> None:
        """A passing note is not a mistake, and must not be 'corrected'."""
        rows = self._with_clash()
        rows[1]["duration_beats"] = 0.5
        self.assertEqual(mp.pass_clashes(rows, ["D", "D"], key="D", meter="4/4"), [])

    def test_a_note_in_the_key_is_left_alone_even_outside_the_chord(self) -> None:
        """The ninth over a triad is music, not an error."""
        rows = [
            {"pitch": "E5", "midi": 76, "beat": 0.0, "duration_beats": 4.0, "is_rest": False,
             "pass_index": 0, "repeat_index": 0}
        ]
        self.assertEqual(mp.pass_clashes(rows, ["D"], key="D", meter="4/4"), [])

    def test_fitting_moves_the_clash_by_the_smallest_step(self) -> None:
        fixed, changes = mp.fit_events_to_chords(
            self._with_clash(), ["D", "D"], key="D", meter="4/4"
        )
        self.assertEqual(len(changes), 1)
        self.assertLessEqual(abs(changes[0]["semitones"]), 2)
        self.assertEqual(fixed[1]["midi"], 69)  # B flat -> A, a chord tone of D

    def test_fitting_never_changes_the_rhythm(self) -> None:
        rows = self._with_clash()
        before = [(e["beat"], e["duration_beats"]) for e in rows]
        fixed, _ = mp.fit_events_to_chords(rows, ["D", "D"], key="D", meter="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"]) for e in fixed], before)

    def test_fitting_leaves_notes_that_already_fit(self) -> None:
        rows = self._with_clash()
        fixed, _ = mp.fit_events_to_chords(rows, ["D", "D"], key="D", meter="4/4")
        self.assertEqual(fixed[0]["midi"], rows[0]["midi"])

    def test_a_copy_onto_different_chords_reports_what_it_adjusted(self) -> None:
        evs = expand_melody_events_by_repeats(
            [
                {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 8.0, "is_rest": False},
                {"pitch": "Bb4", "midi": 70, "beat": 8.0, "duration_beats": 8.0, "is_rest": False},
            ],
            2,
        )
        out, changes = mp.copy_pass(
            evs, 0, [1], chords=EIGHT_BARS_VARIED, key="D", meter="4/4"
        )
        self.assertTrue(changes, "a clashing copy was placed with no report")
        for ch in changes:
            self.assertEqual(ch["pass"], 2)
            self.assertIn("from", ch)
            self.assertIn("to", ch)
        self.assertAlmostEqual(timeline_span(out), timeline_span(evs), places=2)

    def test_fitting_can_be_declined(self) -> None:
        """An exact repeat is a legitimate musical choice."""
        evs = expand_melody_events_by_repeats(
            [
                {"pitch": "Bb4", "midi": 70, "beat": 0.0, "duration_beats": 16.0,
                 "is_rest": False}
            ],
            2,
        )
        _out, changes = mp.copy_pass(
            evs, 0, [1], chords=EIGHT_BARS_VARIED, key="D", fit_to_chords=False
        )
        self.assertEqual(changes, [])


class TestThePureFunctionsStayPure(unittest.TestCase):
    """Section identity, chord data and Backing loops are not this module's business."""

    def test_nothing_mutates_its_input(self) -> None:
        evs = tiled(2)
        snapshot = copy.deepcopy(evs)
        mp.apply_to_scope(evs, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1)
        mp.copy_pass(evs, 0, [1], chords=FOUR_BARS * 2, key="D")
        mp.fit_events_to_chords(evs, FOUR_BARS * 2, key="D")
        mp.pass_clashes(evs, FOUR_BARS * 2, key="D")
        self.assertEqual(evs, snapshot)

    def test_the_module_knows_nothing_about_loops(self) -> None:
        source = (ROOT / "composition_melody_passes.py").read_text(encoding="utf-8")
        self.assertNotIn("loops", source)
        for word in ("section_by_id", "apply_melody_events", "_save_doc"):
            self.assertNotIn(word, source)


class TestEditingChosenBars(unittest.TestCase):
    """Bars are what the musician reads off the staff, so the window can be given in bars."""

    def test_bars_map_to_beats_one_based(self) -> None:
        self.assertEqual(mp.bar_bounds(1, 4, meter="4/4"), (0.0, 16.0))
        self.assertEqual(mp.bar_bounds(5, 8, meter="4/4"), (16.0, 32.0))
        self.assertEqual(mp.bar_bounds(3, 3, meter="4/4"), (8.0, 12.0))

    def test_a_reversed_range_is_read_in_the_order_meant(self) -> None:
        self.assertEqual(mp.bar_bounds(8, 5, meter="4/4"), mp.bar_bounds(5, 8, meter="4/4"))

    def test_the_caption_names_the_bars(self) -> None:
        self.assertIn("bars 5-8", mp.scope_caption(mp.SCOPE_BARS, bars=(5, 8)))
        self.assertIn("bar 3", mp.scope_caption(mp.SCOPE_BARS, bars=(3, 3)))

    def test_only_the_chosen_bars_change(self) -> None:
        evs = tiled(2)
        before_early = [
            (round(float(e["beat"]), 4), str(e.get("pitch")), float(e["duration_beats"]))
            for e in evs
            if float(e["beat"]) < 16.0
        ]
        out = mp.apply_to_scope(
            evs, refine("simplify"), scope=mp.SCOPE_BARS, bars=(5, 8), meter="4/4"
        )
        after_early = [
            (round(float(e["beat"]), 4), str(e.get("pitch")), float(e["duration_beats"]))
            for e in out
            if float(e["beat"]) < 16.0
        ]
        self.assertEqual(after_early, before_early)

    def test_a_bar_edit_does_not_change_the_section_length(self) -> None:
        evs = tiled(2)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = mp.apply_to_scope(
                evs, refine(rid), scope=mp.SCOPE_BARS, bars=(1, 4), meter="4/4"
            )
            with self.subTest(refinement=rid):
                self.assertAlmostEqual(timeline_span(out), timeline_span(evs), places=2)

    def test_nothing_grows_past_the_chosen_bars(self) -> None:
        evs = tiled(2)
        out = mp.apply_to_scope(
            evs, refine("emotional"), scope=mp.SCOPE_BARS, bars=(1, 4), meter="4/4"
        )
        for ev in out:
            beat = float(ev.get("beat") or 0)
            if beat < 16.0:
                end = beat + float(ev.get("duration_beats") or 0)
                self.assertLessEqual(end, 16.01)

    def test_bars_beyond_the_melody_are_a_no_op(self) -> None:
        evs = tiled(2)
        out = mp.apply_to_scope(
            evs, refine("simplify"), scope=mp.SCOPE_BARS, bars=(40, 44), meter="4/4"
        )
        self.assertEqual(len(out), len(evs))


class TestShortEndingVersusTruncated(unittest.TestCase):
    """Two kinds of silence at the end of a section that must never be confused."""

    CHORDS = EIGHT_BARS_VARIED  # eight bars = 32 beats

    def _notes(self, last_end: float, closing_rest: bool = False) -> list[dict]:
        rows = [
            {"pitch": "D5", "midi": 74, "beat": b, "duration_beats": 4.0, "is_rest": False}
            for b in [x * 4.0 for x in range(int(last_end // 4))]
        ]
        if closing_rest:
            rows.append(
                {
                    "pitch": "rest",
                    "midi": None,
                    "beat": last_end,
                    "duration_beats": 32.0 - last_end,
                    "is_rest": True,
                }
            )
        return rows

    def test_a_melody_that_reaches_the_end_covers(self) -> None:
        got = mp.coverage_report(self._notes(32.0), self.CHORDS, meter="4/4")
        self.assertEqual(got["verdict"], "covers")
        self.assertTrue(got["covers"])

    def test_a_written_closing_rest_is_an_intended_ending(self) -> None:
        got = mp.coverage_report(self._notes(24.0, closing_rest=True), self.CHORDS, meter="4/4")
        self.assertEqual(got["verdict"], "intended_ending")
        self.assertTrue(got["closing_rest"])
        self.assertIn("written in", got["message"])

    def test_stopping_just_short_reads_as_a_phrase_ending(self) -> None:
        rows = self._notes(32.0)
        rows[-1]["duration_beats"] = 2.0  # ends at 30 of 32
        got = mp.coverage_report(rows, self.CHORDS, meter="4/4")
        self.assertEqual(got["verdict"], "intended_ending")

    def test_a_missing_second_half_is_reported_as_truncated(self) -> None:
        """The defect the musician reported: chords playing with no melody over them."""
        got = mp.coverage_report(self._notes(16.0), self.CHORDS, meter="4/4")
        self.assertEqual(got["verdict"], "truncated")
        self.assertFalse(got["covers"])
        self.assertAlmostEqual(got["silent_tail_bars"], 4.0, places=2)
        self.assertIn("4 bar", got["message"])

    def test_truncation_is_measured_in_bars_of_the_actual_meter(self) -> None:
        got = mp.coverage_report(self._notes(16.0), self.CHORDS, meter="4/4")
        self.assertAlmostEqual(got["silent_tail_beats"], 16.0, places=2)

    def test_a_generated_melody_covers_its_section(self) -> None:
        got = mp.coverage_report(tiled(2), FOUR_BARS * 2, meter="4/4")
        self.assertEqual(got["verdict"], "covers")

    def test_a_pass_edit_does_not_make_a_section_look_truncated(self) -> None:
        evs = tiled(2)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = mp.apply_to_scope(evs, refine(rid), scope=mp.SCOPE_ONE_PASS, pass_index=1)
            with self.subTest(refinement=rid):
                self.assertNotEqual(
                    mp.coverage_report(out, FOUR_BARS * 2, meter="4/4")["verdict"], "truncated"
                )


class TestRestoringOnePass(unittest.TestCase):
    """Changed your mind about pass 2, having since worked on pass 1."""

    def test_the_restored_pass_matches_the_original_exactly(self) -> None:
        original = tiled(2)
        edited = mp.apply_to_scope(
            original, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        back = mp.restore_pass(edited, original, 1)
        self.assertEqual(shape(back, 1), shape(original, 1))

    def test_work_on_the_other_pass_is_kept(self) -> None:
        original = tiled(2)
        edited = mp.apply_to_scope(
            original, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=0
        )
        edited = mp.apply_to_scope(
            edited, refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        back = mp.restore_pass(edited, original, 1)
        self.assertEqual(shape(back, 0), shape(edited, 0), "restoring pass 2 undid pass 1")
        self.assertEqual(shape(back, 1), shape(original, 1))

    def test_rests_and_durations_come_back_unchanged(self) -> None:
        original = expand_melody_events_by_repeats(
            [
                {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 1.5,
                 "is_rest": False},
                {"pitch": "rest", "midi": None, "beat": 1.5, "duration_beats": 0.5,
                 "is_rest": True},
                {"pitch": "A4", "midi": 69, "beat": 2.0, "duration_beats": 2.0,
                 "is_rest": False},
            ],
            2,
        )
        edited = mp.apply_to_scope(
            original, refine("energetic"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        back = mp.restore_pass(edited, original, 1)
        self.assertEqual(shape(back, 1), shape(original, 1))
        self.assertTrue(any(e.get("is_rest") for e in mp.events_in_pass(back, 1)))

    def test_the_section_length_is_unchanged(self) -> None:
        original = tiled(2)
        edited = mp.apply_to_scope(
            original, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        back = mp.restore_pass(edited, original, 1)
        self.assertAlmostEqual(timeline_span(back), timeline_span(original), places=2)

    def test_restoring_a_pass_that_is_not_in_the_original_is_a_no_op(self) -> None:
        original = tiled(2)
        self.assertEqual(len(mp.restore_pass(original, original, 9)), len(original))

    def test_nothing_is_mutated(self) -> None:
        original = tiled(2)
        snapshot = copy.deepcopy(original)
        edited = mp.apply_to_scope(
            original, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1
        )
        mp.restore_pass(edited, original, 1)
        self.assertEqual(original, snapshot)


class TestEventsThatCrossABarBoundary(unittest.TestCase):
    """A phrase does not stop at bar lines, and a scoped edit must not pretend it does.

    These exist because the first version of the windowed path had two faults that the earlier
    bar tests did not catch: it DUPLICATED every selected event (the partition compared
    deep-copied rows by object identity), and it SHORTENED a note that sang across the window's
    end. Both are invisible to a test that only checks the total span or the final beat, so
    these check the event count and each note's own length.
    """

    def _crossing(self) -> list[dict]:
        # The F sharp starts in bar 4 and sings into bar 5 - written that way on purpose.
        return [
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "A4", "midi": 69, "beat": 4.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "B4", "midi": 71, "beat": 8.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "F#5", "midi": 78, "beat": 15.0, "duration_beats": 3.0, "is_rest": False},
            {"pitch": "E5", "midi": 76, "beat": 20.0, "duration_beats": 4.0, "is_rest": False},
        ]

    def _tup(self, events) -> list[tuple]:
        return [
            (round(float(e.get("beat") or 0), 4), str(e.get("pitch")), float(e.get("duration_beats") or 0))
            for e in events
        ]

    def test_an_edit_that_changes_nothing_changes_nothing(self) -> None:
        """The sharpest check there is: an identity transform must be a no-op."""
        rows = self._crossing()
        for bars in ((1, 4), (5, 6), (1, 6), (3, 5)):
            out = mp.apply_to_scope(rows, lambda evs: evs, scope=mp.SCOPE_BARS, bars=bars,
                                    meter="4/4")
            with self.subTest(bars=bars):
                self.assertEqual(self._tup(out), self._tup(rows))

    def test_no_event_is_duplicated(self) -> None:
        rows = self._crossing()
        for bars in ((1, 4), (5, 6), (2, 3)):
            out = mp.apply_to_scope(rows, refine("energetic"), scope=mp.SCOPE_BARS, bars=bars,
                                    meter="4/4")
            with self.subTest(bars=bars):
                # Duplication showed up as the SAME event twice: identical onset, pitch and
                # length. A refinement may add or split notes, but it never emits a twin.
                triples = self._tup(out)
                self.assertEqual(
                    len(triples), len(set(triples)), f"duplicated events: {triples}"
                )

    def test_a_note_crossing_the_window_end_keeps_its_length(self) -> None:
        rows = self._crossing()
        out = mp.apply_to_scope(rows, lambda evs: evs, scope=mp.SCOPE_BARS, bars=(1, 4),
                                meter="4/4")
        crossing = [e for e in out if str(e.get("pitch")) == "F#5"]
        self.assertEqual(len(crossing), 1)
        self.assertAlmostEqual(float(crossing[0]["duration_beats"]), 3.0, places=3)

    def test_a_note_starting_outside_the_window_is_untouched(self) -> None:
        """Bars 5-6 selected: the note that merely sounds into bar 5 began in bar 4."""
        rows = self._crossing()
        out = mp.apply_to_scope(rows, refine("simplify"), scope=mp.SCOPE_BARS, bars=(5, 6),
                                meter="4/4")
        before = [t for t in self._tup(rows) if t[0] < 16.0]
        after = [t for t in self._tup(out) if t[0] < 16.0]
        self.assertEqual(after, before)

    def test_a_rest_that_crosses_the_boundary_survives(self) -> None:
        rows = [
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 12.0, "is_rest": False},
            {"pitch": "rest", "midi": None, "beat": 14.0, "duration_beats": 4.0,
             "is_rest": True},
            {"pitch": "A4", "midi": 69, "beat": 20.0, "duration_beats": 4.0, "is_rest": False},
        ]
        out = mp.apply_to_scope(rows, lambda evs: evs, scope=mp.SCOPE_BARS, bars=(1, 4),
                                meter="4/4")
        rest = [e for e in out if e.get("is_rest")]
        self.assertEqual(len(rest), 1)
        self.assertAlmostEqual(float(rest[0]["duration_beats"]), 4.0, places=3)

    def test_an_edit_still_cannot_grow_past_what_the_selection_held(self) -> None:
        """The clamp must still do its job: nothing may reach further than it already did."""
        rows = self._crossing()
        reach = max(float(e["beat"]) + float(e["duration_beats"]) for e in rows[:4])
        out = mp.apply_to_scope(rows, refine("emotional"), scope=mp.SCOPE_BARS, bars=(1, 4),
                                meter="4/4")
        for ev in out:
            if float(ev.get("beat") or 0) < 16.0:
                end = float(ev["beat"]) + float(ev["duration_beats"])
                self.assertLessEqual(end, reach + 0.01)


class TestNonFourFourMeters(unittest.TestCase):
    """Bars are not always four beats, and the window must be built from the real meter."""

    METERS = ("3/4", "6/8", "5/4", "7/8", "12/8")

    def test_bar_bounds_agree_with_the_chord_grid(self) -> None:
        """The same bar length the chord timeline uses - otherwise bars and chords disagree."""
        from composition_melody_audit import chord_segments

        for meter in self.METERS:
            segs = chord_segments(["D", "Bm", "G", "A"], meter)
            one_bar = float(segs[0][1]) - float(segs[0][0])
            with self.subTest(meter=meter):
                self.assertAlmostEqual(mp.bar_beats(meter), one_bar, places=3)
                self.assertEqual(mp.bar_bounds(1, 1, meter=meter), (0.0, round(one_bar, 4)))

    def test_bar_windows_tile_without_gaps(self) -> None:
        for meter in self.METERS:
            bar = mp.bar_beats(meter)
            with self.subTest(meter=meter):
                self.assertEqual(mp.bar_bounds(1, 2, meter=meter), (0.0, round(2 * bar, 4)))
                self.assertEqual(
                    mp.bar_bounds(3, 4, meter=meter),
                    (round(2 * bar, 4), round(4 * bar, 4)),
                )

    def _melody_for(self, meter: str) -> list[dict]:
        return build_concept_events("direct_line", FOUR_BARS, key="D", meter=meter)

    def test_only_the_chosen_bars_change_in_any_meter(self) -> None:
        for meter in self.METERS:
            rows = self._melody_for(meter)
            bar = mp.bar_beats(meter)
            out = mp.apply_to_scope(
                rows, refine("simplify"), scope=mp.SCOPE_BARS, bars=(3, 4), meter=meter
            )
            before = [
                (round(float(e["beat"]), 4), str(e.get("pitch")), float(e["duration_beats"]))
                for e in rows
                if float(e["beat"]) < 2 * bar - 0.001
            ]
            after = [
                (round(float(e["beat"]), 4), str(e.get("pitch")), float(e["duration_beats"]))
                for e in out
                if float(e["beat"]) < 2 * bar - 0.001
            ]
            with self.subTest(meter=meter):
                self.assertEqual(after, before)

    def test_an_identity_edit_is_a_no_op_in_any_meter(self) -> None:
        for meter in self.METERS:
            rows = self._melody_for(meter)
            out = mp.apply_to_scope(
                rows, lambda evs: evs, scope=mp.SCOPE_BARS, bars=(1, 2), meter=meter
            )
            with self.subTest(meter=meter):
                self.assertEqual(len(out), len(rows))
                self.assertEqual(
                    [round(float(e["beat"]), 4) for e in out],
                    [round(float(e["beat"]), 4) for e in rows],
                )

    def test_the_section_keeps_its_length_in_any_meter(self) -> None:
        for meter in self.METERS:
            rows = self._melody_for(meter)
            for rid, _label, _why in MELODY_REFINEMENTS:
                out = mp.apply_to_scope(
                    rows, refine(rid), scope=mp.SCOPE_BARS, bars=(1, 2), meter=meter
                )
                with self.subTest(meter=meter, refinement=rid):
                    self.assertAlmostEqual(timeline_span(out), timeline_span(rows), places=2)

    def test_a_compound_meter_pass_edit_leaves_the_other_pass_alone(self) -> None:
        for meter in ("6/8", "12/8"):
            rows = expand_melody_events_by_repeats(self._melody_for(meter), 2)
            before = shape(rows, 0)
            out = mp.apply_to_scope(
                rows, refine("simplify"), scope=mp.SCOPE_ONE_PASS, pass_index=1, meter=meter
            )
            with self.subTest(meter=meter):
                self.assertEqual(shape(out, 0), before)


class TestTruncationIsOnlyADiagnosis(unittest.TestCase):
    """coverage_report describes; it must never repair."""

    def test_it_does_not_change_the_events_it_is_given(self) -> None:
        rows = [
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False}
        ]
        snapshot = copy.deepcopy(rows)
        mp.coverage_report(rows, FOUR_BARS, meter="4/4")
        self.assertEqual(rows, snapshot)

    def test_it_returns_a_description_and_no_events(self) -> None:
        got = mp.coverage_report(
            [{"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False}],
            FOUR_BARS,
            meter="4/4",
        )
        self.assertNotIn("events", got)
        self.assertIn("verdict", got)
        self.assertIn("message", got)

    def test_a_long_deliberate_silence_is_reported_without_a_claim_of_error(self) -> None:
        """A long ending with no notes may be exactly what was wanted."""
        got = mp.coverage_report(
            [{"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False}],
            FOUR_BARS,
            meter="4/4",
        )
        self.assertEqual(got["verdict"], "truncated")
        low = got["message"].lower()
        for word in ("error", "wrong", "invalid", "must", "broken"):
            with self.subTest(word=word):
                self.assertNotIn(word, low)


class TestCrossingTheEdgesOfASelectedRange(unittest.TestCase):
    """The contract at the two edges of Selected Bars, under real edits and not only identity.

    **Selection is by ONSET, never by overlap.** A note beginning in bar 4 and singing into
    bar 5 belongs to bar 4, so selecting bars 5-8 must leave it completely alone - even though
    it is sounding inside the selection. A note beginning inside the range keeps whatever
    length it already had, even where that reaches past the end.

    Refinements are deliberately not used here. These transforms change pitch and duration by
    known amounts, so a failure says which guarantee broke rather than which refinement ran.
    """

    WINDOW = (5, 8)          # beats 16-32 in 4/4
    EDGE = 16.0

    def _melody(self) -> list[dict]:
        return [
            # bar 1-3: well before the range
            {"pitch": "D5", "midi": 74, "beat": 0.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "A4", "midi": 69, "beat": 4.0, "duration_beats": 4.0, "is_rest": False},
            {"pitch": "rest", "midi": None, "beat": 8.0, "duration_beats": 4.0, "is_rest": True},
            # bar 4: STARTS OUTSIDE, SOUNDS INSIDE bars 5-8
            {"pitch": "B4", "midi": 71, "beat": 14.0, "duration_beats": 4.0, "is_rest": False},
            # inside the range
            {"pitch": "F#5", "midi": 78, "beat": 16.0, "duration_beats": 2.0, "is_rest": False},
            {"pitch": "rest", "midi": None, "beat": 18.0, "duration_beats": 2.0, "is_rest": True},
            {"pitch": "E5", "midi": 76, "beat": 20.0, "duration_beats": 4.0, "is_rest": False},
            # STARTS INSIDE, SOUNDS PAST the range end at beat 32
            {"pitch": "D5", "midi": 74, "beat": 30.0, "duration_beats": 4.0, "is_rest": False},
        ]

    # --- transforms with known, checkable effects ------------------------------------------
    @staticmethod
    def _identity(evs):
        return evs

    @staticmethod
    def _up_two(evs):
        out = []
        for e in evs:
            row = dict(e)
            if not row.get("is_rest") and row.get("midi") is not None:
                row["midi"] = int(row["midi"]) + 2
                row["pitch"] = f"X{row['midi']}"
            out.append(row)
        return out

    @staticmethod
    def _double_lengths(evs):
        return [dict(e, duration_beats=float(e.get("duration_beats") or 0) * 2) for e in evs]

    @staticmethod
    def _halve_lengths(evs):
        return [
            dict(e, duration_beats=max(0.25, float(e.get("duration_beats") or 0) / 2))
            for e in evs
        ]

    def _edits(self):
        return (
            ("identity", self._identity),
            ("pitch up a tone", self._up_two),
            ("durations doubled", self._double_lengths),
            ("durations halved", self._halve_lengths),
        )

    def _tup(self, events):
        return [
            (
                round(float(e.get("beat") or 0), 4),
                str(e.get("pitch")),
                float(e.get("duration_beats") or 0),
                bool(e.get("is_rest")),
            )
            for e in events
        ]

    def _run(self, transform):
        return mp.apply_to_scope(
            self._melody(), transform, scope=mp.SCOPE_BARS, bars=self.WINDOW, meter="4/4"
        )

    # --- the rule itself --------------------------------------------------------------------
    def test_selection_is_by_onset_not_overlap(self) -> None:
        chosen = mp.events_in_window(self._melody(), mp.bar_bounds(*self.WINDOW, meter="4/4"))
        onsets = sorted(round(float(e["beat"]), 4) for e in chosen)
        self.assertEqual(onsets, [16.0, 18.0, 20.0, 30.0])
        self.assertNotIn(14.0, onsets, "a note that only SOUNDS inside the range was selected")

    def test_the_transform_receives_exactly_the_selected_events(self) -> None:
        seen: list[int] = []
        self._run(lambda evs: (seen.append(len(evs)), evs)[1])
        self.assertEqual(seen, [4])

    # --- nothing outside the range may move -------------------------------------------------
    def test_an_event_starting_before_the_range_is_never_touched(self) -> None:
        original = [e for e in self._melody() if float(e["beat"]) < self.EDGE]
        for name, transform in self._edits():
            out = self._run(transform)
            before = [e for e in out if float(e.get("beat") or 0) < self.EDGE]
            with self.subTest(edit=name):
                self.assertEqual(self._tup(before), self._tup(original))

    def test_the_note_that_sounds_into_the_range_keeps_pitch_and_length(self) -> None:
        for name, transform in self._edits():
            out = self._run(transform)
            crossing = [e for e in out if round(float(e.get("beat") or 0), 4) == 14.0]
            with self.subTest(edit=name):
                self.assertEqual(len(crossing), 1)
                self.assertEqual(str(crossing[0].get("pitch")), "B4")
                self.assertAlmostEqual(float(crossing[0]["duration_beats"]), 4.0, places=3)

    def test_the_rest_before_the_range_survives(self) -> None:
        for name, transform in self._edits():
            out = self._run(transform)
            rests = [e for e in out if e.get("is_rest") and float(e["beat"]) < self.EDGE]
            with self.subTest(edit=name):
                self.assertEqual(len(rests), 1)
                self.assertAlmostEqual(float(rests[0]["duration_beats"]), 4.0, places=3)

    # --- the edit must land, and only there -------------------------------------------------
    def test_a_pitch_edit_changes_only_the_selected_notes(self) -> None:
        out = self._run(self._up_two)
        changed = [e for e in out if str(e.get("pitch")).startswith("X")]
        self.assertEqual(
            sorted(round(float(e["beat"]), 4) for e in changed), [16.0, 20.0, 30.0]
        )

    def test_a_duration_edit_reaches_the_selected_notes(self) -> None:
        out = self._run(self._halve_lengths)
        inside = {round(float(e["beat"]), 4): float(e["duration_beats"]) for e in out}
        self.assertAlmostEqual(inside[16.0], 1.0, places=3)
        self.assertAlmostEqual(inside[20.0], 2.0, places=3)

    # --- no duplication, no accidental growth ----------------------------------------------
    def test_no_event_is_duplicated_by_any_edit(self) -> None:
        for name, transform in self._edits():
            out = self._run(transform)
            triples = self._tup(out)
            with self.subTest(edit=name):
                self.assertEqual(len(triples), len(set(triples)), f"duplicates: {triples}")
                self.assertEqual(len(out), len(self._melody()))

    def test_the_melody_is_never_extended(self) -> None:
        """Doubling every selected length must not make the section longer."""
        was = timeline_span(self._melody())
        for name, transform in self._edits():
            out = self._run(transform)
            with self.subTest(edit=name):
                self.assertLessEqual(timeline_span(out), was + 0.01)

    def test_the_note_crossing_the_end_is_not_cropped_by_an_unrelated_edit(self) -> None:
        """Its own length is its own business when the transform did not change it."""
        out = self._run(self._up_two)
        tail = [e for e in out if round(float(e.get("beat") or 0), 4) == 30.0]
        self.assertEqual(len(tail), 1)
        self.assertAlmostEqual(float(tail[0]["duration_beats"]), 4.0, places=3)

    def test_the_note_crossing_the_end_may_not_grow_further(self) -> None:
        """Doubling it would push the section past where it already ended."""
        out = self._run(self._double_lengths)
        tail = [e for e in out if round(float(e.get("beat") or 0), 4) == 30.0][0]
        self.assertAlmostEqual(
            float(tail["beat"]) + float(tail["duration_beats"]),
            timeline_span(self._melody()),
            places=2,
        )

    def test_onsets_never_move(self) -> None:
        for name, transform in self._edits():
            out = self._run(transform)
            with self.subTest(edit=name):
                self.assertEqual(
                    sorted(round(float(e["beat"]), 4) for e in out),
                    sorted(round(float(e["beat"]), 4) for e in self._melody()),
                )

    def test_a_range_that_begins_mid_phrase_behaves_the_same(self) -> None:
        """Bars 4-5 start inside the sounding note from bar 4; it still is not selected."""
        out = mp.apply_to_scope(
            self._melody(), self._up_two, scope=mp.SCOPE_BARS, bars=(4, 5), meter="4/4"
        )
        crossing = [e for e in out if round(float(e.get("beat") or 0), 4) == 14.0][0]
        self.assertEqual(str(crossing.get("pitch")), "X73")
        untouched = [e for e in out if round(float(e.get("beat") or 0), 4) == 20.0][0]
        self.assertEqual(str(untouched.get("pitch")), "E5")


if __name__ == "__main__":
    unittest.main()

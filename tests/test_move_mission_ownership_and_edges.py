"""Move Mission Up / Down: concert ownership, range edges, blues thirds, refusals, single-step behaviour."""

from __future__ import annotations

import unittest

from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    apply_mission_motif_transform,
    load_mission_example,
    store_mission_example,
)
from mission_degree_shift import resolve_framework, shift_midis_by_degree
from tests.test_move_mission_by_degree import BLUES, MOTIF, PENT, _pcs, _setup, _state

SCALES = {
    "C": {0, 2, 4, 5, 7, 9, 11},
    "F": {5, 7, 9, 10, 0, 2, 4},
    "D": {2, 4, 6, 7, 9, 11, 1},
    "Bb": {10, 0, 2, 3, 5, 7, 9},
}


def _store(session, ctx, **motif_fields):
    ex = load_mission_example(session, ctx)
    ex.motif = dict(ex.motif, **motif_fields)
    ex.motif.pop("_concert_notes", None)
    store_mission_example(session, ex, persist_artifact=False, interaction="test_edit")


class TestConcertOwnership(unittest.TestCase):
    """The move happens on the concert (Practice Key) phrase; the Written copy is a projection of it."""

    CASES = (
        ("Clarinet", "Bb Clarinet", "F"),
        ("Saxophone", "Tenor saxophone (Bb)", "D"),
        ("Clarinet", "Bb Clarinet", "Bb"),
        ("Saxophone", "Alto saxophone (Eb)", "F"),
    )

    def test_concert_moves_one_degree_and_written_is_its_projection(self) -> None:
        from music_theory import semitone_distance

        from instrument_transposition import written_key_for_type

        for inst, ttype, concert in self.CASES:
            written = written_key_for_type(concert, ttype)
            session, ctx = _setup(MOTIF, concert, concert, instrument=inst, transposing=ttype)
            self.assertEqual(ctx.display_key, written)
            steps = semitone_distance(concert, written)
            self.assertNotEqual(steps, 0)
            n0, m0, _ = _state(session, ctx)
            c0 = [m - steps for m in m0]
            for op, direction in (("sequence_up", +1), ("sequence_down", -1)):
                apply_mission_motif_transform(session, ctx, op, bpm=100)
                n1, m1, meta = _state(session, ctx)
                c1 = [m - steps for m in m1]
                self.assertEqual(c1, shift_midis_by_degree(c0, SCALES[concert], direction), (inst, concert, op))
                self.assertEqual(_pcs(meta["_concert_notes"]), [m % 12 for m in c1])
                self.assertTrue(set(_pcs(meta["_concert_notes"])) <= SCALES[concert])
                self.assertTrue(set(_pcs(n1)) <= {(pc + steps) % 12 for pc in SCALES[concert]})
                self.assertEqual(_pcs(n1), [m % 12 for m in m1])
                apply_mission_motif_transform(session, ctx, "sequence_down" if direction > 0 else "sequence_up", bpm=100)
                n2, m2, meta2 = _state(session, ctx)
                self.assertEqual((n2, m2), (n0, m0), (inst, concert, op))                 # written restored exactly
                self.assertEqual(_pcs(meta2["_concert_notes"]), [m % 12 for m in c0])     # concert restored exactly
                self.assertEqual(meta2["_concert_chord"], concert)

    def test_written_spelling_is_key_correct(self) -> None:
        session, ctx = _setup(MOTIF, "D", "D", instrument="Clarinet", transposing="Bb Clarinet")
        for _ in range(4):
            apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
            notes = _state(session, ctx)[0]
            self.assertFalse(any("b" in n[1:] for n in notes), notes)     # E major is a sharp key
        session, ctx = _setup(MOTIF, "F", "F", instrument="Saxophone", transposing="Tenor saxophone (Bb)")
        for _ in range(4):
            apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
            notes = _state(session, ctx)[0]
            self.assertFalse(any("b" in n[1:] for n in notes), notes)     # G major: F#, never Gb / Bb


class TestRangeBoundaries(unittest.TestCase):
    def test_bottom_edge_down_is_refused_not_renormalised_and_up_down_is_exact(self) -> None:
        session, ctx = _setup(MOTIF, "C", "C")
        _store(session, ctx, notes=["F", "G", "A", "F"], midi=[53, 55, 57, 53])
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [53, 55, 57, 53])          # unchanged, not shifted an octave
        self.assertIn("staff range", session.get("_mission_move_notice", ""))
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [55, 57, 59, 55])
        self.assertFalse(session.get("_mission_move_notice"))
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        self.assertEqual(_state(session, ctx)[:2], (["F", "G", "A", "F"], [53, 55, 57, 53]))

    def test_top_edge_up_is_refused_and_down_up_is_exact(self) -> None:
        session, ctx = _setup(MOTIF, "C", "C")
        _store(session, ctx, notes=["E", "G", "A", "E"], midi=[88, 91, 93, 88])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [88, 91, 93, 88])
        self.assertIn("staff range", session.get("_mission_move_notice", ""))
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [86, 89, 91, 86])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[:2], (["E", "G", "A", "E"], [88, 91, 93, 88]))

    def test_octave_crossing_inside_the_range_is_exact(self) -> None:
        session, ctx = _setup(MOTIF, "C", "C")
        _store(session, ctx, notes=["B", "C", "D", "B"], midi=[71, 72, 74, 71])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [72, 74, 76, 72])
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [69, 71, 72, 69])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[1], [71, 72, 74, 71])


class TestBluesThirds(unittest.TestCase):
    def test_major_blues_has_both_thirds_as_distinct_ordered_degrees(self) -> None:
        _label, names = resolve_framework(BLUES, {"pentatonic_relationship": "root_major_blues"}, chord="Cmaj7", key_center="C")
        self.assertEqual(sorted(names), [0, 2, 3, 4, 7, 9])                  # C D Eb E G A
        self.assertEqual((names[3], names[4]), ("Eb", "E"))
        self.assertEqual(shift_midis_by_degree([63], set(names), +1), [64])  # b3 -> 3
        self.assertEqual(shift_midis_by_degree([64], set(names), +1), [67])  # 3 -> 5, not a semitone to F
        self.assertEqual(shift_midis_by_degree([64], set(names), -1), [63])
        self.assertEqual(shift_midis_by_degree([67], set(names), -1), [64])

    def test_minor_blues_has_only_the_flat_third(self) -> None:
        _label, names = resolve_framework(BLUES, {"pentatonic_relationship": "root_minor_blues"}, chord="A7", key_center="A")
        self.assertEqual(sorted(names), [0, 2, 3, 4, 7, 9])                  # A C D Eb E G
        self.assertNotIn(1, names)                                            # no C# (major 3rd)

    def test_real_major_blues_phrase_with_both_thirds(self) -> None:
        session, ctx = _setup(BLUES, "C", "C", level="Advanced")
        ex = load_mission_example(session, ctx)
        self.assertEqual(ex.motif["pentatonic_relationship"], "root_major_blues")
        _store(session, ctx, notes=["C", "D", "Eb", "E", "G", "A"], midi=[60, 62, 63, 64, 67, 69])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertEqual(_state(session, ctx)[:2], (["D", "Eb", "E", "G", "A", "C"], [62, 63, 64, 67, 69, 72]))
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        self.assertEqual(_state(session, ctx)[:2], (["C", "D", "Eb", "E", "G", "A"], [60, 62, 63, 64, 67, 69]))

    def test_minor_blues_refuses_an_out_of_collection_major_third(self) -> None:
        session, ctx = _setup(BLUES, "A7", "A")
        _store(session, ctx, notes=["A", "C#", "E", "G"], midi=[57, 61, 64, 67])
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        self.assertTrue(session.get("_mission_move_notice"))
        self.assertEqual(_state(session, ctx)[1], [57, 61, 64, 67])


class TestRefusalsAndSteps(unittest.TestCase):
    def test_structure_pinned_mission_moves_or_refuses_with_a_reason(self) -> None:
        outcomes = []
        for chord in ("G7", "Dm7", "Am7"):
            session, ctx = _setup("Resolve convincingly to the chord's 3rd", chord, "C")
            m0 = _state(session, ctx)[1]
            apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
            notice = session.get("_mission_move_notice")
            if notice:
                self.assertIn("scale degree", notice)
                self.assertEqual(_state(session, ctx)[1], m0)
            else:
                self.assertNotEqual(_state(session, ctx)[1], m0)
            outcomes.append(bool(notice))
        self.assertEqual(len(outcomes), 3)

    def test_each_call_moves_exactly_one_step_and_state_is_single_sourced(self) -> None:
        session, ctx = _setup(PENT, "Am", "Am")
        cur = _state(session, ctx)[1]
        for _ in range(3):
            apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
            nxt = _state(session, ctx)[1]
            self.assertEqual(nxt, shift_midis_by_degree(cur, {9, 0, 2, 4, 7}, +1))
            self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["midi"], nxt)
            cur = nxt


if __name__ == "__main__":
    unittest.main()

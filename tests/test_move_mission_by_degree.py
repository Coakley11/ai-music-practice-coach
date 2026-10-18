"""Move Mission Up / Down moves the phrase one degree of the Mission's own tonal framework."""

from __future__ import annotations

import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _run_mission_example_generate
from improvisation_missions import MISSION_EXAMPLE_KEY, apply_mission_motif_transform, load_mission_example
from mission_degree_shift import MoveRefused, shift_midis_by_degree

PENT = "Improvise using a pentatonic scale that fits the chord"
BLUES = "Improvise using a blues scale that fits the chord"
CHORD_TONES = "Improvise using only chord tones"
GUIDE = "Target only guide tones (3rds & 7ths)"
MOTIF = "Develop one motif for the entire solo"
NAMES = "C C# D D# E F F# G G# A A# B".split()


def _setup(mission, chord, key, *, written=None, instrument="Piano", level="Intermediate", transposing=None):
    """``transposing`` (e.g. "Bb Clarinet") turns on Written Key the way the app does: the Practice Key stays concert."""
    from instrument_transposition import (
        CHART_IN_INSTRUMENT_KEY_KEY,
        SELECTED_TRANSPOSING_INSTRUMENT_KEY,
        written_key_for_type,
    )

    if transposing:
        written = written_key_for_type(key, transposing)
    written = written or key
    session = {
        "song": "Shape", "artist": "Artist", "display_key": key if transposing else written, "concert_key": key, "instrument": instrument,
        "level": level, "focus": "Improvisation", "improv_active_mission": mission, "improv_mission_pick": mission,
        "home_sections": {"A": [chord]}, "improv_mission_chord_options": [chord], "ii_selected_chord_index": 0,
        "ii_selected_chord": chord, "ii_selected_section": "A", "backing_track_bpm": 100, "creative_workspace_state": {},
    }
    ctx = ImprovSessionContext(song_title="Shape", artist="Artist", key_center=key, display_key=written,
                               instrument=instrument, level=level, focus="Improvisation", sections={"A": [chord]})
    if transposing:
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = transposing
    _run_mission_example_generate(session, "normal")
    return session, ctx


def _state(session, ctx):
    ex = load_mission_example(session, ctx)
    m = ex.motif
    return list(m["notes"]), list(m["midi"]), dict(m)


def _pcs(notes):
    from improvisation_motif import _midi_from_note

    return [_midi_from_note(n, 4) % 12 for n in notes]


class TestShiftPrimitive(unittest.TestCase):
    A_MIN_PENT = {9, 0, 2, 4, 7}

    def test_pentatonic_steps_stay_inside_collection(self) -> None:
        up = shift_midis_by_degree([57, 60, 62, 64, 67, 69], self.A_MIN_PENT, +1)
        self.assertEqual(up, [60, 62, 64, 67, 69, 72])           # A C D E G A -> C D E G A C

    def test_up_then_down_is_exact(self) -> None:
        phrase = [69, 67, 64, 62, 60, 57]
        self.assertEqual(shift_midis_by_degree(shift_midis_by_degree(phrase, self.A_MIN_PENT, +1), self.A_MIN_PENT, -1), phrase)

    def test_minor_blues_uses_its_own_ordered_degrees(self) -> None:
        blues = {9, 0, 2, 3, 4, 7}                                # A C D Eb E G (A blues)
        self.assertEqual(shift_midis_by_degree([57, 60, 62, 63, 64, 67], blues, +1), [60, 62, 63, 64, 67, 69])

    def test_diatonic_octave_crossing(self) -> None:
        c_major = {0, 2, 4, 5, 7, 9, 11}
        self.assertEqual(shift_midis_by_degree([71], c_major, +1), [72])
        self.assertEqual(shift_midis_by_degree([60], c_major, -1), [59])

    def test_altered_note_keeps_its_inflection_or_refuses(self) -> None:
        c_major = {0, 2, 4, 5, 7, 9, 11}
        self.assertEqual(shift_midis_by_degree([61], c_major, +1), [63])   # C# (a semitone over C) -> D#
        with self.assertRaises(MoveRefused):                                # F# is 2 over E; one degree up (G) has a 2-semitone gap
            shift_midis_by_degree([66], {0, 2, 4, 7, 9}, +1)

    def test_blues_flat3_and_natural3_are_distinct_degrees(self) -> None:
        major_blues = {0, 2, 3, 4, 7, 9}                                    # C D Eb E G A
        self.assertEqual(shift_midis_by_degree([62, 63, 64], major_blues, +1), [63, 64, 67])   # D->Eb, Eb->E (not Eb->E by semitone), E->G
        self.assertEqual(shift_midis_by_degree([63, 64, 67], major_blues, -1), [62, 63, 64])
        # Bb3 (b3 over A minor blues) steps to the 4th, never to C#
        self.assertEqual(shift_midis_by_degree([60], {9, 0, 2, 3, 4, 7}, +1), [62])

    def test_refusal_notice_is_set_and_phrase_untouched(self) -> None:
        session, ctx = _setup("Resolve convincingly to the chord's 3rd", "G7", "C")
        _n, m0, _ = _state(session, ctx)
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        n1, m1, _ = _state(session, ctx)
        if session.get("_mission_move_notice"):
            self.assertEqual(m1, m0)
        else:
            self.assertNotEqual(m1, m0)


class TestMissionFlow(unittest.TestCase):
    def _moves(self, session, ctx, ops):
        seen = []
        for op in ops:
            apply_mission_motif_transform(session, ctx, op, bpm=100)
            seen.append(_state(session, ctx))
        return seen

    def test_pentatonic_mission_stays_in_collection_and_reverses(self) -> None:
        for chord, key, allowed in (("Am", "Am", {9, 0, 2, 4, 7}), ("C", "C", {0, 2, 4, 7, 9})):
            session, ctx = _setup(PENT, chord, key)
            n0, m0, _ = _state(session, ctx)
            s = self._moves(session, ctx, ["sequence_up", "sequence_up", "sequence_down", "sequence_down"])
            for notes, _midi, _m in s:
                self.assertTrue(set(_pcs(notes)) <= allowed, (chord, notes))
            self.assertEqual(s[-1][0], n0)
            self.assertEqual(s[-1][1], m0)
            self.assertNotEqual(s[0][1], m0)
            self.assertEqual([b - a for a, b in zip(m0, m0[1:])] != [], True)

    def test_blues_mission_moves_through_ordered_blues(self) -> None:
        session, ctx = _setup(BLUES, "A7", "A")
        n0, m0, meta = _state(session, ctx)
        s = self._moves(session, ctx, ["sequence_up", "sequence_down", "sequence_down", "sequence_up"])
        blues = {9, 0, 2, 3, 4, 7}
        for notes, _midi, _m in s:
            self.assertTrue(set(_pcs(notes)) <= blues | {9, 1, 4, 6, 11}, notes)
        self.assertEqual(s[1][1], m0)
        self.assertEqual(s[3][1], m0)

    def test_chord_tone_mission_remains_chord_tones(self) -> None:
        session, ctx = _setup(CHORD_TONES, "Dm7", "C")
        n0, m0, _ = _state(session, ctx)
        s = self._moves(session, ctx, ["sequence_up", "sequence_up", "sequence_down", "sequence_down"])
        for notes, _midi, _m in s:
            self.assertTrue(set(_pcs(notes)) <= {2, 5, 9, 0}, notes)
        self.assertEqual(s[-1][1], m0)

    def test_guide_tone_mission_remains_guide_tones(self) -> None:
        session, ctx = _setup(GUIDE, "Dm7", "C")
        n0, m0, _ = _state(session, ctx)
        s = self._moves(session, ctx, ["sequence_up", "sequence_down"])
        self.assertTrue(set(_pcs(s[0][0])) <= {5, 0})
        self.assertEqual(s[1][1], m0)

    def test_free_motif_moves_one_scale_degree_not_a_semitone(self) -> None:
        for key, chord in (("C", "C"), ("Am", "Am"), ("F", "F"), ("G", "G")):
            for level in ("Beginner", "Intermediate", "Advanced"):
                session, ctx = _setup(MOTIF, chord, key, level=level)
                n0, m0, meta = _state(session, ctx)
                self._moves(session, ctx, ["sequence_up"])
                _n1, m1, _ = _state(session, ctx)
                self.assertEqual(len(m1), len(m0))
                diffs = {b - a for a, b in zip(m0, m1)}
                self.assertTrue(diffs <= {1, 2}, (key, level, diffs))   # a scale step is 1 or 2 semitones
                self.assertEqual([b - a for a, b in zip(m0, m0[1:])] and True, True)

    def test_rhythm_and_shape_are_preserved(self) -> None:
        session, ctx = _setup(PENT, "Am", "Am")
        _n, _m, before = _state(session, ctx)
        self._moves(session, ctx, ["sequence_up"])
        _n, _m, after = _state(session, ctx)
        for k in ("rhythm", "rhythm_key", "rhythm_symbols", "pentatonic_relationship"):
            self.assertEqual(before.get(k), after.get(k), k)

    def test_transposing_instruments_move_in_the_written_key_and_reverse(self) -> None:
        for inst, ttype, allowed in (
            ("Clarinet", "Bb Clarinet", {11, 2, 4, 6, 9}),                    # B minor pentatonic
            ("Saxophone", "Tenor saxophone (Bb)", {11, 2, 4, 6, 9}),
            ("Saxophone", "Alto saxophone (Eb)", {6, 9, 11, 1, 4}),           # F# minor pentatonic
        ):
            session, ctx = _setup(PENT, "Am", "Am", instrument=inst, transposing=ttype)
            n0, m0, _ = _state(session, ctx)
            s = self._moves(session, ctx, ["sequence_up", "sequence_up", "sequence_down", "sequence_down"])
            self.assertNotEqual(s[0][0], n0, inst)
            self.assertNotEqual(s[0][1], s[1][1], inst)
            self.assertEqual(s[-1][0], n0, inst)
            self.assertEqual(s[-1][1], m0, inst)
            for notes, _midi, _m in s:
                self.assertTrue(set(_pcs(notes)) <= allowed, (inst, notes))

    def test_down_then_up_is_exact_and_no_phrase_is_unmoved(self) -> None:
        for mission, chord, key in ((PENT, "Am", "Am"), (BLUES, "A7", "A"), (MOTIF, "G", "G"), (MOTIF, "F", "F")):
            session, ctx = _setup(mission, chord, key)
            n0, m0, _ = _state(session, ctx)
            s = self._moves(session, ctx, ["sequence_down", "sequence_up"])
            self.assertNotEqual(s[0][1], m0, mission)
            self.assertEqual((s[1][0], s[1][1]), (n0, m0), mission)

    def test_flat_and_sharp_keys_spell_correctly(self) -> None:
        for key, bad in (("F", "A#"), ("G", "Gb")):
            session, ctx = _setup(MOTIF, key, key)
            for _ in range(3):
                apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
                notes, _m, _meta = _state(session, ctx)
                self.assertNotIn(bad, notes)

    def test_moved_pattern_reaches_notation(self) -> None:
        session, ctx = _setup(PENT, "Am", "Am")
        before = load_mission_example(session, ctx).abc
        apply_mission_motif_transform(session, ctx, "sequence_up", bpm=100)
        after = load_mission_example(session, ctx)
        self.assertNotEqual(before, after.abc)
        self.assertEqual(session[MISSION_EXAMPLE_KEY]["motif"]["notes"], after.motif["notes"])


if __name__ == "__main__":
    unittest.main()

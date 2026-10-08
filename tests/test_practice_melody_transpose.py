"""Tests for practice_melody_transpose.py -- the interval-preserving
transposition that lets a key change move an already-generated Practice
Melody without regenerating it (Slice F1).
"""

from __future__ import annotations

import unittest

from practice_melody_generator import generate_another_practice_melody, generate_practice_melody
from practice_melody_model import validate_practice_melody
from practice_melody_transpose import signed_semitone_interval, transpose_practice_melody

_MAJOR_SECTIONS = {
    "Verse 1": ["C", "Am", "F", "G"] * 2,
    "Chorus": ["F", "C", "G", "Am"] * 2,
}
_MINOR_SECTIONS = {
    "A": ["Am", "Dm7", "G7", "Cmaj7"] * 2,
}


def _melody(sections=None, key_center="C", level="Intermediate", **overrides):
    kwargs = dict(
        song_id="x", song_title="Test", sections=sections or _MAJOR_SECTIONS,
        key_center=key_center, level=level, tempo_bpm=96.0, style="Pop",
    )
    kwargs.update(overrides)
    return generate_practice_melody(**kwargs)


def _sounding_midis(melody):
    return [e.midi for s in melody.sections for e in s.events if not e.is_rest]


def _sounding_intervals(melody):
    midis = _sounding_midis(melody)
    return [b - a for a, b in zip(midis, midis[1:])]


class TestSignedSemitoneInterval(unittest.TestCase):
    def test_up_a_whole_step(self) -> None:
        self.assertEqual(signed_semitone_interval("C", "D"), 2)

    def test_down_a_whole_step_is_negative_not_ten(self) -> None:
        self.assertEqual(signed_semitone_interval("D", "C"), -2)

    def test_tritone_is_six(self) -> None:
        self.assertEqual(signed_semitone_interval("C", "F#"), 6)

    def test_same_key_is_zero(self) -> None:
        self.assertEqual(signed_semitone_interval("G", "G"), 0)

    def test_up_a_semitone_vs_down_eleven(self) -> None:
        # C -> Db must move register by +1, never +11 ("up by almost an octave").
        self.assertEqual(signed_semitone_interval("C", "Db"), 1)
        self.assertEqual(signed_semitone_interval("Db", "C"), -1)

    def test_round_trip_sums_to_zero(self) -> None:
        up = signed_semitone_interval("Bb", "F#")
        down = signed_semitone_interval("F#", "Bb")
        self.assertEqual(up + down, 0)


class TestNoOpCases(unittest.TestCase):
    def test_same_key_center_returns_identical_object(self) -> None:
        melody = _melody(key_center="G")
        self.assertIs(transpose_practice_melody(melody, new_key_center="G"), melody)

    def test_blank_key_center_is_a_no_op(self) -> None:
        melody = _melody(key_center="G")
        self.assertIs(transpose_practice_melody(melody, new_key_center=""), melody)
        self.assertIs(transpose_practice_melody(melody, new_key_center="   "), melody)


class TestIdentityPreservation(unittest.TestCase):
    def test_identity_fields_unchanged_by_transposition(self) -> None:
        melody = _melody(key_center="C")
        transposed = transpose_practice_melody(melody, new_key_center="D")
        self.assertEqual(transposed.melody_id, melody.melody_id)
        self.assertEqual(transposed.song_id, melody.song_id)
        self.assertEqual(transposed.song_title, melody.song_title)
        self.assertEqual(transposed.level, melody.level)
        self.assertEqual(transposed.seed, melody.seed)
        self.assertEqual(transposed.alt_index, melody.alt_index)
        self.assertEqual(transposed.generator_version, melody.generator_version)
        self.assertEqual(transposed.tempo_bpm, melody.tempo_bpm)
        self.assertEqual(transposed.style, melody.style)
        self.assertEqual(transposed.meter, melody.meter)
        self.assertEqual(transposed.section_order, melody.section_order)
        self.assertEqual(transposed.key_center, "D")
        self.assertNotEqual(transposed.key_center, melody.key_center)

    def test_rhythm_and_structure_unchanged(self) -> None:
        melody = _melody(key_center="C")
        transposed = transpose_practice_melody(melody, new_key_center="Eb")
        for before, after in zip(melody.sections, transposed.sections):
            self.assertEqual(before.section_id, after.section_id)
            self.assertEqual(before.measures, after.measures)
            self.assertEqual(before.beats_per_measure, after.beats_per_measure)
            self.assertEqual(before.repeat_of, after.repeat_of)
            for ev_before, ev_after in zip(before.events, after.events):
                self.assertEqual(ev_before.measure, ev_after.measure)
                self.assertEqual(ev_before.beat, ev_after.beat)
                self.assertEqual(ev_before.duration_beats, ev_after.duration_beats)
                self.assertEqual(ev_before.is_rest, ev_after.is_rest)
                self.assertEqual(ev_before.tone_role, ev_after.tone_role)


class TestIntervalPreservation(unittest.TestCase):
    """The core deterministic property the brief asks to test explicitly:
    every consecutive melodic interval must be identical before and after
    transposition, for several different target keys."""

    def test_intervals_preserved_across_several_targets(self) -> None:
        melody = _melody(key_center="C", level="Advanced")
        original_intervals = _sounding_intervals(melody)
        for target in ("D", "Eb", "F#", "Bb", "Ab"):
            transposed = transpose_practice_melody(melody, new_key_center=target)
            self.assertEqual(
                _sounding_intervals(transposed),
                original_intervals,
                f"intervals changed when transposing to {target}",
            )

    def test_absolute_shift_matches_signed_interval(self) -> None:
        melody = _melody(key_center="C")
        steps = signed_semitone_interval("C", "D")
        transposed = transpose_practice_melody(melody, new_key_center="D")
        before = _sounding_midis(melody)
        after = _sounding_midis(transposed)
        self.assertEqual([m + steps for m in before], after)

    def test_downward_transposition_does_not_jump_a_register(self) -> None:
        melody = _melody(key_center="D")
        transposed = transpose_practice_melody(melody, new_key_center="C")
        before = _sounding_midis(melody)
        after = _sounding_midis(transposed)
        # D -> C must move down 2 semitones, not up 10.
        self.assertEqual(after[0] - before[0], -2)


class TestRoundTrip(unittest.TestCase):
    def test_c_to_d_to_c_is_bit_identical(self) -> None:
        melody = _melody(key_center="C")
        out = transpose_practice_melody(transpose_practice_melody(melody, new_key_center="D"), new_key_center="C")
        self.assertEqual(out.to_dict(), melody.to_dict())

    def test_multi_hop_round_trip(self) -> None:
        melody = _melody(key_center="G", level="Beginner")
        hopped = melody
        for key in ("Bb", "F#", "Eb", "G"):
            hopped = transpose_practice_melody(hopped, new_key_center=key)
        self.assertEqual(hopped.to_dict(), melody.to_dict())


class TestStructuralValidity(unittest.TestCase):
    def test_transposed_melody_is_structurally_valid_major(self) -> None:
        melody = _melody(key_center="C")
        for target in ("D", "Eb", "F#", "Ab", "B"):
            transposed = transpose_practice_melody(melody, new_key_center=target)
            self.assertEqual(validate_practice_melody(transposed), [])

    def test_transposed_melody_is_structurally_valid_minor(self) -> None:
        melody = _melody(sections=_MINOR_SECTIONS, key_center="Am", level="Advanced")
        for target in ("Bm", "C#m", "Fm"):
            transposed = transpose_practice_melody(melody, new_key_center=target)
            self.assertEqual(validate_practice_melody(transposed), [])


class TestMinorKeyChordTransposition(unittest.TestCase):
    def test_minor_chord_qualities_preserved(self) -> None:
        melody = _melody(sections=_MINOR_SECTIONS, key_center="Am", level="Advanced")
        transposed = transpose_practice_melody(melody, new_key_center="Bm")
        self.assertEqual(transposed.sections[0].chords[0], "Bm")
        self.assertEqual(transposed.sections[0].chords[1], "Em7")
        self.assertEqual(transposed.sections[0].chords[2], "A7")
        self.assertEqual(transposed.sections[0].chords[3], "Dmaj7")

    def test_event_chord_field_matches_section_chord(self) -> None:
        melody = _melody(sections=_MINOR_SECTIONS, key_center="Am", level="Advanced")
        transposed = transpose_practice_melody(melody, new_key_center="Bm")
        section = transposed.sections[0]
        for event in section.events:
            self.assertEqual(event.chord, section.chords[event.measure])


class TestGenerateAnotherVsTransposeDistinction(unittest.TestCase):
    """Item 7 from the brief, encoded explicitly: a key change transposes
    the same composition; 'Generate Another' produces a different one."""

    def test_transpose_then_generate_another_then_transpose_back(self) -> None:
        melody_a_in_c = _melody(key_center="C")
        melody_a_in_d = transpose_practice_melody(melody_a_in_c, new_key_center="D")
        self.assertEqual(melody_a_in_d.alt_index, melody_a_in_c.alt_index)
        self.assertEqual(melody_a_in_d.melody_id, melody_a_in_c.melody_id)

        melody_b_in_d = generate_another_practice_melody(melody_a_in_d)
        self.assertNotEqual(melody_b_in_d.alt_index, melody_a_in_d.alt_index)
        self.assertNotEqual(melody_b_in_d.melody_id, melody_a_in_d.melody_id)
        self.assertEqual(melody_b_in_d.key_center, "D")

        melody_b_in_c = transpose_practice_melody(melody_b_in_d, new_key_center="C")
        # Same composition as B (same identity), transposed -- NOT melody A,
        # and NOT a freshly generated "melody C".
        self.assertEqual(melody_b_in_c.alt_index, melody_b_in_d.alt_index)
        self.assertEqual(melody_b_in_c.melody_id, melody_b_in_d.melody_id)
        self.assertNotEqual(melody_b_in_c.melody_id, melody_a_in_c.melody_id)
        self.assertNotEqual(
            [e.midi for s in melody_b_in_c.sections for e in s.events if not e.is_rest],
            [e.midi for s in melody_a_in_c.sections for e in s.events if not e.is_rest],
            "melody B transposed back to C must not coincidentally equal melody A",
        )


if __name__ == "__main__":
    unittest.main()

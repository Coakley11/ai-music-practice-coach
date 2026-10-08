"""Tests for the Practice Melody -> ABC bridge (practice_melody_notation.py).

Confirms the bridge produces well-formed ABC via the *existing*
composition_melody_notation.build_abc_from_melody_events pipeline (no
second notation system) and correctly derives octave-qualified pitch
tokens from MelodyEvent's (pitch, midi) pair.
"""

from __future__ import annotations

import unittest

from practice_melody_generator import generate_practice_melody
from practice_melody_notation import (
    _octave_qualified_pitch,
    practice_melody_full_song_abc,
    practice_melody_section_abc,
    practice_melody_sections_abc,
)

_SECTIONS = {
    "Verse 1": ["G", "Em7", "Cadd9", "D"] * 2,
    "Chorus": ["C", "G", "Am7", "F"] * 2,
}


def _melody(level="Intermediate"):
    return generate_practice_melody(
        song_id="abc-test", song_title="ABC Test Song", sections=_SECTIONS,
        key_center="G", level=level, tempo_bpm=96.0, style="Pop",
    )


class TestOctaveQualifiedPitch(unittest.TestCase):
    def test_middle_c_is_octave_4(self) -> None:
        self.assertEqual(_octave_qualified_pitch("C", 60), "C4")

    def test_rest_has_no_octave(self) -> None:
        self.assertEqual(_octave_qualified_pitch(None, None), "rest")

    def test_sharp_pitch_class_preserved(self) -> None:
        self.assertEqual(_octave_qualified_pitch("F#", 66), "F#4")


class TestAbcGeneration(unittest.TestCase):
    def test_full_song_abc_has_expected_headers(self) -> None:
        abc = practice_melody_full_song_abc(_melody())
        self.assertIn("X:1", abc)
        self.assertIn("M:4/4", abc)
        self.assertIn("K:G", abc)
        self.assertIn("ABC Test Song", abc)

    def test_section_abc_uses_section_title(self) -> None:
        melody = _melody()
        abc = practice_melody_section_abc(melody, melody.sections[0])
        self.assertIn("Verse 1", abc)

    def test_full_song_abc_contains_one_bar_separator_per_measure_at_least(self) -> None:
        melody = _melody()
        abc = practice_melody_full_song_abc(melody)
        total_measures = sum(s.measures for s in melody.sections)
        # build_abc_from_melody_events emits "|" once beats_in_bar reaches the
        # bar length, so there should be at least one per measure generated.
        self.assertGreaterEqual(abc.count("|"), total_measures)

    def test_rests_render_as_z(self) -> None:
        melody = _melody(level="Beginner")
        abc = practice_melody_full_song_abc(melody)
        has_rest = any(e.is_rest for s in melody.sections for e in s.events)
        if has_rest:
            self.assertIn("z", abc)

    def test_long_song_wraps_into_multiple_staff_lines(self) -> None:
        big_sections = {f"S{i}": ["G", "C", "D", "Em"] for i in range(20)}
        melody = generate_practice_melody(
            song_id="wrap-test", song_title="Wrap Test", sections=big_sections,
            key_center="G", level="Intermediate", tempo_bpm=100.0, style="",
        )
        abc = practice_melody_full_song_abc(melody)
        music_lines = abc.split("\n")[6:]
        self.assertGreater(len(music_lines), 1, "an 80-measure song should wrap onto several staff lines")

    def test_short_song_is_not_wrapped_unnecessarily(self) -> None:
        melody = _melody()
        abc = practice_melody_full_song_abc(melody)
        music_lines = abc.split("\n")[6:]
        total_measures = sum(s.measures for s in melody.sections)
        if total_measures <= 4:
            self.assertEqual(len(music_lines), 1)

    def test_sections_abc_with_all_sections_equals_full_song(self) -> None:
        melody = _melody()
        self.assertEqual(
            practice_melody_sections_abc(melody, list(melody.sections)),
            practice_melody_full_song_abc(melody),
        )

    def test_sections_abc_with_single_section_equals_section_abc(self) -> None:
        melody = _melody()
        chorus = melody.section_by_id("Chorus")
        self.assertEqual(
            practice_melody_sections_abc(melody, [chorus]),
            practice_melody_section_abc(melody, chorus),
        )

    def test_sections_abc_subset_is_shorter_than_full_song(self) -> None:
        melody = _melody()
        verse = melody.section_by_id("Verse 1")
        subset_abc = practice_melody_sections_abc(melody, [verse])
        full_abc = practice_melody_full_song_abc(melody)
        self.assertLess(subset_abc.count("|"), full_abc.count("|"))

    def test_no_raw_json_keys_leak_into_abc_text(self) -> None:
        abc = practice_melody_full_song_abc(_melody())
        for forbidden in ("tone_role", "duration_beats", "is_rest", "{"):
            self.assertNotIn(forbidden, abc)


if __name__ == "__main__":
    unittest.main()

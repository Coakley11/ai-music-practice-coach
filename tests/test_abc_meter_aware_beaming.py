"""Meter-aware eighth-note beaming in the shared ABC builders.

ABC uses whitespace as the beam separator, so the previous unconditional
``" ".join(tokens)`` rendered every eighth note individually flagged. These
pin the beat-group grouping, the cases that must still break a beam, and --
most importantly -- that only whitespace changed: pitches, durations, order,
bar lines, articulations and slurs are identical to the pre-change output.
"""

from __future__ import annotations

import unittest

from chord_navigation_notation import (
    build_connected_piano_voicings,
    build_piano_voicing_abc,
)
from composition_melody_notation import (
    abc_beat_group_eighths,
    build_abc_from_melody_events,
    join_abc_tokens_with_beams,
)


def _music(abc: str) -> str:
    return abc.split("\n")[-1]


def _note(pitch: str, dur: float, **extra) -> dict:
    ev = {"pitch": pitch, "duration_beats": dur, "is_rest": False}
    ev.update(extra)
    return ev


def _rest(dur: float) -> dict:
    return {"pitch": "rest", "duration_beats": dur, "is_rest": True}


class TestBeatGroupUnits(unittest.TestCase):
    def test_simple_meters_group_by_quarter(self) -> None:
        for meter in ("4/4", "3/4", "2/4", "5/4"):
            self.assertEqual(abc_beat_group_eighths(meter), 2, meter)

    def test_compound_meters_group_by_dotted_quarter(self) -> None:
        self.assertEqual(abc_beat_group_eighths("6/8"), 3)


class TestJoinHelper(unittest.TestCase):
    def test_same_group_beamable_tokens_are_adjacent(self) -> None:
        entries = [("c", True, (0, 0), False), ("d", True, (0, 0), False)]
        self.assertEqual(join_abc_tokens_with_beams(entries), "cd")

    def test_group_change_inserts_a_space(self) -> None:
        entries = [("c", True, (0, 0), False), ("d", True, (0, 1), False)]
        self.assertEqual(join_abc_tokens_with_beams(entries), "c d")

    def test_non_beamable_token_breaks_the_beam(self) -> None:
        entries = [
            ("c", True, (0, 0), False),
            ("z2", False, None, True),
            ("d", True, (0, 1), False),
        ]
        self.assertEqual(join_abc_tokens_with_beams(entries), "c z2 d")

    def test_break_before_wins_even_inside_a_group(self) -> None:
        entries = [("c", True, (0, 0), False), ('"G7"d', True, (0, 0), True)]
        self.assertEqual(join_abc_tokens_with_beams(entries), 'c "G7"d')


class TestMelodyBuilderBeaming(unittest.TestCase):
    def test_four_four_beams_eighths_in_beat_pairs(self) -> None:
        events = [_note("C4", 0.5), _note("D4", 0.5), _note("E4", 0.5), _note("F4", 0.5),
                  _note("G4", 1.0), _note("A4", 1.0)]
        music = _music(build_abc_from_melody_events(events, key="C", meter="4/4"))
        self.assertEqual(music, "cd ef g2 a2 |")

    def test_three_four_beams_eighths_in_beat_pairs(self) -> None:
        events = [_note("C4", 0.5), _note("D4", 0.5), _note("E4", 0.5), _note("F4", 0.5),
                  _note("G4", 1.0)]
        music = _music(build_abc_from_melody_events(events, key="C", meter="3/4"))
        self.assertEqual(music, "cd ef g2 |")

    def test_six_eight_beams_eighths_in_threes(self) -> None:
        # Compound meter counts eighths, so six events of 1.0 fill one 6/8 bar.
        events = [_note(p, 1.0) for p in ("C4", "D4", "E4", "F4", "G4", "A4")]
        music = _music(build_abc_from_melody_events(events, key="C", meter="6/8"))
        self.assertEqual(music, "cde fga |")

    def test_rest_breaks_the_beam(self) -> None:
        events = [_note("C4", 0.5), _rest(0.5), _note("E4", 0.5), _note("F4", 0.5),
                  _note("G4", 1.0), _note("A4", 1.0)]
        music = _music(build_abc_from_melody_events(events, key="C", meter="4/4"))
        self.assertEqual(music, "c z ef g2 a2 |")

    def test_quarter_note_is_never_beamed(self) -> None:
        events = [_note("C4", 1.0), _note("D4", 1.0), _note("E4", 1.0), _note("F4", 1.0)]
        music = _music(build_abc_from_melody_events(events, key="C", meter="4/4"))
        self.assertEqual(music, "c2 d2 e2 f2 |")

    def test_chord_annotation_starts_its_own_beam_group(self) -> None:
        events = [_note("C4", 0.5), _note("D4", 0.5), _note("E4", 0.5), _note("F4", 0.5),
                  _note("G4", 1.0), _note("A4", 1.0)]
        music = _music(
            build_abc_from_melody_events(events, key="C", meter="4/4", chords=["C", "G"])
        )
        # The symbol anchors the note it sits on rather than being swallowed
        # into the middle of a beam.
        self.assertIn('"C"cd', music)
        self.assertTrue(music.startswith('"C"cd ef'))

    def test_barline_count_is_unchanged_by_beaming(self) -> None:
        events = [_note("C4", 0.5) for _ in range(16)]
        music = _music(build_abc_from_melody_events(events, key="C", meter="4/4"))
        self.assertEqual(music.count("|"), 2)

    def test_articulation_and_slur_survive_beaming(self) -> None:
        events = [
            _note("C4", 0.5, articulation="accent", slur="start"),
            _note("D4", 0.5, articulation="staccato"),
            _note("E4", 0.5),
            _note("F4", 0.5, slur="end"),
            _note("G4", 2.0),
        ]
        music = _music(build_abc_from_melody_events(events, key="C", meter="4/4"))
        self.assertIn("!>!", music)
        self.assertIn(".d", music)
        self.assertIn("(", music)
        self.assertIn(")", music)
        # Beamed pair still carries both the accent and the staccato.
        self.assertIn("(!>!c.d", music)


class TestOnlyWhitespaceChanged(unittest.TestCase):
    """Pitches, durations and order must be byte-identical to pre-change output.

    The goldens are the space-stripped music lines captured from the builder
    before beaming was introduced; beaming only ever removes separators, so
    stripping spaces must reproduce them exactly.
    """

    def _assert_content(self, abc: str, golden_no_spaces: str) -> None:
        self.assertEqual(_music(abc).replace(" ", ""), golden_no_spaces)

    def test_practice_melody_content_unchanged(self) -> None:
        from practice_melody_generator import generate_practice_melody
        from practice_melody_notation import practice_melody_section_abc

        melody = generate_practice_melody(
            song_id="aud", song_title="Audit",
            sections={"Verse 1": ["Dm7", "G7", "Cmaj7", "A7"]},
            key_center="C", level="Intermediate", tempo_bpm=120.0,
            style="Jazz", meter=(4, 4), seed=7, focus="Pentatonics",
        )
        abc = practice_melody_section_abc(melody, melody.sections[0])
        self._assert_content(
            abc,
            '"Dm7"z2(!>!c2d4)|"G7"(!>!g4d4)|"Cmaj7"(!>!c.c_a2.c\'.ad\'2)|"A7"(!>!a2^c\'2a4)|',
        )

    def test_notation_exercise_content_unchanged(self) -> None:
        from chord_navigation_notation import (
            arpeggio_events_to_melody_dicts,
            build_connected_arpeggio_line,
        )

        events = build_connected_arpeggio_line(
            ["Dm7", "G7", "Cmaj7", "A7"], level="Advanced",
            beats_per_measure=4, instrument="Saxophone", focus="",
        )
        abc = build_abc_from_melody_events(
            arpeggio_events_to_melody_dicts(events), key="C", meter="4/4", bpm=120, title="n"
        )
        self._assert_content(
            abc,
            "(!>!fa2c'd'2.c'2|!>!bgfdBG.B2|!>!c2egbc'._a2|!>!ge2^c2AG2)|",
        )


class TestPianoVoicingBeaming(unittest.TestCase):
    def test_eighth_voicing_hits_on_one_beat_are_beamed(self) -> None:
        events = build_connected_piano_voicings(
            ["Dm7", "G7", "Cmaj7", "A7"], level="Advanced"
        )
        music = _music(build_piano_voicing_abc(events, key="C", meter="4/4", bpm=100, title="p"))
        # At least one adjacent pair of bare (eighth) voicings, i.e. beamed.
        self.assertRegex(music, r"\]\[")
        self.assertIn("|", music)

    def test_chord_symbol_still_opens_each_measure(self) -> None:
        events = build_connected_piano_voicings(["Dm7", "G7"], level="Intermediate")
        music = _music(build_piano_voicing_abc(events, key="C", meter="4/4", bpm=100, title="p"))
        self.assertIn('"Dm7"[', music)
        self.assertIn('"G7"[', music)

    def test_whole_measure_voicings_are_not_beamed(self) -> None:
        events = build_connected_piano_voicings(["Dm7", "Cmaj7"], level="Beginner")
        music = _music(build_piano_voicing_abc(events, key="C", meter="4/4", bpm=100, title="p"))
        # Beginner holds one voicing per bar: every token is long, so no beams.
        self.assertNotRegex(music, r"\]\[")


if __name__ == "__main__":
    unittest.main()

"""Piano exercises belong on two staves.

Everything else in this app writes one staff, so the piano exercise arrived as a single
treble line of block chords - right harmony, wrong instrument. This module is a rendering
adapter over the events the existing builders already produce; the only musical judgement
it makes is which hand plays what.
"""

from __future__ import annotations

import inspect
import unittest

from piano_grand_staff import (
    MIDDLE_C,
    PIANO_HIGH,
    PIANO_LOW,
    grand_staff_abc,
    hands_for_scale,
    in_piano_range,
    split_hands,
)

BARS = [[[45, 52, 60, 64]], [[48, 55, 64, 67]], [[47, 54, 62, 66]], [[45, 52, 60, 64]]]
CHORDS = ["Am6", "C7", "B7", "Em6"]


class HandSplitting(unittest.TestCase):
    def test_notes_below_middle_c_go_to_the_left_hand(self):
        left, right = split_hands([48, 55, 64, 67])
        self.assertEqual(left, [48, 55])
        self.assertEqual(right, [64, 67])

    def test_the_split_point_is_middle_c(self):
        left, right = split_hands([MIDDLE_C - 1, MIDDLE_C])
        self.assertEqual(left, [MIDDLE_C - 1])
        self.assertEqual(right, [MIDDLE_C])

    def test_a_voicing_entirely_in_the_treble_still_gives_the_bass_a_note(self):
        left, right = split_hands([72, 76, 79])
        self.assertTrue(left, "bass staff would have been empty")
        self.assertTrue(right)
        self.assertLess(max(left), min(right))

    def test_a_voicing_entirely_in_the_bass_is_left_alone(self):
        """Two hands low is real music; inventing a treble note would not be."""
        left, right = split_hands([36, 43])
        self.assertEqual(left, [36, 43])
        self.assertEqual(right, [])

    def test_a_single_note_is_not_torn_in_half(self):
        self.assertEqual(split_hands([72]), ([], [72]))

    def test_empty_input_is_safe(self):
        self.assertEqual(split_hands([]), ([], []))

    def test_order_does_not_matter(self):
        self.assertEqual(split_hands([67, 48, 64, 55]), split_hands([48, 55, 64, 67]))


class TheEmittedAbcIsAGrandStaff(unittest.TestCase):
    def setUp(self):
        self.abc = grand_staff_abc(BARS, key="Am", chords=CHORDS, title="T")

    def test_it_braces_the_two_staves(self):
        self.assertIn("%%score {1 | 2}", self.abc)

    def test_it_declares_a_treble_and_a_bass_voice(self):
        self.assertIn("V:1 clef=treble", self.abc)
        self.assertIn("V:2 clef=bass", self.abc)

    def test_both_voices_carry_music(self):
        tail = self.abc.split("V:2 clef=bass", 1)[1]
        v1 = tail.split("V:1", 1)[1].split("V:2", 1)[0]
        v2 = tail.split("V:2", 1)[1]
        self.assertTrue(v1.strip())
        self.assertTrue(v2.strip())

    def test_the_chord_symbol_appears_once_per_bar_not_twice(self):
        """Printing it over both staves would draw the same label on each."""
        self.assertEqual(self.abc.count('"Am6"'), 1)
        self.assertEqual(self.abc.count('"C7"'), 1)

    def test_every_bar_is_rendered(self):
        v1 = self.abc.split("V:1\n", 1)[1].split("\nV:2", 1)[0]
        self.assertEqual(v1.count("|"), len(BARS))

    def test_the_key_signature_is_present(self):
        self.assertIn("K:", self.abc)

    def test_the_tempo_is_carried_through(self):
        self.assertIn("Q:1/4=96", grand_staff_abc(BARS, bpm=96))

    def test_an_empty_bar_becomes_a_rest_rather_than_breaking_the_bar(self):
        self.assertIn("z", grand_staff_abc([[[]]], key="C"))

    def test_no_bars_at_all_is_safe(self):
        self.assertIn("%%score", grand_staff_abc([]))

    def test_several_hits_in_one_bar_still_fill_it(self):
        abc = grand_staff_abc([[[48, 64], [48, 64]]], key="C", beats_per_bar=4)
        v1 = abc.split("V:1\n", 1)[1].split("\nV:2", 1)[0]
        self.assertEqual(v1.count("4"), 2)  # two hits of four eighths each


class ScaleMotions(unittest.TestCase):
    LINE = [57, 59, 60, 62, 64, 66, 67, 69]

    def test_parallel_hands_move_together_an_octave_apart(self):
        voicings = hands_for_scale(self.LINE, motion="parallel")
        self.assertEqual(len(voicings), len(self.LINE))
        for v in voicings:
            self.assertEqual(len(v), 2)
            self.assertEqual(max(v) - min(v), 12)

    A_DORIAN = (9, 11, 0, 2, 4, 6, 7)   # A B C D E F# G

    def test_contrary_hands_move_in_opposite_directions(self):
        voicings = hands_for_scale(
            self.LINE, motion="contrary", scale_pcs=self.A_DORIAN)
        lefts = [min(v) for v in voicings]
        rights = [max(v) for v in voicings]
        self.assertGreater(rights[-1], rights[0])
        self.assertLess(lefts[-1], lefts[0])

    def test_the_descending_hand_stays_inside_the_scale(self):
        """It walks the scale by degree. Mirroring the line in semitones does not: over
        A Dorian that produced G#, C# and F natural - the exercise contradicting itself."""
        for v in hands_for_scale(self.LINE, motion="contrary", scale_pcs=self.A_DORIAN):
            for m in v:
                with self.subTest(midi=m):
                    self.assertIn(m % 12, self.A_DORIAN)

    def test_the_descending_hand_really_descends_stepwise(self):
        lefts = [min(v) for v in
                 hands_for_scale(self.LINE, motion="contrary", scale_pcs=self.A_DORIAN)]
        for a, b in zip(lefts, lefts[1:]):
            self.assertTrue(1 <= a - b <= 2, f"{a} -> {b} is not a scale step")

    def test_contrary_without_a_scale_falls_back_rather_than_guessing(self):
        """No scale, no invention: it plays parallel instead of inventing notes."""
        self.assertEqual(
            hands_for_scale(self.LINE, motion="contrary"),
            hands_for_scale(self.LINE, motion="parallel"),
        )

    def test_separate_keeps_one_hand(self):
        for v in hands_for_scale(self.LINE, motion="separate"):
            self.assertEqual(len(v), 1)

    def test_every_motion_stays_on_the_keyboard(self):
        for motion in ("parallel", "contrary", "separate"):
            for v in hands_for_scale(self.LINE, motion=motion):
                for m in v:
                    with self.subTest(motion=motion, midi=m):
                        self.assertTrue(in_piano_range(m))

    def test_an_extreme_line_is_folded_back_onto_the_keyboard(self):
        for v in hands_for_scale([21, 108], motion="parallel"):
            for m in v:
                self.assertTrue(PIANO_LOW <= m <= PIANO_HIGH)

    def test_an_empty_line_is_safe(self):
        self.assertEqual(hands_for_scale([]), [])

    def test_an_unknown_motion_falls_back_to_parallel(self):
        self.assertEqual(
            hands_for_scale(self.LINE, motion="sideways"),
            hands_for_scale(self.LINE, motion="parallel"),
        )

    def test_scales_render_as_a_grand_staff_too(self):
        abc = grand_staff_abc(
            [hands_for_scale(self.LINE, motion="parallel")], key="Am", beats_per_bar=4
        )
        self.assertIn("V:2 clef=bass", abc)
        self.assertIn("%%score", abc)


class ItDoesNotReinventHarmony(unittest.TestCase):
    def test_spelling_comes_from_the_apps_own_speller(self):
        """F# in A minor must be written as an altered F, not as a G flat."""
        self.assertIn("^F", grand_staff_abc([[[66]]], key="Am"))
        self.assertNotIn("_G", grand_staff_abc([[[66]]], key="Am"))

    def test_the_adapter_takes_events_rather_than_deciding_music(self):
        params = inspect.signature(grand_staff_abc).parameters
        self.assertIn("bars", params)
        self.assertNotIn("level", params)
        self.assertNotIn("focus", params)


if __name__ == "__main__":
    unittest.main()


class OctavesSurviveIntoTheAbc(unittest.TestCase):
    """The bug this class exists for.

    ``abc_pitch_for_spelled_note`` takes the octave as a keyword argument and does not read
    one off the end of the note name, so passing "E3" spelled E at the default octave 4.
    Every note of every piano exercise came out in one octave: the two staves printed
    identical tokens and the left hand sat four ledger lines above the bass staff. Every
    test here read pitch *classes*, so none of them noticed. These read octaves.
    """

    def test_the_same_pitch_class_an_octave_apart_is_not_the_same_token(self):
        abc = grand_staff_abc([[[52, 64]]], key="G")
        treble = abc.split("V:1\n", 1)[1].split("\nV:2", 1)[0]
        bass = abc.split("V:2\n", 1)[1]
        self.assertNotEqual(treble.strip(), bass.strip())

    def test_the_two_staves_of_a_parallel_scale_differ(self):
        line = [64, 66, 67, 69, 71, 72]
        abc = grand_staff_abc([hands_for_scale(line, motion="parallel")], key="G")
        treble = abc.split("V:1\n", 1)[1].split("\nV:2", 1)[0]
        bass = abc.split("V:2\n", 1)[1]
        self.assertNotEqual(treble.strip(), bass.strip())

    def test_abc_octave_marks_follow_the_midi_octave(self):
        """ABC, as abcjs decodes it: "C," is 48, "C" is 60 (middle C), "c" is 72.

        Asserted the other way round until now - "c" for middle C - which is what the
        app's speller writes and one octave above what abcjs plays. See
        tests/test_piano_abc_round_trip.py and scripts/_proof_piano_grand_staff_abcjs.py.
        """
        self.assertIn("C,", grand_staff_abc([[[48]]], key="C").split("V:2\n")[1])
        self.assertIn("C", grand_staff_abc([[[60]]], key="C").split("V:1\n")[1])
        self.assertIn("c", grand_staff_abc([[[72]]], key="C").split("V:1\n")[1])

    def test_a_low_note_gets_a_comma(self):
        self.assertIn("C,", grand_staff_abc([[[36]]], key="C").split("V:2\n")[1])

    def test_the_left_hand_really_lands_on_the_bass_staff(self):
        """Within two ledger lines of it, rather than floating above the treble."""
        line = [60, 62, 64, 65, 67, 69, 71, 72]
        for v in hands_for_scale(line, motion="parallel"):
            with self.subTest(voicing=v):
                self.assertLessEqual(min(v), 62)   # at or below D4


class SpellingFollowsTheKeySignature(unittest.TestCase):
    def test_a_sharp_the_key_already_carries_needs_no_accidental(self):
        """K:G carries F#, so the token is a bare f - not ^f repeated on every note."""
        bass = grand_staff_abc([[[54]]], key="G").split("V:2\n", 1)[1]
        self.assertNotIn("^", bass)

    def test_a_sharp_the_key_does_not_carry_is_written_out(self):
        self.assertIn("^F", grand_staff_abc([[[66]]], key="Am"))

    def test_a_note_the_key_would_sharpen_is_naturalled(self):
        """In G major a bare "f" reads as F#; an F natural has to say so."""
        tok = grand_staff_abc([[[65]]], key="G")   # F4 natural
        self.assertIn("=", tok)

"""The musician-facing melody description says only what the notes actually do (2026-11-20).

The card used to print measurements ("17 notes over 4 bars (4.3 per bar); 75% of structural beats land on chord
tones..."). musical_summary writes two plain sentences from those same measurements, so every claim has to be
gated on the measurement behind it: no chromatic claim without chromatic notes, no stepwise claim over a leaping
line, and - the trap - "stays inside the key" must mean the KEY's scale, never "these notes belong to the chords".
"""

import unittest

from composition_melody_describe import melody_features, musical_summary

PITCH = {
    48: "C3", 50: "D3", 52: "E3", 53: "F3",
    55: "G3", 57: "A3", 59: "B3", 60: "C4", 61: "C#4", 62: "D4", 63: "D#4", 64: "E4", 65: "F4",
    66: "F#4", 67: "G4", 68: "G#4", 69: "A4", 70: "A#4", 71: "B4", 72: "C5", 74: "D5", 76: "E5",
    77: "F5", 79: "G5",
}


def ev(midis, *, dur=1.0, start=0.0, articulation=""):
    out = []
    beat = start
    for m in midis:
        row = {"pitch": PITCH.get(m, f"m{m}"), "midi": m, "beat": beat, "duration_beats": dur}
        if articulation:
            row["articulation"] = articulation
        out.append(row)
        beat += dur
    return out


CH4 = ["C", "F", "G", "C"]


class TestHarmonyClaims(unittest.TestCase):
    def test_a_diatonic_line_is_called_diatonic(self) -> None:
        events = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertEqual(melody_features(events, CH4, key="C")["chromatic_tones"], 0)
        self.assertIn("inside the key", text)
        self.assertNotIn("outside the key", text)
        self.assertNotIn("chromatic", text)

    def test_a_chromatic_line_is_not_called_diatonic(self) -> None:
        events = ev([60, 61, 62, 63, 64, 65, 66, 67, 68, 67, 66, 65, 64, 63, 62, 60])
        f = melody_features(events, CH4, key="C")
        self.assertGreater(f["chromatic_tones"], 1)
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertNotIn("inside the key", text)
        self.assertTrue("chromatic" in text or "outside the key" in text, text)

    def test_chord_tones_outside_the_key_are_not_called_inside_the_key(self) -> None:
        """The trap: over A7 in C, C# and G are chord tones but C# is NOT in the key of C."""
        chords = ["A7", "A7", "A7", "A7"]
        events = ev([57, 61, 64, 67, 57, 61, 64, 67, 69, 67, 64, 61, 57, 61, 64, 57])
        f = melody_features(events, chords, key="C")
        self.assertGreaterEqual(f["strong_chord_tone_share"], 0.9)  # every strong beat IS a chord tone
        self.assertGreater(f["chromatic_tones"], 0)  # ... and some of them are outside the key
        text = musical_summary(events, chords, key="C", meter="4/4")
        self.assertIn("chord tones", text)
        self.assertNotIn("inside the key", text)

    def test_one_passing_chromatic_note_is_not_called_a_chromatic_style(self) -> None:
        events = ev([60, 62, 64, 65, 66, 67, 65, 64, 60, 62, 64, 65, 67, 65, 64, 60])
        f = melody_features(events, CH4, key="C")
        if f["chromatic_tones"] != 1:
            self.skipTest("fixture no longer has exactly one chromatic note")
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertNotIn("a few notes from outside the key", text)
        self.assertNotIn("inside the key", text)


class TestMotionClaims(unittest.TestCase):
    def test_a_stepwise_line_is_not_called_leaping(self) -> None:
        events = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        self.assertGreaterEqual(melody_features(events, CH4, key="C")["stepwise_share"], 0.9)
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertIn("small steps", text)
        self.assertNotIn("frequent jumps", text)

    def test_a_leaping_line_is_not_called_stepwise(self) -> None:
        events = ev([60, 72, 62, 74, 60, 71, 64, 76, 60, 72, 64, 72, 60, 74, 64, 72])
        f = melody_features(events, CH4, key="C")
        self.assertLess(f["stepwise_share"], 0.3)
        self.assertGreaterEqual(f["largest_leap"], 7)
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertIn("jumps", text)
        self.assertNotIn("almost entirely by small steps", text)

    def test_a_mixed_line_says_steps_and_leaps(self) -> None:
        events = ev([60, 62, 64, 71, 69, 67, 65, 64, 60, 62, 64, 72, 69, 67, 65, 60])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertTrue("expressive leaps" in text or "steps and skips" in text, text)


class TestShapeClaims(unittest.TestCase):
    def test_a_rising_line_reads_as_rising(self) -> None:
        events = ev([55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 72, 74, 76, 79])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertTrue("climbs" in text or "rises" in text, text)
        self.assertNotIn("mostly descends", text)

    def test_a_falling_line_reads_as_falling(self) -> None:
        events = ev([79, 76, 74, 72, 71, 69, 67, 65, 64, 62, 60, 59, 57, 59, 57, 55])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertIn("descends", text)
        self.assertNotIn("climbs toward a high note", text)

    def test_an_arch_reads_as_up_then_down(self) -> None:
        events = ev([60, 62, 64, 67, 69, 72, 74, 76, 74, 72, 69, 67, 64, 62, 60, 60])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertIn("comes back down", text)

    def test_a_narrow_line_says_narrow(self) -> None:
        events = ev([60, 62, 60, 62, 64, 62, 60, 62, 60, 62, 64, 62, 60, 62, 60, 60])
        self.assertLessEqual(melody_features(events, CH4, key="C")["range_semitones"], 4)
        self.assertIn("narrow range", musical_summary(events, CH4, key="C", meter="4/4"))


class TestCharacterAndShape(unittest.TestCase):
    def test_syncopation_is_only_claimed_when_accents_fall_off_the_beat(self) -> None:
        on_beat = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        self.assertNotIn("syncopated", musical_summary(on_beat, CH4, key="C", meter="4/4"))
        off = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65], dur=0.5, start=0.5,
                 articulation="accent")
        f = melody_features(off, CH4, key="C")
        self.assertGreaterEqual(f["accented_offbeat_attacks"], 2)
        self.assertIn("syncopated", musical_summary(off, CH4, key="C", meter="4/4"))

    def test_the_genre_word_is_used_only_when_given(self) -> None:
        events = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        self.assertTrue(musical_summary(events, CH4, key="C").startswith("A phrase"))
        self.assertTrue(
            musical_summary(events, CH4, key="C", style_word="jazz").startswith("A jazz phrase")
        )

    def test_it_is_two_sentences_and_carries_no_statistics(self) -> None:
        events = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        text = musical_summary(events, CH4, key="C", meter="4/4", style_word="pop")
        self.assertEqual(text.count(". "), 1)
        self.assertTrue(text.endswith("."))
        for token in ("%", "notes over", "per bar", "attacks", "cell"):
            self.assertNotIn(token, text)

    def test_an_empty_melody_says_so(self) -> None:
        self.assertIn("No pitched notes", musical_summary([], CH4, key="C"))

    def test_two_different_melodies_do_not_read_the_same(self) -> None:
        """A card the musician cannot tell apart from its neighbour is useless for comparing.

        The shape/movement vocabulary is deliberately coarse, so the description also names where the line
        starts and how high it reaches - the two notes that keep otherwise similar cards distinct.
        """
        melodies = [
            ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60]),
            ev([55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 72, 71, 69, 67]),
            ev([67, 65, 64, 62, 60, 62, 64, 62, 60, 59, 57, 55, 57, 59, 57, 55]),
            ev([60, 72, 62, 74, 60, 71, 64, 76, 60, 72, 64, 72, 60, 74, 64, 72]),
            ev([62, 64, 65, 67, 69, 67, 65, 64, 62, 64, 65, 67, 69, 67, 65, 62]),
        ]
        texts = [musical_summary(m, CH4, key="C", meter="4/4", style_word="pop") for m in melodies]
        self.assertEqual(len(set(texts)), len(texts), texts)

    def test_the_description_names_a_note_from_the_melody(self) -> None:
        events = ev([62, 64, 65, 67, 69, 67, 65, 64, 62, 64, 65, 67, 69, 67, 65, 62])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        self.assertIn("starts on D", text)  # it opens there
        self.assertIn("rises toward A", text)  # and that is its peak

    def test_pitches_are_named_without_octave_numbers(self) -> None:
        """A card reads "starts on D"; "D4" belongs in Musical details, not in the plain description."""
        events = ev([62, 64, 65, 67, 69, 67, 65, 64, 62, 64, 65, 67, 69, 67, 65, 62])
        text = musical_summary(events, CH4, key="C", meter="4/4")
        for octave_number in ("D4", "A4", "4,", "5,"):
            self.assertNotIn(octave_number, text)

    def test_the_same_letters_an_octave_apart_still_read_differently(self) -> None:
        """Dropping the octave number must not make two registers indistinguishable: say the register."""
        low = ev([48, 50, 52, 53, 55, 53, 52, 50, 48, 50, 52, 53, 55, 53, 52, 48])
        middle = ev([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 65, 67, 65, 64, 60])
        high = ev([72, 74, 76, 77, 79, 77, 76, 74, 72, 74, 76, 77, 79, 77, 76, 72])
        texts = [musical_summary(m, CH4, key="C", meter="4/4") for m in (low, middle, high)]
        self.assertEqual(len(set(texts)), 3, texts)
        self.assertIn("a low C", texts[0])
        self.assertIn("starts on C", texts[1])
        self.assertIn("a high C", texts[2])


if __name__ == "__main__":
    unittest.main()

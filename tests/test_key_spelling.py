"""Key-signature spelling for musician-facing theory displays."""

from __future__ import annotations

import unittest

from improvisation_intelligence import build_scale_suggestion, spell_scale_notes
from improvisation_motif import chord_tone_names
from music_theory import (
    reference_spelling_mode,
    respell_note_for_key,
    spell_note_in_key,
)


class TestSpellingMode(unittest.TestCase):
    def test_flat_major_keys(self) -> None:
        for key in ("F", "Bb", "Eb", "Ab"):
            self.assertEqual(reference_spelling_mode(key), "flat")

    def test_sharp_major_keys(self) -> None:
        for key in ("G", "D", "A", "E"):
            self.assertEqual(reference_spelling_mode(key), "sharp")

    def test_flat_minor_keys(self) -> None:
        for key in ("Fm", "Bbm", "Ebm"):
            self.assertEqual(reference_spelling_mode(key), "flat")


class TestFlatKeyScaleSpellings(unittest.TestCase):
    def test_f_major_scale_uses_bb_not_a_sharp(self) -> None:
        notes = spell_scale_notes("F", "major", "F")
        self.assertIn("Bb", notes)
        self.assertNotIn("A#", notes)

    def test_bb_major_pentatonic(self) -> None:
        sug = build_scale_suggestion("Bb major pentatonic", reference_key="Bb")
        self.assertTrue(all("#" not in n for n in sug.notes))
        self.assertIn("Bb", sug.notes)

    def test_eb_major_scale(self) -> None:
        notes = spell_scale_notes("Eb", "major", "Eb")
        for pitch in ("Ab", "Bb", "Eb"):
            self.assertIn(pitch, notes)
        self.assertNotIn("G#", notes)
        self.assertNotIn("A#", notes)

    def test_ab_major_scale(self) -> None:
        notes = spell_scale_notes("Ab", "major", "Ab")
        for pitch in ("Ab", "Bb", "Db", "Eb"):
            self.assertIn(pitch, notes)

    def test_f_minor_dorian_suggestion(self) -> None:
        sug = build_scale_suggestion("F dorian", reference_key="Fm")
        self.assertNotIn("G#", sug.notes)
        self.assertIn("Ab", sug.notes)

    def test_d7_mixolydian_in_bb_major_context(self) -> None:
        sug = build_scale_suggestion("D mixolydian", reference_key="Bb")
        self.assertNotIn("A#", " ".join(sug.notes))
        self.assertIn("C", sug.notes)

    def test_f_natural_minor_label_matches_notes(self) -> None:
        sug = build_scale_suggestion("F natural minor", reference_key="F")
        self.assertIn("Natural Minor", sug.label)
        self.assertIn("Ab", sug.notes)
        self.assertIn("Db", sug.notes)
        self.assertIn("Eb", sug.notes)
        self.assertNotIn("A", sug.notes)

    def test_f_major_label_matches_notes_not_natural_minor(self) -> None:
        sug = build_scale_suggestion("F major", reference_key="F")
        self.assertIn("Major", sug.label)
        self.assertIn("A", sug.notes)
        self.assertIn("Bb", sug.notes)
        self.assertNotIn("Ab", sug.notes)

    def test_gm7_section_suggestions_use_dorian_not_mislabeled_minor(self) -> None:
        sug = build_scale_suggestion("G dorian", reference_key="F")
        self.assertIn("Dorian", sug.label)
        self.assertIn("F", sug.notes)
        self.assertIn("Bb", sug.notes)


class TestChordTonesFlatKeys(unittest.TestCase):
    def test_bb7_in_f_minor(self) -> None:
        tones = chord_tone_names("Bb7", reference_key="Fm")
        self.assertIn("Bb", tones[0])
        self.assertIn("Ab", tones[3] if len(tones) > 3 else tones[-1])

    def test_respell_enharmonic(self) -> None:
        self.assertEqual(respell_note_for_key("A#", "F"), "Bb")
        self.assertEqual(respell_note_for_key("Gb", "G"), "F#")


if __name__ == "__main__":
    unittest.main()

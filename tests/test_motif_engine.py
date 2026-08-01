"""Smoke tests for unified motif engine facade."""

from __future__ import annotations

import unittest

from motif_engine import generate_mission_phrase, generate_musical_phrase


class TestMotifEngineFacade(unittest.TestCase):
    def test_creative_phrase_has_notes(self) -> None:
        motif = generate_musical_phrase("Am7", key_center="G", level="Intermediate", kind="creative")
        self.assertTrue(motif.get("notes"))

    def test_mission_phrase_chord_tones_only(self) -> None:
        motif = generate_musical_phrase(
            "Dm7",
            key_center="F",
            level="Intermediate",
            kind="mission",
            mission="Improvise using only chord tones",
        )
        from music_theory import normalize_root, split_chord
        from improvisation_motif import chord_tone_names

        allowed = {
            normalize_root(split_chord(n)[0])
            for n in chord_tone_names("Dm7", reference_key="F")
        }
        for note in motif.get("notes") or []:
            self.assertIn(normalize_root(split_chord(note)[0]), allowed)


    def test_mission_phrase_via_dedicated_api(self) -> None:
        import random

        motif = generate_mission_phrase(
            "Improvise using only chord tones",
            "Dm7",
            key_center="F",
            level="Intermediate",
            variant="normal",
            rng=random.Random(42),
        )
        self.assertTrue(motif.get("notes"))


if __name__ == "__main__":
    unittest.main()

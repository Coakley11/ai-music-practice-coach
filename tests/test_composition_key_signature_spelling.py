"""Key signature, enharmonic spelling and bar accidentals of the composition score."""

from __future__ import annotations

import unittest

from composition_melody_notation import (
    build_abc_from_melody_events,
    build_section_score_model,
    composition_abc_key_field,
)
from composition_melody_projection import project_melody_events

_E_MAJOR_SCALE = ["E4", "F#4", "G#4", "A4", "B4", "C#5", "D#5", "E5"]


def _events(tokens: list[str]) -> list[dict]:
    return [{"pitch": t, "duration_beats": 1.0} for t in tokens]


def _music(model: dict) -> str:
    return model["abc"].splitlines()[-1]


class TestKeySignatures(unittest.TestCase):
    def test_displayed_key_gives_the_right_signature(self) -> None:
        # four sharps / three flats / four flats
        self.assertEqual(composition_abc_key_field("E"), "E")
        self.assertEqual(composition_abc_key_field("Eb"), "Eb")
        self.assertEqual(composition_abc_key_field("Fm"), "Fm")
        self.assertEqual(composition_abc_key_field("Ebm"), "Ebm")
        self.assertEqual(composition_abc_key_field("C#m"), "C#m")

    def test_the_k_line_of_the_score_matches_the_key_it_is_given(self) -> None:
        for key in ("E", "Eb", "Fm", "D", "Bb"):
            model = build_section_score_model(events=_events(["E4"]), chords=[], key=key, meter="4/4", bpm=90)
            self.assertIn(f"\nK:{key}\n", model["abc"], key)


class TestEnharmonicSpelling(unittest.TestCase):
    def _score(self, practice: str, *, instrument: str = "Piano", sig: str | None = None) -> str:
        out, _, _ = project_melody_events(
            _events(_E_MAJOR_SCALE), original_key="E", practice_key=practice, instrument=instrument, session_state={}
        )
        return _music(build_section_score_model(events=out, chords=[], key=sig or practice, meter="4/4", bpm=90))

    def test_e_major_stays_the_sharp_scale_under_four_sharps(self) -> None:
        self.assertEqual(self._score("E"), "E2 F2 G2 A2 | B2 c2 d2 e2 |")

    def test_e_flat_major_is_spelled_with_flats_not_sharps(self) -> None:
        music = self._score("Eb")
        # the same scale degrees; every accidental comes from the three flats, none written
        self.assertEqual(music, "E2 F2 G2 A2 | B2 c2 d2 e2 |")
        self.assertNotIn("^", music)
        self.assertNotIn("_", music)

    def test_no_double_sharps_from_transposition(self) -> None:
        for practice in ("Eb", "Ab", "Db", "Bb", "F", "G"):
            with self.subTest(practice=practice):
                self.assertNotIn("^^", self._score(practice))

    def test_transposing_instrument_uses_its_written_key(self) -> None:
        # concert Eb -> Bb trumpet reads F major (one flat); not merely relabeled
        music = self._score("Eb", instrument="Trumpet", sig="F")
        self.assertEqual(music, "F2 G2 A2 B2 | c2 d2 e2 f2 |")

    def test_stored_pitches_are_not_changed_by_notation(self) -> None:
        events = _events(_E_MAJOR_SCALE)
        before = [dict(e) for e in events]
        build_section_score_model(events=events, chords=[], key="Eb", meter="4/4", bpm=90)
        self.assertEqual(events, before)


class TestMinorAndModeSwitches(unittest.TestCase):
    def test_f_minor_scale_comes_entirely_from_four_flats(self) -> None:
        tokens = ["F4", "G4", "Ab4", "Bb4", "C5", "Db5", "Eb5", "F5"]
        model = build_section_score_model(events=_events(tokens), chords=[], key="Fm", meter="4/4", bpm=90)
        self.assertEqual(_music(model), "F2 G2 A2 B2 | c2 d2 e2 f2 |")
        self.assertIn("\nK:Fm\n", model["abc"])

    def test_same_tokens_in_a_different_mode_are_not_reused_by_accident(self) -> None:
        # E major score, then F minor score: each builds from its own key
        major = build_section_score_model(events=_events(["G#4"]), chords=[], key="E", meter="4/4", bpm=90)
        minor = build_section_score_model(events=_events(["Ab4"]), chords=[], key="Fm", meter="4/4", bpm=90)
        self.assertIn("K:E", major["abc"])
        self.assertIn("K:Fm", minor["abc"])
        self.assertNotIn("^", _music(major))
        self.assertNotIn("_", _music(minor))


class TestBarAccidentals(unittest.TestCase):
    def test_a_natural_after_a_sharp_in_the_same_bar_is_marked(self) -> None:
        model = build_section_score_model(events=_events(["F#4", "F4", "G4", "F#4"]), chords=[], key="C", meter="4/4", bpm=90)
        self.assertEqual(_music(model), "^F2 =F2 G2 ^F2 |")

    def test_the_key_signature_note_is_restored_after_a_natural(self) -> None:
        model = build_section_score_model(events=_events(["G#4", "G4", "G#4", "A4"]), chords=[], key="E", meter="4/4", bpm=90)
        self.assertEqual(_music(model), "G2 =G2 ^G2 A2 |")

    def test_the_next_bar_starts_clean_again(self) -> None:
        model = build_section_score_model(
            events=_events(["F#4", "F#4", "F#4", "F#4", "F4", "F4", "F4", "F4"]), chords=[], key="C", meter="4/4", bpm=90
        )
        self.assertEqual(_music(model), "^F2 F2 F2 F2 | F2 F2 F2 F2 |")

    def test_accidentals_are_per_octave(self) -> None:
        model = build_section_score_model(events=_events(["F#4", "F5"]), chords=[], key="C", meter="4/4", bpm=90)
        self.assertEqual(_music(model), "^F2 f2 |")


class TestSharedBuilderIsUnchanged(unittest.TestCase):
    def test_default_builder_keeps_its_own_spelling(self) -> None:
        abc = build_abc_from_melody_events(_events(["F#4", "F4", "G4", "F#4"]), key="C", meter="4/4", bpm=90, title="x")
        self.assertEqual(abc.splitlines()[-1], "^f2 f2 g2 ^f2 |")


if __name__ == "__main__":
    unittest.main()

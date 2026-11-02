"""Issue 2: Composition melody transposes into all 12 major and 12 minor keys and round-trips exactly."""

from __future__ import annotations

import copy
import re
import unittest

from composition_melody_notation import build_section_score_model, composition_abc_key_field
from composition_melody_projection import project_melody_events

MAJORS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
MINORS = ["Am", "Em", "Bm", "F#m", "C#m", "G#m", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm"]
E_MAJOR_SCALE = ["E4", "F#4", "G#4", "A4", "B4", "C#5", "D#5", "E5"]
E_MINOR_SCALE = ["E4", "F#4", "G4", "A4", "B4", "C5", "D5", "E5"]
# accidentals in the signature: +sharps / -flats
SIGNATURE = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6,
    "Am": 0, "Em": 1, "Bm": 2, "F#m": 3, "C#m": 4, "G#m": 5, "D#m": 6,
    "Dm": -1, "Gm": -2, "Cm": -3, "Fm": -4, "Bbm": -5, "Ebm": -6,
}
_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(token: str) -> int:
    m = re.fullmatch(r"([A-G])([#b]*)(-?\d)", token)
    assert m, token
    return 12 * (int(m.group(3)) + 1) + _NAMES[m.group(1)] + m.group(2).count("#") - m.group(2).count("b")


def events(tokens: list[str]) -> list[dict]:
    return [{"pitch": t, "duration_beats": 1.0 if i % 2 else 2.0, "beat": float(i)} for i, t in enumerate(tokens)]


def music_line(model: dict) -> str:
    return model["abc"].splitlines()[-1]


def tonic(key: str) -> str:
    return key


class TestAllKeys(unittest.TestCase):
    def _project(self, src_events, original, practice):
        out, key_shift, _ = project_melody_events(
            src_events, original_key=original, practice_key=practice, instrument="Piano", session_state={}
        )
        return out, key_shift

    def test_every_key_signature_is_the_right_one(self) -> None:
        for key in MAJORS + MINORS:
            self.assertIn(key, SIGNATURE, key)
            self.assertEqual(composition_abc_key_field(key), key, key)
        self.assertEqual(SIGNATURE["E"], 4)   # four sharps
        self.assertEqual(SIGNATURE["D"], 2)   # two sharps
        self.assertEqual(SIGNATURE["Eb"], -3)  # three flats
        self.assertEqual(SIGNATURE["Fm"], -4)  # four flats

    def test_major_keys_shift_the_melody_by_the_exact_interval_and_keep_its_shape(self) -> None:
        src = events(E_MAJOR_SCALE)
        base = [midi(e["pitch"]) for e in src]
        for key in MAJORS:
            with self.subTest(key=key):
                out, shift = self._project(src, "E", key)
                got = [midi(e["pitch"]) for e in out]
                self.assertEqual([g - b for g, b in zip(got, base)], [shift] * len(base))
                self.assertEqual([b - a for a, b in zip(got, got[1:])], [b - a for a, b in zip(base, base[1:])])
                self.assertLessEqual(abs(shift), 6)  # nearest direction, never a >tritone leap
                self.assertEqual([e["duration_beats"] for e in out], [e["duration_beats"] for e in src])

    def test_the_transposed_scale_needs_no_written_accidentals_under_its_own_signature(self) -> None:
        for key in MAJORS:
            with self.subTest(key=key):
                out, _ = self._project(events(E_MAJOR_SCALE), "E", key)
                model = build_section_score_model(events=out, chords=[], key=key, meter="4/4", bpm=90)
                self.assertNotRegex(music_line(model), r"[\^_=]", (key, music_line(model)))
        for key in MINORS:
            with self.subTest(key=key):
                out, _ = self._project(events(E_MINOR_SCALE), "Em", key)
                model = build_section_score_model(events=out, chords=[], key=key, meter="4/4", bpm=90)
                self.assertNotRegex(music_line(model), r"[\^_=]", (key, music_line(model)))

    def test_round_trip_back_to_the_source_key_is_exact_and_the_source_is_untouched(self) -> None:
        for original, scale, keys in (("E", E_MAJOR_SCALE, MAJORS), ("Em", E_MINOR_SCALE, MINORS)):
            src = events(scale)
            frozen = copy.deepcopy(src)
            for key in keys:
                with self.subTest(original=original, key=key):
                    there, _ = self._project(src, original, key)
                    back, _ = self._project(there, key, original)
                    self.assertEqual([midi(e["pitch"]) for e in back], [midi(e["pitch"]) for e in src])
                    self.assertEqual(src, frozen)  # stored source pitches were never rewritten

    def test_octave_stays_sane_for_every_target_key(self) -> None:
        src = events(E_MAJOR_SCALE)
        for key in MAJORS:
            out, _ = self._project(src, "E", key)
            self.assertTrue(all(48 <= midi(e["pitch"]) <= 84 for e in out), key)

    def test_e_to_d_lowers_by_two_semitones_and_e_to_eb_by_one(self) -> None:
        src = events(E_MAJOR_SCALE)
        d, shift_d = self._project(src, "E", "D")
        eb, shift_eb = self._project(src, "E", "Eb")
        self.assertEqual((shift_d, shift_eb), (-2, -1))
        self.assertEqual([e["pitch"] for e in d][:2], ["D4", "E4"])
        self.assertEqual([midi(e["pitch"]) for e in eb][:1], [midi("Eb4")])


if __name__ == "__main__":
    unittest.main()

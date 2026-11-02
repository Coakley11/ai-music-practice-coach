"""Integration: dev's bar-accidental rules and the Composition transposition/spelling fixes agree.

An independent ABC reader (absolute accidentals, last to the bar line, key signature otherwise) turns the
rendered notation back into pitches; those must equal the pitches the audio engine plays.
"""

from __future__ import annotations

import re
import unittest

from composition_melody_notation import build_section_score_model, composition_abc_key_field
from composition_melody_projection import project_melody_events
from music_theory import abc_key_signature_letter_alterations

MAJORS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]
MINORS = ["Am", "Em", "Bm", "F#m", "C#m", "G#m", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm"]
SIG = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "Db": -5, "Ab": -4, "Eb": -3, "Bb": -2, "F": -1,
       "Am": 0, "Em": 1, "Bm": 2, "F#m": 3, "C#m": 4, "G#m": 5, "Ebm": -6, "Bbm": -5, "Fm": -4, "Cm": -3, "Gm": -2, "Dm": -1}
BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(token: str) -> int:
    m = re.fullmatch(r"([A-G])(#{0,2}|b{0,2})(-?\d)", token)
    assert m, token
    return 12 * (int(m.group(3)) + 1) + BASE[m.group(1)] + m.group(2).count("#") - m.group(2).count("b")


def read_abc(music_line: str, key_field: str) -> list[int]:
    """Pitches of an ABC music line under the standard accidental rules."""
    sig = abc_key_signature_letter_alterations(key_field)
    out: list[int] = []
    for bar in music_line.replace('"', '\x00').split("|"):
        bar = re.sub(r"\x00[^\x00]*\x00", "", bar)
        state: dict[tuple[str, int], int] = {}
        for acc, letter, marks in re.findall(r"(\^\^|__|\^|_|=)?([A-Ga-g])([',]*)", bar):
            up = letter.isupper()
            octave = (4 if up else 5) + marks.count("'") - marks.count(",")
            slot = (letter.upper(), octave)
            alter = {"^^": 2, "__": -2, "^": 1, "_": -1, "=": 0}.get(acc, state.get(slot, sig.get(letter.upper(), 0)))
            state[slot] = alter
            out.append(12 * (octave + 1) + BASE[letter.upper()] + alter)
    return out


def ev(tokens: list[str]) -> list[dict]:
    return [{"pitch": t, "duration_beats": 1.0, "beat": float(i)} for i, t in enumerate(tokens)]


class TestKeySignatures(unittest.TestCase):
    def test_signature_counts_for_all_24_keys(self) -> None:
        for key, want in SIG.items():
            alt = abc_key_signature_letter_alterations(composition_abc_key_field(key))
            self.assertEqual(sum(alt.values()), want, key)
            self.assertEqual(len(alt), abs(want), key)

    def test_named_cases(self) -> None:
        self.assertEqual(len(abc_key_signature_letter_alterations("E")), 4)
        self.assertEqual(len(abc_key_signature_letter_alterations("D")), 2)
        ab_minor = abc_key_signature_letter_alterations(composition_abc_key_field("Abm"))
        self.assertEqual(sorted(ab_minor.values()), [-1] * 7)


class TestRenderedNotationReadsBackAsThePlayedPitch(unittest.TestCase):
    def _check(self, key: str, tokens: list[str]) -> None:
        src = ev(tokens)
        model = build_section_score_model(events=src, chords=[], key=key, meter="4/4", bpm=90)
        line = model["abc"].splitlines()[-1]
        self.assertEqual(read_abc(line, composition_abc_key_field(key)), [midi(t) for t in tokens], (key, line))

    def test_persistence_and_cancellation_across_barlines(self) -> None:
        # Em has F#: F natural in bar 1 persists to the bar line, bar 2 returns to the signature F#.
        self._check("Em", ["F#4", "F4", "F4", "G4", "F#4", "F#4", "A4", "B4"])
        # a sharp that is NOT in the signature must be cancelled by the next bar
        self._check("C", ["F#4", "F#4", "G4", "A4", "F4", "G4", "A4", "B4"])

    def test_enharmonic_spellings_e_sharp_and_c_flat(self) -> None:
        self._check("F#", ["E#4", "F#4", "G#4", "A#4", "B4", "C#5", "D#5", "E#5"])
        self._check("Gb" if "Gb" in SIG else "Db", ["Cb5", "Db5", "Eb5", "F5", "Gb5", "Ab5", "Bb5", "C6"])

    def test_every_key_every_chromatic_pitch_reads_back_exactly(self) -> None:
        names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        tokens = [f"{n}4" for n in names] + ["C5"]
        for key in MAJORS + MINORS:
            with self.subTest(key=key):
                self._check(key, tokens)

    def test_transposed_scale_reads_back_as_the_projected_pitches_in_every_key(self) -> None:
        scale = ["E4", "F#4", "G#4", "A4", "B4", "C#5", "D#5", "E5"]
        minor = ["E4", "F#4", "G4", "A4", "B4", "C5", "D5", "E5"]
        for original, src_tokens, keys in (("E", scale, MAJORS), ("Em", minor, MINORS)):
            for key in keys:
                with self.subTest(original=original, key=key):
                    out, _shift, _ = project_melody_events(ev(src_tokens), original_key=original, practice_key=key,
                                                           instrument="Piano", session_state={})
                    model = build_section_score_model(events=out, chords=[], key=key, meter="4/4", bpm=90)
                    line = model["abc"].splitlines()[-1]
                    self.assertEqual(read_abc(line, composition_abc_key_field(key)), [midi(e["pitch"]) for e in out], (key, line))

    def test_tritone_round_trip_keeps_pitch_and_octave(self) -> None:
        src = ev(["E4", "G#4", "B4", "E5"])
        for key in ("Bb", "A#" if False else "F"):
            pass
        there, s1, _ = project_melody_events(src, original_key="E", practice_key="Bb", instrument="Piano", session_state={})
        back, s2, _ = project_melody_events(there, original_key="Bb", practice_key="E", instrument="Piano", session_state={})
        self.assertEqual(abs(s1), 6)
        self.assertEqual(s1 + s2, 0)
        self.assertEqual([midi(e["pitch"]) for e in back], [midi(e["pitch"]) for e in src])


if __name__ == "__main__":
    unittest.main()

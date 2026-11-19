"""Melody-fit chord suggestions stay in the key unless the melody itself is chromatic (2026-11-19).

Chord qualities come from a per-style list, not per scale degree, so a fit tie used to keep the first
listed quality: Jazz in D major suggested Amaj7 (G#) / Am7 (C natural) for the V chord.
"""

import re
import unittest

from composition_melody_harmonize import _key_scale_pcs, _pick_chord_for_pcs, harmonize_melody_to_progressions

_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
       "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
_QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10),
         "m7b5": (0, 3, 6, 10), "6": (0, 4, 7, 9), "9": (0, 4, 7, 10, 2), "sus4": (0, 5, 7), "sus2": (0, 2, 7),
         "add9": (0, 4, 7, 2), "7sus4": (0, 5, 7, 10), "m9": (0, 3, 7, 10, 2), "maj9": (0, 4, 7, 11, 2), "m6": (0, 3, 7, 9)}


def _tones(sym: str) -> set[int]:
    m = re.match(r"^([A-G][#b]?)(.*)$", sym)
    return {(_PC[m.group(1)] + d) % 12 for d in _QUAL[m.group(2)]}


def _bars(*pitches_per_bar: tuple[str, ...]) -> list[dict]:
    out, beat = [], 0.0
    for bar in pitches_per_bar:
        for p in bar:
            out.append({"pitch": p, "beat": beat, "duration_beats": 4.0 / len(bar)})
            beat += 4.0 / len(bar)
    return out


class TestKeyScale(unittest.TestCase):
    def test_major_and_minor_scales(self) -> None:
        self.assertEqual(_key_scale_pcs("D"), {2, 4, 6, 7, 9, 11, 1})
        self.assertEqual(_key_scale_pcs("Bm"), {11, 1, 2, 4, 6, 7, 9, 10})  # natural minor + A# (raised 7th)
        self.assertEqual(_key_scale_pcs("B minor"), _key_scale_pcs("Bm"))
        self.assertEqual(_key_scale_pcs("Cmaj"), _key_scale_pcs("C"))


class TestMelodyFitStaysInKey(unittest.TestCase):
    def test_jazz_dominant_in_d_major_is_a7_not_amaj7(self) -> None:
        # A, C#, E melody over the V bar: A7 and Amaj7 fit equally; only A7 belongs to D major.
        sym, _why = _pick_chord_for_pcs([(9, 2.0), (1, 1.0), (4, 1.0)], key="D", style_family="jazz", feeling="stable")
        self.assertEqual(sym, "A7")

    def test_diatonic_melody_gets_diatonic_suggestions(self) -> None:
        events = _bars(("D4", "F#4", "A4", "F#4"), ("E4", "G4", "B4", "G4"), ("A3", "C#4", "E4", "C#4"), ("D4", "A3", "F#4", "D4"))
        scale = _key_scale_pcs("D")
        for fam in ("jazz", "pop", "bossa", "rock"):
            for feeling in ("stable", "tense", "melancholy"):
                for s in harmonize_melody_to_progressions(events, key="D", profile={"style_family": fam}, feeling=feeling, limit=3):
                    syms = [str(e["chord"]) for e in s["chords"]]
                    self.assertEqual(len(syms), 4, (fam, feeling, syms))
                    for sym in syms:
                        self.assertLessEqual(_tones(sym), scale, (fam, feeling, syms))

    def test_context_justified_chromatic_colour_is_kept(self) -> None:
        # Chromatic harmony is not banned: colour that resolves (secondary dominant, tritone sub, diminished
        # passing chord) and does not rub against the melody survives.
        from composition_melody_harmonize import _keep_colour_that_fits_melody

        melody = [[(11, 2.0), (2, 1.0)], [(9, 2.0), (4, 1.0)]]  # B, D then A, E
        self.assertEqual(_keep_colour_that_fits_melody(["Em", "A"], ["E7", "A7"], melody, key="D"), ["E7", "A7"])
        self.assertEqual(_keep_colour_that_fits_melody(["A", "D"], ["Eb7", "D"], [[(7, 2.0)], [(2, 2.0)]], key="D"), ["Eb7", "D"])
        self.assertEqual(_keep_colour_that_fits_melody(["A", "D"], ["C#dim7", "D"], [[(4, 2.0)], [(2, 2.0)]], key="D"), ["C#dim7", "D"])

    def test_unjustified_or_clashing_colour_is_undone(self) -> None:
        from composition_melody_harmonize import _keep_colour_that_fits_melody

        # "melancholy" A -> Am7 under C#: C natural rubs a half step against the melody.
        self.assertEqual(_keep_colour_that_fits_melody(["A", "D"], ["Am7", "D"], [[(9, 2.0), (1, 2.0)], [(2, 2.0)]], key="D"), ["A", "D"])
        # A secondary dominant whose G# rubs against a G in the melody is undone even though it resolves.
        self.assertEqual(_keep_colour_that_fits_melody(["Em", "A"], ["E7", "A"], [[(7, 2.0), (4, 1.0)], [(9, 2.0)]], key="D"), ["Em", "A"])
        # Unresolved chromatic colour (Fm7 going nowhere it explains) is undone.
        self.assertEqual(_keep_colour_that_fits_melody(["D", "G"], ["Fm7", "G"], [[(2, 2.0)], [(7, 2.0)]], key="D"), ["D", "G"])

    def test_chromatic_melody_note_still_allows_its_chord(self) -> None:
        # The melody sounds G#: E major (V/V) is justified even though G# is outside D major.
        sym, _why = _pick_chord_for_pcs([(4, 2.0), (8, 2.0), (11, 1.0)], key="D", style_family="pop", feeling="stable")
        self.assertEqual(sym, "E")


if __name__ == "__main__":
    unittest.main()

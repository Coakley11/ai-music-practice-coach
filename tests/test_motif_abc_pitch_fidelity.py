"""Motif sheet music sounds exactly the motif MIDI: octaves, key signatures, in-bar accidentals."""

from __future__ import annotations

import random
import re
import unittest

from improvisation_motif import (
    _abc_key_header,
    _note_name_to_abc_pitch,
    build_motif_abc,
    build_motif_pattern,
    cycle_motif_rhythm,
    generate_motif_for_chord,
    sync_motif_midi,
)
from melodic_pattern_engine import generate_pattern
from tests.abc_pitch_decoder import body_tokens, decode_abc_midis, key_signature


def _motif(notes: list[str], midis: list[int], sym: str = "♪") -> dict:
    return {"notes": list(notes), "midi": list(midis), "rhythm_symbols": [sym] * len(notes), "meter": "4/4"}


def _abc(notes: list[str], midis: list[int], key: str, sym: str = "♪") -> str:
    return build_motif_abc(_motif(notes, midis, sym), key_center=key)


class TestDecoderSemantics(unittest.TestCase):
    """The test decoder encodes abcjs behaviour observed in the browser proof."""

    def test_octaves_and_carry(self) -> None:
        self.assertEqual(decode_abc_midis("K:C\nC c C, A, C' |"), [60, 72, 48, 57, 72])
        self.assertEqual(decode_abc_midis("K:C\n^F G F f | F |"), [66, 67, 66, 77, 65])
        self.assertEqual(decode_abc_midis("K:F\nB =B B | B |"), [70, 71, 71, 70])

    def test_key_signatures(self) -> None:
        self.assertEqual(key_signature("Dm"), {"B": -1})
        self.assertEqual(key_signature("Ebm"), dict.fromkeys("BEADGC", -1))
        self.assertEqual(key_signature("F#"), dict.fromkeys("FCGDAE", 1))


class TestOctaveEncoding(unittest.TestCase):
    CASES = [
        ("F", 53, "F,"), ("G", 55, "G,"), ("A", 57, "A,"), ("B", 59, "B,"),
        ("C", 60, "C"), ("B", 71, "B"), ("C", 72, "C'"), ("E", 76, "E'"),
        ("E", 52, "E,"), ("C", 48, "C,"), ("A", 45, "A,,"),
    ]

    def test_single_notes(self) -> None:
        for name, midi, token in self.CASES:
            abc = _abc([name], [midi], "C", sym="♩")
            self.assertEqual(body_tokens(abc), [token], (name, midi))
            self.assertEqual(decode_abc_midis(abc), [midi], (name, midi))

    def test_note_name_helper_below_middle_c(self) -> None:
        self.assertEqual(_note_name_to_abc_pitch("A", octave=3), "A,")
        self.assertEqual(_note_name_to_abc_pitch("F#", octave=3), "^F,")
        self.assertEqual(_note_name_to_abc_pitch("Bb", octave=2), "_B,,")
        self.assertEqual(_note_name_to_abc_pitch("C", octave=4), "C")
        self.assertEqual(_note_name_to_abc_pitch("Bb", octave=5), "_B'")

    def test_phrase_crossing_middle_c(self) -> None:
        notes = ["F", "G", "A", "B", "C", "D", "C", "B", "A", "G"]
        midis = [53, 55, 57, 59, 60, 62, 60, 59, 57, 55]
        abc = _abc(notes, midis, "C", sym="♩")
        self.assertEqual(decode_abc_midis(abc), midis)
        self.assertIn("B, C D C B,", " ".join(body_tokens(abc)))

    def test_phrase_crossing_c5(self) -> None:
        notes = ["A", "B", "C", "D", "E", "D", "C", "B"]
        midis = [69, 71, 72, 74, 76, 74, 72, 71]
        abc = _abc(notes, midis, "C")
        self.assertEqual(decode_abc_midis(abc), midis)
        self.assertEqual(body_tokens(abc)[:3], ["A/2", "B/2", "C'/2"])

    def test_letter_octave_differs_from_sounding_octave(self) -> None:
        # B#3 sounds C4; Cb4 sounds B3 — octave marks follow the letter.
        abc = _abc(["B#", "Cb"], [60, 59], "C", sym="♩")
        self.assertEqual(body_tokens(abc), ["^B,", "_C"])
        self.assertEqual(decode_abc_midis(abc), [60, 59])

    def test_midi_is_authority_when_name_disagrees(self) -> None:
        abc = _abc(["C"], [61], "C", sym="♩")
        self.assertEqual(decode_abc_midis(abc), [61])


class TestKeySignatureAccidentals(unittest.TestCase):
    # (key, notes, midis, expected tokens without durations)
    CASES = [
        ("F", ["A", "B", "C"], [69, 71, 72], ["A", "=B", "C'"]),       # natural cancels a flat
        ("G", ["G", "F", "E"], [67, 65, 64], ["G", "=F", "E"]),        # natural cancels a sharp
        ("D", ["D", "C", "B"], [62, 60, 59], ["D", "=C", "B,"]),
        ("Bb", ["F", "E", "D"], [65, 64, 62], ["F", "=E", "D"]),
        ("Eb", ["Bb", "A", "G"], [70, 69, 67], ["B", "=A", "G"]),
        ("F", ["Bb", "A", "G"], [70, 69, 67], ["B", "A", "G"]),        # in-key flat: no accidental
        ("D", ["F#", "G", "A"], [66, 67, 69], ["F", "G", "A"]),        # in-key sharp: no accidental
        ("C", ["F#", "G"], [66, 67], ["^F", "G"]),                     # explicit sharp
        ("Bb", ["F#", "G"], [66, 67], ["^F", "G"]),
        ("C", ["Bb", "A"], [70, 69], ["_B", "A"]),                     # explicit flat
        ("G", ["Bb", "A"], [70, 69], ["_B", "A"]),
        ("Dm", ["C#", "D", "B", "A"], [61, 62, 59, 57], ["^C", "D", "=B,", "A,"]),
        ("Cm", ["B", "C", "Ab", "G"], [71, 72, 68, 67], ["=B", "C'", "A", "G"]),
        ("Bm", ["A#", "B", "C", "B"], [70, 71, 72, 71], ["^A", "B", "=C'", "B"]),
        ("F#m", ["E#", "F#", "D", "C#"], [65, 66, 62, 61], ["^E", "F", "D", "C"]),
        ("Ebm", ["D", "Eb", "B", "Bb"], [62, 63, 59, 58], ["=D", "E", "=B,", "_B,"]),  # restate flat after natural
    ]

    def test_cases(self) -> None:
        for key, notes, midis, tokens in self.CASES:
            abc = _abc(notes, midis, key, sym="♩")
            got = [re.sub(r"[\d/]+$", "", t) for t in body_tokens(abc)]
            self.assertEqual(got, tokens, (key, notes))
            self.assertEqual(decode_abc_midis(abc), midis, (key, notes))

    def test_in_bar_accidentals_are_cancelled_and_restored(self) -> None:
        # C major: F# G F in one bar → the second F needs a natural.
        abc = _abc(["F#", "G", "F", "E"], [66, 67, 65, 64], "C", sym="♩")
        self.assertEqual(body_tokens(abc), ["^F", "G", "=F", "E"])
        # F major: B natural, then Bb again in the same bar → the flat must be restated.
        abc = _abc(["B", "C", "Bb", "A"], [71, 72, 70, 69], "F", sym="♩")
        self.assertEqual(body_tokens(abc), ["=B", "C'", "_B", "A"])
        self.assertEqual(decode_abc_midis(abc), [71, 72, 70, 69])

    def test_barline_resets_accidentals(self) -> None:
        abc = _abc(["F#", "G", "A", "B", "F"], [66, 67, 69, 71, 65], "C", sym="♩")
        self.assertEqual(body_tokens(abc)[-1], "F")
        self.assertEqual(decode_abc_midis(abc), [66, 67, 69, 71, 65])

    def test_accidental_in_another_octave_is_independent(self) -> None:
        abc = _abc(["F#", "F"], [66, 77], "C", sym="♩")
        self.assertEqual(body_tokens(abc), ["^F", "F'"])

    def test_minor_headers_are_valid_abc(self) -> None:
        self.assertEqual(_abc_key_header("Dm"), "Dm")
        self.assertEqual(_abc_key_header("Cm"), "Cm")
        self.assertEqual(_abc_key_header("D minor"), "Dm")
        self.assertEqual(_abc_key_header("C#m"), "C#m")
        self.assertEqual(_abc_key_header("Ebm"), "Ebm")
        for theoretical, enharmonic in (("Dbm", "C#m"), ("Gbm", "F#m"), ("Abm", "G#m")):
            self.assertEqual(_abc_key_header(theoretical), enharmonic)


class TestGeneratedMotifsRoundTrip(unittest.TestCase):
    KEYS = [
        ("C", "G7"), ("F", "C7"), ("G", "D7"), ("D", "A7"), ("Bb", "F7"), ("Eb", "Bb7"),
        ("Db", "Ab7"), ("F#", "C#7"), ("Dm", "A7"), ("Bm", "F#7"), ("Cm", "G7"),
        ("Ebm", "Bb7"), ("Abm", "Eb7"),
    ]

    def _assert_round_trip(self, motif: dict, key: str, label: str) -> None:
        synced = sync_motif_midi(dict(motif))
        abc = build_motif_abc(synced, key_center=key)
        self.assertEqual(decode_abc_midis(abc), [int(m) for m in synced["midi"]], (label, key, abc))

    def test_existing_generator_and_patterns(self) -> None:
        for key, chord in self.KEYS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for tier in ("easier", "normal", "harder"):
                    m = generate_motif_for_chord(
                        chord, key_center=key, level=level, rng=random.Random(3), idea_variant=5,
                        difficulty_tier=tier,
                    )
                    self._assert_round_trip(m, key, f"{level}/{tier}")
            base = generate_motif_for_chord(chord, key_center=key, rng=random.Random(1))
            for ptype in ("auto", "scalar", "thirds", "fourths", "pentatonic"):
                for direction in ("ascending", "descending"):
                    pat = build_motif_pattern(base, key_center=key, pattern_type=ptype, direction=direction)
                    self._assert_round_trip(pat, key, f"{ptype}/{direction}")
                    self._assert_round_trip(cycle_motif_rhythm(pat), key, f"{ptype}/{direction}/rhythm")

    def test_c1_vocabulary(self) -> None:
        families = (
            "scale_1235", "perm_1425", "arpeggio_1357", "lower_approach_arpeggio", "upper_approach_cell",
            "double_approach_below", "chromatic_run_to_target", "enclosure_classic", "enclosure_chromatic",
            "enclosure_four_note", "enclosure_double_chromatic", "arpeggio_approach_ninth",
            "bebop_scale_run", "bebop_run_to_enclosure", "chromatic_sequence_1235",
        )
        checked = 0
        for fid in families:
            for key, chord in self.KEYS:
                for direction in ("ascending", "descending"):
                    try:
                        r = generate_pattern(fid, key=key, chord=chord, direction=direction, length=4)
                    except ValueError:
                        continue
                    m = r.to_motif_fields()
                    m["rhythm_symbols"] = ["♪"] * len(m["notes"])
                    m["meter"] = "4/4"
                    abc = build_motif_abc(m, key_center=key)
                    self.assertEqual(decode_abc_midis(abc), r.midi, (fid, key, chord, direction, abc))
                    checked += 1
        self.assertGreater(checked, 300)

    def test_c1_chromatic_notes_carry_visible_accidentals(self) -> None:
        # G7 in C: D F F# G | F G A# B … every non-diatonic approach is written with ^ or _.
        r = generate_pattern("lower_approach_arpeggio", key="C", chord="G7", length=4)
        m = r.to_motif_fields()
        m["rhythm_symbols"] = ["♩"] * len(m["notes"])
        m["meter"] = "4/4"
        tokens = body_tokens(build_motif_abc(m, key_center="C"))
        for note, tok in zip((n for c in r.cells for n in c), tokens):
            if note.chromatic:
                self.assertTrue(tok.startswith(("^", "_")), (note, tok))


if __name__ == "__main__":
    unittest.main()

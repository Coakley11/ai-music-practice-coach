"""Exact-label audit of minor-key Roman numerals (key as 'Am' and 'A minor' must agree)."""
import unittest

from roman_numeral_analysis import analyze_progression as ap, chord_to_roman as c2r

A = ["Am", "Am7", "Ammaj7", "Bdim", "Bm7b5", "C", "Cmaj7", "Dm", "Dm7", "E", "E7", "Em", "F", "G", "Bb"]
A_EXPECT = ["i", "i7", "i(maj7)", "ii°", "iiø7", "III", "IIImaj7", "iv", "iv7", "V", "V7", "v", "VI", "VII", "♭II"]


class TestMinorRoman(unittest.TestCase):
    def test_diatonic_and_borrowed_labels(self) -> None:
        for key in ("Am", "A minor"):
            self.assertEqual([c2r(x, key) for x in A], A_EXPECT, key)

    def test_key_spellings_agree(self) -> None:
        for chord in A:
            self.assertEqual(c2r(chord, "Am"), c2r(chord, "A minor"))
            self.assertEqual(c2r(chord, "Am"), c2r(chord, "Aminor"))

    def test_parallel_major_tonic_is_major_numeral_not_minor(self) -> None:
        self.assertEqual(c2r("Amaj7", "Am"), "Imaj7")  # Picardy / parallel-major tonic
        self.assertEqual(c2r("A", "Am"), "I")
        self.assertEqual(c2r("Amaj7", "A"), "Imaj7")

    def test_harmonic_minor_leading_tone(self) -> None:
        self.assertEqual(ap(["G#dim7", "Am"], "Am"), ["vii°7", "i"])
        self.assertEqual(ap(["G#dim", "Am"], "A minor"), ["vii°", "i"])
        self.assertEqual(ap(["G#m7b5", "Am"], "Am"), ["viiø7", "i"])

    def test_cadences(self) -> None:
        self.assertEqual(ap(["Bm7b5", "E7", "Am"], "Am"), ["iiø7", "V7", "i"])
        self.assertEqual(ap(["Dm", "E7", "Am"], "Am"), ["iv", "V7", "i"])
        self.assertEqual(ap(["F", "G", "Am"], "Am"), ["VI", "VII", "i"])
        self.assertEqual(ap(["Am", "G", "F", "E"], "Am"), ["i", "VII", "VI", "V"])

    def test_secondary_dominant_to_dominant_is_V7_of_V(self) -> None:
        self.assertEqual(ap(["B7", "E7", "Am"], "Am"), ["V7/V", "V7", "i"])
        self.assertEqual(ap(["B7", "Em"], "Am"), ["V7/v", "v"])
        self.assertEqual(ap(["C7", "F"], "Am"), ["V7/VI", "VI"])

    def test_raised_sixth_is_not_flat_seventh(self) -> None:
        self.assertEqual(ap(["F#m7b5", "B7", "E7", "Am"], "Am")[0], "♯viø7")

    def test_other_minor_keys(self) -> None:
        self.assertEqual(ap(["Cm", "Fm", "G7", "Cm"], "C minor"), ["i", "iv", "V7", "i"])
        self.assertEqual(ap(["Bbm", "Ebm", "F7", "Bbm"], "Bbm"), ["i", "iv", "V7", "i"])


if __name__ == "__main__":
    unittest.main()

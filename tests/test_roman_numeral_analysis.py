"""Regression tests for roman_numeral_analysis module.

Tests Roman numeral chord analysis in major and minor keys,
chromatic/borrowed chords, slash chords, extensions, and
the progression batch analyzer.
"""

from __future__ import annotations

import unittest

FLAT = "♭"
SHARP = "♯"
DIM = "°"
HALF_DIM = "ø"


class TestChordToRomanMajor(unittest.TestCase):
    """Diatonic chords in C major."""

    def test_diatonic_triads(self):
        from roman_numeral_analysis import chord_to_roman

        cases = [
            ("C", "C", "I"),
            ("Dm", "C", "ii"),
            ("Em", "C", "iii"),
            ("F", "C", "IV"),
            ("G", "C", "V"),
            ("Am", "C", "vi"),
            ("Bdim", "C", f"vii{DIM}"),
        ]
        for chord, key, expected in cases:
            with self.subTest(chord=chord, key=key):
                self.assertEqual(chord_to_roman(chord, key), expected)

    def test_dominant_seventh(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("G7", "C"), "V7")

    def test_minor_seventh(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Dm7", "C"), "ii7")
        self.assertEqual(chord_to_roman("Am7", "C"), "vi7")

    def test_major_seventh(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Cmaj7", "C"), "Imaj7")
        self.assertEqual(chord_to_roman("Fmaj7", "C"), "IVmaj7")

    def test_half_diminished(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("F#m7b5", "G"), f"vii{HALF_DIM}7")

    def test_augmented(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Caug", "C"), "I+")


class TestChordToRomanMinor(unittest.TestCase):
    """Diatonic chords in A minor (natural minor)."""

    def test_diatonic_minor_triads(self):
        from roman_numeral_analysis import chord_to_roman

        cases = [
            ("Am", "Am", "i"),
            ("Bdim", "Am", f"ii{DIM}"),
            ("C", "Am", "III"),
            ("Dm", "Am", "iv"),
            ("Em", "Am", "v"),
            ("F", "Am", "VI"),
            ("G", "Am", "VII"),
        ]
        for chord, key, expected in cases:
            with self.subTest(chord=chord, key=key):
                self.assertEqual(chord_to_roman(chord, key), expected)

    def test_harmonic_minor_dominant(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("E7", "Am"), "V7")


class TestChromaticBorrowed(unittest.TestCase):
    """Chromatic / borrowed chords should use flat labels, not sharp."""

    def test_flat_seven_in_major(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Bb", "C"), f"{FLAT}VII")

    def test_flat_three_in_major(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Eb", "C"), f"{FLAT}III")

    def test_flat_six_in_major(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Ab", "C"), f"{FLAT}VI")

    def test_flat_two_in_major(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Db", "C"), f"{FLAT}II")

    def test_sharp_root_uses_sharp_label(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("F#dim", "C"), f"{SHARP}iv{DIM}")
        self.assertEqual(chord_to_roman("C#dim7", "C"), f"{SHARP}i{DIM}7")

    def test_borrowed_minor_iv(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Fm", "C"), "iv")

    def test_flat_seven_maj7(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Bbmaj7", "C"), f"{FLAT}VIImaj7")


class TestSlashChords(unittest.TestCase):
    """Slash chord bass degrees."""

    def test_chord_tone_bass(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("C/E", "C"), "I/III")
        self.assertEqual(chord_to_roman("C/G", "C"), "I/V")
        self.assertEqual(chord_to_roman("Am/C", "C"), "vi/I")

    def test_sharp_bass(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("D/F#", "C"), f"II/{SHARP}IV")

    def test_flat_bass(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("C/Bb", "C"), f"I/{FLAT}VII")


class TestExtensions(unittest.TestCase):
    """Extension suffixes (9, 11, 13, add9, sus2, sus4)."""

    def test_ninth(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Am9", "G"), "ii9")

    def test_major_ninth(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Cmaj9", "C"), "Imaj9")

    def test_ii_V_I_jazz(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("Dm7", "C"), "ii7")
        self.assertEqual(chord_to_roman("G7", "C"), "V7")
        self.assertEqual(chord_to_roman("Cmaj7", "C"), "Imaj7")


class TestEdgeCases(unittest.TestCase):
    """N.C., empty, None, repeat tokens."""

    def test_no_chord(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("N.C.", "C"), "")
        self.assertEqual(chord_to_roman("NC", "C"), "")

    def test_empty_string(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman("", "C"), "")

    def test_none(self):
        from roman_numeral_analysis import chord_to_roman

        self.assertEqual(chord_to_roman(None, "C"), "")


class TestAnalyzeProgression(unittest.TestCase):
    """Batch analysis of chord lists."""

    def test_basic_progression(self):
        from roman_numeral_analysis import analyze_progression

        result = analyze_progression(["C", "Am", "F", "G7"], "C")
        self.assertEqual(result, ["I", "vi", "IV", "V7"])

    def test_minor_progression(self):
        from roman_numeral_analysis import analyze_progression

        result = analyze_progression(["Am", "Dm", "E7", "Am"], "Am")
        self.assertEqual(result, ["i", "iv", "V7", "i"])

    def test_empty_list(self):
        from roman_numeral_analysis import analyze_progression

        self.assertEqual(analyze_progression([], "C"), [])

    def test_mixed_with_nc(self):
        from roman_numeral_analysis import analyze_progression

        result = analyze_progression(["C", "N.C.", "G7"], "C")
        self.assertEqual(result, ["I", "", "V7"])


class TestChordWithRoman(unittest.TestCase):
    def test_returns_dict(self):
        from roman_numeral_analysis import chord_with_roman

        result = chord_with_roman("Dm7", "C")
        self.assertEqual(result["chord"], "Dm7")
        self.assertEqual(result["roman"], "ii7")


class TestCPLRendererKeyCenter(unittest.TestCase):
    """entries_chord_tiles_html and cpl_progression_bar_chart_html accept key_center."""

    def test_tiles_html_roman_labels(self):
        from custom_progression_lab import entries_chord_tiles_html

        entries = [{"chord": "C", "bars": 1}, {"chord": "G7", "bars": 1}]
        html = entries_chord_tiles_html(entries, key_center="C")
        self.assertIn("cpl-roman-label", html)
        self.assertIn(">I<", html)
        self.assertIn(">V7<", html)

    def test_tiles_html_no_key_no_roman(self):
        from custom_progression_lab import entries_chord_tiles_html

        entries = [{"chord": "C", "bars": 1}]
        html = entries_chord_tiles_html(entries, key_center="")
        self.assertNotIn("cpl-roman-label", html)

    def test_bar_chart_html_roman_labels(self):
        from custom_progression_lab import cpl_progression_bar_chart_html

        entries = [{"chord": "Am", "bars": 1}, {"chord": "F", "bars": 1}]
        html = cpl_progression_bar_chart_html(entries, key_center="C")
        self.assertIn("cpl-bar-roman", html)
        self.assertIn("vi", html)
        self.assertIn("IV", html)


if __name__ == "__main__":
    unittest.main()

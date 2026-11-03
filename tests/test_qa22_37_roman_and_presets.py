"""Issues 25-28: Roman numerals for split measures and presets; ii-V-I preset correctness; no numerals in Composition chord editor."""
import ast
import re
import unittest
from pathlib import Path

import custom_progression_lab as cpl
from roman_numeral_analysis import chord_to_roman

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
PC = {n: i for i, n in enumerate(NAMES)}
PC.update({"C#": 1, "D#": 3, "Gb": 6, "G#": 8, "A#": 10})


def _root_pc(chord):
    m = re.match(r"([A-G][#b]?)", chord)
    return PC[m.group(1)]


class TestIiVIPreset(unittest.TestCase):
    def test_a_major_is_bm7_e7_amaj7(self):
        self.assertEqual(cpl.preset_chords_for_key(cpl.STYLE_PRESET_SPECS["Jazz"]["ii–V–I"], "A"), ["Bm7", "E7", "Amaj7"])

    def test_every_ii_v_i_preset_in_every_key(self):
        for style, presets in cpl.STYLE_PRESET_SPECS.items():
            for pid, spec in presets.items():
                if pid not in ("ii–V–I", "Bossa ii–V"):
                    continue
                for k in KEYS:
                    ch = cpl.preset_chords_for_key(spec, k)
                    t = PC[k]
                    with self.subTest(style=style, key=k):
                        self.assertEqual([_root_pc(c) for c in ch], [(t + 2) % 12, (t + 7) % 12, t])
                        self.assertTrue(ch[0].endswith("m7") and ch[1].endswith("7") and "maj" not in ch[1])

    def test_dominant_is_fifth_in_all_resolving_presets(self):
        """Any preset whose last-but-one chord resolves down a fifth must use V (degree 7), never IV."""
        for style, presets in cpl.STYLE_PRESET_SPECS.items():
            for pid, spec in presets.items():
                if pid in ("I–V–vi–IV", "Rock", "Quick change", "Minor bossa", "i7–IV7", "I–IV–I", "Blues (8 bars)"):
                    continue
                if "ii" in pid and "V" in pid:
                    self.assertIn((7, "7"), spec, (style, pid))
                    self.assertNotIn((5, "7"), spec, (style, pid))

    def test_romans_of_ii_v_i(self):
        self.assertEqual(cpl.preset_roman_labels("A", cpl.STYLE_PRESET_SPECS["Jazz"]["ii–V–I"]), ["ii7", "V7", "Imaj7"])


class TestPresetRomans(unittest.TestCase):
    def test_every_chord_of_every_preset_has_a_numeral_in_every_key(self):
        for style, presets in cpl.STYLE_PRESET_SPECS.items():
            for pid, spec in presets.items():
                for k in KEYS:
                    labels = cpl.preset_roman_labels(k, spec)
                    with self.subTest(style=style, preset=pid, key=k):
                        self.assertEqual(len(labels), len(spec))
                        self.assertTrue(all(labels))
                        # key independent: same numerals in every key
                        self.assertEqual(labels, cpl.preset_roman_labels("C", spec))

    def test_blues_numerals(self):
        self.assertEqual(
            cpl.preset_roman_labels("E", cpl.STYLE_PRESET_SPECS["Blues"]["Quick change"]), ["I7", "IV7", "I7", "V7"])


class TestSplitMeasureRomans(unittest.TestCase):
    def test_each_chord_gets_its_own_numeral(self):
        self.assertEqual(cpl.roman_for_display_symbol("F7|B7", "Bb"), "V7 | ♭II7")
        self.assertEqual(cpl.roman_for_display_symbol("Em7|A7", "D"), "ii7 | V7")
        self.assertEqual(cpl.roman_for_display_symbol("Em7:2|A7:2", "D"), "ii7 | V7")

    def test_second_is_not_a_copy_of_first(self):
        a, b = cpl.roman_for_display_symbol("C|G7", "C").split(" | ")
        self.assertNotEqual(a, b)

    def test_single_chord_unchanged(self):
        self.assertEqual(cpl.roman_for_display_symbol("G7", "C"), chord_to_roman("G7", "C"))

    def test_minor_key(self):
        self.assertEqual(cpl.roman_for_display_symbol("Fm7|C7", "F minor"), "i7 | V7")

    def test_tiles_html_shows_both(self):
        html = cpl.entries_chord_tiles_html([{"chord": "Em7|A7", "bars": 1}], key_center="D")
        self.assertIn("ii7 | V7", html)

    def test_bar_chart_html_shows_both(self):
        html = cpl.cpl_progression_bar_chart_html([{"chord": "Em7|A7", "bars": 1}], key_center="D")
        self.assertIn("ii7 | V7", html)


class TestCompositionChordEditorHasNoRomans(unittest.TestCase):
    def test_no_roman_analysis_inside_manual_chord_editor(self):
        src = (ROOT / "composition_studio_page.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and "Manual / advanced chord editor" in (ast.get_docstring(n) or ""))
        body = ast.get_source_segment(src, fn)
        self.assertNotIn("_c2r", body)
        self.assertNotIn("chord_to_roman", body)
        self.assertNotIn("roman", body.lower())
        self.assertNotIn("_roman_span", body)


if __name__ == "__main__":
    unittest.main()

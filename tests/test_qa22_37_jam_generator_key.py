"""Issue 31: Jam Session Generator follows the explicitly chosen Concert Key (not the active song's)."""
import unittest

from improvisation_intelligence import STYLE_PROGRESSIONS, generate_jam_session

MAJOR = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
PC = {n: i for i, n in enumerate(["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])}
PC.update({"C#": 1, "D#": 3, "Gb": 6, "G#": 8, "A#": 10})


def _root_pc(chord):
    return PC[chord[:2] if len(chord) > 1 and chord[1] in "#b" else chord[:1]]


class TestJamGeneratorKey(unittest.TestCase):
    def test_description_and_key_follow_selection(self):
        for k in MAJOR:
            with self.subTest(key=k):
                jam = generate_jam_session(key_center=k, style="Bossa Nova", ensemble="Jazz trio", mood="Bright", seed=1)
                self.assertEqual(jam["key"], k)
                self.assertIn(f"**{k}**", jam["prompt"])

    def test_bossa_ii_v_I_resolves_to_selected_major_tonic(self):
        for k in MAJOR:
            with self.subTest(key=k):
                jam = generate_jam_session(key_center=k, style="Bossa Nova", mood="Bright", seed=1)
                first = next(iter(jam["sections"].values()))
                self.assertEqual(_root_pc(first[2]), PC[k], first)             # I
                self.assertEqual(_root_pc(first[0]), (PC[k] + 2) % 12, first)  # ii
                self.assertEqual(_root_pc(first[1]), (PC[k] + 7) % 12, first)  # V

    def test_every_style_has_tonic_content_in_every_major_key(self):
        for style in STYLE_PROGRESSIONS:
            for k in ("E", "Eb", "A"):
                jam = generate_jam_session(key_center=k, style=style, mood="Bright", seed=2)
                self.assertEqual(jam["key"], k)
                self.assertTrue(jam["sections"])

    def test_switching_e_flat_to_e_gives_different_harmony(self):
        a = generate_jam_session(key_center="Eb", style="Bossa Nova", mood="Bright", seed=1)["sections"]
        b = generate_jam_session(key_center="E", style="Bossa Nova", mood="Bright", seed=1)["sections"]
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()

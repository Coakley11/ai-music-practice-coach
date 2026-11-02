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


class TestMinorKeyJamIsTonicCentred(unittest.TestCase):
    """Issue 31 follow-up: a minor Concert Key is the session's tonal centre, not a relative-major ii-V-I."""

    def _first(self, **kw):
        from improvisation_intelligence import generate_style_progression

        return list(generate_style_progression(seed=1, mood="Mellow", **kw).values())[0]

    def test_e_minor_jazz_is_em_am_b7_em(self):
        self.assertEqual(self._first(style="Jazz Swing", key_center="Em")[:4], ["Em7", "Am7", "B7", "Em7"])

    def test_every_style_starts_and_resolves_on_the_minor_tonic(self):
        from improvisation_intelligence import MINOR_STYLE_PROGRESSIONS, STYLE_PROGRESSIONS

        self.assertEqual(set(MINOR_STYLE_PROGRESSIONS), set(STYLE_PROGRESSIONS))
        for style in STYLE_PROGRESSIONS:
            for key, tonic in (("Em", "E"), ("Cm", "C"), ("F#m", "F#"), ("Bbm", "Bb")):
                with self.subTest(style=style, key=key):
                    first = self._first(style=style, key_center=key)[0]
                    self.assertTrue(first.startswith(tonic), (style, key, first))

    def test_relative_major_remains_an_explicit_option_and_major_keys_are_unchanged(self):
        from improvisation_intelligence import generate_style_progression

        rel = list(generate_style_progression(style="Jazz Swing", key_center="Em", seed=1, mood="Mellow", tonality="relative_major").values())[0]
        self.assertEqual(rel[:3], ["Am7", "D7", "Gmaj7"])
        major = list(generate_style_progression(style="Jazz Swing", key_center="C", seed=1, mood="Mellow").values())[0]
        self.assertEqual(major[:4], ["Dm7", "G7", "Cmaj7", "A7"])

    def test_chosen_key_is_not_overwritten(self):
        from improvisation_intelligence import generate_jam_session

        jam = generate_jam_session(style="Jazz Swing", key_center="Em", seed=1)
        self.assertEqual(jam["key"], "Em")

"""Issue 3: choosing a different Backing feel changes the generated accompaniment."""

from __future__ import annotations

import hashlib
import unittest

from backing_audio import generate_backing_track

FEELS = ["Pop groove", "Rock groove", "Jazz swing", "Bossa nova", "Funk groove", "Blues groove"]
CHORDS = ["Fm7", "Fm7", "Bb7", "Fm7"]


def _audio(feel: str) -> bytes:
    out = generate_backing_track(CHORDS, bpm=120, loops=1, style=feel)
    data = out[0] if isinstance(out, tuple) else out
    return bytes(data.getbuffer()) if hasattr(data, "getbuffer") else bytes(data)


class TestFeelChangesTheAccompaniment(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.digests = {f: hashlib.sha256(_audio(f)).hexdigest() for f in FEELS}

    def test_every_supported_feel_renders_different_audio(self) -> None:
        self.assertEqual(len(set(self.digests.values())), len(FEELS), self.digests)

    def test_switching_back_reproduces_the_original_feel_exactly(self) -> None:
        self.assertEqual(hashlib.sha256(_audio("Blues groove")).hexdigest(), self.digests["Blues groove"])

    def test_the_rhythm_patterns_differ_per_feel(self) -> None:
        import json

        from backing_style_recipes import style_pattern_for_recipe, style_recipe_id

        pats = {f: json.dumps(style_pattern_for_recipe(style_recipe_id(f), pulses=4), sort_keys=True, default=str) for f in FEELS}
        self.assertEqual(len(set(pats.values())), len(FEELS))


if __name__ == "__main__":
    unittest.main()

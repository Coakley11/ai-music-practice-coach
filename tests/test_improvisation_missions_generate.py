"""Regression: generate_mission_example must populate abc/tab outputs."""

from __future__ import annotations

import unittest

from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example


class TestGenerateMissionExample(unittest.TestCase):
    def test_generate_mission_example_sets_abc_tab_and_flags(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Test Song",
            artist="Artist",
            key_center="D",
            display_key="D",
            instrument="Guitar",
            level="Intermediate",
            focus="Changes",
            sections={"Verse": ["D", "G"]},
        )
        example = generate_mission_example(
            "Target only guide tones (3rds & 7ths)",
            improv_ctx=ctx,
            chord="D",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Changes",
        )
        self.assertTrue(example.abc)
        self.assertTrue(example.show_tab)
        self.assertFalse(example.show_piano)
        self.assertIsInstance(example.motif, dict)


if __name__ == "__main__":
    unittest.main()

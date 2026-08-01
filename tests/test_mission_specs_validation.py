"""Parameterized mission validator coverage."""

from __future__ import annotations

import random
import unittest

from improvisation_intelligence import PRACTICE_MISSIONS
from improvisation_mission_specs import validate_mission_motif
from motif_engine import generate_mission_phrase_validated


class MissionSpecValidationTests(unittest.TestCase):
    def test_every_mission_variant_passes_validator(self) -> None:
        chord = "Am7"
        key_center = "C"
        level = "Intermediate"
        variants = ("normal", "easier", "harder", "new")
        for mission in PRACTICE_MISSIONS:
            for variant in variants:
                rng = random.Random(f"{mission}|{variant}|{chord}")
                motif = generate_mission_phrase_validated(
                    mission,
                    chord,
                    key_center=key_center,
                    level=level,
                    variant=variant,
                    rng=rng,
                    idea_variant=rng.randint(0, 11),
                )
                ok, reason = validate_mission_motif(
                    mission,
                    motif,
                    chord=chord,
                    key_center=key_center,
                )
                self.assertTrue(ok, f"{mission!r} {variant}: {reason}")


if __name__ == "__main__":
    unittest.main()

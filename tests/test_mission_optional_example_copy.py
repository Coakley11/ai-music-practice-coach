"""Optional example wording for missions."""

from __future__ import annotations

import unittest

from improvisation_missions import _practice_steps, mission_brief_for_practice


class TestMissionOptionalExampleCopy(unittest.TestCase):
    def test_mission_brief_does_not_require_copying_notes(self) -> None:
        brief = mission_brief_for_practice("Develop a Motif")
        self.assertIn("freely", brief.lower())

    def test_practice_steps_label_example_optional(self) -> None:
        steps = _practice_steps("Develop a Motif", "Intermediate", "Guitar")
        joined = " ".join(steps).lower()
        self.assertIn("optional", joined)
        self.assertNotIn("reproduce", joined)


if __name__ == "__main__":
    unittest.main()

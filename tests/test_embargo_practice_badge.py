"""Harness: SBI concert-key line is a valid Practice Key badge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _walk_core_workflows_embargo import practice_badge  # noqa: E402


class TestEmbargoPracticeBadge(unittest.TestCase):
    def test_sbi_concert_key_c_token_is_c_major(self) -> None:
        body = (
            "Practice concert key: C\n"
            "Concert Practice Key Progression: Dm · Dm · C · C"
        )
        self.assertEqual(practice_badge(body).lower(), "c major")

    def test_sbi_concert_key_cm_token_is_c_minor(self) -> None:
        body = "Practice concert key: Cm\nConcert Practice Key Progression: Cm"
        self.assertEqual(practice_badge(body).lower(), "c minor")


if __name__ == "__main__":
    unittest.main()

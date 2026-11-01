"""Heal The World (A major extension) — E/G# is a passing chord inside the A bar."""

from __future__ import annotations

import unittest

from song_catalog.pop_extensions_2026 import pop_extension_chart_overrides


class TestHealTheWorldBars(unittest.TestCase):
    def test_chorus_merges_e_over_g_sharp_into_a_bar(self) -> None:
        pack = pop_extension_chart_overrides()[("Heal The World", "Michael Jackson")]
        chorus = pack["sections"]["Chorus 1"]
        self.assertIn("A:3|E/G#:1", chorus)
        idx = chorus.index("A:3|E/G#:1")
        self.assertEqual(chorus[idx + 1], "F#m7")
        self.assertNotIn("E/G#", chorus)


if __name__ == "__main__":
    unittest.main()

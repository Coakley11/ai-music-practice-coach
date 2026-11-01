"""Issue 1: Roman numerals under chord buttons never sit under the next row (phone widths)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "app_ui.py").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", SRC)
    assert m, selector
    return m.group(1)


class TestRomanNumeralLayout(unittest.TestCase):
    def test_numeral_is_legible_without_zoom(self) -> None:
        css = _rule(".cpl-pick-roman")
        size = float(re.search(r"font-size:\s*([\d.]+)rem", css).group(1))
        self.assertGreaterEqual(size, 0.8)  # >= 12.8px at the default root size, scales with settings
        self.assertIn("min-height", css)
        self.assertNotIn("margin-top: -", css)  # the negative margin pulled it under the next row

    def test_each_cell_reserves_the_numerals_height(self) -> None:
        css = _rule('div[class*="st-key-cpl_chord_pick_grid"] [data-testid="stColumn"]')
        self.assertIn("padding-bottom", css)
        pad = float(re.search(r"padding-bottom:\s*([\d.]+)rem", css).group(1))
        numeral_height = 1.1  # min-height of .cpl-pick-roman, rem
        self.assertGreaterEqual(pad, numeral_height)

    def test_numeral_and_button_are_still_rendered_together(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "cpl_page_ui.py").read_text(encoding="utf-8")
        i = text.index("cpl_chord_pick_grid")
        window = text[i : i + 1200]
        self.assertIn("cpl_pick_", window)
        self.assertIn("cpl-pick-roman", window)


if __name__ == "__main__":
    unittest.main()

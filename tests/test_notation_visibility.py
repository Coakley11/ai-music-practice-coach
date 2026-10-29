"""Regression tests for notation visibility fixes (P6).

Ensures render_abc_html produces scrollable notation with adequate padding,
and composition_studio_page mounts staves with scrolling enabled.
"""

from __future__ import annotations

import unittest


class TestRenderAbcHtmlOverflow(unittest.TestCase):
    """render_abc_html must allow vertical scrolling."""

    def _html(self) -> str:
        from composition_melody_notation import render_abc_html
        return render_abc_html("X:1\nK:C\nCDEF|")

    def test_no_overflow_hidden(self):
        html = self._html()
        self.assertNotIn("overflow-y: hidden", html)

    def test_overflow_y_auto(self):
        html = self._html()
        self.assertIn("overflow-y: auto", html)

    def test_padding_top_present(self):
        html = self._html()
        self.assertIn("paddingtop:", html)

    def test_padding_bottom_increased(self):
        html = self._html()
        self.assertIn("paddingbottom: 14", html)

    def test_wrap_option_present(self):
        html = self._html()
        self.assertIn("wrap:", html)
        self.assertIn("preferredMeasuresPerLine", html)


class TestStaffHeightAndScrolling(unittest.TestCase):
    """composition_studio_page mounts notation with scrolling=True."""

    def test_render_melody_staff_uses_scrolling_true(self):
        from pathlib import Path
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        fn_start = src.index("def _render_melody_staff(")
        fn_end = src.index("\ndef ", fn_start + 1)
        fn_body = src[fn_start:fn_end]
        self.assertIn("scrolling=True", fn_body)
        self.assertNotIn("scrolling=False", fn_body)

    def test_minimum_staff_height_at_least_220(self):
        from pathlib import Path
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        import re
        m = re.search(r"staff_h\s*=\s*(\d+)\s+if\s+n_ev\s*<=\s*12", src)
        self.assertIsNotNone(m, "staff_h assignment not found")
        min_h = int(m.group(1))
        self.assertGreaterEqual(min_h, 220)


if __name__ == "__main__":
    unittest.main()

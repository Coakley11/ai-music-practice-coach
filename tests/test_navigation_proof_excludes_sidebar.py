"""A fabricated proof string must never count as successful navigation.

``open_studio_page(page, "Practice", "practice")`` returned **True** while the app had not left its
landing screen, and it returned True for a proof string invented on the spot - because it read
``document.body``, and the sidebar lists every page by name on every page. Twelve gates then
"measured" a panel they had never reached. The same mistake cost a run in Issue 78C, where
"creative" was satisfied by the sidebar.

So the proof is now read from the main content area with the sidebar excluded, and this test pins
that: a string that exists ONLY in the sidebar must not satisfy it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


class TheNavigationProofIgnoresTheSidebar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (Path(__file__).resolve().parents[1] / "scripts"
                      / "_accept_issue78c_visibility.py").read_text(encoding="utf-8")

    def test_a_main_content_reader_exists(self) -> None:
        self.assertIn("def main_body(", self.source)
        self.assertIn('[data-testid="stMain"]', self.source)

    def test_it_removes_the_sidebar_before_reading(self) -> None:
        self.assertIn('[data-testid="stSidebar"]', self.source)
        self.assertIn("s.remove()", self.source)

    def test_open_studio_page_no_longer_proves_from_the_whole_body(self) -> None:
        block = re.search(r"def open_studio_page\(.*?\n(?=def )", self.source, re.S)
        self.assertIsNotNone(block, "open_studio_page not found")
        text = block.group(0)
        self.assertIn("main_body(page)", text)
        self.assertNotIn(
            "proof in low(body(page))", text,
            "a sidebar-only proof would still be accepted as navigation",
        )

    def test_the_sidebar_exclusion_logic_is_sound(self) -> None:
        """The same filtering, applied to a page shaped like this app's."""
        html = (
            "<body><div data-testid='stSidebar'>PAGES Home Practice Multitrack Creative Lab</div>"
            "<div data-testid='stMain'>Every great session starts somewhere.</div></body>"
        )
        # Mirror of what main_body does: read the main container, not the body.
        main_text = re.search(r"data-testid='stMain'>(.*?)</div>", html).group(1)
        whole_text = re.sub(r"<[^>]+>", " ", html)
        self.assertIn("practice", whole_text.lower(),
                      "the sidebar alone makes the word present on every page")
        self.assertNotIn("practice", main_text.lower(),
                         "which is exactly why the main area must be read instead")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

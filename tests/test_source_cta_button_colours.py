"""Source CTAs wear their own page colour, taken from the canonical page-accent map.

Custom actions are the Custom page's green, Composition actions the Composition page's black. The CSS
carries literal hex values (the theme block is a static stylesheet), so these tests keep those literals
tied to ``STUDIO_PAGE_ACCENTS`` - the one place the accents are defined.
"""
import re
import unittest
from pathlib import Path

from app_ui import STUDIO_PAGE_ACCENTS

APP_UI = Path(__file__).resolve().parents[1] / "app_ui.py"
APP = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"


def _rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", css)
    return m.group(1) if m else ""


class TestAccentsAreTheSingleSource(unittest.TestCase):
    def setUp(self):
        self.css = APP_UI.read_text(encoding="utf-8")

    def test_custom_green_and_composition_black_are_the_page_accents(self):
        self.assertEqual(STUDIO_PAGE_ACCENTS["custom"], "#059669")
        self.assertEqual(STUDIO_PAGE_ACCENTS["composer"], "#0f172a")

    def test_edit_custom_chart_button_is_custom_green(self):
        body = _rule(self.css, ".st-key-picker_card_edit_chart_custom button")
        self.assertIn(STUDIO_PAGE_ACCENTS["custom"], body)
        self.assertIn("background", body)

    def test_edit_composition_button_is_black_not_red(self):
        body = _rule(self.css, ".st-key-picker_card_edit_chart_composition button")
        self.assertIn(STUDIO_PAGE_ACCENTS["composer"], body)
        self.assertNotIn("#dc2626", body)                       # the old red primary

    def test_use_custom_progression_backing_is_custom_green(self):
        body = _rule(self.css, ".st-key-backing_use_custom_btn button")
        self.assertIn(STUDIO_PAGE_ACCENTS["custom"], body)


class TestTheButtonsCarryThoseKeys(unittest.TestCase):
    def test_edit_cta_is_wrapped_in_a_source_keyed_container(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn('st.container(key=f"picker_card_edit_chart_{_edit_mode}")', src)
        self.assertIn('key="picker_card_edit_chart"', src)       # the widget key itself is unchanged

    def test_use_custom_backing_button_key_is_unchanged(self):
        src = (Path(__file__).resolve().parents[1] / "backing_context_ui.py").read_text(encoding="utf-8")
        self.assertIn('key="backing_use_custom_btn"', src)


if __name__ == "__main__":
    unittest.main()

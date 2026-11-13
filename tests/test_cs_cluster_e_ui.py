"""Cluster E: Backing custom CTA accent (P11), split button icons (P12), narrow-viewport notation (P7)."""
import re
import unittest
from pathlib import Path

from app_ui import STUDIO_PAGE_ACCENTS
from composition_melody_notation import render_abc_html, split_abc_title
from music_feature_icons import action_label

ROOT = Path(__file__).resolve().parents[1]
APP_UI = (ROOT / "app_ui.py").read_text(encoding="utf-8")
PAGE = (ROOT / "composition_studio_page.py").read_text(encoding="utf-8")


def _rule(css, selector):
    """Every declaration block whose selector list ends with ``selector`` (a selector may be declared twice)."""
    return "\n".join(m.group(1) for m in re.finditer(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


class ChooseCustomAccent(unittest.TestCase):
    def test_choose_custom_is_custom_green(self):
        body = _rule(APP_UI, ".st-key-backing_choose_custom_btn button")
        self.assertIn(STUDIO_PAGE_ACCENTS["custom"], body)
        self.assertIn("background", body)

    def test_not_purple_and_key_unchanged(self):
        body = _rule(APP_UI, ".st-key-backing_choose_custom_btn button")
        self.assertNotIn("#7c3aed", body.lower())
        src = (ROOT / "backing_context_ui.py").read_text(encoding="utf-8")
        self.assertIn('key="backing_choose_custom_btn"', src)
        self.assertIn("switch_backing_source_to_custom", src)


class SplitButtonIcons(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(action_label("accept", "Apply split to draft"), "✔️ Apply split to draft")
        self.assertEqual(action_label("cancel", "Cancel split"), "❌ Cancel split")

    def test_buttons_use_icon_helper(self):
        self.assertIn('action_label("accept", "Apply split to draft")', PAGE)
        self.assertIn('action_label("cancel", "Cancel split")', PAGE)
        self.assertIn('key=f"composer_split_apply_{sid}"', PAGE)  # widget keys unchanged
        self.assertIn('key=f"composer_split_cancel_{sid}"', PAGE)


class NarrowViewportNotation(unittest.TestCase):
    ABC = "X:1\nT:Rhythmic take - Off-beat accent\nM:4/4\nK:C\nCDEF|"

    def test_title_moved_to_wrapping_html(self):
        title, body = split_abc_title(self.ABC)
        self.assertEqual(title, "Rhythmic take - Off-beat accent")
        self.assertNotIn("T:", body)
        h = render_abc_html(self.ABC)
        self.assertIn('<div id="score-title">Rhythmic take - Off-beat accent</div>', h)
        self.assertIn("overflow-wrap: anywhere", h)
        self.assertNotIn("T:Rhythmic", h)

    def test_removing_title_leaves_no_blank_line(self):
        # A blank line ends the ABC tune header in abcjs: the staff rendered with zero notes.
        _title, body = split_abc_title("X:1\nT:Take\nM:4/4\nK:C\nCDEF|")
        self.assertEqual(body, "X:1\nM:4/4\nK:C\nCDEF|")
        h = render_abc_html("X:1\nT:Take\nM:4/4\nK:C\nCDEF|")
        self.assertNotIn("\n\n", h.split("renderAbc")[1].split("`")[1])

    def test_title_is_escaped(self):
        h = render_abc_html("X:1\nT:Q & A <b>\nK:C\nC|")
        self.assertIn("Q &amp; A &lt;b&gt;", h)

    def test_staff_fits_375_390_and_scrolls_inside(self):
        h = render_abc_html(self.ABC)
        for vw in (375, 390, 1280):
            w = max(280, min(520, vw - 2 * 10 - 12))
            self.assertLessEqual(w + 2 * 10 + 12, max(vw, 312))
        self.assertIn("Math.max(280, Math.min(520", h)
        self.assertIn("paddingleft: pad", h)
        self.assertRegex(h, r"#paper \{[^}]*overflow-x: auto")
        self.assertIn("max-width: 100%", h)
        self.assertIn("width=device-width", h)
        self.assertNotRegex(h, r"staffwidth:\s*\d{3,},")

    def test_css_cards_wrap_titles(self):
        card = _rule(PAGE, ".composer-suggestion-card h4")
        for token in ("overflow-wrap: anywhere", "min-width: 0", "white-space: normal"):
            self.assertIn(token, card)
        self.assertIn("overflow-x: auto", _rule(PAGE, ".composer-score-wrap"))
        self.assertIn("max-width: 100%", _rule(PAGE, ".composer-suggestion-card"))
        self.assertIn("@media (max-width: 480px)", PAGE)


if __name__ == "__main__":
    unittest.main()

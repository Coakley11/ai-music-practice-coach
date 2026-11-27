"""Icons and compact preview layout for the Composition recording controls.

Two kinds of check, deliberately separated:

* the label helpers, which are ordinary functions and can be asserted directly;
* the page's own use of them, asserted against the source, because a heading or a stylesheet
  rule is a contract a unit test cannot otherwise reach. Those are regression guards for work
  whose real verification is the browser round - they say "this is still wired", not "this
  looks right".
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from composition_melody_improve import (
    ORIGINAL_TAKE_ICON,
    QUICK_ACTION_ICONS,
    QUICK_ACTIONS,
    original_take_label,
    quick_action_label,
)
from music_feature_icons import ACTION_ICONS, AMI_ACTION_ICONS, FEATURE_ICONS, action_label

PAGE = (ROOT / "composition_studio_page.py").read_text(encoding="utf-8")


class TestEveryTakeAdjustmentHasAnIcon(unittest.TestCase):
    def test_all_six_are_covered(self) -> None:
        for qid, _label in QUICK_ACTIONS:
            with self.subTest(action=qid):
                self.assertTrue(QUICK_ACTION_ICONS.get(qid), f"{qid} has no icon")

    def test_the_glyphs_are_ones_the_app_already_uses(self) -> None:
        """A new glyph here would mean the same action looked different elsewhere."""
        known = set(ACTION_ICONS.values()) | set(AMI_ACTION_ICONS.values()) | set(
            FEATURE_ICONS.values()
        )
        for qid, icon in QUICK_ACTION_ICONS.items():
            with self.subTest(action=qid):
                self.assertIn(icon, known, f"{qid} introduces a glyph the app does not use")

    def test_the_label_keeps_the_words_and_adds_the_icon(self) -> None:
        got = quick_action_label("shorten_first", "Shorten the first note")
        self.assertTrue(got.endswith("Shorten the first note"))
        self.assertNotEqual(got, "Shorten the first note")

    def test_an_unknown_action_is_left_alone(self) -> None:
        self.assertEqual(quick_action_label("nope", "Plain text"), "Plain text")

    def test_the_kinds_of_change_are_distinguishable(self) -> None:
        """Six identical glyphs would be no better than none."""
        self.assertGreaterEqual(len(set(QUICK_ACTION_ICONS.values())), 4)


class TestRestoreAndUndoDoNotLookAlike(unittest.TestCase):
    """They sit next to each other and do different things."""

    def test_restore_uses_the_apps_original_glyph(self) -> None:
        self.assertEqual(ORIGINAL_TAKE_ICON, FEATURE_ICONS["practice_melody_original"])

    def test_restore_is_not_the_undo_arrow(self) -> None:
        self.assertNotEqual(ORIGINAL_TAKE_ICON, ACTION_ICONS["reset"])

    def test_the_label_carries_it(self) -> None:
        self.assertTrue(original_take_label("Restore original take").startswith(ORIGINAL_TAKE_ICON))


class TestTheRecordingControlsAreIconned(unittest.TestCase):
    def test_analyze_reuses_the_ai_evaluation_glyph(self) -> None:
        self.assertEqual(action_label("analyze", "x"), f"{ACTION_ICONS['analyze']} x")

    def test_analyze_recording_is_wired_through_the_helper(self) -> None:
        self.assertIn('action_label("analyze", "Analyze recording")', PAGE)

    def test_apply_adjustment_undo_and_restore_are_wired(self) -> None:
        for snippet in (
            'action_label("apply_text", "Apply adjustment")',
            'action_label("reset", "Undo previous adjustment")',
            'original_take_label("Restore original take")',
            'original_take_label("Restore original transcription")',
            "quick_action_label(qid, qlabel)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, PAGE)


class TestTheMelodyGlyphIsOneGlyph(unittest.TestCase):
    def test_the_helper_reads_the_shared_registry(self) -> None:
        sys.path.insert(0, str(ROOT))
        from composition_studio_page import _melody_icon

        self.assertEqual(_melody_icon(), FEATURE_ICONS["phase_melody"])

    def test_no_melody_heading_hardcodes_a_note_glyph(self) -> None:
        """A literal note in a heading is how the glyphs drifted apart before."""
        for heading in re.findall(r'st\.markdown\(f?"\*\*[^"]*[Mm]elody[^"]*\*\*"\)', PAGE):
            with self.subTest(heading=heading):
                self.assertNotIn("\U0001f3b5", heading)  # single note
                self.assertNotIn("\U0001f3b6", heading)  # the glyph belongs in the helper

    def test_the_melody_headings_use_the_helper(self) -> None:
        for name in (
            "Hum or sing your melody",
            "Melody Feel & Notes",
            "AI Melody Suggestions",
            "Melody repeats",
            "Shape / refine active melody",
        ):
            with self.subTest(heading=name):
                self.assertIn(f'f"**{{_melody_icon()}} {name}**"', PAGE)


class TestThePreviewControlsAreCompact(unittest.TestCase):
    """Play and Stop are at the bottom of the player's frame; Close belongs with them."""

    def _styles(self) -> str:
        start = PAGE.index("def inject_composition_studio_styles")
        return PAGE[start : start + 6000]

    def test_close_preview_is_pulled_up_to_the_transport(self) -> None:
        css = self._styles()
        self.assertIn('div[class*="st-key-composer_preview_close_"]', css)
        self.assertRegex(css, r"margin-top:\s*-\d+px")

    def test_close_preview_is_not_a_full_width_button(self) -> None:
        self.assertRegex(self._styles(), r"width:\s*auto\s*!important")

    def test_the_player_frame_does_not_add_a_trailing_gap(self) -> None:
        self.assertIn('div[data-testid="stCustomComponentV1"]', self._styles())

    def test_the_frame_height_is_left_to_the_measured_code(self) -> None:
        """Clipped notation is worse than a gap, so the CSS must not set the frame's height."""
        css = self._styles()
        close_rule = css[css.index("st-key-composer_preview_close_") :][:600]
        # A bare `height:` would fix the frame; `min-height` and `line-height` are the button's
        # own metrics and are fine.
        bare = re.findall(r"(?<![a-z-])height\s*:", close_rule)
        self.assertEqual(bare, [], f"the compact rule sets a height: {close_rule[:200]!r}")


if __name__ == "__main__":
    unittest.main()

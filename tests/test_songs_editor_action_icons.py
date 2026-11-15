"""The same action looks the same in both Songs editors, and different actions stay different.

Before this, every button at the foot of Edit Song Chart and Edit Lyrics & Cues wore
``feature_label("charts_lyrics", ...)`` - the 📝 that is *also* ``ACTION_ICONS["apply_text"]``. So
"Save corrected chart", "Save as user verified" and "Revert to catalog" were indistinguishable from
each other and from applying pasted text, while the structural buttons (Add section, Delete section,
Duplicate, the bar steppers, the JSON backup pair) carried no icon at all.

Two things are asserted here and they pull in opposite directions on purpose:

* the same verb is the same glyph wherever it appears, and
* **verbs that mean different things never share a glyph** - Save is not Verify, Revert is not Reset,
  and removing the last bar of a section is not deleting the section.

Labels for per-section buttons are built from the *action*, never from a section name, so Intro,
Verse, Chorus, Solo, Outro and anything else the musician types all get the same icon. That is
checked by calling the label builder with section names that appear nowhere in the source.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from music_feature_icons import ACTION_ICONS, action_label, semantic_action_icon

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "song_chart_editor.py"
LYRICS = ROOT / "lyrics_cues_panel.py"


class TheNewVerbsExistAndAreDistinct(unittest.TestCase):
    def test_each_new_verb_has_an_icon(self) -> None:
        for verb in ("verify", "revert", "duplicate", "remove", "import"):
            with self.subTest(verb=verb):
                self.assertTrue(semantic_action_icon(verb), verb)

    def test_verify_matches_what_the_app_already_shows_for_user_verified(self) -> None:
        """st.toast("User verified version saved.", icon="✅") was there first."""
        self.assertEqual(semantic_action_icon("verify"), "✅")
        panel = LYRICS.read_text(encoding="utf-8")
        self.assertIn('icon="✅"', panel)

    def test_duplicate_reuses_the_copy_glyph_the_app_already_uses(self) -> None:
        from music_feature_icons import FEATURE_ICONS

        self.assertEqual(semantic_action_icon("duplicate"), FEATURE_ICONS["action_copy"])

    def test_saving_verifying_and_reverting_never_share_a_glyph(self) -> None:
        glyphs = [semantic_action_icon(v) for v in ("save", "verify", "revert", "reset")]
        self.assertEqual(len(set(glyphs)), 4, glyphs)

    def test_removing_a_bar_is_not_deleting_a_section(self) -> None:
        self.assertNotEqual(semantic_action_icon("remove"), semantic_action_icon("delete"))

    def test_verify_is_not_the_accept_check(self) -> None:
        """Accepting a suggestion and marking your own version verified are different acts."""
        self.assertNotEqual(semantic_action_icon("verify"), semantic_action_icon("accept"))

    def test_upload_and_import_are_the_two_steps_of_one_flow(self) -> None:
        self.assertNotEqual(semantic_action_icon("upload"), semantic_action_icon("import"))


class TheChartEditorUsesTheSharedMap(unittest.TestCase):
    CASES = (
        ("apply_text", "Apply section order"),
        ("add", "Add section"),
        ("delete", "Delete section"),
        ("apply_text", "Apply pasted chords to "),
        ("add", "bar @ end ("),
        ("remove", "last bar ("),
        ("duplicate", "Duplicate ("),
        ("save", "Save corrected chart"),
        ("verify", "Save as user verified"),
        ("revert", "Revert to catalog"),
        ("reset", "Reset draft"),
        ("download", "Download all overrides (JSON)"),
        ("upload", "Import overrides JSON"),
        ("import", "Merge imported overrides"),
    )

    def setUp(self) -> None:
        self.src = CHART.read_text(encoding="utf-8")

    def test_each_button_goes_through_action_label(self) -> None:
        for verb, label in self.CASES:
            with self.subTest(verb=verb, label=label):
                pattern = re.compile(
                    r'action_label\(\s*"' + verb + r'"\s*,\s*f?"[^"]*' + re.escape(label)
                )
                self.assertRegex(self.src, pattern)

    def test_no_editor_action_still_wears_the_charts_lyrics_badge(self) -> None:
        """The panel HEADING keeps it - it names the feature. The buttons must not."""
        for label in ("Save corrected chart", "Save as user verified", "Revert to catalog"):
            with self.subTest(label=label):
                self.assertNotIn('feature_label("charts_lyrics", "%s")' % label, self.src)

    def test_the_label_is_not_doubled_up(self) -> None:
        """A button that already printed its own "+" or "-" must not end up with both."""
        self.assertNotIn('"+ bar @ end', self.src)
        self.assertNotIn("− last bar", self.src)


class TheLyricsEditorUsesTheSameMap(unittest.TestCase):
    CASES = (
        ("apply_text", "Auto-assign to sections"),
        ("add", "Add"),
        ("reset", "Reset sections to match chart"),
        ("save", "Save Lyrics & Cues"),
        ("verify", "Save as user verified"),
        ("revert", "Revert my lyrics"),
    )

    def setUp(self) -> None:
        self.src = LYRICS.read_text(encoding="utf-8")

    def test_each_button_goes_through_action_label(self) -> None:
        for verb, label in self.CASES:
            with self.subTest(verb=verb, label=label):
                pattern = re.compile(
                    r'action_label\(\s*"' + verb + r'"\s*,\s*f?"[^"]*' + re.escape(label)
                )
                self.assertRegex(self.src, pattern)

    def test_both_editors_mark_user_verified_the_same_way(self) -> None:
        chart = CHART.read_text(encoding="utf-8")
        for src in (chart, self.src):
            self.assertRegex(src, r'action_label\(\s*"verify"\s*,\s*"Save as user verified"')

    def test_both_editors_revert_the_same_way(self) -> None:
        chart = CHART.read_text(encoding="utf-8")
        self.assertRegex(chart, r'action_label\(\s*"revert"')
        self.assertRegex(self.src, r'action_label\(\s*"revert"')


class EverySectionGetsTheSameIcon(unittest.TestCase):
    """Section names are the musician's, so the icon comes from the action, not the name."""

    SECTIONS = ("Intro", "Verse 7", "Pre-Chorus", "Solo", "Outro", "Coda", "My own bit")

    def test_apply_duplicate_add_and_remove_look_identical_for_any_section(self) -> None:
        for verb, template in (
            ("apply_text", "Apply pasted chords to %s"),
            ("duplicate", "Duplicate (%s)"),
            ("add", "bar @ end (%s)"),
            ("remove", "last bar (%s)"),
        ):
            icon = semantic_action_icon(verb)
            for section in self.SECTIONS:
                with self.subTest(verb=verb, section=section):
                    label = action_label(verb, template % section)
                    self.assertTrue(label.startswith(icon + " "), label)
                    self.assertIn(section, label)

    def test_no_section_name_is_hardcoded_beside_an_icon(self) -> None:
        src = CHART.read_text(encoding="utf-8")
        for section in ("Verse 3", "Bridge", "Final Chorus"):
            with self.subTest(section=section):
                self.assertNotIn('"%s %s' % (ACTION_ICONS["duplicate"], section), src)
                self.assertNotIn('"%s %s' % (ACTION_ICONS["apply_text"], section), src)


class TheActionsThemselvesAreUntouched(unittest.TestCase):
    """This slice changes label text only - the handlers, keys and guards stay as they were."""

    def test_the_chart_editor_still_calls_the_same_handlers(self) -> None:
        src = CHART.read_text(encoding="utf-8")
        for call in (
            "delete_user_override(title, artist)",
            "export_overrides_json()",
            "import_overrides_json(",
            "parse_pipe_chord_line(quick)",
        ):
            with self.subTest(call=call):
                self.assertIn(call, src)

    def test_the_widget_keys_are_unchanged(self) -> None:
        src = CHART.read_text(encoding="utf-8")
        for key in (
            'key=f"chart_edit_apply_order::{title}"',
            'key=f"chart_edit_add_sec::{title}"',
            'key=f"chart_edit_del_sec::{title}"',
            'key=f"chart_edit_quick_apply::{sec_name}"',
            'key=f"chart_edit_add_bar::{sec_name}"',
            'key=f"chart_edit_rm_bar::{sec_name}"',
            'key=f"chart_edit_dup_go::{sec_name}"',
            'key="chart_override_import"',
        ):
            with self.subTest(key=key):
                self.assertIn(key, src)

    def test_the_lyrics_editor_still_calls_the_same_handlers(self) -> None:
        src = LYRICS.read_text(encoding="utf-8")
        for call in (
            "save_lyrics_my_version(",
            "save_lyrics_user_verified(",
            "revert_user_lyrics(",
            "apply_auto_assign_lyrics(",
            "add_lyrics_section(",
            "reset_lyrics_section_layout(",
        ):
            with self.subTest(call=call):
                self.assertIn(call, src)

    def test_the_destructive_button_keeps_its_disabled_guard(self) -> None:
        """Delete saved progression was already correct on dev; it must stay that way."""
        src = (ROOT / "cpl_page_ui.py").read_text(encoding="utf-8")
        self.assertIn('st.button("%s Delete saved progression", disabled=del_pick == "—")'
                      % ACTION_ICONS["delete"], src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

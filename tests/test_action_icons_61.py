"""Issue 61 — one icon per action verb, drawn from looks this app had already settled on.

The point of the shared map is that a verb looks the same everywhere. These tests pin the
new verbs, pin that each reuses an existing convention rather than inventing a glyph, and
pin that the buttons named in the issue actually route through ``action_label`` instead of
hard-coding a label.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from music_feature_icons import (
    ACTION_ICONS,
    FEATURE_ICONS,
    action_label,
    semantic_action_icon,
)

ROOT = Path(__file__).resolve().parents[1]


def _src(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class NewActionVerbs(unittest.TestCase):
    def test_every_creative_example_verb_has_an_icon(self):
        for verb in ("generate", "easier", "harder", "idea"):
            self.assertTrue(semantic_action_icon(verb), f"{verb} has no icon")

    def test_export_library_and_load_verbs_have_icons(self):
        for verb in ("play", "download", "analyze", "delete", "load"):
            self.assertTrue(semantic_action_icon(verb), f"{verb} has no icon")

    def test_action_label_prefixes_the_icon(self):
        self.assertEqual(action_label("idea", "New idea"), "💡 New idea")
        self.assertEqual(action_label("generate", "Generate example"), "🪄 Generate example")

    def test_an_unknown_verb_leaves_the_text_alone(self):
        self.assertEqual(action_label("no_such_verb", "Plain"), "Plain")


class VerbsReuseSettledLooks(unittest.TestCase):
    """Each new glyph matches one the codebase already used for that meaning."""

    def test_difficulty_pair_reuses_the_level_badges(self):
        from practice_ui_labels import LEVEL_ICONS

        self.assertEqual(ACTION_ICONS["easier"], LEVEL_ICONS["Beginner"])
        self.assertEqual(ACTION_ICONS["harder"], LEVEL_ICONS["Advanced"])

    def test_load_reuses_the_existing_load_feature_icon(self):
        self.assertEqual(ACTION_ICONS["load"], FEATURE_ICONS["action_load"])

    def test_play_matches_preview_because_it_is_the_same_gesture(self):
        self.assertEqual(ACTION_ICONS["play"], ACTION_ICONS["preview"])

    def test_generate_matches_the_composition_melody_generator(self):
        self.assertIn(f'"{ACTION_ICONS["generate"]} ', _src("composition_studio_page.py"))

    def test_idea_matches_the_existing_idea_glyph(self):
        self.assertIn(ACTION_ICONS["idea"], _src("composition_document.py"))

    def test_no_two_distinct_verbs_collide_unintentionally(self):
        """Shared glyphs must be deliberate pairs, not accidents."""
        allowed_shared = {
            frozenset({"new", "add"}),
            frozenset({"play", "preview"}),
        }
        by_icon: dict[str, set[str]] = {}
        for verb, icon in ACTION_ICONS.items():
            by_icon.setdefault(icon, set()).add(verb)
        for icon, verbs in by_icon.items():
            if len(verbs) > 1:
                self.assertIn(frozenset(verbs), allowed_shared, f"{icon} shared by {verbs}")


class CreativeButtonsUseTheSharedMap(unittest.TestCase):
    def setUp(self):
        self.src = _src("mission_span_ui.py")

    def test_the_four_example_buttons_route_through_action_label(self):
        self.assertIn("st.button(action_label(verb, label)", self.src)

    def test_each_button_declares_its_verb(self):
        for label, verb in (
            ("Generate example", "generate"),
            ("Easier example", "easier"),
            ("Harder example", "harder"),
            ("New idea", "idea"),
        ):
            row = re.search(rf'"{re.escape(label)}".*', self.src)
            self.assertIsNotNone(row, f"{label} row missing")
            self.assertIn(f'"{verb}"', row.group(0), f"{label} does not declare verb {verb}")

    def test_new_idea_shows_an_idea_not_a_plus(self):
        """Its intent is "new", but a plus would read as "add another track"."""
        row = re.search(r'"New idea".*', self.src).group(0)
        self.assertIn('"new"', row)   # the intent value is unchanged
        self.assertIn('"idea"', row)  # the icon verb is deliberately different
        self.assertNotEqual(ACTION_ICONS["idea"], ACTION_ICONS["new"])

    def test_the_labels_themselves_are_unchanged(self):
        for label in ("Generate example", "Easier example", "Harder example", "New idea"):
            self.assertIn(f'"{label}"', self.src)

    def test_no_hard_coded_emoji_was_pasted_into_the_labels(self):
        for label in ("Generate example", "Easier example", "Harder example", "New idea"):
            self.assertNotIn(f'"{ACTION_ICONS["generate"]} {label}"', self.src)


class ExportLibraryButtonsUseTheSharedMap(unittest.TestCase):
    def setUp(self):
        self.src = _src("multitrack_export_ui.py")

    def test_play_download_analyze_delete_all_route_through_action_label(self):
        for verb, label in (
            ("play", "Play"),
            ("download", "Download"),
            ("analyze", "Send to Upload Analysis"),
            ("delete", "Delete"),
        ):
            self.assertIn(f'action_label("{verb}", "{label}")', self.src)

    def test_save_export_still_uses_the_save_verb(self):
        self.assertIn('action_label("save", "Save Export")', self.src)

    def test_no_export_button_label_is_a_bare_string(self):
        for label in ('"Play"', '"Delete"', '"Send to Upload Analysis"'):
            self.assertNotIn(f"button({label}", self.src)


class SavedHistoryButtonsUseTheSharedMap(unittest.TestCase):
    def setUp(self):
        self.src = _src("studio_history_ui.py")

    def test_load_button_is_iconised_at_the_render_site(self):
        """So "Load" and "Load Project" both get it, without touching callers."""
        self.assertIn('action_label("load", load_button_label)', self.src)

    def test_the_load_project_caller_is_untouched(self):
        self.assertIn('load_button_label="Load Project"', self.src)

    def test_compact_delete_uses_the_shared_wastebasket_with_a_fallback(self):
        self.assertIn('semantic_action_icon("delete") or "✕"', self.src)

    def test_compact_delete_keeps_its_tooltip(self):
        self.assertIn('help="Delete"', self.src)


class BehaviourIsUnchanged(unittest.TestCase):
    """Issue 61 is cosmetic: no playback or analysis behaviour may move."""

    def test_export_button_keys_are_unchanged(self):
        src = _src("multitrack_export_ui.py")
        for key in (
            'key=f"mt_export_play_{eid}"',
            'key=f"mt_export_dl_{eid}"',
            'key=f"mt_export_analyze_{eid}"',
            'key=f"mt_export_del_{eid}"',
        ):
            self.assertIn(key, src)

    def test_creative_button_keys_and_intents_are_unchanged(self):
        src = _src("mission_span_ui.py")
        for key in (
            "improv_span_mission_gen",
            "improv_span_mission_easier",
            "improv_span_mission_harder",
            "improv_span_mission_new",
        ):
            self.assertIn(key, src)
        self.assertIn("intent = value", src)

    def test_history_button_keys_are_unchanged(self):
        src = _src("studio_history_ui.py")
        self.assertIn('key=f"{key_prefix}_load_{suffix}"', src)
        self.assertIn('key=f"{key_prefix}_del_{suffix}"', src)


if __name__ == "__main__":
    unittest.main()

"""One icon per action verb, used consistently across Multitrack and the Composition melody editor."""
import re
import unittest
from pathlib import Path

from music_feature_icons import ACTION_ICONS, action_label, semantic_action_icon

ROOT = Path(__file__).resolve().parents[1]


class TestActionIconMap(unittest.TestCase):
    def test_every_verb_the_ui_needs_has_an_icon(self):
        for verb in ("save", "download", "upload", "create_mix", "new", "add",
                     "delete", "edit", "apply_text", "preview", "accept", "reset", "continue", "feel"):
            self.assertTrue(semantic_action_icon(verb), verb)

    def test_the_same_verb_always_looks_the_same(self):
        self.assertEqual(semantic_action_icon("add"), semantic_action_icon("new"))
        self.assertEqual(action_label("save", "Save Export"), f"{ACTION_ICONS['save']} Save Export")

    def test_an_unknown_verb_leaves_the_label_alone(self):
        self.assertEqual(semantic_action_icon("flibble"), "")
        self.assertEqual(action_label("flibble", "Do it"), "Do it")

    def test_the_feel_icon_matches_the_style_field_badge(self):
        from music_feature_icons import semantic_field_icon

        self.assertEqual(semantic_action_icon("feel"), semantic_field_icon("feel"))


class TestButtonsUseTheMap(unittest.TestCase):
    CASES = (
        ("streamlit_music_practice_app.py", "create_mix", "Create mixed WAV"),
        ("streamlit_music_practice_app.py", "download", "Download mixed track WAV"),
        ("streamlit_music_practice_app.py", "delete", "Clear all multitrack layers"),
        ("streamlit_music_practice_app.py", "save", "Save layer"),
        ("streamlit_music_practice_app.py", "upload", "Upload"),
        ("streamlit_music_practice_app.py", "feel", "Groove / feel"),
        ("multitrack_export_ui.py", "save", "Save Export"),
        ("multitrack_export_ui.py", "download", "Download WAV"),
        ("studio_history_ui.py", "new", "New Project"),
        ("composition_studio_page.py", "edit", "Apply to selected note"),
        ("composition_studio_page.py", "delete", "Delete selected note"),
        ("composition_studio_page.py", "add", "Add note"),
        ("composition_studio_page.py", "apply_text", "Apply description"),
        ("composition_studio_page.py", "reset", "Reset proposal"),
    )

    def test_each_named_button_goes_through_action_label(self):
        for filename, verb, label in self.CASES:
            with self.subTest(file=filename, label=label):
                src = (ROOT / filename).read_text(encoding="utf-8")
                pattern = re.compile(r'action_label\(\s*"' + verb + r'"\s*,\s*f?"[^"]*' + re.escape(label))
                self.assertRegex(src, pattern)

    def test_the_files_import_the_helper(self):
        for filename in {c[0] for c in self.CASES}:
            src = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("action_label", src)


if __name__ == "__main__":
    unittest.main()

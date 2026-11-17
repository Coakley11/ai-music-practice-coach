"""Recording, analysis and project-save buttons carry the shared icons (save 💾, analyze 🎯, Upload Analysis 🎙️)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def src(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class Icons(unittest.TestCase):
    def test_save_tone_take(self):
        self.assertIn('action_label("save", "Save Tone Take")', src("tone_take_history_ui.py"))

    def test_run_ai_coach_analysis(self):
        self.assertIn('action_label("analyze", "Run AI coach analysis")', src("streamlit_music_practice_app.py"))

    def test_open_upload_analysis_uses_the_upload_analysis_icon(self):
        self.assertIn('page_feature_label("analysis", "Open Upload Analysis")', src("improvisation_intelligence_ui.py"))
        from music_feature_icons import page_feature_label

        self.assertTrue(page_feature_label("analysis", "x").startswith("🎙️"))

    def test_project_saves(self):
        s = src("studio_history_ui.py")
        for text in ("Save Changes", "Save New Project", "Save as New Project"):
            self.assertIn(f'action_label("save", "{text}")', s)


if __name__ == "__main__":
    unittest.main()

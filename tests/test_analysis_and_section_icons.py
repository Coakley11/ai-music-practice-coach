"""Upload Analysis history saves, Manage sections and Restore saved audio carry the shared icons."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def src(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class Icons(unittest.TestCase):
    def test_upload_history_saves(self):
        s = src("studio_history_ui.py")
        self.assertIn('action_label("save", save_label)', s)       # "Save to History" / "Save Changes"
        self.assertIn('action_label("save", "Save as New Copy")', s)
        self.assertIn('action_label("load", load_button_label)', s)  # Load a saved analysis (already had it)

    def test_manage_sections(self):
        self.assertIn('st.expander(action_label("edit", "Manage sections")', src("lyrics_cues_panel.py"))

    def test_restore_saved_audio(self):
        self.assertIn('action_label("load", "Restore saved audio")', src("streamlit_music_practice_app.py"))


class RemainingUserFacingButtons(unittest.TestCase):
    def test_composition_dismiss_uses_the_ami_dismiss_icon(self):
        s = src("composition_studio_page.py")
        self.assertIn('icon=AMI_ACTION_ICONS["dismiss"]', s)

    def test_download_this_reference(self):
        self.assertIn('_dl_label("download", "Download this reference")', src("song_document_panel.py"))

    def test_practice_log_open_upload_analysis(self):
        self.assertIn('page_feature_label("analysis", "Open Upload Analysis")', src("practice_log_coach.py"))


if __name__ == "__main__":
    unittest.main()

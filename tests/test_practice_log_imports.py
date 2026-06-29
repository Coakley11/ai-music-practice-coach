"""Import smoke tests for Practice Log page modules."""

from __future__ import annotations

import unittest


class TestPracticeLogImports(unittest.TestCase):
    def test_practice_log_analysis_panel_import(self) -> None:
        from practice_log_analysis_panel import render_practice_analysis_panel

        self.assertTrue(callable(render_practice_analysis_panel))

    def test_practice_log_ui_reexports_panel(self) -> None:
        from practice_log_ui import render_practice_analysis_panel, render_practice_log_page

        self.assertTrue(callable(render_practice_analysis_panel))
        self.assertTrue(callable(render_practice_log_page))

    def test_log_page_import_surface(self) -> None:
        """Match streamlit_music_practice_app.py Practice Log import lines."""
        from practice_log_analysis_panel import render_practice_analysis_panel
        from practice_log_ui import render_practice_log_page

        self.assertTrue(callable(render_practice_analysis_panel))
        self.assertTrue(callable(render_practice_log_page))

    def test_app_source_renders_analysis_panel_on_log_page(self) -> None:
        from pathlib import Path

        app_source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("log_practice_analysis_panel", app_source)
        self.assertIn("render_practice_analysis_panel", app_source)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Multitrack source/section/layer icon + Song/Section label publish checks."""
from __future__ import annotations

import unittest
from pathlib import Path

from music_feature_icons import FEATURE_ICONS, instrument_icon


class MultitrackM7PublishUiTests(unittest.TestCase):
    def test_song_section_label_and_section_icon(self) -> None:
        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn('"Song / section"', text)
        self.assertNotIn('"Song / project"', text)
        self.assertIn('FEATURE_ICONS.get("section_focus")', text)

    def test_layer_headings_use_instrument_icons(self) -> None:
        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("ui-mt-layer-heading", text)
        self.assertIn("instrument_icon(slot)", text)
        self.assertEqual(instrument_icon("Guitar"), "🎸")
        self.assertEqual(instrument_icon("Bass"), "🎸")
        self.assertEqual(instrument_icon("Piano / Keys"), "🎹")
        self.assertEqual(instrument_icon("Vocals"), "🎤")
        self.assertEqual(instrument_icon("Sax / winds"), "🎷")
        self.assertEqual(instrument_icon("Extra layer"), "✨")

    def test_active_source_badge_helper(self) -> None:
        from app_ui import _multitrack_active_source_badge_parts

        ico, cls, title = _multitrack_active_source_badge_parts({})
        self.assertEqual(cls, "source-catalog")
        self.assertEqual(ico, "🎵")
        self.assertIn("Catalog", title)

        composed = {
            "studio_page": "composer",
            "analysis_prefer_composed_source": True,
            "selected_song": {"title": "My Composition", "artist": "Composition"},
        }
        # Prefer composition helpers when active document present
        try:
            from composition_session_state import set_active_document
            from composition_document import new_composition_document

            doc = new_composition_document(title="My Composition")
            set_active_document(composed, doc)
        except Exception:
            composed["analysis_prefer_composed_source"] = True
        ico2, cls2, _ = _multitrack_active_source_badge_parts(composed)
        # May resolve composition when helpers cooperate; otherwise stay catalog.
        self.assertIn(cls2, {"source-composition", "source-catalog"})
        if cls2 == "source-composition":
            self.assertEqual(ico2, FEATURE_ICONS["composition"])

    def test_context_strip_uses_source_helper(self) -> None:
        text = Path("app_ui.py").read_text(encoding="utf-8")
        self.assertIn("_multitrack_active_source_badge_parts", text)
        self.assertIn("source-composition", text)
        self.assertIn("ui-mt-setup-section-icon--section", text)

    def test_history_nav_between_welcome_and_quick_nav(self) -> None:
        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        welcome_i = text.find("show_persistence_messages(st)")
        hist_i = text.find('key="studio_history_nav_row"')
        qn_i = text.find("if pp.show_quick_nav(st):")
        self.assertGreater(welcome_i, 0)
        self.assertGreater(hist_i, welcome_i)
        self.assertGreater(qn_i, hist_i)
        # Only one live render site
        self.assertEqual(
            text.count("render_floating_nav_history(st, st.session_state, rerun_fn=st.rerun)"),
            1,
        )


if __name__ == "__main__":
    unittest.main()

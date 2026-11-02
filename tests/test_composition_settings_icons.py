"""Issue 11: Composition Song Settings labels carry the app's standard field icons."""

from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest

from music_feature_icons import semantic_field_icon


def _page() -> None:
    import streamlit as st

    from composition_document import new_composition_document
    from composition_studio_page import _render_compact_song_settings

    doc = new_composition_document(title="Icons")
    _render_compact_song_settings(st.session_state, doc, key_prefix="iconstest")


class TestSongSettingsIcons(unittest.TestCase):
    def test_every_setting_leads_with_its_standard_icon(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120).run()
        self.assertFalse(at.exception)
        labels = [w.label for w in list(at.selectbox) + list(at.number_input)]
        want = {
            "Genre / Style": semantic_field_icon("style"),
            "Original Key": semantic_field_icon("original_key"),
            "Tempo (BPM)": semantic_field_icon("bpm"),
            "Meter": semantic_field_icon("meter"),
        }
        for text, icon in want.items():
            match = [label for label in labels if label.endswith(text)]
            self.assertEqual(len(match), 1, (text, labels))
            self.assertTrue(match[0].startswith(icon), match[0])

    def test_the_icons_are_the_requested_glyphs(self) -> None:
        self.assertEqual(semantic_field_icon("style"), "✨")
        self.assertEqual(semantic_field_icon("meter"), "\U0001f941")
        self.assertEqual(semantic_field_icon("bpm").rstrip("️"), "⏱")


if __name__ == "__main__":
    unittest.main()

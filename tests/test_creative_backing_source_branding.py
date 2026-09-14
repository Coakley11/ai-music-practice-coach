"""SBI/Custom/Composition Backing cards follow current source branding + semantic icons."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backing_context import BackingContext
from backing_context_ui import render_backing_creative_context_card
from music_feature_icons import FEATURE_ICONS, semantic_field_icon


def _sbi_ctx(*, kind: str, title: str, pick: str) -> BackingContext:
    return BackingContext(
        source="song_improv",
        source_label="Song-Based Improvisation",
        active_song_id=pick,
        song_title=title,
        key="C#",
        display_key="C#",
        concert_key="C#",
        bpm=100,
        style="Auto",
        groove="Auto",
        meter="4/4",
        progression=["C#", "C#", "F#", "F#"],
        progression_label="Verse / Chorus",
        section=None,
        sections=["Verse", "Chorus"],
        section_labels=["Verse", "Chorus"],
        entry_mode="Song-Based Improvisation",
        mode_label="Song-Based Improvisation",
        bound_pick_key=pick,
        sbi_source_owner=(
            "Custom progression"
            if kind == "custom"
            else ("Composition" if kind == "composition" else "Active song")
        ),
        sbi_material_kind=kind,
    )


def _render(ctx: BackingContext, session: dict) -> str:
    st = MagicMock()
    render_backing_creative_context_card(
        st,
        ctx,
        session,
        applied_bpm=100,
        applied_groove="Auto",
        applied_meter="4/4",
        practice_key="C#",
    )
    return str(st.markdown.call_args[0][0])


class TestSbiCustomBackingBranding(unittest.TestCase):
    def test_sbi_custom_uses_custom_green_and_logo_not_sax(self) -> None:
        ctx = _sbi_ctx(kind="custom", title="My Progression", pick="custom::my-progression")
        html_out = _render(
            ctx,
            {
                "instrument": "Piano",
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
        )
        self.assertIn("Creative backing session", html_out)
        self.assertIn("My Progression", html_out)
        self.assertIn("Song-Based Improvisation · Custom progression", html_out)
        self.assertIn(FEATURE_ICONS["custom"], html_out)
        self.assertIn("source-custom", html_out)
        self.assertIn("mode-source-custom-backing", html_out)
        self.assertIn("#10b981", html_out)
        self.assertIn('data-backing-card-owner="custom"', html_out)
        self.assertNotIn("🎷<small>", html_out)
        self.assertNotIn("mode-source-catalog-backing", html_out)
        self.assertNotIn(FEATURE_ICONS["composition"], html_out)
        # Style / Concert key / Sections use canonical field icons, not sax / score / notes.
        self.assertIn(f'{semantic_field_icon("style")} Style', html_out)
        self.assertIn(f'{semantic_field_icon("concert_key")} Concert key', html_out)
        self.assertIn(f'{semantic_field_icon("bpm")} BPM', html_out)
        self.assertIn(f'{semantic_field_icon("meter")} Meter', html_out)
        self.assertIn(f'{semantic_field_icon("section")} Sections', html_out)
        self.assertNotIn("🎷 Style", html_out)
        self.assertNotIn("🎼 Concert key", html_out)
        self.assertNotIn("𝄞 Meter", html_out)
        self.assertNotIn("🎵 Sections", html_out)

    def test_sbi_catalog_stays_blue_catalog_branded(self) -> None:
        ctx = _sbi_ctx(kind="catalog", title="Shape of You", pick="Pop\x1fShape of You")
        html_out = _render(
            ctx,
            {
                "instrument": "Piano",
                "improv_song_source": "Active song",
                "sbi_preview_source": "Active song",
            },
        )
        self.assertIn("Shape of You", html_out)
        self.assertIn(FEATURE_ICONS["songs"], html_out)
        self.assertIn("mode-source-catalog-backing", html_out)
        self.assertIn('data-backing-card-owner="catalog"', html_out)
        self.assertNotIn("source-custom", html_out)
        self.assertNotIn(FEATURE_ICONS["custom"], html_out)

    def test_sbi_composition_uses_black_composition_logo(self) -> None:
        ctx = _sbi_ctx(kind="composition", title="My Composition", pick="composition::generic")
        html_out = _render(
            ctx,
            {
                "instrument": "Piano",
                "improv_song_source": "Composition",
                "sbi_preview_source": "Composition",
            },
        )
        self.assertIn(FEATURE_ICONS["composition"], html_out)
        self.assertIn("source-composition", html_out)
        self.assertIn("mode-source-composition-backing", html_out)
        self.assertIn('data-backing-card-owner="composition"', html_out)
        self.assertNotIn("source-custom", html_out)
        self.assertNotIn("🎷<small>", html_out)


class TestSemanticFieldIconsSsot(unittest.TestCase):
    def test_canonical_field_mapping(self) -> None:
        self.assertEqual(semantic_field_icon("style"), "✨")
        self.assertEqual(semantic_field_icon("concert_key"), "🗝️")
        self.assertEqual(semantic_field_icon("section"), "🔁")
        self.assertEqual(semantic_field_icon("meter"), "🥁")
        self.assertEqual(semantic_field_icon("bpm"), "⏱")
        self.assertNotEqual(semantic_field_icon("style"), "🎷")
        self.assertNotEqual(semantic_field_icon("section"), "🎵")


if __name__ == "__main__":
    unittest.main()

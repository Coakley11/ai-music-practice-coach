"""SBI source-type labels and Composition owner isolation."""

from __future__ import annotations

import unittest

from source_session_state import (
    COMPOSITION_SBI_UNAVAILABLE_TITLE,
    IMPROV_SONG_SOURCES,
    format_sbi_backing_blue_card_subtitle,
    resolve_sbi_preview,
    sbi_source_type_label,
)
from studio_page_state import (
    apply_improv_song_source,
    creative_song_source_display_label,
)


class TestSbiSongSourceSelector(unittest.TestCase):
    def test_selector_includes_composition_next_to_custom(self) -> None:
        self.assertEqual(
            IMPROV_SONG_SOURCES,
            ("Active song", "Custom progression", "Composition"),
        )
        self.assertEqual(creative_song_source_display_label("Active song"), "Active Source")
        self.assertIn("Custom Progression", creative_song_source_display_label("Custom progression"))
        self.assertEqual(creative_song_source_display_label("Composition"), "🎹 Composition")


class TestSbiBlueCardSourceType(unittest.TestCase):
    def test_custom_owner_label_is_custom_progression_not_title(self) -> None:
        session = {
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "song": "Trial Song",
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Pop\x1fShape of You",
        }
        self.assertEqual(sbi_source_type_label(session), "Custom progression")
        self.assertEqual(
            format_sbi_backing_blue_card_subtitle(session),
            "Song-Based Improvisation · Custom progression",
        )
        self.assertNotIn("Catalog song", format_sbi_backing_blue_card_subtitle(session))

    def test_active_catalog_owner_label_is_catalog_song(self) -> None:
        session = {
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "song": "Shape of You",
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Pop\x1fShape of You",
        }
        self.assertEqual(sbi_source_type_label(session), "Catalog song")
        self.assertEqual(
            format_sbi_backing_blue_card_subtitle(session),
            "Song-Based Improvisation · Catalog song",
        )

    def test_does_not_derive_kind_from_title(self) -> None:
        session = {
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "song": "Shape of You",
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Pop\x1fShape of You",
        }
        self.assertEqual(sbi_source_type_label(session), "Custom progression")

    def test_sealed_ctx_wins_over_session_title(self) -> None:
        from types import SimpleNamespace

        ctx = SimpleNamespace(
            sbi_material_kind="custom",
            sbi_source_owner="Custom progression",
            song_title="Shape of You",
            bound_pick_key="custom::trial",
        )
        session = {
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "song": "Shape of You",
        }
        self.assertEqual(sbi_source_type_label(session, ctx=ctx), "Custom progression")

    def test_composition_label_ready_for_future_source(self) -> None:
        session = {
            "improv_song_source": "Composition",
            "sbi_preview_source": "Composition",
            "song": "Shape of You",
        }
        self.assertEqual(sbi_source_type_label(session), "Composition")
        self.assertEqual(
            format_sbi_backing_blue_card_subtitle(session),
            "Song-Based Improvisation · Composition",
        )


class TestSbiCompositionIsolation(unittest.TestCase):
    def test_preview_is_empty_not_catalog_or_custom(self) -> None:
        session = {
            "improv_song_source": "Composition",
            "sbi_preview_source": "Composition",
            "song": "Shape of You",
            "active_catalog_pick_key": "Pop\x1fShape of You",
            "custom_session": {
                "title": "Trial Song",
                "sections": {"Verse": ["D", "G"]},
            },
            "catalog_session": {
                "pick_key": "Pop\x1fShape of You",
                "selected_song": {"title": "Shape of You", "key": "Bm"},
            },
        }
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("source"), "Composition")
        self.assertEqual(preview.get("title"), COMPOSITION_SBI_UNAVAILABLE_TITLE)
        self.assertFalse(preview.get("available"))
        self.assertEqual(preview.get("sections") or {}, {})
        self.assertNotEqual(preview.get("title"), "Shape of You")
        self.assertNotEqual(preview.get("title"), "Trial Song")

    def test_selecting_composition_does_not_mutate_global_or_custom_pk(self) -> None:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, SOURCE_CATALOG

        shape = "Pop\x1fShape of You"
        session = {
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": shape,
            "song": "Shape of You",
            "practice_key_by_source": {shape: "Bm", "custom::trial": "E"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "pick_key": "custom::trial",
            },
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
        }
        before = {
            "active_music_source": session["active_music_source"],
            "active_catalog_pick_key": session["active_catalog_pick_key"],
            "practice_key_by_source": dict(session["practice_key_by_source"]),
            "last_custom": dict(session[LAST_CUSTOM_STATE_KEY]),
        }
        apply_improv_song_source(
            session,
            "Composition",
            set_catalog_source=lambda s: s.__setitem__("active_music_source", "catalog_mutated"),
            set_custom_source=lambda s: s.__setitem__("active_music_source", "custom_mutated"),
        )
        self.assertEqual(session.get("improv_song_source"), "Composition")
        self.assertEqual(session.get("sbi_preview_source"), "Composition")
        self.assertEqual(session.get("active_music_source"), before["active_music_source"])
        self.assertEqual(session.get("active_catalog_pick_key"), before["active_catalog_pick_key"])
        self.assertEqual(session.get("practice_key_by_source"), before["practice_key_by_source"])
        self.assertEqual(session.get(LAST_CUSTOM_STATE_KEY), before["last_custom"])

    def test_build_song_improv_context_does_not_fall_through_to_catalog(self) -> None:
        from backing_context import build_song_improv_context, sections_dict_from_backing_context

        session = {
            "improv_song_source": "Composition",
            "sbi_preview_source": "Composition",
            "song": "Shape of You",
            "active_catalog_pick_key": "Pop\x1fShape of You",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": "Pop\x1fShape of You"},
            "improv_song_concert_sections": {"Verse": ["Bm", "Em", "G", "A"]},
        }
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(ctx.sbi_source_owner, "Composition")
        self.assertEqual(ctx.sbi_material_kind, "composition")
        self.assertEqual(ctx.song_title, COMPOSITION_SBI_UNAVAILABLE_TITLE)
        self.assertEqual(list(ctx.progression or []), [])
        self.assertEqual(ctx.bound_pick_key, "")
        sections = sections_dict_from_backing_context(session, ctx)
        self.assertEqual(sections, {})
        self.assertNotEqual(ctx.song_title, "Shape of You")

    def test_custom_sbi_context_stamps_custom_kind(self) -> None:
        from backing_context import build_song_improv_context
        from studio_page_state import CREATIVE_BACKING_SONG_SOURCE_KEY

        session = {
            "active_catalog_pick_key": "Pop::Photograph",
            "selected_song": {"title": "Photograph", "key": "E", "pick_key": "Pop::Photograph"},
            "song": "Photograph",
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Custom progression",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "improv_entry_mode": "Song-Based Improvisation",
            "cpl_active_progression": {
                "id": "custom-rev-trial",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [{"chord": "D", "bars": 1}, {"chord": "G", "bars": 1}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
                "bpm": 90,
            },
        }
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertEqual(ctx.sbi_source_owner, "Custom progression")
        self.assertEqual(ctx.sbi_material_kind, "custom")
        self.assertEqual(sbi_source_type_label(session, ctx=ctx), "Custom progression")


if __name__ == "__main__":
    unittest.main()

"""Regression: invalid source/key/card combinations must never pass silently."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock


class TestSourceAuthorityCoherence(unittest.TestCase):
    def test_composition_banner_never_uses_custom_title(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import active_source_labels

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "G",
            CPL_ACTIVE_KEY: {
                "name": "My Progression",
                "id": "prog-1",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            },
            "active_catalog_pick_key": "custom::prog-1",
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        kind, detail = active_source_labels(
            ss,
            catalog_title="My Progression",
            catalog_artist="Custom",
            custom_name="My Progression",
        )
        self.assertEqual(kind, "Composition")
        self.assertNotIn("My Progression", detail)
        self.assertEqual(detail, "My Composition")

    def test_get_song_context_composition_outranks_custom_pick(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.state import get_song_context

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "C",
            "active_catalog_pick_key": "custom::stale",
            "selected_song": {
                "pick_key": "custom::stale",
                "title": "My Progression",
                "artist": "Custom",
            },
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        genre, title, data = get_song_context(
            st, song_library={}, song_picker_catalog={}
        )
        self.assertEqual(genre, "Composition")
        self.assertEqual(title, "My Composition")
        self.assertTrue(data.get("is_composition"))
        self.assertFalse(bool(data.get("is_custom")))

    def test_catalog_radio_commits_without_custom_hub_window(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            commit_explicit_music_source_choice,
            music_picker_shows_custom_hub,
            reconcile_music_picker_source_widget,
            set_custom_source,
        )

        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial",
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        set_custom_source(ss)
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        reconcile_music_picker_source_widget(ss)
        self.assertEqual(ss.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertFalse(music_picker_shows_custom_hub(ss))

    def test_invalid_combinations_detected(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SOURCE_COMPOSITION,
            SOURCE_CUSTOM,
            commit_explicit_music_source_choice,
            set_custom_source,
        )
        from songs.source_authority_coherence import coherence_violations

        ss: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "custom::x",
            "display_key": "G",
            "song_picker_active_source": "🪶 Composition",
        }
        commit_explicit_music_source_choice(ss, SOURCE_COMPOSITION)
        bad = coherence_violations(
            ss,
            card_source="Custom progression",
            card_practice_key="C",
            sidebar_practice_key="G",
            body_text="Edit chords in Custom Progression Lab. My Progression · Custom",
        )
        self.assertIn("composition_owner_with_custom_pick", bad)
        self.assertIn("composition_active_with_custom_card", bad)
        self.assertIn("composition_page_has_custom_lab_copy", bad)
        self.assertIn("sidebar_key_ne_card_practice_key", bad)

        ss2: dict = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "composition::doc",
        }
        set_custom_source(ss2)
        commit_explicit_music_source_choice(ss2, SOURCE_CUSTOM)
        bad2 = coherence_violations(ss2, card_source="Composition")
        self.assertIn("custom_active_with_composition_pick", bad2)

    def test_composition_sidebar_card_practice_key_agree(self) -> None:
        from backing_context import build_composition_song_context, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from composition_songs_bridge import (
            commit_composition_active_song,
            composition_pick_key_for,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.practice_key_state import set_practice_concert_key

        ss: dict = {
            "instrument": "Alto Sax",
            "composer_saved_compositions": {},
            "display_key": "G",
            "concert_key": "G",
            "studio_page": "backing",
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(
            st, doc, invalidate_backing=lambda _s: None, reset_practice_to_original=True
        )
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "D#", pick_key=pick)
        ss["display_key"] = "G"  # simulate stale sidebar leftover
        ss["concert_key"] = "G"
        ctx = build_composition_song_context(ss)
        set_backing_context(ss, ctx)
        state = resolve_current_backing_musical_state(ss, applied_bpm=96)
        self.assertEqual(state.practice_concert_key[:2].replace("♯", "#"), "D#")
        self.assertEqual(state.sidebar_display_key[:2].replace("♯", "#"), "D#")


class TestDisplayKeyContextComposition(unittest.TestCase):
    def test_display_key_context_composition_before_cpl(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import display_key_context

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            CPL_ACTIVE_KEY: {
                "name": "My Progression",
                "id": "x",
                "original_key_center": "G",
                "original_sections": {"A": [{"chord": "G", "bars": 1}]},
            },
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        home, identity = display_key_context(
            ss,
            catalog_song_data={"title": "My Progression", "key": "G"},
            cpl_active_key=CPL_ACTIVE_KEY,
        )
        self.assertEqual(home, "C")
        self.assertIn("Composition", str(identity))


if __name__ == "__main__":
    unittest.main()

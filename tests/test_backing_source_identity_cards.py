"""Songs captions + Custom/Composition Backing source-identity cards."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock

from music_feature_icons import FEATURE_ICONS


class TestSongsSourceCaptions(unittest.TestCase):
    def test_composition_and_custom_captions_include_creative(self) -> None:
        import streamlit_music_practice_app as app

        comp_src = inspect.getsource(app._render_composition_active_song_hub)
        custom_src = inspect.getsource(app._render_custom_active_song_hub)
        self.assertIn("Practice, Creative, Backing Track, and Karaoke", comp_src)
        self.assertIn("Practice, Creative, Backing Track, and charts", custom_src)
        self.assertIn("FEATURE_ICONS.get('composition'", comp_src)
        self.assertIn("FEATURE_ICONS.get('custom'", custom_src)
        self.assertNotIn("UUID identity", comp_src)


class TestCustomBackingCardGreen(unittest.TestCase):
    def test_custom_backing_card_uses_green_and_custom_icon(self) -> None:
        from backing_context import build_custom_progression_context, set_backing_context
        from backing_context_ui import render_backing_custom_progression_context_card

        session = {
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-green-1",
                "original_key_center": "D",
                "bpm": 120,
                "original_sections": {
                    "Verse": [{"chord": "Dm7", "bars": 2}, {"chord": "G7", "bars": 2}],
                },
            },
            "active_music_source": "custom_progression",
        }
        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.source, "custom_progression")
        set_backing_context(session, ctx)
        st = MagicMock()
        render_backing_custom_progression_context_card(
            st,
            ctx,
            session,
            applied_bpm=120,
            applied_groove="Pop groove",
            practice_key="D",
        )
        html_out = str(st.markdown.call_args[0][0])
        self.assertIn(FEATURE_ICONS["custom"], html_out)
        self.assertIn("#10b981", html_out)
        self.assertIn("#059669", html_out)
        self.assertIn("mode-custom-progression-backing", html_out)
        self.assertNotIn("#0891b2", html_out)
        self.assertNotIn(FEATURE_ICONS["composition"], html_out)
        self.assertNotIn(FEATURE_ICONS["songs"], html_out)


class TestCompositionBackingCard(unittest.TestCase):
    def test_composition_active_backing_produces_my_composition_in_c(self) -> None:
        from backing_context import build_composition_song_context, set_backing_context
        from backing_context_ui import render_backing_composition_song_context_card
        from composition_songs_bridge import (
            SOURCE_COMPOSITION,
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "C",
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        self.assertEqual(ss.get("active_music_source"), SOURCE_COMPOSITION)
        ctx = build_composition_song_context(ss)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ctx.song_title, "My Composition")
        self.assertEqual(ctx.key, "C")
        set_backing_context(ss, ctx)

        st_ui = MagicMock()
        render_backing_composition_song_context_card(
            st_ui,
            ctx,
            ss,
            applied_bpm=96,
            applied_groove="Auto",
            practice_key="C",
        )
        html_out = str(st_ui.markdown.call_args[0][0])
        self.assertIn("My Composition", html_out)
        self.assertIn("Backing Track · Composition song", html_out)
        self.assertIn(FEATURE_ICONS["composition"], html_out)
        self.assertIn("#0f172a", html_out)
        self.assertIn("mode-composition-song-backing", html_out)
        self.assertNotIn(FEATURE_ICONS["custom"], html_out)
        self.assertNotIn("#10b981", html_out)

    def test_composition_source_survives_refresh_and_does_not_leak(self) -> None:
        import copy

        from backing_context import (
            build_composition_song_context,
            build_custom_progression_context,
            build_regular_song_context,
            reset_backing_on_active_song_change,
        )
        from composition_songs_bridge import (
            SOURCE_COMPOSITION,
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        from songs.practice_key_state import set_practice_concert_key
        from composition_songs_bridge import composition_pick_key_for

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "G",
            "cpl_saved_progressions": {},
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        # User Practice Key G must be persisted per Composition pick (not live leak).
        set_practice_concert_key(ss, "G", pick_key=composition_pick_key_for(doc))
        ss["display_key"] = "G"
        ctx = reset_backing_on_active_song_change(ss)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ss.get("active_music_source"), SOURCE_COMPOSITION)
        self.assertTrue(str(ss.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("composition::"))
        self.assertEqual(ctx.concert_key, "G")

        blob = copy.deepcopy(ss)
        restored = copy.deepcopy(blob)
        ctx2 = build_composition_song_context(restored)
        self.assertEqual(ctx2.source, "composition_song")
        self.assertEqual(ctx2.song_title, "My Composition")
        self.assertEqual(restored.get("active_music_source"), SOURCE_COMPOSITION)
        # Practice Key preserved via per-pick store on restore snapshot
        self.assertEqual(ctx2.concert_key, "G")
        self.assertEqual(restored.get("display_key"), "G")

        # Source isolation: custom / catalog builders must not claim Composition session
        custom_ss = {
            "cpl_active_progression": {
                "name": "Other",
                "id": "cust-1",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 2}]},
                "bpm": 100,
            },
            "active_music_source": "custom_progression",
        }
        self.assertEqual(build_custom_progression_context(custom_ss).source, "custom_progression")
        catalog_ss = {
            "active_music_source": "catalog_song",
            "selected_song": {
                "title": "My Composition",
                "artist": "Catalog",
                "key": "Ab",
                "pick_key": "Jazz\x1fMy Composition — Catalog",
            },
            "active_catalog_pick_key": "Jazz\x1fMy Composition — Catalog",
        }
        cat_ctx = build_regular_song_context(catalog_ss)
        self.assertEqual(cat_ctx.source, "regular_song")
        self.assertNotEqual(cat_ctx.source, "composition_song")


class TestCompositionSourceOwnership(unittest.TestCase):
    def test_ensure_composition_owns_active_song_promotes_my_composition(self) -> None:
        from unittest.mock import MagicMock

        from composition_songs_bridge import GENERIC_COMPOSITION_KEY, GENERIC_COMPOSITION_TITLE
        from songs.music_source import (
            composition_song_is_active,
            ensure_composition_owns_active_song,
        )

        st = MagicMock()
        ss: dict = {
            "active_catalog_pick_key": "Pop\x1fSay — John Mayer",
            "selected_song": {
                "pick_key": "Pop\x1fSay — John Mayer",
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            "active_music_source": "catalog_song",
            "_user_chose_catalog_music_source": True,
        }
        st.session_state = ss

        doc = ensure_composition_owns_active_song(st, invalidate_backing=lambda _st: None)
        self.assertIsInstance(doc, dict)
        self.assertEqual(str(doc.get("title") or ""), GENERIC_COMPOSITION_TITLE)
        self.assertEqual(
            str((doc.get("global") or {}).get("original_key_center") or ""),
            GENERIC_COMPOSITION_KEY,
        )
        self.assertTrue(composition_song_is_active(ss))
        self.assertTrue(str(ss.get("active_catalog_pick_key") or "").startswith("composition::"))
        self.assertEqual((ss.get("selected_song") or {}).get("title"), GENERIC_COMPOSITION_TITLE)

    def test_composition_pick_is_not_catalog_practice_owner(self) -> None:
        from music_source_ownership import intended_practice_owner

        ss = {
            "active_catalog_pick_key": "composition::abc",
            "active_music_source": "composition_song",
            "selected_song": {
                "pick_key": "composition::abc",
                "title": "My Composition",
                "artist": "Composition",
                "key": "C",
                "is_composition": True,
            },
        }
        self.assertIsNone(intended_practice_owner(ss))

    def test_commit_composition_persists_with_music_source_switch(self) -> None:
        """Composition ownership must use music_source_switch (not suppressed song_edit)."""
        from unittest.mock import MagicMock, patch

        from composition_songs_bridge import (
            SOURCE_COMPOSITION,
            commit_composition_active_song,
            ensure_generic_composition_document,
        )

        st = MagicMock()
        ss: dict = {
            "active_catalog_pick_key": "custom::My Progression",
            "active_music_source": "custom_progression",
            "selected_song": {
                "pick_key": "custom::My Progression",
                "title": "My Progression",
                "artist": "Custom",
                "key": "C",
            },
        }
        st.session_state = ss
        doc = ensure_generic_composition_document(ss)
        seen: list[str] = []

        def _persist(_st, **extra):
            seen.append(str(extra.get("save_reason") or ""))

        with patch(
            "songs.state.persist_music_local_state",
            side_effect=_persist,
        ):
            commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        self.assertIn("music_source_switch", seen)
        self.assertEqual(ss.get("active_music_source"), SOURCE_COMPOSITION)
        self.assertTrue(str(ss.get("active_catalog_pick_key") or "").startswith("composition::"))

    def test_open_backing_forces_composition_when_pick_is_composition(self) -> None:
        """Custom active_music_source must not win when pick_key is composition::."""
        from types import SimpleNamespace

        from backing_source_navigation import open_backing_for_practice_source
        from composition_songs_bridge import ensure_generic_composition_document

        ss: dict = {
            "active_catalog_pick_key": "composition::force-test",
            "active_music_source": "custom_progression",
            "active_song_state": {
                "pick_key": "composition::force-test",
                "music_source": "composition_song",
            },
            "selected_song": {
                "pick_key": "composition::force-test",
                "title": "My Composition",
                "artist": "Composition",
                "key": "C",
                "is_composition": True,
            },
            "_backing_source_preference": "custom",
            "_force_composition_backing_open": True,
        }
        ensure_generic_composition_document(ss)
        # Force pick onto the generic doc id after ensure.
        pick = str(ss.get("active_catalog_pick_key") or "")
        if not pick.startswith("composition::"):
            ss["active_catalog_pick_key"] = "composition::force-test"
        ss["active_music_source"] = "custom_progression"
        ss["_backing_source_preference"] = "custom"
        ss["_force_composition_backing_open"] = True

        ctx = open_backing_for_practice_source(
            ss, st_like=SimpleNamespace(session_state=ss)
        )
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", None), "composition_song")


if __name__ == "__main__":
    unittest.main()

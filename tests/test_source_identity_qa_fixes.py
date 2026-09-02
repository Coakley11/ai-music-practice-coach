"""Focused regressions for Custom/Composition identity + lifecycle QA."""
from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock


class TestBackingCardSubregions(unittest.TestCase):
    def test_custom_backing_card_greens_only_left_identity(self) -> None:
        from backing_context import BackingContext
        from backing_context_ui import render_backing_custom_progression_context_card

        ctx = BackingContext(
            source="custom_progression",
            source_label="Custom progression",
            active_song_id="custom::trial",
            song_title="Trial Song",
            key="D",
            display_key="D",
            concert_key="D",
            bpm=120,
            style="Pop",
            groove="Pop",
            progression=["Dm", "G", "C", "Am"],
            progression_label="Trial",
            bound_pick_key="custom::trial",
        )
        st = MagicMock()
        render_backing_custom_progression_context_card(
            st,
            ctx,
            {"display_key": "D"},
            applied_bpm=120,
            applied_groove="Pop",
        )
        html_out = str(st.markdown.call_args[0][0])
        self.assertIn("ui-source-identity-art source-custom", html_out)
        self.assertIn("#10b981", html_out)
        self.assertIn("tone-source", html_out)
        self.assertIn("📀", html_out)
        self.assertIn("Custom progression", html_out)
        self.assertIn("mode-custom-progression-backing", html_out)
        # Left art carries green; whole-card body is not green-washed inline.
        art_idx = html_out.find("source-custom")
        body_idx = html_out.find("ui-backing-active-body")
        self.assertGreater(art_idx, 0)
        self.assertGreater(body_idx, art_idx)
        art_chunk = html_out[art_idx : body_idx]
        self.assertIn("#10b981", art_chunk)

    def test_composition_backing_card_blacks_only_left_and_style_auto(self) -> None:
        from backing_context import BackingContext
        from backing_context_ui import render_backing_composition_song_context_card

        ctx = BackingContext(
            source="composition_song",
            source_label="Composition song",
            active_song_id="composition::doc1",
            song_title="My Composition",
            key="C",
            display_key="E",
            concert_key="E",
            bpm=96,
            style="Auto",
            groove="Auto",
            progression=["C", "Am", "F", "G"],
            progression_label="My Composition",
            bound_pick_key="composition::doc1",
        )
        st = MagicMock()
        render_backing_composition_song_context_card(
            st,
            ctx,
            {"display_key": "E"},
            applied_bpm=96,
            applied_groove="Auto",
        )
        html_out = str(st.markdown.call_args[0][0])
        self.assertIn("ui-source-identity-art source-composition", html_out)
        self.assertIn("#1e293b", html_out)
        self.assertIn("tone-source", html_out)
        self.assertIn("📀", html_out)
        self.assertIn("tone-style", html_out)
        style_chunk = html_out[html_out.find("tone-style") : html_out.find("tone-style") + 260]
        self.assertIn("Auto", style_chunk)
        self.assertNotIn("Composition", style_chunk)


class TestSongsCardIdentity(unittest.TestCase):
    def test_songs_meta_badges_use_shared_source_badge(self) -> None:
        from app_ui import studio_song_meta_badges_html

        custom_html = studio_song_meta_badges_html(
            original_key="D",
            display_key="E",
            bpm=120,
            meter="4/4",
            style="Pop",
            source="Custom progression",
        )
        self.assertIn("tone-source", custom_html)
        self.assertIn("📀", custom_html)
        self.assertIn("Custom progression", custom_html)
        self.assertNotIn("✍️", custom_html)

        comp_html = studio_song_meta_badges_html(
            original_key="C",
            display_key="E",
            bpm=96,
            meter="4/4",
            style="Auto",
            source="Composition",
        )
        self.assertIn("tone-source", comp_html)
        self.assertIn("📀", comp_html)
        self.assertIn("Composition", comp_html)
        style_chunk = comp_html[comp_html.find("tone-style") : comp_html.find("tone-style") + 220]
        self.assertIn("Auto", style_chunk)
        self.assertNotIn("🪶", comp_html)


class TestComposerTransportLifecycle(unittest.TestCase):
    def test_section_transport_does_not_assign_widget_key_after_slider(self) -> None:
        import composition_studio_page as page

        src = inspect.getsource(page._render_section_transport)
        self.assertIn("loops_key not in session_state", src)
        self.assertNotIn('session_state["composer_play_loops"] = loops', src)

    def test_section_transport_render_order_safe_with_prebound_key(self) -> None:
        import composition_studio_page as page

        calls: list[str] = []

        class _Col:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class FakeSt:
            def columns(self, _spec):
                return (_Col(), _Col())

            def slider(self, *args, **kwargs):
                calls.append(f"slider:{kwargs.get('key')}")
                return 3

            def button(self, *args, **kwargs):
                calls.append(f"button:{kwargs.get('key')}")
                return False

            def audio(self, *args, **kwargs):
                return None

            def warning(self, *args, **kwargs):
                return None

        session = {"composer_play_loops": 2}
        original_st = page.st
        page.st = FakeSt()
        try:
            page._render_section_transport(
                session,
                {"id": "doc", "sections": []},
                "sec-1",
                loops_key="composer_play_loops",
            )
        finally:
            page.st = original_st
        self.assertTrue(calls and calls[0].startswith("slider:"))
        # Pre-bound widget key must remain untouched by post-slider assignment.
        self.assertEqual(session.get("composer_play_loops"), 2)


class TestCompositionPracticeKeyPersistence(unittest.TestCase):
    def test_composition_context_keeps_saved_practice_key_e(self) -> None:
        from backing_context import build_composition_song_context
        from composition_songs_bridge import (
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.practice_key_state import set_practice_concert_key

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "C",
        }
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        pick = f"composition::{doc.get('id')}"
        ss["active_catalog_pick_key"] = pick
        set_practice_concert_key(ss, "E", pick_key=pick)
        ss["display_key"] = "E"
        ss["concert_key"] = "E"
        ctx = build_composition_song_context(ss, doc=doc)
        self.assertEqual(ctx.key, "C")
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ctx.display_key, "E")

    def test_restore_seeds_practice_key_before_activate(self) -> None:
        from pathlib import Path

        src = Path("songs/state.py").read_text(encoding="utf-8")
        block_start = src.find('if pick_key.startswith("composition::")')
        block = src[block_start : block_start + 1200]
        seed = block.find("set_practice_concert_key(")
        activate = block.find("ok = activate_composition_by_pick_key(")
        self.assertGreater(seed, 0)
        self.assertGreater(activate, 0)
        self.assertLess(seed, activate)


class TestExplicitSourceSwitchPriority(unittest.TestCase):
    def test_custom_radio_outranks_stale_composition_pick(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_COMPOSITION,
            SOURCE_CUSTOM,
            clear_composition_one_shot_nav_flags,
            composition_song_is_active,
        )

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_catalog_pick_key": "composition::stale-doc",
            "active_song_state": {
                "pick_key": "composition::stale-doc",
                "music_source": SOURCE_COMPOSITION,
            },
            "_force_composition_backing_open": True,
        }
        self.assertFalse(composition_song_is_active(ss))
        clear_composition_one_shot_nav_flags(ss)
        self.assertNotIn("_force_composition_backing_open", ss)

    def test_catalog_choice_outranks_composition_pick(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SOURCE_COMPOSITION,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            composition_song_is_active,
        )

        ss = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::stale-doc",
        }
        self.assertFalse(composition_song_is_active(ss))

    def test_open_backing_respects_explicit_custom_leave(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
        )

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_catalog_pick_key": "composition::stale-doc",
            "active_song_state": {
                "pick_key": "composition::stale-doc",
                "music_source": "composition_song",
            },
            "cpl_active_progression": {
                "name": "Custom Song",
                "id": "cust-1",
                "original_key_center": "G",
                "bpm": 100,
                "original_sections": {"A": [{"chord": "G", "bars": 2}]},
            },
        }
        ctx = open_backing_for_practice_source(
            ss, st_like=SimpleNamespace(session_state=ss)
        )
        self.assertIsNotNone(ctx)
        self.assertNotEqual(getattr(ctx, "source", None), "composition_song")

    def test_open_backing_ignores_stale_force_when_explicit_custom(self) -> None:
        from backing_source_navigation import open_backing_for_practice_source
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CUSTOM,
        )

        ss = {
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial-d",
            "active_song_state": {
                "pick_key": "composition::stale-doc",
                "music_source": "composition_song",
            },
            "_force_composition_backing_open": True,
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-d",
                "original_key_center": "D",
                "bpm": 100,
                "original_sections": {"A": [{"chord": "D", "bars": 2}]},
            },
        }
        ctx = open_backing_for_practice_source(
            ss, st_like=SimpleNamespace(session_state=ss)
        )
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", None), "custom_progression")
        self.assertNotIn("_force_composition_backing_open", ss)

    def test_catalog_radio_outranks_stale_composition_pick_for_hub_nav(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            songs_hub_catalog_backing_selected,
            songs_hub_composition_backing_selected,
        )

        ss = {
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::stale-doc",
        }
        self.assertTrue(songs_hub_catalog_backing_selected(ss))
        self.assertFalse(songs_hub_composition_backing_selected(ss))

    def test_reconcile_does_not_reclaim_composition_when_explicit_catalog(self) -> None:
        from songs.music_source import (
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SOURCE_CATALOG,
            SOURCE_COMPOSITION,
            reconcile_picker_music_source,
        )

        ss = {
            "studio_page": "picker",
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            "active_music_source": SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::stale-doc",
            "active_song_state": {
                "pick_key": "composition::stale-doc",
                "music_source": SOURCE_COMPOSITION,
            },
        }
        reconcile_picker_music_source(ss)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CATALOG)

    def test_picker_snapshot_does_not_restore_stale_source_radio(self) -> None:
        from songs.music_source import (
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_COMPOSITION,
            song_picker_composition_option_label,
        )
        from studio_page_persistence import apply_page_snapshot

        ss = {
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_COMPOSITION,
            "active_music_source": SOURCE_COMPOSITION,
            SONG_PICKER_ACTIVE_SOURCE_KEY: song_picker_composition_option_label(),
            "active_catalog_pick_key": "composition::doc-1",
        }
        apply_page_snapshot(
            ss,
            {
                "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
                "song_picker_level_filter": "Any level",
            },
        )
        self.assertEqual(
            ss[SONG_PICKER_ACTIVE_SOURCE_KEY],
            song_picker_composition_option_label(),
        )
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_COMPOSITION)
        self.assertEqual(ss.get("song_picker_level_filter"), "Any level")


class TestCompositionSidebarPracticeKeyWrite(unittest.TestCase):
    def test_sidebar_composition_practice_key_persists_e(self) -> None:
        from backing_context import build_composition_song_context, set_backing_context
        from composition_songs_bridge import (
            ensure_generic_composition_document,
            set_composition_source,
        )
        from creative_key_sync import sync_sidebar_creative_concert_key
        from songs.practice_key_state import get_practice_concert_key

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "C",
            "concert_key": "C",
        }
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        pick = f"composition::{doc.get('id')}"
        ss["active_catalog_pick_key"] = pick
        ctx = build_composition_song_context(ss, doc=doc)
        set_backing_context(ss, ctx)
        ss["display_key"] = "E"
        sync_sidebar_creative_concert_key(ss, st_like=None)
        self.assertEqual(get_practice_concert_key(ss, pick), "E")
        rebuilt = build_composition_song_context(ss, doc=doc)
        self.assertEqual(rebuilt.key, "C")
        self.assertEqual(rebuilt.concert_key, "E")
        self.assertEqual(rebuilt.display_key, "E")


if __name__ == "__main__":
    unittest.main()

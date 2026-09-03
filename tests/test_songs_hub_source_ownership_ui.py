"""Regression: Songs hub uniqueness, Custom→Composition key ownership, provenance."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock


class TestSongsHubCanonicalActions(unittest.TestCase):
    def test_custom_and_composition_hubs_suppress_card_nav_and_source_edit(self) -> None:
        import streamlit_music_practice_app as app

        comp_src = inspect.getsource(app._render_composition_active_song_hub)
        custom_src = inspect.getsource(app._render_custom_active_song_hub)
        catalog_src = inspect.getsource(app._render_catalog_active_song_hub)
        card_src = inspect.getsource(app._render_active_song_card)
        nav_src = inspect.getsource(app._render_songs_hub_nav_actions)
        label_src = inspect.getsource(app._active_source_edit_button_label)

        self.assertIn('show_nav_actions=False', comp_src)
        self.assertIn('edit_mode="composition"', comp_src)
        self.assertIn('show_nav_actions=False', custom_src)
        self.assertIn('edit_mode="custom"', custom_src)
        self.assertNotIn('key="composition_hub_edit"', comp_src)
        self.assertNotIn('key="custom_hub_edit"', custom_src)
        self.assertIn("Edit custom chart", label_src)
        self.assertIn("Edit composition", label_src)
        self.assertNotIn("Edit composition chart", label_src)
        self.assertIn("show_nav_actions", card_src)
        # Shared five-action row (exactly once per hub via key_prefix).
        self.assertIn("_render_songs_hub_nav_actions", comp_src)
        self.assertIn("_render_songs_hub_nav_actions", custom_src)
        self.assertIn("_render_songs_hub_nav_actions", catalog_src)
        self.assertIn('key_prefix="composition_hub"', comp_src)
        self.assertIn('key_prefix="custom_hub"', custom_src)
        self.assertIn('key_prefix="catalog_hub"', catalog_src)
        self.assertIn("show_nav_actions=False", catalog_src)
        for suffix in ("_practice", "_backing", "_creative", "_karaoke", "_chord_coach"):
            self.assertIn(f"{{key_prefix}}{suffix}", nav_src)
        self.assertIn('nav_icon_button_label("creative")', nav_src)
        self.assertIn('feature_label("karaoke"', nav_src)
        self.assertIn('feature_label("chord_song_coach"', nav_src)


class TestCustomEbDoesNotLeakIntoComposition(unittest.TestCase):
    def test_custom_eb_then_composition_resolves_to_c(self) -> None:
        from backing_context import build_composition_song_context
        from composition_songs_bridge import (
            commit_composition_active_song,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from creative_key_sync import prepare_backing_context_sidebar_display_key
        from songs.practice_key_state import set_practice_concert_key

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "Eb",
            "concert_key": "Eb",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": "custom::trial",
            "cpl_active_progression": {
                "name": "Trial",
                "id": "trial-eb",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            },
        }
        set_practice_concert_key(ss, "Eb", pick_key="custom::trial")
        self.assertEqual(ss.get("display_key"), "Eb")

        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        ctx = build_composition_song_context(ss)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ctx.key, "C")
        self.assertEqual(ctx.concert_key, "C")
        self.assertEqual(ss.get("display_key"), "C")
        self.assertEqual(ss.get("concert_key"), "C")

        options = prepare_backing_context_sidebar_display_key(st, ss)
        self.assertTrue(any("C" == str(o).split()[0] or str(o).startswith("C") for o in options) or "C" in options)
        # Authoritative live keys must stay Composition C, not Custom Eb.
        self.assertNotIn(ss.get("display_key"), {"Eb", "E♭", "Eb major"})
        self.assertEqual(str(ss.get("display_key") or "")[:1], "C")


class TestCompositionEnsureSurvivesCustomPick(unittest.TestCase):
    def test_ensure_replaces_custom_pick_even_if_identity_hydration_fails(self) -> None:
        from songs.music_source import ensure_composition_owns_active_song
        from unittest.mock import patch

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "Eb",
            "concert_key": "Eb",
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": "custom::My Progression",
            # on_change Composition updates the widget before ensure runs.
            "song_picker_active_source": "🪶 Composition",
            "_streamlit_widgets_locked_this_run": True,
            "cpl_active_progression": {
                "name": "My Progression",
                "id": "my-prog",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            },
        }
        st = MagicMock()
        st.session_state = ss

        def _boom(*_a, **_k):
            raise RuntimeError("simulated identity hydrate failure")

        with patch(
            "songs.music_source.on_active_song_identity_changed",
            side_effect=_boom,
        ):
            # Import path uses songs.music_source → composition_songs_bridge.commit
            doc = ensure_composition_owns_active_song(
                st, invalidate_backing=lambda _st: None
            )
        self.assertIsInstance(doc, dict)
        pick = str(ss.get("active_catalog_pick_key") or "")
        self.assertTrue(pick.startswith("composition::"), pick)
        self.assertEqual(ss.get("active_music_source"), "composition_song")


class TestCompositionPracticeKeyPersistsAcrossRebuild(unittest.TestCase):
    def test_saved_composition_e_survives_rebuild(self) -> None:
        from backing_context import build_composition_song_context
        from composition_songs_bridge import (
            commit_composition_active_song,
            composition_pick_key_for,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.practice_key_state import set_practice_concert_key

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
        pick = composition_pick_key_for(doc)
        set_practice_concert_key(ss, "E", pick_key=pick)
        ctx = build_composition_song_context(ss)
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ss.get("display_key"), "E")
        # Simulate leftover Custom live key after a prior session — must not win.
        ss["display_key"] = "Eb"
        ss["concert_key"] = "Eb"
        ctx2 = build_composition_song_context(ss)
        self.assertEqual(ctx2.concert_key, "E")
        self.assertEqual(ss.get("display_key"), "E")


class TestBackingProvenance(unittest.TestCase):
    def test_songs_provenance_not_creative(self) -> None:
        from backing_source_navigation import (
            BACKING_PROVENANCE_CREATIVE,
            BACKING_PROVENANCE_SONGS,
            backing_opened_from_creative,
            peek_backing_open_provenance,
            return_to_source_button_label,
            set_backing_open_provenance,
            target_page_for_backing_context,
        )
        from backing_context import BackingContext

        ss: dict = {}
        set_backing_open_provenance(ss, BACKING_PROVENANCE_SONGS)
        self.assertEqual(peek_backing_open_provenance(ss), BACKING_PROVENANCE_SONGS)
        self.assertFalse(backing_opened_from_creative(ss))

        set_backing_open_provenance(ss, BACKING_PROVENANCE_CREATIVE)
        self.assertTrue(backing_opened_from_creative(ss))

        ctx = BackingContext(
            source="composition_song",
            source_label="Composition",
            active_song_id="composition::x",
            song_title="My Composition",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=96,
            style="Auto",
            groove="Auto",
            scope="Full song",
            loops=2,
            progression=["C", "Am", "F", "G"],
            progression_label="My Composition",
            loop=True,
        )
        self.assertEqual(target_page_for_backing_context(ctx), "composer")
        label = return_to_source_button_label(ctx)
        self.assertIn("Composition", label)
        self.assertNotIn("Creative", label)


class TestBackingCardBadgesAndProjection(unittest.TestCase):
    def test_custom_card_has_separate_source_and_style_badges(self) -> None:
        from backing_context import build_custom_progression_context, set_backing_context
        from backing_context_ui import render_backing_custom_progression_context_card

        session = {
            "cpl_active_progression": {
                "name": "Trial Song",
                "id": "trial-style-1",
                "original_key_center": "D",
                "bpm": 120,
                "progression_style": "Pop",
                "original_sections": {
                    "Verse": [{"chord": "Dm7", "bars": 2}, {"chord": "G7", "bars": 2}],
                },
            },
            "active_music_source": "custom_progression",
            "instrument": "Piano",
        }
        ctx = build_custom_progression_context(session)
        set_backing_context(session, ctx)
        st = MagicMock()
        render_backing_custom_progression_context_card(
            st, ctx, session, applied_bpm=120, applied_groove="Pop groove", practice_key="D"
        )
        html_out = str(st.markdown.call_args[0][0])
        self.assertIn("tone-source", html_out)
        self.assertIn("tone-style", html_out)
        self.assertIn("Custom progression", html_out)
        self.assertIn("📀", html_out)
        self.assertIn("✨", html_out)

    def test_composition_card_uses_state_practice_key_not_stale_live(self) -> None:
        from backing_context import build_composition_song_context, set_backing_context
        from backing_context_ui import render_backing_composition_song_context_card
        from composition_songs_bridge import (
            commit_composition_active_song,
            composition_pick_key_for,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.practice_key_state import set_practice_concert_key

        ss: dict = {"instrument": "Piano", "composer_saved_compositions": {}, "display_key": "C"}
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _st: None)
        set_practice_concert_key(ss, "E", pick_key=composition_pick_key_for(doc))
        ctx = build_composition_song_context(ss)
        set_backing_context(ss, ctx)
        st_ui = MagicMock()
        render_backing_composition_song_context_card(
            st_ui, ctx, ss, applied_bpm=96, applied_groove="Auto", practice_key="E"
        )
        html_out = str(st_ui.markdown.call_args[0][0])
        self.assertIn("E", html_out)
        self.assertIn("tone-source", html_out)
        self.assertIn("tone-style", html_out)
        self.assertIn("Composition", html_out)
        self.assertIn("ui-backing-badge practice-key", html_out)
        self.assertIn("ui-backing-badge bpm", html_out)
        self.assertIn("ui-backing-badge meter", html_out)


class TestExplicitSourceSwitchResetsPracticeKey(unittest.TestCase):
    """Same-source persistence vs explicit switch → original key."""

    def test_composition_same_source_keeps_e_then_switch_to_custom_resets(self) -> None:
        from composition_songs_bridge import (
            commit_composition_active_song,
            composition_home_key,
            composition_pick_key_for,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import commit_custom_active_song, ensure_composition_owns_active_song
        from songs.practice_key_state import (
            get_practice_concert_key,
            set_practice_concert_key,
        )

        ss: dict = {
            "instrument": "Piano",
            "composer_saved_compositions": {},
            "display_key": "C",
            CPL_ACTIVE_KEY: {
                "name": "Trial Song",
                "id": "trial-d",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
            },
        }
        st = MagicMock()
        st.session_state = ss
        set_composition_source(ss)
        doc = ensure_generic_composition_document(ss)
        commit_composition_active_song(st, doc, invalidate_backing=lambda _s: None)
        pick = composition_pick_key_for(doc)
        home = composition_home_key(doc)
        self.assertEqual(home, "C")
        set_practice_concert_key(ss, "E", pick_key=pick)
        ss["display_key"] = "E"
        ss["concert_key"] = "E"
        # Same-source re-ensure must preserve E.
        ensure_composition_owns_active_song(st, invalidate_backing=lambda _s: None)
        self.assertEqual(get_practice_concert_key(ss, pick), "E")
        self.assertEqual(str(ss.get("display_key") or "")[:1], "E")

        # Explicit switch to Custom → Trial Song original D (not prior F).
        from songs.music_source import custom_pick_key_for

        custom_pick = custom_pick_key_for(ss[CPL_ACTIVE_KEY])
        set_practice_concert_key(ss, "F", pick_key=custom_pick)
        commit_custom_active_song(
            st,
            ss[CPL_ACTIVE_KEY],
            invalidate_backing=lambda _s: None,
            reset_practice_to_original=True,
        )
        self.assertEqual(str(ss.get("display_key") or "")[:1], "D")
        self.assertEqual(get_practice_concert_key(ss, custom_pick), "")

        # Explicit switch back to Composition → original C, not E.
        # on_change Composition updates the widget before ensure runs.
        from songs.music_source import song_picker_composition_option_label

        ss["song_picker_active_source"] = song_picker_composition_option_label()
        ss["active_catalog_pick_key"] = custom_pick
        ss["_composition_reset_practice_on_ensure"] = True
        ensure_composition_owns_active_song(st, invalidate_backing=lambda _s: None)
        self.assertEqual(str(ss.get("display_key") or "")[:1], "C")
        self.assertEqual(get_practice_concert_key(ss, pick), "")

    def test_activate_empty_prior_preserves_seeded_practice_key(self) -> None:
        """Disk restore seeds E then activate with empty prior — must not wipe."""
        from composition_songs_bridge import (
            activate_composition_by_pick_key,
            composition_home_key,
            composition_pick_key_for,
            ensure_generic_composition_document,
            set_composition_source,
        )
        from songs.practice_key_state import (
            get_practice_concert_key,
            set_practice_concert_key,
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
        pick = composition_pick_key_for(doc)
        self.assertEqual(composition_home_key(doc), "C")
        # Simulate restore: seed store before activate; pick not yet stamped.
        ss.pop("active_catalog_pick_key", None)
        set_practice_concert_key(ss, "E", pick_key=pick)
        ok = activate_composition_by_pick_key(st, pick, invalidate_backing=lambda _s: None)
        self.assertTrue(ok)
        self.assertEqual(get_practice_concert_key(ss, pick), "E")
        self.assertEqual(str(ss.get("display_key") or "")[:1], "E")

        # Same-pick re-activate must also preserve E.
        ok2 = activate_composition_by_pick_key(st, pick, invalidate_backing=lambda _s: None)
        self.assertTrue(ok2)
        self.assertEqual(get_practice_concert_key(ss, pick), "E")


if __name__ == "__main__":
    unittest.main()

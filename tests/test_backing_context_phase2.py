"""Phase 2 tests — Creative handoff wiring for backing_context."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    PENDING_BACKING_CONTEXT_APPLY,
    apply_backing_context_to_session,
    build_entry_jam_context,
    build_mission_context,
    compute_source_signature,
    format_backing_context_banner,
    get_backing_context,
    invalidate_if_song_changed,
    open_backing_from_creative,
    restore_regular_song_backing,
)
from custom_progression_lab import PENDING_BACKING_LOOPS, PENDING_BACKING_SCOPE
from songs.bpm_state import PENDING_BACKING_TRACK_BPM
from songs.key_state import PENDING_DISPLAY_KEY
from songs.playback_defaults import PENDING_BACKING_GROOVE


class TestBackingContextPhase2(unittest.TestCase):
    def test_apply_entry_jam_sets_bpm_and_scope(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style": "Jazz Swing",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "G",
        }
        ctx = build_entry_jam_context(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=False)
        self.assertEqual(session.get("backing_track_bpm"), 90)
        self.assertEqual(session.get("backing_groove_style"), "Jazz swing")

    def test_widget_safe_handoff_queues_pending_keys(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "F",
            "concert_key": "F",
            "improv_style": "Jazz Swing",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 90, "groove": "Medium"},
            "improv_style_key": "G",
        }
        ctx = build_entry_jam_context(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
        self.assertNotIn(PENDING_DISPLAY_KEY, session)
        self.assertEqual(session.get(PENDING_BACKING_TRACK_BPM), 90)
        self.assertEqual(session.get(PENDING_BACKING_GROOVE), "Jazz swing")
        self.assertEqual(session.get(PENDING_BACKING_LOOPS), 2)
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Full song")
        self.assertTrue(session.get(PENDING_BACKING_CONTEXT_APPLY))
        self.assertNotIn("backing_track_bpm", session)

    def test_open_backing_from_mission(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_active_mission": "ii–V–I drill",
            "improv_intelligence_tab": "Missions",
            "improv_mission_progression": ["Dm7", "G7", "Cmaj7"],
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = open_backing_from_creative(session, source="mission", st_like=st_like)
        self.assertEqual(ctx.source, "mission")
        self.assertEqual(get_backing_context(session).mission_id, "ii–V–I drill")

    def test_reopen_updates_signature_when_bpm_changes(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style_meta": {"bpm": 82, "groove": "Medium"},
        }
        ctx1 = build_entry_jam_context(session)
        session["improv_style_meta"] = {"bpm": 95, "groove": "Medium"}
        ctx2 = build_entry_jam_context(session)
        self.assertNotEqual(compute_source_signature(ctx1), compute_source_signature(ctx2))

    def test_restore_regular_song_clears_creative_source(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "backing_track_bpm": 90,
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 90,
                "style": "Jazz",
                "groove": "Medium",
                "bound_pick_key": "say|artist",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(get_backing_context(session).source, "regular_song")

    def test_reconcile_does_not_rebuild_creative_after_catalog_switch(self) -> None:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_SOURCE_PREFERENCE_KEY,
            reconcile_backing_context_on_backing_page,
        )

        session = {
            "active_catalog_pick_key": "Pop::Shape of You",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": "Pop::Shape of You"},
            "display_key": "Bm",
            "improv_entry_mode": "Style Jam Mode",
            "improv_generated_sections": {"12-bar blues": ["G7", "C7", "D7"]},
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "G",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "source_label": "Catalog song",
                "active_song_id": "Pop::Shape of You",
                "song_title": "Shape of You",
                "key": "Bm",
                "display_key": "Bm",
                "concert_key": "Bm",
                "bpm": 96,
                "progression": [],
            },
            BACKING_SOURCE_PREFERENCE_KEY: BACKING_PREF_CATALOG,
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.progression, [])

    def test_entry_jam_survives_when_song_unchanged(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "Jazz",
                "groove": "Medium",
                "bound_pick_key": "say|artist",
            },
        }
        self.assertFalse(invalidate_if_song_changed(session))
        self.assertIsNotNone(get_backing_context(session))

    def test_mission_context_survives_active_song_change(self) -> None:
        session = {
            "active_catalog_pick_key": "daughters|artist",
            BACKING_CONTEXT_KEY: {
                "source": "mission",
                "source_label": "Mission",
                "active_song_id": "say|artist",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "",
                "groove": "Pop groove",
                "mission_id": "ii–V–I drill",
                "bound_pick_key": "say|artist",
            },
        }
        self.assertTrue(invalidate_if_song_changed(session))
        reset_ctx = get_backing_context(session)
        self.assertIsNotNone(reset_ctx)
        assert reset_ctx is not None
        self.assertEqual(reset_ctx.source, "regular_song")

    def test_custom_progression_invalidates_on_song_change(self) -> None:
        session = {
            "active_catalog_pick_key": "daughters|artist",
            BACKING_CONTEXT_KEY: {
                "source": "custom_progression",
                "source_label": "Custom progression",
                "active_song_id": "custom-rev-1",
                "song_title": "My progression",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 82,
                "style": "",
                "groove": "Pop groove",
                "bound_pick_key": "say|artist",
                "custom_revision_id": "custom-rev-1",
            },
        }
        self.assertTrue(invalidate_if_song_changed(session))
        reset_ctx = get_backing_context(session)
        self.assertIsNotNone(reset_ctx)
        assert reset_ctx is not None
        self.assertEqual(reset_ctx.source, "regular_song")

    def test_banner_entry_jam(self) -> None:
        ctx = build_entry_jam_context(
            {
                "active_catalog_pick_key": "say|artist",
                "song": "Say",
                "display_key": "G",
                "improv_style_meta": {"bpm": 82, "groove": "Medium"},
            }
        )
        banner = format_backing_context_banner(ctx)
        self.assertIn("Entry & Jam", banner)
        self.assertIn("Concert G", banner)
        self.assertIn("82 BPM", banner)

    def test_reconcile_does_not_queue_rerun(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, reconcile_backing_context_on_backing_page

        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "F",
            "concert_key": "F",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_key": "F",
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 110, "groove": "Jazz swing"},
            "improv_generated_sections": {"Head (Jazz Swing)": ["Dm7", "G7", "Cmaj7"]},
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say|artist",
                "song_title": "Jazz Swing",
                "key": "F",
                "display_key": "F",
                "concert_key": "F",
                "bpm": 110,
                "style": "Jazz Swing",
                "groove": "Jazz swing",
                "bound_pick_key": "say|artist",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        self.assertEqual(session.get("backing_track_bpm"), 110)
        self.assertNotIn(PENDING_BACKING_CONTEXT_APPLY, session)


class TestCatalogCreativeOwnershipP0(unittest.TestCase):
    def test_ensure_backing_context_does_not_overwrite_regular_song(self) -> None:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_SOURCE_PREFERENCE_KEY,
            ensure_backing_context_from_creative_session,
        )

        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_generated_sections": {"12-bar blues": ["G7", "C7", "D7"]},
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "F",
                "style": "Blues",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "source_label": "Catalog song",
                "active_song_id": "photo|artist",
                "song_title": "Photograph",
                "key": "E",
                "display_key": "E",
                "concert_key": "E",
                "bpm": 76,
                "progression": ["E", "B", "C#m", "A"],
            },
            BACKING_SOURCE_PREFERENCE_KEY: BACKING_PREF_CATALOG,
        }
        ctx = ensure_backing_context_from_creative_session(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.song_title, "Photograph")
        self.assertEqual(ctx.concert_key, "E")

    def test_hydrate_after_restore_skips_when_catalog_active(self) -> None:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_SOURCE_PREFERENCE_KEY,
            hydrate_backing_context_after_restore,
        )

        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_generated_sections": {"12-bar blues": ["G7", "C7", "D7"]},
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "F",
                "style": "Blues",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "source_label": "Catalog song",
                "active_song_id": "Pop::Shape of You",
                "song_title": "Shape of You",
                "key": "Bm",
                "display_key": "Bm",
                "concert_key": "Bm",
                "bpm": 96,
                "progression": [],
            },
            BACKING_SOURCE_PREFERENCE_KEY: BACKING_PREF_CATALOG,
        }
        hydrate_backing_context_after_restore(session)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.song_title, "Shape of You")
        self.assertNotEqual(ctx.style, "Blues")

    def test_restore_catalog_clears_live_creative_keys_preserves_blob(self) -> None:
        from creative_session_state import creative_session_is_active, get_creative_session

        session = {
            "active_catalog_pick_key": "photo|artist",
            "selected_song": {"title": "Photograph", "key": "E", "pick_key": "photo|artist"},
            "song": "Photograph",
            "display_key": "F",
            "concert_key": "F",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Blues",
            "improv_style_key": "F",
            "improv_generated_sections": {"12-bar blues": ["G7", "C7", "D7"]},
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "F",
                "style": "Blues",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "photo|artist",
                "song_title": "Photograph",
                "key": "F",
                "display_key": "F",
                "concert_key": "F",
                "bpm": 70,
                "style": "Blues",
                "groove": "Medium",
            },
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("concert_key"), "E")
        self.assertEqual(session.get("display_key"), "E")
        self.assertNotIn("improv_generated_sections", session)
        self.assertNotIn("improv_entry_mode", session)
        self.assertIsNotNone(get_creative_session(session))
        self.assertFalse(creative_session_is_active(session))


class TestCatalogCustomBackingResolution(unittest.TestCase):
    def test_resolve_last_catalog_pick_skips_custom(self) -> None:
        from songs.music_source import LAST_CATALOG_STATE_KEY, resolve_last_catalog_pick_key

        session = {
            "active_catalog_pick_key": "custom::trial",
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "Pop::Photograph",
                "selected_song": {"title": "Photograph", "key": "E"},
                "original_key": "E",
            },
        }
        self.assertEqual(resolve_last_catalog_pick_key(session), "Pop::Photograph")

    def test_restore_catalog_uses_last_catalog_not_custom(self) -> None:
        from songs.music_source import LAST_CATALOG_STATE_KEY

        session = {
            "active_catalog_pick_key": "custom::trial",
            "selected_song": {"title": "trial song", "key": "C", "pick_key": "custom::trial"},
            "song": "trial song",
            "display_key": "F",
            "concert_key": "F",
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "Pop::Photograph",
                "selected_song": {"title": "Photograph", "key": "E", "pick_key": "Pop::Photograph"},
                "original_key": "E",
                "display_key": "E",
            },
            "improv_generated_sections": {"12-bar blues": ["G7"]},
        }
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("active_catalog_pick_key"), "Pop::Photograph")
        self.assertEqual(session.get("concert_key"), "E")


class TestReturnToCreativeToolRestore(unittest.TestCase):
    def test_return_from_entry_jam_restores_jam_session_generator(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_entry_jam_context
        from backing_source_navigation import prepare_return_to_backing_source

        session = {
            "improv_entry_mode": "Style Jam Mode",
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "G",
                "style": "Blues",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
        }
        ctx = build_entry_jam_context(
            {
                **session,
                "improv_entry_mode": "Jam Session Generator",
                "improv_jam_style": "Blues",
                "improv_jam_key": "F",
                "improv_jam_bpm": 70,
                "improv_jam_mood": "Mellow",
                "improv_jam_session": {
                    "title": "Jam",
                    "sections": {"Blues (Jam)": ["F7", "Bb7", "C7"]},
                },
            }
        )
        ctx.entry_mode = "Jam Session Generator"
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        page = prepare_return_to_backing_source(session)
        self.assertEqual(page, "creative")
        self.assertEqual(session.get("improv_entry_mode"), "Jam Session Generator")
        self.assertEqual(session.get("improv_jam_key"), ctx.concert_key)

    def test_return_from_song_improv_restores_song_based_mode(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_song_improv_context
        from backing_source_navigation import prepare_return_to_backing_source

        session = {
            "improv_entry_mode": "Style Jam Mode",
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
        }
        ctx = build_song_improv_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        page = prepare_return_to_backing_source(session)
        self.assertEqual(page, "creative")
        self.assertEqual(session.get("improv_entry_mode"), "Song-Based Improvisation")


class TestSongImprovCustomProgression(unittest.TestCase):
    def test_song_improv_custom_uses_trial_song_not_catalog(self) -> None:
        from backing_context import build_song_improv_context
        from studio_page_state import CREATIVE_BACKING_SONG_SOURCE_KEY

        session = {
            "active_catalog_pick_key": "Pop::Photograph",
            "selected_song": {"title": "Photograph", "key": "E", "pick_key": "Pop::Photograph"},
            "song": "Photograph",
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Custom progression",
            "improv_song_source": "Custom progression",
            "improv_entry_mode": "Song-Based Improvisation",
            "cpl_active_progression": {
                "id": "custom-rev-trial",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [{"chord": "D", "bars": 1}, {"chord": "G", "bars": 1}, {"chord": "A", "bars": 1}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
                "bpm": 90,
            },
        }
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertNotEqual(ctx.song_title, "Photograph")
        self.assertEqual(ctx.bound_pick_key, "custom::custom-rev-trial")


class TestDisplayKeyWidgetSafe(unittest.TestCase):
    def test_apply_display_key_after_widget_exists_uses_pending(self) -> None:
        from songs.key_state import apply_display_key_for_active_song, song_display_identity

        class _FakeSt:
            session_state: dict

        st = _FakeSt()
        st.session_state = {
            "display_key": "Bm",
            "_music_restore_phase_complete": True,
        }
        identity = song_display_identity("Say", "John Mayer", "G", pick_key="Pop::Say")
        apply_display_key_for_active_song(st, "G", identity, pending_key="G")
        self.assertEqual(st.session_state.get("display_key"), "Bm")
        self.assertEqual(st.session_state.get("_pending_display_key"), "G")


if __name__ == "__main__":
    unittest.main()

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
        # Pass 8: widget-safe still mirrors live BPM for same-rerun Backing transport.
        self.assertEqual(session.get("backing_track_bpm"), 90)

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

    def test_reopen_signature_stable_when_bpm_changes(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_style_meta": {"bpm": 82, "groove": "Medium"},
            "improv_mood": "Bright",
            "improv_difficulty": "Intermediate",
            "improv_entry_mode": "Style Jam Mode",
        }
        ctx1 = build_entry_jam_context(session)
        session["improv_style_meta"] = {"bpm": 95, "groove": "Medium"}
        ctx2 = build_entry_jam_context(session)
        self.assertEqual(compute_source_signature(ctx1), compute_source_signature(ctx2))

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
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_PREF_CREATIVE,
            reconcile_backing_context_on_backing_page,
            set_backing_source_preference,
        )

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
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
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

    def test_restore_catalog_uses_before_custom_snapshot(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY, resolve_catalog_pick_for_backing_restore

        shape_pick = format_pick_key("Pop", "Shape of You")
        session = {
            "active_catalog_pick_key": "custom::trial",
            "selected_song": {"title": "trial song", "key": "C", "pick_key": "custom::trial"},
            "song": "trial song",
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape_pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape_pick,
                    "bpm": 96,
                },
                "original_key": "Bm",
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "Pop::Photograph",
                "selected_song": {"title": "Photograph", "key": "E"},
                "original_key": "E",
            },
        }
        self.assertEqual(resolve_catalog_pick_for_backing_restore(session), shape_pick)

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
        self.assertFalse(str(session.get("active_catalog_pick_key") or "").startswith("custom::"))
        self.assertEqual(session.get("concert_key"), "E")
        self.assertEqual(session.get("song"), "Photograph")
        self.assertEqual(ctx.song_title, "Photograph")
        self.assertNotEqual(ctx.groove, "Bossa")


class TestCustomProgressionConcertKey(unittest.TestCase):
    def _trial_session(self, *, display_key: str = "D") -> dict:
        from custom_progression_lab import CPL_ACTIVE_KEY

        return {
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "user_locked_home_key": True,
                "bpm": 120,
                "progression_style": "Bossa",
                "groove_style": "Bossa",
                "original_sections": {
                    "Verse": [
                        {"chord": "D", "bars": 4},
                        {"chord": "A", "bars": 2},
                    ],
                },
            },
            "display_key": display_key,
            "concert_key": display_key,
        }

    def test_build_custom_context_transposes_progression_to_practice_key(self) -> None:
        from backing_context import build_custom_progression_context

        ctx = build_custom_progression_context(self._trial_session(display_key="E"))
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ctx.key, "D")
        self.assertEqual(ctx.progression, ["E", "E", "E", "E", "B", "B"])

    def test_resolve_musical_state_uses_transposed_custom_sections(self) -> None:
        from backing_context import build_custom_progression_context, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state

        session = self._trial_session(display_key="E")
        set_backing_context(session, build_custom_progression_context(session))
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "E")
        flat = list(state.concert_sections.get("Verse") or [])
        self.assertEqual(flat, ["E", "E", "E", "E", "B", "B"])

    def test_reconcile_custom_does_not_reset_sidebar_practice_key(self) -> None:
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_PREF_CUSTOM,
            BACKING_SOURCE_PREFERENCE_KEY,
            build_custom_progression_context,
            reconcile_backing_context_on_backing_page,
            set_backing_source_preference,
        )

        session = self._trial_session(display_key="E")
        stale = build_custom_progression_context(self._trial_session(display_key="D"))
        session[BACKING_CONTEXT_KEY] = stale.to_dict()
        set_backing_source_preference(session, BACKING_PREF_CUSTOM)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get("concert_key"), "E")

    def test_live_backing_concert_keys_custom_ignores_stale_creative_entry(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, _live_backing_concert_keys, build_custom_progression_context, set_backing_context

        session = self._trial_session(display_key="D")
        session["improv_jam_key"] = "C"
        session["creative_session"] = {"concert_key": "C", "display_key": "C"}
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        set_backing_context(session, ctx)
        _, _, practice = _live_backing_concert_keys(session)
        self.assertEqual(practice, "D")

    def test_sync_sidebar_custom_key_change_updates_backing(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, get_backing_context, set_backing_context
        from creative_key_sync import sync_sidebar_creative_concert_key
        from custom_progression_lab import CPL_LAST_DISPLAY_KEY

        session = self._trial_session(display_key="D")
        session[CPL_LAST_DISPLAY_KEY] = "D"
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        set_backing_context(session, ctx)
        session["display_key"] = "E"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("concert_key"), "E")
        self.assertEqual(
            session.get("practice_key_by_source", {}).get("custom::trial-1"),
            "E",
        )
        refreshed = get_backing_context(session)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.concert_key, "E")
        self.assertEqual(refreshed.progression[:4], ["E", "E", "E", "E"])

    def test_prepare_custom_sidebar_display_key_prefers_live_over_creative_session(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, set_backing_context
        from creative_key_sync import prepare_backing_context_sidebar_display_key
        from creative_session_state import CreativeSession, set_creative_session

        session = self._trial_session(display_key="E")
        session["concert_key"] = "E"
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        set_backing_context(session, ctx)
        set_creative_session(
            session,
            CreativeSession(
                session_id="",
                tool_type="song_based_improvisation",
                entry_mode="Song-Based Improvisation",
                concert_key="C",
                display_key="C",
                sections={"Verse": ["C"]},
            ),
        )
        st = SimpleNamespace(session_state=session)
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertIn("E", options)

    def test_backing_page_transport_defaults_uses_ctx_bpm_when_canonical_stale(self) -> None:
        from backing_context import BackingContext, BACKING_CONTEXT_KEY, backing_page_transport_defaults

        session = {
            "active_catalog_pick_key": "Pop::In My Life",
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": "Pop::In My Life", "bpm": 100},
            "backing_track_state": {"backing_track_bpm": 35},
            BACKING_CONTEXT_KEY: BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id="Pop::In My Life",
                bound_pick_key="Pop::In My Life",
                song_title="In My Life",
                key="A",
                display_key="A",
                concert_key="A",
                bpm=100,
                style="",
                groove="Pop groove",
            ).to_dict(),
        }
        bpm, _groove, _meter = backing_page_transport_defaults(session)
        self.assertEqual(bpm, 100)

    def test_mission_backing_preserves_user_bpm_on_refresh(self) -> None:
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_CTX_TRANSPORT_APPLIED_SIG,
            BackingContext,
            backing_page_transport_defaults,
            build_mission_context,
        )

        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="Pop::Say",
            bound_pick_key="Pop::Say",
            song_title="Say",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=82,
            style="Pop",
            groove="Pop groove",
            mission_id="chord_tones",
            progression=["C"],
            section="Verse",
        )
        session = {
            "improv_active_mission": "chord_tones",
            "ii_selected_chord_index": 0,
            "improv_mission_chord_options": ["C"],
            "backing_track_bpm": 95,
            BACKING_CONTEXT_KEY: ctx.to_dict(),
            BACKING_CTX_TRANSPORT_APPLIED_SIG: ctx.source_signature,
        }
        bpm, _g, _m = backing_page_transport_defaults(session)
        self.assertEqual(bpm, 95)
        rebuilt = build_mission_context(session)
        # Pass 8: live Mission override stays on session transport; rebuild may
        # reseal a catalog/default BPM while widgets keep reading live 95.
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 95)
        self.assertEqual(backing_page_transport_defaults(session)[0], 95)
        self.assertEqual(rebuilt.source, "mission")

    def test_custom_to_catalog_restore_uses_catalog_before_custom(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, restore_regular_song_backing
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY

        photo_pick = "photo|artist"
        say_pick = "say|artist"
        session = self._trial_session(display_key="D")
        session.update(
            {
                "active_catalog_pick_key": "custom::trial-1",
                "active_music_source": "custom_progression",
                "user_catalog_source_choice": True,
                CATALOG_BEFORE_CUSTOM_KEY: {
                    "pick_key": photo_pick,
                    "selected_song": {"title": "Photograph", "key": "E", "pick_key": photo_pick, "bpm": 108},
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": say_pick,
                    "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick, "bpm": 98},
                },
            }
        )
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            restored = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(restored.source, "regular_song")
        self.assertEqual(restored.song_title, "Photograph")
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get("catalog_restore_pick_source"), "catalog_before_custom")

    def test_switch_to_catalog_backing_prefers_catalog_before_creative_over_stale_custom(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, restore_regular_song_backing
        from song_catalog.catalog import format_pick_key
        from songs.music_source import (
            CATALOG_BEFORE_CREATIVE_KEY,
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            resolve_catalog_pick_for_backing_restore_with_source,
        )

        in_my_life_pick = format_pick_key("Pop", "In My Life")
        say_pick = format_pick_key("Pop", "Say")
        session = self._trial_session(display_key="D")
        session.update(
            {
                "active_catalog_pick_key": "custom::trial-1",
                "active_music_source": "custom_progression",
                CATALOG_BEFORE_CREATIVE_KEY: {
                    "pick_key": in_my_life_pick,
                    "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick, "bpm": 100},
                    "original_key": "A",
                    "display_key": "A",
                },
                CATALOG_BEFORE_CUSTOM_KEY: {
                    "pick_key": say_pick,
                    "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick, "bpm": 82},
                    "original_key": "G",
                    "display_key": "G",
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": say_pick,
                    "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick, "bpm": 82},
                    "original_key": "G",
                    "display_key": "G",
                },
            }
        )
        pick, source = resolve_catalog_pick_for_backing_restore_with_source(
            session,
            reason="switch_to_catalog_backing",
        )
        self.assertEqual(pick, in_my_life_pick)
        self.assertEqual(source, "catalog_before_creative")
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            restored = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(restored.song_title, "In My Life")
        self.assertEqual(session.get("catalog_restore_pick_source"), "catalog_before_creative")

    def test_prepare_custom_sidebar_does_not_clobber_live_display_key(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, set_backing_context
        from creative_key_sync import prepare_backing_context_sidebar_display_key

        session = self._trial_session(display_key="E")
        stale = build_custom_progression_context(self._trial_session(display_key="D"))
        session[BACKING_CONTEXT_KEY] = stale.to_dict()
        set_backing_context(session, stale)
        st = SimpleNamespace(session_state=session)
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get("concert_key"), "E")
        self.assertIn("E", options)

    def test_picker_hydrate_resets_stale_leaked_key_for_trial_song(self) -> None:
        from backing_source_navigation import hydrate_picker_source_for_page
        from custom_progression_lab import CPL_ACTIVE_KEY, CPL_LAST_DISPLAY_KEY
        from songs.music_source import active_song_key_pair

        session = self._trial_session(display_key="C")
        session.update(
            {
                "studio_page": "picker",
                CPL_ACTIVE_KEY: session[CPL_ACTIVE_KEY],
                CPL_LAST_DISPLAY_KEY: "D",
                "active_catalog_pick_key": "custom::trial-1",
                "active_music_source": "custom_progression",
                "improv_jam_key": "C",
            }
        )
        hydrate_picker_source_for_page(session)
        original, practice = active_song_key_pair(session, {"key": "D"})
        self.assertEqual(original, "D")
        self.assertEqual(practice, "D")

    def test_catalog_restore_survives_stale_dropdown_reconcile(self) -> None:
        from active_song_state import mark_active_song_local_edit, prepare_active_song_context
        from backing_context import BACKING_CONTEXT_KEY, build_custom_progression_context, restore_regular_song_backing
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, LAST_CATALOG_STATE_KEY
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        shape_pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm", "bpm": 96},
                "Say — John Mayer": {"title": "Say", "artist": "John Mayer", "key": "G", "bpm": 82},
            },
        }
        session = self._trial_session(display_key="D")
        session.update(
            {
                "active_catalog_pick_key": "custom::trial-1",
                "active_music_source": "custom_progression",
                "user_catalog_source_choice": True,
                "matching_song_dropdown": say_pick,
                CATALOG_BEFORE_CUSTOM_KEY: {
                    "pick_key": shape_pick,
                    "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape_pick, "bpm": 96},
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": say_pick,
                    "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick, "bpm": 82},
                },
                "_reconcile_song_picker_catalog": catalog,
            }
        )
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        mark_active_song_local_edit(session)
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            restored = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(restored.song_title, "Shape of You")
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), shape_pick)
        prepare_active_song_context(session)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), shape_pick)
        self.assertEqual(session.get("song"), "Shape of You")
        refreshed = get_backing_context(session)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.song_title, "Shape of You")
        self.assertEqual(str(refreshed.bound_pick_key or ""), shape_pick)


class TestResetBackingOnSongChange(unittest.TestCase):
    def test_catalog_pick_wins_over_custom_session_flags(self) -> None:
        from backing_context import reset_backing_on_active_song_change
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        session = {
            CPL_ACTIVE_KEY: {"id": "trial-1", "name": "Trial Song", "original_key_center": "D"},
            "active_catalog_pick_key": "custom::trial",
            "active_music_source": "custom_progression",
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        ctx = reset_backing_on_active_song_change(
            session,
            new_pick_key="Pop::Shape of You",
            practice_concert_key="Bm",
        )
        self.assertEqual(ctx.source, "regular_song")


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
        # Pass 8: identity change applies pending before the widget (not leave Bm).
        self.assertEqual(st.session_state.get("display_key"), "G")
        self.assertNotIn("_pending_display_key", st.session_state)


if __name__ == "__main__":
    unittest.main()

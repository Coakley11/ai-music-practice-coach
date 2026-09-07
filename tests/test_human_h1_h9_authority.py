"""Focused H1–H9 product authority: sidebar owner, SBI refresh, jam key, mission mode."""

from __future__ import annotations

import unittest

from backing_context import BackingContext, restore_regular_song_backing, set_backing_context
from song_catalog.catalog import format_pick_key
from source_session_state import (
    RESTORE_SBI_CUSTOM_SOURCE_KEY,
    SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
    bind_sidebar_practice_key_to_backing_owner,
    get_sbi_preview_source,
    note_explicit_sbi_source_selection,
    sbi_must_follow_global_active,
)


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")


class _St:
    def __init__(self, session: dict) -> None:
        self.session_state = session


class TestH1CatalogBackingReleasesCustomSidebar(unittest.TestCase):
    def test_custom_page_d_does_not_remain_sidebar_on_shape_backing(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "D",
            "concert_key": "D",
            "_custom_page_sidebar_overlay": True,
            "cpl_last_display_key": "D",
            "active_catalog_pick_key": SHAPE_PICK,
            "active_music_source": "catalog",
            "practice_key_by_source": {SHAPE_PICK: "Bm"},
            "selected_song": {
                "title": "Shape of You",
                "key": "Bm",
                "pick_key": SHAPE_PICK,
            },
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=SHAPE_PICK,
                bound_pick_key=SHAPE_PICK,
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertEqual(tok, "Bm")
        self.assertEqual(session.get("display_key"), "Bm")
        self.assertFalse(session.get("_custom_page_sidebar_overlay"))


class TestH2SbiCustomRefreshOutranksFollowActive(unittest.TestCase):
    def test_persisted_custom_click_survives_follow_active_on_flush(self) -> None:
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "Custom progression",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "creative_workspace_state": {
                SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
                "sbi_preview_source": "Custom progression",
                RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            },
        }
        self.assertFalse(sbi_must_follow_global_active(session))
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))

    def test_page_snapshot_cannot_reclaim_active_over_restored_custom_click(self) -> None:
        from studio_page_persistence import apply_page_snapshot

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
        }
        apply_page_snapshot(
            session,
            {
                "improv_song_source": "Active song",
                "sbi_preview_source": "Active song",
            },
        )
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        session = {
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "creative_workspace_state": {
                SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            },
        }
        note_explicit_sbi_source_selection(session, "Custom progression")
        self.assertFalse(session.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        blob = session.get("creative_workspace_state") or {}
        self.assertFalse(blob.get(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY))
    def test_seed_custom_radio_before_render_outranks_empty_or_active(self) -> None:
        from source_session_state import seed_sbi_custom_radio_before_render

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
        }
        self.assertEqual(seed_sbi_custom_radio_before_render(session), "Custom progression")
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            "_streamlit_widgets_locked_this_run": True,
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "",
            "creative_workspace_state": {
                RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
                "sbi_preview_source": "Custom progression",
            },
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_flush_pending_active_clears_stale_custom_restore_stamp(self) -> None:
        from source_session_state import seed_sbi_custom_radio_before_render
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            PENDING_IMPROV_SONG_SOURCE: "Active song",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "creative_workspace_state": {
                RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
                "sbi_preview_source": "Custom progression",
            },
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(get_sbi_preview_source(session), "Active song")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        blob = session.get("creative_workspace_state") or {}
        self.assertFalse(blob.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertEqual(seed_sbi_custom_radio_before_render(session), "Active song")
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_next_rerun_cannot_readopt_cleared_custom_stamp(self) -> None:
        from source_session_state import (
            adopt_restore_sbi_custom_stamp,
            seed_sbi_custom_radio_before_render,
        )
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            PENDING_IMPROV_SONG_SOURCE: "Active song",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }
        flush_pending_improv_song_source(session)
        self.assertFalse(adopt_restore_sbi_custom_stamp(session))
        self.assertEqual(seed_sbi_custom_radio_before_render(session), "Active song")
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_explicit_custom_click_still_stamps_session_and_blob(self) -> None:
        session = {
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "creative_workspace_state": {},
        }
        note_explicit_sbi_source_selection(session, "Custom progression")
        self.assertEqual(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY), True)
        blob = session.get("creative_workspace_state") or {}
        self.assertTrue(blob.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_active_custom_cycle_one_transition_each(self) -> None:
        from studio_page_state import apply_improv_song_source

        session = {
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }

        def _noop(_sess: dict) -> None:
            return None

        apply_improv_song_source(
            session, "Active song", set_catalog_source=_noop, set_custom_source=_noop
        )
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertFalse((session.get("creative_workspace_state") or {}).get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

        apply_improv_song_source(
            session, "Custom progression", set_catalog_source=_noop, set_custom_source=_noop
        )
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertTrue((session.get("creative_workspace_state") or {}).get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

        apply_improv_song_source(
            session, "Active song", set_catalog_source=_noop, set_custom_source=_noop
        )
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

        apply_improv_song_source(
            session, "Custom progression", set_catalog_source=_noop, set_custom_source=_noop
        )
        self.assertEqual(session.get("sbi_preview_source"), "Custom progression")
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_composition_remains_a_distinct_third_source(self) -> None:
        from studio_page_state import apply_improv_song_source

        session = {
            "improv_song_source": "Custom progression",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }

        def _noop(_sess: dict) -> None:
            return None

        apply_improv_song_source(
            session, "Composition", set_catalog_source=_noop, set_custom_source=_noop
        )
        self.assertEqual(session.get("improv_song_source"), "Composition")
        self.assertEqual(session.get("sbi_preview_source"), "Composition")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertNotEqual(session.get("improv_song_source"), "Custom progression")
        self.assertNotEqual(session.get("improv_song_source"), "Active song")

    def test_refresh_after_active_keeps_active_not_custom(self) -> None:
        from source_session_state import seed_sbi_custom_radio_before_render
        from studio_page_state import PENDING_IMPROV_SONG_SOURCE, flush_pending_improv_song_source

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            PENDING_IMPROV_SONG_SOURCE: "Active song",
            "improv_song_source": "Active song",
            "sbi_preview_source": "Active song",
            "_last_improv_song_source": "Custom progression",
            "_sbi_song_source_hydrated": True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }
        flush_pending_improv_song_source(session)
        remount = {
            "improv_song_source": "Active song",
            "sbi_preview_source": session.get("sbi_preview_source"),
            "_last_improv_song_source": session.get("_last_improv_song_source"),
            "_sbi_song_source_hydrated": False,
            "creative_workspace_state": dict(session.get("creative_workspace_state") or {}),
        }
        flush_pending_improv_song_source(remount)
        self.assertEqual(seed_sbi_custom_radio_before_render(remount), "Active song")
        self.assertEqual(remount.get("improv_song_source"), "Active song")
        self.assertFalse(remount.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))

    def test_refresh_after_explicit_custom_still_restores_custom(self) -> None:
        from source_session_state import seed_sbi_custom_radio_before_render
        from studio_page_state import flush_pending_improv_song_source

        session = {
            "studio_page": "creative",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "Active song",
            "_sbi_song_source_hydrated": False,
            "creative_workspace_state": {
                RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
                "sbi_preview_source": "Custom progression",
            },
        }
        flush_pending_improv_song_source(session)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(seed_sbi_custom_radio_before_render(session), "Custom progression")

    def test_last_custom_trial_survives_when_active_wins(self) -> None:
        from songs.music_source import LAST_CUSTOM_STATE_KEY
        from studio_page_state import apply_improv_song_source

        trial = {
            "name": "Trial Song",
            "active": {"name": "Trial Song", "original_key_center": "D"},
        }
        session = {
            LAST_CUSTOM_STATE_KEY: trial,
            "improv_song_source": "Custom progression",
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "creative_workspace_state": {RESTORE_SBI_CUSTOM_SOURCE_KEY: True},
        }

        def _noop(_sess: dict) -> None:
            return None

        apply_improv_song_source(
            session, "Active song", set_catalog_source=_noop, set_custom_source=_noop
        )
        snap = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(snap.get("name"), "Trial Song")
        self.assertEqual((snap.get("active") or {}).get("original_key_center"), "D")
        self.assertEqual(session.get("improv_song_source"), "Active song")

    def test_remounted_active_radio_cannot_pop_restore_stamp(self) -> None:
        from source_session_state import apply_sbi_radio_live_against_restore_stamp

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY: True,
            "improv_song_source": "Active song",
            "sbi_preview_source": "Custom progression",
            "_last_improv_song_source": "",
            "creative_workspace_state": {
                RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
                "sbi_preview_source": "Custom progression",
            },
        }
        won = apply_sbi_radio_live_against_restore_stamp(session, "Active song")
        self.assertEqual(won, "Custom progression")
        self.assertTrue(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))
        self.assertFalse(sbi_must_follow_global_active(session))
        self.assertEqual(get_sbi_preview_source(session), "Custom progression")

    def test_genuine_active_click_after_custom_may_leave(self) -> None:
        from source_session_state import (
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY,
            apply_sbi_radio_live_against_restore_stamp,
        )

        session = {
            RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
            "improv_song_source": "Active song",
            "_last_improv_song_source": "Custom progression",
            SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY: True,
        }
        won = apply_sbi_radio_live_against_restore_stamp(session, "Active song")
        self.assertEqual(won, "Active song")
        self.assertFalse(session.get(RESTORE_SBI_CUSTOM_SOURCE_KEY))


class TestH3H4JamBackingKeyAuthority(unittest.TestCase):
    def test_leftover_missions_tab_does_not_steal_jam_backing_key(self) -> None:
        from creative_key_sync import (
            entry_jam_practice_key_authority_active,
            generated_backing_owns_left_panel_key,
        )
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

        session = {
            "studio_page": "backing",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "display_key": "C",
            "concert_key": "C",
            "active_catalog_pick_key": SHAPE_PICK,
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "jam_session_generator",
                "practice_key_token": "C",
                "practice_tonic": "C",
                "practice_mode": "major",
                "entry_mode": "Jam Session Generator",
            },
            "_generated_jam_key_owner_active": True,
        }
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Bossa nova",
            ),
        )
        self.assertTrue(generated_backing_owns_left_panel_key(session))
        self.assertTrue(entry_jam_practice_key_authority_active(session))
        from creative_key_sync import (
            _catalog_song_workflow_owns_practice_key,
            resolve_practice_key_write_owner,
        )

        self.assertEqual(resolve_practice_key_write_owner(session), "entry_jam")
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))

    def test_leftover_sbi_tab_does_not_steal_jam_backing_write(self) -> None:
        from creative_key_sync import (
            _catalog_song_workflow_owns_practice_key,
            generated_backing_owns_left_panel_key,
            resolve_practice_key_write_owner,
            sync_sidebar_creative_concert_key,
        )
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY
        from songs.key_state import mark_display_key_changed
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
        from types import SimpleNamespace
        from unittest.mock import patch

        session = {
            "studio_page": "backing",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "display_key": "Eb",
            "concert_key": "C",
            "active_catalog_pick_key": SHAPE_PICK,
            "selected_song": {
                "title": "Shape of You",
                "key": "Bm",
                "pick_key": SHAPE_PICK,
            },
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "key_owner": "jam_session_generator",
                "practice_key_token": "C",
                "practice_tonic": "C",
                "practice_mode": "major",
                "entry_mode": "Jam Session Generator",
            },
            "_generated_jam_key_owner_active": True,
        }
        set_practice_concert_key(session, "Bm", pick_key=SHAPE_PICK)
        catalog_before = get_practice_concert_key(session, SHAPE_PICK)
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Bossa nova",
            ),
        )
        self.assertEqual(resolve_practice_key_write_owner(session), "entry_jam")
        self.assertTrue(generated_backing_owns_left_panel_key(session))
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))
        st = SimpleNamespace(session_state=session)
        with patch("active_song_state.flush_active_song_edits_and_save", create=True, return_value=True):
            with patch("songs.state.persist_music_local_state"):
                with patch("custom_progression_lab.on_global_display_key_change", return_value=False):
                    mark_display_key_changed(st)
        self.assertEqual(get_practice_concert_key(session, SHAPE_PICK), catalog_before)
        self.assertNotEqual(str(get_practice_concert_key(session, SHAPE_PICK) or ""), "Eb")
        self.assertEqual(session.get("improv_jam_key"), "Eb")
        ctx = session.get("backing_context") if isinstance(session.get("backing_context"), dict) else {}
        self.assertIn(str(ctx.get("concert_key") or ctx.get("key") or ""), {"Eb", "Eb major"})
        session["display_key"] = "Eb"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("improv_jam_key"), "Eb")
        self.assertEqual(get_practice_concert_key(session, SHAPE_PICK), catalog_before)

    def test_catalog_backing_write_owner_is_catalog(self) -> None:
        from creative_key_sync import resolve_practice_key_write_owner

        session = {
            "studio_page": "backing",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "display_key": "Bm",
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=SHAPE_PICK,
                bound_pick_key=SHAPE_PICK,
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        self.assertEqual(resolve_practice_key_write_owner(session), "catalog")

    def test_mission_backing_write_owner_is_mission(self) -> None:
        from creative_key_sync import resolve_practice_key_write_owner

        session = {
            "studio_page": "backing",
            "improv_intelligence_tab": "Missions",
            "display_key": "Cm",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        self.assertEqual(resolve_practice_key_write_owner(session), "mission")

    def test_return_to_catalog_backing_binds_sidebar_to_card_key(self) -> None:
        session = {
            "studio_page": "backing",
            "display_key": "Bm",
            "concert_key": "Bm",
            "active_catalog_pick_key": SHAPE_PICK,
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=SHAPE_PICK,
                bound_pick_key=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertEqual(tok, "Cm")
        self.assertEqual(session.get("display_key"), "Cm")


class TestH5H6MissionModeAndPersist(unittest.TestCase):
    def test_minor_mission_backing_options_are_minor_only(self) -> None:
        from creative_key_sync import prepare_backing_context_sidebar_display_key
        from music_theory import key_mode

        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_intelligence_tab": "Missions",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        opts = prepare_backing_context_sidebar_display_key(_St(session), session)
        majors = [o for o in opts if key_mode(o) == "major"]
        self.assertGreaterEqual(len(opts), 4)
        self.assertEqual(majors, [])
        self.assertIn("Cm", opts)
        self.assertIn("C#m", opts)

    def test_hydrate_restores_saved_mission_practice_key(self) -> None:
        from improvisation_mission_persistence import hydrate_mission_workspace_after_restore

        session = {
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Bm",
        }
        hydrate_mission_workspace_after_restore(session)
        self.assertEqual(session.get("display_key"), "Bm")
        self.assertEqual(session.get("concert_key"), "Bm")
        self.assertEqual(session.get("display_key_mission_backing"), "Bm")


    def test_mission_pk_transaction_cm_bb_becomes_bm_a(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import apply_specialized_mission_practice_key
        from music_persistent_state import _PERSIST_KEYS

        self.assertIn("improv_mission_concert_key", _PERSIST_KEYS)
        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "ii_selected_chord": "Bb",
            "show_chart_in_instrument_key": True,
            "_mission_pk_transpose_from": "Cm",
            "practice_key_by_source": {SHAPE_PICK: "Bm"},
            "active_catalog_pick_key": SHAPE_PICK,
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
                bound_pick_key=SHAPE_PICK,
                progression=["Bb"],
            ),
        )
        applied = apply_specialized_mission_practice_key(session, "Bm")
        self.assertEqual(applied, "Bm")
        self.assertEqual(session.get("display_key"), "Bm")
        self.assertEqual(session.get("improv_mission_concert_key"), "Bm")
        self.assertEqual(session.get("ii_selected_chord"), "A")
        raw = session.get("backing_context")
        self.assertIsInstance(raw, dict)
        self.assertEqual(str(raw.get("concert_key") or raw.get("key") or ""), "Bm")
        self.assertEqual(session.get("practice_key_by_source", {}).get(SHAPE_PICK), "Bm")
        self.assertTrue(session.get("show_chart_in_instrument_key"))
        self.assertEqual(str(session.get("display_key_change_source") or ""), "sidebar_on_change")
        self.assertEqual(session.get("_pending_mission_practice_key"), "Bm")
        self.assertNotEqual(session.get("display_key_mission_backing"), "Bm")

    def test_stale_mission_widget_does_not_own_written_or_card(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import (
            canonical_mission_practice_key,
            mission_backing_projection_concert_and_written,
            seed_mission_backing_practice_key_widget,
        )
        from instrument_transposition import written_key_for_type

        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "display_key_mission_backing": "Bm",
            "show_chart_in_instrument_key": True,
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        self.assertEqual(canonical_mission_practice_key(session), "Cm")
        concert, written = mission_backing_projection_concert_and_written(session)
        self.assertEqual(concert, "Cm")
        self.assertEqual(written, written_key_for_type("Cm", "Alto saxophone (Eb)"))
        self.assertEqual(written, "Am")
        self.assertEqual(session.get("display_key_mission_backing"), "Bm")
        seeded = seed_mission_backing_practice_key_widget(session)
        self.assertEqual(seeded, "Cm")
        self.assertEqual(session.get("display_key_mission_backing"), "Cm")

    def test_stale_mission_widget_does_not_keep_old_generation_after_user_bm(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import (
            mission_backing_projection_concert_and_written,
            seed_mission_backing_practice_key_widget,
        )
        from instrument_transposition import written_key_for_type

        session = {
            "studio_page": "backing",
            "display_key": "Bm",
            "concert_key": "Bm",
            "improv_mission_concert_key": "Bm",
            "display_key_mission_backing": "Cm",
            "show_chart_in_instrument_key": True,
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        concert, written = mission_backing_projection_concert_and_written(session)
        self.assertEqual(concert, "Bm")
        self.assertEqual(written, written_key_for_type("Bm", "Alto saxophone (Eb)"))
        self.assertEqual(written, "G#m")
        seeded = seed_mission_backing_practice_key_widget(session)
        self.assertEqual(seeded, "Bm")
        self.assertEqual(session.get("display_key_mission_backing"), "Bm")

    def test_catalog_leave_does_not_snap_mission_widget_back_to_landing_bm(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import (
            canonical_mission_practice_key,
            prepare_mission_backing_practice_key_widget,
        )
        from songs.key_state import (
            DISPLAY_KEY_OWNER_TRANSITION_KEY,
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY,
            apply_display_key_owner_transition_if_needed,
        )
        from source_session_state import (
            bind_sidebar_practice_key_to_backing_owner,
            sync_specialized_leave_catalog_widget,
        )

        owner = "mission::shape"
        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "display_key_mission_backing": "Cm",
            "improv_active_mission": "shape",
            DISPLAY_KEY_WIDGET_OWNER_ID_KEY: owner,
            DISPLAY_KEY_OWNER_TRANSITION_KEY: {
                "from": "catalog::shape",
                "to": owner,
                "canonical": "Bm",
                "stale": "Bm",
            },
            "_specialized_practice_token_leaving": "Bm",
            "_specialized_leave_catalog_pk": "Bm",
            "_pending_display_key": "Bm",
            "show_chart_in_instrument_key": True,
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id="shape",
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
                mission_id="shape",
            ),
        )
        rebound = apply_display_key_owner_transition_if_needed(session)
        self.assertEqual(rebound, "")
        self.assertEqual(canonical_mission_practice_key(session), "Cm")
        sync_specialized_leave_catalog_widget(
            session, widget_key="display_key_mission_backing"
        )
        self.assertEqual(session.get("display_key_mission_backing"), "Cm")
        session["display_key_mission_backing"] = "Bm"
        session["_pending_display_key"] = "Bm"
        mirrored = prepare_mission_backing_practice_key_widget(
            session, options=["Cm", "Dm", "Em", "Fm", "Gm", "Am", "Bm"]
        )
        self.assertEqual(mirrored, "Cm")
        self.assertEqual(session.get("display_key_mission_backing"), "Cm")
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertEqual(tok, "Cm")
        self.assertEqual(session.get("display_key"), "Cm")
        self.assertEqual(session.get("improv_mission_concert_key"), "Cm")

    def test_stale_widget_cm_does_not_override_canonical_bm_after_user_edit(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import prepare_mission_backing_practice_key_widget
        from instrument_transposition import written_key_for_type
        from creative_key_sync import mission_backing_projection_concert_and_written

        session = {
            "studio_page": "backing",
            "display_key": "Bm",
            "concert_key": "Bm",
            "improv_mission_concert_key": "Bm",
            "display_key_mission_backing": "Cm",
            "_pending_display_key": "Cm",
            "show_chart_in_instrument_key": True,
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Bm",
                display_key="Bm",
                concert_key="Bm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        concert, written = mission_backing_projection_concert_and_written(session)
        self.assertEqual(concert, "Bm")
        self.assertEqual(written, written_key_for_type("Bm", "Alto saxophone (Eb)"))
        self.assertEqual(written, "G#m")
        mirrored = prepare_mission_backing_practice_key_widget(
            session, options=["Cm", "Dm", "Em", "Fm", "Gm", "Am", "Bm"]
        )
        self.assertEqual(mirrored, "Bm")
        self.assertEqual(session.get("display_key_mission_backing"), "Bm")

    def test_refresh_keeps_transformed_mission_chord_not_map_default(self) -> None:
        from creative_mission_config_persistence import reconcile_mission_target_identity

        session = {
            "studio_page": "backing",
            "improv_mission_concert_key": "Bm",
            "ii_selected_chord": "Em",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 1,
            "ii_selected_chord_label": "Verse 1 · Em",
            "improv_mission_practice_context": {
                "chord": {"symbol": "Em", "section": "Verse 1", "chord_index": 1}
            },
        }
        values = {
            "ii_selected_chord": "Em",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 1,
            "ii_selected_chord_label": "Verse 1 · Em",
            "improv_mission_chord_options": ["Cm", "Gm", "Ab", "Fm"],
        }
        out = reconcile_mission_target_identity(
            session,
            values,
            save_reason="restore",
            function="test_h6_refresh_chord",
        )
        self.assertEqual(out.get("ii_selected_chord"), "Em")
        self.assertNotEqual(out.get("ii_selected_chord"), "Cm")

    def test_restore_backing_context_does_not_replace_mission_chord_with_progression_head(self) -> None:
        from backing_context import BackingContext
        from backing_source_navigation import restore_session_widgets_from_backing_context

        session = {
            "studio_page": "backing",
            "improv_mission_concert_key": "Bm",
            "ii_selected_chord": "Em",
            "II_SELECTED_CHORD": "Em",
            "ii_selected_section": "Verse 1",
            "display_key": "Bm",
            "concert_key": "Bm",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id=SHAPE_PICK,
            song_title="Shape of You",
            key="Bm",
            display_key="Bm",
            concert_key="Bm",
            bpm=96,
            style="Pop",
            groove="Pop groove",
            progression=["Cm", "Gm", "Ab", "Fm"],
            mission_id="Improvise using only chord tones",
        )
        restore_session_widgets_from_backing_context(session, ctx, widget_safe=True)
        self.assertEqual(session.get("ii_selected_chord"), "Em")

    def test_freeze_overlay_does_not_replace_live_mission_practice_key(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_artifact_global_key_guard import (
            CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY,
            apply_frozen_global_keys_to_payload,
        )

        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            CREATIVE_ARTIFACT_FROZEN_GLOBAL_SNAPSHOT_KEY: {"display_key": "Bm", "concert_key": "Bm"},
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        payload = {
            "core": {"display_key": "Cm"},
            "session": {"display_key": "Cm", "improv_mission_concert_key": "Cm"},
            "active_song_state": {"display_key": "Cm"},
        }
        out = apply_frozen_global_keys_to_payload(session, payload)
        self.assertEqual(out["core"].get("display_key"), "Cm")
        self.assertEqual(out["session"].get("display_key"), "Cm")
        self.assertEqual(out["active_song_state"].get("display_key"), "Cm")

    def test_mission_pk_transaction_does_not_transpose_twice(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from creative_key_sync import apply_specialized_mission_practice_key

        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "ii_selected_chord": "Bb",
            "_mission_pk_transpose_from": "Cm",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
                bound_pick_key=SHAPE_PICK,
                progression=["Bb"],
            ),
        )
        apply_specialized_mission_practice_key(session, "Bm")
        session["_mission_pk_transpose_from"] = "Cm"
        apply_specialized_mission_practice_key(session, "Bm")
        self.assertEqual(session.get("ii_selected_chord"), "A")
        self.assertEqual(session.get("improv_mission_concert_key"), "Bm")

    def test_authoritative_display_key_follows_mission_not_catalog_sticky(self) -> None:
        from backing_context import BackingContext, set_backing_context
        from songs.key_state import get_authoritative_display_key
        from songs.practice_key_state import set_practice_concert_key

        session = {
            "studio_page": "backing",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_mission_concert_key": "Cm",
            "active_catalog_pick_key": SHAPE_PICK,
        }
        set_practice_concert_key(session, "Bm", pick_key=SHAPE_PICK)
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id=SHAPE_PICK,
                song_title="Shape of You",
                key="Cm",
                display_key="Cm",
                concert_key="Cm",
                bpm=96,
                style="Pop",
                groove="Pop groove",
            ),
        )
        self.assertEqual(
            get_authoritative_display_key(session, original_key="Bm", surface="test"),
            "Cm",
        )


class TestH7H8MissionProjectionIdentity(unittest.TestCase):
    def test_alto_bb_minor_written_and_example_are_g_minor(self) -> None:
        from effective_practice_context import musician_facing_chord
        from mission_projection_state import display_chord_from_concert

        shown = display_chord_from_concert("Bbm", concert_key="Bbm", chart_key="Gm")
        shown_l = shown.lower().replace("♭", "b")
        self.assertNotIn("gb", shown_l)
        self.assertTrue(shown_l.startswith("g"))
        chord = musician_facing_chord("Bbm", concert_key="Bbm", chart_key="Gm")
        self.assertNotIn("gb", chord.lower().replace("♭", "b"))

    def test_selected_b_minor_is_the_canonical_mission_chord_identity(self) -> None:
        session = {
            "ii_selected_chord": "Bm",
            "display_key": "F#m",
            "concert_key": "Bm",
        }
        live = str(session.get("ii_selected_chord") or "").strip()
        self.assertEqual(live, "Bm")
        self.assertNotEqual(live, "A#m")


class TestH3CanonicalJamWorkflowBlob(unittest.TestCase):
    def test_native_jam_key_updates_generated_uuid_blob_not_ballad_leftover(self) -> None:
        from creative_key_sync import apply_specialized_jam_practice_key
        from generated_jam_key_change import resolve_generated_workflow_session_id
        from music_workflow_generated_session import commit_jam_session_generation
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            get_active_workflow_pointer,
            get_workflow_blob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        jam_id = "24a4bc47-2774-4fb4-8d5c-5054f9912a80"
        sections = {
            "A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"],
            "B (Bossa Nova)": ["Dm7", "G7", "Em7", "A7"],
        }
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_jam_key": "C",
            "improv_jam_style": "Bossa Nova",
            "improv_groove": "Ballad",
            "improv_jam_bpm": 70,
            "display_key": "C",
            "concert_key": "C",
            "active_catalog_pick_key": SHAPE_PICK,
            "selected_song": {
                "title": "Shape of You",
                "key": "Bm",
                "pick_key": SHAPE_PICK,
            },
        }
        set_practice_concert_key(session, "Bm", pick_key=SHAPE_PICK)
        catalog_before = get_practice_concert_key(session, SHAPE_PICK)
        commit_jam_session_generation(
            session,
            {
                "id": jam_id,
                "style": "Bossa Nova",
                "bpm": 70,
                "mood": "daylight clarity, forward motion",
                "key": "C",
                "sections": sections,
            },
            key_center="C",
            style="Bossa Nova",
            new_session=False,
        )
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="jam_session_generator",
                workflow_session_id="Ballad",
                generated_session_id="Ballad",
                keys=KeyAuthority(
                    practice_tonic="C",
                    practice_mode="major",
                    original_tonic="G",
                    original_mode="major",
                    key_owner="jam_session_generator",
                ),
                section_map={},
                style="Bossa Nova",
                groove="Ballad",
                tempo_bpm=70,
                source_type="generated",
            ),
            source="test_leftover_ballad",
        )
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="jam_session_generator",
                workflow_session_id="Ballad",
                activation_source="leftover_groove",
            ),
            source="test_leftover_ballad",
        )
        session.pop("improv_jam_session", None)
        session["studio_page"] = "backing"
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        self.assertEqual(resolve_generated_workflow_session_id(session, "jam_session_generator"), jam_id)
        session["display_key"] = "Eb"
        session["_streamlit_widgets_locked_this_run"] = True
        landed = apply_specialized_jam_practice_key(session, "Eb")
        self.assertEqual(landed, "Eb")
        self.assertEqual(session.get("improv_jam_key"), "Eb")
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")
        self.assertEqual(str(live.style or ""), "Bossa Nova")
        self.assertEqual(int(live.tempo_bpm or 0), 70)
        a_chords = [str(c) for c in (live.section_map or {}).get("A (Bossa Nova)") or []]
        self.assertTrue(a_chords)
        self.assertTrue(any(c.startswith("Eb") or c.startswith("Fm") or c.startswith("Bb") for c in a_chords), a_chords)
        self.assertFalse(any(c.startswith("Cmaj") for c in a_chords), a_chords)
        hollow = get_workflow_blob(session, "jam_session_generator", "Ballad")
        assert hollow is not None
        ident = resolve_practice_key_identity_for_ui(session)
        assert ident is not None
        self.assertEqual(ident.workflow_session_id, jam_id)
        self.assertEqual(ident.practice_tonic, "Eb")
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "jam_session_generator")
        self.assertEqual(ptr.workflow_session_id, jam_id)
        self.assertEqual(get_practice_concert_key(session, SHAPE_PICK), catalog_before)
        ctx = session.get("backing_context") if isinstance(session.get("backing_context"), dict) else {}
        self.assertIn(str(ctx.get("concert_key") or ctx.get("key") or ""), {"Eb", "Eb major"})
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY

        snap = session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY)
        self.assertIsInstance(snap, dict)
        self.assertEqual(str(snap.get("practice_tonic") or ""), "Eb")
        self.assertEqual(str(snap.get("workflow_session_id") or ""), jam_id)

    def test_nested_persist_uuid_blob_is_hydrated_when_live_store_only_has_ballad(self) -> None:
        from creative_key_sync import apply_specialized_jam_practice_key
        from generated_jam_key_change import resolve_generated_workflow_session_id
        from music_workflow_generated_session import commit_jam_session_generation
        from music_workflow_state_store import (
            MUSIC_WORKFLOW_STATE_STORE_KEY,
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            get_workflow_blob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        jam_id = "38ed358e-d7ff-400d-a842-7cfa974406f4"
        sections = {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"]}
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "improv_jam_style": "Bossa Nova",
            "improv_groove": "Ballad",
            "improv_jam_bpm": 70,
            "display_key": "C",
        }
        commit_jam_session_generation(
            session,
            {"id": jam_id, "style": "Bossa Nova", "bpm": 70, "key": "C", "sections": sections},
            key_center="C",
            style="Bossa Nova",
            new_session=False,
        )
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        uuid_raw = live.to_dict()
        store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
        assert isinstance(store, dict)
        (store.get("blobs") or {}).pop(f"jam_session_generator|{jam_id}", None)
        session["creative_workspace_state"] = {
            "music_workflow_state_v1": {
                "store": {"blobs": {f"jam_session_generator|{jam_id}": uuid_raw}},
            }
        }
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="jam_session_generator",
                workflow_session_id="Ballad",
                generated_session_id="Ballad",
                keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
                section_map={},
                groove="Ballad",
                source_type="generated",
            ),
            source="test_leftover_ballad",
        )
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="Ballad"),
            source="test_leftover_ballad",
        )
        session.pop("improv_jam_session", None)
        session["studio_page"] = "backing"
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        self.assertEqual(resolve_generated_workflow_session_id(session, "jam_session_generator"), jam_id)
        landed = apply_specialized_jam_practice_key(session, "Eb")
        self.assertEqual(landed, "Eb")
        restored = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert restored is not None
        self.assertEqual(str(restored.keys.practice_tonic), "Eb")
        ident = resolve_practice_key_identity_for_ui(session)
        assert ident is not None
        self.assertEqual(ident.workflow_session_id, jam_id)
        self.assertEqual(ident.practice_tonic, "Eb")


class TestH3StaleSnapshotDoesNotOutrankUuidBlob(unittest.TestCase):
    def _session_uuid_eb_stale_snap_c(self) -> tuple[dict, str]:
        from generated_workflow_artifact import (
            BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
            GeneratedWorkflowArtifactSnapshot,
        )
        from music_theory import transpose_sections_dict
        from music_workflow_generated_session import commit_jam_session_generation
        from music_workflow_state_store import get_workflow_blob, save_workflow_blob

        jam_id = "7c9e6679-742f-4d63-9a3c-0f1e2d3c4b5a"
        sections_c = {
            "A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"],
            "B (Bossa Nova)": ["Dm7", "G7", "Em7", "A7"],
        }
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "improv_jam_style": "Bossa Nova",
            "improv_groove": "Ballad",
            "improv_jam_bpm": 70,
            "display_key": "C",
            "concert_key": "C",
            "active_catalog_pick_key": SHAPE_PICK,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
        }
        commit_jam_session_generation(
            session,
            {
                "id": jam_id,
                "style": "Bossa Nova",
                "bpm": 70,
                "mood": "mellow",
                "key": "C",
                "sections": sections_c,
            },
            key_center="C",
            style="Bossa Nova",
            new_session=False,
        )
        blob = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert blob is not None
        keys = blob.keys
        blob.keys = type(keys)(
            original_tonic=keys.original_tonic,
            original_mode=keys.original_mode,
            practice_tonic="Eb",
            practice_mode="major",
            written_tonic=keys.written_tonic,
            written_mode=keys.written_mode,
            instrument=keys.instrument,
            transposition=keys.transposition,
            key_owner="jam_session_generator",
        )
        blob.section_map = transpose_sections_dict(sections_c, "C", "Eb")
        save_workflow_blob(session, blob, source="test_stale_snap")
        session["studio_page"] = "backing"
        session["improv_jam_key"] = "Eb"
        session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = GeneratedWorkflowArtifactSnapshot(
            workflow_owner="jam_session_generator",
            workflow_session_id=jam_id,
            artifact_id=jam_id,
            artifact_revision=1,
            practice_tonic="C",
            practice_mode="major",
            style="Bossa Nova",
            groove="Ballad",
            bpm=70,
            section_map=dict(sections_c),
            progression=["Dm7", "G7", "Cmaj7", "Cmaj7"],
            entry_mode="Jam Session Generator",
        ).to_dict()
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        return session, jam_id

    def test_build_entry_jam_context_prefers_uuid_eb_over_stale_c_snapshot(self) -> None:
        from backing_context import build_entry_jam_context
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY

        session, jam_id = self._session_uuid_eb_stale_snap_c()
        ctx = build_entry_jam_context(session)
        token = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(token.startswith("Eb"), token)
        prog = " ".join(ctx.progression or [])
        self.assertTrue(
            any(str(p).startswith("Eb") or str(p).startswith("Fm") or str(p).startswith("Bb") for p in (ctx.progression or [])),
            prog,
        )
        self.assertFalse(any(str(c).startswith("Cmaj") for c in (ctx.progression or [])), prog)
        snap = session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY)
        self.assertIsInstance(snap, dict)
        self.assertEqual(str(snap.get("practice_tonic") or ""), "Eb")
        self.assertEqual(str(snap.get("workflow_session_id") or ""), jam_id)

    def test_sidebar_bind_resolves_eb_when_snapshot_is_stale_c(self) -> None:
        session, _jam_id = self._session_uuid_eb_stale_snap_c()
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("Eb"), tok)
        self.assertTrue(str(session.get("display_key") or "").startswith("Eb"))

    def test_style_and_bpm_preserved_across_uuid_key_mutation(self) -> None:
        from creative_key_sync import apply_specialized_jam_practice_key
        from music_workflow_generated_session import commit_jam_session_generation
        from music_workflow_state_store import get_workflow_blob

        jam_id = "aaaaaaaa-1111-4bbb-8ccc-ddddeeee0001"
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "improv_jam_style": "Bossa Nova",
            "improv_groove": "Ballad",
            "improv_jam_bpm": 70,
            "display_key": "C",
            "concert_key": "C",
        }
        commit_jam_session_generation(
            session,
            {
                "id": jam_id,
                "style": "Bossa Nova",
                "bpm": 70,
                "key": "C",
                "sections": {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"]},
            },
            key_center="C",
            style="Bossa Nova",
            new_session=False,
        )
        session["studio_page"] = "backing"
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                song_title="Jam",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        apply_specialized_jam_practice_key(session, "Eb")
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")
        self.assertEqual(str(live.style or ""), "Bossa Nova")
        self.assertEqual(int(live.tempo_bpm or 0), 70)


class TestH4CatalogReturnReleasesJamRenderAuthority(unittest.TestCase):
    def test_return_catalog_clears_jam_snapshot_and_keeps_uuid_eb(self) -> None:
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY
        from music_workflow_state_store import get_workflow_blob
        from types import SimpleNamespace
        from unittest.mock import patch

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        session["practice_key_by_source"] = {SHAPE_PICK: "Bm"}
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                        "key": "Bm",
                        "pick_key": SHAPE_PICK,
                        "bpm": 96,
                        "sections": {"Verse": ["Bm", "F#m", "Em", "G"]},
                    },
                    "Bm",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        catalog_tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertFalse(catalog_tok.startswith("Eb"), catalog_tok)
        prog = " ".join(ctx.progression or [])
        self.assertNotIn("Ebmaj", prog)
        snap = session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY)
        jam_snap = isinstance(snap, dict) and str(snap.get("workflow_owner") or "") == "jam_session_generator"
        self.assertFalse(jam_snap)
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")
        a_chords = [str(c) for c in (live.section_map or {}).get("A (Bossa Nova)") or []]
        self.assertTrue(any(c.startswith("Eb") or c.startswith("Fm") or c.startswith("Bb") for c in a_chords), a_chords)
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertFalse(str(tok).startswith("Eb"), tok)

    def test_jam_eb_does_not_stamp_catalog_say_g(self) -> None:
        from song_catalog.catalog import format_pick_key
        from types import SimpleNamespace
        from unittest.mock import patch

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session["active_catalog_pick_key"] = say_pick
        session["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
        }
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"
        session["practice_key_by_source"] = {say_pick: "G"}
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Say",
                        "artist": "John Mayer",
                        "key": "G",
                        "pick_key": say_pick,
                        "bpm": 82,
                        "sections": {"Verse": ["Eb", "Ab", "Cm", "Bb"]},
                    },
                    "G",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        catalog_tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(catalog_tok.startswith("G"), catalog_tok)
        self.assertFalse(catalog_tok.startswith("Eb"), catalog_tok)
        from songs.practice_key_state import get_practice_concert_key

        self.assertEqual(str(get_practice_concert_key(session, say_pick) or ""), "G")
        from music_workflow_state_store import get_workflow_blob

        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")
        store = session.get("practice_key_by_source") if isinstance(session.get("practice_key_by_source"), dict) else {}
        self.assertEqual(str(store.get(say_pick) or ""), "G")
        jam_sticky = str(store.get("creative::jam_session_generator") or "")
        self.assertFalse(jam_sticky.startswith("G"), jam_sticky)
        live_dk = str(session.get("display_key") or session.get("concert_key") or "")
        sealed = str(session.get("_specialized_leave_catalog_pk") or "")
        if live_dk.startswith("Eb"):
            self.assertEqual(sealed, "G")
        else:
            self.assertTrue(live_dk.startswith("G"), live_dk)
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)

    def test_bind_sidebar_prefers_sealed_catalog_g_over_ctx_eb(self) -> None:
        from song_catalog.catalog import format_pick_key

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session = {
            "studio_page": "backing",
            "display_key": "Eb",
            "concert_key": "Eb",
            "_specialized_practice_token_leaving": "Eb",
            "_specialized_leave_catalog_pk": "G",
            "_specialized_leave_catalog_pick": say_pick,
            "practice_key_by_source": {say_pick: "G"},
            "active_catalog_pick_key": say_pick,
        }
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog song",
                active_song_id=say_pick,
                bound_pick_key=say_pick,
                song_title="Say",
                key="Eb",
                display_key="Eb",
                concert_key="Eb",
                bpm=82,
                style="",
                groove="Pop groove",
            ),
        )
        tok = bind_sidebar_practice_key_to_backing_owner(_St(session), session)
        self.assertTrue(str(tok).startswith("G"), tok)
        self.assertTrue(str(session.get("display_key") or "").startswith("G"))

    def test_sync_widget_replaces_leaving_eb_with_sealed_g(self) -> None:
        from source_session_state import sync_specialized_leave_catalog_widget

        session = {
            "display_key": "Eb",
            "_specialized_practice_token_leaving": "Eb",
            "_specialized_leave_catalog_pk": "G",
        }
        sync_specialized_leave_catalog_widget(session)
        self.assertEqual(session.get("display_key"), "G")
        self.assertEqual(session.get("_specialized_leave_catalog_pk"), "G")
        sync_specialized_leave_catalog_widget(session, allow_clear=True)
        self.assertIsNone(session.get("_specialized_practice_token_leaving"))
        self.assertIsNone(session.get("_specialized_leave_catalog_pk"))

    def test_release_then_restore_does_not_stamp_jam_eb_on_say(self) -> None:
        from backing_source_navigation import release_specialized_backing_for_generic_navigation
        from song_catalog.catalog import format_pick_key
        from types import SimpleNamespace
        from unittest.mock import patch

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session["active_catalog_pick_key"] = say_pick
        session["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
        }
        session["display_key"] = "Eb"
        session["concert_key"] = "Eb"
        session["practice_key_by_source"] = {say_pick: "G"}
        session["_backing_explicit_handoff_source"] = "entry_jam"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Say",
                        "artist": "John Mayer",
                        "key": "G",
                        "pick_key": say_pick,
                        "bpm": 82,
                        "sections": {"Verse": ["G", "C", "Em", "D"]},
                    },
                    "G",
                ),
            ):
                release_specialized_backing_for_generic_navigation(session, st_like=st_like)
                ctx = restore_regular_song_backing(session, st_like=st_like)
        catalog_tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(catalog_tok.startswith("G"), catalog_tok)
        from songs.practice_key_state import get_practice_concert_key

        self.assertEqual(str(get_practice_concert_key(session, say_pick) or ""), "G")
        from music_workflow_state_store import get_workflow_blob

        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")

    def test_catalog_return_does_not_redirect_g_onto_jam_sticky(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.practice_key_state import (
            CREATIVE_JAM_SESSION_PICK,
            resolve_settings_pick_for_write,
            set_practice_concert_key,
        )

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "display_key": "Eb",
            "concert_key": "Eb",
            "_specialized_practice_token_leaving": "Eb",
            "practice_key_by_source": {
                say_pick: "G",
                CREATIVE_JAM_SESSION_PICK: "Eb",
            },
            "backing_context": {
                "source": "entry_jam",
                "display_key": "Eb",
                "concert_key": "Eb",
                "key": "Eb",
            },
        }
        self.assertEqual(
            resolve_settings_pick_for_write(session, say_pick),
            say_pick,
        )
        set_practice_concert_key(
            session, "G", pick_key=say_pick, allow_restore_original=True
        )
        store = session.get("practice_key_by_source") if isinstance(session.get("practice_key_by_source"), dict) else {}
        self.assertEqual(str(store.get(say_pick) or ""), "G")
        self.assertEqual(str(store.get(CREATIVE_JAM_SESSION_PICK) or ""), "Eb")

    def test_jam_eb_does_not_fill_empty_catalog_pk(self) -> None:
        from song_catalog.catalog import format_pick_key
        from types import SimpleNamespace
        from unittest.mock import patch

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session["active_catalog_pick_key"] = say_pick
        session["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
        }
        session["display_key"] = "Eb"
        session["practice_key_by_source"] = {}
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Say",
                        "artist": "John Mayer",
                        "key": "G",
                        "pick_key": say_pick,
                        "bpm": 82,
                        "sections": {"Verse": ["G", "C", "Em", "D"]},
                    },
                    "G",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        catalog_tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(catalog_tok.startswith("G"), catalog_tok)
        from songs.practice_key_state import get_practice_concert_key

        stamped = str(get_practice_concert_key(session, say_pick) or "")
        self.assertFalse(stamped.startswith("Eb"), stamped)

    def test_dict_backing_context_and_handoff_still_block_jam_eb(self) -> None:
        """Hydrated persist stores backing_context as a dict, not a dataclass."""
        from song_catalog.catalog import format_pick_key
        from types import SimpleNamespace
        from unittest.mock import patch

        helper = TestH3StaleSnapshotDoesNotOutrankUuidBlob()
        session, jam_id = helper._session_uuid_eb_stale_snap_c()
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        session["active_catalog_pick_key"] = say_pick
        session["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
        }
        session["display_key"] = "Eb"
        session["practice_key_by_source"] = {say_pick: "G"}
        session["_backing_explicit_handoff_source"] = "entry_jam"
        raw = session.get("backing_context")
        if hasattr(raw, "to_dict"):
            session["backing_context"] = raw.to_dict()
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Say",
                        "artist": "John Mayer",
                        "key": "G",
                        "pick_key": say_pick,
                        "bpm": 82,
                        "sections": {"Verse": ["G", "C", "Em", "D"]},
                    },
                    "G",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        catalog_tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(catalog_tok.startswith("G"), catalog_tok)
        self.assertNotEqual(str(session.get("_backing_explicit_handoff_source") or ""), "entry_jam")
        from music_workflow_state_store import get_workflow_blob

        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")


class TestH3LiveStoreVersusNestedCws(unittest.TestCase):
    """Competing live C vs nested CWS Eb — the actual Streamlit post-callback split."""

    def _blob(self, jam_id: str, tonic: str, sections: dict):
        from music_workflow_state_store import KeyAuthority, WorkflowStateBlob

        return WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id=jam_id,
            generated_session_id=jam_id,
            keys=KeyAuthority(
                practice_tonic=tonic,
                practice_mode="major",
                original_tonic="C",
                original_mode="major",
                key_owner="jam_session_generator",
            ),
            section_map=dict(sections),
            style="Bossa Nova",
            groove="Ballad",
            tempo_bpm=70,
            source_type="generated",
        )

    def _split_session(self) -> tuple[dict, str]:
        from music_workflow_state_store import (
            MUSIC_WORKFLOW_STATE_STORE_KEY,
            blob_storage_key,
            save_workflow_blob,
        )

        jam_id = "401ea4e9-43b5-4d50-8cd2-929eaefc3160"
        c_sections = {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"]}
        eb_sections = {"A (Bossa Nova)": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]}
        session: dict = {
            "studio_page": "backing",
            "display_key": "Eb",
            "concert_key": "Eb",
            "improv_jam_key": "C",
            "improv_entry_mode": "Jam Session Generator",
            "_jam_session_generator_session_id": jam_id,
            "improv_jam_session": {"id": jam_id, "key": "C", "sections": c_sections},
            "backing_context": {
                "source": "entry_jam",
                "entry_mode": "Jam Session Generator",
                "concert_key": "C",
                "key": "C",
                "display_key": "C",
            },
        }
        save_workflow_blob(session, self._blob(jam_id, "C", c_sections), source="test_live_c")
        live_store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
        nested_eb = self._blob(jam_id, "Eb", eb_sections).to_dict()
        session["creative_workspace_state"] = {
            "music_workflow_state_v1": {
                "store": {
                    "workspace_id": str((live_store or {}).get("workspace_id") or ""),
                    "blobs": {blob_storage_key("jam_session_generator", jam_id): nested_eb},
                    "context_revision_seq": 15,
                }
            }
        }
        return session, jam_id

    def test_stale_live_c_nested_eb_get_workflow_blob_returns_eb(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        session, jam_id = self._split_session()
        blob = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic), "Eb")
        live = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert live is not None
        self.assertEqual(str(live.keys.practice_tonic), "Eb")

    def test_stale_live_c_nested_eb_build_entry_jam_context_and_sidebar_eb(self) -> None:
        from backing_context import BackingContext, build_entry_jam_context, set_backing_context

        session, _jam_id = self._split_session()
        set_backing_context(
            session,
            BackingContext(
                source="entry_jam",
                source_label="Jam Session Generator",
                entry_mode="Jam Session Generator",
                active_song_id="jam",
                bound_pick_key="jam",
                song_title="Jam Session",
                concert_key="C",
                display_key="C",
                key="C",
                bpm=70,
                style="Bossa Nova",
                groove="Ballad",
            ),
        )
        ctx = build_entry_jam_context(session)
        tok = str(ctx.concert_key or ctx.display_key or ctx.key or "")
        self.assertTrue(tok.startswith("Eb"), tok)
        from types import SimpleNamespace

        bound = bind_sidebar_practice_key_to_backing_owner(SimpleNamespace(session_state=session), session)
        self.assertTrue(str(bound).startswith("Eb"), bound)
        self.assertTrue(str(session.get("display_key") or "").startswith("Eb"))

    def test_live_eb_stale_nested_c_keeps_eb_when_widget_is_eb(self) -> None:
        from music_workflow_state_store import (
            MUSIC_WORKFLOW_STATE_STORE_KEY,
            blob_storage_key,
            get_workflow_blob,
            save_workflow_blob,
        )

        jam_id = "401ea4e9-43b5-4d50-8cd2-929eaefc3160"
        c_sections = {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "Cmaj7"]}
        eb_sections = {"A (Bossa Nova)": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]}
        session: dict = {
            "studio_page": "backing",
            "display_key": "Eb",
            "improv_jam_key": "Eb",
            "_jam_session_generator_session_id": jam_id,
        }
        save_workflow_blob(session, self._blob(jam_id, "Eb", eb_sections), source="test_live_eb")
        live_store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
        session["creative_workspace_state"] = {
            "music_workflow_state_v1": {
                "store": {
                    "workspace_id": str((live_store or {}).get("workspace_id") or ""),
                    "blobs": {
                        blob_storage_key("jam_session_generator", jam_id): self._blob(
                            jam_id, "C", c_sections
                        ).to_dict()
                    },
                }
            }
        }
        blob = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic), "Eb")

    def test_stale_display_key_c_cannot_rewrite_nested_eb_via_get(self) -> None:
        from music_workflow_state_store import get_workflow_blob

        session, jam_id = self._split_session()
        session["display_key"] = "C"
        session["improv_jam_key"] = "C"
        blob = get_workflow_blob(session, "jam_session_generator", jam_id)
        assert blob is not None
        # Widget C matches live C; nested Eb must not be destroyed by a read.
        # After a native click the widget is Eb. A leftover C widget is the
        # pre-click state and may keep live C. Nested Eb remains in CWS.
        self.assertEqual(str(blob.keys.practice_tonic), "C")
        nested = (
            ((session.get("creative_workspace_state") or {}).get("music_workflow_state_v1") or {})
            .get("store")
            or {}
        )
        nested_blob = ((nested.get("blobs") or {}).get(f"jam_session_generator|{jam_id}") or {})
        keys = nested_blob.get("keys") if isinstance(nested_blob, dict) else {}
        self.assertEqual(str((keys or {}).get("practice_tonic") or ""), "Eb")


if __name__ == "__main__":
    unittest.main()

"""Tests for canonical Backing Track page state (Phase C acceptance A–E)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from backing_track_state import (
    BACKING_DIRTY_KEY,
    BACKING_DURABLE_WIDGET_KEYS,
    BACKING_WIDGETS_SEEDED_KEY,
    apply_backing_source_state_from_ami,
    apply_cloud_backing_state_if_allowed,
    BACKING_DEVICE_COMPARE_LABELS,
    bind_backing_rendered_widgets_from_canonical,
    classify_backing_stale_cloud_hint,
    classify_backing_sync_failure_class,
    collect_backing_device_context,
    format_backing_device_compare_trace,
    coerce_backing_groove_for_widget,
    backing_filters_for_workspace_envelope,
    collect_backing_persistence_trace,
    collect_rendered_backing_widget_trace,
    commit_backing_canonical_blob_only,
    commit_backing_state_from_session,
    flush_backing_edits,
    gather_backing_filters,
    is_backing_locally_dirty,
    is_backing_user_dirty,
    mark_backing_local_edit,
    mark_backing_user_edit,
    mark_backing_pending_sync,
    prepare_backing_page,
    record_backing_disk_payload_trace,
    resolve_backing_trace_payloads,
    write_canonical_backing_state,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state

_SAMPLE = {
    "backing_track_scope": "Single section",
    "backing_track_single_section": "Chorus",
    "backing_track_multi_sections": ["Verse", "Chorus"],
    "backing_track_loops": 4,
    "backing_track_bpm": 108,
    "backing_groove_style": "Jazz swing",
    "backing_volume": 0.9,
    "backing_time_signature": "3/4",
    "backing_time_signature_override": True,
    "backing_quick_section": "Chorus",
}


_PHASE_C_PAUSED = "Phase C backing persistence paused for page-sync recovery"


class TestBackingTrackState(unittest.TestCase):
    def test_a_local_persist_prepare_preserves_edits(self) -> None:
        session: dict = {}
        write_canonical_backing_state(session, _SAMPLE, reason="setup")
        session["backing_track_bpm"] = 120
        session["backing_groove_style"] = "Rock groove"
        mark_backing_user_edit(session)
        flush_backing_edits(session, reason="backing_edit")
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_bpm"], 120)
        self.assertEqual(session["backing_groove_style"], "Rock groove")
        self.assertEqual(session["backing_track_state"]["backing_track_bpm"], 120)
        self.assertTrue(is_backing_user_dirty(session))

    def test_a_prepare_seeds_from_canonical(self) -> None:
        session = {"backing_track_state": {**_SAMPLE, "last_write_reason": "cloud"}}
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_bpm"], 108)
        self.assertEqual(session["backing_groove_style"], "Jazz swing")
        self.assertEqual(session["backing_track_scope"], "Single section")

    def test_b_cross_device_cloud_restore(self) -> None:
        session: dict = {"backing_track_bpm": 100, "backing_groove_style": "Auto"}
        cloud = {
            "backing_track_state": dict(_SAMPLE),
            "music_workspace_state": {"backing_filters": dict(_SAMPLE)},
        }
        self.assertTrue(apply_cloud_backing_state_if_allowed(session, cloud))
        self.assertEqual(session["backing_track_bpm"], 108)
        self.assertEqual(session["backing_groove_style"], "Jazz swing")
        self.assertFalse(is_backing_locally_dirty(session))

    @unittest.skip(_PHASE_C_PAUSED)
    def test_b_disk_blob_round_trip(self) -> None:
        st = MagicMock()
        st.session_state = dict(_SAMPLE)
        write_canonical_backing_state(st.session_state, _SAMPLE, reason="setup")
        blob = build_music_disk_state(st)
        self.assertIn("backing_track_state", blob)
        meta = blob.get("music_workspace_state") or {}
        self.assertEqual(meta.get("backing_filters", {}).get("backing_track_bpm"), 108)
        self.assertEqual(meta.get("backing_filters", {}).get("backing_groove_style"), "Jazz swing")

        st2 = MagicMock()
        st2.session_state = {}
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        self.assertEqual(st2.session_state.get("backing_track_bpm"), 108)
        self.assertEqual(st2.session_state.get("backing_groove_style"), "Jazz swing")

    def test_c_stale_cloud_blocked_when_user_dirty(self) -> None:
        session = {**_SAMPLE, "backing_track_bpm": 130}
        mark_backing_user_edit(session)
        cloud = {"backing_track_state": dict(_SAMPLE)}
        self.assertFalse(apply_cloud_backing_state_if_allowed(session, cloud))
        self.assertEqual(session["backing_track_bpm"], 130)

    def test_spurious_dirty_does_not_block_cloud_restore(self) -> None:
        session = {
            "backing_track_bpm": 100,
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            BACKING_DIRTY_KEY: True,
        }
        cloud = {
            "backing_track_state": dict(_SAMPLE),
            "music_workspace_state": {"backing_filters": dict(_SAMPLE)},
        }
        self.assertTrue(apply_cloud_backing_state_if_allowed(session, cloud))
        self.assertEqual(session["backing_track_bpm"], 108)
        self.assertFalse(is_backing_user_dirty(session))

    def test_pending_sync_alone_does_not_mark_user_dirty(self) -> None:
        session = {
            "backing_track_bpm": 100,
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
        }
        mark_backing_pending_sync(session)
        prepare_backing_page(session)
        self.assertFalse(is_backing_user_dirty(session))
        self.assertNotIn("local_edit_preserve", (session.get("backing_track_state") or {}).get("last_write_reason", ""))

    def test_flush_without_user_intent_does_not_block_restore(self) -> None:
        session = {
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            "backing_track_bpm": 100,
        }
        flush_backing_edits(session, reason="backing_edit")
        cloud = {
            "backing_track_state": dict(_SAMPLE),
            "music_workspace_state": {"backing_filters": dict(_SAMPLE)},
        }
        self.assertTrue(apply_cloud_backing_state_if_allowed(session, cloud))
        self.assertEqual(session["backing_track_bpm"], 108)

    def test_d_navigation_does_not_clear_backing_filters(self) -> None:
        session = dict(_SAMPLE)
        write_canonical_backing_state(session, _SAMPLE, reason="setup")
        session["studio_page"] = "practice"
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_bpm"], 108)

    def test_e_ami_return_restores_backing_filters(self) -> None:
        session: dict = {}
        source = {
            "source_page": "backing",
            "widget_params": {
                "backing_track_scope": "Full song",
                "backing_track_bpm": 95,
                "backing_groove_style": "Bossa Nova",
                "backing_track_loops": 3,
            },
        }
        apply_backing_source_state_from_ami(session, source)
        self.assertEqual(session["backing_track_scope"], "Full song")
        self.assertEqual(session["backing_track_bpm"], 95)
        self.assertEqual(session["backing_groove_style"], "Bossa nova")
        self.assertEqual(session["backing_track_loops"], 3)
        self.assertFalse(session.get(BACKING_DIRTY_KEY))

    def test_backing_edit_bypasses_post_restore_block(self) -> None:
        from suite_user_persistence import _cloud_autosave_blocked_reason

        st = MagicMock()
        st.session_state = {}
        state = {"backing_track_state": dict(_SAMPLE)}
        self.assertIsNone(
            _cloud_autosave_blocked_reason(st, "music", state, save_reason="backing_edit")
        )

    def test_autosave_preserves_canonical_bpm_without_dirty(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "last_write_reason": "backing_edit",
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Ballad",
        }
        commit_backing_state_from_session(session, reason="autosave")
        self.assertEqual(session["backing_track_state"]["backing_track_bpm"], 108)
        self.assertEqual(session["backing_track_bpm"], 108)
        self.assertEqual(session["backing_groove_style"], "Jazz swing")

    def test_coerce_prefers_canonical_over_song_default(self) -> None:
        session = {"backing_track_state": {**_SAMPLE, "last_write_reason": "cloud_restore"}}
        apply_cloud_backing_state_if_allowed(
            session,
            {
                "backing_track_state": session["backing_track_state"],
                "music_workspace_state": {"backing_filters": session["backing_track_state"]},
            },
        )
        session.pop("backing_groove_style", None)
        groove = coerce_backing_groove_for_widget(session, default_groove="Ballad")
        self.assertEqual(groove, "Jazz swing")

    def test_hard_refresh_playback_defaults_seed_from_canonical(self) -> None:
        from songs.playback_defaults import apply_backing_defaults_for_song, canonicalize_backing_defaults_for_song

        session = {"backing_track_state": {**_SAMPLE, "last_write_reason": "cloud_restore"}}
        prepare_backing_page(session)
        st = MagicMock()
        st.session_state = session
        sync_id = "pk::Pop::Song — Artist"
        bpm, groove = apply_backing_defaults_for_song(
            st,
            song_id=sync_id,
            default_bpm=100,
            default_groove="Ballad",
        )
        self.assertEqual(bpm, 108)
        self.assertEqual(groove, "Jazz swing")
        self.assertEqual(st.session_state["backing_track_scope"], "Single section")
        self.assertEqual(st.session_state["backing_track_loops"], 4)

        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=100,
            active_song_groove="Ballad",
            active_song_meter="4/4",
        )
        self.assertFalse(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 108)
        self.assertEqual(canon["applied_groove"], "Jazz swing")

    def test_autosave_after_playback_default_clobber_preserves_scope(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "last_write_reason": "backing_edit",
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Ballad",
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
        }
        commit_backing_state_from_session(session, reason="autosave")
        self.assertEqual(session["backing_track_state"]["backing_track_bpm"], 108)
        self.assertEqual(session["backing_track_state"]["backing_track_scope"], "Single section")
        self.assertEqual(session["backing_track_state"]["backing_track_loops"], 4)
        self.assertEqual(session["backing_track_scope"], "Single section")
        self.assertEqual(session["backing_track_loops"], 4)

    def test_prepare_canonical_over_song_default_clobber(self) -> None:
        session = {
            "backing_track_state": {**_SAMPLE, "last_write_reason": "cloud_restore"},
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            "backing_quick_section": "Full song",
            "backing_time_signature": "4/4",
            "backing_time_signature_override": False,
            BACKING_WIDGETS_SEEDED_KEY: True,
        }
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_scope"], "Single section")
        self.assertEqual(session["backing_track_loops"], 4)
        self.assertEqual(session["backing_quick_section"], "Chorus")

    def test_prepare_session_backing_wins_over_stale_canonical(self) -> None:
        session = {
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Verse",
            "backing_track_loops": 1,
            "backing_quick_section": "Verse",
            "backing_track_bpm": 120,
            "backing_groove_style": "Rock groove",
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_scope": "Full song",
                "backing_track_loops": 2,
                "last_write_reason": "cloud_restore",
            },
            BACKING_WIDGETS_SEEDED_KEY: True,
        }
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_scope"], "Single section")
        self.assertEqual(session["backing_track_loops"], 1)
        self.assertEqual(session["backing_track_state"]["backing_track_scope"], "Single section")
        self.assertEqual(session["backing_track_state"]["backing_track_loops"], 1)
        self.assertEqual(session["backing_track_state"]["last_write_reason"], "session_backing_wins")

    def test_meter_hard_refresh_seeds_from_canonical(self) -> None:
        from songs.meter_state import BACKING_METER_KEY, BACKING_METER_OVERRIDE_KEY, apply_backing_meter_for_song

        session = {
            "backing_track_state": {
                **_SAMPLE,
                "last_write_reason": "cloud_restore",
            }
        }
        prepare_backing_page(session)
        st = MagicMock()
        st.session_state = session
        applied, override, _default = apply_backing_meter_for_song(
            st,
            song_id="pk::Pop::Song — Artist",
            default_time_signature="4/4",
        )
        self.assertEqual(applied, "3/4")
        self.assertTrue(override)
        self.assertEqual(st.session_state[BACKING_METER_KEY], "3/4")
        self.assertTrue(st.session_state[BACKING_METER_OVERRIDE_KEY])

    def test_loops_one_persists_through_backing_edit(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_loops": 2,
                "last_write_reason": "backing_edit",
            },
            "backing_track_loops": 1,
            "backing_track_scope": "Full song",
        }
        commit_backing_state_from_session(session, reason="backing_edit")
        self.assertEqual(session["backing_track_state"]["backing_track_loops"], 1)
        self.assertEqual(session["backing_track_loops"], 1)

    def test_gather_syncs_quick_section_to_scope(self) -> None:
        session = {
            "backing_quick_section": "Chorus",
            "backing_track_scope": "Full song",
        }
        filters = gather_backing_filters(session)
        self.assertEqual(filters["backing_track_scope"], "Single section")
        self.assertEqual(filters["backing_track_single_section"], "Chorus")
        self.assertEqual(filters["backing_quick_section"], "Chorus")

    def test_commit_canonical_blob_only_does_not_mutate_widget_keys(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_scope": "Full song",
                "backing_track_loops": 2,
                "last_write_reason": "cloud",
            },
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            "backing_time_signature": "4/4",
            "backing_time_signature_override": False,
            "backing_track_bpm": 100,
            "backing_groove_style": "Ballad",
        }
        before = {key: session[key] for key in BACKING_DURABLE_WIDGET_KEYS if key in session}
        commit_backing_canonical_blob_only(session, reason="post_render")
        after = {key: session[key] for key in BACKING_DURABLE_WIDGET_KEYS if key in session}
        self.assertEqual(before, after)
        self.assertEqual(session["backing_track_state"]["backing_track_scope"], "Full song")
        self.assertEqual(session["backing_track_state"]["backing_track_loops"], 2)
        self.assertEqual(session["backing_track_state"]["backing_track_bpm"], 100)

    def test_backing_prepare_durable_before_step1_widgets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        src = (repo_root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        backing_block = src.split('elif _studio_page == "backing":', 1)[1]
        prepare_idx = backing_block.find("prepare_backing_durable_widgets")
        step1_idx = backing_block.find("_render_backing_playback_setup_panel")
        self.assertGreater(prepare_idx, -1, "prepare_backing_durable_widgets missing on backing page")
        self.assertGreater(step1_idx, prepare_idx, "prepare must run before Step 1 widgets")

    def test_backing_step2_does_not_prepare_durable_widgets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        src = (repo_root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        step2_body = src.split("def _render_backing_step2_playback_action", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn(
            "prepare_backing_durable_widgets",
            step2_body,
            "Step 2 must not write widget keys after Step 1 widgets render",
        )
        self.assertNotIn("prepare_backing_scope_for_widget", step2_body)

    @unittest.skip(_PHASE_C_PAUSED)
    def test_workspace_envelope_populates_all_backing_filters(self) -> None:
        st = MagicMock()
        st.session_state = dict(_SAMPLE)
        write_canonical_backing_state(st.session_state, _SAMPLE, reason="backing_edit")
        blob = build_music_disk_state(st)
        bf = (blob.get("music_workspace_state") or {}).get("backing_filters") or {}
        self.assertEqual(bf.get("backing_track_scope"), "Single section")
        self.assertEqual(bf.get("backing_track_single_section"), "Chorus")
        self.assertEqual(bf.get("backing_track_loops"), 4)
        self.assertEqual(bf.get("backing_track_bpm"), 108)
        self.assertEqual(bf.get("backing_groove_style"), "Jazz swing")
        self.assertEqual(bf.get("backing_time_signature"), "3/4")
        self.assertTrue(bf.get("backing_time_signature_override"))
        self.assertEqual(bf.get("backing_quick_section"), "Chorus")
        top = blob.get("backing_track_state") or {}
        self.assertEqual(top.get("backing_track_loops"), 4)
        ws_session = st.session_state.get("music_workspace_state") or {}
        session_bf = ws_session.get("backing_filters") or {}
        self.assertEqual(session_bf.get("backing_track_loops"), 4)

    def test_envelope_from_canonical_when_state_blob_missing_key(self) -> None:
        session = dict(_SAMPLE)
        write_canonical_backing_state(session, _SAMPLE, reason="backing_edit")
        filters = backing_filters_for_workspace_envelope(session, state_blob={"core": {}})
        self.assertEqual(filters["backing_track_loops"], 4)
        self.assertEqual(filters["backing_track_bpm"], 108)

    def test_trace_envelope_from_local_workspace_state(self) -> None:
        session = dict(_SAMPLE)
        write_canonical_backing_state(session, _SAMPLE, reason="backing_edit")
        session["music_workspace_state"] = {
            "backing_filters": dict(_SAMPLE),
        }
        trace = collect_backing_persistence_trace(
            session,
            envelope_payload={"music_workspace_state": session["music_workspace_state"]},
            cloud_payload={"backing_track_state": dict(_SAMPLE)},
        )
        self.assertEqual(trace["backing_filters_loops"], 4)
        self.assertEqual(trace["backing_filters_bpm"], 108)
        self.assertEqual(trace["cloud_payload_backing_loops"], 4)
        self.assertEqual(trace["cloud_payload_backing_bpm"], 108)

    def test_resolve_trace_envelope_prefers_canonical_over_stale_workspace(self) -> None:
        from backing_track_state import resolve_backing_trace_payloads

        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_scope": "Single section",
                "backing_track_single_section": "Intro",
                "backing_track_loops": 1,
                "backing_time_signature": "2/4",
                "backing_time_signature_override": True,
                "last_write_reason": "backing_edit",
            },
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Intro",
            "backing_track_loops": 1,
            "backing_time_signature": "2/4",
            "backing_time_signature_override": True,
            "music_workspace_state": {
                "backing_filters": {
                    "backing_track_scope": "Full song",
                    "backing_track_loops": 2,
                    "backing_time_signature": "4/4",
                }
            },
        }
        envelope_payload, _cloud = resolve_backing_trace_payloads(MagicMock(), session)
        bf = (envelope_payload.get("music_workspace_state") or {}).get("backing_filters") or {}
        self.assertEqual(bf.get("backing_track_scope"), "Single section")
        self.assertEqual(bf.get("backing_track_loops"), 1)
        self.assertEqual(bf.get("backing_time_signature"), "2/4")
        self.assertEqual(session.get("_backing_filters_source"), "canonical")

    @unittest.skip(_PHASE_C_PAUSED)
    def test_autosave_envelope_uses_widget_values_when_canonical_stale(self) -> None:
        st = MagicMock()
        st.session_state = {
            **_SAMPLE,
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_scope": "Single section",
                "backing_track_single_section": "Intro",
                "backing_track_loops": 1,
                "backing_time_signature": "2/4",
                "backing_time_signature_override": True,
                "last_write_reason": "backing_edit",
            },
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Intro",
            "backing_track_loops": 1,
            "backing_time_signature": "2/4",
            "backing_time_signature_override": True,
            "music_workspace_state": {
                "backing_filters": {
                    "backing_track_scope": "Full song",
                    "backing_track_loops": 2,
                    "backing_time_signature": "4/4",
                    "backing_time_signature_override": False,
                }
            },
        }
        blob = build_music_disk_state(st)
        bf = (blob.get("music_workspace_state") or {}).get("backing_filters") or {}
        self.assertEqual(bf.get("backing_track_scope"), "Single section")
        self.assertEqual(bf.get("backing_track_single_section"), "Intro")
        self.assertEqual(bf.get("backing_track_loops"), 1)
        self.assertEqual(bf.get("backing_time_signature"), "2/4")
        self.assertTrue(bf.get("backing_time_signature_override"))
        self.assertEqual(st.session_state.get("_backing_filters_source"), "canonical")

    @unittest.skip(_PHASE_C_PAUSED)
    def test_autosave_preserves_canonical_in_envelope(self) -> None:
        st = MagicMock()
        st.session_state = {
            **_SAMPLE,
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_loops": 7,
                "last_write_reason": "backing_edit",
            },
            "backing_track_loops": 2,
            "backing_track_scope": "Full song",
        }
        blob = build_music_disk_state(st)
        bf = (blob.get("music_workspace_state") or {}).get("backing_filters") or {}
        self.assertEqual(bf.get("backing_track_loops"), 2)
        self.assertEqual(bf.get("backing_track_bpm"), 108)

    def test_prepare_does_not_clobber_seeded_widgets(self) -> None:
        session = {
            "backing_track_state": {**_SAMPLE, "last_write_reason": "cloud"},
            "backing_track_scope": "Full song",
            "backing_track_loops": 1,
            "backing_time_signature": "2/4",
            "backing_time_signature_override": True,
            BACKING_WIDGETS_SEEDED_KEY: True,
        }
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_scope"], "Full song")
        self.assertEqual(session["backing_track_loops"], 1)
        self.assertEqual(session["backing_time_signature"], "2/4")
        self.assertTrue(session["backing_time_signature_override"])

    def test_gather_reads_per_song_slider_bpm_key(self) -> None:
        session = {
            "backing_track_bpm::pk__Pop__Song": 125,
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Verse",
            "backing_track_loops": 3,
            "backing_groove_style": "Rock groove",
        }
        filters = gather_backing_filters(session)
        self.assertEqual(filters["backing_track_bpm"], 125)
        self.assertEqual(session["backing_track_bpm"], 125)

    def test_classify_dell_widget_canonical_mismatch(self) -> None:
        trace = {
            "backing_widget_bpm": 125,
            "backing_canonical_bpm": 108,
            "backing_payload_bpm": 108,
            "backing_cloud_bpm": 108,
        }
        self.assertEqual(
            classify_backing_sync_failure_class(trace),
            "dell_widget_canonical_mismatch",
        )

    def test_classify_phone_restore_overwrite_defaults(self) -> None:
        trace = {
            "backing_widget_bpm": 100,
            "backing_cloud_bpm": 125,
            "backing_restore_source": "cloud_restore",
            "backing_widget_scope": "Full song",
            "backing_widget_loops": 2,
            "backing_widget_quick_section": "Full song",
        }
        self.assertEqual(
            classify_backing_sync_failure_class(trace),
            "phone_restore_overwrite_defaults",
        )

    def test_classify_rendered_canonical_mismatch_scope(self) -> None:
        trace = {
            "backing_widget_bpm": 130,
            "backing_canonical_bpm": 130,
            "backing_payload_bpm": 130,
            "backing_cloud_bpm": 130,
            "backing_widget_canonical_mismatch": True,
            "backing_rendered_scope": "Full song",
            "backing_canonical_scope": "Single section",
        }
        self.assertEqual(
            classify_backing_sync_failure_class(trace),
            "rendered_canonical_mismatch",
        )

    def test_bind_rendered_widgets_reconciles_stale_per_song_slider(self) -> None:
        sync_id = "pk::Pop::Song — Artist"
        slider_key = f"backing_track_bpm::{sync_id.replace(':', '_').replace('/', '_').replace(' ', '_')}"
        session = {
            "backing_track_state": {**_SAMPLE, "backing_track_bpm": 130, "last_write_reason": "cloud"},
            "backing_track_bpm": 130,
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Chorus",
            "backing_track_loops": 3,
            "backing_groove_style": "Rock groove",
            slider_key: 100,
            BACKING_WIDGETS_SEEDED_KEY: True,
        }
        trace = bind_backing_rendered_widgets_from_canonical(session, sync_id=sync_id, default_bpm=100)
        self.assertEqual(session[slider_key], 130)
        self.assertEqual(trace["backing_rendered_bpm"], 130)
        self.assertFalse(trace["backing_widget_canonical_mismatch"])
        self.assertEqual(session["_backing_render_bind_reason"], "rendered_canonical_mismatch")

    def test_trace_reports_rendered_widget_keys(self) -> None:
        sync_id = "pk::Pop::Song — Artist"
        slider_key = f"backing_track_bpm::{sync_id.replace(':', '_').replace('/', '_').replace(' ', '_')}"
        session = dict(_SAMPLE)
        write_canonical_backing_state(session, _SAMPLE, reason="backing_edit")
        session[slider_key] = 100
        session["backing_track_loops"] = 1
        trace = collect_backing_persistence_trace(session, sync_id=sync_id)
        self.assertEqual(trace["backing_rendered_bpm_key"], slider_key)
        self.assertEqual(trace["backing_rendered_bpm"], 100)
        self.assertEqual(trace["backing_canonical_bpm"], 108)
        self.assertTrue(trace["backing_widget_canonical_mismatch"])
        self.assertIn("100!=108", trace["backing_rendered_bpm_vs_canonical"])

    def test_collect_rendered_trace_all_controls(self) -> None:
        sync_id = "pk::Pop::Song"
        session = {
            "backing_track_scope": "Single section",
            "backing_track_loops": 3,
            "backing_groove_style": "Rock groove",
            "backing_quick_section": "Verse",
            "backing_track_single_section": "Verse",
            "backing_time_signature": "3/4",
            "backing_time_signature_override": True,
        }
        trace = collect_rendered_backing_widget_trace(session, sync_id=sync_id)
        self.assertEqual(trace["backing_rendered_scope"], "Single section")
        self.assertEqual(trace["backing_rendered_loops"], 3)
        self.assertEqual(trace["backing_rendered_groove"], "Rock groove")
        self.assertEqual(trace["backing_rendered_quick_section"], "Verse")
        self.assertEqual(trace["backing_rendered_meter"], "3/4")
        self.assertTrue(trace["backing_rendered_meter_override"])

    def test_record_disk_payload_trace_from_envelope(self) -> None:
        session: dict = {}
        state = {
            "music_workspace_state": {
                "backing_filters": {
                    **_SAMPLE,
                    "backing_track_bpm": 125,
                }
            }
        }
        record_backing_disk_payload_trace(session, state)
        self.assertEqual(session["_music_backing_payload_bpm"], 125)

    def test_flush_after_pending_sync_captures_widget_values(self) -> None:
        session = {
            "backing_track_state": dict(_SAMPLE),
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Verse",
            "backing_track_loops": 1,
            "backing_time_signature": "2/4",
            "backing_time_signature_override": True,
            "backing_track_bpm": 120,
            "backing_groove_style": "Rock groove",
        }
        mark_backing_pending_sync(session)
        flush_backing_edits(session, reason="backing_edit")
        meta = session["backing_track_state"]
        self.assertEqual(meta["backing_track_scope"], "Single section")
        self.assertEqual(meta["backing_track_loops"], 1)
        self.assertEqual(meta["backing_time_signature"], "2/4")
        self.assertTrue(meta["backing_time_signature_override"])
        self.assertEqual(meta["backing_track_bpm"], 120)

    def test_meter_two_four_reaches_canonical_after_flush(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_time_signature": "4/4",
                "backing_time_signature_override": False,
            },
            "backing_time_signature": "2/4",
            "backing_time_signature_override": True,
            "backing_track_scope": "Single section",
            "backing_track_single_section": "Chorus",
            "backing_track_loops": 1,
        }
        flush_backing_edits(session, reason="backing_edit")
        meta = session["backing_track_state"]
        self.assertEqual(meta["backing_time_signature"], "2/4")
        self.assertTrue(meta["backing_time_signature_override"])

    @unittest.skip(_PHASE_C_PAUSED)
    def test_apply_backing_meter_preserves_non_default_without_override_flag(self) -> None:
        from songs.meter_state import (
            BACKING_METER_KEY,
            BACKING_METER_OVERRIDE_KEY,
            apply_backing_meter_for_song,
        )

        session = {
            BACKING_METER_KEY: "2/4",
            BACKING_METER_OVERRIDE_KEY: False,
            "_last_backing_meter_song": "pk::Pop::Song — Artist",
        }
        st = MagicMock()
        st.session_state = session
        applied, override, default = apply_backing_meter_for_song(
            st,
            song_id="pk::Pop::Song — Artist",
            default_time_signature="4/4",
        )
        self.assertEqual(applied, "2/4")
        self.assertTrue(override)
        self.assertEqual(default, "4/4")
        self.assertTrue(st.session_state[BACKING_METER_OVERRIDE_KEY])

    @unittest.skip(_PHASE_C_PAUSED)
    def test_sync_backing_meter_override_from_widget(self) -> None:
        from songs.meter_state import (
            BACKING_METER_KEY,
            BACKING_METER_OVERRIDE_KEY,
            sync_backing_meter_override_from_widget,
        )

        session = {BACKING_METER_KEY: "2/4"}
        meter, override = sync_backing_meter_override_from_widget(session, "4/4")
        self.assertEqual(meter, "2/4")
        self.assertTrue(override)
        self.assertTrue(session[BACKING_METER_OVERRIDE_KEY])

    @unittest.skip(_PHASE_C_PAUSED)
    def test_device_context_includes_timestamps_and_writer(self) -> None:
        st = MagicMock()
        st.session_state = {
            **_SAMPLE,
            "_suite_cloud_fetch_updated_at": "2026-06-09T10:00:00+00:00",
            "_suite_persist_last_save_at": "2026-06-09T10:00:05+00:00",
            "_suite_persist_last_save_cloud": True,
            "_suite_last_cloud_save_payload": {
                "music_workspace_state": {
                    "device_id": "dell-device-uuid",
                    "updated_at": "2026-06-09T10:00:05+00:00",
                    "backing_filters": dict(_SAMPLE),
                }
            },
        }
        ctx = collect_backing_device_context(st, st.session_state)
        self.assertIn("device_id", ctx)
        self.assertEqual(ctx["cloud_updated_at"], "2026-06-09T10:00:00+00:00")
        self.assertEqual(ctx["backing_last_save_at"], "2026-06-09T10:00:05+00:00")
        self.assertEqual(ctx["backing_cloud_writer_device_id"], "dell-device-uuid")

    def test_format_device_compare_includes_all_labels(self) -> None:
        trace = {label: f"val_{label}" for label in BACKING_DEVICE_COMPARE_LABELS}
        text = format_backing_device_compare_trace(trace)
        for label in BACKING_DEVICE_COMPARE_LABELS:
            self.assertIn(f"{label}: val_{label}", text)

    def test_stale_cloud_hint_rendered_differs_from_cloud(self) -> None:
        hint = classify_backing_stale_cloud_hint(
            {
                "backing_rendered_bpm": 130,
                "backing_cloud_bpm": 100,
                "cloud_updated_at": "2026-06-09T09:00:00+00:00",
                "local_updated_at": "2026-06-09T10:00:00+00:00",
            }
        )
        self.assertEqual(hint, "local_newer_than_cloud_fetch")

    def test_trace_includes_device_fields_when_st_passed(self) -> None:
        st = MagicMock()
        st.session_state = dict(_SAMPLE)
        write_canonical_backing_state(st.session_state, _SAMPLE, reason="backing_edit")
        st.session_state["_suite_cloud_fetch_updated_at"] = "2026-06-09T10:00:00+00:00"
        cloud_payload = {
            "backing_track_state": dict(_SAMPLE),
            "music_workspace_state": {"backing_filters": dict(_SAMPLE)},
        }
        trace = collect_backing_persistence_trace(
            st.session_state,
            cloud_payload=cloud_payload,
            st=st,
        )
        self.assertIn("device_id", trace)
        self.assertEqual(trace["cloud_updated_at"], "2026-06-09T10:00:00+00:00")
        self.assertEqual(trace["backing_cloud_scope"], "Single section")
        self.assertEqual(trace["backing_cloud_loops"], 4)

    def test_resolve_trace_cloud_prefers_last_write_payload(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_scope": "Single section",
                "backing_track_loops": 1,
                "backing_time_signature": "2/4",
                "backing_time_signature_override": True,
            },
            "_suite_persist_last_save_cloud": True,
            "_suite_last_cloud_save_payload": {
                "backing_track_state": {
                    "backing_track_scope": "Single section",
                    "backing_track_loops": 1,
                    "backing_time_signature": "2/4",
                },
                "music_workspace_state": {
                    "backing_filters": {
                        "backing_track_scope": "Single section",
                        "backing_track_loops": 1,
                        "backing_time_signature": "2/4",
                    }
                },
            },
        }
        _envelope, cloud = resolve_backing_trace_payloads(MagicMock(), session)
        trace = collect_backing_persistence_trace(session, cloud_payload=cloud)
        self.assertEqual(trace["cloud_payload_backing_scope"], "Single section")
        self.assertEqual(trace["cloud_payload_backing_loops"], 1)
        self.assertEqual(trace["cloud_payload_backing_meter"], "2/4")
        self.assertEqual(session.get("_backing_cloud_payload_source"), "last_write")


if __name__ == "__main__":
    unittest.main()

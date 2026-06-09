"""Tests for canonical Backing Track page state (Phase C acceptance A–E)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from backing_track_state import (
    BACKING_DIRTY_KEY,
    BACKING_DURABLE_WIDGET_KEYS,
    apply_backing_source_state_from_ami,
    apply_cloud_backing_state_if_allowed,
    coerce_backing_groove_for_widget,
    backing_filters_for_workspace_envelope,
    collect_backing_persistence_trace,
    commit_backing_canonical_blob_only,
    commit_backing_state_from_session,
    flush_backing_edits,
    gather_backing_filters,
    is_backing_locally_dirty,
    mark_backing_local_edit,
    prepare_backing_page,
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


class TestBackingTrackState(unittest.TestCase):
    def test_a_local_persist_prepare_preserves_edits(self) -> None:
        session: dict = {}
        write_canonical_backing_state(session, _SAMPLE, reason="setup")
        session["backing_track_bpm"] = 120
        session["backing_groove_style"] = "Rock groove"
        mark_backing_local_edit(session)
        flush_backing_edits(session, reason="backing_edit")
        prepare_backing_page(session)
        self.assertEqual(session["backing_track_bpm"], 120)
        self.assertEqual(session["backing_groove_style"], "Rock groove")
        self.assertEqual(session["backing_track_state"]["backing_track_bpm"], 120)
        self.assertTrue(is_backing_locally_dirty(session))

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

    def test_c_stale_cloud_blocked_when_locally_dirty(self) -> None:
        session = {**_SAMPLE, "backing_track_bpm": 130}
        mark_backing_local_edit(session)
        cloud = {"backing_track_state": dict(_SAMPLE)}
        self.assertFalse(apply_cloud_backing_state_if_allowed(session, cloud))
        self.assertEqual(session["backing_track_bpm"], 130)

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
        self.assertEqual(session["backing_track_bpm"], 108)
        self.assertEqual(session["backing_track_scope"], "Single section")

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

    def test_loops_one_persists_through_autosave(self) -> None:
        session = {
            "backing_track_state": {
                **_SAMPLE,
                "backing_track_loops": 1,
                "last_write_reason": "backing_edit",
            },
            "backing_track_loops": 2,
            "backing_track_scope": "Full song",
        }
        commit_backing_state_from_session(session, reason="autosave")
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
        self.assertEqual(bf.get("backing_track_loops"), 7)
        self.assertEqual(bf.get("backing_track_bpm"), 108)


if __name__ == "__main__":
    unittest.main()

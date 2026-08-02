"""Cold reboot must not emit false song_edit or page_change cloud writes."""

from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import MagicMock, patch

from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_restore_phase import MUSIC_RESTORE_PHASE_COMPLETE_KEY, complete_music_restore_phase
from music_startup_save_suppression import (
    STARTUP_SUPPRESSION_ARMED_KEY,
    record_hydrated_canonical_fingerprint,
    run_late_startup_restore_guard,
    should_suppress_music_workspace_save,
)
from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint
from music_workspace_hydration import mark_workspace_blob_hydrated
from workspace_revision import workspace_revision_from_blob


def _cloud_payload(rev: int) -> dict:
    return {
        "core": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "studio_page": "practice",
            "instrument": "Saxophone",
            "level": "Advanced",
            "focus": "Tone",
            "display_key": "C minor",
        },
        "active_song_state": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "instrument": "Saxophone",
            "level": "Advanced",
            "focus": "Tone",
            "display_key": "C minor",
            "music_source": "catalog",
            "guitar_capo_shape_key": "G",
            "last_write_reason": "cloud_restore",
            "selected_song": {"title": "Hevenu Shalom Aleichem", "label": "Hevenu — fmt"},
        },
        "backing_track_state": {
            "backing_track_bpm": 88,
            "backing_groove_style": "swing",
            "backing_transport_status": "idle",
            "last_write_reason": "cloud_restore",
        },
        "practice_state": {
            "practice_minutes": 30,
            "practice_groove_style": "bossa",
            "last_write_reason": "cloud_restore",
        },
        "practice_workspace_state": {
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "music_workspace_state": {
            "workspace_revision": rev,
            "studio_page": "practice",
            "updated_at": "2026-01-01T00:00:00Z",
            "active_song": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "source_type": "catalog",
                "music_source": "catalog",
            },
            "backing_filters": {
                "backing_track_bpm": 88,
                "backing_groove_style": "swing",
                "backing_transport_status": "playing",
            },
            "practice_filters": {
                "practice_minutes": 30,
                "practice_groove_style": "bossa",
            },
        },
        "workspace_revision": rev,
    }


def _noisy_session_defaults(payload: dict) -> dict:
    """Simulate widget/reconcile defaults that differ from cloud until alignment."""
    return {
        "_music_workspace_blob_hydrated": True,
        "_suite_last_cloud_fetch_payload": payload,
        "studio_page": "practice",
        "instrument": "Saxophone",
        "level": "Advanced",
        "focus": "Tone",
        "display_key": "C minor",
        "active_catalog_pick_key": "Traditional::Hevenu Shalom Aleichem",
        "active_music_source": "catalog",
        "backing_track_bpm": 120,
        "backing_groove_style": "straight",
        "backing_transport_status": "playing",
        "practice_minutes": 15,
        "practice_groove_style": "swing",
        "backing_track_state": {
            "backing_track_bpm": 120,
            "backing_groove_style": "straight",
            "backing_transport_status": "playing",
            "last_write_reason": "widget_seed",
        },
        "practice_state": {
            "practice_minutes": 15,
            "practice_groove_style": "swing",
            "last_write_reason": "widget_seed",
        },
        "active_song_state": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "instrument": "Saxophone",
            "music_source": "catalog",
            "last_write_reason": "widget_seed",
            "selected_song": {"title": "Hevenu Shalom Aleichem", "label": "different label"},
        },
        "music_workspace_state": copy.deepcopy(payload["music_workspace_state"]),
    }


class StartupSaveSuppressionTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_page_change_suppressed_while_armed(self) -> None:
        ss: dict = {STARTUP_SUPPRESSION_ARMED_KEY: True}
        suppress, why = should_suppress_music_workspace_save(ss, "page_change")
        self.assertTrue(suppress)
        self.assertIn("page_change", why)

    def test_cold_reboot_no_upsert_when_canonical_matches(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        rev = 113
        payload = _cloud_payload(rev)
        ss = _noisy_session_defaults(payload)
        record_hydrated_canonical_fingerprint(ss, payload, stage="test:hydrate")
        st = MagicMock()
        st.session_state = ss

        cloud_calls: list[object] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        def _build_after_align(_st: object) -> dict:
            from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

            align_authoritative_canonical_from_hydrated(ss, payload)
            return payload

        with patch(
            "music_persistent_state.build_music_disk_state",
            side_effect=_build_after_align,
        ), patch(
            "suite_cloud_state.save_cloud_full_session",
            side_effect=_save_cloud,
        ), patch("music_egress_strict_save.bump_cloud_write_count", return_value=1):
            mark_workspace_blob_hydrated(ss)
            from music_startup_save_suppression import finalize_startup_canonical_alignment

            finalize_startup_canonical_alignment(st, stage="test:early")
            complete_music_restore_phase(ss)
            run_late_startup_restore_guard(st)

            from music_persistent_state import (
                flush_active_song_edits_and_save,
                maybe_flush_deferred_page_change_save,
                maybe_flush_pending_active_song_edits,
            )

            ss["_suite_deferred_page_change_save"] = "practice"
            maybe_flush_deferred_page_change_save(st)
            maybe_flush_pending_active_song_edits(st)
            flush_active_song_edits_and_save(st, reason="song_edit")
            from music_workspace_cloud_save import force_music_workspace_save

            force_music_workspace_save(st, reason="page_change", build_state=lambda _s: payload)
            force_music_workspace_save(st, reason="song_edit", build_state=lambda _s: payload)

        self.assertEqual(cloud_calls, [])
        self.assertTrue(ss.get("startup_fingerprint_matches"))
        self.assertTrue(ss.get("startup_suppression_released"))
        self.assertEqual(ss.get("startup_revision_loaded"), rev)
        self.assertEqual(ss.get("startup_revision_final"), rev)
        self.assertEqual(workspace_revision_from_blob(payload), rev)
        self.assertTrue(ss.get(MUSIC_RESTORE_PHASE_COMPLETE_KEY))
        self.assertTrue(ss.get("startup_write_suppressed"))
        self.assertIsNone(ss.get("_suite_deferred_page_change_save"))
        hydrated_fp = workspace_canonical_content_fingerprint(payload)
        self.assertEqual(ss.get("post_restore_canonical_fingerprint"), hydrated_fp)


if __name__ == "__main__":
    unittest.main()

"""Cold reboot must not emit false song_edit cloud writes."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_restore_phase import MUSIC_RESTORE_PHASE_COMPLETE_KEY, complete_music_restore_phase
from music_startup_save_suppression import (
    record_hydrated_canonical_fingerprint,
    run_late_startup_restore_guard,
)
from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint
from music_workspace_hydration import mark_workspace_blob_hydrated
from workspace_revision import workspace_revision_from_blob


def _cloud_payload(rev: int) -> dict:
    return {
        "core": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "studio_page": "Creative",
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
        },
        "music_workspace_state": {
            "workspace_revision": rev,
            "studio_page": "Creative",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "workspace_revision": rev,
    }


class StartupSaveSuppressionTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_cold_reboot_no_upsert_when_canonical_matches(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        rev = 113
        payload = _cloud_payload(rev)

        ss: dict = {
            "_music_workspace_blob_hydrated": True,
            "_suite_last_cloud_fetch_payload": payload,
            "studio_page": "Creative",
            "instrument": "Saxophone",
            "level": "Advanced",
            "focus": "Tone",
            "display_key": "C minor",
            "active_catalog_pick_key": "Traditional::Hevenu Shalom Aleichem",
        }
        record_hydrated_canonical_fingerprint(ss, payload, stage="test:hydrate")
        st = MagicMock()
        st.session_state = ss

        cloud_calls: list[object] = []
        tx_count = 0

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        def _force_save(*_a: object, **kwargs: object) -> bool:
            nonlocal tx_count
            from music_workspace_cloud_save import force_music_workspace_save

            reason = str(kwargs.get("reason") or "song_edit")
            tx_count += 1
            return force_music_workspace_save(st, reason=reason, build_state=lambda _s: payload)

        with patch("music_persistent_state.build_music_disk_state", return_value=payload), patch(
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
                maybe_flush_pending_active_song_edits,
            )

            maybe_flush_pending_active_song_edits(st)
            flush_active_song_edits_and_save(st, reason="song_edit")
            _force_save(reason="song_edit")

        self.assertEqual(cloud_calls, [])
        self.assertTrue(ss.get("startup_fingerprint_matches"))
        self.assertTrue(ss.get("startup_suppression_armed"))
        self.assertTrue(ss.get("startup_suppression_released"))
        self.assertEqual(ss.get("startup_revision_loaded"), rev)
        self.assertEqual(workspace_revision_from_blob(payload), rev)
        self.assertTrue(ss.get(MUSIC_RESTORE_PHASE_COMPLETE_KEY))
        self.assertTrue(ss.get("startup_write_suppressed"))
        self.assertEqual(ss.get("_suite_persist_last_save_reason"), None)
        tx = ss.get("_music_workspace_save_transaction")
        if isinstance(tx, dict):
            self.assertNotEqual(tx.get("raw_save_reason"), "song_edit")


if __name__ == "__main__":
    unittest.main()

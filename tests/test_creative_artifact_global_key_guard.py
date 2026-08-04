"""Creative artifact saves must not mutate global display_key."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from active_song_state import write_canonical_active_song_state
from creative_artifact_global_key_guard import (
    VIOLATION_CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION,
    audit_payload_global_keys,
    canonical_global_key_snapshot,
    collect_creative_artifact_global_key_diagnostics,
    freeze_global_keys_for_creative_artifact_save,
)
from creative_mission_artifact_persistence import (
    SAVE_REASON_MISSION_EXAMPLE,
    handle_user_mission_example_artifact_saved,
)
from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY, default_creative_workspace_state
from improvisation_missions import MISSION_EXAMPLE_KEY
from mission_backing_handoff_persistence import (
    arm_mission_backing_handoff_page_change,
    begin_mission_backing_handoff,
)
from music_persistent_state import build_music_disk_state
from suite_user_persistence import _local_dirty_key


class TestCreativeArtifactGlobalKeyGuard(unittest.TestCase):
    def _session_cm_with_stale_dm(self) -> dict[str, Any]:
        ss: dict[str, Any] = {
            "developer_mode": True,
            "startup_suppression_released": True,
            "instrument": "Piano",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "display_key": "Dm",
            "chart_key": "Dm",
            "concert_key": "Dm",
            "active_catalog_pick_key": "Traditional::Hevenu Shalom Aleichem",
            "selected_song": {
                "title": "Hevenu Shalom Aleichem",
                "artist": "Traditional",
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "key": "Cm",
            },
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            MISSION_EXAMPLE_KEY: {
                "mission": "test",
                "variant": "normal",
                "motif": {"notes": ["C"], "display": "C"},
                "key_center": "Cm",
            },
            "_script_run_seq": 7,
            _local_dirty_key("music"): True,
        }
        write_canonical_active_song_state(
            ss,
            {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "display_key": "Cm",
                "instrument": "Piano",
                "level": "Intermediate",
                "focus": "Melody",
                "selected_song": ss["selected_song"],
                "music_source": "catalog",
            },
            reason="test_setup",
            local_edit=False,
        )
        return ss

    def test_freeze_snapshot_without_mutating_live_session_keys(self) -> None:
        ss = self._session_cm_with_stale_dm()
        live_before = str(ss.get("display_key"))
        result = freeze_global_keys_for_creative_artifact_save(
            ss,
            save_reason=SAVE_REASON_MISSION_EXAMPLE,
            caller="test",
        )
        self.assertTrue(result.get("frozen"))
        self.assertTrue(result.get("snapshot_only"))
        self.assertFalse(result.get("reverted"))
        self.assertEqual(ss.get("display_key"), live_before)
        self.assertEqual(result.get("frozen_snapshot", {}).get("display_key"), "Cm")
        diag = collect_creative_artifact_global_key_diagnostics(ss)
        writes = diag.get("writes") or []
        self.assertTrue(any(w.get("field") == "display_key" and not w.get("reverted") for w in writes))

    def test_apply_frozen_overlay_puts_cm_in_payload_not_session(self) -> None:
        ss = self._session_cm_with_stale_dm()
        freeze_global_keys_for_creative_artifact_save(
            ss,
            save_reason=SAVE_REASON_MISSION_EXAMPLE,
            caller="test",
        )
        from creative_artifact_global_key_guard import apply_frozen_global_keys_to_payload

        payload = {"core": {"display_key": "Dm"}, "session": {"display_key": "Dm"}, "active_song_state": {}}
        apply_frozen_global_keys_to_payload(ss, payload)
        self.assertEqual(payload["core"]["display_key"], "Cm")
        self.assertEqual(ss.get("display_key"), "Dm")

    def test_freeze_reverts_stale_session_display_key_before_artifact_save(self) -> None:
        ss = self._session_cm_with_stale_dm()
        result = freeze_global_keys_for_creative_artifact_save(
            ss,
            save_reason=SAVE_REASON_MISSION_EXAMPLE,
            caller="test",
        )
        self.assertTrue(result.get("frozen"))
        self.assertEqual(ss.get("display_key"), "Dm")
        self.assertEqual(result.get("frozen_snapshot", {}).get("display_key"), "Cm")

    def test_mission_example_save_payload_keeps_cm_display_key(self) -> None:
        ss = self._session_cm_with_stale_dm()
        with patch(
            "creative_mission_artifact_persistence.request_mission_artifact_cloud_save",
            return_value=True,
        ):
            handle_user_mission_example_artifact_saved(ss, interaction="test_generate")
        st = MagicMock()
        st.session_state = ss
        ss["_suite_pending_save_reason"] = SAVE_REASON_MISSION_EXAMPLE
        freeze_global_keys_for_creative_artifact_save(
            ss,
            save_reason=SAVE_REASON_MISSION_EXAMPLE,
            caller="test_build",
        )
        payload = build_music_disk_state(st)

        self.assertEqual(str((payload.get("core") or {}).get("display_key") or ""), "Cm")
        audit_payload_global_keys(ss, payload, save_reason=SAVE_REASON_MISSION_EXAMPLE)
        diag = collect_creative_artifact_global_key_diagnostics(ss)
        codes = [v.get("code") for v in (diag.get("violations") or [])]
        self.assertNotIn(VIOLATION_CREATIVE_ARTIFACT_GLOBAL_KEY_MUTATION, codes)

    def test_handoff_arm_preserves_canonical_cm(self) -> None:
        ss = self._session_cm_with_stale_dm()
        begin_mission_backing_handoff(
            ss,
            navigation_callback="_open_mission_backing",
            with_practice_lick=True,
        )
        arm_mission_backing_handoff_page_change(ss)
        self.assertEqual(ss.get("display_key"), "Dm")
        self.assertEqual(
            (ss.get("_creative_artifact_frozen_global_snapshot") or {}).get("display_key"),
            "Cm",
        )
        self.assertEqual(canonical_global_key_snapshot(ss).get("display_key"), "Cm")


if __name__ == "__main__":
    unittest.main()

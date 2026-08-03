"""Phase 1 Item 5 — refresh / cold-reboot certification regression."""

from __future__ import annotations

import copy
import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    prepare_creative_workspace_for_render,
    sync_creative_workspace_state_before_persist,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_persistent_state import apply_music_disk_state
from music_restore_phase import complete_music_restore_phase
from music_startup_save_suppression import (
    record_hydrated_canonical_fingerprint,
    run_late_startup_restore_guard,
)
from music_workspace_hydration import mark_workspace_blob_hydrated
from phase1_item5_refresh_certification import (
    ITEM5_PANEL_HEADING,
    collect_phase1_item5_refresh_certification,
    render_phase1_item5_refresh_certification_panel,
)
from phase1_item5_revision315_fixture import (
    AUTHORITATIVE_REVISION,
    build_authoritative_music_payload,
    expected_certification_fields,
    expected_globals_rev315,
)
from workspace_revision import workspace_revision_from_blob


def _network_hydrated_session(payload: dict[str, Any]) -> dict[str, Any]:
    ss: dict[str, Any] = {}
    apply_music_disk_state(
        MagicMock(session_state=ss),
        payload,
        song_picker_catalog={},
        song_library={},
        authoritative_restore=True,
    )
    prepare_creative_workspace_for_render(ss)
    ss["_music_last_cloud_fetch_source"] = "network"
    ss["_suite_last_cloud_fetch_payload"] = copy.deepcopy(payload)
    ss["startup_revision_loaded"] = AUTHORITATIVE_REVISION
    ss["startup_revision_final"] = AUTHORITATIVE_REVISION
    ss["_suite_applied_workspace_revision"] = AUTHORITATIVE_REVISION
    ss["_phase1_item5_session_start_kind"] = "cold_reboot"
    return ss


def _run_startup_suppression_guard(ss: dict[str, Any], payload: dict[str, Any]) -> None:
    record_hydrated_canonical_fingerprint(ss, payload, stage="test:item5")
    st = MagicMock()
    st.session_state = ss
    mark_workspace_blob_hydrated(ss)
    from music_startup_save_suppression import finalize_startup_canonical_alignment

    finalize_startup_canonical_alignment(st, stage="test:item5")
    complete_music_restore_phase(ss)
    run_late_startup_restore_guard(st)


class TestPhase1Item5ColdReboot(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_full_envelope_cold_reboot_no_cloud_write(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        payload = build_authoritative_music_payload()
        self.assertEqual(workspace_revision_from_blob(payload), AUTHORITATIVE_REVISION)
        ss = _network_hydrated_session(payload)
        _run_startup_suppression_guard(ss, payload)

        cloud_calls: list[object] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        with patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud):
            sync_creative_workspace_state_before_persist(ss, reason="autosave")

        self.assertEqual(cloud_calls, [])
        expected = expected_certification_fields()
        self.assertEqual(str(ss.get("display_key") or ""), expected["globals"]["display_key"])
        self.assertEqual(str(ss.get("instrument") or ""), expected["globals"]["instrument"])
        self.assertEqual(str(ss.get("studio_page") or "").lower(), "backing")
        self.assertEqual(ss.get("ii_selected_chord"), "Ab")
        self.assertEqual(ss.get("harmony_map_chord"), "G7")
        cws = ss.get(CREATIVE_WORKSPACE_STATE_KEY)
        self.assertIsInstance(cws, dict)
        example = ss.get("improv_mission_example")
        self.assertIsInstance(example, dict)
        self.assertEqual(example.get("key_center"), "Cm")
        self.assertEqual(example.get("motif", {}).get("notes"), expected["artifact_motif_notes"])

        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertEqual(diag["fetch_source"], "network")
        self.assertEqual(diag["loaded_revision"], AUTHORITATIVE_REVISION)
        self.assertEqual(diag["current_cloud_revision"], AUTHORITATIVE_REVISION)
        self.assertFalse(diag["revision_reserved_during_startup"])
        self.assertFalse(diag["cloud_write_attempted"])
        self.assertEqual(diag["item4_violations"], [])

    def test_certification_collector_is_read_only(self) -> None:
        payload = build_authoritative_music_payload()
        ss = _network_hydrated_session(payload)
        before = copy.deepcopy(ss)
        collect_phase1_item5_refresh_certification(ss)
        self.assertEqual({k: ss[k] for k in ss if not k.startswith("_")}, {k: before[k] for k in before if not k.startswith("_")})


class TestPhase1Item5HardRefresh(unittest.TestCase):
    def test_second_streamlit_run_restores_without_save(self) -> None:
        payload = build_authoritative_music_payload()
        ss_first = _network_hydrated_session(payload)
        ss_second: dict[str, Any] = {}
        apply_music_disk_state(
            MagicMock(session_state=ss_second),
            payload,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_creative_workspace_for_render(ss_second)
        ss_second["_music_last_cloud_fetch_source"] = "network"
        ss_second["startup_revision_loaded"] = AUTHORITATIVE_REVISION
        ss_second["startup_revision_final"] = AUTHORITATIVE_REVISION
        ss_second["_suite_already_synced_before_restore"] = True
        ss_second["_phase1_item5_session_start_kind"] = "hard_refresh"

        cloud_calls: list[object] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            return None

        with patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud):
            sync_creative_workspace_state_before_persist(ss_second, reason="autosave")

        self.assertEqual(cloud_calls, [])
        self.assertEqual(ss_second.get("harmony_map_chord"), ss_first.get("harmony_map_chord"))
        self.assertEqual(ss_second.get("ii_selected_chord"), "Ab")
        self.assertEqual(str(ss_second.get("display_key") or ""), expected_globals_rev315()["display_key"])
        self.assertEqual(str(ss_second.get("studio_page") or "").lower(), "backing")


class TestPhase1Item5DevPanel(unittest.TestCase):
    def test_panel_heading_and_certification_fields(self) -> None:
        payload = build_authoritative_music_payload()
        ss = _network_hydrated_session(payload)
        st = MagicMock()
        render_phase1_item5_refresh_certification_panel(st, ss)
        md = [str(c) for c in st.markdown.call_args_list]
        self.assertTrue(any(ITEM5_PANEL_HEADING in m for m in md))
        diag = collect_phase1_item5_refresh_certification(ss)
        self.assertTrue(diag["certification_passed"])


if __name__ == "__main__":
    unittest.main()

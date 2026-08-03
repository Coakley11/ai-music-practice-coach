"""Device applied revision initialization and Item 8 CAS preflight tests."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from music_device_applied_revision import (
    set_device_applied_revision_from_authoritative_hydrate,
    resolve_device_applied_revision_for_cas,
    confirm_device_applied_revision_after_successful_cas,
)
from music_startup_save_suppression import (
    HYDRATED_CANONICAL_FP_KEY,
    record_hydrated_canonical_fingerprint,
)
from music_workspace_conditional_cloud_write import (
    prepare_music_conditional_write,
    record_conditional_write_result,
    VIOLATION_FAILED_CAS_ADVANCED_APPLIED,
)
from suite_cloud_state import save_cloud_full_session
from workspace_revision import APPLIED_REVISION_KEY as WR_APPLIED


def _payload(rev: int, *, harmony: str = "G7") -> dict[str, Any]:
    return {
        "workspace_revision": rev,
        "music_workspace_state": {
            "workspace_revision": rev,
            "harmony_map_section": "Melody A",
            "harmony_map_chord": harmony,
        },
    }


class TestHydrateInitializesAppliedRevision(unittest.TestCase):
    def test_record_hydrated_sets_applied_revision(self) -> None:
        ss: dict[str, Any] = {}
        record_hydrated_canonical_fingerprint(ss, _payload(321), stage="test:network_hydrate")
        self.assertEqual(int(ss.get(WR_APPLIED) or 0), 321)
        self.assertEqual(int(ss.get("_music_authoritative_hydrated_revision") or 0), 321)
        self.assertEqual(ss.get("_music_device_applied_revision_set_stage"), "test:network_hydrate")

    def test_fresh_reader_save_uses_hydrated_applied(self) -> None:
        ss: dict[str, Any] = {}
        record_hydrated_canonical_fingerprint(ss, _payload(321), stage="hydrate")
        state = _payload(322, harmony="Ab")
        prep = prepare_music_conditional_write(ss, state)
        with patch(
            "music_workspace_conditional_cloud_write._authoritative_row_metrics",
            return_value=(True, 321),
        ):
            prep = prepare_music_conditional_write(ss, state)
        self.assertEqual(prep["precondition_expected_revision"], 321)
        self.assertEqual(prep["candidate_revision"], 322)
        self.assertFalse(prep["create_path_selected"])
        self.assertFalse(prep["blocked_precheck"])


class TestMissingWorkspaceCreatePath(unittest.TestCase):
    def test_create_path_when_no_row_and_no_hydrate_markers(self) -> None:
        ss: dict[str, Any] = {}
        with patch(
            "music_workspace_conditional_cloud_write._authoritative_row_metrics",
            return_value=(False, 0),
        ):
            prep = prepare_music_conditional_write(ss, _payload(1))
        self.assertTrue(prep["create_path_selected"])
        self.assertEqual(prep["precondition_expected_revision"], 0)


class TestUninitializedAppliedExistingRow(unittest.TestCase):
    def test_row_lookup_recovers_applied_without_create(self) -> None:
        ss: dict[str, Any] = {HYDRATED_CANONICAL_FP_KEY: "abc123"}
        ss["startup_revision_loaded"] = 321
        with patch(
            "music_workspace_conditional_cloud_write._authoritative_row_metrics",
            return_value=(True, 321),
        ):
            prep = prepare_music_conditional_write(ss, _payload(322))
        self.assertFalse(prep["create_path_selected"])
        self.assertEqual(prep["precondition_expected_revision"], 321)


class TestFailedCasPreservesApplied(unittest.TestCase):
    def test_failed_cas_abandons_reservation_and_keeps_applied(self) -> None:
        ss = {WR_APPLIED: 321, "_music_reserved_write_revision": 326}
        prep = prepare_music_conditional_write(ss, _payload(326))
        prep["applied_revision_before_prep"] = 321
        cas = {
            "accepted": False,
            "rows_affected": 0,
            "write_mode": "conflict",
            "conditional_write_attempted": True,
            "reason": "conditional_patch_zero_rows",
        }
        record_conditional_write_result(ss, prep=prep, cas=cas, saved=False)
        self.assertEqual(int(ss.get(WR_APPLIED) or 0), 321)
        self.assertTrue(ss.get("_phase1_item8_stale_write_diag", {}).get("reservation_abandoned"))
        self.assertNotIn("_music_reserved_write_revision", ss)
        violations = ss.get("_phase1_item8_stale_write_violations") or []
        self.assertNotIn(VIOLATION_FAILED_CAS_ADVANCED_APPLIED, violations)


class TestStaleDeviceConflict(unittest.TestCase):
    def test_stale_device_zero_row_cas(self) -> None:
        ss = {WR_APPLIED: 321}
        prep = prepare_music_conditional_write(ss, _payload(322, harmony="Cm"))
        self.assertEqual(prep["precondition_expected_revision"], 321)


class TestConfirmedWriteUpdatesApplied(unittest.TestCase):
    def test_confirm_after_cas_bumps_applied(self) -> None:
        ss = {WR_APPLIED: 321}
        confirm_device_applied_revision_after_successful_cas(ss, 322)
        self.assertEqual(int(ss.get(WR_APPLIED) or 0), 322)
        self.assertEqual(ss.get("_music_device_applied_revision_source"), "cas_write_confirmed")


class TestSaveCloudFullSessionHydratedPhone(unittest.TestCase):
    def test_hydrated_phone_save_cas_expected_321(self) -> None:
        mock_storage = MagicMock()
        mock_storage.normalize_app_key = lambda app: app
        mock_storage.save_current_state_conditional_cas.return_value = {
            "accepted": True,
            "rows_affected": 1,
            "write_mode": "conditional_patch",
            "conditional_write_attempted": True,
            "unconditional_upsert_attempted": False,
        }
        ss: dict[str, Any] = {}
        record_hydrated_canonical_fingerprint(ss, _payload(321), stage="cloud_hydrate")
        state = _payload(322, harmony="Ab")

        with patch("suite_storage_config.cloud_storage_enabled", return_value=True):
            with patch("suite_storage_config.get_cloud_config", return_value=object()):
                with patch("suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")):
                    with patch("suite_cloud_state._streamlit_session", return_value=ss):
                        with patch("suite_cloud_state._cloud_storage_app_id", return_value="music"):
                            with patch(
                                "music_workspace_conditional_cloud_write._authoritative_row_metrics",
                                return_value=(True, 321),
                            ):
                                result = save_cloud_full_session("music", state)

        self.assertTrue(result.success)
        kw = mock_storage.save_current_state_conditional_cas.call_args.kwargs
        self.assertEqual(kw["expected_workspace_revision"], 321)
        self.assertEqual(kw["candidate_workspace_revision"], 322)


if __name__ == "__main__":
    unittest.main()

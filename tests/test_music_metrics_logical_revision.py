"""Unified metrics logical revision — Item 8 revision surface unification."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from music_metrics_logical_revision import (
    FILTER_MUSIC_WORKSPACE_STATE,
    FILTER_TOP_LEVEL,
    LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE,
    LOGICAL_SOURCE_TOP_LEVEL,
    build_cas_patch_filter_params,
    resolve_logical_stored_revision,
    revision_for_authoritative_hydrate,
    sync_metrics_revision_surfaces,
)
from music_workspace_conditional_cloud_write import (
    ITEM8_VIOLATIONS_CURRENT_ATTEMPT_KEY,
    VIOLATION_CAS_EXPECTED_ZERO,
    prepare_music_conditional_write,
    record_conditional_write_result,
)
from workspace_revision import APPLIED_REVISION_KEY


def _blob(rev: int) -> dict[str, Any]:
    return {
        "workspace_revision": rev,
        "music_workspace_state": {"workspace_revision": rev, "harmony_map_chord": "G7"},
    }


class TestResolveLogicalStoredRevision(unittest.TestCase):
    def test_top_level_absent_blob_valid(self) -> None:
        m = {"full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        self.assertEqual(r["logical_revision_source"], LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE)
        self.assertEqual(r["selected_cas_filter_path"], FILTER_MUSIC_WORKSPACE_STATE)
        self.assertFalse(r["stored_top_level_present"])

    def test_top_level_zero_blob_valid(self) -> None:
        m = {"workspace_revision": 0, "full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        self.assertEqual(r["selected_cas_filter_path"], FILTER_MUSIC_WORKSPACE_STATE)
        self.assertTrue(r["stored_top_level_present"])
        self.assertFalse(r["top_level_consistent_with_blob"])

    def test_top_level_null_key_present_blob_valid(self) -> None:
        m = {"workspace_revision": None, "full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        self.assertEqual(r["selected_cas_filter_path"], FILTER_MUSIC_WORKSPACE_STATE)

    def test_top_level_stale_blob_valid(self) -> None:
        m = {"workspace_revision": 323, "full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        self.assertEqual(r["logical_revision_source"], LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE)
        self.assertIn("music_workspace_state", r["selected_cas_filter_path"])

    def test_top_level_and_blob_equal(self) -> None:
        m = {"workspace_revision": 321, "full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        self.assertEqual(r["logical_revision_source"], LOGICAL_SOURCE_TOP_LEVEL)
        self.assertEqual(r["selected_cas_filter_path"], FILTER_TOP_LEVEL)
        self.assertTrue(r["top_level_consistent_with_blob"])

    def test_divergent_positive_prefers_blob(self) -> None:
        m = {"workspace_revision": 400, "full_session": _blob(321)}
        r = resolve_logical_stored_revision(m)
        self.assertEqual(r["logical_revision"], 321)
        params, field, resolved = build_cas_patch_filter_params(m, 321)
        self.assertIn("music_workspace_state", field)
        self.assertEqual(resolved["logical_revision_source"], LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE)

    def test_filter_path_matches_source(self) -> None:
        for metrics, expected_substr in (
            ({"full_session": _blob(5)}, "music_workspace_state"),
            ({"workspace_revision": 5, "full_session": _blob(5)}, "metrics->>workspace_revision"),
        ):
            _params, field, resolved = build_cas_patch_filter_params(metrics, 5)
            self.assertEqual(field, resolved["selected_cas_filter_path"])
            self.assertIn(expected_substr.replace("metrics->>", "").split("->")[-1], field)


class TestSyncMetricsRevisionSurfaces(unittest.TestCase):
    def test_successful_write_syncs_all_surfaces(self) -> None:
        merged = sync_metrics_revision_surfaces({"full_session": _blob(321)}, 322)
        self.assertEqual(merged["workspace_revision"], 322)
        full = merged["full_session"]
        self.assertEqual(full["workspace_revision"], 322)
        self.assertEqual(full["music_workspace_state"]["workspace_revision"], 322)


class TestHydrateUsesLogicalRevision(unittest.TestCase):
    def test_revision_for_hydrate_prefers_cached_logical(self) -> None:
        ss = {
            "_music_cloud_metrics_logical_revision": {
                "logical_revision": 321,
                "logical_revision_source": LOGICAL_SOURCE_MUSIC_WORKSPACE_STATE,
            }
        }
        self.assertEqual(revision_for_authoritative_hydrate(ss, _blob(999)), 321)


class TestCasExpectedViolationRepair(unittest.TestCase):
    def test_repair_does_not_retain_cas_expected_zero(self) -> None:
        ss: dict[str, Any] = {}
        with patch(
            "music_workspace_conditional_cloud_write._authoritative_stored_metrics",
            return_value=(True, 321, {"full_session": _blob(321)}),
        ):
            prep = prepare_music_conditional_write(ss, {**_blob(322), "workspace_revision": 322})
        self.assertNotIn(VIOLATION_CAS_EXPECTED_ZERO, prep.get("violations_precheck") or [])

    def test_cas_expected_only_when_no_stored_revision(self) -> None:
        ss: dict[str, Any] = {}
        with patch(
            "music_workspace_conditional_cloud_write._authoritative_stored_metrics",
            return_value=(True, 0, {"full_session": {}}),
        ):
            prep = prepare_music_conditional_write(ss, _blob(1))
        self.assertIn(VIOLATION_CAS_EXPECTED_ZERO, prep.get("violations_precheck") or [])


class TestFailedCasFailClosed(unittest.TestCase):
    def test_failed_cas_abandons_reservation(self) -> None:
        ss = {APPLIED_REVISION_KEY: 321, "_music_reserved_write_revision": 323}
        prep = {"applied_revision_before_prep": 321, "device_applied_revision": 321, "violations_precheck": []}
        cas = {
            "accepted": False,
            "rows_affected": 0,
            "write_mode": "conflict",
            "conditional_write_attempted": True,
            "reason": "conditional_patch_zero_rows",
        }
        record_conditional_write_result(ss, prep=prep, cas=cas, saved=False)
        self.assertEqual(int(ss.get(APPLIED_REVISION_KEY) or 0), 321)
        self.assertNotIn("_music_reserved_write_revision", ss)


class TestSupabaseCasStaleTopLevel(unittest.TestCase):
    @patch("suite_workspace.logical_storage_app_key", return_value="music")
    @patch("suite_storage_supabase.ACTIVE_APP_KEYS", frozenset({"music"}))
    @patch("suite_storage_supabase.normalize_app_key", return_value="music")
    @patch("suite_storage_supabase._request")
    @patch("suite_storage_supabase._cloud_user_id", return_value="user-1")
    @patch("suite_storage_supabase._scoped_storage_app", return_value="music:daniel")
    def test_stale_top_level_uses_nested_patch_and_succeeds(
        self, _scoped: MagicMock, _uid: MagicMock, req: MagicMock, *_p: MagicMock
    ) -> None:
        from suite_storage_supabase import save_current_state_conditional_cas

        stored = {"workspace_revision": 323, "full_session": _blob(321)}
        req.side_effect = [
            [{"metrics": stored}],
            [{"metrics": stored}],
            [{"app": "music:daniel", "metrics": sync_metrics_revision_surfaces(stored, 322)}],
        ]
        out = save_current_state_conditional_cas(
            "music",
            metrics={"full_session": _blob(322)},
            expected_workspace_revision=321,
            candidate_workspace_revision=322,
        )
        self.assertTrue(out["accepted"])
        patch_calls = [c for c in req.call_args_list if c.args and c.args[0] == "PATCH"]
        params = patch_calls[0].kwargs.get("params") or {}
        self.assertTrue(any("music_workspace_state" in k for k in params))


if __name__ == "__main__":
    unittest.main()

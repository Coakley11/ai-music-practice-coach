"""Phase 1 Item 8 — conditional CAS cloud write tests."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from music_workspace_conditional_cloud_write import (
    prepare_music_conditional_write,
    record_conditional_write_result,
)
from suite_cloud_state import save_cloud_full_session
from workspace_revision import APPLIED_REVISION_KEY


def _payload(rev: int, *, harmony: str = "G7") -> dict[str, Any]:
    return {
        "workspace_revision": rev,
        "music_workspace_state": {
            "workspace_revision": rev,
            "harmony_map_section": "Melody A",
            "harmony_map_chord": harmony,
        },
    }


class TestItem8ConditionalCloudWrite(unittest.TestCase):
    def test_precheck_rejects_candidate_not_gt_applied(self) -> None:
        ss = {APPLIED_REVISION_KEY: 321}
        prep = prepare_music_conditional_write(ss, _payload(321, harmony="Cm"))
        self.assertTrue(prep["blocked_precheck"])
        self.assertIn("REVISION_REUSED_WITH_DIFFERENT_PAYLOAD", prep["violations_precheck"])

    def test_live_scenario_client_a_blocked_when_cloud_at_321(self) -> None:
        ss: dict[str, Any] = {APPLIED_REVISION_KEY: 319}
        state_b = _payload(321, harmony="Ab")
        state_a = _payload(322, harmony="Melody B / Cm")  # would be 322 if reserved correctly

        cas_b = {
            "accepted": True,
            "rows_affected": 1,
            "write_mode": "conditional_patch",
            "conditional_write_attempted": True,
            "unconditional_upsert_attempted": False,
        }
        self.assertTrue(cas_b["accepted"])

        prep_a = prepare_music_conditional_write(ss, _payload(321, harmony="Cm"))
        self.assertFalse(prep_a["blocked_precheck"])

        cas_a = {
            "accepted": False,
            "rows_affected": 0,
            "write_mode": "conflict",
            "conditional_write_attempted": True,
            "unconditional_upsert_attempted": False,
            "reason": "conditional_patch_zero_rows",
            "stored_workspace_revision": 321,
        }
        record_conditional_write_result(ss, prep=prep_a, cas=cas_a, saved=False)
        self.assertTrue(ss.get("_music_stale_write_blocked"))
        self.assertFalse(cas_a["accepted"])

    def test_save_cloud_full_session_music_uses_cas_not_merge_upsert(self) -> None:
        mock_storage = MagicMock()
        mock_storage.normalize_app_key = lambda app: app
        mock_storage.save_current_state_conditional_cas.return_value = {
            "accepted": True,
            "rows_affected": 1,
            "write_mode": "conditional_patch",
            "conditional_write_attempted": True,
            "unconditional_upsert_attempted": False,
        }
        state = _payload(320)
        ss: dict[str, Any] = {APPLIED_REVISION_KEY: 319}

        with patch("suite_storage_config.cloud_storage_enabled", return_value=True):
            with patch("suite_storage_config.get_cloud_config", return_value=object()):
                with patch("suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")):
                    with patch("suite_cloud_state._streamlit_session", return_value=ss):
                        with patch("suite_cloud_state._cloud_storage_app_id", return_value="music"):
                            result = save_cloud_full_session("music", state)

        self.assertTrue(result.success)
        mock_storage.save_current_state_conditional_cas.assert_called_once()
        mock_storage.save_current_state.assert_not_called()
        kw = mock_storage.save_current_state_conditional_cas.call_args.kwargs
        self.assertEqual(kw["expected_workspace_revision"], 319)
        self.assertEqual(kw["candidate_workspace_revision"], 320)

    def test_stale_conflict_returns_not_success(self) -> None:
        mock_storage = MagicMock()
        mock_storage.normalize_app_key = lambda app: app
        mock_storage.save_current_state_conditional_cas.return_value = {
            "accepted": False,
            "rows_affected": 0,
            "write_mode": "conflict",
            "conditional_write_attempted": True,
            "unconditional_upsert_attempted": False,
            "reason": "conditional_patch_zero_rows",
        }
        ss = {APPLIED_REVISION_KEY: 319}
        state = _payload(321, harmony="Cm")

        with patch("suite_storage_config.cloud_storage_enabled", return_value=True):
            with patch("suite_storage_config.get_cloud_config", return_value=object()):
                with patch("suite_cloud_state._import_storage", return_value=(mock_storage, "suite_storage_supabase")):
                    with patch("suite_cloud_state._streamlit_session", return_value=ss):
                        with patch("suite_cloud_state._cloud_storage_app_id", return_value="music"):
                            result = save_cloud_full_session("music", state)

        self.assertFalse(result.success)
        self.assertTrue(result.stale_write_blocked)
        self.assertEqual(result.failure_stage, "stale_revision_conflict")


class TestSupabaseConditionalCas(unittest.TestCase):
    def test_build_cas_filter_legacy_nested_blob(self) -> None:
        from suite_storage_supabase import build_cas_patch_filter_params, describe_cas_patch_filter

        stored = {
            "full_session": _payload(321, harmony="Ab"),
        }
        params, field = build_cas_patch_filter_params(stored, 321)
        self.assertIn("music_workspace_state", field)
        self.assertEqual(params[field], "eq.321")
        self.assertIn(
            "music_workspace_state",
            describe_cas_patch_filter(stored, 321),
        )

    def test_build_cas_filter_top_level_when_present(self) -> None:
        from suite_storage_supabase import build_cas_patch_filter_params

        stored = {"workspace_revision": 321, "full_session": _payload(321)}
        params, field = build_cas_patch_filter_params(stored, 321)
        self.assertEqual(field, "metrics->>workspace_revision")

    @patch("suite_workspace.logical_storage_app_key", return_value="music")
    @patch("suite_storage_supabase.ACTIVE_APP_KEYS", frozenset({"music"}))
    @patch("suite_storage_supabase.normalize_app_key", return_value="music")
    @patch("suite_storage_supabase._request")
    @patch("suite_storage_supabase._cloud_user_id", return_value="user-1")
    @patch("suite_storage_supabase._scoped_storage_app", return_value="music:daniel")
    def test_legacy_row_patch_succeeds_with_nested_filter(
        self, _scoped: MagicMock, _uid: MagicMock, req: MagicMock, *_p: MagicMock
    ) -> None:
        from suite_storage_supabase import save_current_state_conditional_cas

        legacy = {"full_session": _payload(321, harmony="G7")}
        req.side_effect = [
            [{"metrics": legacy}],
            [{"metrics": legacy}],
            [{"app": "music:daniel", "metrics": {**legacy, "workspace_revision": 323}}],
        ]
        out = save_current_state_conditional_cas(
            "music",
            page="creative",
            summary="s",
            metrics={"full_session": _payload(323, harmony="Ab")},
            expected_workspace_revision=321,
            candidate_workspace_revision=323,
        )
        self.assertTrue(out["accepted"])
        patch_calls = [c for c in req.call_args_list if c.args and c.args[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 1)
        params = patch_calls[0].kwargs.get("params") or {}
        self.assertTrue(
            any("music_workspace_state" in k for k in params),
            msg=f"expected nested CAS filter, got {params!r}",
        )

    @patch("suite_workspace.logical_storage_app_key", return_value="music")
    @patch("suite_storage_supabase.ACTIVE_APP_KEYS", frozenset({"music"}))
    @patch("suite_storage_supabase.normalize_app_key", return_value="music")
    @patch("suite_storage_supabase._request")
    @patch("suite_storage_supabase._cloud_user_id", return_value="user-1")
    @patch("suite_storage_supabase._scoped_storage_app", return_value="music:daniel")
    def test_zero_row_patch_is_conflict(
        self, _scoped: MagicMock, _uid: MagicMock, req: MagicMock, *_p: MagicMock
    ) -> None:
        from suite_storage_supabase import save_current_state_conditional_cas

        req.side_effect = [
            [{"metrics": {"workspace_revision": 319}}],  # stored_before
            [{"metrics": {"workspace_revision": 319}}],  # merge prior
            [],  # PATCH zero rows
            [{"metrics": {"workspace_revision": 321, "full_session": {}}}],  # stored after conflict
        ]
        out = save_current_state_conditional_cas(
            "music",
            page="creative",
            summary="s",
            metrics={"full_session": _payload(321, harmony="Cm")},
            expected_workspace_revision=319,
            candidate_workspace_revision=321,
        )
        self.assertFalse(out["accepted"])
        self.assertEqual(out["write_mode"], "conflict")
        self.assertEqual(out["rows_affected"], 0)
        methods = [c.args[0] for c in req.call_args_list]
        self.assertIn("PATCH", methods)


if __name__ == "__main__":
    unittest.main()

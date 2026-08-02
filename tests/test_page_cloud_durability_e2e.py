"""E2E cloud durability: Creative page_change upsert + authoritative refetch + fresh hydrate."""

from __future__ import annotations

import copy
import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_page_cloud_durability_trace import (
    authoritative_page_change_cloud_confirmed,
    begin_page_change_cloud_transaction,
    evaluate_authoritative_page_change_confirmation,
    page_fields_from_state,
    record_authoritative_refetch,
    record_attempted_upsert,
    record_revision_stages,
    record_supabase_response,
)
from music_persistent_state import apply_music_disk_state
from studio_nav_state import prepare_studio_nav
from suite_cloud_state import CloudSaveResult
from suite_user_persistence import _local_dirty_key


class _FakeSessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[key] = value


def _backing_at(rev: int) -> dict[str, Any]:
    return {
        "core": {"pick_key": "Traditional::Hevenu", "studio_page": "backing", "page": "backing"},
        "session": {"studio_page": "backing"},
        "studio_nav_state": {"studio_page": "backing", "page": "backing"},
        "practice_workspace_state": {"studio_page": "backing", "page": "backing"},
        "music_workspace_state": {"studio_page": "backing", "page": "backing", "workspace_revision": rev},
        "workspace_revision": rev,
    }


def _creative_at(rev: int) -> dict[str, Any]:
    blob = _backing_at(rev)
    for part in ("core", "session", "studio_nav_state", "practice_workspace_state", "music_workspace_state"):
        if isinstance(blob.get(part), dict):
            blob[part]["studio_page"] = "creative"
            blob[part]["page"] = "creative"
    blob["workspace_revision"] = rev
    blob["music_workspace_state"]["workspace_revision"] = rev
    return blob


class PageCloudDurabilityE2ETests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_authoritative_confirmation_requires_refetch_gt_startup(self) -> None:
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_phase1_write_journal_force": True,
                "startup_revision_loaded": 191,
                "_script_run_seq": 1,
                "_music_page_change_transaction_seq": 1,
            }
        )
        begin_page_change_cloud_transaction(ss, save_reason="page_change")
        creative = _creative_at(192)
        record_revision_stages(
            ss,
            canonical_revision_before=191,
            reserved_revision=192,
            revision_in_upsert_payload=192,
            startup_revision_loaded=191,
        )
        record_attempted_upsert(ss, creative, page_arg="creative", write_path="test")
        record_supabase_response(
            ss,
            cloud_result_diag={
                "save_cloud_full_session_return_value": True,
                "cloud_payload_revision": 192,
                "cloud_upsert_succeeded": True,
            },
        )
        record_authoritative_refetch(
            ss,
            creative,
            force=True,
            cache_bypassed=True,
            fetch_source="network",
        )
        detail = evaluate_authoritative_page_change_confirmation(ss, target_page="creative")
        self.assertTrue(detail.get("confirmed"))
        self.assertTrue(authoritative_page_change_cloud_confirmed(ss))
        self.assertEqual(detail.get("refetch_revision"), 192)
        self.assertTrue(detail.get("checks", {}).get("refetch_revision_gt_startup_loaded"))

    def test_stale_revision_191_not_authoritative_for_page_change(self) -> None:
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "startup_revision_loaded": 191,
                "_music_last_confirmed_cloud_revision": 191,
                "_script_run_seq": 2,
                "_music_page_change_transaction_seq": 2,
            }
        )
        begin_page_change_cloud_transaction(ss, save_reason="page_change")
        record_revision_stages(
            ss,
            canonical_revision_before=191,
            reserved_revision=191,
            revision_in_upsert_payload=191,
            startup_revision_loaded=191,
        )
        record_attempted_upsert(ss, _creative_at(191), write_path="test")
        record_authoritative_refetch(
            ss,
            _creative_at(191),
            force=True,
            cache_bypassed=True,
            fetch_source="network",
        )
        detail = evaluate_authoritative_page_change_confirmation(ss, target_page="creative")
        self.assertFalse(detail.get("confirmed"))
        self.assertFalse(detail.get("checks", {}).get("not_reusing_legacy_revision_only"))

    def test_fresh_hydration_reads_creative_after_authoritative_store(self) -> None:
        cloud_store: dict[int, dict[str, Any]] = {191: _backing_at(191)}

        def _save(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            rev = int(state.get("workspace_revision") or 0)
            cloud_store[rev] = copy.deepcopy(state)
            return CloudSaveResult(
                success=True,
                save_cloud_full_session_return_value=True,
                cloud_payload_revision=rev,
                cloud_upsert_succeeded=True,
            )

        def _load(_app: str, *, force: bool = False):
            rev = max(cloud_store.keys())
            return copy.deepcopy(cloud_store[rev]), "2026-01-01T00:00:00Z"

        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_music_workspace_blob_hydrated": True,
                "startup_revision_loaded": 191,
                _local_dirty_key("music"): True,
            }
        )
        st = MagicMock()
        st.session_state = ss

        creative = _creative_at(192)
        with ExitStack() as stack:
            for ctx in (
                patch("suite_cloud_state.save_cloud_full_session", side_effect=_save),
                patch("suite_cloud_state.load_cloud_full_session", side_effect=_load),
            ):
                stack.enter_context(ctx)
            from music_persistent_state import save_music_cloud_session

            save_music_cloud_session(st, creative, write_path="test", page="creative")
            begin_page_change_cloud_transaction(ss, save_reason="page_change")
            record_revision_stages(
                ss,
                canonical_revision_before=191,
                reserved_revision=192,
                revision_in_upsert_payload=192,
            )
            record_attempted_upsert(ss, creative, write_path="test")
            record_supabase_response(ss, cloud_result_diag={"cloud_payload_revision": 192, "save_cloud_full_session_return_value": True})
            record_authoritative_refetch(ss, _load("music", force=True)[0], force=True, cache_bypassed=True, fetch_source="network")
            evaluate_authoritative_page_change_confirmation(ss, target_page="creative")

        ss2 = _FakeSessionState({"developer_mode": True})
        st2 = MagicMock()
        st2.session_state = ss2
        payload, _ = _load("music", force=True)
        apply_music_disk_state(
            st2,
            payload,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        pages = page_fields_from_state(payload)
        self.assertEqual(pages.get("core"), "creative")
        self.assertEqual(prepare_studio_nav(ss2), "creative")
        self.assertNotIn(191, [k for k in cloud_store if k > 191 and page_fields_from_state(cloud_store[k]).get("core") == "backing"])


if __name__ == "__main__":
    unittest.main()

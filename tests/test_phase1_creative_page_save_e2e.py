"""End-to-end Creative page_change via real navigate + persist + hydrate."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_page_save_pipeline_trace import payload_pages_from_state
from music_persistent_state import apply_music_disk_state
from studio_nav_history import navigate_studio_page
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav
from suite_cloud_state import CloudSaveResult
from suite_user_persistence import _local_dirty_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class _FakeSessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _backing_cloud_blob(*, rev: int = 3) -> dict[str, Any]:
    return {
        "core": {
            "pick_key": "Traditional::Hevenu Shalom Aleichem",
            "studio_page": "backing",
            "page": "backing",
            "instrument": "Piano",
            "level": "Beginner",
            "focus": "Left-Hand Patterns",
        },
        "session": {"studio_page": "backing"},
        "studio_nav_state": {"studio_page": "backing", "page": "backing"},
        "music_workspace_state": {
            "studio_page": "backing",
            "page": "backing",
            "workspace_revision": rev,
        },
        "workspace_revision": rev,
    }


def _all_payload_pages(payload: dict[str, Any]) -> dict[str, str]:
    pages = payload_pages_from_state(payload)
    env = payload.get("music_workspace_state")
    if isinstance(env, dict):
        pages["envelope"] = str(env.get("studio_page") or env.get("page") or "").strip()
    return pages


class TestCreativePageSaveE2E(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _cloud_patches(self, ss: dict[str, Any], *, cloud_writes: list[dict[str, Any]]):
        stack = ExitStack()

        def _save_cloud(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            import copy

            cloud_writes.append(copy.deepcopy(state))
            ss["_suite_persist_last_save_cloud"] = True
            ss["_music_last_confirmed_cloud_revision"] = (
                (state.get("music_workspace_state") or {}).get("workspace_revision")
                if isinstance(state.get("music_workspace_state"), dict)
                else None
            )
            return CloudSaveResult(success=True, save_cloud_full_session_return_value=True)

        for ctx in (
            patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
            patch("suite_user_persistence.save_user_state", return_value=True),
            patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            patch("suite_storage_config.get_cloud_config", return_value=object()),
            patch("suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")),
            patch("suite_cloud_state._cloud_storage_app_id", return_value="music"),
            patch.object(suite_storage, "save_current_state"),
            patch("suite_cloud_state._streamlit_session", return_value=ss),
            patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud),
            patch("music_egress_config.skip_cloud_readback_after_write", return_value=True),
            patch(
                "music_startup_save_suppression.gate_music_workspace_save_at_startup",
                return_value=(False, ""),
            ),
        ):
            stack.enter_context(ctx)
        return stack

    def _session_from_backing_cloud(self) -> _FakeSessionState:
        blob = _backing_cloud_blob()
        ss = _FakeSessionState(
            {
                "developer_mode": True,
                "_phase1_write_journal_force": True,
                "startup_suppression_released": True,
                "_music_workspace_blob_hydrated": True,
                "_music_studio_page_restore_projection_complete": True,
                SELECTED_SONG_STATE_KEY: {"pick_key": blob["core"]["pick_key"]},
                ACTIVE_CATALOG_PICK_KEY: blob["core"]["pick_key"],
                "studio_page": "backing",
                STUDIO_NAV_STATE_KEY: dict(blob["studio_nav_state"]),
                "music_workspace_state": dict(blob["music_workspace_state"]),
                "_suite_last_cloud_fetch_payload": blob,
                _local_dirty_key("music"): True,
                "_script_run_seq": 42,
            }
        )
        return ss

    def test_navigate_creative_e2e_cloud_payload_and_hydrate(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = self._session_from_backing_cloud()
        cloud_writes: list[dict[str, Any]] = []

        with self._cloud_patches(ss, cloud_writes=cloud_writes):
            changed = navigate_studio_page(ss, "creative")
            self.assertTrue(changed)
            self.assertEqual(ss.get("studio_page"), "creative")

        self.assertGreaterEqual(len(cloud_writes), 1, "expected at least one cloud upsert")
        last = cloud_writes[-1]
        pages = _all_payload_pages(last)
        for key, val in pages.items():
            if val:
                self.assertEqual(
                    val.lower(),
                    "creative",
                    msg=f"cloud payload field {key}={val!r} in {pages}",
                )

        page_change_only = [
            w
            for w in cloud_writes
            if all(
                (v or "").lower() in ("", "creative")
                for v in _all_payload_pages(w).values()
            )
        ]
        self.assertTrue(
            any(_all_payload_pages(w).get("workspace") == "creative" for w in cloud_writes),
            f"writes={[_all_payload_pages(w) for w in cloud_writes]}",
        )
        backing_rewrites = [
            w
            for w in cloud_writes
            if any(v == "backing" for v in _all_payload_pages(w).values() if v)
        ]
        self.assertEqual(
            backing_rewrites,
            [],
            msg="later backing cloud write after creative navigation",
        )

        ss2 = _FakeSessionState({"developer_mode": True, "_script_run_seq": 43})
        st2 = MagicMock()
        st2.session_state = ss2
        apply_music_disk_state(
            st2,
            last,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        rendered = prepare_studio_nav(ss2)
        self.assertEqual(rendered, "creative")
        self.assertEqual(ss2.get("studio_page"), "creative")

        trace = ss.get("_music_page_save_pipeline_trace") or {}
        checkpoints = trace.get("checkpoints") or {}
        self.assertIn("A_post_navigate_studio_page", checkpoints)
        self.assertIn("D_build_music_disk_state_return", checkpoints)


if __name__ == "__main__":
    unittest.main()

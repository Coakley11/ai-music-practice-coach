"""Workspace isolation for Music Practice Coach (Daniel vs Ariel)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from music_workspace_paths import music_data_path, workspace_persistence_context
from suite_account import load_saved_items, remember_saved_item
from suite_user_persistence import save_user_state, state_file_path
from suite_workspace import (
    DEFAULT_WORKSPACE_ID,
    scoped_cloud_app_id,
    set_active_workspace_id,
)


class _FakeSt:
    def __init__(self, workspace: str = "daniel") -> None:
        self.session_state: dict = {}
        self.query_params: dict = {}
        set_active_workspace_id(self, workspace)


class TestMusicScopedCloudKeys(unittest.TestCase):
    def test_daniel_music_legacy_key(self) -> None:
        with patch("suite_workspace.resolve_workspace_id", return_value="daniel"):
            self.assertEqual(scoped_cloud_app_id("music"), "music")

    def test_ariel_music_namespaced_key(self) -> None:
        with patch("suite_workspace.resolve_workspace_id", return_value="ariel"):
            self.assertEqual(scoped_cloud_app_id("music"), "music__ariel")


class TestMusicSavedItemsScoping(unittest.TestCase):
    def _mock_storage(self) -> MagicMock:
        storage = MagicMock()
        storage.upsert_saved_item.return_value = {"write_mode": "upsert"}
        storage.load_saved_items.return_value = []
        return storage

    def test_ariel_insight_uses_namespaced_app(self) -> None:
        storage = self._mock_storage()
        with patch.dict(sys.modules, {"suite_storage": storage}), patch(
            "suite_account._scoped_storage_app", return_value="music__ariel"
        ):
            remember_saved_item(
                "music",
                "applied_math_insight",
                "music-insight-ariel",
                title="Ariel coach insight",
                payload={"insight_id": "music-insight-ariel"},
            )
        self.assertEqual(storage.upsert_saved_item.call_args[0][0], "music__ariel")

    def test_ariel_load_skips_legacy_music_key(self) -> None:
        storage = self._mock_storage()
        with patch.dict(sys.modules, {"suite_storage": storage}), patch(
            "suite_account._scoped_storage_app", return_value="music__ariel"
        ):
            load_saved_items(app="music", item_type="applied_math_insight", limit=10)
        storage.load_saved_items.assert_called_once_with(
            app="music__ariel", item_type="applied_math_insight", limit=10
        )


class TestMusicWorkspaceDiskIsolation(unittest.TestCase):
    def test_daniel_and_ariel_session_files_differ(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with patch("suite_workspace.DATA_DIR", data), patch("suite_user_persistence.DATA_DIR", data):
                save_user_state(
                    "music",
                    {"core": {"instrument": "Guitar", "pick_key": "daniel-song"}},
                    workspace_id="daniel",
                )
                save_user_state(
                    "music",
                    {"core": {"instrument": "Piano", "pick_key": "ariel-song"}},
                    workspace_id="ariel",
                )
                daniel_path = state_file_path("music", "daniel")
                ariel_path = state_file_path("music", "ariel")
                self.assertNotEqual(daniel_path.read_text(encoding="utf-8"), ariel_path.read_text(encoding="utf-8"))

    def test_practice_history_paths_differ_by_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with patch("suite_workspace.DATA_DIR", data), patch(
                "music_workspace_paths.DATA_DIR", data
            ):
                daniel_path = music_data_path("practice_history", "daniel")
                ariel_path = music_data_path("practice_history", "ariel")
                self.assertNotEqual(daniel_path, ariel_path)
                daniel_path.parent.mkdir(parents=True, exist_ok=True)
                ariel_path.parent.mkdir(parents=True, exist_ok=True)
                daniel_path.write_text(json.dumps([{"song": "Daniel Song"}]), encoding="utf-8")
                ariel_path.write_text(json.dumps([{"song": "Ariel Song"}]), encoding="utf-8")
                self.assertIn("Daniel Song", daniel_path.read_text(encoding="utf-8"))
                self.assertIn("Ariel Song", ariel_path.read_text(encoding="utf-8"))

    def test_chart_overrides_migrate_legacy_for_daniel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            legacy = data / "user_chart_overrides.json"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({"version": 1, "overrides": {"a|b": {}}}), encoding="utf-8")
            import music_workspace_paths as mwp

            mwp._migrated_keys.clear()
            with patch("suite_workspace.DATA_DIR", data), patch(
                "music_workspace_paths.DATA_DIR", data
            ), patch("suite_workspace.resolve_workspace_id", return_value=DEFAULT_WORKSPACE_ID):
                target = music_data_path("user_chart_overrides", DEFAULT_WORKSPACE_ID)
                self.assertTrue(target.is_file())
                payload = json.loads(target.read_text(encoding="utf-8"))
                self.assertIn("overrides", payload)


class TestMusicWorkspaceSwitchClearsSession(unittest.TestCase):
    def test_profile_switch_clears_workspace_sync_and_ami_caches(self) -> None:
        st = _FakeSt("daniel")
        st.session_state["instrument"] = "Guitar"
        st.session_state["studio_page"] = "practice"
        st.session_state["_ami_pending_insight"] = {"conclusion": "test"}
        st.session_state["_suite_workspace_synced::music"] = True
        set_active_workspace_id(st, "ariel")
        self.assertEqual(st.session_state["_suite_active_workspace_id"], "ariel")
        self.assertNotIn("_ami_pending_insight", st.session_state)
        self.assertNotIn("_suite_workspace_synced::music", st.session_state)


class TestMusicWorkspaceDiagnostics(unittest.TestCase):
    def test_persistence_context_includes_paths(self) -> None:
        with patch("suite_workspace.get_active_workspace_id", return_value="ariel"):
            ctx = workspace_persistence_context()
        self.assertEqual(ctx.get("active_workspace_id"), "ariel")
        self.assertIn("practice_history_path", ctx)
        self.assertIn("ariel", ctx["practice_history_path"])


if __name__ == "__main__":
    unittest.main()

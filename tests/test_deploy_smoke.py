"""Deploy smoke tests — catch Streamlit Cloud runtime incompatibilities before release."""

from __future__ import annotations

import inspect
import py_compile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDeploySmoke(unittest.TestCase):
    def test_key_modules_py_compile(self) -> None:
        paths = [
            REPO_ROOT / "streamlit_music_practice_app.py",
            REPO_ROOT / "music_persistent_state.py",
            REPO_ROOT / "studio_nav_history.py",
            REPO_ROOT / "suite_cloud_state.py",
            REPO_ROOT / "suite_user_persistence.py",
            REPO_ROOT / "suite_deploy_probe.py",
            REPO_ROOT / "suite_storage_config.py",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                py_compile.compile(str(path), doraise=True)

    def test_pick_restore_session_accepts_cloud_first(self) -> None:
        from suite_cloud_state import pick_restore_session

        params = inspect.signature(pick_restore_session).parameters
        self.assertIn("cloud_first", params)
        self.assertEqual(params["cloud_first"].default, True)

    def test_sync_workspace_protocol_calls_compatible_pick_restore(self) -> None:
        import suite_user_persistence as sup

        source = inspect.getsource(sup.sync_workspace_protocol)
        self.assertIn("cloud_first=", source)

    def test_suite_deploy_probe_does_not_call_config_get(self) -> None:
        text = (REPO_ROOT / "suite_deploy_probe.py").read_text(encoding="utf-8")
        self.assertNotIn("cfg.get(", text)

    def test_cloud_config_probe_handles_missing_config(self) -> None:
        from suite_deploy_probe import cloud_config_probe

        result = cloud_config_probe()
        self.assertIsInstance(result, dict)
        self.assertIn("cloud_enabled", result)
        self.assertIn("suite_user_id_set", result)
        self.assertNotIn("get", str(result.get("config_error") or ""))

    def test_import_music_persistence_stack(self) -> None:
        import music_coach_context
        import music_persistent_state
        import suite_deploy_probe

        self.assertTrue(callable(music_persistent_state.prepare_music_workspace))
        self.assertTrue(callable(suite_deploy_probe.cloud_config_probe))
        self.assertIn("music", music_coach_context.APP_ID)


if __name__ == "__main__":
    unittest.main()

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

    def test_deploy_info_build_marker_matches_persist_version(self) -> None:
        from music_persistence_trace import MUSIC_PERSIST_DEPLOY_VERSION
        from suite_deploy_probe import deploy_info

        info = deploy_info()
        self.assertEqual(info["build_marker"], MUSIC_PERSIST_DEPLOY_VERSION)
        self.assertNotIn("phase-b-nav-stable-v14", info["build_marker"])

    def test_streamlit_app_does_not_bare_render_catalog_song_data(self) -> None:
        """Bare `_catalog_song_data` in the Streamlit script dumps the full song dict."""
        text = (REPO_ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertNotRegex(
            text,
            r"(?m)^\s+_catalog_song_data\s*$",
            "Remove bare _catalog_song_data — Streamlit renders it as st.write()",
        )

    def test_streamlit_app_has_no_module_level_bare_song_dumps(self) -> None:
        """Any module-level bare name in the Streamlit script is auto-rendered via st.write."""
        import ast

        path = REPO_ROOT / "streamlit_music_practice_app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        songish = {
            "song_data",
            "selected_song",
            "active_song",
            "active_workspace",
            "current_song",
            "_catalog_song_data",
            "_catalog_song",
            "song",
            "SONG_LIBRARY",
            "SONG_PICKER_CATALOG",
            "music_workspace_state",
            "workspace_state",
            "song_library",
            "_chart_bundle",
            "ALL_SONG_RECORDS",
            "level_source_sections",
            "sections",
        }

        class _Finder(ast.NodeVisitor):
            def __init__(self) -> None:
                self.depth = 0
                self.hits: list[tuple[int, str]] = []

            def _enter(self) -> None:
                self.depth += 1

            def _exit(self) -> None:
                self.depth -= 1

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._enter()
                self.generic_visit(node)
                self._exit()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._enter()
                self.generic_visit(node)
                self._exit()

            def visit_Expr(self, node: ast.Expr) -> None:
                if self.depth == 0 and isinstance(node.value, ast.Name):
                    self.hits.append((node.lineno, node.value.id))
                self.generic_visit(node)

        finder = _Finder()
        finder.visit(tree)
        offenders = [
            (line, name)
            for line, name in finder.hits
            if name in songish or "song" in name.lower() or "workspace" in name.lower()
        ]
        self.assertEqual(
            offenders,
            [],
            f"Module-level bare expressions auto-render in Streamlit: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()

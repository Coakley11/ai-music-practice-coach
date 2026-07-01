"""Regression: Music developer UI workspace gate."""

from __future__ import annotations

import unittest

from suite_workspace import can_show_developer_tools, set_active_workspace_id


class _FakeSt:
    def __init__(self, workspace: str, *, dev_query: bool = False) -> None:
        self.session_state: dict = {}
        self.query_params = {"dev": "1"} if dev_query else {}
        set_active_workspace_id(self, workspace)  # type: ignore[arg-type]


class TestDeveloperWorkspaceGating(unittest.TestCase):
    def test_music_developer_mode_ariel_blocked(self) -> None:
        from music_persistence_trace import init_developer_mode_from_query, music_developer_mode

        st = _FakeSt("ariel", dev_query=True)
        init_developer_mode_from_query(st)  # type: ignore[arg-type]
        self.assertFalse(music_developer_mode(st))  # type: ignore[arg-type]

    def test_music_developer_mode_daniel_dev(self) -> None:
        from music_persistence_trace import init_developer_mode_from_query, music_developer_mode

        st = _FakeSt("daniel", dev_query=True)
        init_developer_mode_from_query(st)  # type: ignore[arg-type]
        self.assertTrue(music_developer_mode(st))  # type: ignore[arg-type]
        self.assertTrue(can_show_developer_tools(st=st))  # type: ignore[arg-type]

    def test_source_ownership_diagnostics_any_workspace_with_dev_query(self) -> None:
        from backing_source_navigation import source_ownership_diagnostics_enabled

        st = _FakeSt("ariel", dev_query=True)
        self.assertTrue(source_ownership_diagnostics_enabled(st=st))  # type: ignore[arg-type]
        self.assertFalse(can_show_developer_tools(st=st))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

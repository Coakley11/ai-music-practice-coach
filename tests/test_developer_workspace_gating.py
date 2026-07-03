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
    def test_music_developer_mode_ariel_with_dev_query(self) -> None:
        from music_persistence_trace import init_developer_mode_from_query, music_developer_mode

        st = _FakeSt("ariel", dev_query=True)
        init_developer_mode_from_query(st)  # type: ignore[arg-type]
        self.assertTrue(music_developer_mode(st))  # type: ignore[arg-type]
        self.assertFalse(can_show_developer_tools(st=st))  # type: ignore[arg-type]

    def test_music_developer_mode_ariel_normal_blocked(self) -> None:
        from music_persistence_trace import music_developer_mode

        st = _FakeSt("ariel", dev_query=False)
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

    def test_source_ownership_diagnostics_survives_missing_song_title(self) -> None:
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession
        from backing_source_navigation import render_source_ownership_dev_table

        sess = CreativeSession(
            session_id="diag-test",
            tool_type="entry_style_jam",
            entry_mode="Style Jam Mode",
            style="Bossa Nova",
        )

        class _DiagSt(_FakeSt):
            def caption(self, *_a, **_k) -> None:
                return None

            def warning(self, *_a, **_k) -> None:
                return None

            def table(self, data) -> None:
                self.last_table = data

            def expander(self, *_a, **_k):
                return self

            def __enter__(self):
                return self

            def __exit__(self, *_a) -> None:
                return None

        st = _DiagSt("daniel", dev_query=True)
        st.session_state[CREATIVE_SESSION_KEY] = sess.to_dict()
        st.session_state["studio_page"] = "creative"
        render_source_ownership_dev_table(st, st.session_state)  # type: ignore[arg-type]
        rows = {row["field"]: row["value"] for row in st.last_table}
        self.assertEqual(rows["creative_session.tool"], "entry_style_jam")
        self.assertEqual(rows["creative_session.title"], "Bossa Nova")


if __name__ == "__main__":
    unittest.main()

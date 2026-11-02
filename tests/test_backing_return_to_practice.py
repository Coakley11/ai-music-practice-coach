"""Issue 7: Backing offers Return to Practice for Catalog / Custom / Composition songs."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest import mock

# The function is exercised from its *source*, not by importing streamlit_music_practice_app: importing
# that module executes the whole Streamlit script against whatever bare-mode session_state earlier tests
# left behind, which made these tests order-dependent (TypeError at the chart-bundle gate).
APP_SOURCE = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
FUNC_NAME = "_render_backing_return_to_practice_action"


def _function_source() -> str:
    for node in ast.parse(APP_SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name == FUNC_NAME:
            return ast.get_source_segment(APP_SOURCE, node)
    raise AssertionError(FUNC_NAME + " not found")


class TestReturnToPractice(unittest.TestCase):
    def _run(self, source: str, practice_loop: bool = False):
        st = mock.MagicMock()
        nav = mock.Mock()
        ns = {"st": st, "navigate_studio_page": nav, "feature_label": lambda _k, default: default}
        exec(compile(_function_source(), "<return_to_practice>", "exec"), ns)  # noqa: S102 - our own source
        ctx = mock.Mock(source=source)
        with mock.patch("backing_context.get_backing_context", return_value=ctx), mock.patch(
            "backing_source_navigation.practice_loop_backing_is_active", return_value=practice_loop
        ), mock.patch("studio_page_persistence.save_page_snapshot"):
            st.session_state = {}
            st.button.return_value = True
            st.rerun.side_effect = RuntimeError("rerun")
            try:
                ns[FUNC_NAME]()
            except RuntimeError:
                pass
        return st, nav

    def test_ordinary_song_sources_get_the_button_and_navigate_without_loading_a_song(self) -> None:
        for source in ("regular_song", "custom_progression", "composition_song", ""):
            st, nav = self._run(source)
            self.assertEqual(st.button.call_count, 1, source)
            nav.assert_called_once()
            self.assertEqual(nav.call_args.args[1], "practice", source)

    def test_mission_creative_and_practice_loop_keep_their_own_return(self) -> None:
        for source, loop in (("mission", False), ("song_improv", False), ("entry_jam", False), ("regular_song", True)):
            st, nav = self._run(source, practice_loop=loop)
            self.assertEqual(st.button.call_count, 0, (source, loop))
            nav.assert_not_called()

    def test_it_is_navigation_only(self) -> None:
        src = _function_source()
        for forbidden in ("apply_cpl_session_progression", "activate_catalog_song", "restore_last_custom", "set_composition_source"):
            self.assertNotIn(forbidden, src)

    def test_it_is_rendered_on_the_backing_page(self) -> None:
        self.assertIn("_render_backing_return_source_action()" + chr(10) + "    _render_backing_return_to_practice_action()", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()

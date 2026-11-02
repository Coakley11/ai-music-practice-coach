"""Issue 7: Backing offers Return to Practice for Catalog / Custom / Composition songs."""

from __future__ import annotations

import inspect
import unittest
from unittest import mock


class TestReturnToPractice(unittest.TestCase):
    def _fn(self):
        import streamlit_music_practice_app as app

        return app._render_backing_return_to_practice_action

    def _run(self, source: str, practice_loop: bool = False):
        import streamlit_music_practice_app as app

        ctx = mock.Mock(source=source)
        with mock.patch("backing_context.get_backing_context", return_value=ctx), mock.patch(
            "backing_source_navigation.practice_loop_backing_is_active", return_value=practice_loop
        ), mock.patch.object(app, "st") as st, mock.patch.object(app, "navigate_studio_page") as nav, mock.patch(
            "studio_page_persistence.save_page_snapshot"
        ):
            st.session_state = {}
            st.button.return_value = True
            st.rerun.side_effect = RuntimeError("rerun")
            try:
                self._fn()()
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
        src = inspect.getsource(self._fn())
        for forbidden in ("apply_cpl_session_progression", "activate_catalog_song", "restore_last_custom", "set_composition_source"):
            self.assertNotIn(forbidden, src)

    def test_it_is_rendered_on_the_backing_page(self) -> None:
        import streamlit_music_practice_app as app

        text = inspect.getsource(app)
        self.assertIn("_render_backing_return_source_action()\n    _render_backing_return_to_practice_action()", text)


if __name__ == "__main__":
    unittest.main()

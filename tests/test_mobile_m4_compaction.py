"""Mobile M4 — vertical-scroll compaction; desktop layout preserved."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path


class TestMobileM4Shell(unittest.TestCase):
    def test_m4_shell_token(self) -> None:
        from responsive_layout import MOBILE_M4_SHELL, PHONE_PILL_GRID_MIN_PCT

        self.assertEqual(MOBILE_M4_SHELL, "m4-scroll-compact-v1")
        self.assertGreaterEqual(PHONE_PILL_GRID_MIN_PCT, 28)
        self.assertLessEqual(PHONE_PILL_GRID_MIN_PCT, 36)


class TestMobileM4Css(unittest.TestCase):
    def test_compaction_css_covers_priority_surfaces(self) -> None:
        from app_ui import _mobile_m4_compaction_css

        css = _mobile_m4_compaction_css()
        self.assertIn("m4-scroll-compact-v1", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("genre_filter_pill_grid", css)
        self.assertIn("min-width: 30%", css)
        self.assertIn("composer_journey_rail", css)
        self.assertIn('data-studio-page="composer"', css)
        self.assertIn("cpl_chord_pick_grid", css)
        self.assertIn("cpl_bar_duration_row", css)
        self.assertIn("ui-custom-builder-head", css)

    def test_inject_hooks_m4_into_theme(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_m4_compaction", src)


class TestMobileM4GenreFilterGrid(unittest.TestCase):
    def test_genre_pills_use_keyed_grid_and_row_major(self) -> None:
        import streamlit_music_practice_app as app

        src = inspect.getsource(app._render_genre_filter_pills)
        self.assertIn('st.container(key="genre_filter_pill_grid")', src)
        self.assertIn('st.container(key="genre_filter_controls_head")', src)
        self.assertIn("iter_ui_rows", src)
        self.assertIn("genre_filter_label", src)
        self.assertIn("toggle_genre_filter", src)
        self.assertIn("request_clear_browse_filters", src)

    def test_genre_filter_reuses_canonical_visual_style(self) -> None:
        from practice_studio import genre_filter_label, genre_filter_pill_css, genre_visual_style

        pop = genre_visual_style("Pop")
        self.assertEqual(pop["emoji"], "🎤")
        self.assertIn("linear-gradient", pop["gradient"])
        self.assertTrue(pop["soft"].startswith("#"))
        self.assertEqual(genre_filter_label("Pop"), "🎤 Pop")
        self.assertEqual(genre_filter_label("Rock"), "🤘 Rock")
        self.assertEqual(genre_filter_label("Jazz"), "🎷 Jazz")
        self.assertEqual(genre_filter_label("Jewish"), "✡ Jewish")
        css = genre_filter_pill_css()
        self.assertIn("genre_pill_Pop", css)
        self.assertIn("genre_pill_Rock", css)
        self.assertIn(pop["soft"], css)
        self.assertIn(pop["gradient"], css)
        # Selectors must keep song_library_panel scoped on BOTH pill and more keys.
        self.assertIn(
            '.st-key-song_library_panel [class*="st-key-genre_pill_Pop"]',
            css,
        )
        self.assertIn(
            '.st-key-song_library_panel [class*="st-key-genre_more_Pop"]',
            css,
        )
        # Guard against the comma-precedence bug that dropped panel scope.
        self.assertNotIn(
            '.st-key-song_library_panel [class*="st-key-genre_pill_Pop"], [class*="st-key-genre_more_Pop"]',
            css,
        )
        # Selected vs unselected remain distinct kinds.
        self.assertIn('button[kind="primary"]', css)
        self.assertIn('button[kind="secondary"]', css)

    def test_theme_injects_genre_pill_chrome(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_genre_filter_pill_chrome", src)


class TestMobileM4CompositionCustomWiring(unittest.TestCase):
    def test_composer_journey_and_section_nav_keyed(self) -> None:
        import composition_studio_page as comp

        journey = inspect.getsource(comp._render_journey_rail)
        self.assertIn('st.container(key="composer_journey_rail")', journey)
        nav = inspect.getsource(comp._render_section_nav_strip)
        self.assertIn('st.container(key="composer_section_nav")', nav)
        self.assertIn("iter_ui_rows", nav)

    def test_cpl_chord_and_launch_grids_keyed(self) -> None:
        src = Path("cpl_page_ui.py").read_text(encoding="utf-8")
        self.assertIn('key="cpl_chord_pick_grid"', src)
        self.assertIn('key="cpl_bar_duration_row"', src)
        self.assertIn("cpl_launch_actions_", src)
        self.assertIn("iter_ui_rows", src)
        # No ownership / PK mutation in M4 CSS module path.
        from app_ui import _mobile_m4_compaction_css

        css = _mobile_m4_compaction_css()
        self.assertNotIn("set_practice", css)
        self.assertNotIn("navigate_studio", css)


if __name__ == "__main__":
    unittest.main()

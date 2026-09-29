"""Mobile M1 — compact phone quick-nav shell; desktop art preserved; BF docked."""

from __future__ import annotations

import unittest


class TestMobileM1ResponsiveTokens(unittest.TestCase):
    def test_phone_breakpoint_constant(self) -> None:
        from responsive_layout import PHONE_MAX_WIDTH_PX, phone_media_query, wrap_phone_css

        self.assertEqual(PHONE_MAX_WIDTH_PX, 720)
        self.assertIn("720", phone_media_query())
        css = wrap_phone_css(".x { color: red; }")
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn(".x { color: red; }", css)


class TestMobileM1QuickNavCss(unittest.TestCase):
    def test_mobile_shell_marker_and_three_col(self) -> None:
        from app_ui import _mobile_quick_nav_shell_css, _quick_nav_artistic_css

        shell = _mobile_quick_nav_shell_css()
        self.assertIn("m1-compact-3col", shell)
        self.assertIn("max-width: 32.5%", shell)
        self.assertIn('data-testid="stColumn"', shell)
        self.assertIn("min-width: 30%", shell)
        self.assertIn("display: contents", shell)
        self.assertIn(".ui-nav-art-face", shell)
        self.assertIn("display: none", shell)
        full = _quick_nav_artistic_css()
        self.assertIn("m1-compact-3col", full)
        # Desktop art face rules still present outside the phone media block.
        self.assertIn(".ui-nav-art-face {", full)
        self.assertIn("Caveat", full)

    def test_mobile_labels_cover_all_top_nav_pages(self) -> None:
        from app_ui import (
            TOP_NAV_PAGE_IDS,
            _css_content_string,
            _mobile_quick_nav_label_css,
            nav_icon_button_label,
        )

        css = _mobile_quick_nav_label_css()
        for page_id in TOP_NAV_PAGE_IDS:
            self.assertIn(f"studio_quick_nav_btn_{page_id}", css)
            # Labels use CSS unicode escapes (not JSON \\uXXXX).
            self.assertIn(_css_content_string(nav_icon_button_label(page_id)), css)

    def test_navigate_studio_page_still_called_from_art_cell(self) -> None:
        import inspect

        from app_ui import _STUDIO_QUICK_NAV_OPEN_LABEL, _render_nav_art_cell

        src = inspect.getsource(_render_nav_art_cell)
        self.assertIn("navigate_studio_page(session_state, page_id)", src)
        self.assertIn("_STUDIO_QUICK_NAV_OPEN_LABEL", src)
        self.assertEqual(_STUDIO_QUICK_NAV_OPEN_LABEL, "Open")


class TestMobileM1HistoryDock(unittest.TestCase):
    def test_pin_script_phone_in_flow_desktop_gutter(self) -> None:
        import inspect

        from app_ui import _inject_studio_history_nav_pin_script

        src = inspect.getsource(_inject_studio_history_nav_pin_script)
        self.assertIn("phoneMax", src)
        # Phone: static in-flow above quick-nav (no bottom dock).
        self.assertIn("position:static", src)
        self.assertIn("studio_history_nav_row", src)
        self.assertIn("top:50vh", src)  # desktop path preserved
        self.assertIn("gutterBackLeft", src)
        self.assertNotIn("bottom:max(0.7rem", src)
        self.assertNotIn("38vh", src)

    def test_theme_css_phone_history_in_flow(self) -> None:
        import inspect

        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("studio_history_nav_row", src)
        self.assertIn("position: static", src)
        self.assertIn("ui-brand-tagline { display: none", src)


class TestMobileM1NavSemanticsUnchanged(unittest.TestCase):
    def test_quick_nav_rows_unchanged(self) -> None:
        from app_ui import QUICK_NAV_ROW_PRIMARY, QUICK_NAV_ROW_SECONDARY, TOP_NAV_PAGE_IDS

        self.assertEqual(
            set(QUICK_NAV_ROW_PRIMARY + QUICK_NAV_ROW_SECONDARY), set(TOP_NAV_PAGE_IDS)
        )
        self.assertEqual(QUICK_NAV_ROW_PRIMARY[0], "practice")
        self.assertEqual(QUICK_NAV_ROW_SECONDARY[0], "composer")

    def test_no_parallel_mobile_router(self) -> None:
        from pathlib import Path

        src = Path("app_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("mobile_navigate_studio_page", src)
        self.assertNotIn("def navigate_mobile", src)


if __name__ == "__main__":
    unittest.main()

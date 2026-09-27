"""Mobile M2 — shared phone density chrome; desktop layout preserved."""

from __future__ import annotations

import unittest


class TestMobileM2DensityTokens(unittest.TestCase):
    def test_density_tokens_and_shell_marker(self) -> None:
        from responsive_layout import (
            MOBILE_DENSITY_SHELL,
            PHONE_DENSITY_GAP,
            PHONE_MAX_WIDTH_PX,
            phone_density_css_vars,
        )

        self.assertEqual(PHONE_MAX_WIDTH_PX, 720)
        self.assertEqual(MOBILE_DENSITY_SHELL, "m2-chrome-v1")
        self.assertTrue(PHONE_DENSITY_GAP)
        vars_css = phone_density_css_vars()
        self.assertIn("--mpc-phone-gap:", vars_css)
        self.assertIn("--mpc-phone-pad-card:", vars_css)


class TestMobileM2DensityCss(unittest.TestCase):
    def test_density_css_covers_shared_surfaces(self) -> None:
        from app_ui import _mobile_density_chrome_css

        css = _mobile_density_chrome_css()
        self.assertIn("m2-chrome-v1", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn(".ui-studio-meta-badges", css)
        self.assertIn(".ui-backing-setup-context", css)
        self.assertIn(".ui-practice-meta-row", css)
        self.assertIn(".ui-creative-song-meta", css)
        self.assertIn(".ui-card", css)
        self.assertIn(".ui-page-head", css)
        self.assertIn(".ui-ctrl-section", css)
        self.assertIn("_hub_nav_actions", css)
        # Keep fact fields 2-col on phone (do not stack to 1fr).
        self.assertIn(".ui-backing-setup-fields-row", css)
        self.assertIn("repeat(2, minmax(0, 1fr))", css)

    def test_inject_hooks_density_into_theme(self) -> None:
        import inspect

        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_density_chrome", src)


class TestMobileM2HubActionsContainer(unittest.TestCase):
    def test_songs_hub_nav_uses_keyed_container(self) -> None:
        import inspect

        import streamlit_music_practice_app as app

        src = inspect.getsource(app._render_songs_hub_nav_actions)
        self.assertIn('st.container(key=f"{key_prefix}_nav_actions")', src)
        for suffix in ("_practice", "_backing", "_creative", "_karaoke", "_chord_coach"):
            self.assertIn(f"{{key_prefix}}{suffix}", src)


class TestMobileM2NavSemanticsUnchanged(unittest.TestCase):
    def test_no_ownership_or_pk_writes_in_density_module(self) -> None:
        from pathlib import Path

        src = Path("responsive_layout.py").read_text(encoding="utf-8")
        self.assertNotIn("set_practice", src)
        self.assertNotIn("navigate_studio", src)
        self.assertNotIn("session_state", src)


if __name__ == "__main__":
    unittest.main()

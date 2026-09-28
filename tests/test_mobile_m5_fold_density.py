# -*- coding: utf-8 -*-
"""Unit checks for Mobile M5 Practice/Backing/Creative fold density."""
from __future__ import annotations

import inspect
import unittest

from responsive_layout import MOBILE_M4_SHELL, MOBILE_M5_SHELL, MOBILE_DENSITY_SHELL


class MobileM5FoldDensityTests(unittest.TestCase):
    def test_shell_marker(self) -> None:
        self.assertEqual(MOBILE_M5_SHELL, "m5-fold-density-v1")
        self.assertEqual(MOBILE_M4_SHELL, "m4-scroll-compact-v1")
        self.assertEqual(MOBILE_DENSITY_SHELL, "m2-chrome-v1")

    def test_m5_css_phone_only_and_surfaces(self) -> None:
        from app_ui import _mobile_m5_fold_density_css

        css = _mobile_m5_fold_density_css()
        self.assertIn("m5-fold-density-v1", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("st-key-practice_control_panel", css)
        self.assertIn("st-key-backing_playback_panel", css)
        self.assertIn("ui-studio-script-header", css)
        self.assertIn("ui-instrument-strip", css)
        self.assertIn("practice_panel_qc_row", css)
        self.assertIn("creative_dha_qc_row", css)
        self.assertIn("practice_tools_grid_", css)
        self.assertIn("creative_lab_analysis_mode", css)
        # Must not use overly broad _qc_row matching
        self.assertNotIn('[class*="_qc_row"]', css)
        # Must not force Advanced expander open/closed
        self.assertNotIn("expanded=False", css)
        self.assertNotIn("expanded: false", css.lower())

    def test_m5_injected_from_global_chrome(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_m5_fold_density", src)

    def test_m1_m4_still_injected(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_density_chrome", src)
        self.assertIn("_inject_mobile_m4_compaction", src)

    def test_quick_controls_keyed_row(self) -> None:
        from practice_setup_controls import render_setup_quick_controls

        src = inspect.getsource(render_setup_quick_controls)
        self.assertIn('key=f"{key_prefix}_qc_row"', src)
        self.assertIn("columns(3)", src)

    def test_practice_tools_keyed_grid(self) -> None:
        from practice_tools_ui import render_practice_tools_launcher

        src = inspect.getsource(render_practice_tools_launcher)
        self.assertIn("practice_tools_grid_", src)

    def test_backing_advanced_not_forced_closed(self) -> None:
        from pathlib import Path

        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("Advanced playback settings", text)
        self.assertIn("do not force expanded=False", text)
        # Exact expander call must not pass expanded=
        needle = 'with st.expander("Advanced playback settings")'
        self.assertIn(needle, text)
        self.assertNotIn(
            'with st.expander("Advanced playback settings", expanded=False)',
            text,
        )


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Unit checks for Mobile M6 Creative/Upload/Karaoke tool density."""
from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from responsive_layout import (
    MOBILE_DENSITY_SHELL,
    MOBILE_M4_SHELL,
    MOBILE_M5_SHELL,
    MOBILE_M6_SHELL,
)


class MobileM6ToolDensityTests(unittest.TestCase):
    def test_shell_marker(self) -> None:
        self.assertEqual(MOBILE_M6_SHELL, "m6-tool-density-v1")
        self.assertEqual(MOBILE_M5_SHELL, "m5-fold-density-v1")
        self.assertEqual(MOBILE_M4_SHELL, "m4-scroll-compact-v1")
        self.assertEqual(MOBILE_DENSITY_SHELL, "m2-chrome-v1")

    def test_m6_css_phone_only_surfaces(self) -> None:
        from app_ui import _mobile_m6_tool_density_css

        css = _mobile_m6_tool_density_css()
        self.assertIn("m6-tool-density-v1", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("st-key-creative_studio_panel", css)
        self.assertIn("improv_motif_gen_actions", css)
        self.assertIn("improv_mission_gen_actions", css)
        self.assertIn("improv_style_jam_controls", css)
        self.assertIn("improv_jam_gen_controls", css)
        self.assertIn("improv_live_coach_qc_row", css)
        self.assertIn("ui-upload-studio-head", css)
        self.assertIn("karaoke_setlist_actions", css)
        self.assertIn("karaoke-lyric-panel", css)
        self.assertIn("ui-creative-section-label", css)
        self.assertIn("composer_desktop_split", css)
        self.assertIn("composer-partner-lead", css)
        self.assertIn("composer-score-wrap", css)
        self.assertIn("composer_journey_rail", css)
        self.assertIn("composer_cross_nav", css)
        self.assertIn("body:has([class*=\"st-key-composer_\"])", css)
        # Scoped keys only — no broad _qc_row matcher
        self.assertNotIn('[class*="_qc_row"]', css)
        # Must not force Advanced expander
        self.assertNotIn("expanded=False", css)
        self.assertNotIn("Advanced playback", css)

    def test_m6_injected_with_prior_slices(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_m6_tool_density", src)
        self.assertIn("_inject_mobile_m5_fold_density", src)
        self.assertIn("_inject_mobile_m4_compaction", src)
        self.assertIn("_inject_mobile_density_chrome", src)

    def test_creative_keyed_rows_present(self) -> None:
        text = Path("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        for key in (
            "improv_style_jam_controls",
            "improv_jam_gen_controls",
            "improv_motif_gen_actions",
            "improv_motif_transforms",
            "improv_motif_pattern_fields",
            "improv_motif_pattern_actions",
            "improv_mission_gen_actions",
            "improv_mission_transforms",
        ):
            self.assertIn(f'key="{key}"', text)

    def test_karaoke_keyed_rows_present(self) -> None:
        text = Path("karaoke_ui.py").read_text(encoding="utf-8")
        for key in (
            "karaoke_setlist_actions",
            "karaoke_countdown_controls",
            "karaoke_session_transport",
        ):
            self.assertIn(f'key="{key}"', text)

    def test_composition_phone_split_gated_and_keyed(self) -> None:
        text = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("@media (min-width: 721px)", text)
        self.assertIn('key="composer_library_actions"', text)
        self.assertIn('key="composer_cross_nav"', text)
        self.assertIn("composer-partner-lead", text)
        # Desktop nowrap must not apply globally on phone
        # (nowrap lives inside the desktop media query).
        desktop_gate = text.split("@media (min-width: 721px)", 1)[1]
        self.assertIn("flex-wrap: nowrap", desktop_gate)

    def test_abc_staffwidth_is_viewport_aware(self) -> None:
        text = Path("composition_melody_notation.py").read_text(encoding="utf-8")
        self.assertIn("window.innerWidth", text)
        self.assertIn("overflow-x: auto", text)
        self.assertNotIn("staffwidth: 520,", text)

    def test_backing_advanced_still_unforced(self) -> None:
        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("do not force expanded=False", text)
        self.assertNotIn(
            'with st.expander("Advanced playback settings", expanded=False)',
            text,
        )


if __name__ == "__main__":
    unittest.main()

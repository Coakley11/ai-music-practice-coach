# -*- coding: utf-8 -*-
"""Unit checks for Mobile M7 Creative/Karaoke finishing density."""
from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from responsive_layout import (
    MOBILE_DENSITY_SHELL,
    MOBILE_M4_SHELL,
    MOBILE_M5_SHELL,
    MOBILE_M6_SHELL,
    MOBILE_M7_SHELL,
)


class MobileM7FinishDensityTests(unittest.TestCase):
    def test_shell_marker(self) -> None:
        self.assertEqual(MOBILE_M7_SHELL, "m7-finish-density-v1")
        self.assertEqual(MOBILE_M6_SHELL, "m6-tool-density-v1")
        self.assertEqual(MOBILE_M5_SHELL, "m5-fold-density-v1")
        self.assertEqual(MOBILE_M4_SHELL, "m4-scroll-compact-v1")
        self.assertEqual(MOBILE_DENSITY_SHELL, "m2-chrome-v1")

    def test_m7_css_phone_only_surfaces(self) -> None:
        from app_ui import _mobile_m7_finish_density_css

        css = _mobile_m7_finish_density_css()
        self.assertIn("m7-finish-density-v1", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("improv_motif_setup_qc_row", css)
        self.assertIn("improv_mission_qc_row", css)
        self.assertIn("improv_live_coach_qc_row", css)
        self.assertIn("improv_live_coach_insight_row", css)
        self.assertIn("improv_style_jam_controls", css)
        self.assertIn("karaoke-lyric-panel", css)
        self.assertIn("karaoke-lp-lyric-line", css)
        self.assertIn("karaoke_session_transport", css)
        self.assertIn("composer-score-wrap", css)
        self.assertIn("ui-creative-section-label", css)
        # Scoped keys only — no broad _qc_row matcher
        self.assertNotIn('[class*="_qc_row"]', css)
        # Must not force Advanced expander
        self.assertNotIn("expanded=False", css)
        self.assertNotIn("Advanced playback", css)

    def test_m7_injected_with_prior_slices(self) -> None:
        from app_ui import inject_app_theme

        src = inspect.getsource(inject_app_theme)
        self.assertIn("_inject_mobile_m7_finish_density", src)
        self.assertIn("_inject_mobile_m6_tool_density", src)
        self.assertIn("_inject_mobile_m5_fold_density", src)

    def test_practice_copy_replacement(self) -> None:
        text = Path("app_ui.py").read_text(encoding="utf-8")
        self.assertIn(
            "Session goal, key behavior, and section focus shape coaching below.",
            text,
        )
        self.assertNotIn(
            "Groove and length shape coaching below.",
            text,
        )

    def test_live_coach_insight_row_keyed(self) -> None:
        text = Path("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        self.assertIn('key="improv_live_coach_insight_row"', text)

    def test_motif_abc_staffwidth_viewport_aware(self) -> None:
        text = Path("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        self.assertIn("window.innerWidth", text)
        self.assertIn("overflow-x: auto", text)
        # Fixed 520 staffwidth must not remain as the sole render path
        self.assertNotIn("staffwidth: 520, paddingbottom: 12", text)

    def test_composition_abc_still_viewport_aware(self) -> None:
        text = Path("composition_melody_notation.py").read_text(encoding="utf-8")
        self.assertIn("window.innerWidth", text)
        self.assertIn("overflow-x: auto", text)

    def test_backing_advanced_still_unforced(self) -> None:
        text = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("do not force expanded=False", text)
        self.assertNotIn(
            'with st.expander("Advanced playback settings", expanded=False)',
            text,
        )

    def test_seeded_melody_score_html_contains_containment(self) -> None:
        from composition_melody_notation import (
            build_abc_from_melody_events,
            render_abc_html,
        )

        events = [
            {"pitch": "C4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "E4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "G4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "C5", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "D4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "F4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "A4", "duration_beats": 1.0, "is_rest": False},
            {"pitch": "G4", "duration_beats": 1.0, "is_rest": False},
        ]
        abc = build_abc_from_melody_events(
            events, key="C", meter="4/4", bpm=96, title="M7 Score Proof"
        )
        self.assertIn("C", abc)
        html = render_abc_html(abc, height=240)
        self.assertIn("window.innerWidth", html)
        self.assertIn("overflow-x: auto", html)
        self.assertIn("max-width: 100%", html)
        self.assertIn("staffwidth", html)
        self.assertNotIn("staffwidth: 520,", html)


if __name__ == "__main__":
    unittest.main()

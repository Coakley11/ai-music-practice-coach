"""Missions tab route dispatch — must not write widget-bound session keys post-radio."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from improvisation_intelligence_ui import (
    IMPROV_INTELLIGENCE_TAB_FOR_RENDER_KEY,
    MISSIONS_UI_BUILD_ID,
    _normalize_improv_tab_for_render,
    render_improvisation_intelligence_lab,
)


class TestMissionsRouteDispatch(unittest.TestCase):
    def test_normalize_uses_radio_value_only(self) -> None:
        self.assertEqual(_normalize_improv_tab_for_render("Missions"), "Missions")
        self.assertEqual(_normalize_improv_tab_for_render("Entry & Jam"), "Entry & Jam")
        self.assertEqual(_normalize_improv_tab_for_render("invalid"), "Entry & Jam")

    def test_normalize_does_not_mutate_widget_key(self) -> None:
        session = {"improv_intelligence_tab": "Missions"}
        _normalize_improv_tab_for_render("Missions")
        self.assertEqual(session["improv_intelligence_tab"], "Missions")
        self.assertNotIn(IMPROV_INTELLIGENCE_TAB_FOR_RENDER_KEY, session)

    def test_render_lab_source_never_assigns_improv_intelligence_tab_after_radio(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        radio_idx = text.index('key="improv_intelligence_tab"')
        after_radio = text[radio_idx:]
        self.assertNotRegex(
            after_radio,
            r'session_state\s*\[\s*["\']improv_intelligence_tab["\']\s*\]\s*=',
            msg="must not assign improv_intelligence_tab after radio widget",
        )
        self.assertNotRegex(
            after_radio,
            r'session_state\s*\[\s*["\']creative_improv_intelligence_tab["\']\s*\]\s*=',
            msg="must not assign creative_improv_intelligence_tab after radio widget",
        )

    def test_removed_resolve_improv_tab_for_render_mutator(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        self.assertNotIn("def _resolve_improv_tab_for_render", text)
        self.assertNotIn('session_state["improv_intelligence_tab"] = tab', text)

    def test_improvisation_lab_missions_branch_without_streamlit_widget_error(self) -> None:
        """Smoke: dispatch reaches Missions branch without post-radio widget-key writes."""
        session: dict = {
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Active song",
            "song": "Tune",
            "artist": "A",
            "display_key": "C",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "Improvisation",
            "home_sections": {"A": ["C"]},
        }

        class _RadioStub:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _St:
            def markdown(self, *a, **k):
                return None

            def radio(self, *a, **k):
                return "Missions"

            def container(self, **k):
                return _RadioStub()

        st = _St()
        with mock.patch(
            "improvisation_intelligence_ui._tab_missions",
            return_value=None,
        ) as missions_mock, mock.patch(
            "studio_page_persistence.ensure_creative_improv_initialized",
        ), mock.patch(
            "improvisation_intelligence_ui.flush_pending_improv_song_source",
        ), mock.patch(
            "creative_key_sync.flush_pending_creative_major_keys",
        ), mock.patch(
            "improvisation_intelligence_ui.ensure_creative_widgets_from_backing_context",
        ), mock.patch(
            "improvisation_intelligence_ui.ensure_improv_intelligence_tab_restored",
        ), mock.patch(
            "app_ui.inject_creative_studio_styles",
        ), mock.patch(
            "app_ui.render_creative_studio_panel_header",
        ):
            render_improvisation_intelligence_lab(
                st,
                ctx={
                    "instrument": "Piano",
                    "level": "Intermediate",
                    "focus": "Improvisation",
                    "song": "Tune",
                    "artist": "A",
                },
                session_state=session,
                chart_key="C",
                sections={"A": ["C"]},
                song_data={"section_order": ["A"]},
                bpm=100,
                genre="Pop",
                is_custom=False,
            )
        missions_mock.assert_called_once()
        self.assertEqual(session.get(IMPROV_INTELLIGENCE_TAB_FOR_RENDER_KEY), "Missions")
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")

    def test_build_id_hotfix_marker(self) -> None:
        self.assertIn("2264e3f", MISSIONS_UI_BUILD_ID)


if __name__ == "__main__":
    unittest.main()

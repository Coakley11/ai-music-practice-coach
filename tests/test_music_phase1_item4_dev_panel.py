"""Item 4 dev panel — always visible under ?dev=1 Phase 1 diagnostics."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from creative_context_snapshot_persistence import (
    CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY,
    ITEM4_DEV_PANEL_HEADING,
    ITEM4_DEV_PANEL_KEYS,
    SAVE_REASON_CONTEXT_SECTION,
    collect_creative_context_snapshot_diagnostics,
    default_item4_dev_diag,
    render_item4_creative_context_snapshot_panel,
)
from music_phase1_dev_diagnostics import render_phase1_live_path_diagnostics


class TestItem4DevPanelRender(unittest.TestCase):
    def _mock_st(self) -> MagicMock:
        st = MagicMock()
        st.sidebar.expander.return_value.__enter__ = MagicMock(return_value=st)
        st.sidebar.expander.return_value.__exit__ = MagicMock(return_value=False)
        return st

    def test_default_diag_exposes_all_panel_keys_with_explicit_none(self) -> None:
        diag = default_item4_dev_diag({})
        self.assertIsNone(diag["last_user_interaction"])
        self.assertIsNone(diag["save_reason"])
        self.assertEqual(diag["violations"], [])
        for key in ITEM4_DEV_PANEL_KEYS:
            self.assertIn(key, diag)

    def test_render_panel_heading_and_keys_before_any_interaction(self) -> None:
        st = MagicMock()
        session: dict[str, Any] = {}
        render_item4_creative_context_snapshot_panel(st, session)
        md_calls = [str(c) for c in st.markdown.call_args_list]
        self.assertTrue(any(ITEM4_DEV_PANEL_HEADING in c for c in md_calls))
        captions = {str(c[0][0]) for c in st.caption.call_args_list}
        for key in ITEM4_DEV_PANEL_KEYS:
            self.assertTrue(any(f"`{key}`:" in cap for cap in captions), key)

    def test_render_panel_after_creative_context_section_change_retains_revision(self) -> None:
        st = MagicMock()
        session: dict[str, Any] = {
            CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY: {
                "last_user_interaction": "harmony_map_chord_button",
                "save_reason": SAVE_REASON_CONTEXT_SECTION,
                "payload_revision": 315,
                "cloud_write_attempted": True,
                "cloud_write_succeeded": True,
                "cloud_confirmed": True,
            },
            "display_key": "Cm",
        }
        render_item4_creative_context_snapshot_panel(st, session)
        diag = collect_creative_context_snapshot_diagnostics(session)
        self.assertEqual(diag["save_reason"], SAVE_REASON_CONTEXT_SECTION)
        self.assertEqual(diag["payload_revision"], 315)
        self.assertEqual(diag["last_user_interaction"], "harmony_map_chord_button")
        captions = " ".join(str(c[0][0]) for c in st.caption.call_args_list)
        self.assertIn("315", captions)
        self.assertIn(SAVE_REASON_CONTEXT_SECTION, captions)

    def test_phase1_expander_includes_item4_panel_when_modules_load(self) -> None:
        st = self._mock_st()
        session: dict[str, Any] = {"studio_page": "Creative"}
        render_phase1_live_path_diagnostics(st, session)
        inner = st.sidebar.expander.return_value.__enter__.return_value
        md_calls = [str(c) for c in inner.markdown.call_args_list]
        self.assertTrue(any(ITEM4_DEV_PANEL_HEADING in c for c in md_calls))

    def test_panel_survives_simulated_navigation_rerun(self) -> None:
        session: dict[str, Any] = {
            CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY: {"payload_revision": 315, "save_reason": SAVE_REASON_CONTEXT_SECTION},
        }
        for page in ("Creative", "Harmony Map", "Backing"):
            session["studio_page"] = page
            st = MagicMock()
            render_item4_creative_context_snapshot_panel(st, session)
            diag = collect_creative_context_snapshot_diagnostics(session)
            self.assertEqual(diag["payload_revision"], 315)

    def test_missing_optional_values_do_not_suppress_panel(self) -> None:
        st = MagicMock()
        session: dict[str, Any] = {"envelope_field_presence": None, "global_keys_before": None}
        render_item4_creative_context_snapshot_panel(st, session)
        self.assertGreater(st.caption.call_count, len(ITEM4_DEV_PANEL_KEYS) - 1)
        md_calls = [str(c) for c in st.markdown.call_args_list]
        self.assertTrue(any(ITEM4_DEV_PANEL_HEADING in c for c in md_calls))


if __name__ == "__main__":
    unittest.main()

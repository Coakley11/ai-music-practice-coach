"""Item 8 dev panel — always visible under ?dev=1 Phase 1 diagnostics."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from music_phase1_dev_diagnostics import render_phase1_live_path_diagnostics
from phase1_item8_stale_write_certification import (
    ITEM8_PANEL_HEADING,
    ITEM8_PANEL_KEYS,
    default_item8_dev_diag,
    render_phase1_item8_stale_write_certification_panel,
)


class TestItem8DevPanelRender(unittest.TestCase):
    def _mock_st(self) -> MagicMock:
        st = MagicMock()
        st.sidebar.expander.return_value.__enter__ = MagicMock(return_value=st)
        st.sidebar.expander.return_value.__exit__ = MagicMock(return_value=False)
        return st

    def test_default_diag_exposes_all_panel_keys_with_explicit_none(self) -> None:
        diag = default_item8_dev_diag({})
        self.assertIsNone(diag["device_applied_revision"])
        self.assertIsNone(diag["candidate_revision"])
        self.assertEqual(diag["violations"], [])
        self.assertFalse(diag["stale_write_blocked"])
        for key in ITEM8_PANEL_KEYS:
            self.assertIn(key, diag)

    def test_render_panel_heading_and_keys_on_fresh_run(self) -> None:
        st = MagicMock()
        session: dict[str, Any] = {}
        render_phase1_item8_stale_write_certification_panel(st, session)
        md_calls = [str(c) for c in st.markdown.call_args_list]
        self.assertTrue(any(ITEM8_PANEL_HEADING in c for c in md_calls))
        captions = {str(c[0][0]) for c in st.caption.call_args_list}
        for key in ITEM8_PANEL_KEYS:
            self.assertTrue(any(f"`{key}`:" in cap for cap in captions), key)

    def test_phase1_expander_includes_item8_panel_when_modules_load(self) -> None:
        st = self._mock_st()
        session: dict[str, Any] = {"studio_page": "creative"}
        render_phase1_live_path_diagnostics(st, session)
        inner = st.sidebar.expander.return_value.__enter__.return_value
        md_calls = [str(c) for c in inner.markdown.call_args_list]
        self.assertTrue(any(ITEM8_PANEL_HEADING in c for c in md_calls))

    def test_panel_survives_simulated_navigation_rerun(self) -> None:
        for page in ("creative", "backing", "Creative"):
            st = MagicMock()
            session: dict[str, Any] = {"studio_page": page, "stale_write_blocked": True}
            render_phase1_item8_stale_write_certification_panel(st, session)
            md_calls = [str(c) for c in st.markdown.call_args_list]
            self.assertTrue(any(ITEM8_PANEL_HEADING in c for c in md_calls))


if __name__ == "__main__":
    unittest.main()

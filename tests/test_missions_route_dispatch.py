"""Missions tab route dispatch (single renderer, tab resolution)."""

from __future__ import annotations

import unittest

from improvisation_intelligence_ui import (
    MISSIONS_UI_BUILD_ID,
    _resolve_improv_tab_for_render,
)


class TestMissionsRouteDispatch(unittest.TestCase):
    def test_resolve_tab_prefers_valid_radio_value(self) -> None:
        session: dict = {"improv_intelligence_tab": "Entry & Jam"}
        tab = _resolve_improv_tab_for_render(session, "Missions")
        self.assertEqual(tab, "Missions")
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")

    def test_build_id_bumped_for_deploy_probe(self) -> None:
        self.assertIn("a6962ec", MISSIONS_UI_BUILD_ID)


if __name__ == "__main__":
    unittest.main()

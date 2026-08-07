"""Return handoff must sync canonical Creative selectors before II widget restore."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from backing_context import open_backing_from_creative
from backing_creative_return_route import get_creative_return_route
from backing_source_navigation import (
    project_return_destination_to_canonical_creative_selectors,
    prepare_return_to_backing_source,
)
from creative_tab_tool_persistence import CREATIVE_WORKSPACE_STATE_KEY
from music_workflow_pending_creative_return import handle_return_to_creative_click
from studio_page_persistence import _ACTIVE_PAGE_TRACKER
from studio_page_state import (
    CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY,
    ensure_improv_entry_mode_restored,
    ensure_improv_intelligence_tab_restored,
)
from tests.test_backing_source_navigation import _style_jam_like_session
from tests.test_entry_jam_return_submode_lifecycle import (
    _jam_generator_session,
    _mission_backing_session,
)
from tests.test_song_improv_scope_authority import _mission_bridge_session


def _st_like(session: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(session_state=session)


def _stale_canonical_style_jam(session: dict[str, Any]) -> None:
    session["_creative_selector_hydration_complete"] = True
    session[CREATIVE_WORKSPACE_STATE_KEY] = {
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
    }


class TestCreativeReturnCanonicalSelectorSync(unittest.TestCase):
    def _simulate_return_prepare(self, session: dict[str, Any]) -> None:
        session["studio_page"] = "backing"
        session[_ACTIVE_PAGE_TRACKER] = "backing"
        st_mock = mock.MagicMock()
        handle_return_to_creative_click(st_mock, session)
        session.pop("_creative_restore_from_backing", None)

    def _assert_selector_state(
        self,
        session: dict[str, Any],
        *,
        entry_mode: str,
        tab: str = "Entry & Jam",
    ) -> None:
        self.assertEqual(str(session.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), tab)
        self.assertEqual(str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""), tab)
        cws = session.get(CREATIVE_WORKSPACE_STATE_KEY)
        assert isinstance(cws, dict)
        self.assertEqual(str(cws.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(str(cws.get("improv_intelligence_tab") or ""), tab)
        self.assertEqual(ensure_improv_intelligence_tab_restored(session), tab)
        self.assertEqual(ensure_improv_entry_mode_restored(session), entry_mode)

    def test_jam_generator_stale_canonical_wins_after_return(self) -> None:
        session = _jam_generator_session()
        _stale_canonical_style_jam(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        route = get_creative_return_route(session)
        assert route is not None
        self._simulate_return_prepare(session)
        self._assert_selector_state(session, entry_mode="Jam Session Generator")

    def test_entry_style_return_with_stale_jam_canonical(self) -> None:
        session = _style_jam_like_session()
        session[CREATIVE_WORKSPACE_STATE_KEY] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Entry & Jam",
        }
        session["_creative_selector_hydration_complete"] = True
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        self._simulate_return_prepare(session)
        self._assert_selector_state(session, entry_mode="Style Jam Mode")

    def test_song_based_improv_with_stale_canonical(self) -> None:
        session = _mission_bridge_session()
        session["improv_intelligence_tab"] = "Entry & Jam"
        session[CREATIVE_WORKSPACE_STATE_KEY] = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_intelligence_tab": "Missions",
        }
        session["_creative_selector_hydration_complete"] = True
        open_backing_from_creative(session, source="song_improv", st_like=_st_like(session))
        self._simulate_return_prepare(session)
        self._assert_selector_state(session, entry_mode="Song-Based Improvisation")

    def test_missions_with_stale_entry_canonical(self) -> None:
        session = _mission_backing_session()
        session[CREATIVE_WORKSPACE_STATE_KEY] = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_intelligence_tab": "Entry & Jam",
        }
        session["_creative_selector_hydration_complete"] = True
        open_backing_from_creative(session, source="mission", st_like=_st_like(session))
        self._simulate_return_prepare(session)
        self._assert_selector_state(
            session,
            entry_mode="Song-Based Improvisation",
            tab="Missions",
        )

    def test_consecutive_returns_update_canonical_each_time(self) -> None:
        session = _style_jam_like_session()
        _stale_canonical_style_jam(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        self._simulate_return_prepare(session)
        self._assert_selector_state(session, entry_mode="Style Jam Mode")

        session.update(_jam_generator_session())
        session["studio_page"] = "creative"
        session[CREATIVE_WORKSPACE_STATE_KEY] = copy.deepcopy(session[CREATIVE_WORKSPACE_STATE_KEY])
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        self._simulate_return_prepare(session)
        self._assert_selector_state(session, entry_mode="Jam Session Generator")

    def test_project_helper_matches_apply_route(self) -> None:
        session = _jam_generator_session()
        _stale_canonical_style_jam(session)
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        session["studio_page"] = "backing"
        prepare_return_to_backing_source(session)
        session.pop("_creative_restore_from_backing", None)
        self._assert_selector_state(session, entry_mode="Jam Session Generator")

    def test_without_projection_stale_canonical_would_win(self) -> None:
        """Documents pre-fix failure mode: canonical read before projection."""
        from creative_tab_tool_persistence import canonical_creative_selector_value

        session = _jam_generator_session()
        session["improv_entry_mode"] = "Jam Session Generator"
        session["improv_intelligence_tab"] = "Entry & Jam"
        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Entry & Jam"
        _stale_canonical_style_jam(session)
        self.assertEqual(
            canonical_creative_selector_value(session, "improv_entry_mode"),
            "Style Jam Mode",
        )
        project_return_destination_to_canonical_creative_selectors(
            session,
            intelligence_tab="Entry & Jam",
            entry_mode="Jam Session Generator",
        )
        self.assertEqual(
            canonical_creative_selector_value(session, "improv_entry_mode"),
            "Jam Session Generator",
        )
        self.assertEqual(ensure_improv_entry_mode_restored(session), "Jam Session Generator")


if __name__ == "__main__":
    unittest.main()

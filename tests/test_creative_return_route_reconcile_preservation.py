"""Preserve launch-sealed creative_return_route across Backing reconcile + Return."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from typing import Any

from backing_context import open_backing_from_creative, reconcile_backing_context_on_backing_page
from backing_creative_return_route import get_creative_return_route
from creative_return_trace import SESSION_TRACE_LOG_KEY
from music_workflow_pending_creative_return import handle_return_to_creative_click
from studio_page_persistence import _ACTIVE_PAGE_TRACKER, handle_studio_page_transition
from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY, ensure_improv_entry_mode_restored
from tests.test_backing_source_navigation import _style_jam_like_session
from tests.test_entry_jam_return_submode_lifecycle import (
    _jam_generator_session,
    _mission_backing_session,
)
from tests.test_song_improv_scope_authority import _mission_bridge_session


def _st_like(session: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(session_state=session)


def _reconcile_backing_page(session: dict[str, Any]) -> None:
    session["studio_page"] = "backing"
    reconcile_backing_context_on_backing_page(session, st_like=_st_like(session))


def _trace_entries(session: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    log = session.get(SESSION_TRACE_LOG_KEY)
    if not isinstance(log, list):
        return []
    return [e for e in log if isinstance(e, dict) and str(e.get("phase") or "") == phase]


def _reconcile_set_backing_trace_entries(session: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in _trace_entries(session, "SET_BACKING_CONTEXT"):
        extra = e.get("extra")
        if not isinstance(extra, dict):
            continue
        caller = str(extra.get("caller") or "")
        if "reconcile" in caller or "hydrate_backing" in caller or "ensure_backing_context" in caller:
            out.append(e)
    return out


def _simulate_return(session: dict[str, Any]) -> None:
    from unittest import mock

    st_mock = mock.MagicMock()
    session["studio_page"] = "backing"
    session[_ACTIVE_PAGE_TRACKER] = "backing"
    handle_return_to_creative_click(st_mock, session)
    session["studio_page"] = "creative"
    handle_studio_page_transition(session)


class TestCreativeReturnRouteReconcilePreservation(unittest.TestCase):
    def _assert_submode(
        self,
        session: dict[str, Any],
        *,
        entry_mode: str,
        tab: str = "Entry & Jam",
    ) -> None:
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), tab)
        self.assertEqual(str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""), tab)
        self.assertEqual(str(session.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(ensure_improv_entry_mode_restored(session), entry_mode)

    def _assert_reconcile_preserves_route(self, session: dict[str, Any], sealed: dict[str, Any]) -> None:
        _reconcile_backing_page(session)
        after = get_creative_return_route(session)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after, sealed)
        for entry in _reconcile_set_backing_trace_entries(session):
            extra = entry.get("extra")
            assert isinstance(extra, dict)
            self.assertFalse(
                extra.get("route_dropped"),
                msg=f"route dropped by {extra.get('caller')!r}",
            )
            self.assertEqual(
                extra.get("preservation_reason"),
                "preserved_same_signature",
                msg=extra,
            )

    def _assert_return_uses_blob_route(self, session: dict[str, Any], sealed: dict[str, Any]) -> None:
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Missions"
        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Missions"
        _simulate_return(session)
        read_entries = _trace_entries(session, "ON_RETURN_ROUTE_READ")
        self.assertTrue(read_entries, "expected ON_RETURN_ROUTE_READ trace")
        extra = read_entries[-1].get("extra")
        assert isinstance(extra, dict)
        self.assertEqual(extra.get("route_source"), "blob_sealed")
        self.assertEqual(extra.get("route_applied"), sealed)
        tab = str(sealed.get("intelligence_tab") or "Entry & Jam")
        entry = str(sealed.get("entry_mode") or "")
        self._assert_submode(session, entry_mode=entry, tab=tab)

    def test_entry_style_survives_reconcile_and_return(self) -> None:
        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        sealed = get_creative_return_route(session)
        assert sealed is not None
        sealed_copy = copy.deepcopy(sealed)
        self._assert_reconcile_preserves_route(session, sealed_copy)
        self._assert_return_uses_blob_route(session, sealed_copy)

    def test_jam_session_generator_survives_reconcile_and_return(self) -> None:
        session = _jam_generator_session()
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        sealed = get_creative_return_route(session)
        assert sealed is not None
        sealed_copy = copy.deepcopy(sealed)
        self.assertEqual(sealed_copy.get("entry_mode"), "Jam Session Generator")
        self._assert_reconcile_preserves_route(session, sealed_copy)
        self._assert_return_uses_blob_route(session, sealed_copy)

    def test_song_based_improv_survives_reconcile_and_return(self) -> None:
        session = _mission_bridge_session()
        session["improv_intelligence_tab"] = "Entry & Jam"
        open_backing_from_creative(session, source="song_improv", st_like=_st_like(session))
        sealed = get_creative_return_route(session)
        assert sealed is not None
        sealed_copy = copy.deepcopy(sealed)
        self._assert_reconcile_preserves_route(session, sealed_copy)
        self._assert_return_uses_blob_route(session, sealed_copy)

    def test_missions_survives_reconcile_and_return(self) -> None:
        session = _mission_backing_session()
        open_backing_from_creative(session, source="mission", st_like=_st_like(session))
        sealed = get_creative_return_route(session)
        assert sealed is not None
        sealed_copy = copy.deepcopy(sealed)
        self.assertEqual(sealed_copy.get("intelligence_tab"), "Missions")
        self._assert_reconcile_preserves_route(session, sealed_copy)
        self._assert_return_uses_blob_route(session, sealed_copy)

    def test_new_backing_launch_replaces_previous_sealed_route(self) -> None:
        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        route_style = get_creative_return_route(session)
        assert route_style is not None
        _reconcile_backing_page(session)

        session.update(_jam_generator_session())
        session["studio_page"] = "creative"
        open_backing_from_creative(session, source="entry_jam", st_like=_st_like(session))
        route_jam = get_creative_return_route(session)
        assert route_jam is not None
        self.assertNotEqual(route_jam.get("entry_mode"), route_style.get("entry_mode"))
        self.assertEqual(route_jam.get("entry_mode"), "Jam Session Generator")
        self.assertEqual(route_jam.get("workflow_owner"), "jam_session_generator")

        _reconcile_backing_page(session)
        self.assertEqual(get_creative_return_route(session), route_jam)
        _simulate_return(session)
        self._assert_submode(session, entry_mode="Jam Session Generator")


if __name__ == "__main__":
    unittest.main()

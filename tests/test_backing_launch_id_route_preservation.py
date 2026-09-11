"""Return route survives source_signature churn within one Backing launch (launch_id)."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from backing_context import (
    BACKING_CONTEXT_KEY,
    BACKING_CTX_TRANSPORT_APPLIED_SIG,
    BACKING_SESSION_LAUNCH_ID_BLOB_KEY,
    _sync_creative_backing_transport_handoff,
    diff_source_signature_fields,
    get_backing_context,
    open_backing_from_creative,
)
from backing_creative_return_route import get_creative_return_route
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


def _simulate_bpm_signature_change(session: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Mirror live Backing: widget BPM diverges → _sync_creative_backing_transport_handoff."""
    ctx = get_backing_context(session)
    assert ctx is not None
    raw = session.get(BACKING_CONTEXT_KEY)
    assert isinstance(raw, dict)
    sig_before = str(raw.get("source_signature") or "")
    session[BACKING_CTX_TRANSPORT_APPLIED_SIG] = sig_before
    new_bpm = int(ctx.bpm or 100) + 7
    session["backing_track_bpm"] = new_bpm
    session["bpm"] = new_bpm
    _sync_creative_backing_transport_handoff(session, ctx, st_like=_st_like(session))
    raw_after = session.get(BACKING_CONTEXT_KEY)
    assert isinstance(raw_after, dict)
    sig_after = str(raw_after.get("source_signature") or "")
    changed = diff_source_signature_fields(raw, ctx)
    return sig_before, sig_after, changed


def _simulate_return(session: dict[str, Any]) -> None:
    st_mock = mock.MagicMock()
    session["studio_page"] = "backing"
    session[_ACTIVE_PAGE_TRACKER] = "backing"
    handle_return_to_creative_click(st_mock, session)
    session["studio_page"] = "creative"
    handle_studio_page_transition(session)


class TestBackingLaunchIdRoutePreservation(unittest.TestCase):
    def _open_and_seal(self, session: dict[str, Any], *, source: str) -> tuple[dict[str, Any], str]:
        open_backing_from_creative(session, source=source, st_like=_st_like(session))
        route = get_creative_return_route(session)
        assert route is not None
        raw = session.get(BACKING_CONTEXT_KEY)
        assert isinstance(raw, dict)
        launch_id = str(raw.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or "")
        self.assertTrue(launch_id)
        return copy.deepcopy(route), launch_id

    def _assert_return_origin(
        self,
        session: dict[str, Any],
        route: dict[str, Any],
        *,
        entry_mode: str,
        tab: str = "Entry & Jam",
    ) -> None:
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Missions"
        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Missions"
        _simulate_return(session)
        self.assertEqual(str(session.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), tab)
        self.assertEqual(ensure_improv_entry_mode_restored(session), entry_mode)
        self.assertEqual(get_creative_return_route(session), route)

    def test_jam_generator_bpm_sync_preserves_route_and_launch_id(self) -> None:
        session = _jam_generator_session()
        route, launch_id = self._open_and_seal(session, source="entry_jam")
        ctx_before = get_backing_context(session)
        assert ctx_before is not None
        source_bpm = int(ctx_before.bpm or 0)
        sig_before, sig_after, changed = _simulate_bpm_signature_change(session)
        self.assertEqual(sig_before, sig_after)
        self.assertNotIn("bpm", changed)
        raw = session.get(BACKING_CONTEXT_KEY)
        assert isinstance(raw, dict)
        self.assertEqual(str(raw.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or ""), launch_id)
        self.assertEqual(get_creative_return_route(session), route)
        ctx_after = get_backing_context(session)
        assert ctx_after is not None
        self.assertEqual(int(ctx_after.bpm or 0), source_bpm)
        self.assertNotEqual(int(session.get("backing_track_bpm") or 0), source_bpm)
        self._assert_return_origin(session, route, entry_mode="Jam Session Generator")

    def test_entry_style_bpm_sync_preserves_route(self) -> None:
        session = _style_jam_like_session()
        route, launch_id = self._open_and_seal(session, source="entry_jam")
        sig_before, sig_after, changed = _simulate_bpm_signature_change(session)
        self.assertEqual(sig_before, sig_after)
        self.assertNotIn("bpm", changed)
        self.assertEqual(get_creative_return_route(session), route)
        self._assert_return_origin(session, route, entry_mode="Style Jam Mode")

    def test_song_based_improv_bpm_sync_preserves_route(self) -> None:
        session = _mission_bridge_session()
        session["improv_intelligence_tab"] = "Entry & Jam"
        route, _launch_id = self._open_and_seal(session, source="song_improv")
        sig_before, sig_after, changed = _simulate_bpm_signature_change(session)
        self.assertEqual(sig_before, sig_after)
        self.assertNotIn("bpm", changed)
        self.assertEqual(get_creative_return_route(session), route)
        self._assert_return_origin(session, route, entry_mode="Song-Based Improvisation")

    def test_missions_bpm_sync_preserves_route(self) -> None:
        session = _mission_backing_session()
        route, _launch_id = self._open_and_seal(session, source="mission")
        sig_before, sig_after, changed = _simulate_bpm_signature_change(session)
        self.assertEqual(sig_before, sig_after)
        self.assertNotIn("bpm", changed)
        self.assertEqual(get_creative_return_route(session), route)
        self._assert_return_origin(
            session,
            route,
            entry_mode="Song-Based Improvisation",
            tab="Missions",
        )

    def test_new_backing_launch_replaces_launch_id_and_route(self) -> None:
        session = _style_jam_like_session()
        _route_a, launch_a = self._open_and_seal(session, source="entry_jam")
        session.update(_jam_generator_session())
        session["studio_page"] = "creative"
        route_b, launch_b = self._open_and_seal(session, source="entry_jam")
        self.assertNotEqual(launch_a, launch_b)
        self.assertEqual(route_b.get("entry_mode"), "Jam Session Generator")
        _simulate_bpm_signature_change(session)
        self.assertEqual(get_creative_return_route(session), route_b)


if __name__ == "__main__":
    unittest.main()

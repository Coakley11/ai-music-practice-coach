"""Launch-sealed creative_return_route — Return consumes origin, not stale session inference."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from backing_context import BACKING_CONTEXT_KEY, get_backing_context, open_backing_from_creative
from backing_creative_return_route import get_creative_return_route
from music_workflow_pending_creative_return import handle_return_to_creative_click
from studio_page_persistence import _ACTIVE_PAGE_TRACKER, handle_studio_page_transition
from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY, ensure_improv_entry_mode_restored
from tests.test_backing_source_navigation import _style_jam_like_session
from tests.test_song_improv_scope_authority import _mission_bridge_session


def _jam_generator_session() -> dict[str, Any]:
    session = _style_jam_like_session()
    session.update(
        {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Jazz Swing",
            "improv_jam_bpm": 110,
            "improv_jam_mood": "Mellow",
            "improv_jam_key": "D",
            "improv_jam_session": {"sections": {"Jam": ["Dmaj7", "G7", "Cmaj7"]}},
        }
    )
    session.pop("improv_generated_sections", None)
    return session


def _mission_backing_session() -> dict[str, Any]:
    session = _style_jam_like_session()
    session.update(
        {
            "improv_intelligence_tab": "Missions",
            CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY: "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_active_mission": "chord_tones",
            "improv_mission_pick": "chord_tones",
            "ii_selected_chord": "G7",
            "II_SELECTED_CHORD": "G7",
            "ii_selected_section": "Verse",
            "II_SELECTED_SECTION": "Verse",
            "improv_mission_chord_options": ["G7", "Cmaj7"],
            "home_sections": {"Verse": ["G7", "Cmaj7"]},
        }
    )
    return session


def _simulate_return_click_and_next_creative_run(session: dict[str, Any]) -> None:
    st_mock = mock.MagicMock()
    session["studio_page"] = "backing"
    session[_ACTIVE_PAGE_TRACKER] = "backing"
    handle_return_to_creative_click(st_mock, session)
    if str(session.get("studio_page") or "") != "creative":
        raise AssertionError(f"expected studio_page creative, got {session.get('studio_page')!r}")
    session["studio_page"] = "creative"
    handle_studio_page_transition(session)


class TestEntryJamReturnSubmodeLifecycle(unittest.TestCase):
    def _assert_creative_submode(self, session: dict[str, Any], *, entry_mode: str, tab: str = "Entry & Jam") -> None:
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), tab)
        self.assertEqual(str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""), tab)
        self.assertEqual(str(session.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(ensure_improv_entry_mode_restored(session), entry_mode)

    def test_launch_seals_route_in_backing_context(self) -> None:
        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        route = get_creative_return_route(session)
        self.assertIsNotNone(route)
        assert route is not None
        self.assertEqual(route.get("entry_mode"), "Style Jam Mode")
        self.assertEqual(route.get("intelligence_tab"), "Entry & Jam")
        raw = session.get(BACKING_CONTEXT_KEY)
        self.assertIsInstance(raw, dict)
        assert isinstance(raw, dict)
        self.assertIn("creative_return_route", raw)

    def test_return_uses_launch_route_not_backing_page_drift(self) -> None:
        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        route = get_creative_return_route(session)
        assert route is not None
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Missions"
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode=str(route["entry_mode"]))

    def test_style_jam_return(self) -> None:
        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Style Jam Mode")

    def test_jam_session_generator_return(self) -> None:
        session = _jam_generator_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        route = get_creative_return_route(session)
        self.assertEqual(str((route or {}).get("entry_mode") or ""), "Jam Session Generator")
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Jam Session Generator")

    def test_song_based_improv_return(self) -> None:
        session = _mission_bridge_session()
        session["improv_intelligence_tab"] = "Entry & Jam"
        open_backing_from_creative(session, source="song_improv", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Song-Based Improvisation")

    def test_missions_return(self) -> None:
        session = _mission_backing_session()
        open_backing_from_creative(session, source="mission", st_like=SimpleNamespace(session_state=session))
        route = get_creative_return_route(session)
        self.assertEqual(str((route or {}).get("intelligence_tab") or ""), "Missions")
        session["improv_entry_mode"] = "Style Jam Mode"
        session["improv_intelligence_tab"] = "Entry & Jam"
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(
            session,
            entry_mode="Song-Based Improvisation",
            tab="Missions",
        )
        self.assertEqual(str(session.get("improv_active_mission") or ""), "chord_tones")

    def test_consecutive_returns_do_not_leak_submode(self) -> None:
        from music_restore_phase import complete_music_restore_phase

        session = _style_jam_like_session()
        complete_music_restore_phase(session)

        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Style Jam Mode")

        session.update(_jam_generator_session())
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Jam Session Generator")

        sbi = _mission_bridge_session()
        for key, val in sbi.items():
            session[key] = val
        session["improv_intelligence_tab"] = "Entry & Jam"
        open_backing_from_creative(session, source="song_improv", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Song-Based Improvisation")

        session.update(_mission_backing_session())
        open_backing_from_creative(session, source="mission", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Song-Based Improvisation", tab="Missions")

    def test_style_jam_return_releases_backing_owner_keeps_session(self) -> None:
        from backing_source_navigation import BACKING_ENTRY_CLASS_KEY, BACKING_ENTRY_SPECIALIZED_HANDOFF
        from music_workflow_pending_backing_handoff import (
            PENDING_BACKING_WORKFLOW_KEY,
            queue_pending_backing_workflow_handoff,
        )

        session = _style_jam_like_session()
        session["improv_style_key"] = "C#"
        session["improv_generated_sections"] = {
            "Style Jam": ["C#maj7", "D#m7", "F#maj7", "G#7"],
        }
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        session["_backing_explicit_handoff_source"] = "entry_jam"
        session[BACKING_ENTRY_CLASS_KEY] = BACKING_ENTRY_SPECIALIZED_HANDOFF
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="entry_jam",
            workflow_owner="style_jam",
        )
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Style Jam Mode")
        self.assertNotEqual(session.get("_backing_explicit_handoff_source"), "entry_jam")
        self.assertIsNone(session.get(PENDING_BACKING_WORKFLOW_KEY))
        self.assertEqual(str(session.get("improv_style_key") or ""), "C#")
        sections = session.get("improv_generated_sections")
        self.assertIsInstance(sections, dict)
        self.assertIn("Style Jam", sections)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(str(ctx.source or ""), "entry_jam")

    def test_pending_backing_handoff_cannot_reclaim_after_return(self) -> None:
        from music_workflow_pending_backing_handoff import (
            PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY,
            consume_pending_backing_workflow_handoff,
            queue_pending_backing_workflow_handoff,
        )
        from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers

        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        req = queue_pending_backing_workflow_handoff(
            session,
            backing_source="entry_jam",
            workflow_owner="style_jam",
        )
        session[PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY] = req["request_seq"]
        session["_creative_restore_from_backing"] = True
        phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "skipped")
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        run_pre_widget_application_consumers(session)
        self.assertEqual(str(session.get("studio_page") or ""), "creative")

    def test_persist_restore_cannot_overwrite_creative_return(self) -> None:
        from studio_nav_state import resolve_studio_page_for_restore

        session = _style_jam_like_session()
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        blob = {"core": {"studio_page": "backing"}, "session": {"studio_page": "backing"}}
        page, source = resolve_studio_page_for_restore(
            session,
            blob,
            pre_restore_page="creative",
            user_owns_page=False,
        )
        self.assertEqual(page, "creative")
        self.assertEqual(source, "creative_return_from_backing")


if __name__ == "__main__":
    unittest.main()

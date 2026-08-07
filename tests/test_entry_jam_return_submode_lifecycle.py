"""Return to Creative restores exact Entry & Jam submode from backing_context."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from backing_context import get_backing_context, open_backing_from_creative
from music_workflow_pending_creative_return import handle_return_to_creative_click
from studio_page_persistence import _ACTIVE_PAGE_TRACKER, handle_studio_page_transition, save_page_snapshot
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


def _simulate_return_click_and_next_creative_run(session: dict[str, Any]) -> None:
    st_mock = mock.MagicMock()
    session["studio_page"] = "backing"
    session[_ACTIVE_PAGE_TRACKER] = "backing"
    handle_return_to_creative_click(st_mock, session)
    self_assert_creative = str(session.get("studio_page") or "") == "creative"
    if not self_assert_creative:
        raise AssertionError(f"expected studio_page creative, got {session.get('studio_page')!r}")
    session["studio_page"] = "creative"
    handle_studio_page_transition(session)


class TestEntryJamReturnSubmodeLifecycle(unittest.TestCase):
    def _assert_creative_submode(self, session: dict[str, Any], *, entry_mode: str) -> None:
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), "Entry & Jam")
        self.assertEqual(str(session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY) or ""), "Entry & Jam")
        self.assertEqual(str(session.get("improv_entry_mode") or ""), entry_mode)
        self.assertEqual(ensure_improv_entry_mode_restored(session), entry_mode)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)

    def test_style_jam_return_after_stale_sbi_snapshot(self) -> None:
        from music_restore_phase import complete_music_restore_phase

        session = _style_jam_like_session()
        session.update(
            {
                "studio_page": "creative",
                "improv_intelligence_tab": "Entry & Jam",
                CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY: "Entry & Jam",
            }
        )
        complete_music_restore_phase(session)
        save_page_snapshot(session, "creative")
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Missions"
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Style Jam Mode")

    def test_jam_session_generator_return(self) -> None:
        session = _jam_generator_session()
        session["studio_page"] = "creative"
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(str(ctx.entry_mode or ""), "Jam Session Generator")
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Jam Session Generator")

    def test_song_based_improv_return(self) -> None:
        session = _mission_bridge_session()
        session["studio_page"] = "creative"
        session["improv_intelligence_tab"] = "Missions"
        open_backing_from_creative(session, source="song_improv", st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "song_improv")
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Song-Based Improvisation")

    def test_consecutive_returns_do_not_leak_submode(self) -> None:
        from music_restore_phase import complete_music_restore_phase

        session = _style_jam_like_session()
        session["studio_page"] = "creative"
        complete_music_restore_phase(session)

        # A: Style Jam
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Style Jam Mode")

        # B: Jam Session Generator (same session)
        session.update(_jam_generator_session())
        session["studio_page"] = "creative"
        open_backing_from_creative(session, source="entry_jam", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Jam Session Generator")

        # C: Song-Based Improvisation (same session)
        sbi = _mission_bridge_session()
        for key, val in sbi.items():
            session[key] = val
        session["studio_page"] = "creative"
        open_backing_from_creative(session, source="song_improv", st_like=SimpleNamespace(session_state=session))
        _simulate_return_click_and_next_creative_run(session)
        self._assert_creative_submode(session, entry_mode="Song-Based Improvisation")


if __name__ == "__main__":
    unittest.main()

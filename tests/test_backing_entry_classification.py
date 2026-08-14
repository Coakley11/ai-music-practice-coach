"""Shared specialized vs generic Backing entry classification."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    BACKING_PREF_CREATIVE,
    BackingContext,
    open_backing_from_creative,
    set_backing_context,
    set_backing_source_preference,
)
from creative_session_state import CreativeSession, set_creative_session
from backing_source_navigation import (
    BACKING_INTENT_FROM_CREATIVE,
    BACKING_INTENT_RESTORE_LAST,
    BACKING_OPEN_INTENT_KEY,
    hydrate_backing_source_for_page,
    mark_generic_catalog_backing_entry,
    mark_specialized_backing_handoff_entry,
    set_backing_open_intent,
)
from music_source_ownership import intentional_creative_backing_active
from studio_nav_history import navigate_studio_page


def _mission_ctx(mission_id: str = "Mission A") -> BackingContext:
    return BackingContext(
        source="mission",
        source_label="Mission",
        active_song_id="pick",
        song_title="Tune",
        key="C",
        display_key="C",
        concert_key="C",
        bpm=100,
        style="Pop",
        groove="Straight",
        mission_id=mission_id,
    )


def _entry_jam_ctx(*, entry_mode: str = "Jam Session Generator") -> BackingContext:
    return BackingContext(
        source="entry_jam",
        source_label="Entry & Jam",
        active_song_id="jam",
        song_title="Jam",
        key="D",
        display_key="D",
        concert_key="D",
        bpm=110,
        style="Rock",
        groove="Medium",
        entry_mode=entry_mode,
    )


def _attach_mission_blob(session: dict, mission_id: str = "Mission A") -> None:
    set_creative_session(
        session,
        CreativeSession(
            session_id="mission-blob",
            tool_type="mission",
            entry_mode="Song-Based Improvisation",
            mission_id=mission_id,
            sections={"A": ["C"]},
            intelligence_tab="Missions",
        ),
    )


def _attach_style_jam_blob(session: dict) -> None:
    set_creative_session(
        session,
        CreativeSession(
            session_id="style-jam-blob",
            tool_type="entry_style_jam",
            entry_mode="Style Jam Mode",
            concert_key="D",
            style="Rock",
            sections={"A": ["D", "G"]},
            intelligence_tab="Entry & Jam",
        ),
    )


class BackingEntryClassificationTests(unittest.TestCase):
    def test_double_hydrate_preserves_specialized_mission_context(self) -> None:
        """Root cause: second hydrate defaulted intent to restore_last and released mission ctx."""
        session: dict = {
            "studio_page": "backing",
            "improv_entry_mode": "Missions",
            "improv_intelligence_tab": "Missions",
            "improv_active_mission": "Mission A",
        }
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="mission", st_like=st_like)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        mark_specialized_backing_handoff_entry(session)
        hydrate_backing_source_for_page(session, st_like=st_like)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = session.get(BACKING_CONTEXT_KEY)
        self.assertIsInstance(ctx, dict)
        self.assertEqual(ctx.get("source"), "mission")
        self.assertEqual(ctx.get("mission_id"), "Mission A")
        self.assertNotIn("_backing_released_specialized_context", session)

    def test_restore_last_without_generic_flag_does_not_release(self) -> None:
        session: dict = {
            "studio_page": "backing",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "D",
            "improv_style_bpm": 110,
            "improv_generated_sections": {"A": ["Dmaj7", "Gmaj7"]},
        }
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True) as recon:
            hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertFalse(recon.called)
        self.assertTrue(intentional_creative_backing_active(session))

    def test_generic_top_level_nav_restores_last_valid_mission(self) -> None:
        """Upload/Multitrack/Log → Backing must restore the last valid Mission session."""
        session: dict = {"studio_page": "backing", "active_catalog_pick_key": "Pop::X"}
        set_backing_context(session, _mission_ctx())
        _attach_mission_blob(session)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        mark_generic_catalog_backing_entry(session)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True) as recon:
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertFalse(recon.called)
        self.assertTrue(intentional_creative_backing_active(session))
        ctx = session.get(BACKING_CONTEXT_KEY) or {}
        self.assertEqual(ctx.get("source"), "mission")
        self.assertEqual(ctx.get("mission_id"), "Mission A")

    def test_creative_to_backing_uses_specialized_not_generic(self) -> None:
        session: dict = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
        }
        set_backing_context(session, _entry_jam_ctx())
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        navigate_studio_page(session, "backing")
        self.assertEqual(
            str(session.get(BACKING_OPEN_INTENT_KEY) or ""),
            BACKING_INTENT_FROM_CREATIVE,
        )

    def test_log_to_backing_restores_last_mission(self) -> None:
        session: dict = {"studio_page": "log", "active_catalog_pick_key": "Pop::X"}
        set_backing_context(session, _mission_ctx("Mission B"))
        _attach_mission_blob(session, "Mission B")
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        navigate_studio_page(session, "backing")
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True) as recon:
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertFalse(recon.called)
        self.assertTrue(intentional_creative_backing_active(session))
        ctx = session.get(BACKING_CONTEXT_KEY) or {}
        self.assertEqual(ctx.get("source"), "mission")
        self.assertEqual(ctx.get("mission_id"), "Mission B")

    def test_upload_to_backing_restores_mission_session(self) -> None:
        session: dict = {
            "studio_page": "analysis",
            "active_catalog_pick_key": "Pop::X",
            "improv_active_mission": "Mission A",
        }
        set_backing_context(session, _mission_ctx())
        _attach_mission_blob(session)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        navigate_studio_page(session, "backing")
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = session.get(BACKING_CONTEXT_KEY) or {}
        self.assertEqual(ctx.get("source"), "mission")
        self.assertEqual(ctx.get("mission_id"), "Mission A")
        self.assertTrue(intentional_creative_backing_active(session))

    def test_multitrack_to_backing_restores_style_jam_session(self) -> None:
        session: dict = {
            "studio_page": "multitrack",
            "active_catalog_pick_key": "Pop::X",
            "improv_entry_mode": "Style Jam Mode",
        }
        set_backing_context(session, _entry_jam_ctx(entry_mode="Style Jam Mode"))
        _attach_style_jam_blob(session)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        navigate_studio_page(session, "backing")
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = session.get(BACKING_CONTEXT_KEY) or {}
        self.assertEqual(ctx.get("source"), "entry_jam")
        self.assertEqual(ctx.get("entry_mode"), "Style Jam Mode")
        self.assertTrue(intentional_creative_backing_active(session))

    def test_stale_mission_with_wrong_song_still_releases_on_generic_nav(self) -> None:
        session: dict = {"studio_page": "backing", "active_catalog_pick_key": "Pop::Other"}
        ctx = _mission_ctx()
        ctx.bound_pick_key = "Pop::X"
        set_backing_context(session, ctx)
        mark_generic_catalog_backing_entry(session)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True) as recon:
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertTrue(recon.called)
        self.assertFalse(intentional_creative_backing_active(session))

    def test_mission_b_then_mission_a_via_specialized_handoff(self) -> None:
        session: dict = {"studio_page": "backing"}
        set_backing_context(session, _mission_ctx("Mission B"))
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        mark_specialized_backing_handoff_entry(session)
        st_like = SimpleNamespace(session_state=session)
        with patch(
            "backing_source_navigation.open_backing_for_creative_source",
            side_effect=lambda s, **k: set_backing_context(s, _mission_ctx("Mission A")),
        ):
            hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = session.get(BACKING_CONTEXT_KEY) or {}
        self.assertEqual(ctx.get("mission_id"), "Mission A")


if __name__ == "__main__":
    unittest.main()

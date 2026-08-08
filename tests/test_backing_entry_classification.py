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
        session: dict = {"studio_page": "backing", "improv_entry_mode": "Style Jam Mode"}
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True) as recon:
            hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertFalse(recon.called)
        self.assertTrue(intentional_creative_backing_active(session))

    def test_generic_top_level_nav_releases_specialized(self) -> None:
        session: dict = {"studio_page": "backing", "active_catalog_pick_key": "Pop::X"}
        set_backing_context(session, _mission_ctx())
        mark_generic_catalog_backing_entry(session)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True):
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertFalse(intentional_creative_backing_active(session))

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

    def test_log_to_backing_marks_generic(self) -> None:
        session: dict = {"studio_page": "log", "active_catalog_pick_key": "Pop::X"}
        set_backing_context(session, _mission_ctx("Mission B"))
        navigate_studio_page(session, "backing")
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True):
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
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

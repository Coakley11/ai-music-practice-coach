"""Section scope invariants: Full Song default on fresh entry; user section selection preserved."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from backing_context import BackingContext, build_entry_jam_context, set_backing_context
from backing_source_navigation import (
    hydrate_backing_source_for_page,
    mark_generic_catalog_backing_entry,
)
from backing_track_state import (
    BACKING_STATE_KEY,
    canonical_backing_filters,
    gather_backing_filters,
    reset_backing_playback_scope_to_full_song,
    sync_backing_scope_widgets_after_user_edit,
    write_canonical_backing_state,
)
from practice_studio import PRACTICE_FOCUS_FULL, practice_is_full_song
from song_improv_scope_authority import SONG_IMPROV_PLAYBACK_FULL, apply_song_improv_entry_defaults
from tests.test_song_improv_scope_authority import _mission_bridge_session


def _sections_hevenu() -> dict[str, list[str]]:
    return {
        "Melody A": ["Dm", "G"],
        "Melody B": ["Am", "Dm"],
        "Verse": ["Dm", "Bb", "C"],
    }


class WorkflowSectionScopeInvariantTests(unittest.TestCase):
    def test_song_based_entry_defaults_full_song_then_user_melody_b(self) -> None:
        session = _mission_bridge_session()
        apply_song_improv_entry_defaults(session, source="entry_mode_song_based")
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))

        session["backing_track_scope"] = "Selected sections"
        session["backing_track_single_section"] = "Melody B"
        session["backing_track_multi_sections"] = ["Melody B"]
        sync_backing_scope_widgets_after_user_edit(session)
        write_canonical_backing_state(
            session,
            gather_backing_filters(session),
            reason="test_user_melody_b",
            local_edit=True,
        )
        filters = gather_backing_filters(session)
        self.assertEqual(str(filters.get("backing_track_scope") or ""), "Selected sections")
        self.assertEqual(filters.get("backing_track_multi_sections"), ["Melody B"])

    def test_generic_catalog_backing_entry_resets_stale_mission_section(self) -> None:
        session = _mission_bridge_session()
        session["studio_page"] = "log"
        mark_generic_catalog_backing_entry(session)
        with patch("music_source_ownership.reconcile_source_ownership", return_value=True):
            hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)
        canon = canonical_backing_filters(session) or {}
        self.assertEqual(str(canon.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)
        self.assertFalse(canon.get("backing_track_multi_sections"))

    def test_entry_jam_build_defaults_full_song_with_generated_sections(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["Bridge"],
            "improv_generated_sections": _sections_hevenu(),
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.scope or ""), "Full song")

    def test_jam_generator_user_section_selection_gathers_for_backing(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_generated_sections": _sections_hevenu(),
            "backing_track_scope": "Full song",
        }
        session["backing_track_scope"] = "Selected sections"
        session["backing_track_single_section"] = "Melody A"
        session["backing_track_multi_sections"] = ["Melody A"]
        sync_backing_scope_widgets_after_user_edit(session)
        filters = gather_backing_filters(session)
        self.assertEqual(filters.get("backing_track_multi_sections"), ["Melody A"])

    def test_leave_section_workflow_fresh_song_based_starts_full_song(self) -> None:
        mission = _mission_bridge_session()
        mission["improv_entry_mode"] = "Jam Session Generator"
        mission["backing_track_multi_sections"] = ["Bridge"]
        apply_song_improv_entry_defaults(mission, source="creative_tab_change")
        self.assertTrue(practice_is_full_song(mission.get("practice_focus_section")))
        self.assertEqual(str(mission.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)

    def test_full_song_canonical_survives_stale_quick_section_on_gather(self) -> None:
        session = {
            "backing_track_scope": "Full song",
            "backing_quick_section": "Bridge",
            "backing_track_multi_sections": ["Bridge"],
        }
        write_canonical_backing_state(
            session,
            gather_backing_filters(session),
            reason="test_persist_full_song",
            local_edit=True,
        )
        filters = gather_backing_filters(session)
        self.assertEqual(str(filters.get("backing_track_scope") or ""), "Full song")
        self.assertFalse(filters.get("backing_track_multi_sections"))
        blob = session.get(BACKING_STATE_KEY)
        self.assertIsInstance(blob, dict)
        assert isinstance(blob, dict)
        self.assertEqual(str(blob.get("backing_track_scope") or ""), "Full song")

    def test_regular_catalog_backing_practice_full_song_queue(self) -> None:
        from backing_source_navigation import queue_backing_scope_from_practice_focus

        session = {
            "practice_focus_section": PRACTICE_FOCUS_FULL,
            "selected_song": {"sections": _sections_hevenu()},
        }
        queue_backing_scope_from_practice_focus(session)
        from custom_progression_lab import PENDING_BACKING_SCOPE

        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Full song")

    def test_specialized_song_improv_backing_may_carry_section_in_context(self) -> None:
        session: dict[str, Any] = {"studio_page": "backing"}
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based",
            active_song_id="pick",
            song_title="Hevenu",
            key="Dm",
            display_key="Dm",
            concert_key="Dm",
            bpm=100,
            style="",
            groove="Auto",
            scope="Selected sections",
            section="Melody B",
            sections=["Melody B"],
            entry_mode="Song-Based Improvisation",
        )
        set_backing_context(session, ctx)
        self.assertEqual(str(ctx.section or ""), "Melody B")
        reset_backing_playback_scope_to_full_song(session, source="generic_catalog_backing_entry")
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)


if __name__ == "__main__":
    unittest.main()

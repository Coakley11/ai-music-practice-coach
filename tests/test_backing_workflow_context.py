"""Backing workflow envelope isolation from catalog song context."""

from __future__ import annotations

import unittest
from typing import Any

from backing_context import BackingContext, build_entry_jam_context, open_backing_from_creative, set_backing_context
from backing_nav_actions import build_backing_nav_actions
from backing_session_route import return_to_regular_backing_label, visible_navigation_actions
from backing_workflow_context import (
    get_backing_workflow_envelope,
    sync_backing_workflow_envelope,
    workflow_is_generated,
)


class TestBackingWorkflowContext(unittest.TestCase):
    def test_generated_jam_never_shows_catalog_return_label(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_bpm": 120,
            "improv_jam_mood": "Mellow",
            "improv_style_meta": {"style": "Jewish ballad", "groove": "Jewish ballad"},
            "backing_groove_style": "Jewish ballad",
            "song": "Hevenu Shalom Aleichem",
            "active_catalog_pick_key": "catalog::jewish::hevenu",
            "improv_generated_sections": {"A": ["Dm7", "G7", "Cmaj7"]},
        }
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_backing_workflow_envelope(session, ctx)
        self.assertTrue(workflow_is_generated(session))
        env = get_backing_workflow_envelope(session) or {}
        self.assertEqual(env.get("workflow_type"), "jam_session_generator")
        self.assertEqual(env.get("source_type"), "generated")
        self.assertIn("Bossa Nova", str(ctx.style or ctx.groove))
        self.assertNotIn("Jewish", str(ctx.style or ""))
        actions, _ = build_backing_nav_actions(session)
        labels = " ".join(a.label for a in actions)
        self.assertIn("Return to Regular Catalog Song Backing", labels)
        self.assertIn("Return to Creative Page", labels)

    def test_entry_jam_defaults_full_song_scope(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Rock",
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["A (Bossa Nova)"],
            "improv_generated_sections": {"A": ["C", "F", "G"]},
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.scope or ""), "Full song")

    def test_song_improv_open_syncs_workflow(self) -> None:
        session: dict[str, Any] = {
            "improv_song_source": "Active song",
            "active_catalog_pick_key": "catalog::pop::test",
            "song": "Test Song",
            "improv_style": "Pop groove",
        }
        open_backing_from_creative(session, source="song_improv")
        env = get_backing_workflow_envelope(session) or {}
        self.assertEqual(env.get("workflow_type"), "song_based_improvisation")


if __name__ == "__main__":
    unittest.main()

"""Authoritative workflow envelope — mission chord vs song key, contamination regression."""

from __future__ import annotations

import unittest
from typing import Any

from active_musical_workflow_envelope import (
    VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH,
    VIOLATION_STALE_GENERATED_JAM_KEY_LEAK,
    apply_atomic_mission_chord_selection,
    build_active_workflow_envelope,
    mission_example_allowed_for_projection,
    reconcile_mission_workflow_envelope,
    validate_mission_workflow_envelope,
)
from backing_context import BackingContext, build_mission_context, set_backing_context
from backing_nav_actions import build_backing_nav_actions, backing_nav_has_return_mission
from workflow_musical_authority import (
    save_workflow_snapshot,
    switch_workflow_owner,
)


class TestMissionEnvelopeValidation(unittest.TestCase):
    def test_example_mismatch_detected(self) -> None:
        session: dict[str, Any] = {
            "ii_selected_chord": "B",
            "ii_selected_chord_index": 2,
            "display_key": "Em",
            "concert_key": "Em",
            MISSION_EXAMPLE_KEY: {"chord": "Ab", "mission": "Outline chord tones"},
        }
        diag = validate_mission_workflow_envelope(session)
        self.assertIn(VIOLATION_MISSION_EXAMPLE_OWNER_MISMATCH, diag.get("violations", []))

    def test_reconcile_clears_stale_example(self) -> None:
        session: dict[str, Any] = {
            "ii_selected_chord": "B",
            "display_key": "Em",
            "concert_key": "Em",
            MISSION_EXAMPLE_KEY: {"chord": "Ab"},
        }
        reconcile_mission_workflow_envelope(session)
        self.assertNotIn(MISSION_EXAMPLE_KEY, session)

    def test_projection_blocked_for_wrong_chord(self) -> None:
        session = {"ii_selected_chord": "B"}
        self.assertFalse(mission_example_allowed_for_projection(session, {"chord": "Ab"}))
        self.assertTrue(mission_example_allowed_for_projection(session, {"chord": "B"}))


class TestWorkflowContaminationSequence(unittest.TestCase):
    def test_generator_then_missions_restores_song_key(self) -> None:
        session: dict[str, Any] = {
            "display_key": "Em",
            "concert_key": "Em",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "D",
            "improv_intelligence_tab": "Missions",
            "ii_selected_chord": "B",
            "ii_selected_section": "Melody A",
            "ii_selected_chord_index": 1,
            "improv_song_concert_sections": {"Melody A": ["Em", "B"]},
        }
        save_workflow_snapshot(session, "song_based_improvisation")
        save_workflow_snapshot(session, "mission_jam")
        session["display_key"] = "D"
        session["concert_key"] = "D"
        switch_workflow_owner(session, "mission_jam")
        self.assertEqual(str(session.get("display_key")), "Em")
        self.assertEqual(str(session.get("ii_selected_chord")), "B")

    def test_mission_backing_uses_song_practice_key_not_chord_root(self) -> None:
        session: dict[str, Any] = {
            "display_key": "Em",
            "concert_key": "Em",
            "song": "Hevenu Shalom Aleichem",
            "ii_selected_chord": "B",
            "ii_selected_chord_index": 1,
            "improv_mission_chord_options": ["Em", "B"],
            "improv_active_mission": "Outline chord tones",
            "improv_style": "Jewish ballad",
        }
        ctx = build_mission_context(session)
        self.assertEqual(str(ctx.concert_key), "Em")
        self.assertEqual(list(ctx.progression or []), ["B"])


class TestBackingNavDedupeMission(unittest.TestCase):
    def test_single_return_to_mission(self) -> None:
        session: dict[str, Any] = {}
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="catalog::hevenu",
            song_title="Hevenu",
            key="Em",
            display_key="Em",
            concert_key="Em",
            bpm=100,
            style="Jewish ballad",
            groove="Ballad",
            progression=["B"],
            sections=["Melody A"],
            scope="Mission chord",
            mission_id="Outline chord tones",
        )
        set_backing_context(session, ctx)
        actions, removed = build_backing_nav_actions(session)
        mission_buttons = [a for a in actions if a.action_id == "return_mission"]
        self.assertEqual(len(mission_buttons), 1)
        self.assertTrue(backing_nav_has_return_mission(session))
        self.assertIn("Return to Creative Page", " ".join(a.label for a in actions))

    def test_creative_and_mission_destinations_distinct(self) -> None:
        session: dict[str, Any] = {}
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="x",
            song_title="T",
            key="Em",
            display_key="Em",
            concert_key="Em",
            bpm=90,
            style="Pop",
            groove="Pop",
            progression=["B"],
            sections=[],
            scope="Mission chord",
        )
        set_backing_context(session, ctx)
        actions, _ = build_backing_nav_actions(session)
        dests = {a.action_id: a.destination for a in actions}
        self.assertNotEqual(dests.get("return_creative"), dests.get("return_mission"))


class TestAtomicMissionChordSelection(unittest.TestCase):
    def test_atomic_updates_selected_chord(self) -> None:
        session: dict[str, Any] = {
            "improv_mission_pick": "Outline chord tones",
            "improv_active_mission": "Outline chord tones",
            "improv_mission_chord_options": ["Ab", "B"],
            MISSION_EXAMPLE_KEY: {"chord": "Ab", "mission": "Outline chord tones"},
        }
        apply_atomic_mission_chord_selection(
            session,
            chord="B",
            section="Melody A",
            chord_index=1,
            chord_label="Melody A · B",
        )
        try:
            from creative_mission_config_persistence import canonical_mission_config_value

            ch = canonical_mission_config_value(session, "ii_selected_chord")
            if ch:
                self.assertEqual(str(ch), "B")
            else:
                self.assertEqual(session.get("ii_selected_chord"), "B")
        except ImportError:
            self.assertEqual(session.get("ii_selected_chord"), "B")
        self.assertNotIn(MISSION_EXAMPLE_KEY, session)


if __name__ == "__main__":
    unittest.main()

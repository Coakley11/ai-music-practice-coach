"""Commit 3 — workflow mutation and route precedence tests."""

from __future__ import annotations

import unittest
from typing import Any

from improvisation_missions import MISSION_EXAMPLE_KEY
from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
from music_workflow_mutation import (
    ACTIVE_CREATIVE_VIEW_KEY,
    mutate_mission_chord_selection,
    resolve_workflow_routes,
    update_active_practice_key,
)
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
    workflow_cache_identity,
)
from active_musical_workflow_envelope import apply_atomic_mission_chord_selection


def _session(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"_suite_active_workspace_id": "daniel"}
    base.update(extra)
    return base


class TestMissionChordMutation(unittest.TestCase):
    def test_select_b_updates_active_blob(self) -> None:
        session = _session(
            display_key="Em",
            concert_key="Em",
            active_catalog_pick_key="hevenu",
            improv_active_mission="Outline chord tones",
        )
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|hevenu",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="Ab",
            example_fingerprint="abfp123",
            section_map={"Melody A": ["Em", "B"]},
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|hevenu", context_revision=1),
            source="test",
        )
        session[MISSION_EXAMPLE_KEY] = {"chord": "Ab", "mission": "Outline chord tones"}
        apply_atomic_mission_chord_selection(
            session,
            chord="B",
            section="Melody A",
            chord_index=1,
            chord_label="Melody A · B",
        )
        loaded = get_workflow_blob(session, "mission_jam", "mission|hevenu")
        assert loaded is not None
        self.assertEqual(loaded.selected_chord_symbol, "B")
        self.assertEqual(loaded.keys.practice_tonic, "E")
        self.assertEqual(loaded.keys.practice_mode, "minor")
        self.assertNotIn(MISSION_EXAMPLE_KEY, session)

    def test_mission_chord_does_not_change_song_key(self) -> None:
        session = _session(display_key="Em", concert_key="Em")
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|h",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="Ab",
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|h"),
            source="t",
        )
        mutate_mission_chord_selection(session, chord="B", section="A", chord_index=1, chord_label="B")
        loaded = get_workflow_blob(session, "mission_jam", "mission|h")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_mode, "minor")
        self.assertEqual(loaded.keys.practice_tonic, "E")


class TestRoutePrecedence(unittest.TestCase):
    def test_missions_activation_does_not_bounce_to_backing(self) -> None:
        session = _session(studio_page="creative")
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            last_backing_route="backing",
            page_route="backing",
        )
        save_workflow_blob(session, blob, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="m",
                activation_source="missions_tab_render",
                navigation_intent="creative_missions",
            ),
        )
        self.assertEqual(str(session.get("studio_page")), "creative")

    def test_resolve_routes_creative_over_backing(self) -> None:
        blob = WorkflowStateBlob(last_backing_route="backing", page_route="backing")
        nav = resolve_workflow_routes(blob=blob, navigation_intent="creative_missions")
        self.assertEqual(nav.get("chosen_studio_page"), "creative")
        self.assertIn("STALE_BACKING_ROUTE_OVERRIDE", nav.get("violations") or [])


class TestKeyMutationIsolation(unittest.TestCase):
    def test_style_jam_key_only_updates_style_blob(self) -> None:
        session = _session(improv_style_key="D", display_key="D")
        style = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Disco",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            section_map={"A": ["D", "G"]},
        )
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, style, source="t")
        save_workflow_blob(session, mission, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Disco"),
            source="t",
        )
        update_active_practice_key(session, "G", source="on_improv_style_key_change")
        self.assertEqual(get_workflow_blob(session, "mission_jam", "m").keys.practice_tonic, "E")
        updated = get_workflow_blob(session, "style_jam", "Disco")
        assert updated is not None
        self.assertEqual(updated.keys.practice_tonic, "G")

    def test_generator_key_updates_generator_blob(self) -> None:
        session = _session(
            improv_jam_key="D",
            improv_jam_session={"id": "j1", "sections": {"A": ["D", "A"]}},
        )
        gen = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="j1",
            keys=KeyAuthority(practice_tonic="D", practice_mode="major"),
            section_map={"A": ["D", "A"]},
        )
        save_workflow_blob(session, gen, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="j1"),
            source="t",
        )
        update_active_practice_key(session, "C", source="on_improv_jam_key_change")
        loaded = get_workflow_blob(session, "jam_session_generator", "j1")
        assert loaded is not None
        self.assertEqual(loaded.keys.practice_tonic, "C")


class TestCacheIdentityChord(unittest.TestCase):
    def test_cache_differs_ab_vs_b_mission(self) -> None:
        session = _session()
        b1 = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="Ab",
            example_fingerprint="fp_ab",
        )
        b2 = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="B",
            example_fingerprint="fp_b",
        )
        save_workflow_blob(session, b1, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m"),
            source="t",
        )
        id_ab = workflow_cache_identity(session)
        save_workflow_blob(session, b2, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m", context_revision=2),
            source="t",
        )
        id_b = workflow_cache_identity(session)
        self.assertNotEqual(id_ab, id_b)


class TestCreativeViewSeparate(unittest.TestCase):
    def test_activation_sets_creative_view(self) -> None:
        session = _session()
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="m",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
        )
        save_workflow_blob(session, blob, source="t")
        activate_workflow(
            session,
            ActivateWorkflowRequest(
                target_owner="mission_jam",
                target_session_id="m",
                activation_source="test",
                navigation_intent="creative_missions",
                active_creative_view="Missions",
            ),
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "mission_jam")
        self.assertEqual(session.get(ACTIVE_CREATIVE_VIEW_KEY), "Missions")


if __name__ == "__main__":
    unittest.main()

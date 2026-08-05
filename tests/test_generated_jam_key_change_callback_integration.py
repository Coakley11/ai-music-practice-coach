"""Selectbox callback integration — generated jam key edits + hydration guard."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from generated_jam_key_change import GENERATED_KEY_CHANGE_DIAG_KEY, GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY
from music_workflow_canonical_persistence import apply_workflow_state_canonical_slice
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
)


def _style_session(*, tonic: str = "C") -> dict[str, Any]:
    sections = {"Head (Pop)": ["C", "G", "Am", "F"]}
    style_name = "Pop groove"
    sid = style_name
    blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic=tonic, practice_mode="major"),
        section_map=copy.deepcopy(sections),
        style=style_name,
    )
    session: dict[str, Any] = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": style_name,
        "improv_style_key": tonic,
        "improv_generated_sections": copy.deepcopy(sections),
        "_streamlit_widgets_locked_this_run": True,
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
        source="test",
    )
    return session


class TestGeneratedJamKeyCallbackIntegration(unittest.TestCase):
    def test_style_widget_state_model_c_to_d(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        from generated_jam_key_change import apply_generated_workflow_practice_key_user_edit

        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_style_key")
        )
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        self.assertEqual(session.get("improv_style_key"), "D")
        self.assertIsInstance(session.get(GENERATED_KEY_CHANGE_DIAG_KEY), list)

    def test_generator_widget_state_model_c_to_a(self) -> None:
        sections = {"A": ["Cmaj7", "Am7", "Dm7", "G7"]}
        blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-1",
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map=copy.deepcopy(sections),
            generated_session_id="jam-1",
        )
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "A",
            "improv_jam_session": {"id": "jam-1", "sections": copy.deepcopy(sections)},
            "_streamlit_widgets_locked_this_run": True,
        }
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
            source="test",
        )
        from generated_jam_key_change import apply_generated_workflow_practice_key_user_edit

        self.assertTrue(apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_jam_key"))
        live = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert live is not None
        self.assertEqual(live.keys.practice_tonic, "A")
        self.assertEqual(session.get("improv_jam_key"), "A")

    def test_older_cloud_slice_cannot_overwrite_pending_style_jam_key(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        from generated_jam_key_change import apply_generated_workflow_practice_key_user_edit

        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_style_key")
        )
        live = get_workflow_blob(session, "style_jam", "Pop groove")
        assert live is not None
        old_cloud = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id="Pop groove",
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map={"Head (Pop)": ["C", "G", "Am", "F"]},
        )
        nested = {
            "schema_version": 2,
            "saved_workspace_revision": 1,
            "store": {"schema_version": 1, "blobs": {f"style_jam|Pop groove": old_cloud.to_dict()}},
            "active_pointer": {
                "workflow_owner": "style_jam",
                "workflow_session_id": "Pop groove",
                "context_revision": 1,
            },
        }
        apply_workflow_state_canonical_slice(session, nested)
        after = get_workflow_blob(session, "style_jam", "Pop groove")
        assert after is not None
        self.assertEqual(after.keys.practice_tonic, "D")
        self.assertIn(GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY, session)


if __name__ == "__main__":
    unittest.main()

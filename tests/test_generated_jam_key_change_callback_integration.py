"""Selectbox callback integration — capture → pre-widget consume for generated keys."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from typing import Any

from generated_jam_key_change import GENERATED_KEY_CHANGE_DIAG_KEY, GENERATED_KEY_PENDING_HYDRATE_GUARD_KEY
from music_workflow_canonical_persistence import apply_workflow_state_canonical_slice
from music_workflow_pending_generated_key_edit import (
    PENDING_GENERATED_KEY_EDIT_KEY,
    PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY,
    PENDING_GENERATED_KEY_EDIT_USER_MESSAGE_KEY,
    peek_pending_generated_key_edit,
    run_pre_widget_generated_key_edit_consumer,
)
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
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
        source="test",
    )
    return session


def _generator_session(*, tonic: str = "C") -> dict[str, Any]:
    sections = {"A": ["Cmaj7", "Am7", "Dm7", "G7"]}
    blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id="jam-1",
        keys=KeyAuthority(practice_tonic=tonic, practice_mode="major"),
        section_map=copy.deepcopy(sections),
        generated_session_id="jam-1",
    )
    session: dict[str, Any] = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_key": tonic,
        "improv_jam_session": {"id": "jam-1", "sections": copy.deepcopy(sections)},
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
        source="test",
    )
    return session


class TestGeneratedJamKeyStreamlitOrder(unittest.TestCase):
    def test_style_capture_then_pre_widget_consume(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        session["_streamlit_widgets_locked_this_run"] = True
        from generated_jam_key_change import capture_generated_key_edit_intent

        self.assertTrue(capture_generated_key_edit_intent(session, widget_key="improv_style_key"))
        blob_mid = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob_mid is not None
        self.assertEqual(blob_mid.keys.practice_tonic, "C")
        self.assertIsNotNone(peek_pending_generated_key_edit(session))
        session.pop("_streamlit_widgets_locked_this_run", None)
        phase = run_pre_widget_generated_key_edit_consumer(session)
        self.assertEqual(phase, "applied")
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        self.assertEqual(session.get("improv_style_key"), "D")
        self.assertEqual(session.get("display_key"), "D")
        head = blob.section_map.get("Head (Pop)") or []
        self.assertNotEqual(head[0], "C")
        self.assertIsNone(peek_pending_generated_key_edit(session))

    def test_generator_capture_then_pre_widget_consume(self) -> None:
        session = _generator_session(tonic="C")
        session["improv_jam_key"] = "A"
        session["_streamlit_widgets_locked_this_run"] = True
        from generated_jam_key_change import capture_generated_key_edit_intent

        self.assertTrue(capture_generated_key_edit_intent(session, widget_key="improv_jam_key"))
        mid = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert mid is not None
        self.assertEqual(mid.keys.practice_tonic, "C")
        session.pop("_streamlit_widgets_locked_this_run", None)
        self.assertEqual(run_pre_widget_generated_key_edit_consumer(session), "applied")
        live = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert live is not None
        self.assertEqual(live.keys.practice_tonic, "A")
        jam = session.get("improv_jam_session")
        assert isinstance(jam, dict)
        self.assertEqual(str(jam.get("sections", {}).get("A", [""])[0]), "Amaj7")

    def test_older_cloud_slice_cannot_overwrite_after_consume(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(session, widget_key="improv_style_key")
        run_pre_widget_generated_key_edit_consumer(session)
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

    def test_invalid_pending_intent_fails_closed(self) -> None:
        session = _style_session(tonic="C")
        session[PENDING_GENERATED_KEY_EDIT_KEY] = {
            "request_seq": 1,
            "request_token": "test-token-wrong-id",
            "workflow_owner": "style_jam",
            "workflow_session_id": "wrong-id",
            "widget_key": "improv_style_key",
            "selected_key_token": "D",
            "practice_tonic": "D",
            "practice_mode": "major",
            "callback_source": "on_improv_style_key_change",
        }
        session["improv_style_key"] = "D"
        phase = run_pre_widget_generated_key_edit_consumer(session)
        self.assertEqual(phase, "invalid")
        diag = session.get(PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY)
        assert isinstance(diag, dict)
        self.assertEqual(diag.get("failed_predicate"), "session_id_mismatch")

    def test_callbacks_do_not_mutate_in_widget_phase(self) -> None:
        root = Path(__file__).resolve().parents[1] / "creative_key_sync.py"
        text = root.read_text(encoding="utf-8")
        for fn in ("on_improv_style_key_change", "on_improv_jam_key_change"):
            start = text.index(f"def {fn}(")
            end = text.index("\ndef ", start + 1)
            body = text[start:end]
            self.assertNotIn("update_active_practice_key", body)
            self.assertNotIn("apply_generated_workflow_practice_key_user_edit", body)
            self.assertNotIn("project_active_blob_to_legacy_session", body)
            self.assertIn("capture_generated_key_edit_intent", body)

    def test_no_requires_pre_widget_in_successful_consume(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(session, widget_key="improv_style_key")
        run_pre_widget_generated_key_edit_consumer(session)
        diag = session.get(GENERATED_KEY_CHANGE_DIAG_KEY) or []
        traces = [d for d in diag if isinstance(d, dict)]
        self.assertTrue(any(d.get("phase") == "mutation_result" and d.get("ok") for d in traces))
        for d in traces:
            trace = d.get("trace")
            if isinstance(trace, dict):
                self.assertNotEqual(trace.get("error_code"), "REQUIRES_PRE_WIDGET_ACTIVATION")


if __name__ == "__main__":
    unittest.main()

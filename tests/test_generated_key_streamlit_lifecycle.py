"""Full rerun lifecycle: widget callback → bootstrap consume → canonical + selector."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


def _style_session(*, tonic: str = "C") -> dict[str, Any]:
    sections = {"Head (Pop)": ["C", "G", "Am", "F"]}
    sid = "Pop groove"
    blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic=tonic, practice_mode="major"),
        section_map=copy.deepcopy(sections),
        style=sid,
    )
    session: dict[str, Any] = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": sid,
        "improv_style_key": tonic,
        "improv_generated_sections": copy.deepcopy(sections),
        "_suite_active_workspace_id": "daniel",
        "_suite_account_id": "acct-daniel",
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
        "_suite_active_workspace_id": "daniel",
        "_suite_account_id": "acct-daniel",
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
        source="test",
    )
    return session


def _simulate_widget_rerun(session: dict[str, Any], *, widget_key: str, new_key: str, callback) -> None:
    """Callback run (widgets locked) then next script run bootstrap (pre-widget)."""
    import streamlit as st_mod

    session[widget_key] = new_key
    session["_streamlit_widgets_locked_this_run"] = True
    session["_music_first_streamlit_widget"] = {"marker": widget_key, "simulated": True}
    prior_state = getattr(st_mod, "session_state", None)
    st_mod.session_state = session  # type: ignore[misc]
    try:
        callback()
    finally:
        if prior_state is not None:
            st_mod.session_state = prior_state  # type: ignore[misc]
    session.pop("_streamlit_widgets_locked_this_run", None)
    session.pop("_music_first_streamlit_widget", None)
    session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
    run_pre_widget_application_consumers(session)


class TestGeneratedKeyStreamlitLifecycle(unittest.TestCase):
    def test_style_jam_improv_style_key_callback_then_bootstrap(self) -> None:
        from creative_key_sync import on_improv_style_key_change
        from generated_jam_key_change import GENERATED_KEY_EDIT_OUTCOME_KEY

        session = _style_session(tonic="C")
        before = list(session["improv_generated_sections"]["Head (Pop)"])
        _simulate_widget_rerun(session, widget_key="improv_style_key", new_key="D", callback=on_improv_style_key_change)
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        after = blob.section_map.get("Head (Pop)") or []
        self.assertNotEqual(before, after)
        self.assertEqual(session.get("improv_style_key"), "D")
        outcome = session.get(GENERATED_KEY_EDIT_OUTCOME_KEY) or {}
        self.assertEqual(outcome.get("canonical_commit"), "SUCCESS")
        self.assertEqual(outcome.get("progression_rebuild"), "SUCCESS")

    def test_generator_improv_jam_key_callback_then_bootstrap(self) -> None:
        from creative_key_sync import on_improv_jam_key_change

        session = _generator_session(tonic="C")
        _simulate_widget_rerun(session, widget_key="improv_jam_key", new_key="A", callback=on_improv_jam_key_change)
        blob = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "A")
        self.assertEqual(session.get("improv_jam_key"), "A")

    def test_hevenu_sidebar_identity_structured_dm(self) -> None:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY
        from sidebar_key_identity import resolve_sidebar_key_identity

        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
            "selected_song": {"pick_key": "Jewish|Hevenu Shalom Aleichem", "key": "Dm"},
            "display_key": "D#",
            "concert_key": "D#",
            GENERATED_JAM_KEY_CONTEXT_KEY: {"key_owner": "entry_jam", "entry_mode": "Style Jam Mode"},
        }
        ident = resolve_sidebar_key_identity(session)
        self.assertEqual(ident.concert_tonic, "D")
        self.assertEqual(ident.concert_mode, "minor")
        self.assertEqual(ident.practice_tonic, "D")
        self.assertEqual(ident.practice_mode, "minor")
        self.assertIn(ident.label, {"Dm", "D minor"})

    def test_workspace_scope_mismatch_rejects_pending(self) -> None:
        from music_workflow_pending_generated_key_edit import (
            consume_pending_generated_key_edit,
            queue_pending_generated_key_edit,
        )

        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        queue_pending_generated_key_edit(session, widget_key="improv_style_key", selected_key_token="D")
        session["_suite_account_id"] = "other_account"
        phase = consume_pending_generated_key_edit(session)
        self.assertEqual(phase, "invalid")
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "C")

    def test_bootstrap_runs_once_per_run(self) -> None:
        session: dict[str, Any] = {"_script_run_seq": 1}
        first = run_pre_widget_application_consumers(session)
        second = run_pre_widget_application_consumers(session)
        self.assertEqual(second.get("duplicate_call"), "skipped")
        self.assertEqual(first.get("started_run_seq"), "1")


if __name__ == "__main__":
    unittest.main()

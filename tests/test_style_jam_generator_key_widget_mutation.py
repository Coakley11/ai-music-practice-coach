"""Style Jam / Generator major-key edits during widget phase (Commit 7 regression)."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from generated_jam_key_change import apply_generated_workflow_practice_key_user_edit
from music_workflow_mutation import update_active_practice_key
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
)
from music_workflow_restore_guard import activate_workflow_restore_guard, complete_workflow_restore_guard


def _style_jam_session(*, tonic: str = "C", sections: dict | None = None) -> dict[str, Any]:
    sections = sections or {"Head (Pop)": ["C", "G", "Am", "F"]}
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
        "_creative_mission_widgets_instantiated": True,
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
    jam = {"id": "jam-1", "title": "Jam", "sections": copy.deepcopy(sections)}
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
        "improv_jam_session": copy.deepcopy(jam),
        "_streamlit_widgets_locked_this_run": True,
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id="jam-1"),
        source="test",
    )
    return session


class TestStyleJamGeneratorKeyWidgetMutation(unittest.TestCase):
    def test_style_jam_c_to_d_with_widgets_locked(self) -> None:
        session = _style_jam_session(tonic="C")
        before = list(session["improv_generated_sections"]["Head (Pop)"])
        session["improv_style_key"] = "D"
        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_style_key")
        )
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        self.assertEqual(blob.keys.practice_mode, "major")
        after = blob.section_map.get("Head (Pop)") or []
        self.assertNotEqual(before, after)
        self.assertEqual(session.get("improv_style_key"), "D")

    def test_generator_c_to_a_with_widgets_locked(self) -> None:
        session = _generator_session(tonic="C")
        session["improv_jam_key"] = "A"
        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_jam_key")
        )
        blob = get_workflow_blob(session, "jam_session_generator", "jam-1")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "A")
        self.assertEqual(session.get("improv_jam_key"), "A")
        jam = session.get("improv_jam_session")
        assert isinstance(jam, dict)
        self.assertEqual(str(jam.get("sections", {}).get("A", [""])[0]), "Amaj7")

    def test_style_jam_and_generator_blobs_independent(self) -> None:
        style_sess = _style_jam_session(tonic="C")
        gen_sess = _generator_session(tonic="C")
        style_sess["improv_style_key"] = "D"
        gen_sess["improv_jam_key"] = "A"
        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(style_sess, widget_key="improv_style_key")
        )
        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(gen_sess, widget_key="improv_jam_key")
        )
        style_blob = get_workflow_blob(style_sess, "style_jam", "Pop groove")
        gen_blob = get_workflow_blob(gen_sess, "jam_session_generator", "jam-1")
        assert style_blob is not None and gen_blob is not None
        self.assertEqual(style_blob.keys.practice_tonic, "D")
        self.assertEqual(gen_blob.keys.practice_tonic, "A")

    def test_user_key_change_after_restore_guard_completes(self) -> None:
        session = _style_jam_session(tonic="C")
        activate_workflow_restore_guard(session, run_id="run-1")
        session["_music_script_run_id"] = "run-1"
        complete_workflow_restore_guard(session)
        session["improv_style_key"] = "D"
        self.assertTrue(
            apply_generated_workflow_practice_key_user_edit(session, widget_key="improv_style_key")
        )
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")

    def test_pre_widget_key_change_without_widget_lock(self) -> None:
        session = _style_jam_session(tonic="C")
        session.pop("_streamlit_widgets_locked_this_run", None)
        result = update_active_practice_key(
            session, "D", source="on_improv_style_key_change", transpose_progression=True
        )
        self.assertTrue(result.ok, msg=str(result.trace))
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")

    def test_stale_legacy_display_key_blocked_while_guard_active(self) -> None:
        from music_workflow_restore_guard import block_legacy_overwrite

        session = _style_jam_session(tonic="D")
        activate_workflow_restore_guard(session, run_id="run-x")
        session["_music_script_run_id"] = "run-x"
        self.assertTrue(
            block_legacy_overwrite(
                session,
                "display_key",
                caller="stale_adapter",
                value="C",
                authoritative_projection=False,
            )
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")


if __name__ == "__main__":
    unittest.main()

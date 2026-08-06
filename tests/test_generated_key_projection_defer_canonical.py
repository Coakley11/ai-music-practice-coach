"""Canonical blob retained when legacy projection defers for generated key edits."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_workflow_mutation import update_active_practice_key
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)


def _style_session(*, tonic: str = "C") -> dict[str, Any]:
    sid = "Pop groove"
    blob = WorkflowStateBlob(
        workflow_owner="style_jam",
        workflow_session_id=sid,
        keys=KeyAuthority(practice_tonic=tonic, practice_mode="major"),
        section_map={"Head (Pop)": ["C", "G", "Am", "F"]},
        style=sid,
    )
    session: dict[str, Any] = {
        "improv_style": sid,
        "improv_style_key": "D",
        "_streamlit_widgets_locked_this_run": True,
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
        source="test",
    )
    return session


class TestGeneratedKeyProjectionDeferCanonical(unittest.TestCase):
    def test_practice_key_mutation_ok_when_projection_blocked(self) -> None:
        session = _style_session(tonic="C")
        result = update_active_practice_key(
            session,
            "D",
            source="on_improv_style_key_change",
            transpose_progression=True,
        )
        self.assertTrue(result.ok, msg=str(result.trace))
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")
        self.assertIn("D", str(blob.section_map.get("Head (Pop)", [""])[0]))


if __name__ == "__main__":
    unittest.main()

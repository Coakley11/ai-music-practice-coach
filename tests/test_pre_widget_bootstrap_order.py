"""Pre-widget bootstrap must run before auth widgets and duplicate late consumers."""

from __future__ import annotations

import unittest
from pathlib import Path


class TestPreWidgetBootstrapScriptOrder(unittest.TestCase):
    def test_bootstrap_before_auth_gate_in_entry_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        bootstrap = text.find("run_pre_widget_application_consumers")
        auth = text.find("apply_suite_auth_gate(st)")
        self.assertGreater(bootstrap, 0)
        self.assertGreater(auth, 0)
        self.assertLess(bootstrap, auth, "pre-widget bootstrap must run before apply_suite_auth_gate")

    def test_late_block_is_fallback_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("PRE_WIDGET_BOOTSTRAP_RAN_KEY", text)
        self.assertNotIn("run_pre_widget_generated_key_edit_consumer", text)


class TestBootstrapAllowsConsumeUnderLockFlag(unittest.TestCase):
    def test_consume_runs_during_bootstrap_active(self) -> None:
        import copy

        from music_workflow_pending_generated_key_edit import (
            consume_pending_generated_key_edit,
            queue_pending_generated_key_edit,
        )
        from music_workflow_pre_widget_bootstrap import PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            get_workflow_blob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )

        sections = {"Head (Pop)": ["C", "G", "Am", "F"]}
        sid = "Pop groove"
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id=sid,
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map=copy.deepcopy(sections),
            style=sid,
        )
        session: dict = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
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
        queue_pending_generated_key_edit(session, widget_key="improv_style_key", selected_key_token="D")
        session[PRE_WIDGET_BOOTSTRAP_ACTIVE_KEY] = True
        phase = consume_pending_generated_key_edit(session)
        self.assertEqual(phase, "applied")
        live = get_workflow_blob(session, "style_jam", sid)
        assert live is not None
        self.assertEqual(live.keys.practice_tonic, "D")


if __name__ == "__main__":
    unittest.main()

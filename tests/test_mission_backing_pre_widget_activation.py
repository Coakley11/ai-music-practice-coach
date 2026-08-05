"""Mission / Jam backing must defer workflow activation until pre-widget script run."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from music_workflow_legacy_projection import RequiresPreWidgetActivation, project_active_blob_to_legacy_session
from music_workflow_pending_backing_handoff import (
    PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY,
    PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY,
    PENDING_BACKING_WORKFLOW_KEY,
    PENDING_BACKING_WORKFLOW_RERUN_SEQ_KEY,
    arm_pending_backing_handoff_consume,
    consume_pending_backing_workflow_handoff,
    peek_pending_backing_workflow_handoff,
    queue_pending_backing_workflow_handoff,
    resolve_backing_workflow_owner,
    should_request_backing_handoff_rerun,
)
from music_workflow_state_store import KeyAuthority, WorkflowStateBlob


def _mission_blob() -> WorkflowStateBlob:
    return WorkflowStateBlob(
        workflow_owner="mission_jam",
        workflow_session_id="ms-test",
        keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
        selected_chord_symbol="Cmaj7",
        selected_section="A",
    )


class TestMissionBackingPreWidgetActivation(unittest.TestCase):
    def test_click_run_queues_one_pending_request_when_widgets_locked(self) -> None:
        session: dict = {"_streamlit_widgets_locked_this_run": True}
        req = queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        self.assertEqual(req["request_seq"], 1)
        self.assertEqual(peek_pending_backing_workflow_handoff(session), session[PENDING_BACKING_WORKFLOW_KEY])
        req2 = queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        self.assertEqual(req2["request_seq"], 2)

    def test_rerun_guard_fires_once_per_seq(self) -> None:
        session: dict = {}
        queue_pending_backing_workflow_handoff(session, backing_source="mission", workflow_owner="mission_jam")
        self.assertTrue(should_request_backing_handoff_rerun(session))
        self.assertFalse(should_request_backing_handoff_rerun(session))

    def test_new_request_seq_changes_rerun_fingerprint(self) -> None:
        from music_workflow_pending_backing_handoff import build_backing_handoff_rerun_fingerprint

        session: dict = {"studio_page": "creative"}
        q1 = queue_pending_backing_workflow_handoff(
            session, backing_source="mission", workflow_owner="mission_jam", with_practice_lick=False
        )
        fp1 = build_backing_handoff_rerun_fingerprint(session, q1)
        q2 = queue_pending_backing_workflow_handoff(
            session, backing_source="mission", workflow_owner="mission_jam", with_practice_lick=True
        )
        fp2 = build_backing_handoff_rerun_fingerprint(session, q2)
        self.assertNotEqual(fp1, fp2)

    def test_blocked_rerun_does_not_call_bare_st_rerun(self) -> None:
        from music_workflow_pending_backing_handoff import (
            PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY,
            PENDING_BACKING_WORKFLOW_KEY,
            PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY,
            request_pending_backing_handoff_rerun,
        )

        session: dict = {"studio_page": "creative", "_creative_mission_widgets_instantiated": True}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
        )
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=False):
            sent = request_pending_backing_handoff_rerun(st_mock, session)
        self.assertFalse(sent)
        st_mock.rerun.assert_not_called()
        self.assertIsInstance(session.get(PENDING_BACKING_WORKFLOW_KEY), dict)
        self.assertIn("status", session.get(PENDING_BACKING_WORKFLOW_RERUN_DIAG_KEY) or {})
        self.assertTrue(session.get(PENDING_BACKING_HANDOFF_USER_MESSAGE_KEY))

    def test_improv_open_backing_mission_deferred_path_has_no_bare_rerun(self) -> None:
        root = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        text = root.read_text(encoding="utf-8")
        start = text.index("def _improv_open_backing")
        end = text.index("\n    def _improv_open_practice", start)
        body = text[start:end]
        self.assertIn("defer_wf and creative_source == \"mission\"", body)
        self.assertIn("request_pending_backing_handoff_rerun", body)
        mission_block = body[body.index("if defer_wf and creative_source") : body.index("open_backing_from_creative(")]
        self.assertNotIn("st.rerun()", mission_block)

    def test_late_projection_raises_requires_pre_widget_activation(self) -> None:
        session: dict = {"_streamlit_widgets_locked_this_run": True, "display_key": "C"}
        with self.assertRaises(RequiresPreWidgetActivation):
            project_active_blob_to_legacy_session(session, _mission_blob())

    def test_open_backing_supports_skip_workflow_activation_flag(self) -> None:
        root = Path(__file__).resolve().parents[1] / "backing_context.py"
        text = root.read_text(encoding="utf-8")
        self.assertIn("skip_workflow_activation: bool = False", text)
        self.assertIn("if not skip_workflow_activation:", text)

    def test_improv_open_backing_defers_late_activation(self) -> None:
        root = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        text = root.read_text(encoding="utf-8")
        start = text.index("def _improv_open_backing")
        end = text.index("\n    def _improv_open_practice", start)
        body = text[start:end]
        self.assertIn("should_defer_backing_workflow_activation", body)
        self.assertIn("queue_pending_backing_workflow_handoff", body)
        self.assertIn("skip_workflow_activation=defer_wf or not needs_activation", body)

    def test_pre_widget_consumer_before_studio_page_routing(self) -> None:
        root = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        text = root.read_text(encoding="utf-8")
        consume_idx = text.index("consume_pending_backing_workflow_handoff(st.session_state")
        page_idx = text.index("_studio_page = ensure_studio_page(st.session_state)")
        self.assertLess(consume_idx, page_idx)

    def test_consume_marks_consumed_and_clears_pending(self) -> None:
        session: dict = {
            "improv_entry_mode": "Style Jam Mode",
            "studio_page": "creative",
        }
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        arm_pending_backing_handoff_consume(session)
        seq = session[PENDING_BACKING_WORKFLOW_KEY]["request_seq"]
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("backing_context.open_backing_from_creative"):
                phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))
        self.assertEqual(session.get(PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY), seq)

    def test_refresh_does_not_replay_consumed_seq(self) -> None:
        session: dict = {}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        pending = session[PENDING_BACKING_WORKFLOW_KEY]
        seq = pending["request_seq"]
        session[PENDING_BACKING_WORKFLOW_CONSUMED_SEQ_KEY] = seq
        session[PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY] = pending["consume_token"]
        session[PENDING_BACKING_WORKFLOW_KEY] = dict(pending)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "already_consumed")
        activate.assert_not_called()

    def test_style_jam_owner_resolution(self) -> None:
        session: dict = {"improv_entry_mode": "Style Jam Mode"}
        owner = resolve_backing_workflow_owner(session, backing_source="entry_jam")
        self.assertIn(owner, {"style_jam", "jam_session_generator", "entry_jam"})

    def test_generator_owner_resolution(self) -> None:
        session: dict = {"improv_entry_mode": "Jam Session Generator"}
        owner = resolve_backing_workflow_owner(session, backing_source="entry_jam")
        self.assertIn(owner, {"style_jam", "jam_session_generator", "entry_jam"})

    def test_commit_rollback_on_requires_pre_widget_activation(self) -> None:
        from music_workflow_mutation import commit_staged_workflow
        from music_workflow_state_store import ActiveWorkflowPointer, set_active_workflow_pointer

        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "C",
            "studio_page": "creative",
        }
        blob = _mission_blob()
        ptr = ActiveWorkflowPointer(
            workflow_owner="mission_jam",
            workflow_session_id="ms-test",
            context_revision=1,
            activation_source="test",
            workspace_id="ws",
            account_id="acct",
        )
        set_active_workflow_pointer(session, ptr, source="test_setup")
        with mock.patch("music_workflow_state_store.save_workflow_blob"):
            result = commit_staged_workflow(
                session,
                blob,
                mutation_type="workflow_activation",
                source="test_late",
                ptr=ptr,
                legacy_snapshot={"display_key": "C"},
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "REQUIRES_PRE_WIDGET_ACTIVATION")
        self.assertTrue(session.get(PENDING_BACKING_WORKFLOW_KEY))


if __name__ == "__main__":
    unittest.main()

"""Mission backing alignment deferral and widget-safe workflow rollback."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest import mock

from mission_backing_alignment import (
    MISSION_PENDING_BACKING_ALIGNMENT_KEY,
    build_mission_backing_alignment_payload,
    mission_alignment_fingerprint,
)
from music_workflow_legacy_projection import RequiresPreWidgetActivation, project_active_blob_to_legacy_session
from music_workflow_mutation import _restore_legacy_snapshot, commit_staged_workflow
from music_workflow_pending_backing_handoff import (
    PENDING_BACKING_WORKFLOW_KEY,
    consume_pending_backing_workflow_handoff,
    queue_pending_backing_workflow_handoff,
)
from music_workflow_state_store import ActiveWorkflowPointer, KeyAuthority, WorkflowStateBlob, set_active_workflow_pointer


def _mission_blob() -> WorkflowStateBlob:
    return WorkflowStateBlob(
        workflow_owner="mission_jam",
        workflow_session_id="ms-test",
        keys=KeyAuthority(practice_tonic="D", practice_mode="minor"),
        selected_chord_symbol="Bb",
        selected_section="A",
    )


class TestMissionBackingAlignmentAndRollback(unittest.TestCase):
    def test_open_mission_backing_defers_mutable_alignment_when_locked(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        start = text.index("def _open_mission_backing")
        end = text.index("\n    if not example:", start)
        body = text[start:end]
        self.assertIn("should_defer_backing_workflow_activation", body)
        self.assertIn("build_mission_backing_alignment_payload", body)
        self.assertIn("if with_practice_lick and example and defer:", body)

    def test_alignment_payload_is_complete(self) -> None:
        session: dict = {
            "display_key": "Dm",
            "concert_key": "Dm",
            "active_catalog_pick_key": "Hevenu",
        }
        payload = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=2,
            song_title="Hevenu",
            concert_key="Dm",
            display_key="Dm",
        )
        self.assertEqual(payload["chord_symbol"], "Bb")
        self.assertEqual(payload["section_label"], "Verse")
        self.assertEqual(payload["concert_key"], "Dm")
        self.assertTrue(payload.get("alignment_fingerprint"))

    def test_click_run_queues_alignment_in_pending_handoff(self) -> None:
        session: dict = {"_streamlit_widgets_locked_this_run": True}
        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="Song",
        )
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            mission_alignment=align,
        )
        req = session[PENDING_BACKING_WORKFLOW_KEY]
        self.assertIsInstance(req.get("mission_alignment"), dict)
        self.assertEqual(req["alignment_fingerprint"], mission_alignment_fingerprint(align))

    def test_requires_pre_widget_does_not_restore_display_key(self) -> None:
        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "C",
            "studio_page": "creative",
        }
        snap = {"display_key": "F#", "concert_key": "F#", "improv_intelligence_tab": "Missions"}
        skipped = _restore_legacy_snapshot(session, snap, widget_safe=True)
        self.assertEqual(session.get("display_key"), "C")
        self.assertIn("display_key", skipped)

    def test_commit_requires_pre_widget_skips_legacy_fail_mutation_restore(self) -> None:
        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "C",
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
                legacy_snapshot={"display_key": "A"},
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "REQUIRES_PRE_WIDGET_ACTIVATION")
        self.assertEqual(session.get("display_key"), "C")

    def test_consume_applies_alignment_once(self) -> None:
        session: dict = {"studio_page": "creative"}
        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=1,
            song_title="Song",
        )
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            mission_alignment=align,
        )
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment") as apply_align:
                apply_align.return_value = True
                with mock.patch("backing_context.open_backing_from_creative"):
                    phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        apply_align.assert_called_once()

    def test_locked_rollback_never_assigns_display_key_directly(self) -> None:
        session: dict = {"_streamlit_widgets_locked_this_run": True, "display_key": "Dm"}
        original = copy.deepcopy(session)
        _restore_legacy_snapshot(
            session,
            {"display_key": "A", "improv_active_mission": "Outline"},
            widget_safe=True,
        )
        self.assertEqual(session.get("display_key"), original["display_key"])
        self.assertEqual(session.get("improv_active_mission"), "Outline")


class TestMissionNotationStaffKey(unittest.TestCase):
    def test_d_minor_bb_mission_one_flat_signature(self) -> None:
        from harmonic_spelling import mission_notation_staff_key
        from improvisation_missions import rebuild_mission_outputs

        motif = {
            "notes": ["Bb", "D", "F"],
            "rhythm": "quarter quarter quarter",
            "midi": [70, 74, 77],
        }
        out = rebuild_mission_outputs(
            motif,
            chord="Bb",
            instrument="Piano",
            key_center="Dm",
            bpm=100,
            song_display_key="Dm",
            song_concert_key="Dm",
        )
        abc = str(out.get("abc") or "")
        self.assertIn("K:d", abc.replace(" ", ""))
        self.assertNotIn("K:A", abc)
        self.assertNotIn("K:F#", abc)
        staff = mission_notation_staff_key(song_concert_key="Dm", song_display_key="Dm")
        self.assertEqual(staff, "Dm")

    def test_chord_tones_bb_d_f(self) -> None:
        from improvisation_motif import chord_tone_names

        tones = chord_tone_names("Bb", reference_key="Bb")
        self.assertEqual([t.replace("♭", "b") for t in tones], ["Bb", "D", "F"])


if __name__ == "__main__":
    unittest.main()

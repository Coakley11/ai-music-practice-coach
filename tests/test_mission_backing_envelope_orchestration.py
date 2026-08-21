"""Mission envelope prerequisite + Practice-in-Jam backing orchestration."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY, activate_generated_jam_key_ownership
from mission_backing_alignment import build_mission_backing_alignment_payload
from music_workflow_mission_backing_orchestration import (
    mission_envelope_reconciliation_required,
    prepare_deferred_mission_backing_handoff,
    run_pre_widget_mission_handoff_consumers,
    try_finalize_backing_after_mission_envelope,
)
from music_workflow_pending_backing_handoff import (
    PENDING_BACKING_WORKFLOW_KEY,
    arm_pending_backing_handoff_consume,
    consume_pending_backing_workflow_handoff,
    peek_pending_backing_workflow_handoff,
    queue_pending_backing_workflow_handoff,
)
from music_workflow_pending_mission_envelope import peek_pending_mission_envelope_reconciliation
from workflow_musical_authority import save_workflow_snapshot, switch_workflow_owner


class TestMissionBackingEnvelopeOrchestration(unittest.TestCase):
    def _missions_with_jam_ownership(self) -> dict[str, Any]:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Em",
            "concert_key": "Em",
            "improv_entry_mode": "Style Jam Mode",
            "improv_jam_key": "A",
            "ii_selected_chord": "B",
            "_creative_mission_widgets_instantiated": True,
            "_streamlit_widgets_locked_this_run": True,
        }
        save_workflow_snapshot(session, "style_jam")
        activate_generated_jam_key_ownership(session, entry_mode="Style Jam Mode")
        session["display_key"] = "A"
        switch_workflow_owner(session, "mission_jam")
        return session

    def test_practice_in_jam_click_captures_intent_with_envelope_prerequisite(self) -> None:
        session = self._missions_with_jam_ownership()
        self.assertTrue(mission_envelope_reconciliation_required(session))
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="B",
            section_label="A",
            chord_idx=0,
            song_title="Song",
            with_practice_lick=True,
        )
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            ok = prepare_deferred_mission_backing_handoff(
                st_mock,
                session,
                backing_source="mission",
                workflow_owner="mission_jam",
                with_practice_lick=True,
                mission_alignment=align,
            )
        self.assertTrue(ok)
        backing = peek_pending_backing_workflow_handoff(session)
        self.assertIsNotNone(backing)
        assert backing is not None
        # Explicit click + alignment reconciles synchronously — do not defer on envelope.
        self.assertFalse(backing.get("waiting_for_mission_envelope"))
        self.assertTrue(session.get("_mission_backing_envelope_defer_overridden"))
        self.assertEqual(backing.get("handoff_mode"), "practice_in_jam")
        diag = session.get("_mission_explicit_handoff_envelope_diag") or {}
        self.assertIn("consistent", diag)

    def test_orchestrated_pre_widget_opens_backing_one_click(self) -> None:
        session = self._missions_with_jam_ownership()
        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="B",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=True,
        )
        session.pop("_streamlit_widgets_locked_this_run", None)
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            mission_alignment=align,
            waiting_for_mission_envelope=True,
        )
        from music_workflow_pending_mission_envelope import queue_pending_mission_envelope_reconciliation

        queue_pending_mission_envelope_reconciliation(session, reason="t", violations=[])
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                with mock.patch("backing_context.open_backing_from_creative"):
                    phases = run_pre_widget_mission_handoff_consumers(session)
        self.assertIn(phases.get("mission_envelope"), {"applied", "applied_pending"})
        self.assertEqual(phases.get("backing_handoff"), "applied")
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))

    def test_waiting_backing_not_cleared_when_unarmed(self) -> None:
        session: dict[str, Any] = {"studio_page": "creative"}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            waiting_for_mission_envelope=True,
        )
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "skipped")
        activate.assert_not_called()
        self.assertIsNotNone(peek_pending_backing_workflow_handoff(session))

    def test_finalize_arms_backing_after_envelope(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Em",
            "concert_key": "Em",
            "ii_selected_chord": "B",
        }
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=False,
            waiting_for_mission_envelope=True,
        )
        self.assertFalse(mission_envelope_reconciliation_required(session))
        self.assertTrue(try_finalize_backing_after_mission_envelope(session))
        pending = peek_pending_backing_workflow_handoff(session)
        assert pending is not None
        self.assertFalse(pending.get("waiting_for_mission_envelope"))
        arm_pending_backing_handoff_consume(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("backing_context.open_backing_from_creative"):
                phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")

    def test_tab_missions_requests_rerun_without_queuing_envelope(self) -> None:
        """Missions tab may consume pending envelope work via rerun; queuing stays in orchestration."""
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        start = text.index("def _tab_missions(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        self.assertIn("request_pending_mission_envelope_rerun", body)
        self.assertIn("peek_pending_mission_envelope_reconciliation", body)
        self.assertNotIn("queue_pending_mission_envelope_reconciliation", body)


if __name__ == "__main__":
    unittest.main()

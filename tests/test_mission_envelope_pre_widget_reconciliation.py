"""Pre-widget mission envelope reconciliation — generated jam key ownership."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from active_musical_workflow_envelope import (
    VIOLATION_STALE_GENERATED_JAM_KEY_LEAK,
    apply_mission_workflow_envelope_reconciliation,
    inspect_mission_workflow_envelope,
    reconcile_mission_workflow_envelope,
    validate_mission_workflow_envelope,
)
from generated_jam_key_context import (
    GENERATED_JAM_KEY_CONTEXT_KEY,
    SONG_PRACTICE_KEY_SNAPSHOT_KEY,
    activate_generated_jam_key_ownership,
    deactivate_generated_jam_key_ownership,
)
from music_workflow_pending_mission_envelope import (
    PENDING_MISSION_ENVELOPE_KEY,
    ensure_mission_envelope_reconciliation_before_widgets,
    peek_pending_mission_envelope_reconciliation,
    queue_pending_mission_envelope_reconciliation,
)
from workflow_musical_authority import save_workflow_snapshot, switch_workflow_owner


class TestGeneratedJamKeyOwnershipAudit(unittest.TestCase):
    def test_deactivate_writes_classified_keys_pre_widget(self) -> None:
        session: dict[str, Any] = {
            "display_key": "D",
            "concert_key": "D",
            GENERATED_JAM_KEY_CONTEXT_KEY: {"key_owner": "entry_jam"},
            SONG_PRACTICE_KEY_SNAPSHOT_KEY: {
                "display_key": "Em",
                "concert_key": "Em",
                "practice_concert_key": "Em",
            },
        }
        self.assertTrue(deactivate_generated_jam_key_ownership(session, pre_widget=True))
        self.assertEqual(session.get("display_key"), "Em")
        self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)

    def test_deactivate_no_op_when_widgets_locked(self) -> None:
        session: dict[str, Any] = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "D",
            GENERATED_JAM_KEY_CONTEXT_KEY: {"key_owner": "entry_jam"},
            SONG_PRACTICE_KEY_SNAPSHOT_KEY: {"display_key": "Em", "concert_key": "Em"},
        }
        self.assertFalse(deactivate_generated_jam_key_ownership(session))
        self.assertIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)
        self.assertEqual(session.get("display_key"), "D")


class TestMissionEnvelopePreWidgetReconciliation(unittest.TestCase):
    def _style_jam_then_missions_session(self) -> dict[str, Any]:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Em",
            "concert_key": "Em",
            "improv_entry_mode": "Style Jam Mode",
            "improv_jam_key": "A",
            "ii_selected_chord": "B",
            "ii_selected_section": "Chorus",
            "ii_selected_chord_index": 0,
        }
        save_workflow_snapshot(session, "song_based_improvisation")
        save_workflow_snapshot(session, "style_jam")
        activate_generated_jam_key_ownership(session, entry_mode="Style Jam Mode")
        session["display_key"] = "A"
        session["concert_key"] = "A"
        switch_workflow_owner(session, "mission_jam")
        return session

    def test_pre_widget_releases_generated_jam_ownership(self) -> None:
        session = self._style_jam_then_missions_session()
        self.assertIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)
        status = ensure_mission_envelope_reconciliation_before_widgets(session)
        self.assertEqual(status, "applied")
        self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)
        self.assertNotEqual(str(session.get("display_key")), "A")

    def test_style_jam_snapshot_preserved_after_mission_reconcile(self) -> None:
        session = self._style_jam_then_missions_session()
        from workflow_musical_authority import WORKFLOW_MUSICAL_STATES_KEY

        store = dict(session.get(WORKFLOW_MUSICAL_STATES_KEY) or {})
        style_before = store.get("style_jam")
        ensure_mission_envelope_reconciliation_before_widgets(session)
        store_after = dict(session.get(WORKFLOW_MUSICAL_STATES_KEY) or {})
        self.assertEqual(store_after.get("style_jam"), style_before)

    def test_inspect_does_not_mutate(self) -> None:
        session = self._style_jam_then_missions_session()
        before = dict(session)
        inspect_mission_workflow_envelope(session)
        self.assertEqual(session.get("display_key"), before.get("display_key"))
        self.assertIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)

    def test_locked_reconcile_queues_pending_not_display_key(self) -> None:
        session = self._style_jam_then_missions_session()
        session["_streamlit_widgets_locked_this_run"] = True
        with mock.patch(
            "generated_jam_key_context.deactivate_generated_jam_key_ownership",
            wraps=deactivate_generated_jam_key_ownership,
        ) as deactivate:
            reconcile_mission_workflow_envelope(session)
        deactivate.assert_not_called()
        self.assertIsNotNone(peek_pending_mission_envelope_reconciliation(session))

    def test_tab_missions_source_uses_inspect_not_mutating_reconcile(self) -> None:
        from pathlib import Path

        text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        start = text.index("def _tab_missions(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        self.assertIn("inspect_mission_workflow_envelope", body)
        self.assertNotIn("reconcile_mission_workflow_envelope(session_state)", body)

    def test_late_queue_requests_guarded_rerun(self) -> None:
        session: dict[str, Any] = {"studio_page": "creative"}
        queue_pending_mission_envelope_reconciliation(session, reason="t", violations=["x"])
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True) as rerun:
            from music_workflow_pending_mission_envelope import request_pending_mission_envelope_rerun

            self.assertTrue(request_pending_mission_envelope_rerun(st_mock, session))
        rerun.assert_called_once()

    def test_generator_entry_same_pre_widget_path(self) -> None:
        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "display_key": "Em",
            "concert_key": "Em",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "F",
            "ii_selected_chord": "C",
        }
        activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator")
        session["display_key"] = "F"
        switch_workflow_owner(session, "mission_jam")
        diag = validate_mission_workflow_envelope(session)
        if VIOLATION_STALE_GENERATED_JAM_KEY_LEAK in diag.get("violations", []):
            apply_mission_workflow_envelope_reconciliation(session)
            self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)


if __name__ == "__main__":
    unittest.main()

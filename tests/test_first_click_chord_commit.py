"""First-click chord selection must commit in the same run (no pre-widget UI leak)."""

from __future__ import annotations

import unittest
from unittest import mock


class FirstClickChordCommitTests(unittest.TestCase):
    def test_mission_chord_click_keeps_canonical_when_widgets_locked(self) -> None:
        """Widgets already instantiated must not roll back an explicit chord click."""
        from music_workflow_legacy_projection import RequiresPreWidgetActivation
        from music_workflow_mutation import mutate_mission_chord_selection
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )

        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "E",
            "concert_key": "E",
            "improv_active_mission": "Improvise using only chord tones",
            "ii_selected_chord": "F#m",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 0,
            "ii_selected_chord_label": "Verse 1 · F#m",
        }
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="ms-chord-click",
            keys=KeyAuthority(practice_tonic="E", practice_mode="major"),
            selected_chord_symbol="F#m",
            selected_section="Verse 1",
            selected_chord_index=0,
        )
        ptr = ActiveWorkflowPointer(
            workflow_owner="mission_jam",
            workflow_session_id="ms-chord-click",
            context_revision=1,
            activation_source="test",
            workspace_id="ws",
            account_id="acct",
        )
        set_active_workflow_pointer(session, ptr, source="test_setup")
        save_workflow_blob(session, blob, source="test_setup")

        with mock.patch(
            "music_workflow_mutation.project_active_blob_to_legacy_session",
            side_effect=RequiresPreWidgetActivation("mission_jam", field="display_key"),
        ):
            result = mutate_mission_chord_selection(
                session,
                chord="G",
                section="Verse 1",
                chord_index=1,
                chord_label="Verse 1 · G",
                button_key="ii_chord_tile_1",
            )

        self.assertTrue(result.ok, msg=f"expected first-click ok, got {result}")
        self.assertEqual(result.error_code, "PROJECTION_DEFERRED")
        self.assertNotIn("requires_pre_widget_activation", (result.error_message or "").lower())
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "G")
        self.assertEqual(int(session.get("ii_selected_chord_index") or -1), 1)

    def test_non_mission_owner_still_seals_chord_without_ui_error(self) -> None:
        """Live Coach / Harmony may not have mission_jam active — click still commits."""
        from music_workflow_mutation import mutate_mission_chord_selection
        from music_workflow_state_store import (
            ActiveWorkflowPointer,
            KeyAuthority,
            WorkflowStateBlob,
            save_workflow_blob,
            set_active_workflow_pointer,
        )

        session: dict = {
            "ii_selected_chord": "F#m",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 0,
            "ii_selected_chord_label": "Verse 1 · F#m",
        }
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id="sbi-1",
            keys=KeyAuthority(practice_tonic="E", practice_mode="major"),
            selected_chord_symbol="F#m",
            selected_section="Verse 1",
            selected_chord_index=0,
        )
        ptr = ActiveWorkflowPointer(
            workflow_owner="song_based_improvisation",
            workflow_session_id="sbi-1",
            context_revision=1,
            activation_source="test",
            workspace_id="ws",
            account_id="acct",
        )
        set_active_workflow_pointer(session, ptr, source="test_setup")
        save_workflow_blob(session, blob, source="test_setup")

        with mock.patch(
            "music_workflow_activation.activate_workflow",
            return_value=mock.Mock(ok=False),
        ):
            result = mutate_mission_chord_selection(
                session,
                chord="G",
                section="Verse 1",
                chord_index=1,
                chord_label="Verse 1 · G",
                button_key="ii_chord_tile_1",
            )

        self.assertTrue(result.ok, msg=f"expected sealed ok, got {result}")
        self.assertEqual(result.error_code, "CHORD_OWNER_ACTIVATE_DEFERRED")
        self.assertEqual(result.error_message, "")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "G")

    def test_envelope_never_warns_internal_pre_widget_token(self) -> None:
        from active_musical_workflow_envelope import apply_atomic_mission_chord_selection
        from music_workflow_mutation import MutationResult

        session: dict = {}
        warnings: list[str] = []

        class _St:
            @staticmethod
            def warning(msg: str) -> None:
                warnings.append(str(msg))

        with mock.patch(
            "music_workflow_mutation.mutate_mission_chord_selection",
            return_value=MutationResult(
                ok=False,
                error_code="REQUIRES_PRE_WIDGET_ACTIVATION",
                error_message="requires_pre_widget_activation:mission_jam:display_key",
            ),
        ):
            with mock.patch.dict("sys.modules", {"streamlit": _St()}):
                apply_atomic_mission_chord_selection(
                    session,
                    chord="G",
                    section="Verse 1",
                    chord_index=1,
                    chord_label="Verse 1 · G",
                )

        leaked = [w for w in warnings if "requires_pre_widget_activation" in w.lower()]
        self.assertEqual(leaked, [], msg=f"internal token leaked: {warnings}")

    def test_envelope_never_warns_owner_mismatch(self) -> None:
        from active_musical_workflow_envelope import apply_atomic_mission_chord_selection
        from music_workflow_mutation import MutationResult

        warnings: list[str] = []

        class _St:
            @staticmethod
            def warning(msg: str) -> None:
                warnings.append(str(msg))

        with mock.patch(
            "music_workflow_mutation.mutate_mission_chord_selection",
            return_value=MutationResult(
                ok=False,
                error_code="OWNER_MISMATCH",
                error_message="Active owner mismatch.",
            ),
        ):
            with mock.patch.dict("sys.modules", {"streamlit": _St()}):
                apply_atomic_mission_chord_selection(
                    {},
                    chord="G",
                    section="Verse 1",
                    chord_index=1,
                    chord_label="Verse 1 · G",
                )

        self.assertEqual(warnings, [], msg=f"owner mismatch leaked: {warnings}")


if __name__ == "__main__":
    unittest.main()

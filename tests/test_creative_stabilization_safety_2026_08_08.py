"""Creative stabilization — generated key spelling, Style Jam provenance, mission notation."""

from __future__ import annotations

import copy
import unittest
import uuid
from unittest.mock import MagicMock

from backing_musical_state import resolve_current_backing_musical_state
from creative_key_sync import prepare_backing_context_sidebar_display_key
from generated_workflow_artifact import build_snapshot_from_session
from generated_workflow_projection import (
    project_generated_owner_from_active_blob,
    style_jam_control_blob_drift,
    sync_style_jam_legacy_from_active_blob,
)
from music_workflow_mutation import update_active_practice_key
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from musical_context_authority import format_practice_concert_key_line
from workflow_key_identity import normalize_user_practice_key_selection, resolve_practice_key_identity_for_ui


def _jam_session(session: dict, *, tonic: str, mode: str, sid: str | None = None) -> str:
    sid = sid or str(uuid.uuid4())
    blob = WorkflowStateBlob(
        workflow_owner="jam_session_generator",
        workflow_session_id=sid,
        keys=KeyAuthority(
            practice_tonic=tonic,
            practice_mode=mode,
            original_tonic=tonic,
            original_mode=mode,
        ),
        section_map={"A": ["Dmaj7", "G7", "Em7", "A7"]},
        style="Bossa Nova",
    )
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="jam_session_generator", workflow_session_id=sid),
        source="test",
    )
    return sid


class CreativeStabilizationSafetyTests(unittest.TestCase):
    def test_normalize_preserves_explicit_enharmonic_tokens(self) -> None:
        cases = [
            ("C# major", "C#", "major", "C#"),
            ("Db major", "Db", "major", "Db"),
            ("Eb major", "Eb", "major", "Eb"),
            ("F# minor", "F#", "minor", "F#m"),
            ("Bb minor", "Bb", "minor", "Bbm"),
        ]
        for raw, tonic, mode, token in cases:
            pt, pm, tok = normalize_user_practice_key_selection(raw, default_mode="major")
            self.assertEqual(pt, tonic, raw)
            self.assertEqual(pm, mode, raw)
            self.assertEqual(tok, token, raw)

    def test_jam_d_major_backing_header_not_d_minor(self) -> None:
        session: dict = {
            "studio_page": "backing",
            "improv_entry_mode": "Jam Session Generator",
            "active_catalog_pick_key": "Jewish|Hevenu",
            "display_key": "Dm",
            "concert_key": "Dm",
            "practice_key_mode": "fixed",
            "fixed_practice_key": "D",
        }
        _jam_session(session, tonic="D", mode="major")
        st = MagicMock()
        prepare_backing_context_sidebar_display_key(st, session)
        ident = resolve_practice_key_identity_for_ui(session)
        self.assertIsNotNone(ident)
        assert ident is not None
        self.assertEqual(ident.practice_mode, "major")
        line = format_practice_concert_key_line(session)
        self.assertIn("major", line.lower())
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "D")

    def test_style_jam_hybrid_controls_repaired_from_blob(self) -> None:
        sid = str(uuid.uuid4())
        session: dict = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_mood": "Bright",
            "improv_style_key": "C",
            "improv_generated_sections": {
                "Head (Jazz Swing)": ["Am7", "D7", "Gmaj7", "E7"],
            },
        }
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id=sid,
            keys=KeyAuthority(practice_tonic="C", practice_mode="major"),
            section_map={"Head (Bossa Nova)": ["Cmaj7", "Dm7", "Em7", "A7"]},
            style="Bossa Nova",
            mood="Bright",
            tempo_bpm=72,
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
            source="test",
        )
        drift = style_jam_control_blob_drift(session)
        self.assertTrue(drift.get("drift"))
        self.assertTrue(sync_style_jam_legacy_from_active_blob(session, writer="test"))
        self.assertEqual(str(session.get("improv_style") or ""), "Bossa Nova")
        self.assertIn("Bossa Nova", next(iter(session["improv_generated_sections"].keys())))
        snap = build_snapshot_from_session(session, owner="style_jam", entry_mode="Style Jam Mode")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.style, "Bossa Nova")
        self.assertIn("Bossa Nova", next(iter(snap.section_map.keys())))

    def test_generated_key_mutation_keeps_c_sharp_major_spelling(self) -> None:
        sid = str(uuid.uuid4())
        session: dict = {"improv_entry_mode": "Style Jam Mode"}
        blob = WorkflowStateBlob(
            workflow_owner="style_jam",
            workflow_session_id=sid,
            keys=KeyAuthority(practice_tonic="Eb", practice_mode="major"),
            section_map={"Head (Pop)": ["Ebmaj7", "Abmaj7", "Bb7", "Ebmaj7"]},
            style="Pop",
        )
        save_workflow_blob(session, blob, source="test")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
            source="test",
        )
        result = update_active_practice_key(session, "C# major", source="on_improv_style_key_change")
        self.assertTrue(result.ok, result.error_code)
        ident = resolve_practice_key_identity_for_ui(session)
        self.assertIsNotNone(ident)
        assert ident is not None
        self.assertEqual(ident.practice_tonic, "C#")
        self.assertEqual(ident.practice_mode, "major")
        project_generated_owner_from_active_blob(session, writer="test")
        self.assertEqual(str(session.get("improv_style_key") or ""), "C#")


if __name__ == "__main__":
    unittest.main()

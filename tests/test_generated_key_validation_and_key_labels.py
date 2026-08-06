"""Generated-key validation + structured key label regressions."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from music_theory import format_key_label_from_parts, key_center_token, split_key_center
from music_workflow_pending_generated_key_edit import (
    PENDING_GENERATED_KEY_EDIT_KEY,
    PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY,
    consume_pending_generated_key_edit,
    queue_pending_generated_key_edit,
)
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
    ActiveWorkflowPointer,
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
    }
    save_workflow_blob(session, blob, source="test")
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id=sid),
        source="test",
    )
    return session


class TestGeneratedKeyValidation(unittest.TestCase):
    def test_c_to_d_passes_when_legacy_session_id_drifts(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        pending = queue_pending_generated_key_edit(session, widget_key="improv_style_key", selected_key_token="D")
        assert pending is not None
        session["improv_style"] = ""
        phase = consume_pending_generated_key_edit(session)
        self.assertEqual(phase, "applied")
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        self.assertEqual(blob.keys.practice_tonic, "D")

    def test_fingerprint_change_on_widget_only_does_not_invalidate(self) -> None:
        session = _style_session(tonic="C")
        session["improv_style_key"] = "D"
        pending = queue_pending_generated_key_edit(session, widget_key="improv_style_key", selected_key_token="D")
        assert pending is not None
        blob = get_workflow_blob(session, "style_jam", "Pop groove")
        assert blob is not None
        blob.material_fingerprint = "changed_after_widget_only"
        save_workflow_blob(session, blob, source="test")
        self.assertEqual(consume_pending_generated_key_edit(session), "applied")

    def test_missing_blob_session_reports_session_id_mismatch(self) -> None:
        session = _style_session(tonic="C")
        session[PENDING_GENERATED_KEY_EDIT_KEY] = {
            "request_seq": 1,
            "request_token": "abc",
            "workflow_owner": "style_jam",
            "workflow_session_id": "missing-style",
            "widget_key": "improv_style_key",
            "selected_key_token": "D",
            "practice_tonic": "D",
            "practice_mode": "major",
            "callback_source": "on_improv_style_key_change",
        }
        phase = consume_pending_generated_key_edit(session)
        self.assertEqual(phase, "invalid")
        diag = session.get(PENDING_GENERATED_KEY_EDIT_LAST_DIAG_KEY)
        assert isinstance(diag, dict)
        self.assertEqual(diag.get("failed_predicate"), "session_id_mismatch")


class TestStructuredKeyLabels(unittest.TestCase):
    def test_d_minor_token_and_label(self) -> None:
        self.assertEqual(split_key_center("Dm"), ("D", "minor"))
        self.assertEqual(key_center_token("D", "minor"), "Dm")
        self.assertEqual(format_key_label_from_parts("D", "minor"), "D minor")

    def test_dm_never_normalizes_to_d_sharp(self) -> None:
        from music_theory import normalize_root

        tonic, mode = split_key_center("Dm")
        self.assertEqual(mode, "minor")
        self.assertEqual(normalize_root(tonic), "D")
        self.assertNotEqual(key_center_token(tonic, mode), "D#")
        self.assertNotIn("#", format_key_label_from_parts("D", "minor"))

    def test_d_sharp_minor_parses_correctly(self) -> None:
        self.assertEqual(split_key_center("D#m"), ("D#", "minor"))


class TestCatalogSidebarAuthority(unittest.TestCase):
    def test_hevenu_catalog_owns_sidebar_over_generated_jam(self) -> None:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY, generated_jam_owns_practice_key
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key, resolve_authoritative_practice_key

        session: dict[str, Any] = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "active_catalog_pick_key": "Jewish|Hevenu Shalom Aleichem",
            "display_key": "Dm",
            "concert_key": "Dm",
            GENERATED_JAM_KEY_CONTEXT_KEY: {"key_owner": "entry_jam", "entry_mode": "Style Jam Mode"},
        }
        self.assertTrue(catalog_song_should_own_sidebar_practice_key(session))
        self.assertFalse(generated_jam_owns_practice_key(session))
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "minor")
        self.assertEqual(pk.practice_tonic, "D")

    def test_resolve_sidebar_identity_hevenu_dm(self) -> None:
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
        self.assertEqual(ident.practice_mode, "minor")
        self.assertEqual(ident.practice_tonic, "D")
        self.assertIn(ident.label, {"Dm", "D minor"})
        self.assertNotIn("#", ident.label)


if __name__ == "__main__":
    unittest.main()

"""CPL draft persistence — no display_key mutation; pending chord survives export."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import (
    CPL_PENDING_CHORD_KEY,
    CPL_PENDING_SECTION_KEY,
    cpl_clear_pending_chord,
    cpl_get_pending_chord,
    cpl_set_pending_chord,
    export_cpl_widget_state,
    persist_cpl_draft_state,
)
from music_persistent_state import flush_active_song_edits_and_save


class TestCplDraftPersist(unittest.TestCase):
    def test_cpl_draft_edit_skips_flush_active_song_edits(self) -> None:
        st = SimpleNamespace(session_state={})
        with patch("active_song_state.flush_active_song_edits") as flush, patch(
            "music_persistent_state.force_autosave",
            return_value=True,
        ) as autosave:
            ok = flush_active_song_edits_and_save(st, reason="cpl_draft_edit")
        flush.assert_not_called()
        autosave.assert_called_once()
        self.assertTrue(ok)

    def test_persist_cpl_draft_state_uses_cpl_draft_edit_reason(self) -> None:
        st = SimpleNamespace(session_state={})
        with patch(
            "music_persistent_state.flush_active_song_edits_and_save",
            return_value=True,
        ) as flush:
            ok = persist_cpl_draft_state(st)
        flush.assert_called_once_with(st, reason="cpl_draft_edit")
        self.assertTrue(ok)

    def test_pending_chord_canonical_keys_survive_export(self) -> None:
        session = {"cpl_edit_section": "Chorus"}
        cpl_set_pending_chord(session, section="Chorus", chord="C")
        self.assertEqual(cpl_get_pending_chord(session, "Chorus"), "C")
        blob = export_cpl_widget_state(session)
        self.assertEqual(blob[CPL_PENDING_CHORD_KEY], "C")
        self.assertEqual(blob[CPL_PENDING_SECTION_KEY], "Chorus")
        self.assertEqual(blob["cpl_pending_chord_Chorus"], "C")

    def test_export_uses_canonical_bpm_and_style_keys_only(self) -> None:
        session = {
            "cpl_bpm_builder": 170,
            "cpl_bpm": 85,
            "cpl_style_early": "Soul/R&B",
            "cpl_progression_style": "Pop",
        }
        blob = export_cpl_widget_state(session)
        self.assertEqual(blob.get("cpl_bpm_builder"), 170)
        self.assertEqual(blob.get("cpl_style_early"), "Soul/R&B")
        self.assertNotIn("cpl_bpm", blob)
        self.assertNotIn("cpl_progression_style", blob)

    def test_set_pending_records_last_chord_click(self) -> None:
        session = {}
        cpl_set_pending_chord(session, section="Chorus", chord="C")
        click = session.get("_cpl_last_chord_click") or {}
        self.assertEqual(click.get("section"), "Chorus")
        self.assertEqual(click.get("chord"), "C")
        self.assertEqual(click.get("pending_key_written"), "cpl_pending_chord_Chorus")
        self.assertIn("timestamp", click)

    def test_clear_pending_removes_all_pending_keys(self) -> None:
        session = {}
        cpl_set_pending_chord(session, section="Chorus", chord="Am")
        cpl_clear_pending_chord(session, "Chorus")
        self.assertIsNone(cpl_get_pending_chord(session, "Chorus"))
        self.assertNotIn(CPL_PENDING_CHORD_KEY, session)


if __name__ == "__main__":
    unittest.main()

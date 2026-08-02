"""Phase 1 runtime write journal."""

from __future__ import annotations

import unittest

from music_phase1_write_journal import (
    begin_phase1_write_journal_run,
    finalize_phase1_write_journal,
    format_journal_copy_block,
    phase1_journal_enabled,
    record_phase1_global_write,
    record_phase1_page_write,
)


class TestPhase1WriteJournal(unittest.TestCase):
    def setUp(self) -> None:
        self.session: dict = {
            "developer_mode": True,
            "_script_run_seq": 1,
            "instrument": "Saxophone",
            "level": "Advanced",
            "focus": "Tone",
            "studio_page": "analysis",
        }

    def test_global_overwrite_detected(self) -> None:
        begin_phase1_write_journal_run(self.session)
        self.session["instrument"] = "Piano"
        self.session["_phase1_write_journal"]["user_selection_at_run_start"] = {"instrument": "Piano"}
        self.session["_phase1_write_journal"]["user_widget_events"] = {"instrument": "Piano"}
        record_phase1_global_write(
            self.session,
            key="instrument",
            old_value="Piano",
            new_value="Saxophone",
            module="active_song_state",
            function="prepare_active_song_context",
            reason="canonical_preserve",
            origin="canonical",
        )
        self.session["instrument"] = "Saxophone"
        from music_restore_phase import mark_global_controls_restore_projection_complete

        mark_global_controls_restore_projection_complete(self.session)
        summary = finalize_phase1_write_journal(self.session)
        violations = self.session["_phase1_write_journal"].get("violations") or []
        self.assertTrue(any(v.get("code") == "PHASE1_GLOBAL_OVERWRITE" for v in violations))
        self.assertEqual(summary["final_globals"]["instrument"], "Saxophone")

    def test_page_journal_and_copy_block(self) -> None:
        begin_phase1_write_journal_run(self.session)
        record_phase1_page_write(
            self.session,
            key="studio_page",
            old_page="analysis",
            new_page="creative",
            module="studio_nav_history",
            function="navigate_studio_page",
            reason="user_navigation",
            origin="user_navigation",
        )
        self.session["studio_page"] = "creative"
        text = format_journal_copy_block(self.session)
        self.assertIn("creative", text)
        self.assertTrue(phase1_journal_enabled(self.session))


if __name__ == "__main__":
    unittest.main()

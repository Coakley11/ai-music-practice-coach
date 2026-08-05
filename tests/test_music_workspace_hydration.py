"""Tests for workspace hydration gating vs restore finalization."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_restore_phase import (
    MUSIC_RESTORE_PHASE_COMPLETE_KEY,
    MUSIC_STARTUP_RESTORE_FINALIZED_KEY,
    begin_music_script_run,
    complete_music_restore_phase,
)
from music_workspace_hydration import (
    can_finalize_music_restore,
    clear_stale_restore_completion_flags,
    mark_workspace_blob_hydrated,
    mark_workspace_empty_confirmed,
    record_sync_outcome_after_attempt,
)


class TestMusicWorkspaceHydration(unittest.TestCase):
    def test_cannot_finalize_until_hydrated_or_empty(self) -> None:
        ss: dict = {}
        self.assertFalse(can_finalize_music_restore(ss))
        mark_workspace_blob_hydrated(ss)
        self.assertTrue(can_finalize_music_restore(ss))

    def test_empty_confirmed_allows_finalize(self) -> None:
        ss: dict = {}
        mark_workspace_empty_confirmed(ss, "no workspace blob")
        self.assertTrue(can_finalize_music_restore(ss))

    def test_complete_restore_phase_blocked_without_hydration(self) -> None:
        ss: dict = {}
        complete_music_restore_phase(ss)
        self.assertNotIn(MUSIC_RESTORE_PHASE_COMPLETE_KEY, ss)
        mark_workspace_blob_hydrated(ss)
        complete_music_restore_phase(ss)
        self.assertTrue(ss.get(MUSIC_RESTORE_PHASE_COMPLETE_KEY))

    def test_begin_script_run_clears_stale_completion_flags(self) -> None:
        ss = {
            MUSIC_STARTUP_RESTORE_FINALIZED_KEY: True,
            MUSIC_RESTORE_PHASE_COMPLETE_KEY: True,
            "_script_run_seq": 1,
        }
        begin_music_script_run(ss)
        self.assertNotIn(MUSIC_STARTUP_RESTORE_FINALIZED_KEY, ss)
        self.assertNotIn(MUSIC_RESTORE_PHASE_COMPLETE_KEY, ss)

    def test_stale_flags_kept_when_hydrated(self) -> None:
        ss = {
            MUSIC_STARTUP_RESTORE_FINALIZED_KEY: True,
            MUSIC_RESTORE_PHASE_COMPLETE_KEY: True,
        }
        mark_workspace_blob_hydrated(ss)
        clear_stale_restore_completion_flags(ss)
        self.assertTrue(ss.get(MUSIC_STARTUP_RESTORE_FINALIZED_KEY))

    def test_sync_no_blob_marks_empty_confirmed(self) -> None:
        ss: dict = {"_suite_persist_restore_skip_reason": "no workspace blob"}
        record_sync_outcome_after_attempt(ss, sync_applied=False)
        self.assertTrue(can_finalize_music_restore(ss))

    def test_hydration_wait_treats_persist_applied_as_hydrated(self) -> None:
        from music_workspace_hydration import render_workspace_hydration_wait_or_stop

        ss: dict = {"_suite_persist_restore_applied": True}
        st = MagicMock()
        st.session_state = ss
        st.rerun = MagicMock()
        out = render_workspace_hydration_wait_or_stop(st, song_picker_catalog={}, song_library={})
        self.assertFalse(out)
        self.assertTrue(can_finalize_music_restore(ss))
        st.rerun.assert_not_called()

    def test_finalize_skipped_until_hydration(self) -> None:
        from music_persistent_state import finalize_music_startup_restore

        ss = {
            "_suite_last_cloud_fetch_payload": {"core": {"pick_key": "Pop::X"}},
            "studio_page": "practice",
        }
        st = type("St", (), {"session_state": ss})()

        class _Cat(dict):
            pass

        finalize_music_startup_restore(st, song_picker_catalog=_Cat(), song_library=_Cat())
        self.assertNotIn(MUSIC_STARTUP_RESTORE_FINALIZED_KEY, ss)
        mark_workspace_blob_hydrated(ss)
        finalize_music_startup_restore(st, song_picker_catalog=_Cat(), song_library=_Cat())
        self.assertTrue(ss.get(MUSIC_STARTUP_RESTORE_FINALIZED_KEY))


if __name__ == "__main__":
    unittest.main()

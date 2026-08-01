"""Tests for music_restore_phase gate."""

from __future__ import annotations

import unittest

from music_restore_phase import (
    begin_music_script_run,
    complete_music_restore_phase,
    mark_page_snapshot_hydrated,
    page_snapshot_hydrated,
    should_hydrate_page_snapshot,
    workspace_is_truly_empty,
)
from music_workspace_hydration import mark_workspace_blob_hydrated, mark_workspace_empty_confirmed


class TestMusicRestorePhase(unittest.TestCase):
    def test_begin_script_run_resets_tracker_only_on_new_session(self) -> None:
        ss = {"_script_run_seq": 2, "_studio_active_page_id": "picker"}
        begin_music_script_run(ss)
        self.assertIsNone(ss.get("_studio_active_page_id"))
        ss["_studio_active_page_id"] = "backing"
        begin_music_script_run(ss)
        self.assertEqual(ss.get("_studio_active_page_id"), "backing")

    def test_page_snapshot_hydrates_once_after_restore_complete(self) -> None:
        ss: dict = {}
        mark_workspace_blob_hydrated(ss)
        complete_music_restore_phase(ss)
        self.assertTrue(should_hydrate_page_snapshot(ss, page_id="picker", page_changed=False))
        mark_page_snapshot_hydrated(ss, "picker")
        self.assertFalse(should_hydrate_page_snapshot(ss, page_id="picker", page_changed=False))

    def test_page_change_always_hydrates(self) -> None:
        ss: dict = {}
        mark_workspace_blob_hydrated(ss)
        complete_music_restore_phase(ss)
        mark_page_snapshot_hydrated(ss, "picker")
        self.assertTrue(should_hydrate_page_snapshot(ss, page_id="backing", page_changed=True))

    def test_workspace_not_empty_when_cloud_restored(self) -> None:
        ss = {"_suite_persist_restore_applied": True}
        self.assertFalse(workspace_is_truly_empty(ss))

    def test_workspace_empty_when_confirmed(self) -> None:
        ss: dict = {}
        mark_workspace_empty_confirmed(ss, "no workspace blob")
        self.assertTrue(workspace_is_truly_empty(ss))


if __name__ == "__main__":
    unittest.main()

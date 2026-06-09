"""Tests for canonical Practice page state (Phase C acceptance A–E)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state, build_music_disk_state
from practice_state import (
    PRACTICE_DIRTY_KEY,
    apply_cloud_practice_state_if_allowed,
    apply_practice_source_state_from_ami,
    flush_practice_edits,
    is_practice_locally_dirty,
    mark_practice_local_edit,
    prepare_practice_page,
    write_canonical_practice_state,
)

_SAMPLE = {
    "practice_focus_section": "Chorus",
    "practice_groove_style": "Pop groove",
    "practice_notation_lines": 3,
    "practice_notation_difficulty": "medium",
    "last_practice_mode": "section",
}


class TestPracticeState(unittest.TestCase):
    def test_a_local_persist_prepare_preserves_edits(self) -> None:
        session: dict = {}
        write_canonical_practice_state(session, _SAMPLE, reason="setup")
        session["practice_groove_style"] = "Jazz swing"
        mark_practice_local_edit(session)
        flush_practice_edits(session, reason="practice_edit")
        prepare_practice_page(session)
        self.assertEqual(session["practice_groove_style"], "Jazz swing")
        self.assertEqual(session["practice_state"]["practice_groove_style"], "Jazz swing")
        self.assertTrue(is_practice_locally_dirty(session))

    def test_a_prepare_seeds_from_canonical(self) -> None:
        session = {"practice_state": {**_SAMPLE, "last_write_reason": "cloud"}}
        prepare_practice_page(session)
        self.assertEqual(session["practice_groove_style"], "Pop groove")
        self.assertEqual(session["practice_notation_lines"], 3)

    def test_b_cross_device_cloud_restore(self) -> None:
        session: dict = {"practice_groove_style": "Auto"}
        cloud = {
            "practice_state": dict(_SAMPLE),
            "music_workspace_state": {"practice_filters": dict(_SAMPLE)},
        }
        self.assertTrue(apply_cloud_practice_state_if_allowed(session, cloud))
        self.assertEqual(session["practice_groove_style"], "Pop groove")
        self.assertFalse(is_practice_locally_dirty(session))

    def test_b_disk_blob_round_trip(self) -> None:
        st = MagicMock()
        st.session_state = dict(_SAMPLE)
        write_canonical_practice_state(st.session_state, _SAMPLE, reason="setup")
        blob = build_music_disk_state(st)
        self.assertIn("practice_state", blob)
        meta = blob.get("music_workspace_state") or {}
        self.assertEqual(meta.get("practice_filters", {}).get("practice_groove_style"), "Pop groove")

        st2 = MagicMock()
        st2.session_state = {}
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        self.assertEqual(st2.session_state.get("practice_groove_style"), "Pop groove")
        self.assertEqual(st2.session_state.get("practice_state", {}).get("practice_focus_section"), "Chorus")

    def test_c_stale_cloud_blocked_when_locally_dirty(self) -> None:
        session = {**_SAMPLE, "practice_groove_style": "Rock groove"}
        mark_practice_local_edit(session)
        cloud = {"practice_state": dict(_SAMPLE)}
        self.assertFalse(apply_cloud_practice_state_if_allowed(session, cloud))
        self.assertEqual(session["practice_groove_style"], "Rock groove")

    def test_d_navigation_does_not_clear_practice_filters(self) -> None:
        session = dict(_SAMPLE)
        write_canonical_practice_state(session, _SAMPLE, reason="setup")
        session["studio_page"] = "backing"
        prepare_practice_page(session)
        self.assertEqual(session["practice_groove_style"], "Pop groove")

    def test_e_ami_return_restores_practice_filters(self) -> None:
        session: dict = {}
        source = {
            "source_page": "practice",
            "widget_params": {
                "practice_focus_section": "Verse",
                "practice_groove_style": "Ballad",
                "practice_notation_lines": 4,
                "practice_notation_difficulty": "easy",
            },
        }
        apply_practice_source_state_from_ami(session, source)
        self.assertEqual(session["practice_focus_section"], "Verse")
        self.assertEqual(session["practice_groove_style"], "Ballad")
        self.assertEqual(session["practice_notation_lines"], 4)
        self.assertFalse(session.get(PRACTICE_DIRTY_KEY))

    def test_practice_edit_bypasses_post_restore_block(self) -> None:
        from suite_user_persistence import _cloud_autosave_blocked_reason

        st = MagicMock()
        st.session_state = {}
        state = {"practice_state": dict(_SAMPLE)}
        self.assertIsNone(
            _cloud_autosave_blocked_reason(st, "music", state, save_reason="practice_edit")
        )


if __name__ == "__main__":
    unittest.main()

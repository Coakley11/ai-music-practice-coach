"""Tests for canonical studio nav state (Phase C acceptance A–E)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state, build_music_disk_state
from studio_nav_state import (
    STUDIO_NAV_DIRTY_KEY,
    apply_cloud_studio_nav_state_if_allowed,
    apply_studio_nav_source_state_from_ami,
    clear_studio_nav_local_edit,
    is_studio_nav_locally_dirty,
    mark_studio_nav_local_edit,
    prepare_studio_nav,
    resolve_studio_page_for_restore,
    write_canonical_studio_nav_state,
)


class TestStudioNavState(unittest.TestCase):
    def test_a_local_persist_prepare_preserves_page(self) -> None:
        session: dict = {"studio_page": "practice"}
        write_canonical_studio_nav_state(session, "practice", reason="setup")
        session["studio_page"] = "backing"
        mark_studio_nav_local_edit(session)
        prepare_studio_nav(session)
        self.assertEqual(session["studio_page"], "backing")
        self.assertEqual(session["studio_nav_state"]["studio_page"], "backing")
        self.assertTrue(is_studio_nav_locally_dirty(session))

    def test_a_prepare_seeds_from_canonical(self) -> None:
        session = {"studio_nav_state": {"studio_page": "backing", "last_write_reason": "cloud"}}
        prepare_studio_nav(session)
        self.assertEqual(session["studio_page"], "backing")

    def test_prepare_session_page_wins_over_stale_canonical(self) -> None:
        """Songs→Backing: live studio_page must not revert to canonical picker."""
        session = {
            "studio_page": "backing",
            "studio_nav_state": {"studio_page": "picker", "last_write_reason": "page_change"},
        }
        prepare_studio_nav(session)
        self.assertEqual(session["studio_page"], "backing")
        self.assertEqual(session["studio_nav_state"]["studio_page"], "backing")
        self.assertEqual(session["studio_nav_state"]["last_write_reason"], "session_page_wins")
        self.assertTrue(is_studio_nav_locally_dirty(session))

    def test_b_cross_device_cloud_restore(self) -> None:
        session: dict = {"studio_page": "practice"}
        cloud = {
            "studio_nav_state": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing"},
            "core": {"studio_page": "backing"},
        }
        self.assertTrue(apply_cloud_studio_nav_state_if_allowed(session, cloud))
        self.assertEqual(session["studio_page"], "backing")
        self.assertFalse(is_studio_nav_locally_dirty(session))

    def test_b_disk_blob_round_trip(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "custom"}
        write_canonical_studio_nav_state(st.session_state, "custom", reason="setup")
        blob = build_music_disk_state(st)
        self.assertIn("studio_nav_state", blob)
        self.assertEqual(blob["studio_nav_state"]["studio_page"], "custom")

        st2 = MagicMock()
        st2.session_state = {}
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        self.assertEqual(st2.session_state.get("studio_page"), "custom")

    def test_c_stale_cloud_blocked_when_locally_dirty(self) -> None:
        session = {"studio_page": "multitrack"}
        mark_studio_nav_local_edit(session)
        cloud = {"studio_nav_state": {"studio_page": "practice"}}
        self.assertFalse(apply_cloud_studio_nav_state_if_allowed(session, cloud))
        self.assertEqual(session["studio_page"], "multitrack")

    def test_d_user_nav_preserved_on_restore(self) -> None:
        page, source = resolve_studio_page_for_restore(
            {},
            {"studio_nav_state": {"studio_page": "practice"}, "core": {"studio_page": "practice"}},
            pre_restore_page="backing",
            user_owns_page=True,
        )
        self.assertEqual(page, "backing")
        self.assertEqual(source, "user_page_preserved")

    def test_e_ami_return_restores_studio_page(self) -> None:
        session: dict = {}
        source = {
            "source_page": "backing",
            "widget_params": {"studio_page": "backing", "instrument": "Guitar"},
        }
        page = apply_studio_nav_source_state_from_ami(session, source)
        self.assertEqual(page, "backing")
        self.assertEqual(session["studio_page"], "backing")
        self.assertFalse(session.get(STUDIO_NAV_DIRTY_KEY))

    def test_claim_marks_dirty_via_write(self) -> None:
        session: dict = {}
        write_canonical_studio_nav_state(session, "picker", reason="user_nav", local_edit=True)
        self.assertTrue(is_studio_nav_locally_dirty(session))
        clear_studio_nav_local_edit(session)
        self.assertFalse(is_studio_nav_locally_dirty(session))


if __name__ == "__main__":
    unittest.main()

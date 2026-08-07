"""Creative page_change payload must not use stale workspace backing page."""

from __future__ import annotations

import unittest

from music_persistent_state import (
    MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY,
    MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY,
    _page_change_write_target,
    build_music_disk_state,
    finalize_music_page_change_cloud_payload,
    mark_user_navigated_page_this_run,
    synchronize_page_bearing_state_for_save,
)
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


class TestCreativePageSavePayload(unittest.TestCase):
    def test_page_change_target_prefers_user_nav_over_stale_pending(self) -> None:
        ss: dict = {
            "studio_page": "creative",
            "_script_run_seq": 5,
            "_suite_page_user_nav": True,
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
            STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            "_suite_page_change_write_pending": "backing",
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "creative",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 5,
        }
        page, source = _page_change_write_target(ss)
        self.assertEqual(page, "creative")
        self.assertEqual(source, MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY)

    def test_prepare_studio_nav_keeps_user_nav_this_run(self) -> None:
        ss: dict = {
            "studio_page": "creative",
            "_script_run_seq": 5,
            STUDIO_NAV_STATE_KEY: {"studio_page": "backing", "page": "backing"},
            "_music_hydrated_studio_page": "backing",
            "_suite_page_overwrite_source": "workspace_blob",
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "creative",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 5,
            "_music_studio_page_restore_projection_complete": True,
        }
        page = prepare_studio_nav(ss)
        self.assertEqual(page, "creative")
        self.assertEqual(ss.get("studio_page"), "creative")

    def test_finalize_stamps_creative_into_payload(self) -> None:
        ss = _FakeSessionState(
            {
                "studio_page": "creative",
                "_script_run_seq": 5,
                "_suite_page_user_nav": True,
                MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "creative",
                MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 5,
                "music_workspace_state": {"studio_page": "backing", "page": "backing"},
                STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            }
        )
        st = _FakeSt(ss)
        mark_user_navigated_page_this_run(ss, "creative")
        synchronize_page_bearing_state_for_save(ss, "creative")
        state: dict = {
            "core": {"studio_page": "backing", "page": "backing"},
            "session": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
            "studio_nav_state": {"studio_page": "backing", "page": "backing"},
        }
        state, trace = finalize_music_page_change_cloud_payload(st, state, save_reason="page_change")
        self.assertEqual(trace.get("save_payload_core_page"), "creative")
        self.assertEqual(trace.get("save_payload_session_page"), "creative")
        self.assertEqual(trace.get("save_payload_workspace_page"), "creative")
        self.assertEqual(trace.get("save_payload_studio_nav_page"), "creative")


if __name__ == "__main__":
    unittest.main()

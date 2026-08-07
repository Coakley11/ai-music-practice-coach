"""Regression: _music_user_navigated_page_this_run must not leak across script runs."""

from __future__ import annotations

import unittest

from backing_source_navigation import CREATIVE_RESTORE_FROM_BACKING_KEY
from music_persistent_state import (
    MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY,
    MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY,
    begin_script_run_navigation_markers,
    current_run_user_navigated_page,
    mark_user_navigated_page_this_run,
)
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav


def _entry_jam_backing_session(*, run_seq: int) -> dict:
    return {
        "_script_run_seq": run_seq,
        "studio_page": "creative",
        STUDIO_NAV_STATE_KEY: {"studio_page": "backing", "page": "backing"},
        "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        "backing_context": {
            "source": "entry_jam",
            "entry_mode": "Jam Session Generator",
            "creative_return_route": {
                "intelligence_tab": "Entry & Jam",
                "entry_mode": "Jam Session Generator",
                "workflow_owner": "jam_session_generator",
                "backing_source": "entry_jam",
            },
        },
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Jam Session Generator",
        CREATIVE_RESTORE_FROM_BACKING_KEY: True,
    }


class UserNavigatedPageRunScopeTests(unittest.TestCase):
    def test_begin_script_run_clears_stale_marker(self) -> None:
        session: dict = {
            "_script_run_seq": 10,
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "backing",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 9,
        }
        begin_script_run_navigation_markers(session)
        self.assertIsNone(session.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY))
        self.assertIsNone(session.get(MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY))

    def test_scoped_reader_ignores_previous_run_stamp(self) -> None:
        session: dict = {
            "_script_run_seq": 10,
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "backing",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 9,
        }
        self.assertEqual(current_run_user_navigated_page(session), "")

    def test_prepare_studio_nav_after_return_not_overwritten_by_stale_backing(self) -> None:
        session = _entry_jam_backing_session(run_seq=10)
        session[MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY] = "backing"
        session[MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY] = 9
        begin_script_run_navigation_markers(session)
        mark_user_navigated_page_this_run(session, "creative")
        page = prepare_studio_nav(session)
        self.assertEqual(page, "creative")
        self.assertEqual(session.get("studio_page"), "creative")

    def test_stale_backing_marker_ignored_when_run_seq_mismatches(self) -> None:
        session = _entry_jam_backing_session(run_seq=10)
        session[MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY] = "backing"
        session[MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY] = 9
        self.assertEqual(current_run_user_navigated_page(session), "")
        mark_user_navigated_page_this_run(session, "creative")
        page = prepare_studio_nav(session)
        self.assertEqual(page, "creative")

    def test_return_consume_stamps_creative_for_current_run_when_navigate_noops(self) -> None:
        session = _entry_jam_backing_session(run_seq=9)
        session["studio_page"] = "creative"
        session[MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY] = "backing"
        session[MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY] = 8
        mark_user_navigated_page_this_run(session, "creative")
        self.assertEqual(current_run_user_navigated_page(session), "creative")

    def test_consecutive_creative_backing_return_cycles_without_refresh(self) -> None:
        for cycle, run_seq in enumerate((11, 12, 13, 14), start=1):
            session = _entry_jam_backing_session(run_seq=run_seq)
            begin_script_run_navigation_markers(session)
            mark_user_navigated_page_this_run(session, "backing")
            self.assertEqual(current_run_user_navigated_page(session), "backing")
            session["studio_page"] = "creative"
            mark_user_navigated_page_this_run(session, "creative")
            self.assertEqual(current_run_user_navigated_page(session), "creative")
            page = prepare_studio_nav(session)
            self.assertEqual(page, "creative", msg=f"cycle={cycle} run_seq={run_seq}")
            next_run = run_seq + 1
            session["_script_run_seq"] = next_run
            begin_script_run_navigation_markers(session)
            session[MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY] = "backing"
            session[MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY] = run_seq
            session["studio_page"] = "creative"
            page_after = prepare_studio_nav(session)
            self.assertEqual(
                page_after,
                "creative",
                msg=f"stale backing from run {run_seq} must not win on run {next_run}",
            )


if __name__ == "__main__":
    unittest.main()

"""Regression: a stale startup snapshot must not revert a Practice edit made since.

Live failure (traced in the browser): choose Notation Difficulty "advanced" -> the edit is
flushed into the canonical Practice state -> the end-of-run ``run_late_startup_restore_guard``
re-runs ``align_authoritative_canonical_from_hydrated``, which re-applied the *startup*
snapshot ("medium") over it -> the next rerun (e.g. clicking Generate) restored "medium"
into the selector, so the TAB was generated at the old difficulty.
"""

from __future__ import annotations

import unittest

from music_startup_canonical_align import align_authoritative_canonical_from_hydrated
from music_startup_save_suppression import arm_startup_suppression
from practice_state import (
    PRACTICE_USER_EDITED_SINCE_HYDRATE_KEY,
    canonical_practice_filters,
    flush_practice_edits,
    mark_practice_pending_sync,
    mark_practice_user_edit,
    prepare_practice_page,
)

SNAPSHOT = {
    "practice_state": {
        "practice_notation_difficulty": "medium",
        "practice_minutes": 30,
        "practice_focus_section": "Full Song",
    },
}


def _hydrated_session() -> dict:
    """A session right after startup: the snapshot has been applied once."""
    session: dict = {}
    arm_startup_suppression(session, "test")
    align_authoritative_canonical_from_hydrated(session, SNAPSHOT)
    return session


def _user_picks(session: dict, difficulty: str) -> None:
    """What the Difficulty selectbox's on_change callback does."""
    session["practice_notation_difficulty"] = difficulty
    mark_practice_pending_sync(session)
    mark_practice_user_edit(session)
    flush_practice_edits(session, reason="practice_edit")


class TestStartupSnapshotDoesNotRevertUserEdits(unittest.TestCase):
    def test_startup_snapshot_is_applied_when_the_user_has_not_edited(self) -> None:
        session = _hydrated_session()
        self.assertEqual(session["practice_notation_difficulty"], "medium")
        self.assertEqual(canonical_practice_filters(session)["practice_notation_difficulty"], "medium")

    def test_late_realignment_keeps_the_users_difficulty(self) -> None:
        for difficulty in ("easy", "medium", "advanced"):
            with self.subTest(difficulty=difficulty):
                session = _hydrated_session()
                _user_picks(session, "advanced" if difficulty == "medium" else difficulty)
                chosen = session["practice_notation_difficulty"]
                align_authoritative_canonical_from_hydrated(session, SNAPSHOT)  # run_late_startup_restore_guard
                self.assertEqual(canonical_practice_filters(session)["practice_notation_difficulty"], chosen)
                prepare_practice_page(session)  # the next rerun (e.g. clicking Generate)
                self.assertEqual(session["practice_notation_difficulty"], chosen)

    def test_repeated_realignment_and_reruns_keep_it(self) -> None:
        session = _hydrated_session()
        _user_picks(session, "advanced")
        for _ in range(3):
            align_authoritative_canonical_from_hydrated(session, SNAPSHOT)
            prepare_practice_page(session)
        self.assertEqual(session["practice_notation_difficulty"], "advanced")
        self.assertEqual(canonical_practice_filters(session)["practice_notation_difficulty"], "advanced")

    def test_later_change_of_mind_is_also_kept(self) -> None:
        session = _hydrated_session()
        _user_picks(session, "advanced")
        align_authoritative_canonical_from_hydrated(session, SNAPSHOT)
        _user_picks(session, "easy")
        align_authoritative_canonical_from_hydrated(session, SNAPSHOT)
        prepare_practice_page(session)
        self.assertEqual(session["practice_notation_difficulty"], "easy")

    def test_a_newly_hydrated_payload_is_authoritative_again(self) -> None:
        session = _hydrated_session()
        _user_picks(session, "advanced")
        self.assertTrue(session.get(PRACTICE_USER_EDITED_SINCE_HYDRATE_KEY))
        arm_startup_suppression(session, "new_hydrate")  # a fresh restore from storage
        self.assertFalse(session.get(PRACTICE_USER_EDITED_SINCE_HYDRATE_KEY))
        newer = {"practice_state": {"practice_notation_difficulty": "easy", "practice_minutes": 30,
                                    "practice_focus_section": "Full Song"}}
        align_authoritative_canonical_from_hydrated(session, newer)
        self.assertEqual(canonical_practice_filters(session)["practice_notation_difficulty"], "easy")


if __name__ == "__main__":
    unittest.main()

"""QA cloud pass: sync fixes found by running the app against an isolated Supabase project.

1. Cloud timestamps are UTC (naive local time was stored in timestamptz columns).
2. A disk copy with an OLDER workspace revision never outranks the cloud, however fresh its timestamp.
3. Releasing startup suppression never rolls revision surfaces backwards.
4. An empty stored capo value is not "drift" (it re-applied the saved workspace over local edits).
5. A conflict against the session's OWN earlier write is recognisable; a foreign write is not.
"""
from __future__ import annotations

import unittest
from datetime import datetime

import suite_cloud_state as scs
import suite_storage_supabase as sss
from music_persistent_state import _capo_value_differs
from music_startup_save_suppression import _advance_revision_surfaces


def _blob(rev: int, tag: str = "x") -> dict:
    return {"workspace_revision": rev, "music_workspace_state": {"workspace_revision": rev}, "tag": tag}


class TestUtcTimestamps(unittest.TestCase):
    def test_now_iso_is_utc_with_offset(self) -> None:
        stamp = sss._now_iso()
        parsed = datetime.fromisoformat(stamp)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)


class TestRevisionBeatsTimestamp(unittest.TestCase):
    def test_stale_disk_with_fresh_timestamp_loses_to_cloud(self) -> None:
        pick = scs.pick_restore_session(_blob(8), "2026-11-14T08:00:00", _blob(6), "2026-11-14T13:00:00+00:00")
        self.assertEqual(pick.source, "cloud")
        self.assertEqual(pick.reason, "cloud revision ahead of disk")

    def test_disk_at_or_ahead_of_cloud_still_wins_when_newer(self) -> None:
        pick = scs.pick_restore_session(_blob(8), "2026-11-14T08:00:00", _blob(9), "2026-11-14T13:00:00+00:00")
        self.assertEqual(pick.source, "disk")

    def test_local_unsaved_edits_still_win(self) -> None:
        pick = scs.pick_restore_session(_blob(8), "2026-11-14T08:00:00", _blob(6), "2026-11-14T13:00:00+00:00",
                                        local_dirty=True)
        self.assertEqual(pick.source, "disk")

    def test_unrevisioned_blobs_keep_previous_behaviour(self) -> None:
        pick = scs.pick_restore_session({"a": 1}, "2026-11-14T08:00:00", {"b": 2}, "2026-11-14T13:00:00+00:00")
        self.assertEqual(pick.source, "disk")


class TestAdvanceOnly(unittest.TestCase):
    def test_never_lowers_a_surface(self) -> None:
        ss = {"a": 8, "b": 3, "c": None}
        _advance_revision_surfaces(ss, 6, ("a", "b", "c", "d"))
        self.assertEqual(ss, {"a": 8, "b": 6, "c": 6, "d": 6})


class TestCapoDrift(unittest.TestCase):
    def test_empty_stored_value_is_not_drift(self) -> None:
        for stored in (None, ""):
            self.assertFalse(_capo_value_differs("Bb", stored))
            self.assertFalse(_capo_value_differs(None, stored))

    def test_real_difference_is_drift(self) -> None:
        self.assertTrue(_capo_value_differs("Bb", "C"))
        self.assertTrue(_capo_value_differs(True, False))
        self.assertFalse(_capo_value_differs("C", "C"))


class _FakeStorage:
    def __init__(self, metrics: dict):
        self._m = metrics

    def _load_state_row_metrics(self, _key: str) -> dict:
        return dict(self._m)


class TestOwnWriteRecognition(unittest.TestCase):
    def test_token_is_stable_per_session_and_random_across_sessions(self) -> None:
        a, b = {}, {}
        self.assertEqual(scs._music_writer_token(a), scs._music_writer_token(a))
        self.assertNotEqual(scs._music_writer_token(a), scs._music_writer_token(b))
        self.assertEqual(scs._music_writer_token(None), "")

    def test_row_written_by_this_session_is_recognised(self) -> None:
        st = _FakeStorage({"writer_session": "tok", "workspace_revision": 14, "full_session": {"workspace_revision": 14}})
        self.assertEqual(scs._own_write_revision(st, "music", "tok"), 14)

    def test_row_written_by_someone_else_is_never_adopted(self) -> None:
        st = _FakeStorage({"writer_session": "other", "workspace_revision": 14, "full_session": {"workspace_revision": 14}})
        self.assertEqual(scs._own_write_revision(st, "music", "tok"), 0)

    def test_row_without_a_writer_is_never_adopted(self) -> None:
        st = _FakeStorage({"workspace_revision": 14, "full_session": {"workspace_revision": 14}})
        self.assertEqual(scs._own_write_revision(st, "music", "tok"), 0)


if __name__ == "__main__":
    unittest.main()

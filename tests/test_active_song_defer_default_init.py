"""Defer default catalog song when cloud workspace expects a saved song."""

from __future__ import annotations

import unittest

from active_song_workspace_restore import (
    ACTIVE_SONG_RESTORE_INCOMPLETE_KEY,
    should_defer_default_master_song_init,
)


class TestDeferDefaultMasterSongInit(unittest.TestCase):
    def test_defer_when_cloud_has_pick_key_not_yet_in_session(self) -> None:
        ss: dict = {
            "_suite_last_cloud_fetch_payload": {
                "core": {"pick_key": "Pop::Some Song — Artist"},
            }
        }
        self.assertTrue(should_defer_default_master_song_init(ss))
        self.assertTrue(ss.get(ACTIVE_SONG_RESTORE_INCOMPLETE_KEY))

    def test_no_defer_when_session_already_has_pick_key(self) -> None:
        ss = {
            "active_catalog_pick_key": "Pop::Some Song — Artist",
            "_suite_last_cloud_fetch_payload": {"core": {"pick_key": "Pop::Other — X"}},
        }
        self.assertFalse(should_defer_default_master_song_init(ss))


if __name__ == "__main__":
    unittest.main()

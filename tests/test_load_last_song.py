"""Issue 15: Load Last Song offers the previous distinct Catalog song, never the current one."""

from __future__ import annotations

import unittest
from unittest import mock

from songs import music_source as ms
from songs.state import ACTIVE_CATALOG_PICK_KEY

BLACKBIRD = "Rock\x1fBlackbird"
ATTENTION = "Pop\x1fAttention"


def _snap(pick: str) -> dict:
    return {"pick_key": pick, "selected_song": {"title": pick.split("\x1f")[1]}}


class TestLoadLastSong(unittest.TestCase):
    def _session(self, current: str, recent: list[str]) -> dict:
        return {
            ACTIVE_CATALOG_PICK_KEY: current,
            ms.LAST_CATALOG_STATE_KEY: _snap(current),  # the commit keeps LAST == current
            ms.CATALOG_RECENT_PICK_KEYS: recent,
        }

    def setUp(self) -> None:
        p = mock.patch.object(ms, "_catalog_snapshot_for_pick_key", side_effect=lambda ss, pk, **k: _snap(pk))
        p.start()
        self.addCleanup(p.stop)

    def test_the_catalog_page_offers_the_previous_distinct_song(self) -> None:
        ss = self._session(BLACKBIRD, [BLACKBIRD, ATTENTION])
        self.assertEqual(ms.load_last_song_snapshot(ss, on_catalog_page=True)["pick_key"], ATTENTION)

    def test_rerunning_the_current_song_does_not_replace_the_previous_entry(self) -> None:
        ss = self._session(BLACKBIRD, [BLACKBIRD, ATTENTION])
        for _ in range(3):
            ss[ms.CATALOG_RECENT_PICK_KEYS] = [BLACKBIRD] + [k for k in ss[ms.CATALOG_RECENT_PICK_KEYS] if k != BLACKBIRD]
            self.assertEqual(ms.load_last_song_snapshot(ss, on_catalog_page=True)["pick_key"], ATTENTION)

    def test_no_previous_distinct_song_means_no_button(self) -> None:
        ss = self._session(BLACKBIRD, [BLACKBIRD])
        self.assertIsNone(ms.load_last_song_snapshot(ss, on_catalog_page=True))

    def test_from_the_custom_hub_the_last_catalog_song_is_the_way_back(self) -> None:
        ss = self._session(ATTENTION, [ATTENTION, BLACKBIRD])
        self.assertEqual(ms.load_last_song_snapshot(ss, on_catalog_page=False)["pick_key"], ATTENTION)


if __name__ == "__main__":
    unittest.main()

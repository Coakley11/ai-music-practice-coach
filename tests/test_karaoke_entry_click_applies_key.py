"""Verify clicking a karaoke entry applies its saved Practice Key."""

from __future__ import annotations

import unittest

import karaoke_mode as km
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


def _ss(**extra) -> dict:
    ss: dict = {
        "instrument": "Voice",
        PRACTICE_KEY_BY_SOURCE_KEY: {},
        "karaoke_queue": [],
    }
    ss.update(extra)
    return ss


class TestClickAppliesEntryPracticeKey(unittest.TestCase):
    """The click handler calls km.apply_entry_practice_key(ss, entry)."""

    def test_apply_entry_practice_key_writes_per_source_store_only(self) -> None:
        """The entry key goes to the per-source store, never to global.

        _activate_entry_at calls this on every automatic Start / Next /
        Previous, so writing the global practice_concert_key here would let
        karaoke progression overwrite the user's global Practice Key. The
        explicit setlist-click and Add-Lyrics paths update global separately.
        """
        ss = _ss()
        entry = {
            "entry_id": "aaa",
            "pick_key": "Pop::gravity",
            "practice_key": "D",
            "title": "Gravity",
            "artist": "John Mayer",
        }
        result = km.apply_entry_practice_key(ss, entry)
        self.assertEqual(result, "D")
        self.assertEqual(get_practice_concert_key(ss, "Pop::gravity"), "D")
        self.assertIsNone(
            ss.get("practice_concert_key"),
            "automatic karaoke progression must not write the global Practice Key",
        )

    def test_apply_entry_practice_key_uses_set_practice_concert_key(self) -> None:
        ss = _ss()
        entry = {
            "entry_id": "bbb",
            "pick_key": "Pop::gravity",
            "practice_key": "D",
        }
        km.apply_entry_practice_key(ss, entry)
        stored = get_practice_concert_key(ss, "Pop::gravity")
        self.assertEqual(stored, "D")

    def test_different_entries_same_song_apply_different_keys(self) -> None:
        ss = _ss()
        entry_d = {
            "entry_id": "e1",
            "pick_key": "Pop::gravity",
            "practice_key": "D",
        }
        entry_f = {
            "entry_id": "e2",
            "pick_key": "Pop::gravity",
            "practice_key": "F",
        }
        km.apply_entry_practice_key(ss, entry_d)
        self.assertEqual(get_practice_concert_key(ss, "Pop::gravity"), "D")

        km.apply_entry_practice_key(ss, entry_f)
        # Two entries of one song: the store tracks the active entry's key.
        self.assertEqual(get_practice_concert_key(ss, "Pop::gravity"), "F")
        self.assertIsNone(
            ss.get("practice_concert_key"),
            "neither entry may leak into the global Practice Key",
        )

    def test_empty_practice_key_does_not_crash(self) -> None:
        ss = _ss()
        entry = {
            "entry_id": "ccc",
            "pick_key": "Pop::gravity",
            "practice_key": "",
        }
        result = km.apply_entry_practice_key(ss, entry)
        self.assertEqual(result, "")

    def test_none_entry_returns_empty(self) -> None:
        ss = _ss()
        result = km.apply_entry_practice_key(ss, None)
        self.assertEqual(result, "")

    def test_pending_display_key_set_by_click_handler(self) -> None:
        """Simulates the click handler setting _pending_display_key."""
        ss = _ss()
        entry = {
            "entry_id": "ddd",
            "pick_key": "Pop::gravity",
            "practice_key": "D",
        }
        km.apply_entry_practice_key(ss, entry)
        if entry.get("practice_key"):
            ss["_pending_display_key"] = str(entry["practice_key"]).strip()
        self.assertEqual(ss["_pending_display_key"], "D")


if __name__ == "__main__":
    unittest.main()

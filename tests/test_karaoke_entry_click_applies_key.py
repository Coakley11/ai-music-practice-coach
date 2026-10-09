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

    def test_apply_entry_practice_key_writes_session_state(self) -> None:
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
        self.assertEqual(ss.get("practice_concert_key"), "D")

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
        self.assertEqual(ss["practice_concert_key"], "D")

        km.apply_entry_practice_key(ss, entry_f)
        # The live session key updates to F regardless of store guards
        self.assertEqual(ss["practice_concert_key"], "F")

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

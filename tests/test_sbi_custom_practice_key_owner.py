"""SBI Custom Practice Key must write LAST_CUSTOM pick, not Global Active catalog."""
from __future__ import annotations

import unittest

from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    get_practice_concert_key,
    resolve_settings_pick_for_write,
    set_practice_concert_key,
)


class TestSbiCustomPracticeKeyOwner(unittest.TestCase):
    def test_custom_sbi_backing_pk_does_not_contaminate_catalog(self) -> None:
        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Custom progression",
            "sbi_preview_source": "Custom progression",
            "active_catalog_pick_key": shape,
            "practice_key_by_source": {shape: "Dbm"},
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "active": {
                    "id": "trial-sbi-1",
                    "name": "Trial Song",
                    "original_key_center": "C",
                },
            },
        }
        write_pick = resolve_settings_pick_for_write(session)
        self.assertTrue(str(write_pick).startswith("custom::"), write_pick)
        set_practice_concert_key(session, "Eb")
        self.assertEqual(get_practice_concert_key(session, shape), "Dbm")
        self.assertEqual(get_practice_concert_key(session, write_pick), "Eb")


if __name__ == "__main__":
    unittest.main()

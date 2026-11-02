"""Issues 13 / 10: each Custom song opens at its OWN Practice Key (its saved override, else its Original Key)."""

from __future__ import annotations

import copy
import unittest

from custom_progression_lab import CPL_ACTIVE_KEY, apply_cpl_session_progression, load_saved_progression, save_progression
from songs.music_source import custom_pick_key_for
from songs.practice_key_state import (
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)

TRIAL = {"id": "trial-1", "name": "Trial Song", "original_key_center": "D", "progression_style": "Pop",
         "original_sections": {"Verse": [{"chord": "D", "bars": 1}, {"chord": "Bm", "bars": 1}]}}
BLUES = {"id": "blues-1", "name": "Blues in F minor", "original_key_center": "Fm", "progression_style": "Blues",
         "original_sections": {"Verse": [{"chord": "Fm7", "bars": 2}, {"chord": "C7", "bars": 1}]}}


def _store() -> dict:
    store: dict = {}
    save_progression(store, "Trial Song", copy.deepcopy(TRIAL))
    save_progression(store, "Blues in F minor", copy.deepcopy(BLUES))
    return store


def _load(ss: dict, store: dict, name: str) -> None:
    ss["cpl_saved_progressions"] = store  # the app always has the library; pick aliases resolve through it
    apply_cpl_session_progression(ss, load_saved_progression(store, name), reset_display_key=True)


def _pk(ss: dict) -> str:
    return get_practice_concert_key(ss, custom_pick_key_for(ss[CPL_ACTIVE_KEY]))


def _choose(ss: dict, key: str) -> None:
    pick = custom_pick_key_for(ss[CPL_ACTIVE_KEY])
    set_practice_concert_key(ss, key, pick_key=pick)
    mark_practice_key_user_override(ss, pick)


class TestPerSongPracticeKey(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _store()
        self.ss: dict = {}

    def test_without_an_override_a_song_opens_at_its_original_key(self) -> None:
        _load(self.ss, self.store, "Trial Song")
        self.assertEqual(_pk(self.ss), "D")
        _load(self.ss, self.store, "Blues in F minor")
        self.assertEqual(_pk(self.ss), "Fm")

    def test_each_song_restores_its_own_explicit_key_and_never_the_others(self) -> None:
        _load(self.ss, self.store, "Trial Song")
        _choose(self.ss, "E")
        _load(self.ss, self.store, "Blues in F minor")
        self.assertEqual(_pk(self.ss), "Fm")  # Trial's E did not leak
        _choose(self.ss, "Cm")
        _load(self.ss, self.store, "Trial Song")
        self.assertEqual(_pk(self.ss), "E")  # Blues' Cm did not leak
        _load(self.ss, self.store, "Blues in F minor")
        self.assertEqual(_pk(self.ss), "Cm")

    def test_original_key_is_never_changed_by_a_practice_key(self) -> None:
        _load(self.ss, self.store, "Blues in F minor")
        _choose(self.ss, "Cm")
        self.assertEqual(self.ss[CPL_ACTIVE_KEY]["original_key_center"], "Fm")
        _load(self.ss, self.store, "Trial Song")
        _load(self.ss, self.store, "Blues in F minor")
        self.assertEqual(self.ss[CPL_ACTIVE_KEY]["original_key_center"], "Fm")
        self.assertEqual(self.store["Blues in F minor"]["original_key_center"], "Fm")
        self.assertEqual(self.store["Trial Song"]["original_key_center"], "D")

    def test_a_key_of_the_other_mode_is_ignored_not_converted(self) -> None:
        _load(self.ss, self.store, "Trial Song")
        _choose(self.ss, "Em")  # minor key chosen on a major song (stale or wrong-mode)
        _load(self.ss, self.store, "Blues in F minor")
        _load(self.ss, self.store, "Trial Song")
        self.assertEqual(_pk(self.ss), "D")

    def test_saved_records_are_not_modified_by_switching(self) -> None:
        before = copy.deepcopy(self.store)
        _load(self.ss, self.store, "Trial Song")
        _choose(self.ss, "E")
        _load(self.ss, self.store, "Blues in F minor")
        _load(self.ss, self.store, "Trial Song")
        for name in before:
            for key in ("id", "name", "original_key_center", "progression_style", "original_sections"):
                self.assertEqual(self.store[name][key], before[name][key], (name, key))


if __name__ == "__main__":
    unittest.main()

"""Loading a saved Custom song installs *that* song's content, never a mix with the previous one."""

from __future__ import annotations

import copy
import re
import unittest

from streamlit.testing.v1 import AppTest

from custom_progression_lab import CPL_ACTIVE_KEY, CPL_SAVED_KEY, save_progression


def _page() -> None:
    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


TRIAL = {
    "id": "trial-1",
    "name": "Trial Song",
    "original_key_center": "D",
    "time_signature": "4/4",
    "bpm": 100,
    "progression_style": "Pop",
    "original_sections": {
        "Verse": [{"chord": "D", "bars": 1}, {"chord": "Bm", "bars": 1}, {"chord": "G", "bars": 1}, {"chord": "A", "bars": 1}]
    },
}
BLUES = {
    "id": "blues-1",
    "name": "Blues in F minor",
    "original_key_center": "Fm",
    "time_signature": "4/4",
    "bpm": 130,
    "progression_style": "Blues",
    "original_sections": {
        "Verse": [
            {"chord": "Fm7", "bars": 2},
            {"chord": "Bb7", "bars": 1},
            {"chord": "Fm7", "bars": 1},
            {"chord": "C7", "bars": 1},
        ]
    },
}


def _store() -> dict:
    store: dict = {}
    save_progression(store, "Trial Song", copy.deepcopy(TRIAL))
    save_progression(store, "Blues in F minor", copy.deepcopy(BLUES))
    return store


def _verse(song: dict) -> list[str]:
    return [str(e["chord"]) for e in (song.get("original_sections") or {}).get("Verse", [])]


def _load(at: AppTest, name: str) -> AppTest:
    at.session_state["cpl_load_pick"] = name
    at.button(key="cpl_load_btn").click().run()
    return at


class TestLoadSelected(unittest.TestCase):
    def setUp(self) -> None:
        self.at = AppTest.from_function(_page, default_timeout=120)
        self.at.session_state[CPL_SAVED_KEY] = _store()
        self.at.run()
        self.assertFalse(self.at.exception)

    def test_each_load_installs_its_own_chords_and_metadata(self) -> None:
        for name, want in (("Trial Song", TRIAL), ("Blues in F minor", BLUES), ("Trial Song", TRIAL), ("Blues in F minor", BLUES)):
            _load(self.at, name)
            self.assertFalse(self.at.exception, name)
            active = self.at.session_state[CPL_ACTIVE_KEY]
            self.assertEqual(active["name"], name)
            self.assertEqual(active["id"], want["id"], name)
            self.assertEqual(_verse(active), _verse(want), name)
            self.assertEqual(active["original_key_center"], want["original_key_center"], name)
            self.assertEqual(active["progression_style"], want["progression_style"], name)
            self.assertEqual(active["bpm"], want["bpm"], name)

    def test_loading_never_alters_either_saved_record(self) -> None:
        before = copy.deepcopy(self.at.session_state[CPL_SAVED_KEY])
        for name in ("Trial Song", "Blues in F minor", "Trial Song"):
            _load(self.at, name)
        after = self.at.session_state[CPL_SAVED_KEY]
        for name in before:
            for key in ("id", "name", "original_key_center", "progression_style", "bpm", "original_sections"):
                self.assertEqual(after[name][key], before[name][key], f"{name}.{key}")

    def test_the_page_shows_the_loaded_songs_chords_not_the_previous_ones(self) -> None:
        _load(self.at, "Trial Song")
        _load(self.at, "Blues in F minor")
        text = " ".join(re.sub(r"<[^>]+>", " ", str(m.value)) for m in self.at.markdown)
        self.assertIn("Fm7", text)
        self.assertNotIn("Bm", text.replace("Bb", ""))  # Trial Song's Bm must be gone
        self.assertNotIn(">Dm<", text)

    def test_load_then_reload_persisted_state_keeps_the_same_content(self) -> None:
        _load(self.at, "Blues in F minor")
        saved_now = copy.deepcopy(self.at.session_state[CPL_SAVED_KEY])
        fresh = AppTest.from_function(_page, default_timeout=120)
        fresh.session_state[CPL_SAVED_KEY] = saved_now
        fresh.run()
        _load(fresh, "Blues in F minor")
        self.assertEqual(_verse(fresh.session_state[CPL_ACTIVE_KEY]), _verse(BLUES))


class TestStaleLastCustomMemory(unittest.TestCase):
    """Issue 12: LAST_CUSTOM (identity memory) must never overwrite a loaded, named song."""

    def _session(self) -> dict:
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        store = _store()
        return {
            CPL_SAVED_KEY: store,
            CPL_ACTIVE_KEY: copy.deepcopy(store["Blues in F minor"]),
            LAST_CUSTOM_STATE_KEY: {
                "name": "Trial Song",
                "active": copy.deepcopy(store["Trial Song"]),
                "pick_key": "custom::trial-1",
                "custom_home_key": "D",
            },
        }

    def test_a_stale_snapshot_does_not_replace_the_loaded_named_song(self) -> None:
        from songs.music_source import install_last_custom_into_live_cpl

        ss = self._session()
        install_last_custom_into_live_cpl(ss, prefer_last_custom=True)
        active = ss[CPL_ACTIVE_KEY]
        self.assertEqual((active["name"], active["id"]), ("Blues in F minor", "blues-1"))
        self.assertEqual(_verse(active), _verse(BLUES))
        self.assertEqual(active["original_key_center"], "Fm")

    def test_the_memory_follows_the_loaded_song_afterwards(self) -> None:
        from songs.music_source import LAST_CUSTOM_STATE_KEY, install_last_custom_into_live_cpl

        ss = self._session()
        install_last_custom_into_live_cpl(ss, prefer_last_custom=True)
        self.assertEqual(ss[LAST_CUSTOM_STATE_KEY]["active"]["id"], "blues-1")

    def test_a_generic_shell_is_still_replaced_by_the_named_last_custom(self) -> None:
        from songs.music_source import install_last_custom_into_live_cpl

        ss = self._session()
        ss[CPL_ACTIVE_KEY] = {"name": "My Progression", "original_key_center": "C",
                              "original_sections": {"Verse": [{"chord": "C", "bars": 1}]}}
        install_last_custom_into_live_cpl(ss, prefer_last_custom=True)
        self.assertEqual(ss[CPL_ACTIVE_KEY]["name"], "Trial Song")

    def test_load_selected_updates_the_memory_in_the_real_page(self) -> None:
        from songs.music_source import LAST_CUSTOM_STATE_KEY

        at = AppTest.from_function(_page, default_timeout=120)
        at.session_state[CPL_SAVED_KEY] = _store()
        at.run()
        _load(at, "Trial Song")
        _load(at, "Blues in F minor")
        self.assertEqual(at.session_state[LAST_CUSTOM_STATE_KEY]["active"]["id"], "blues-1")


if __name__ == "__main__":
    unittest.main()

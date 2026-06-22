"""Genre filter, music source alignment, and multitrack session persistence tests."""

from __future__ import annotations

import json
import unittest

from music_persistent_state import apply_music_disk_state, build_music_disk_state
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SONG_PICKER_ACTIVE_SOURCE_KEY,
    SONG_PICKER_SOURCE_CATALOG,
    SONG_PICKER_SOURCE_CUSTOM,
    SOURCE_CUSTOM,
    cpl_session_is_active,
    reconcile_music_picker_source_widget,
)
from songs.picker_session import WORKSPACE_GENRE_FILTERS_KEY, toggle_genre_filter


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeSt:
    def __init__(self, session_state: dict | None = None) -> None:
        self.session_state = session_state if session_state is not None else _FakeSessionState()


class TestGenreFilterPersistence(unittest.TestCase):
    def test_cloud_restore_does_not_clobber_live_genre_filters(self) -> None:
        ss = _FakeSessionState(
            {
                "studio_page": "picker",
                WORKSPACE_GENRE_FILTERS_KEY: ["Pop"],
                "_genre_filters_user_touched": True,
            }
        )
        st = _FakeSt(ss)
        blob = {
            "core": {"studio_page": "picker"},
            "session": {WORKSPACE_GENRE_FILTERS_KEY: []},
        }
        apply_music_disk_state(st, blob, song_picker_catalog={}, song_library=None)
        self.assertEqual(ss.get(WORKSPACE_GENRE_FILTERS_KEY), ["Pop"])

    def test_toggle_updates_filters(self) -> None:
        state: dict = {WORKSPACE_GENRE_FILTERS_KEY: []}
        toggle_genre_filter(state, "Pop")
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], ["Pop"])
        toggle_genre_filter(state, "Rock")
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], ["Pop", "Rock"])
        toggle_genre_filter(state, "Pop")
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], ["Rock"])


class TestMusicSourceAlignment(unittest.TestCase):
    def test_custom_pick_key_wins_over_catalog_choice_flag(self) -> None:
        ss = {
            "active_catalog_pick_key": "custom::trial-1",
            "active_music_source": "catalog",
            "user_catalog_source_choice": True,
        }
        self.assertTrue(cpl_session_is_active(ss))

    def test_reconcile_sets_custom_source_widget(self) -> None:
        ss = {
            "active_catalog_pick_key": "custom::trial-1",
            "active_music_source": "catalog",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": ["D"]},
            },
        }
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)


class TestMultitrackSessionPersistence(unittest.TestCase):
    def test_mt_tracks_round_trip_through_disk_state(self) -> None:
        audio = b"guitar-layer-bytes"
        ss = _FakeSessionState(
            {
                "studio_page": "multitrack",
                "mt_tracks": {"Guitar": audio, "Bass": None},
                "mt_track_filenames": {"Guitar": "guitar.wav", "Bass": ""},
            }
        )
        st = _FakeSt(ss)
        state = build_music_disk_state(st)
        blob = json.loads(json.dumps(state, default=str))
        fresh = _FakeSessionState({"studio_page": "multitrack"})
        fresh_st = _FakeSt(fresh)
        apply_music_disk_state(fresh_st, blob, song_picker_catalog={}, song_library=None)
        self.assertEqual(fresh.get("mt_tracks", {}).get("Guitar"), audio)


if __name__ == "__main__":
    unittest.main()

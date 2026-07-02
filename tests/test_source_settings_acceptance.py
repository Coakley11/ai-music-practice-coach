"""Acceptance tests for per-source key/BPM isolation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from song_catalog.catalog import format_pick_key
from songs.playback_defaults import (
    active_song_sync_id,
    apply_backing_defaults_for_song,
    playback_song_id,
    sync_backing_bpm_from_slider,
)
from songs.practice_key_state import (
    BPM_BY_SOURCE_KEY,
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    get_source_bpm,
    resolve_practice_concert_key_for_pick,
    set_practice_concert_key,
    set_source_bpm,
)


def _shape_pick() -> str:
    return format_pick_key("Pop", "Shape of You")


class TestPerSourceKeyBacking(unittest.TestCase):
    def test_catalog_rebuild_uses_saved_practice_key(self) -> None:
        from music_source_ownership import rebuild_catalog_backing_from_canonical_pick

        pick = _shape_pick()
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": pick,
                "bpm": 96,
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        ctx = rebuild_catalog_backing_from_canonical_pick(
            session,
            pick_key=pick,
            reset_to_original=True,
        )
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(session.get("catalog_rebuild_result_key"), "Am")
        self.assertEqual(str(ctx.concert_key), "Am")
        self.assertEqual(str(ctx.display_key), "Am")

    def test_custom_backing_keeps_saved_eb_key(self) -> None:
        from backing_context import restore_custom_song_backing
        from custom_progression_lab import CPL_ACTIVE_KEY

        pick = "custom::trial-1"
        session = {
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
                "bpm": 100,
            },
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Eb"},
            "display_key": "Eb",
            "concert_key": "Eb",
        }
        restore_custom_song_backing(session)
        self.assertEqual(session.get("display_key"), "Eb")
        self.assertEqual(session.get("concert_key"), "Eb")

    def test_shape_am_refresh_stays_am(self) -> None:
        pick = _shape_pick()
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        resolved = resolve_practice_concert_key_for_pick(session, pick, original_key="Bm")
        self.assertEqual(resolved, "Am")


class TestPerSourceBpmIsolation(unittest.TestCase):
    def test_switching_song_loads_default_not_previous_bpm(self) -> None:
        trial = "custom::trial-1"
        shape = _shape_pick()
        st = SimpleNamespace(
            session_state={
                "active_catalog_pick_key": shape,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape,
                    "bpm": 96,
                },
                BPM_BY_SOURCE_KEY: {trial: 120},
                "backing_track_bpm": 120,
                "bpm": 120,
            }
        )
        shape_pid = playback_song_id(
            is_custom=False,
            song_title="Shape of You",
            song_artist="Ed Sheeran",
        )
        sync_id = active_song_sync_id(pick_key=shape, playback_song_id=shape_pid, is_custom=False)
        bpm, _ = apply_backing_defaults_for_song(
            st,
            song_id=sync_id,
            default_bpm=96,
            default_groove="Pop groove",
        )
        self.assertEqual(bpm, 96)
        self.assertNotEqual(bpm, 120)

    def test_saved_bpm_restored_for_same_source(self) -> None:
        shape = _shape_pick()
        session = {
            "active_catalog_pick_key": shape,
            BPM_BY_SOURCE_KEY: {shape: 88},
        }
        self.assertEqual(get_source_bpm(session, shape, default=96), 88)

    def test_bpm_slider_writes_bpm_by_source(self) -> None:
        shape = _shape_pick()
        st = SimpleNamespace(
            session_state={
                "active_catalog_pick_key": shape,
                "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
            }
        )
        sync_backing_bpm_from_slider(st, slider_bpm=105)
        self.assertEqual(st.session_state[BPM_BY_SOURCE_KEY][shape], 105)

    def test_sources_do_not_share_keys(self) -> None:
        trial = "custom::trial-1"
        shape = _shape_pick()
        session = {
            "active_catalog_pick_key": trial,
            PRACTICE_KEY_BY_SOURCE_KEY: {shape: "Am", trial: "Eb"},
        }
        self.assertEqual(get_practice_concert_key(session, trial), "Eb")
        self.assertEqual(get_practice_concert_key(session, shape), "Am")


if __name__ == "__main__":
    unittest.main()

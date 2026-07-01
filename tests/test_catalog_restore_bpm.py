"""Catalog restore BPM slider convergence tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from songs.playback_defaults import (
    active_song_sync_id,
    backing_bpm_slider_widget_key,
    resolve_backing_bpm_for_slider,
)
from songs.practice_key_state import mark_force_bpm_sync


class TestCatalogRestoreBpmSlider(unittest.TestCase):
    def test_force_bpm_sync_overrides_stale_slider(self) -> None:
        pick = "Pop::Shape of You"
        sync_id = active_song_sync_id(
            pick_key=pick,
            playback_song_id="cat::Shape of You::Ed Sheeran",
            is_custom=False,
        )
        slider_key = backing_bpm_slider_widget_key(sync_id)
        session = {
            "_last_bpm_song": sync_id,
            "_canonical_active_backing_song_id": sync_id,
            slider_key: 100,
            "backing_track_bpm": 100,
            "bpm": 100,
        }
        mark_force_bpm_sync(session, sync_id)
        st = SimpleNamespace(session_state=session)
        bpm = resolve_backing_bpm_for_slider(
            st,
            sync_id=sync_id,
            default_bpm=96,
            song_just_reset=False,
        )
        self.assertEqual(bpm, 96)
        self.assertEqual(session[slider_key], 96)
        self.assertEqual(session["backing_track_bpm"], 96)


if __name__ == "__main__":
    unittest.main()

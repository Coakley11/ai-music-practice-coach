"""Issue 21: a Custom song's Backing tempo is its own, never the previous song's leftover slider."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import backing_play_session as bps


def _session(domain_bpm: int, saved_bpm: int) -> dict:
    return {
        "backing_track_bpm": domain_bpm,
        "bpm": domain_bpm,
        "_backing_source_default_bpm": saved_bpm,
    }


class TestLeftoverSliderAfterSongSwitch(unittest.TestCase):
    def _ctx(self, source: str):
        return SimpleNamespace(source=source, bpm=0, bound_pick_key="custom::blues-1", active_song_id="custom::blues-1")

    def test_expired_custom_session_ignores_previous_songs_slider(self) -> None:
        ss = _session(domain_bpm=100, saved_bpm=130)
        with mock.patch("backing_context.get_backing_context", return_value=self._ctx("custom_progression")), \
                mock.patch.object(bps, "_play_session_is_existing", return_value=False), \
                mock.patch.object(bps, "_source_init_bpm", return_value=130), \
                mock.patch.object(bps, "_live_slider_bpm", return_value=100), \
                mock.patch.object(bps, "_stale_widget_default_bpms", return_value={130}):
            self.assertEqual(bps.current_backing_play_bpm(ss, default=0), 130)

    def test_live_play_session_edit_still_wins(self) -> None:
        ss = _session(domain_bpm=100, saved_bpm=130)
        with mock.patch("backing_context.get_backing_context", return_value=self._ctx("custom_progression")), \
                mock.patch.object(bps, "_play_session_is_existing", return_value=True), \
                mock.patch.object(bps, "_source_init_bpm", return_value=130), \
                mock.patch.object(bps, "_live_slider_bpm", return_value=100), \
                mock.patch.object(bps, "_stale_widget_default_bpms", return_value={130}):
            self.assertEqual(bps.current_backing_play_bpm(ss, default=0), 100)

    def test_catalog_source_behaviour_unchanged(self) -> None:
        ss = _session(domain_bpm=100, saved_bpm=130)
        with mock.patch("backing_context.get_backing_context", return_value=self._ctx("regular_song")), \
                mock.patch.object(bps, "_play_session_is_existing", return_value=False), \
                mock.patch.object(bps, "_source_init_bpm", return_value=130), \
                mock.patch.object(bps, "_live_slider_bpm", return_value=100), \
                mock.patch.object(bps, "_stale_widget_default_bpms", return_value={130}):
            self.assertEqual(bps.current_backing_play_bpm(ss, default=0), 100)


if __name__ == "__main__":
    unittest.main()

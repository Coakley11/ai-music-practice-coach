"""Tests for multitrack Project Library load debug trace."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_multitrack_catalog import load_multitrack_project_from_catalog, save_multitrack_session_with_notes
from multitrack_project_load_trace import (
    begin_project_load_trace,
    verify_loaded_project_matches_catalog,
)
from multitrack_slots import MULTITRACK_SLOTS


class TestMultitrackProjectLoadTrace(unittest.TestCase):
    def _session(self) -> dict:
        return {
            "mt_tracks": {slot: (b"guitar" if slot == "Guitar" else None) for slot in MULTITRACK_SLOTS},
            "mt_track_filenames": {"Guitar": "guitar.wav"},
            "mt_name_Guitar": "Guitar A",
            "mt_track_controls": {"Guitar": {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0}},
            "multitrack_backing_music_wav": b"backing-a",
            "mt_backing_volume": 1.1,
            "mt_loop_backing": True,
            "mt_metronome_playback": False,
            "mt_use_backing_monitor": True,
            "active_song_title": "Say",
        }

    def test_save_as_new_creates_separate_project_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            ok_a, mid_a, _ = save_multitrack_session_with_notes(
                                self._session(),
                                project_name="Project A",
                                notes="Forest Park",
                                song_title="Say",
                            )
                            self.assertTrue(ok_a)
                            session_b = {
                                **self._session(),
                                "mt_name_Guitar": "Piano B",
                                "mt_backing_volume": 0.45,
                                "mt_loop_backing": False,
                                "mt_metronome_playback": True,
                                "multitrack_backing_music_wav": b"backing-b",
                                "multitrack_catalog_active_id": mid_a,
                                "_last_catalog_multitrack_id": mid_a,
                            }
                            ok_b, mid_b, _ = save_multitrack_session_with_notes(
                                session_b,
                                project_name="Project B",
                                notes="Queens Park",
                                song_title="Annie's Song",
                            )
                            self.assertTrue(ok_b)
                            self.assertNotEqual(mid_a, mid_b)

    def test_load_trace_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            ok, mid, _ = save_multitrack_session_with_notes(
                                self._session(),
                                project_name="Project A",
                                notes="Forest Park",
                                song_title="Say",
                            )
                            self.assertTrue(ok)
                            working: dict = {}
                            begin_project_load_trace(
                                working,
                                clicked_project_id=mid,
                                clicked_project_title="Project A",
                                payload_multitrack_id=mid,
                            )
                            with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (b"x", "")):
                                with patch("media_multitrack_catalog.load_backing_audio", lambda session, st=None: (b"backing-a", "")):
                                    ok_load, _ = load_multitrack_project_from_catalog(working, mid, load_audio=True)
                            self.assertTrue(ok_load)
                            trace = working.get("_mt_project_load_trace") or {}
                            self.assertEqual((trace.get("clicked") or {}).get("clicked_project_id"), mid)
                            self.assertEqual((trace.get("catalog_row") or {}).get("loaded_project_title"), "Project A")
                            result = verify_loaded_project_matches_catalog(working)
                            self.assertTrue(result.get("match"), result.get("mismatches"))


if __name__ == "__main__":
    unittest.main()

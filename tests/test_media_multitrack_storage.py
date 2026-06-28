"""Multitrack track storage tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_storage import (
    PLAYBACK_METADATA_ONLY,
    PLAYBACK_PLAYABLE,
    build_storage_ref,
    load_track_audio,
    persist_track_audio,
    track_playback_status,
)
from media_persistence import build_media_ami_payload


class TestMultitrackTrackStorage(unittest.TestCase):
    def test_persist_track_local_and_cloud_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def _fake_ws_dir(ws=None):
                d = root / "workspaces" / str(ws or "daniel")
                d.mkdir(parents=True, exist_ok=True)
                return d

            with patch("media_storage.recording_local_abs_path", lambda ws, rel: _fake_ws_dir(ws) / rel):
                with patch("media_storage._cloud_storage_enabled", lambda: True):
                    mock_client = MagicMock()
                    with patch("media_storage._service_storage_client", lambda: mock_client):
                        store = persist_track_audio(
                            None,
                            "mt-1",
                            "track-1",
                            b"layer-audio",
                            filename="guitar.wav",
                            workspace_id="daniel",
                        )
                        self.assertTrue(store.get("local_ok"))
                        self.assertTrue(store.get("storage_ref"))
                        self.assertEqual(store.get("playback_status"), PLAYBACK_PLAYABLE)

    def test_track_playback_status_no_download(self) -> None:
        track = {
            "track_id": "t1",
            "slot": "Guitar",
            "storage_ref": build_storage_ref("music-media", "u/daniel/multitrack/m1/t1.wav"),
        }
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            with patch("media_storage._cloud_storage_enabled", lambda: True):
                with patch("media_storage._track_local_exists", lambda ws, rel: False):
                    self.assertEqual(
                        track_playback_status(track, session_workspace="daniel", st=None),
                        PLAYBACK_PLAYABLE,
                    )

    def test_load_track_from_cloud_caches_locally(self) -> None:
        audio = b"cloud-layer"
        storage_ref = build_storage_ref("music-media", "u/daniel/multitrack/m1/t1.wav")
        track = {
            "track_id": "t1",
            "slot": "Guitar",
            "storage_ref": storage_ref,
            "local_path": "media/multitrack/m1/t1.wav",
        }
        session = {"multitrack_id": "m1", "workspace_id": "daniel"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def _fake_ws_dir(ws=None):
                d = root / "workspaces" / str(ws or "daniel")
                d.mkdir(parents=True, exist_ok=True)
                return d

            with patch("media_storage.recording_local_abs_path", lambda ws, rel: _fake_ws_dir(ws) / rel):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.download_recording_cloud", lambda ref, st=None: (audio, "")):
                        loaded, err = load_track_audio(track, session=session, st=None)
                        self.assertEqual(loaded, audio, err)

    def test_metadata_only_track_not_playable(self) -> None:
        track = {
            "track_id": "t1",
            "slot": "Guitar",
            "analysis_summary": {"has_audio": True},
        }
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            self.assertEqual(
                track_playback_status(track, session_workspace="daniel"),
                PLAYBACK_METADATA_ONLY,
            )

    def test_ami_payload_excludes_multitrack_blobs(self) -> None:
        import json

        catalog = {
            "uploaded_recordings": [],
            "multitrack_sessions": [
                {
                    "multitrack_id": "m1",
                    "title": "Say layers",
                    "song": "Say",
                    "updated_at": "2026-06-28T10:00:00+00:00",
                    "tracks": [
                        {
                            "track_id": "t1",
                            "slot": "Guitar",
                            "name": "Lead",
                            "storage_ref": "supabase://music-media/u/ws/m1/t1.wav",
                            "local_path": "media/multitrack/m1/t1.wav",
                        }
                    ],
                }
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        text = json.dumps(payload)
        self.assertIn("multitrack_sessions", text)
        self.assertNotIn("supabase://", text)
        self.assertNotIn("local_path", text)

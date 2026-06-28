"""Media file storage — local + cloud playback resolution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_persistence import (
    add_uploaded_recording,
    build_media_ami_payload,
    load_media_catalog,
    update_uploaded_recording,
)
from media_state import normalize_uploaded_recordings
from media_storage import (
    PLAYBACK_METADATA_ONLY,
    PLAYBACK_PLAYABLE,
    build_storage_ref,
    delete_recording_files,
    load_recording_audio,
    persist_recording_audio,
    recording_playback_status,
    save_recording_local,
)
from media_upload_catalog import apply_catalog_recording_to_session, register_upload_analysis_in_catalog


class TestMediaStorage(unittest.TestCase):
    def _patch_paths(self, tmp: str):
        root = Path(tmp)

        def _fake_catalog_path(*, st=None):
            return root / "media_catalog.json"

        def _fake_workspace_dir(ws=None):
            d = root / "workspaces" / str(ws or "daniel")
            d.mkdir(parents=True, exist_ok=True)
            return d

        return _fake_catalog_path, _fake_workspace_dir

    def test_persist_creates_local_path_and_storage_ref(self) -> None:
        audio = b"RIFFtest-audio-bytes"
        with tempfile.TemporaryDirectory() as tmp:
            cat_path, ws_dir = self._patch_paths(tmp)
            with patch("media_persistence._local_path", cat_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir(ws) / rel):
                                with patch("media_storage._cloud_storage_enabled", lambda: True):
                                    with patch(
                                        "media_storage.upload_recording_cloud",
                                        lambda ws, rid, data, **kw: (
                                            build_storage_ref("music-media", f"user/{ws}/recordings/{rid}.wav"),
                                            "",
                                        ),
                                    ):
                                        row = add_uploaded_recording(None, {"filename": "take.wav", "song": "Say"})
                                        rid = str(row.get("recording_id"))
                                        store = persist_recording_audio(
                                            None,
                                            rid,
                                            audio,
                                            filename="take.wav",
                                            workspace_id="daniel",
                                        )
                                        self.assertTrue(store.get("local_ok"))
                                        self.assertTrue(store.get("storage_ref"))
                                        update_uploaded_recording(
                                            None,
                                            rid,
                                            {
                                                "local_path": store.get("local_path"),
                                                "storage_ref": store.get("storage_ref"),
                                                "playback_status": store.get("playback_status"),
                                            },
                                        )
                                        catalog = load_media_catalog(st=None)
                                        rec = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])[0]
                                        self.assertTrue(rec.get("local_path"))
                                        self.assertTrue(rec.get("storage_ref"))

    def test_refresh_can_reload_local_audio(self) -> None:
        audio = b"refreshable-audio"
        with tempfile.TemporaryDirectory() as tmp:
            cat_path, ws_dir = self._patch_paths(tmp)
            with patch("media_persistence._local_path", cat_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir(ws) / rel):
                                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                    with patch("media_storage._cloud_storage_enabled", lambda: False):
                                        row = add_uploaded_recording(None, {"filename": "take.wav", "song": "Say"})
                                        rid = str(row.get("recording_id"))
                                        store = persist_recording_audio(None, rid, audio, filename="take.wav")
                                        update_uploaded_recording(
                                            None,
                                            rid,
                                            {"local_path": store.get("local_path"), "storage_ref": store.get("storage_ref")},
                                        )
                                        catalog = load_media_catalog(st=None)
                                        rec = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])[0]
                                        loaded, err = load_recording_audio(rec, st=None)
                                        self.assertEqual(loaded, audio, err)
                                        self.assertEqual(recording_playback_status(rec, st=None), PLAYBACK_PLAYABLE)

    def test_simulated_other_device_downloads_storage_ref(self) -> None:
        audio = b"cross-device-audio"
        storage_ref = build_storage_ref("music-media", "user/daniel/recordings/rec-x.wav")
        with tempfile.TemporaryDirectory() as tmp:
            cat_path, ws_dir = self._patch_paths(tmp)
            with patch("media_persistence._local_path", cat_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir(ws) / rel):
                                row = add_uploaded_recording(
                                    None,
                                    {
                                        "recording_id": "rec-x",
                                        "filename": "take.wav",
                                        "song": "Say",
                                        "workspace_id": "daniel",
                                        "storage_ref": storage_ref,
                                    },
                                )
                                with patch("media_storage.download_recording_cloud", lambda ref: (audio, "")):
                                    with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                        loaded, err = load_recording_audio(row, st=None)
                                    self.assertEqual(loaded, audio, err)

    def test_metadata_only_not_playable(self) -> None:
        rec = {
            "recording_id": "meta-only",
            "filename": "take.wav",
            "workspace_id": "daniel",
            "analysis_summary": {"coach_summary": "No audio"},
        }
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            self.assertEqual(recording_playback_status(rec, st=None), PLAYBACK_METADATA_ONLY)
            session: dict = {}
            ok, _msg = apply_catalog_recording_to_session(session, rec, st=None)
            self.assertTrue(ok)
            self.assertNotIn("last_analysis_audio", session)
            self.assertEqual(session.get("upload_catalog_playback_status"), PLAYBACK_METADATA_ONLY)

    def test_delete_removes_local_file(self) -> None:
        audio = b"delete-me"
        with tempfile.TemporaryDirectory() as tmp:
            _cat_path, ws_dir = self._patch_paths(tmp)
            with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir(ws) / rel):
                rel, err = save_recording_local("daniel", "rec-del", audio, filename="take.wav")
                self.assertFalse(err)
                rec = {"recording_id": "rec-del", "workspace_id": "daniel", "local_path": rel}
                delete_recording_files(rec, st=None)
                path = ws_dir("daniel") / rel
                self.assertFalse(path.is_file())

    def test_register_upload_persists_audio(self) -> None:
        session = {
            "last_analysis_result": {"ok": True, "coach_summary": "Groove", "scores": {"timing": 7}},
            "last_analysis_source_label": "dev_test_upload.wav",
            "last_analysis_audio": b"tiny-wav-bytes",
            "active_song_title": "Say",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cat_path, ws_dir = self._patch_paths(tmp)
            with patch("media_persistence._local_path", cat_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir(ws) / rel):
                                with patch("media_storage._cloud_storage_enabled", lambda: False):
                                    row = register_upload_analysis_in_catalog(session, st=None)
                                    assert row is not None
                                    self.assertTrue(row.get("local_path"))

    def test_ami_payload_excludes_raw_audio(self) -> None:
        catalog = {
            "uploaded_recordings": [
                {
                    "recording_id": "r1",
                    "filename": "take.wav",
                    "song": "Say",
                    "storage_ref": "supabase://music-media/u/ws/rec.wav",
                    "local_path": "media/recordings/r1.wav",
                    "analysis_summary": {"coach_summary": "Good", "scores": {"timing": 8}},
                    "updated_at": "2026-06-28T10:00:00+00:00",
                }
            ],
            "multitrack_sessions": [],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        text = json.dumps(payload)
        self.assertNotIn("supabase://", text)
        self.assertNotIn("local_path", text)
        self.assertIn("coach_summary", text)

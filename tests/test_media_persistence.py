"""Media catalog persistence — local/cloud merge, CRUD, workspace isolation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_persistence import (
    MEDIA_ITEM_KEY,
    MEDIA_ITEM_TYPE,
    add_multitrack_session,
    add_uploaded_recording,
    build_media_ami_payload,
    delete_multitrack_session,
    delete_uploaded_recording,
    load_media_catalog,
    save_media_catalog,
)
from media_state import migrate_multitrack_session, migrate_uploaded_recording, normalize_uploaded_recordings


class TestMediaPersistence(unittest.TestCase):
    def _patches(self, tmp: str, ws: str = "daniel"):
        path = Path(tmp) / "media_catalog.json"

        def _fake_path(*, st=None):
            return path

        def _fake_ws(*, st=None):
            return ws

        return path, _fake_path, _fake_ws

    def test_upload_metadata_save_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path, fake_ws = self._patches(tmp)
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_uploaded_recording(
                                None,
                                {
                                    "filename": "say_take1.wav",
                                    "song": "Say",
                                    "instrument": "Tenor Saxophone",
                                    "duration_seconds": 42,
                                },
                            )
                            self.assertTrue(path.exists())
                            catalog = load_media_catalog(st=None)
                            visible = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])
                            self.assertEqual(len(visible), 1)
                            self.assertEqual(visible[0].get("recording_id"), row.get("recording_id"))
                            self.assertEqual(visible[0].get("song"), "Say")

    def test_multitrack_metadata_save_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path, fake_ws = self._patches(tmp)
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_multitrack_session(
                                None,
                                {
                                    "title": "Say — 2 layers",
                                    "song": "Say",
                                    "instrument": "Tenor Saxophone",
                                    "tracks": [{"name": "Take 1", "slot": "Sax / winds"}],
                                },
                            )
                            catalog = load_media_catalog(st=None)
                            self.assertEqual(len(catalog.get("multitrack_sessions") or []), 1)
                            self.assertEqual(
                                catalog["multitrack_sessions"][0].get("multitrack_id"),
                                row.get("multitrack_id"),
                            )

    def test_phone_dell_merge_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path, fake_ws = self._patches(tmp)
            local = {
                "version": 1,
                "workspace_id": "daniel",
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "local-rec",
                            "song": "Local Song",
                            "updated_at": "2026-06-10T10:00:00+00:00",
                        }
                    )
                ],
                "multitrack_sessions": [],
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(local), encoding="utf-8")

            cloud = {
                "version": 1,
                "workspace_id": "daniel",
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "cloud-rec",
                            "song": "Cloud Song",
                            "updated_at": "2026-06-11T10:00:00+00:00",
                        }
                    )
                ],
                "multitrack_sessions": [
                    migrate_multitrack_session(
                        {
                            "multitrack_id": "cloud-mt",
                            "title": "Cloud MT",
                            "updated_at": "2026-06-11T11:00:00+00:00",
                        }
                    )
                ],
            }

            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: (cloud, None)):
                        catalog = load_media_catalog(st=None)
            rec_ids = {r.get("recording_id") for r in catalog.get("uploaded_recordings") or []}
            mt_ids = {m.get("multitrack_id") for m in catalog.get("multitrack_sessions") or []}
            self.assertIn("local-rec", rec_ids)
            self.assertIn("cloud-rec", rec_ids)
            self.assertIn("cloud-mt", mt_ids)

    def test_empty_cloud_does_not_wipe_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path, fake_ws = self._patches(tmp)
            local = {
                "workspace_id": "daniel",
                "uploaded_recordings": [
                    migrate_uploaded_recording(
                        {
                            "recording_id": "keep-local",
                            "song": "Say",
                            "updated_at": "2026-06-20T10:00:00+00:00",
                        }
                    )
                ],
                "multitrack_sessions": [],
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(local), encoding="utf-8")

            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        catalog = load_media_catalog(st=None)
            visible = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])
            self.assertEqual(len(visible), 1)
            self.assertEqual(visible[0].get("recording_id"), "keep-local")

    def test_delete_upload_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path, fake_ws = self._patches(tmp)
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_uploaded_recording(None, {"filename": "x.wav", "song": "X"})
                            rid = str(row.get("recording_id"))
                            self.assertTrue(delete_uploaded_recording(None, rid))
                            catalog = load_media_catalog(st=None)
                            visible = normalize_uploaded_recordings(catalog.get("uploaded_recordings") or [])
                            self.assertEqual(len(visible), 0)

    def test_delete_multitrack_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path, fake_ws = self._patches(tmp)
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_multitrack_session(None, {"title": "MT", "song": "Say"})
                            mid = str(row.get("multitrack_id"))
                            self.assertTrue(delete_multitrack_session(None, mid))
                            catalog = load_media_catalog(st=None)
                            from media_state import normalize_multitrack_sessions

                            visible = normalize_multitrack_sessions(catalog.get("multitrack_sessions") or [])
                            self.assertEqual(len(visible), 0)

    def test_workspace_isolation_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            daniel_path = Path(tmp) / "daniel" / "media_catalog.json"
            ariel_path = Path(tmp) / "ariel" / "media_catalog.json"

            def _fake_path(*, st=None):
                ws = _fake_ws(st=st)
                return Path(tmp) / ws / "media_catalog.json"

            def _fake_ws(*, st=None):
                return getattr(self, "_ws", "daniel")

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", _fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            self._ws = "daniel"
                            add_uploaded_recording(None, {"song": "Daniel Song", "filename": "d.wav"})
                            self._ws = "ariel"
                            add_uploaded_recording(None, {"song": "Ariel Song", "filename": "a.wav"})
            daniel_data = json.loads(daniel_path.read_text(encoding="utf-8"))
            ariel_data = json.loads(ariel_path.read_text(encoding="utf-8"))
            self.assertEqual(daniel_data.get("workspace_id"), "daniel")
            self.assertEqual(ariel_data.get("workspace_id"), "ariel")
            self.assertNotEqual(
                daniel_data["uploaded_recordings"][0].get("song"),
                ariel_data["uploaded_recordings"][0].get("song"),
            )

    def test_save_writes_cloud_item_type(self) -> None:
        captured: dict = {}

        def _capture_save(catalog, *, st=None):
            captured["payload"] = catalog
            return True, ""

        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path, fake_ws = self._patches(tmp)
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", fake_ws):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", _capture_save):
                            with patch("studio_history_cloud.cloud_enabled", return_value=True):
                                with patch("media_persistence._cloud_authoritative", return_value=True):
                                    save_media_catalog(
                                        {
                                            "uploaded_recordings": [
                                                migrate_uploaded_recording(
                                                    {"recording_id": "r1", "filename": "t.wav"}
                                                )
                                            ],
                                            "multitrack_sessions": [],
                                        },
                                        st=None,
                                    )
        self.assertIn("uploaded_recordings", captured.get("payload") or {})

    def test_build_media_ami_payload_includes_summaries(self) -> None:
        catalog = {
            "uploaded_recordings": [
                migrate_uploaded_recording(
                    {
                        "recording_id": "r1",
                        "song": "Say",
                        "instrument": "Tenor Saxophone",
                        "updated_at": "2026-06-27T10:00:00+00:00",
                        "analysis_summary": {"coach_summary": "Timing in chorus"},
                    }
                )
            ],
            "multitrack_sessions": [
                migrate_multitrack_session(
                    {
                        "multitrack_id": "m1",
                        "title": "Say layers",
                        "song": "Say",
                        "updated_at": "2026-06-27T11:00:00+00:00",
                    }
                )
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        self.assertEqual(len(payload.get("uploaded_recordings") or []), 1)
        self.assertEqual(len(payload.get("multitrack_sessions") or []), 1)
        self.assertIn("Say", payload["uploaded_recordings"][0].get("song") or "")
        ctx = payload.get("recording_analysis_context") or []
        self.assertGreaterEqual(len(ctx), 2)


if __name__ == "__main__":
    unittest.main()

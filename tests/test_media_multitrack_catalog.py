"""Multitrack catalog wiring tests (Step D)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_multitrack_catalog import (
    apply_catalog_multitrack_to_session,
    build_multitrack_catalog_fields,
    catalog_multitrack_row_summary,
    delete_catalog_multitrack_session,
    migrate_legacy_multitrack_history,
    save_multitrack_session_with_notes,
)
from media_persistence import build_media_ami_payload, load_media_catalog
from media_state import is_real_multitrack_track, merge_catalog, normalize_multitrack_sessions, real_multitrack_tracks
from multitrack_history import build_multitrack_history_payload
from multitrack_session_persistence import clear_multitrack_persisted_state, count_mt_layers
from multitrack_slots import MULTITRACK_SLOTS


class TestMediaMultitrackCatalog(unittest.TestCase):
    def _session_with_guitar(self) -> dict:
        return {
            "mt_tracks": {slot: (b"abc" if slot == "Guitar" else None) for slot in MULTITRACK_SLOTS},
            "mt_track_filenames": {"Guitar": "guitar.wav"},
            "mt_name_Guitar": "Lead",
            "mt_vol_Guitar": 0.8,
            "mt_delay_Guitar": 0.1,
            "mt_track_controls": {"Lead": {"volume": 0.8, "mute": True, "solo": False, "delay": 0.1}},
            "mixed_track_wav": b"mix",
            "active_song_title": "Say",
        }

    def test_build_fields_resolves_layer_name_controls(self) -> None:
        fields = build_multitrack_catalog_fields(
            self._session_with_guitar(),
            project_name="Test project",
            song_title="Say",
        )
        self.assertIsNotNone(fields)
        assert fields is not None
        guitar = next(t for t in fields["tracks"] if t.get("slot") == "Guitar")
        self.assertEqual(guitar.get("name"), "Lead")
        summary = guitar.get("analysis_summary") or {}
        self.assertTrue(summary.get("mute"))
        self.assertTrue(summary.get("has_audio"))

    def test_history_payload_uses_layer_name_controls(self) -> None:
        session = self._session_with_guitar()
        payload, err = build_multitrack_history_payload(session, project_name="Test", song_title="Say")
        self.assertFalse(err)
        assert payload is not None
        controls = payload.get("track_controls") or {}
        self.assertIn("Guitar", controls)
        self.assertTrue(controls["Guitar"].get("mute"))

    def test_save_reload_multitrack_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            ok, mid, err = save_multitrack_session_with_notes(
                                self._session_with_guitar(),
                                project_name="Say layers",
                                song_title="Say",
                            )
                            self.assertTrue(ok, err)
                            catalog = load_media_catalog(st=None)
                            visible = normalize_multitrack_sessions(catalog.get("multitrack_sessions") or [])
                            self.assertEqual(len(visible), 1)
                            self.assertEqual(visible[0].get("multitrack_id"), mid)

    def test_phone_dell_merge_multitrack(self) -> None:
        local = {
            "version": 1,
            "uploaded_recordings": [],
            "multitrack_sessions": [
                {
                    "multitrack_id": "phone-mt",
                    "title": "Phone project",
                    "updated_at": "2026-06-01T10:00:00+00:00",
                    "tracks": [],
                }
            ],
        }
        cloud = {
            "version": 1,
            "uploaded_recordings": [],
            "multitrack_sessions": [
                {
                    "multitrack_id": "dell-mt",
                    "title": "Dell project",
                    "updated_at": "2026-06-02T10:00:00+00:00",
                    "tracks": [],
                }
            ],
        }
        merged = merge_catalog(local, cloud)
        ids = {m.get("multitrack_id") for m in merged.get("multitrack_sessions") or []}
        self.assertEqual(ids, {"phone-mt", "dell-mt"})

    def test_delete_tombstone_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            ok, mid, _ = save_multitrack_session_with_notes(
                                self._session_with_guitar(),
                                project_name="Delete me",
                            )
                            self.assertTrue(ok)
                            self.assertTrue(delete_catalog_multitrack_session(mid)[0])
                            visible = normalize_multitrack_sessions(
                                load_media_catalog(st=None).get("multitrack_sessions") or []
                            )
                            self.assertEqual(len(visible), 0)

    def test_clear_all_layers_clears_persist_blob(self) -> None:
        session = self._session_with_guitar()
        session["_mt_tracks_persist_blob"] = {"Guitar": "encoded"}
        session["_studio_page_snapshots"] = {
            "multitrack": {
                "mt_tracks": {"Guitar": "encoded"},
                "mixed_track_wav": b"mix",
            }
        }
        clear_multitrack_persisted_state(session)
        self.assertEqual(count_mt_layers(session.get("mt_tracks")), 0)
        self.assertIsNone(session.get("mixed_track_wav"))
        self.assertNotIn("_mt_tracks_persist_blob", session)
        snap = session["_studio_page_snapshots"]["multitrack"]
        self.assertEqual(count_mt_layers(snap.get("mt_tracks")), 0)

    def test_apply_catalog_metadata_to_session(self) -> None:
        fields = build_multitrack_catalog_fields(
            self._session_with_guitar(),
            project_name="Restore test",
            song_title="Say",
        )
        assert fields is not None
        fresh: dict = {"mt_tracks": {slot: None for slot in MULTITRACK_SLOTS}}
        ok, _msg = apply_catalog_multitrack_to_session(
            fresh,
            {**fields, "multitrack_id": "mt-1", "workspace_id": "daniel"},
            load_audio=False,
        )
        self.assertTrue(ok)
        self.assertEqual(fresh.get("mt_name_Guitar"), "Lead")
        self.assertIsNone(fresh.get("mt_tracks", {}).get("Guitar"))

    def test_save_persists_track_storage_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"
            root = Path(tmp)

            def _fake_path(*, st=None):
                return path

            def _fake_ws_dir(ws=None):
                d = root / "workspaces" / str(ws or "daniel")
                d.mkdir(parents=True, exist_ok=True)
                return d

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage.recording_local_abs_path", lambda ws, rel: _fake_ws_dir(ws) / rel):
                                with patch("media_storage._cloud_storage_enabled", lambda: False):
                                    ok, mid, err = save_multitrack_session_with_notes(
                                        self._session_with_guitar(),
                                        project_name="Persist tracks",
                                        song_title="Say",
                                    )
                                    self.assertTrue(ok, err)
                                    visible = normalize_multitrack_sessions(
                                        load_media_catalog(st=None).get("multitrack_sessions") or []
                                    )
                                    guitar = next(
                                        t for t in visible[0].get("tracks") or [] if t.get("slot") == "Guitar"
                                    )
                                    self.assertTrue(guitar.get("local_path"))
                                    self.assertEqual(guitar.get("playback_status"), "playable")

    def test_lazy_load_resolves_track_from_storage_ref(self) -> None:
        audio = b"guitar-track-bytes"
        storage_ref = "supabase://music-media/user/daniel/multitrack/mt-1/track-1.wav"
        session = {
            "multitrack_id": "mt-1",
            "workspace_id": "daniel",
            "title": "Test",
            "tracks": [
                {
                    "track_id": "track-1",
                    "slot": "Guitar",
                    "name": "Lead",
                    "storage_ref": storage_ref,
                    "local_path": "media/multitrack/mt-1/track-1.wav",
                    "playback_status": "playable",
                    "analysis_summary": {"has_audio": True, "volume": 1.0, "delay": 0.0},
                }
            ],
            "track_controls": {"Guitar": {"volume": 1.0, "delay": 0.0, "mute": False, "solo": False}},
        }
        fresh: dict = {"mt_tracks": {slot: None for slot in MULTITRACK_SLOTS}}
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            with patch("media_storage._cloud_storage_enabled", lambda: True):
                with patch("media_storage.download_recording_cloud", lambda ref, st=None: (audio, "")):
                    with patch("media_storage._track_local_exists", lambda ws, rel: False):
                        ok, msg = apply_catalog_multitrack_to_session(fresh, session, st=None, load_audio=True)
                        self.assertTrue(ok, msg)
                        self.assertEqual(fresh["mt_tracks"]["Guitar"], audio)

    def test_migrate_legacy_multitrack_history(self) -> None:
        legacy_rows = [
            {
                "item_key": "mt_20260601_abcd",
                "title": "Legacy MT",
                "payload": {
                    "workspace_id": "daniel",
                    "saved_at": "2026-06-01T10:00:00+00:00",
                    "project_name": "Legacy project",
                    "song_title": "Say",
                    "tracks": [
                        {
                            "slot": "Guitar",
                            "layer_name": "Lead",
                            "filename": "g.wav",
                            "has_audio": True,
                            "volume": 1.0,
                            "delay": 0.0,
                        }
                    ],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            ss: dict = {}
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch(
                                "media_multitrack_catalog.list_multitrack_history",
                                return_value=(legacy_rows, None),
                            ):
                                count = migrate_legacy_multitrack_history(st=ss)
                                self.assertEqual(count, 1)
                                visible = normalize_multitrack_sessions(
                                    load_media_catalog(st=ss).get("multitrack_sessions") or []
                                )
                                self.assertEqual(len(visible), 1)
                                self.assertEqual(visible[0].get("song"), "Say")

    def test_row_summary_ignores_empty_slots(self) -> None:
        session = {
            "multitrack_id": "mt-1",
            "title": "Trial 1",
            "song": "Say",
            "workspace_id": "daniel",
            "tracks": [
                {
                    "track_id": "t1",
                    "slot": "Guitar",
                    "name": "Guitar",
                    "storage_ref": "supabase://music-media/u/ws/mt/t1.wav",
                    "local_path": "media/multitrack/mt/t1.wav",
                    "playback_status": "playable",
                    "analysis_summary": {"has_audio": True},
                },
                {
                    "track_id": "t2",
                    "slot": "Piano / Keys",
                    "name": "Piano",
                    "storage_ref": "supabase://music-media/u/ws/mt/t2.wav",
                    "local_path": "media/multitrack/mt/t2.wav",
                    "playback_status": "playable",
                    "analysis_summary": {"has_audio": True},
                },
                {"track_id": "e1", "slot": "Bass", "name": "Bass", "analysis_summary": {"has_audio": False}},
                {"track_id": "e2", "slot": "Vocals", "name": "Vocals", "analysis_summary": {"has_audio": False}},
                {"track_id": "e3", "slot": "Sax / winds", "name": "Sax / winds", "analysis_summary": {"has_audio": False}},
                {"track_id": "e4", "slot": "Extra layer", "name": "Extra layer", "analysis_summary": {"has_audio": False}},
            ],
        }
        row = {"title": "Trial 1", "payload": session}
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            with patch("media_storage._cloud_storage_enabled", lambda: True):
                with patch("media_storage._track_local_exists", lambda ws, rel: True):
                    summary = catalog_multitrack_row_summary(row)
        self.assertIn("2 playable", summary)
        self.assertNotIn("metadata-only", summary)
        self.assertEqual(len(real_multitrack_tracks(session["tracks"])), 2)

    def test_row_summary_counts_real_metadata_only(self) -> None:
        session = {
            "multitrack_id": "mt-2",
            "title": "Mixed",
            "song": "Say",
            "workspace_id": "daniel",
            "tracks": [
                {
                    "track_id": "t1",
                    "slot": "Guitar",
                    "storage_ref": "supabase://music-media/u/ws/mt/t1.wav",
                    "local_path": "media/multitrack/mt/t1.wav",
                    "playback_status": "playable",
                    "analysis_summary": {"has_audio": True},
                },
                {
                    "track_id": "t2",
                    "slot": "Bass",
                    "analysis_summary": {"has_audio": True},
                    "playback_status": "metadata_only",
                },
            ],
        }
        row = {"title": "Mixed", "payload": session}
        with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
            with patch("media_storage._cloud_storage_enabled", lambda: True):
                with patch("media_storage._track_local_exists", lambda ws, rel: "t1" in rel):
                    summary = catalog_multitrack_row_summary(row)
        self.assertIn("1 playable", summary)
        self.assertIn("1 metadata-only", summary)

    def test_ami_payload_excludes_empty_slot_tracks(self) -> None:
        import json

        catalog = {
            "uploaded_recordings": [],
            "multitrack_sessions": [
                {
                    "multitrack_id": "m1",
                    "title": "Trial 1",
                    "song": "Say",
                    "updated_at": "2026-06-28T10:00:00+00:00",
                    "tracks": [
                        {
                            "track_id": "t1",
                            "slot": "Guitar",
                            "name": "Guitar",
                            "storage_ref": "supabase://music-media/u/ws/m1/t1.wav",
                            "analysis_summary": {"has_audio": True},
                        },
                        {"track_id": "e1", "slot": "Bass", "name": "Bass", "analysis_summary": {"has_audio": False}},
                    ],
                }
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        mt = (payload.get("multitrack_sessions") or [])[0]
        self.assertEqual(mt.get("track_count"), 1)
        text = json.dumps(payload)
        self.assertNotIn("Bass", text)
        self.assertFalse(is_real_multitrack_track({"slot": "Bass", "analysis_summary": {"has_audio": False}}))

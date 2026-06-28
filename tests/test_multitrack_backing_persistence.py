"""Multitrack backing level + catalog persistence tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_multitrack_catalog import (
    apply_catalog_multitrack_to_session,
    apply_multitrack_backing_fields,
    build_multitrack_catalog_fields,
    catalog_multitrack_row_summary,
    gather_multitrack_backing_fields,
    list_catalog_multitrack_sessions,
    persist_prepared_multitrack_backing,
    resolve_multitrack_backing_bytes,
    save_multitrack_session_with_notes,
    seed_multitrack_backing_volume,
)
from media_persistence import build_media_ami_payload, load_media_catalog
from media_state import migrate_multitrack_session
from media_storage import PLAYBACK_METADATA_ONLY, backing_media_relpath
from multitrack_slots import MULTITRACK_SLOTS
from studio_page_persistence import apply_page_snapshot, capture_page_snapshot, restore_page_snapshot


class TestMultitrackBackingPersistence(unittest.TestCase):
    def _session_with_layers(self) -> dict:
        return {
            "mt_tracks": {slot: (b"layer" if slot == "Guitar" else None) for slot in MULTITRACK_SLOTS},
            "mt_track_filenames": {"Guitar": "guitar.wav"},
            "mt_name_Guitar": "Lead",
            "mt_vol_Guitar": 0.8,
            "mt_delay_Guitar": 0.0,
            "mt_track_controls": {"Guitar": {"volume": 0.8, "mute": False, "solo": False, "delay": 0.0}},
            "active_song_title": "Say",
            "mt_backing_volume": 1.1,
            "mt_playback_scope": "Full song",
            "multitrack_bpm": 96,
            "mt_section_loops": 3,
            "mt_groove_style": "Rock groove",
            "mt_time_signature": "4/4",
            "mt_count_in_bars": "2 bars",
            "mt_use_backing_monitor": True,
            "include_backing_mix": True,
            "multitrack_backing_music_wav": b"backing-wav-bytes",
            "mt_backing_prepared_at": "2026-06-28T10:00:00+00:00",
            "mt_backing_scope": "full song",
        }

    def test_mt_backing_volume_isolated_from_backing_page_key(self) -> None:
        session = {"backing_volume": 0.75, "mt_backing_volume": 1.2}
        fields = gather_multitrack_backing_fields(session)
        self.assertEqual(fields["backing_volume"], 1.2)

    def test_seed_multitrack_backing_volume_does_not_clobber_existing(self) -> None:
        session = {"mt_backing_volume": 0.4}
        seed_multitrack_backing_volume(session)
        self.assertEqual(session["mt_backing_volume"], 0.4)

    def test_seed_multitrack_backing_volume_migrates_legacy_key_once(self) -> None:
        session = {"backing_volume": 0.9}
        seed_multitrack_backing_volume(session)
        self.assertEqual(session["mt_backing_volume"], 0.9)

    def test_backing_fields_in_catalog_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._session_with_layers()
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch(
                                "media_multitrack_catalog.persist_backing_audio",
                                lambda st, mid, audio, **kw: {
                                    "ok": True,
                                    "local_path": f"media/multitrack/{mid}/backing.wav",
                                    "storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
                                    "playback_status": "playable",
                                },
                            ):
                                ok, mid, err = save_multitrack_session_with_notes(
                                    session,
                                    project_name="Say layers",
                                    song_title="Say",
                                )
                                self.assertTrue(ok, err)
                                catalog = load_media_catalog(st=None)
                                row = migrate_multitrack_session(catalog["multitrack_sessions"][0])
                                self.assertEqual(row["backing_volume"], 1.1)
                                self.assertEqual(row["backing_loops"], 3)
                                self.assertEqual(row["backing_groove"], "Rock groove")
                                self.assertTrue(row.get("backing_storage_ref"))
                                self.assertTrue(row.get("backing_local_path"))
                                self.assertEqual(row.get("backing_playback_status"), "playable")
                                self.assertEqual(row.get("backing_prepared_at"), session["mt_backing_prepared_at"])

    def test_reload_restores_backing_level_and_audio(self) -> None:
        session: dict = {}
        row = migrate_multitrack_session(
            {
                "multitrack_id": "m1",
                "title": "Say layers",
                "song": "Say",
                "bpm": 96,
                "backing_volume": 1.25,
                "backing_scope": "Full song",
                "backing_loops": 2,
                "backing_groove": "Pop groove",
                "backing_meter": "4/4",
                "backing_count_in_bars": 1,
                "backing_prepared_at": "2026-06-28T10:00:00+00:00",
                "backing_storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
                "backing_local_path": "media/multitrack/m1/backing.wav",
                "tracks": [
                    {
                        "track_id": "t1",
                        "slot": "Guitar",
                        "name": "Lead",
                        "storage_ref": "supabase://music-media/u/ws/m1/t1.wav",
                        "local_path": "media/multitrack/m1/t1.wav",
                        "analysis_summary": {"has_audio": True, "volume": 1.0},
                    }
                ],
            }
        )
        with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (b"layer", "")):
            with patch("media_multitrack_catalog.load_backing_audio", lambda session, st=None: (b"backing-wav", "")):
                ok, msg = apply_catalog_multitrack_to_session(session, row, load_audio=True)
                self.assertTrue(ok, msg)
                self.assertEqual(session["mt_backing_volume"], 1.25)
                self.assertEqual(session["multitrack_bpm"], 96)
                self.assertEqual(session["multitrack_backing_music_wav"], b"backing-wav")
                self.assertEqual(session.get("_mt_backing_playback_status"), "playable")
                self.assertEqual(session.get("_mt_backing_bytes_in_session"), len(b"backing-wav"))

    def test_settings_only_backing_shows_metadata_status(self) -> None:
        session: dict = {}
        row = migrate_multitrack_session(
            {
                "multitrack_id": "m1",
                "title": "Say layers",
                "backing_prepared_at": "2026-06-28T10:00:00+00:00",
                "backing_volume": 0.8,
                "tracks": [
                    {
                        "track_id": "t1",
                        "slot": "Guitar",
                        "name": "Lead",
                        "analysis_summary": {"has_audio": True},
                    }
                ],
            }
        )
        with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (None, "metadata_only")):
            ok, msg = apply_catalog_multitrack_to_session(session, row, load_audio=True)
            self.assertTrue(ok, msg)
            self.assertNotIn("multitrack_backing_music_wav", session)
            self.assertEqual(session.get("_mt_backing_playback_status"), PLAYBACK_METADATA_ONLY)
            self.assertEqual(session.get("_mt_backing_load_error"), "no_backing_ref")

    def test_missing_backing_blob_reports_download_error(self) -> None:
        session: dict = {}
        row = migrate_multitrack_session(
            {
                "multitrack_id": "m1",
                "backing_storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
                "backing_prepared_at": "2026-06-28T10:00:00+00:00",
                "tracks": [
                    {
                        "track_id": "t1",
                        "slot": "Guitar",
                        "name": "Lead",
                        "analysis_summary": {"has_audio": True},
                    }
                ],
            }
        )
        with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (None, "metadata_only")):
            with patch("media_multitrack_catalog.load_backing_audio", lambda session, st=None: (None, "missing_file")):
                ok, _msg = apply_catalog_multitrack_to_session(session, row, load_audio=True)
                self.assertTrue(ok)
                self.assertIsNone(session.get("multitrack_backing_music_wav"))
                self.assertEqual(session.get("_mt_backing_load_error"), "missing_file")

    def test_resolve_backing_bytes_from_local_disk_when_session_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = "daniel"
            mid = "m-local"
            rel = backing_media_relpath(mid)
            path = Path(tmp) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"disk-backing")
            with patch("media_multitrack_catalog.recording_local_abs_path", lambda workspace_id, rel_path: Path(tmp) / rel_path):
                session: dict = {}
                resolved = resolve_multitrack_backing_bytes(session, mid, workspace_id=ws)
                self.assertEqual(resolved, b"disk-backing")
                self.assertEqual(session.get("multitrack_backing_music_wav"), b"disk-backing")

    def test_snapshot_restore_does_not_clobber_live_backing_wav(self) -> None:
        session = self._session_with_layers()
        session["studio_page"] = "multitrack"
        snap = capture_page_snapshot({**session, "multitrack_backing_music_wav": None}, "multitrack")
        session["multitrack_backing_music_wav"] = b"fresh-backing"
        apply_page_snapshot(session, snap)
        self.assertEqual(session["multitrack_backing_music_wav"], b"fresh-backing")

    def test_list_catalog_does_not_load_backing_audio(self) -> None:
        with patch("media_multitrack_catalog.load_backing_audio") as load_mock:
            with patch("media_multitrack_catalog.migrate_legacy_multitrack_history", lambda *, st=None: 0):
                with patch("media_persistence.load_media_catalog", lambda *, st=None: {"multitrack_sessions": [], "uploaded_recordings": []}):
                    rows, err = list_catalog_multitrack_sessions(st=None)
                    self.assertIsNone(err)
                    self.assertEqual(rows, [])
                    load_mock.assert_not_called()

    def test_metadata_only_project_summary(self) -> None:
        row = {
            "payload": {
                "title": "Say layers",
                "backing_prepared_at": "2026-06-28T10:00:00+00:00",
                "backing_playback_status": PLAYBACK_METADATA_ONLY,
                "tracks": [
                    {
                        "slot": "Guitar",
                        "analysis_summary": {"has_audio": True},
                    }
                ],
            }
        }
        summary = catalog_multitrack_row_summary(row)
        self.assertIn("backing metadata-only", summary)

    def test_second_device_loads_same_backing_ref(self) -> None:
        row = {
            "multitrack_id": "m1",
            "workspace_id": "daniel",
            "backing_storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
            "backing_volume": 0.55,
            "tracks": [
                {
                    "track_id": "t1",
                    "slot": "Guitar",
                    "name": "Lead",
                    "analysis_summary": {"has_audio": True},
                }
            ],
        }
        phone: dict = {}
        with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (None, "metadata_only")):
            with patch("media_multitrack_catalog.load_backing_audio", lambda session, st=None: (b"cloud-backing", "")):
                ok, _msg = apply_catalog_multitrack_to_session(phone, row, load_audio=True)
                self.assertTrue(ok)
                self.assertEqual(phone["mt_backing_volume"], 0.55)
                self.assertEqual(phone["multitrack_backing_music_wav"], b"cloud-backing")

    def test_prepare_backing_updates_active_project_not_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._session_with_layers()
            session["_last_catalog_multitrack_id"] = "m-existing"
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            catalog = load_media_catalog(st=None)
                            catalog["multitrack_sessions"] = [
                                {
                                    "multitrack_id": "m-existing",
                                    "title": "Say layers",
                                    "updated_at": "2026-06-27T10:00:00+00:00",
                                    "tracks": [],
                                }
                            ]
                            from media_persistence import save_media_catalog

                            save_media_catalog(catalog, st=None)
                            with patch(
                                "media_multitrack_catalog.persist_backing_audio",
                                lambda st, mid, audio, **kw: {
                                    "ok": True,
                                    "local_path": f"media/multitrack/{mid}/backing.wav",
                                    "storage_ref": "supabase://music-media/u/ws/m-existing/backing.wav",
                                    "playback_status": "playable",
                                },
                            ):
                                ok, msg = persist_prepared_multitrack_backing(
                                    session,
                                    b"new-backing",
                                    st=None,
                                    scope_label="full song",
                                )
                                self.assertTrue(ok, msg)
                                self.assertEqual(msg, "updated_project")
                                updated = load_media_catalog(st=None)
                                rows = updated["multitrack_sessions"]
                                self.assertEqual(len(rows), 1)
                                self.assertEqual(rows[0]["multitrack_id"], "m-existing")
                                self.assertEqual(rows[0]["backing_volume"], 1.1)
                                self.assertTrue(rows[0].get("backing_prepared_at"))

    def test_page_snapshot_persists_mt_backing_volume(self) -> None:
        session = self._session_with_layers()
        session["studio_page"] = "multitrack"
        snap = capture_page_snapshot(session, "multitrack")
        self.assertIn("mt_backing_volume", snap)
        self.assertEqual(snap["mt_backing_volume"], 1.1)

        fresh: dict = {"studio_page": "multitrack", "_studio_page_snapshots": {"multitrack": snap}}
        from studio_page_persistence import restore_page_snapshot

        restore_page_snapshot(fresh, "multitrack")
        self.assertEqual(fresh["mt_backing_volume"], 1.1)

    def test_project_library_summary_shows_backing(self) -> None:
        row = {
            "payload": {
                "title": "Say layers",
                "song": "Say",
                "backing_storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
                "tracks": [
                    {
                        "slot": "Guitar",
                        "storage_ref": "supabase://music-media/u/ws/m1/t1.wav",
                        "analysis_summary": {"has_audio": True},
                    }
                ],
            }
        }
        summary = catalog_multitrack_row_summary(row)
        self.assertIn("backing ready", summary)

    def test_ami_payload_excludes_backing_blob_paths(self) -> None:
        catalog = {
            "uploaded_recordings": [],
            "multitrack_sessions": [
                {
                    "multitrack_id": "m1",
                    "title": "Say layers",
                    "updated_at": "2026-06-28T10:00:00+00:00",
                    "backing_storage_ref": "supabase://music-media/u/ws/m1/backing.wav",
                    "backing_local_path": "media/multitrack/m1/backing.wav",
                    "tracks": [],
                }
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        text = json.dumps(payload)
        self.assertNotIn("supabase://", text)
        self.assertNotIn("backing_local_path", text)

    def test_save_without_session_wav_uses_local_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"
            session = self._session_with_layers()
            session.pop("multitrack_backing_music_wav")

            def _fake_path(*, st=None):
                return path

            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch(
                                "media_multitrack_catalog.resolve_multitrack_backing_bytes",
                                return_value=b"disk-save-backing",
                            ):
                                with patch(
                                    "media_multitrack_catalog.persist_backing_audio",
                                    MagicMock(
                                        return_value={
                                            "ok": True,
                                            "local_path": "media/multitrack/m1/backing.wav",
                                            "storage_ref": "supabase://music-media/u/daniel/m1/backing.wav",
                                            "playback_status": "playable",
                                            "cloud_ok": True,
                                        }
                                    ),
                                ) as persist_mock:
                                    ok, saved_mid, err = save_multitrack_session_with_notes(
                                        session,
                                        project_name="Disk backing",
                                        song_title="Say",
                                    )
                                    self.assertTrue(ok, err)
                                    persist_mock.assert_called_once()
                                    self.assertEqual(persist_mock.call_args.args[2], b"disk-save-backing")

    def test_apply_backing_fields_before_widgets(self) -> None:
        session: dict = {}
        apply_multitrack_backing_fields(
            session,
            {
                "backing_volume": 0.35,
                "backing_scope": "Single section (verse, chorus, solo, …)",
                "backing_single_section": "Verse 1",
                "backing_loops": 4,
                "backing_groove": "Ballad",
                "backing_count_in_bars": 2,
                "bpm": 88,
            },
        )
        self.assertEqual(session["mt_backing_volume"], 0.35)
        self.assertEqual(session["mt_single_section"], "Verse 1")
        self.assertEqual(session["mt_section_loops"], 4)
        self.assertEqual(session["multitrack_bpm"], 88)


if __name__ == "__main__":
    unittest.main()

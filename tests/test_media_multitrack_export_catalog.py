"""Multitrack Export Library — save, list, delete, AMI, upload analysis handoff."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from media_persistence import add_multitrack_export, delete_multitrack_export, load_media_catalog
from media_state import compact_multitrack_export_for_ami, migrate_multitrack_export
from media_multitrack_export_catalog import (
    build_multitrack_export_fields,
    delete_multitrack_export_entry,
    export_row_summary,
    list_multitrack_exports,
    load_export_for_playback,
    save_multitrack_export_from_session,
    send_export_to_upload_analysis,
    suggest_export_name,
)
from media_storage import PLAYBACK_PLAYABLE


def _fake_catalog_path(tmp: str):
    path = Path(tmp) / "media_catalog.json"

    def _fake_path(*, st=None):
        return path

    return path, _fake_path


def _sample_wav_bytes(*, duration_sec: float = 1.0, rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    nframes = int(rate * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


class TestMultitrackExportCatalog(unittest.TestCase):
    def test_save_export_creates_record_with_timestamp(self) -> None:
        session: dict = {"active_song_title": "Say", "instrument": "Alto Saxophone"}
        audio = _sample_wav_bytes(duration_sec=1.14)
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path = _fake_catalog_path(tmp)
            ws_dir = Path(tmp) / "daniel"
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel):
                                    with patch("media_storage.upload_mix_export_cloud", lambda *a, **k: ("", "cloud_disabled")):
                                        ok, eid, err = save_multitrack_export_from_session(
                                            session,
                                            audio,
                                            export_name="Say mix v2",
                                            song_title="Say",
                                            track_items=[{"slot": "Layer 1", "name": "Sax", "volume": 1.0}],
                                            st=None,
                                        )
                                        self.assertTrue(ok, err)
                                        self.assertTrue(eid)
                                        catalog = json.loads(path.read_text(encoding="utf-8"))
                                        row = next(r for r in catalog["multitrack_exports"] if r["export_id"] == eid)
                                        self.assertTrue(str(row.get("created_at") or "").strip())
                                        self.assertEqual(row.get("export_name"), "Say mix v2")
                                        self.assertEqual(row.get("song"), "Say")

    def test_saved_export_stores_storage_ref_not_blob(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path = _fake_catalog_path(tmp)
            ws_dir = Path(tmp) / "daniel"
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel):
                                    with patch("media_storage.upload_mix_export_cloud", lambda *a, **k: ("", "cloud_disabled")):
                                        ok, eid, _ = save_multitrack_export_from_session(session, audio, st=None)
            self.assertTrue(ok)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("audio_b64", text)
            self.assertNotIn("blob", text.lower())
            row = json.loads(text)["multitrack_exports"][0]
            self.assertTrue(row.get("local_path"))

    def test_list_exports_excludes_deleted(self) -> None:
        catalog = {
            "multitrack_exports": [
                migrate_multitrack_export({"export_id": "e1", "export_name": "A", "song": "Say"}),
                migrate_multitrack_export({"export_id": "e2", "export_name": "B", "deleted": True}),
            ]
        }
        with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_multitrack_exports(st=None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("export_id"), "e1")

    def test_row_summary_compact_format(self) -> None:
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Say mix v2",
                "song": "Say",
                "track_count": 2,
                "duration_seconds": 74,
                "format": "wav",
                "created_at": "2026-06-28T21:42:00+00:00",
            }
        )
        summary = export_row_summary(row)
        self.assertIn("Say mix v2", summary)
        self.assertIn("2 tracks", summary)
        self.assertIn("1:14", summary)
        self.assertIn("WAV", summary)
        self.assertNotIn("Say · Say", summary)

    def test_multiple_exports_same_project_allowed(self) -> None:
        catalog = {
            "multitrack_exports": [
                migrate_multitrack_export({"export_id": "e1", "multitrack_id": "p1", "export_name": "v1"}),
                migrate_multitrack_export({"export_id": "e2", "multitrack_id": "p1", "export_name": "v2"}),
            ]
        }
        with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_multitrack_exports(st=None, multitrack_id="p1")
        self.assertEqual(len(rows), 2)

    def test_delete_tombstones_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path = _fake_catalog_path(tmp)
            row = migrate_multitrack_export({"export_id": "del1", "export_name": "X"})
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_multitrack_export(None, row)
                            eid = str(row.get("export_id") or "")
                            self.assertTrue(delete_multitrack_export(None, eid))
                            catalog = load_media_catalog(st=None)
                            visible = list_multitrack_exports(st=None)
                            self.assertEqual(len(visible), 0)

    def test_load_export_resolves_storage_lazy(self) -> None:
        audio = _sample_wav_bytes()
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Test",
                "local_path": "media/multitrack_exports/e1.wav",
                "playback_status": PLAYBACK_PLAYABLE,
            }
        )
        catalog = {"multitrack_exports": [row]}
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = Path(tmp) / "daniel" / "media" / "multitrack_exports"
            ws_dir.mkdir(parents=True)
            (ws_dir / "e1.wav").write_bytes(audio)
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        data, err, _ = load_export_for_playback("e1", st=None)
            self.assertTrue(data)
            self.assertFalse(err)

    def test_send_to_upload_analysis_sets_session_metadata(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Say mix",
                "song": "Say",
                "track_count": 2,
                "local_path": "media/multitrack_exports/e1.wav",
            }
        )
        catalog = {"multitrack_exports": [row]}
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = Path(tmp) / "daniel" / "media" / "multitrack_exports"
            ws_dir.mkdir(parents=True)
            (ws_dir / "e1.wav").write_bytes(audio)
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        ok, err = send_export_to_upload_analysis(session, "e1", st=None)
        self.assertTrue(ok, err)
        self.assertEqual(session.get("analysis_recording_type"), "Multitrack mix export")
        self.assertTrue(session.get("last_analysis_audio"))
        pending = session.get("_pending_multitrack_export_analysis") or {}
        self.assertEqual(pending.get("source"), "multitrack_export")
        self.assertEqual(pending.get("export_id"), "e1")

    def test_ami_compact_excludes_raw_audio(self) -> None:
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Mix",
                "local_path": "media/multitrack_exports/e1.wav",
                "storage_ref": "supabase://bucket/key.wav",
            }
        )
        compact = compact_multitrack_export_for_ami(row)
        text = json.dumps(compact)
        self.assertNotIn("audio_b64", text)
        self.assertNotIn("blob", text)
        self.assertEqual(compact.get("source"), "multitrack_export")
        self.assertTrue(compact.get("audio_available"))

    def test_build_fields_target_equals_written_for_transposing_not_applicable(self) -> None:
        fields = build_multitrack_export_fields(
            {"active_song_title": "Say"},
            _sample_wav_bytes(),
            track_items=[{"slot": "L1", "name": "Lead"}],
        )
        self.assertEqual(fields.get("track_count"), 1)
        self.assertEqual(fields.get("format"), "wav")
        self.assertIsNotNone(fields.get("duration_seconds"))

    def test_suggest_export_name_uses_song(self) -> None:
        name = suggest_export_name(song_title="Say")
        self.assertIn("Say mix", name)

    def test_step4_still_has_direct_download_button(self) -> None:
        app_source = open(
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py",
            encoding="utf-8",
        ).read()
        ui_source = open(
            Path(__file__).resolve().parents[1] / "multitrack_export_ui.py",
            encoding="utf-8",
        ).read()
        self.assertIn("Download mixed track WAV", app_source)
        self.assertIn("Save Export", ui_source)
        self.assertIn("render_multitrack_export_library", app_source)

    def test_deleted_export_excluded_from_ami_compact(self) -> None:
        tomb = migrate_multitrack_export({"export_id": "e1", "deleted": True})
        self.assertEqual(compact_multitrack_export_for_ami(tomb), {})


if __name__ == "__main__":
    unittest.main()

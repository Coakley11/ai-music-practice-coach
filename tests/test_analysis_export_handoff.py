"""Multitrack export → Upload Analysis handoff."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from media_multitrack_export_catalog import (
    ANALYSIS_EXPORT_AUDIO_SIG_KEY,
    ANALYSIS_EXPORT_HANDOFF_META_KEY,
    ANALYSIS_EXPORT_LOADED_LABEL_KEY,
    ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX,
    PENDING_EXPORT_ANALYSIS_KEY,
    analysis_export_handoff_ready,
    apply_pending_multitrack_export_analysis,
    loaded_multitrack_export_analysis_banner,
    replace_upload_analysis_with_multitrack_export,
    resolve_upload_analysis_audio_bytes,
    resolve_upload_analysis_prepared_upload,
    send_export_to_upload_analysis,
)
from media_state import compact_multitrack_export_for_ami, migrate_multitrack_export
from media_storage import PLAYBACK_PLAYABLE
from upload_media import PreparedUpload


def _sample_wav_bytes(*, duration_sec: float = 0.05, rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    nframes = max(1, int(rate * duration_sec))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def _catalog_fixture(tmp: str, row: dict, audio: bytes) -> dict:
    ws_dir = Path(tmp) / "daniel" / "media" / "multitrack_exports"
    ws_dir.mkdir(parents=True)
    eid = str(row.get("export_id") or "e1")
    (ws_dir / f"{eid}.wav").write_bytes(audio)
    return {"multitrack_exports": [migrate_multitrack_export(row)]}


class TestAnalysisExportHandoff(unittest.TestCase):
    def test_send_then_apply_sets_upload_analysis_contract(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        row = {
            "export_id": "e1",
            "export_name": "Say mix v2",
            "song": "Say",
            "track_count": 2,
            "duration_seconds": 74,
            "format": "wav",
            "local_path": "media/multitrack_exports/e1.wav",
            "playback_status": PLAYBACK_PLAYABLE,
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog = _catalog_fixture(tmp, row, audio)
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        ok, err = send_export_to_upload_analysis(session, "e1", st=None)
                        self.assertTrue(ok, err)
                        self.assertIn(PENDING_EXPORT_ANALYSIS_KEY, session)
                        pending = session[PENDING_EXPORT_ANALYSIS_KEY]
                        self.assertEqual(pending.get("source"), "multitrack_export")
                        self.assertEqual(pending.get("export_id"), "e1")
                        self.assertTrue(session.get("_analysis_prepared_upload"))
                        self.assertEqual(bytes(session["last_analysis_audio"]), audio)

                        ok_apply, err_apply = apply_pending_multitrack_export_analysis(session)
                        self.assertTrue(ok_apply, err_apply)
        self.assertNotIn(PENDING_EXPORT_ANALYSIS_KEY, session)
        self.assertEqual(session.get("analysis_mode"), "Single recording")
        self.assertEqual(session.get("analysis_recording_type"), ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX)
        self.assertIn("Say mix v2", loaded_multitrack_export_analysis_banner(session))
        self.assertTrue(analysis_export_handoff_ready(session))

    def test_export_b_replaces_stale_export_a_audio(self) -> None:
        audio_a = _sample_wav_bytes(duration_sec=0.05)
        audio_b = _sample_wav_bytes(duration_sec=0.12)
        session: dict = {
            "last_analysis_audio": audio_a,
            "_analysis_prepared_upload": PreparedUpload(audio_a, "old_upload.wav"),
            "_analysis_upload_prep_sig": ("old", "old_upload.wav"),
            ANALYSIS_EXPORT_LOADED_LABEL_KEY: "Loaded from Multitrack Export: old export.wav",
        }
        meta_b = {
            "source": "multitrack_export",
            "export_id": "e2",
            "export_name": "say export1",
            "song_title": "Say",
            "format": "wav",
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog = _catalog_fixture(
                tmp,
                {
                    "export_id": "e2",
                    "export_name": "say export1",
                    "song": "Say",
                    "local_path": "media/multitrack_exports/e2.wav",
                    "playback_status": PLAYBACK_PLAYABLE,
                },
                audio_b,
            )
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        ok, err = send_export_to_upload_analysis(session, "e2", st=None)
        self.assertTrue(ok, err)
        prepared = resolve_upload_analysis_prepared_upload(session)
        self.assertIsNotNone(prepared)
        self.assertEqual(bytes(prepared.getvalue()), audio_b)
        self.assertNotEqual(bytes(prepared.getvalue()), audio_a)
        self.assertIn("say export1", loaded_multitrack_export_analysis_banner(session))
        self.assertTrue(analysis_export_handoff_ready(session))

    def test_apply_pending_ignores_stale_last_analysis_audio(self) -> None:
        audio_export = _sample_wav_bytes(duration_sec=0.07)
        stale_audio = _sample_wav_bytes(duration_sec=0.03)
        session = {
            PENDING_EXPORT_ANALYSIS_KEY: {
                "source": "multitrack_export",
                "export_id": "e1",
                "export_name": "say export1",
                "song_title": "Say",
            },
            "last_analysis_audio": stale_audio,
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog = _catalog_fixture(
                tmp,
                {
                    "export_id": "e1",
                    "export_name": "say export1",
                    "local_path": "media/multitrack_exports/e1.wav",
                    "playback_status": PLAYBACK_PLAYABLE,
                },
                audio_export,
            )
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        ok, err = apply_pending_multitrack_export_analysis(session)
        self.assertTrue(ok, err)
        self.assertEqual(resolve_upload_analysis_audio_bytes(session), audio_export)
        self.assertNotEqual(bytes(session["last_analysis_audio"]), stale_audio)

    def test_analysis_runner_and_preview_share_prepared_audio(self) -> None:
        audio = _sample_wav_bytes(duration_sec=0.06)
        meta = {
            "source": "multitrack_export",
            "export_id": "e1",
            "export_name": "say export1",
            "song_title": "Say",
        }
        ok, err = replace_upload_analysis_with_multitrack_export(session := {}, meta, audio=audio)
        self.assertTrue(ok, err)
        prepared = resolve_upload_analysis_prepared_upload(session)
        self.assertIsNotNone(prepared)
        self.assertEqual(bytes(prepared.getvalue()), resolve_upload_analysis_audio_bytes(session))

    def test_export_handoff_sig_changes_for_different_exports(self) -> None:
        audio_a = _sample_wav_bytes(duration_sec=0.05)
        audio_b = _sample_wav_bytes(duration_sec=0.08)
        session: dict = {}
        replace_upload_analysis_with_multitrack_export(
            session,
            {"source": "multitrack_export", "export_id": "e1", "export_name": "A"},
            audio=audio_a,
        )
        sig_a = session.get(ANALYSIS_EXPORT_AUDIO_SIG_KEY)
        replace_upload_analysis_with_multitrack_export(
            session,
            {"source": "multitrack_export", "export_id": "e2", "export_name": "B"},
            audio=audio_b,
        )
        sig_b = session.get(ANALYSIS_EXPORT_AUDIO_SIG_KEY)
        self.assertNotEqual(sig_a, sig_b)
        self.assertEqual(sig_b[0], "e2")

    def test_handoff_metadata_excludes_raw_audio(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        row = {
            "export_id": "e1",
            "export_name": "Say mix v2",
            "song": "Say",
            "storage_ref": "supabase://bucket/key.wav",
            "local_path": "media/multitrack_exports/e1.wav",
            "playback_status": PLAYBACK_PLAYABLE,
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog = _catalog_fixture(tmp, row, audio)
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        ok_send, err_send = send_export_to_upload_analysis(session, "e1", st=None)
                        self.assertTrue(ok_send, err_send)
                        ok_apply, err_apply = apply_pending_multitrack_export_analysis(session)
                        self.assertTrue(ok_apply, err_apply)
        meta = session.get(ANALYSIS_EXPORT_HANDOFF_META_KEY) or {}
        text = json.dumps(meta)
        self.assertEqual(meta.get("source"), "multitrack_export")
        self.assertEqual(meta.get("export_id"), "e1")
        self.assertNotIn("audio_b64", text)
        self.assertNotIn("blob", text.lower())

    def test_saved_analysis_catalog_fields_use_multitrack_export_source(self) -> None:
        from media_upload_catalog import build_upload_recording_fields

        session = {
            "last_analysis_result": {"ok": True, "coach_summary": "Nice take", "scores": {}},
            "analysis_recording_type": ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX,
            "last_analysis_source_label": "say export1.wav",
            ANALYSIS_EXPORT_HANDOFF_META_KEY: {
                "source": "multitrack_export",
                "export_id": "e1",
                "export_name": "say export1",
                "song_title": "Say",
                "format": "wav",
                "storage_ref": "supabase://bucket/key.wav",
                "track_count": 2,
            },
        }
        fields = build_upload_recording_fields(session, st=None)
        self.assertIsNotNone(fields)
        assert fields is not None
        self.assertEqual(fields.get("source"), "multitrack_export")
        self.assertEqual(fields.get("export_id"), "e1")
        self.assertEqual(fields.get("export_name"), "say export1")
        self.assertEqual(fields.get("legacy_recording_type"), ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX)

    def test_ami_compact_still_excludes_raw_audio(self) -> None:
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

    def test_handoff_rehydrates_prepared_upload_after_rerun(self) -> None:
        audio = _sample_wav_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            catalog = _catalog_fixture(
                tmp,
                {
                    "export_id": "e1",
                    "export_name": "Say mix v2",
                    "local_path": "media/multitrack_exports/e1.wav",
                    "playback_status": PLAYBACK_PLAYABLE,
                },
                audio,
            )
            session: dict = {
                PENDING_EXPORT_ANALYSIS_KEY: {
                    "source": "multitrack_export",
                    "export_id": "e1",
                    "export_name": "Say mix v2",
                    "song_title": "Say",
                    "format": "wav",
                }
            }
            with patch("media_multitrack_export_catalog.load_media_catalog", lambda *, st=None: catalog):
                with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_storage.recording_local_abs_path", lambda ws, rel: Path(tmp) / "daniel" / rel):
                        apply_pending_multitrack_export_analysis(session)
                        prepared = session.get("_analysis_prepared_upload")
                        self.assertIsNotNone(prepared)
                        session.pop("_analysis_prepared_upload", None)
                        session.pop("_analysis_upload_prep_sig", None)
                        session.pop(ANALYSIS_EXPORT_AUDIO_SIG_KEY, None)
                        session["last_analysis_audio"] = b"stale-bytes"
                        rehydrated = resolve_upload_analysis_prepared_upload(session)
            self.assertIsNotNone(rehydrated)
            self.assertEqual(bytes(rehydrated.getvalue()), audio)

    def test_upload_analysis_ui_uses_resolved_prepared_upload(self) -> None:
        app_source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")
        bootstrap_source = (
            Path(__file__).resolve().parents[1] / "studio_history_bootstrap.py"
        ).read_text(encoding="utf-8")
        self.assertIn("resolve_upload_analysis_prepared_upload", app_source)
        self.assertIn("upload_analysis_has_export_handoff", app_source)
        self.assertIn("apply_pending_multitrack_export_analysis", bootstrap_source)
        self.assertIn("Multitrack mix", app_source)

    def test_run_analysis_enabled_when_handoff_ready(self) -> None:
        audio = _sample_wav_bytes()
        ok, _ = replace_upload_analysis_with_multitrack_export(
            session := {},
            {
                "source": "multitrack_export",
                "export_id": "e1",
                "export_name": "Say mix v2",
                "song_title": "Say",
            },
            audio=audio,
        )
        self.assertTrue(ok)
        prepared = resolve_upload_analysis_prepared_upload(session)
        self.assertIsNotNone(prepared)
        self.assertTrue(getattr(prepared, "getvalue", lambda: b"")())
        self.assertTrue(analysis_export_handoff_ready(session))


if __name__ == "__main__":
    unittest.main()

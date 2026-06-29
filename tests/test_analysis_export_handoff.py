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
    ANALYSIS_EXPORT_HANDOFF_META_KEY,
    ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX,
    PENDING_EXPORT_ANALYSIS_KEY,
    analysis_export_handoff_ready,
    apply_pending_multitrack_export_analysis,
    loaded_multitrack_export_analysis_banner,
    send_export_to_upload_analysis,
)
from media_state import compact_multitrack_export_for_ami, migrate_multitrack_export
from media_storage import PLAYBACK_PLAYABLE


def _sample_wav_bytes(*, duration_sec: float = 0.05, rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    nframes = max(1, int(rate * duration_sec))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


class TestAnalysisExportHandoff(unittest.TestCase):
    def test_send_then_apply_sets_upload_analysis_contract(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Say mix v2",
                "song": "Say",
                "track_count": 2,
                "duration_seconds": 74,
                "format": "wav",
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
        self.assertIn(PENDING_EXPORT_ANALYSIS_KEY, session)
        pending = session[PENDING_EXPORT_ANALYSIS_KEY]
        self.assertEqual(pending.get("source"), "multitrack_export")
        self.assertEqual(pending.get("export_id"), "e1")

        ok_apply, err_apply = apply_pending_multitrack_export_analysis(session)
        self.assertTrue(ok_apply, err_apply)
        self.assertNotIn(PENDING_EXPORT_ANALYSIS_KEY, session)
        self.assertEqual(session.get("analysis_mode"), "Single recording")
        self.assertEqual(session.get("analysis_recording_type"), ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX)
        self.assertTrue(session.get("_analysis_prepared_upload"))
        self.assertTrue(session.get("last_analysis_audio"))
        self.assertIn("Say mix v2", loaded_multitrack_export_analysis_banner(session))
        self.assertTrue(analysis_export_handoff_ready(session))

    def test_handoff_metadata_excludes_raw_audio(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        row = migrate_multitrack_export(
            {
                "export_id": "e1",
                "export_name": "Say mix v2",
                "song": "Say",
                "storage_ref": "supabase://bucket/key.wav",
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
        session: dict = {}
        audio = _sample_wav_bytes()
        meta = {
            "source": "multitrack_export",
            "export_id": "e1",
            "export_name": "Say mix v2",
            "song_title": "Say",
            "format": "wav",
        }
        session[PENDING_EXPORT_ANALYSIS_KEY] = meta
        session["last_analysis_audio"] = audio
        apply_pending_multitrack_export_analysis(session)
        prepared = session.get("_analysis_prepared_upload")
        self.assertIsNotNone(prepared)

        session.pop("_analysis_prepared_upload", None)
        session.pop("_analysis_upload_prep_sig", None)
        session["last_analysis_audio"] = audio
        ok, _ = apply_pending_multitrack_export_analysis(session)
        self.assertTrue(ok)
        self.assertIsNotNone(session.get("_analysis_prepared_upload"))

    def test_upload_analysis_ui_shows_loaded_export_label(self) -> None:
        app_source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")
        bootstrap_source = (
            Path(__file__).resolve().parents[1] / "studio_history_bootstrap.py"
        ).read_text(encoding="utf-8")
        self.assertIn("loaded_multitrack_export_analysis_banner", app_source)
        self.assertIn("analysis_export_handoff_ready", app_source)
        self.assertIn("apply_pending_multitrack_export_analysis", bootstrap_source)
        self.assertIn("Multitrack mix", app_source)

    def test_run_analysis_enabled_when_handoff_ready(self) -> None:
        session: dict = {}
        audio = _sample_wav_bytes()
        session[PENDING_EXPORT_ANALYSIS_KEY] = {
            "source": "multitrack_export",
            "export_id": "e1",
            "export_name": "Say mix v2",
            "song_title": "Say",
        }
        session["last_analysis_audio"] = audio
        apply_pending_multitrack_export_analysis(session)
        prepared = session.get("_analysis_prepared_upload")
        self.assertIsNotNone(prepared)
        self.assertTrue(getattr(prepared, "getvalue", lambda: b"")())


if __name__ == "__main__":
    unittest.main()

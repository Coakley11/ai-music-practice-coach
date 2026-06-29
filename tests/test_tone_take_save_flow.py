"""Tone Sustain Practice save flow — pending cache, catalog save, history filters."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_state import compact_tone_take_for_ami, migrate_tone_take
from media_tone_catalog import (
    cache_pending_tone_take,
    clear_pending_tone_take,
    list_tone_takes,
    note_filter_matches_row,
    pending_tone_take_ready,
    save_pending_tone_take,
    tone_take_row_summary,
)
from tone_take_history_ui import render_pending_tone_save
from tuner_tone import TonePracticeResult


def _fake_catalog_path(tmp: str):
    path = Path(tmp) / "media_catalog.json"

    def _fake_path(*, st=None):
        return path

    return path, _fake_path


def _sample_result(**overrides) -> TonePracticeResult:
    base = dict(
        duration_sec=5.0,
        median_note="G4",
        target_note="A4",
        mean_cents=6.0,
        max_cents_drift=10.0,
        pitch_stability_score=82.0,
        volume_stability_score=75.0,
        sustain_seconds=4.5,
        feedback=["Good sustain stability"],
    )
    base.update(overrides)
    return TonePracticeResult(**base)


class TestToneTakeSaveFlow(unittest.TestCase):
    def test_pending_ready_requires_result_and_audio(self) -> None:
        session: dict = {}
        cache_pending_tone_take(
            session,
            result=_sample_result(),
            audio_bytes=b"RIFF" + b"\x00" * 32,
            target_note="A4",
        )
        self.assertTrue(pending_tone_take_ready(session))
        session.pop("_pending_tone_take_audio", None)
        self.assertFalse(pending_tone_take_ready(session))

    def test_save_tone_take_without_notes(self) -> None:
        session: dict = {}
        cache_pending_tone_take(
            session,
            result=_sample_result(),
            audio_bytes=b"RIFF" + b"\x00" * 64,
            target_note="A4",
            meta={
                "instrument": "Tenor Saxophone",
                "display_key": "G",
                "transposing_type": "Tenor saxophone (Bb)",
                "pitch_class_label": "A",
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path = _fake_catalog_path(tmp)
            ws_dir = Path(tmp) / "daniel"
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel):
                                    with patch("media_storage.upload_tone_take_cloud", lambda *a, **k: ("", "cloud_disabled")):
                                        ok, tid, err = save_pending_tone_take(
                                            session,
                                            st=None,
                                            notes="",
                                        )
        self.assertTrue(ok, err)
        self.assertTrue(tid)
        self.assertFalse(pending_tone_take_ready(session))

    def test_saved_take_has_timestamp_and_transposing_notes(self) -> None:
        session: dict = {}
        cache_pending_tone_take(
            session,
            result=_sample_result(median_note="G4"),
            audio_bytes=b"RIFF" + b"\x00" * 64,
            target_note="A4",
            meta={
                "instrument": "Tenor Saxophone",
                "transposing_type": "Tenor saxophone (Bb)",
                "pitch_class_label": "A",
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path = _fake_catalog_path(tmp)
            ws_dir = Path(tmp) / "daniel"
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                                with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel):
                                    with patch("media_storage.upload_tone_take_cloud", lambda *a, **k: ("", "cloud_disabled")):
                                        ok, tid, _ = save_pending_tone_take(session, st=None)
            self.assertTrue(ok)
            self.assertTrue(tid)
            import json

            catalog = json.loads(path.read_text(encoding="utf-8"))
            row = migrate_tone_take(
                next(
                    r
                    for r in catalog.get("tone_takes") or []
                    if isinstance(r, dict) and str(r.get("tone_take_id") or "") == tid
                )
            )
            self.assertTrue(str(row.get("created_at") or "").strip())
            self.assertEqual(row.get("written_note"), "A4")
            self.assertEqual(row.get("concert_note"), "G4")
            self.assertFalse(row.get("deleted"))

    def test_saved_take_appears_in_history_and_note_filter(self) -> None:
        row = migrate_tone_take(
            {
                "tone_take_id": "t1",
                "instrument": "Tenor Saxophone",
                "written_note": "G#4",
                "concert_note": "F#4",
                "selected_pitch_class": "G#/Ab",
                "target_note": "G#4",
                "duration_seconds": 5,
                "mean_cents": 6,
                "pitch_stability_score": 80,
                "created_at": "2026-06-28T21:42:00+00:00",
            }
        )
        catalog = {"tone_takes": [row]}
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_tone_takes(
                st=None,
                instrument="Tenor Saxophone",
                note_filter="G#/Ab",
                current_instrument_is_transposing=True,
            )
        self.assertEqual(len(rows), 1)
        summary = tone_take_row_summary(row)
        self.assertIn("G#/Ab", summary)
        self.assertIn("Tenor Saxophone", summary)

    def test_note_filter_matches_enharmonic_label(self) -> None:
        row = migrate_tone_take(
            {
                "selected_pitch_class": "G#/Ab",
                "written_note": "G#4",
                "concert_note": "F#4",
            }
        )
        self.assertTrue(
            note_filter_matches_row(row, "G#/Ab", current_instrument_is_transposing=True)
        )
        self.assertFalse(
            note_filter_matches_row(row, "E", current_instrument_is_transposing=True)
        )

    def test_ami_compact_excludes_raw_audio(self) -> None:
        row = migrate_tone_take(
            {
                "tone_take_id": "t1",
                "instrument": "Flute",
                "storage_ref": "supabase://music-media/u/ws/tone.wav",
                "local_path": "media/tone_takes/t1.wav",
            }
        )
        compact = compact_tone_take_for_ami(row)
        text = json.dumps(compact)
        self.assertNotIn("audio_b64", text)
        self.assertNotIn("blob", text)
        self.assertIn("audio_available", compact)

    def test_save_button_ui_present_in_module(self) -> None:
        source = open(render_pending_tone_save.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("Save Tone Take", source)
        self.assertIn("Long-tone analysis ready", source)


if __name__ == "__main__":
    unittest.main()

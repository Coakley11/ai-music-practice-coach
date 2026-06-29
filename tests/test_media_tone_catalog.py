"""Tone & Tuner History — catalog, storage, AMI, and instrument filtering."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_persistence import (
    add_tone_take,
    build_media_ami_payload,
    delete_tone_take,
    load_media_catalog,
    update_tone_take,
)
from media_state import (
    compact_tone_take_for_ami,
    migrate_tone_take,
    normalize_tone_takes,
)
from media_tone_catalog import (
    build_tone_take_fields,
    list_tone_takes,
    resolve_tone_note_context,
    save_pending_tone_take,
    tone_take_quality,
    transpose_note_token,
)
from media_storage import persist_tone_take_audio, tone_take_playback_status
from tuner_tone import TonePracticeResult


def _fake_catalog_path(tmp: str):
    path = Path(tmp) / "media_catalog.json"

    def _fake_path(*, st=None):
        return path

    return path, _fake_path


def _sample_result(**overrides) -> TonePracticeResult:
    base = dict(
        duration_sec=18.0,
        median_note="G4",
        target_note="A4",
        mean_cents=6.0,
        max_cents_drift=12.0,
        pitch_stability_score=82.0,
        volume_stability_score=75.0,
        sustain_seconds=16.0,
        feedback=["Good sustain stability"],
    )
    base.update(overrides)
    return TonePracticeResult(**base)


class TestMediaToneCatalog(unittest.TestCase):
    def test_resolve_transposing_notes_tenor_sax(self) -> None:
        target, written, concert = resolve_tone_note_context(
            target_note="A4",
            detected_note="G4",
            transposing_type="Tenor saxophone (Bb)",
        )
        self.assertEqual(target, "A4")
        self.assertEqual(written, "A4")
        self.assertEqual(concert, "G4")

    def test_transpose_note_token(self) -> None:
        self.assertEqual(transpose_note_token("A4", -2), "G4")
        self.assertEqual(transpose_note_token("G4", 2), "A4")

    def test_build_tone_take_fields_flute(self) -> None:
        session = {"instrument": "Flute"}
        fields = build_tone_take_fields(
            session,
            _sample_result(median_note="A4", target_note="A4"),
            instrument="Flute",
            display_key="C",
        )
        self.assertEqual(fields.get("instrument"), "Flute")
        self.assertIsNone(fields.get("written_note"))
        self.assertEqual(fields.get("concert_note"), "A4")

    def test_build_tone_take_fields_tenor_sax(self) -> None:
        session = {"instrument": "Saxophone", "selected_transposing_instrument": "Tenor saxophone (Bb)"}
        fields = build_tone_take_fields(
            session,
            _sample_result(median_note="G4", target_note="A4"),
            instrument="Saxophone",
            display_key="C",
            transposing_type="Tenor saxophone (Bb)",
        )
        self.assertEqual(fields.get("written_note"), "A4")
        self.assertEqual(fields.get("concert_note"), "G4")

    def test_save_flute_tone_take(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path = _fake_catalog_path(tmp)
            fields = migrate_tone_take(
                {
                    "instrument": "Flute",
                    "concert_note": "A4",
                    "target_note": "A4",
                    "duration_seconds": 15,
                    "mean_cents": 3,
                    "pitch_stability_score": 80,
                }
            )
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_tone_take(None, fields)
                            self.assertTrue(row.get("tone_take_id"))
                            self.assertTrue(path.exists())

    def test_save_tenor_sax_tone_take(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path, fake_path = _fake_catalog_path(tmp)
            fields = migrate_tone_take(
                {
                    "instrument": "Tenor Saxophone",
                    "written_note": "A4",
                    "concert_note": "G4",
                    "target_note": "A4",
                    "duration_seconds": 18,
                    "mean_cents": 6,
                    "pitch_stability_score": 78,
                }
            )
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_tone_take(None, fields)
                            self.assertEqual(row.get("written_note"), "A4")
                            self.assertEqual(row.get("concert_note"), "G4")

    def test_active_instrument_flute_default_history(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take({"tone_take_id": "f1", "instrument": "Flute", "concert_note": "A4"}),
                migrate_tone_take({"tone_take_id": "t1", "instrument": "Tenor Saxophone", "written_note": "A4"}),
            ]
        }
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_tone_takes(st=None, instrument="Flute")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Flute")

    def test_active_instrument_tenor_sax_default_history(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take({"tone_take_id": "f1", "instrument": "Flute", "concert_note": "A4"}),
                migrate_tone_take({"tone_take_id": "t1", "instrument": "Tenor Saxophone", "written_note": "A4"}),
            ]
        }
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_tone_takes(st=None, instrument="Tenor Saxophone")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Tenor Saxophone")

    def test_all_instruments_view(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take({"tone_take_id": "f1", "instrument": "Flute"}),
                migrate_tone_take({"tone_take_id": "t1", "instrument": "Tenor Saxophone"}),
            ]
        }
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_tone_takes(st=None, instrument=None)
        self.assertEqual(len(rows), 2)

    def test_filter_by_note(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take({"tone_take_id": "a1", "instrument": "Flute", "concert_note": "A4"}),
                migrate_tone_take({"tone_take_id": "g1", "instrument": "Flute", "concert_note": "G4"}),
            ]
        }
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            rows = list_tone_takes(
                st=None,
                note_filter="G",
                all_instruments_view=True,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("tone_take_id"), "g1")

    def test_delete_hides_tone_take(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, fake_path = _fake_catalog_path(tmp)
            row = migrate_tone_take({"tone_take_id": "del1", "instrument": "Flute"})
            with patch("media_persistence._local_path", fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            row = add_tone_take(None, row)
                            tid = str(row.get("tone_take_id") or "")
                            self.assertTrue(delete_tone_take(None, tid))
                            catalog = load_media_catalog(st=None)
                            visible = normalize_tone_takes(catalog.get("tone_takes") or [])
                            self.assertEqual(len(visible), 0)

    def test_tone_audio_gets_storage_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = Path(tmp) / "daniel"
            ws_dir.mkdir(parents=True)
            audio = b"RIFF" + b"\x00" * 120
            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                with patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel):
                    with patch("media_storage.upload_tone_take_cloud", lambda *a, **k: ("supabase://music-media/u/ws/tone.wav", "")):
                        result = persist_tone_take_audio(None, "tone-1", audio)
            self.assertTrue(result.get("local_path"))
            self.assertTrue(result.get("storage_ref"))
            self.assertEqual(result.get("playback_status"), "playable")

    def test_playback_status_metadata_only_without_audio(self) -> None:
        row = migrate_tone_take({"tone_take_id": "m1", "instrument": "Flute"})
        status = tone_take_playback_status(row)
        self.assertEqual(status, "metadata_only")

    def test_playback_status_playable_with_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws_dir = Path(tmp) / "daniel"
            rel = "media/tone_takes/tone-1.wav"
            path = ws_dir / rel
            path.parent.mkdir(parents=True)
            path.write_bytes(b"RIFF")
            row = migrate_tone_take(
                {
                    "tone_take_id": "tone-1",
                    "local_path": rel,
                    "workspace_id": "daniel",
                }
            )
            with patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"):
                with patch("media_storage.recording_local_abs_path", lambda ws, r: ws_dir / r):
                    status = tone_take_playback_status(row)
            self.assertEqual(status, "playable")

    def test_ami_payload_includes_tone_summaries_by_instrument(self) -> None:
        catalog = {
            "uploaded_recordings": [],
            "multitrack_sessions": [],
            "tone_takes": [
                migrate_tone_take(
                    {
                        "tone_take_id": "f1",
                        "instrument": "Flute",
                        "concert_note": "A4",
                        "pitch_stability_score": 85,
                        "updated_at": "2026-06-27T10:00:00+00:00",
                    }
                ),
                migrate_tone_take(
                    {
                        "tone_take_id": "t1",
                        "instrument": "Tenor Saxophone",
                        "written_note": "A4",
                        "concert_note": "G4",
                        "pitch_stability_score": 70,
                        "updated_at": "2026-06-27T11:00:00+00:00",
                    }
                ),
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        tone = payload.get("tone_history") or {}
        self.assertEqual(tone.get("tone_take_count_total"), 2)
        by_inst = tone.get("tone_take_count_by_instrument") or {}
        self.assertEqual(by_inst.get("Flute"), 1)
        self.assertEqual(by_inst.get("Tenor Saxophone"), 1)

    def test_ami_payload_excludes_raw_audio(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take(
                    {
                        "tone_take_id": "f1",
                        "instrument": "Flute",
                        "storage_ref": "supabase://music-media/u/ws/tone.wav",
                        "local_path": "media/tone_takes/f1.wav",
                        "updated_at": "2026-06-27T10:00:00+00:00",
                    }
                ),
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        text = json.dumps(payload)
        self.assertNotIn("audio_b64", text)
        self.assertNotIn("base64", text)
        self.assertNotIn("blob", text)
        compact = compact_tone_take_for_ami(catalog["tone_takes"][0])
        self.assertIn("audio_available", compact)
        self.assertTrue(compact.get("audio_available"))

    def test_save_pending_tone_take_end_to_end(self) -> None:
        session: dict = {}
        from media_tone_catalog import cache_pending_tone_take, clear_pending_tone_take

        cache_pending_tone_take(
            session,
            result=_sample_result(),
            audio_bytes=b"RIFF" + b"\x00" * 64,
            target_note="A4",
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
                                            instrument="Tenor Saxophone",
                                            display_key="C",
                                            transposing_type="Tenor saxophone (Bb)",
                                        )
            self.assertTrue(ok, err)
            self.assertTrue(tid)
            clear_pending_tone_take(session)

    def test_ami_payload_excludes_deleted_tone_take(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take(
                    {
                        "tone_take_id": "live",
                        "instrument": "Flute",
                        "concert_note": "A4",
                        "updated_at": "2026-06-27T10:00:00+00:00",
                    }
                ),
                {
                    "tone_take_id": "dead",
                    "deleted": True,
                    "deleted_at": "2026-06-27T11:00:00+00:00",
                    "updated_at": "2026-06-27T11:00:00+00:00",
                },
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        tone = payload.get("tone_history") or {}
        self.assertEqual(tone.get("tone_take_count_total"), 1)
        ids = {r.get("tone_take_id") for r in tone.get("recent_tone_reports") or []}
        self.assertIn("live", ids)
        self.assertNotIn("dead", ids)

    def test_ami_payload_best_worst_by_instrument(self) -> None:
        catalog = {
            "tone_takes": [
                migrate_tone_take(
                    {
                        "tone_take_id": "f1",
                        "instrument": "Flute",
                        "pitch_stability_score": 90,
                        "updated_at": "2026-06-27T10:00:00+00:00",
                    }
                ),
                migrate_tone_take(
                    {
                        "tone_take_id": "t1",
                        "instrument": "Tenor Saxophone",
                        "written_note": "A4",
                        "concert_note": "G4",
                        "pitch_stability_score": 60,
                        "updated_at": "2026-06-27T11:00:00+00:00",
                    }
                ),
            ],
        }
        payload = build_media_ami_payload(None, catalog, window_days=30)
        tone = payload.get("tone_history") or {}
        best_by = tone.get("best_pitch_stability_by_instrument") or {}
        worst_by = tone.get("worst_pitch_stability_by_instrument") or {}
        self.assertEqual(best_by.get("Flute", {}).get("tone_take_id"), "f1")
        self.assertEqual(worst_by.get("Tenor Saxophone", {}).get("tone_take_id"), "t1")
        self.assertIn("improvement_trends_by_instrument_and_note", tone)

    def test_migrate_tone_take_spec_field_aliases(self) -> None:
        row = migrate_tone_take(
            {
                "tone_take_id": "x1",
                "instrument": "Flute",
                "average_cents": 5.0,
                "pitch_stability": 80.0,
                "sustain_steadiness": 75.0,
                "coach_report": "Steady tone",
                "user_notes": "Long tone warmup",
            }
        )
        self.assertEqual(row.get("mean_cents"), 5.0)
        self.assertEqual(row.get("average_cents"), 5.0)
        self.assertEqual(row.get("pitch_stability_score"), 80.0)
        self.assertEqual(row.get("user_notes"), "Long tone warmup")
        self.assertIsInstance(row.get("analysis_summary"), dict)

    def test_quality_filters(self) -> None:
        best = migrate_tone_take({"tone_take_id": "b1", "pitch_stability_score": 85, "mean_cents": 2})
        weak = migrate_tone_take({"tone_take_id": "w1", "pitch_stability_score": 40, "mean_cents": 25})
        self.assertEqual(tone_take_quality(best), "best")
        self.assertEqual(tone_take_quality(weak), "needs_work")


if __name__ == "__main__":
    unittest.main()

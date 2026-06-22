"""Tests for Upload + Multitrack cloud history libraries."""

from __future__ import annotations

from multitrack_history import (
    apply_multitrack_history,
    build_multitrack_history_payload,
    save_multitrack_to_history,
)
from studio_history_cloud import encode_audio_if_safe, widget_key_suffix
from upload_history import (
    apply_upload_history,
    build_upload_history_payload,
    save_upload_to_history,
    scores_summary_from_result,
)


def test_encode_audio_if_safe_skips_large_blob() -> None:
    small, skip = encode_audio_if_safe(b"x" * 1000, max_bytes=2000)
    assert small
    assert skip is None
    large, skip2 = encode_audio_if_safe(b"x" * 600_000, max_bytes=512_000)
    assert large is None
    assert skip2


def test_upload_history_build_and_apply() -> None:
    session = {
        "last_analysis_result": {
            "ok": True,
            "coach_summary": "Solid groove",
            "scores": {"timing": 88, "pitch": 79},
        },
        "last_analysis_audio": b"\x00\x01\xff",
        "last_analysis_source_label": "take_one.wav",
        "analysis_recording_type": "Practice take",
    }
    payload = build_upload_history_payload(session, title="My take", notes="Gig prep")
    assert payload
    assert payload["title"] == "My take"
    assert payload["source_label"] == "take_one.wav"
    assert payload["analysis_result"]["coach_summary"] == "Solid groove"
    assert payload["audio_b64"]

    fresh: dict = {}
    assert apply_upload_history(fresh, payload) is True
    assert fresh["last_analysis_result"]["coach_summary"] == "Solid groove"
    assert fresh["last_analysis_audio"] == b"\x00\x01\xff"


def test_upload_scores_summary() -> None:
    summary = scores_summary_from_result({"ok": True, "coach_summary": "Nice", "scores": {"timing": 90}})
    assert summary["timing"] == 90
    assert summary["coach_summary"] == "Nice"


def test_multitrack_history_metadata_and_embedded_audio() -> None:
    session = {
        "mt_tracks": {
            "Guitar": b"abc",
            "Bass": None,
            "Piano / Keys": None,
            "Vocals": None,
            "Sax / winds": None,
            "Extra layer": None,
        },
        "mt_track_filenames": {"Guitar": "guitar.wav"},
        "mt_name_Guitar": "Lead",
        "mt_vol_Guitar": 0.8,
        "mt_delay_Guitar": 0.1,
        "mixed_track_wav": b"mix",
    }
    payload = build_multitrack_history_payload(session, project_name="Test project", song_title="Autumn Leaves")
    assert payload
    assert payload["project_name"] == "Test project"
    assert payload["embedded_tracks"]["Guitar"]
    assert payload["mixed_preview_b64"]

    fresh = {"mt_tracks": {}, "mt_track_filenames": {}}
    info = apply_multitrack_history(fresh, payload)
    assert info["restored_layers"] == 1
    assert fresh["mt_tracks"]["Guitar"] == b"abc"
    assert fresh["mt_name_Guitar"] == "Lead"
    assert fresh["mixed_track_wav"] == b"mix"


def test_save_upload_to_history_uses_cloud(monkeypatch) -> None:
    saved: dict = {}

    def _save(**kwargs):
        saved.update(kwargs)
        return True

    monkeypatch.setattr("upload_history.save_history_item", _save)
    session = {"last_analysis_result": {"ok": True, "coach_summary": "X"}}
    ok, key = save_upload_to_history(session, title="T", notes="")
    assert ok
    assert key.startswith("upload_")
    assert saved["item_type"] == "upload_history"


def test_widget_key_suffix() -> None:
    assert widget_key_suffix("upload_2026-abc") == "upload_2026_abc"

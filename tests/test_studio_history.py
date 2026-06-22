"""Tests for Upload + Multitrack cloud history libraries."""

from __future__ import annotations

from multitrack_history import (
    apply_multitrack_history,
    apply_pending_multitrack_history,
    build_multitrack_history_payload,
    clear_multitrack_widget_keys,
    queue_multitrack_history_load,
    save_multitrack_to_history,
)
from studio_history_cloud import encode_audio_if_safe, save_history_item, widget_key_suffix
from upload_history import (
    apply_pending_upload_history,
    apply_upload_history,
    build_upload_history_payload,
    compact_analysis_for_history,
    queue_upload_history_load,
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
    payload, err = build_upload_history_payload(session, title="My take", notes="Gig prep")
    assert payload and not err
    assert payload["title"] == "My take"
    assert payload["source_label"] == "take_one.wav"

    fresh: dict = {}
    assert apply_upload_history(fresh, payload) is True
    assert fresh["last_analysis_result"]["coach_summary"] == "Solid groove"
    assert fresh["last_analysis_audio"] == b"\x00\x01\xff"


def test_upload_pending_load_applies_before_widgets() -> None:
    session: dict = {}
    payload = {
        "analysis_result": {"ok": True, "coach_summary": "Queued"},
        "source_label": "queued.wav",
    }
    queue_upload_history_load(session, payload)
    assert apply_pending_upload_history(session) is True
    assert session["last_analysis_result"]["coach_summary"] == "Queued"


def test_multitrack_pending_load_clears_widget_keys() -> None:
    session = {
        "mt_name_Guitar": "Old widget value",
        "mt_vol_slider_Guitar": 0.5,
    }
    payload = {
        "tracks": [{"slot": "Guitar", "layer_name": "Lead", "filename": "g.wav", "volume": 0.8, "delay": 0.0, "has_audio": False}],
        "embedded_tracks": {},
    }
    queue_multitrack_history_load(session, payload)
    info = apply_pending_multitrack_history(session)
    assert info is not None
    assert "mt_name_Guitar" in session
    assert session["mt_name_Guitar"] == "Lead"
    assert "mt_vol_slider_Guitar" not in session


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
    payload, err = build_multitrack_history_payload(session, project_name="Test project", song_title="Autumn Leaves")
    assert payload and not err
    clear_multitrack_widget_keys(session)
    info = apply_multitrack_history(session, payload)
    assert info["restored_layers"] == 1
    assert session["mt_tracks"]["Guitar"] == b"abc"
    assert session["mixed_track_wav"] == b"mix"


def test_save_upload_to_history_checks_cloud_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "upload_history.save_history_item",
        lambda **kwargs: (True, ""),
    )
    session = {"last_analysis_result": {"ok": True, "coach_summary": "X"}}
    ok, key, err = save_upload_to_history(session, title="T", notes="")
    assert ok and key.startswith("upload_") and not err


def test_save_history_item_reports_skipped_write(monkeypatch) -> None:
    monkeypatch.setattr("studio_history_cloud.cloud_enabled", lambda: True)
    monkeypatch.setattr(
        "suite_account.remember_saved_item",
        lambda *a, **k: {"write_mode": "skipped"},
    )
    ok, err = save_history_item(item_type="upload_history", item_key="k", title="T", payload={"workspace_id": "daniel"})
    assert not ok
    assert err == "cloud_write_skipped"


def test_widget_key_suffix() -> None:
    assert widget_key_suffix("upload_2026-abc") == "upload_2026_abc"


def test_scores_summary() -> None:
    summary = scores_summary_from_result({"ok": True, "coach_summary": "Nice", "scores": {"timing": 90}})
    assert summary["timing"] == 90


def test_compact_analysis_for_history() -> None:
    compact = compact_analysis_for_history({"ok": True, "coach_summary": "Hi", "scores": {"timing": 1}})
    assert compact["coach_summary"] == "Hi"

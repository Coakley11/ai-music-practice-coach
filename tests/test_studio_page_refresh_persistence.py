"""Same-device refresh persistence for Upload, Multitrack, Log-adjacent, and Creative pages."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state, build_music_disk_state
from studio_page_persistence import (
    _B64_MARKER,
    apply_page_snapshot,
    capture_page_snapshot,
    flush_current_page_snapshot,
    handle_studio_page_transition,
    restore_current_page_snapshot_if_needed,
)


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeSt:
    def __init__(self, session_state: dict | None = None) -> None:
        self.session_state = session_state if session_state is not None else _FakeSessionState()


def test_flush_current_page_snapshot_before_disk_build() -> None:
    ss = _FakeSessionState(
        {
            "studio_page": "analysis",
            "last_analysis_result": {"ok": True, "coach_summary": "Solid timing"},
            "instrument": "Piano",
        }
    )
    st = _FakeSt(ss)
    flush_current_page_snapshot(ss)
    state = build_music_disk_state(st)
    snap = state.get("session", {}).get("_studio_page_snapshots", {}).get("analysis", {})
    assert snap.get("last_analysis_result", {}).get("coach_summary") == "Solid timing"


def test_refresh_restores_current_page_when_tracker_missing() -> None:
    ss = {
        "studio_page": "creative",
        "improv_motif_abc": "X:1\nT:test",
        "instrument": "Piano",
        "_studio_page_snapshots": {
            "creative": capture_page_snapshot(
                {
                    "studio_page": "creative",
                    "improv_motif_abc": "X:1\nT:test",
                    "instrument": "Piano",
                },
                "creative",
            ),
        },
    }
    ss.pop("improv_motif_abc", None)
    handle_studio_page_transition(ss)
    assert ss.get("improv_motif_abc") == "X:1\nT:test"
    assert ss.get("_studio_active_page_id") == "creative"


def test_reset_tracker_allows_analysis_restore_after_prior_run() -> None:
    from studio_page_persistence import reset_page_snapshot_tracker

    ss = {
        "studio_page": "analysis",
        "_studio_active_page_id": "analysis",
        "_studio_page_snapshots": {
            "analysis": capture_page_snapshot(
                {
                    "last_analysis_result": {"ok": True, "coach_summary": "Kept"},
                },
                "analysis",
            ),
        },
    }
    reset_page_snapshot_tracker(ss)
    handle_studio_page_transition(ss)
    assert ss.get("last_analysis_result", {}).get("coach_summary") == "Kept"


def test_multitrack_binary_round_trips_through_json_disk_state() -> None:
    audio = b"\x00\x01track-audio\xff"
    ss = _FakeSessionState(
        {
            "studio_page": "multitrack",
            "mt_tracks": {"A": audio, "B": None},
            "mt_track_filenames": {"A": "take.wav", "B": ""},
            "mixed_track_wav": b"\x02mixed",
            "instrument": "Piano",
        }
    )
    st = _FakeSt(ss)
    state = build_music_disk_state(st)
    blob = json.loads(json.dumps(state, default=str))
    fresh = _FakeSessionState({"studio_page": "multitrack", "instrument": "Piano"})
    fresh_st = _FakeSt(fresh)
    apply_music_disk_state(
        fresh_st,
        blob,
        song_picker_catalog={},
        song_library=None,
    )
    handle_studio_page_transition(fresh)
    assert fresh.get("mt_tracks", {}).get("A") == audio
    assert fresh.get("mixed_track_wav") == b"\x02mixed"
    assert fresh.get("mt_track_filenames", {}).get("A") == "take.wav"


def test_capture_encodes_bytes_for_json() -> None:
    snap = capture_page_snapshot({"last_analysis_audio": b"\xab\xcd"}, "analysis")
    assert _B64_MARKER in snap.get("last_analysis_audio", {})
    restored: dict = {}
    apply_page_snapshot(restored, snap)
    assert restored.get("last_analysis_audio") == b"\xab\xcd"


def test_multitrack_restore_when_slot_map_empty_but_snapshot_has_audio() -> None:
    from studio_page_persistence import (
        capture_page_snapshot,
        reset_page_snapshot_tracker,
        restore_current_page_snapshot_if_needed,
    )

    audio = b"guitar-take"
    ss = {
        "studio_page": "multitrack",
        "mt_tracks": {"Guitar": None, "Bass": None},
        "_studio_page_snapshots": {
            "multitrack": capture_page_snapshot(
                {
                    "studio_page": "multitrack",
                    "mt_tracks": {"Guitar": audio, "Bass": None},
                    "mt_track_filenames": {"Guitar": "guitar.wav"},
                },
                "multitrack",
            ),
        },
    }
    reset_page_snapshot_tracker(ss)
    restore_current_page_snapshot_if_needed(ss)
    assert ss.get("mt_tracks", {}).get("Guitar") == audio


def test_practice_history_file_survives_reload(tmp_path: Path, monkeypatch) -> None:
    import music_workspace_paths as mwp

    ws_dir = tmp_path / "workspaces" / "daniel"
    ws_dir.mkdir(parents=True)
    log_file = ws_dir / "practice_history.json"
    monkeypatch.setattr(mwp, "workspace_dir", lambda ws: tmp_path / "workspaces" / ws)
    monkeypatch.setattr(mwp, "normalize_workspace_id", lambda raw: "daniel")
    monkeypatch.setattr(mwp, "resolve_workspace_id", lambda **_: "daniel")

    entry = {"date": "2026-06-19", "song": "Autumn Leaves", "minutes": 30}
    log_file.write_text(json.dumps([entry]), encoding="utf-8")

    from streamlit_music_practice_app import load_logs

    loaded = load_logs()
    assert len(loaded) == 1
    assert loaded[0]["song"] == "Autumn Leaves"

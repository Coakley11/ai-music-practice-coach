"""Tests for durable Upload / Analysis session persistence (disk + cloud)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis_session_persistence import (
    analysis_result_ready,
    restore_analysis_session,
    sanitize_analysis_result_for_persist,
    save_analysis_session,
)


@dataclass
class _FakeFeatures:
    waveform_peaks: list[float]
    waveform_times: list[float]
    highlight_regions: list[tuple[float, float]]


def test_sanitize_strips_runtime_features_object() -> None:
    raw = {
        "ok": True,
        "coach_summary": "Solid groove",
        "features": _FakeFeatures([0.1, 0.2], [0.0, 0.5], [(0.1, 0.3)]),
    }
    clean = sanitize_analysis_result_for_persist(raw)
    assert clean["coach_summary"] == "Solid groove"
    assert clean["features"]["waveform_peaks"] == [0.1, 0.2]
    json.dumps(clean)


def test_analysis_session_file_round_trip(tmp_path: Path, monkeypatch) -> None:
    import music_workspace_paths as mwp

    ws_dir = tmp_path / "workspaces" / "daniel"
    ws_dir.mkdir(parents=True)
    monkeypatch.setattr(mwp, "workspace_dir", lambda ws: tmp_path / "workspaces" / ws)
    monkeypatch.setattr(mwp, "normalize_workspace_id", lambda raw: "daniel")
    monkeypatch.setattr(mwp, "resolve_workspace_id", lambda **_: "daniel")
    monkeypatch.setattr(
        "analysis_session_persistence._save_cloud",
        lambda payload: False,
    )
    monkeypatch.setattr(
        "analysis_session_persistence._restore_from_cloud",
        lambda **_: None,
    )

    session = {
        "last_analysis_result": {"ok": True, "coach_summary": "Solid groove"},
        "last_analysis_audio": b"\x00\x01\xff",
    }
    status = save_analysis_session(session)
    assert status["local"] == "ok"

    fresh: dict = {}
    assert restore_analysis_session(fresh) is True
    assert fresh["last_analysis_result"]["coach_summary"] == "Solid groove"
    assert fresh["last_analysis_audio"] == b"\x00\x01\xff"


def test_restore_prefers_cloud_over_local(tmp_path: Path, monkeypatch) -> None:
    import music_workspace_paths as mwp

    ws_dir = tmp_path / "workspaces" / "daniel"
    ws_dir.mkdir(parents=True)
    monkeypatch.setattr(mwp, "workspace_dir", lambda ws: tmp_path / "workspaces" / ws)
    monkeypatch.setattr(mwp, "normalize_workspace_id", lambda raw: "daniel")
    monkeypatch.setattr(mwp, "resolve_workspace_id", lambda **_: "daniel")

    local_path = tmp_path / "workspaces" / "daniel" / "analysis_last_session.json"
    local_path.write_text(
        json.dumps(
            {
                "workspace_id": "daniel",
                "last_analysis_result": {"ok": True, "coach_summary": "Local only"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "analysis_session_persistence._restore_from_cloud",
        lambda **_: {
            "workspace_id": "daniel",
            "last_analysis_result": {"ok": True, "coach_summary": "From cloud"},
        },
    )

    fresh: dict = {}
    assert restore_analysis_session(fresh) is True
    assert fresh["last_analysis_result"]["coach_summary"] == "From cloud"


def test_restore_skips_when_session_already_has_result() -> None:
    session = {"last_analysis_result": {"ok": True}}
    assert restore_analysis_session(session) is False


def test_analysis_result_ready() -> None:
    assert analysis_result_ready({"ok": True, "coach_summary": "x"})
    assert not analysis_result_ready({})
    assert not analysis_result_ready({"ok": False})

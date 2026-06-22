"""Tests for durable Upload / Analysis session file persistence."""

from __future__ import annotations

import json
from pathlib import Path

from analysis_session_persistence import (
    restore_analysis_session,
    save_analysis_session,
)


def test_analysis_session_file_round_trip(tmp_path: Path, monkeypatch) -> None:
    import music_workspace_paths as mwp

    ws_dir = tmp_path / "workspaces" / "daniel"
    ws_dir.mkdir(parents=True)
    monkeypatch.setattr(mwp, "workspace_dir", lambda ws: tmp_path / "workspaces" / ws)
    monkeypatch.setattr(mwp, "normalize_workspace_id", lambda raw: "daniel")
    monkeypatch.setattr(mwp, "resolve_workspace_id", lambda **_: "daniel")

    session = {
        "last_analysis_result": {"ok": True, "coach_summary": "Solid groove"},
        "last_analysis_audio": b"\x00\x01\xff",
    }
    assert save_analysis_session(session) is True

    fresh: dict = {}
    assert restore_analysis_session(fresh) is True
    assert fresh["last_analysis_result"]["coach_summary"] == "Solid groove"
    assert fresh["last_analysis_audio"] == b"\x00\x01\xff"


def test_restore_skips_when_session_already_has_result() -> None:
    session = {"last_analysis_result": {"ok": True}}
    assert restore_analysis_session(session) is False

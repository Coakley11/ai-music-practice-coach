"""Durable Upload / Analysis page session — survives browser refresh (workspace-scoped)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from music_workspace_paths import music_data_path

_SESSION_VERSION = 1


def _session_path() -> Path:
    return music_data_path("analysis_last_session")


def save_analysis_session(session_state: dict[str, Any]) -> bool:
    """Persist coach report + optional preview audio to workspace disk."""
    result = session_state.get("last_analysis_result")
    if not isinstance(result, dict) or not result:
        return False
    audio = session_state.get("last_analysis_audio")
    payload: dict[str, Any] = {
        "version": _SESSION_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "last_analysis_result": result,
    }
    if isinstance(audio, (bytes, bytearray)) and audio:
        payload["last_analysis_audio_b64"] = base64.b64encode(bytes(audio)).decode("ascii")
    path = _session_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def restore_analysis_session(session_state: dict[str, Any]) -> bool:
    """Load last Upload analysis from disk when session/snapshot keys are missing."""
    if session_state.get("last_analysis_result"):
        return False
    path = _session_path()
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(raw, dict):
        return False
    result = raw.get("last_analysis_result")
    if not isinstance(result, dict) or not result:
        return False
    session_state["last_analysis_result"] = result
    b64 = raw.get("last_analysis_audio_b64")
    if isinstance(b64, str) and b64.strip():
        try:
            session_state["last_analysis_audio"] = base64.b64decode(b64.encode("ascii"))
        except Exception:
            pass
    return True


def clear_analysis_session() -> None:
    path = _session_path()
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass

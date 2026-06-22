"""Durable Upload / Analysis session — local disk + Supabase (Streamlit Cloud safe)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from music_workspace_paths import music_data_path

_SESSION_VERSION = 1
_ITEM_TYPE = "analysis_last_session"
_ITEM_KEY = "last"


def _active_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import get_active_workspace_id, normalize_workspace_id

        return normalize_workspace_id(get_active_workspace_id(st))
    except Exception:
        return "daniel"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _extract_persistable_features(features: Any) -> dict[str, Any] | None:
    if features is None:
        return None
    if isinstance(features, dict):
        return {
            "waveform_peaks": list(features.get("waveform_peaks") or []),
            "waveform_times": list(features.get("waveform_times") or []),
            "highlight_regions": list(features.get("highlight_regions") or []),
        }
    peaks = getattr(features, "waveform_peaks", None)
    times = getattr(features, "waveform_times", None)
    regions = getattr(features, "highlight_regions", None)
    if peaks is None and times is None and regions is None:
        return None
    return {
        "waveform_peaks": list(peaks or []),
        "waveform_times": list(times or []),
        "highlight_regions": list(regions or []),
    }


def sanitize_analysis_result_for_persist(result: Any) -> dict[str, Any]:
    """Strip non-JSON runtime objects (AudioFeatures) before disk/cloud writes."""
    if not isinstance(result, dict):
        return {}
    out: dict[str, Any] = {}
    for key, val in result.items():
        if key == "features":
            feat = _extract_persistable_features(val)
            if feat:
                out["features"] = feat
            continue
        try:
            json.dumps(val, default=str)
            out[key] = val
        except (TypeError, ValueError):
            out[key] = str(val)
    return _json_safe(out)


def analysis_result_ready(result: Any) -> bool:
    return isinstance(result, dict) and bool(result) and bool(result.get("ok", True))


def _session_path(*, workspace_id: str | None = None) -> Path:
    ws = workspace_id or _active_workspace_id()
    return music_data_path("analysis_last_session", ws)


def _build_payload(session_state: dict[str, Any], *, st: Any | None = None) -> dict[str, Any] | None:
    raw = session_state.get("last_analysis_result")
    if not analysis_result_ready(raw):
        return None
    result = sanitize_analysis_result_for_persist(raw)
    if not result:
        return None
    audio = session_state.get("last_analysis_audio")
    payload: dict[str, Any] = {
        "version": _SESSION_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": _active_workspace_id(st=st),
        "last_analysis_result": result,
    }
    if isinstance(audio, (bytes, bytearray)) and audio:
        payload["last_analysis_audio_b64"] = base64.b64encode(bytes(audio)).decode("ascii")
    return payload


def _apply_payload(session_state: dict[str, Any], payload: dict[str, Any]) -> bool:
    result = payload.get("last_analysis_result")
    if not analysis_result_ready(result):
        return False
    session_state["last_analysis_result"] = result
    b64 = payload.get("last_analysis_audio_b64")
    if isinstance(b64, str) and b64.strip():
        try:
            session_state["last_analysis_audio"] = base64.b64decode(b64.encode("ascii"))
        except Exception:
            pass
    return True


def _save_local(payload: dict[str, Any], *, workspace_id: str) -> bool:
    path = _session_path(workspace_id=workspace_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _save_cloud(payload: dict[str, Any]) -> bool:
    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError:
        return False
    if not cloud_storage_enabled():
        return False
    try:
        from suite_account import remember_saved_item

        title = str(payload.get("last_analysis_result", {}).get("coach_summary") or "Last Upload analysis")[:120]
        remember_saved_item(
            "music",
            _ITEM_TYPE,
            _ITEM_KEY,
            title=title or "Last Upload analysis",
            payload=payload,
        )
        return True
    except Exception:
        return False


def _restore_from_cloud(*, st: Any | None = None) -> dict[str, Any] | None:
    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError:
        return None
    if not cloud_storage_enabled():
        return None
    try:
        from suite_account import load_saved_items

        rows = load_saved_items(app="music", item_type=_ITEM_TYPE, limit=20)
    except Exception:
        return None
    ws = _active_workspace_id(st=st)
    for row in rows or []:
        if str(row.get("item_key") or "") != _ITEM_KEY:
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        row_ws = str(payload.get("workspace_id") or "daniel").strip().lower()
        if row_ws != ws:
            continue
        if analysis_result_ready(payload.get("last_analysis_result")):
            return payload
    return None


def _restore_from_local(*, workspace_id: str) -> dict[str, Any] | None:
    path = _session_path(workspace_id=workspace_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(raw, dict) and analysis_result_ready(raw.get("last_analysis_result")):
        return raw
    return None


def save_analysis_session(session_state: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    """Persist coach report to workspace disk and Supabase."""
    payload = _build_payload(session_state, st=st)
    if not payload:
        return {"local": "skipped", "cloud": "skipped"}
    ws = str(payload.get("workspace_id") or "daniel")
    local_ok = _save_local(payload, workspace_id=ws)
    cloud_ok = _save_cloud(payload)
    if st is not None and hasattr(st, "session_state"):
        ss = st.session_state
        ss["_analysis_session_save_local"] = local_ok
        ss["_analysis_session_save_cloud"] = cloud_ok
        ss["_analysis_session_save_path"] = str(_session_path(workspace_id=ws))
        ss["_analysis_session_saved_at"] = payload.get("saved_at")
    return {
        "local": "ok" if local_ok else "fail",
        "cloud": "ok" if cloud_ok else "fail",
    }


def restore_analysis_session(session_state: dict[str, Any], *, st: Any | None = None) -> bool:
    """Load last Upload analysis from cloud (preferred) or workspace disk."""
    if analysis_result_ready(session_state.get("last_analysis_result")):
        return False
    payload = _restore_from_cloud(st=st)
    source = "cloud"
    if payload is None:
        payload = _restore_from_local(workspace_id=_active_workspace_id(st=st))
        source = "local"
    if payload is None:
        return False
    applied = _apply_payload(session_state, payload)
    if applied and st is not None and hasattr(st, "session_state"):
        st.session_state["_analysis_session_restore_source"] = source
        st.session_state["_analysis_session_restored_at"] = payload.get("saved_at")
    return applied


def clear_analysis_session(*, workspace_id: str | None = None) -> None:
    ws = workspace_id or _active_workspace_id()
    path = _session_path(workspace_id=ws)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass
    try:
        from suite_account import forget_saved_item

        forget_saved_item("music", _ITEM_TYPE, _ITEM_KEY)
    except Exception:
        pass

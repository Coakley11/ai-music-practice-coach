"""Practice Log — local file + Supabase saved_item for cross-device / reboot survival."""

from __future__ import annotations

import json
from typing import Any

APP_ID = "music"
PRACTICE_LOG_ITEM_TYPE = "practice_log"
PRACTICE_LOG_ITEM_KEY = "workspace_practice_log"
_TRACE_KEY = "_practice_log_persist_trace"


def _resolve_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import get_active_workspace_id, normalize_workspace_id

        if st is not None and hasattr(st, "session_state"):
            ss = st.session_state
            if isinstance(ss, dict):
                raw = ss.get("_suite_active_workspace_id")
                if raw not in (None, ""):
                    return normalize_workspace_id(str(raw))
        return normalize_workspace_id(get_active_workspace_id(st))
    except Exception:
        return "daniel"


def _local_path(*, st: Any | None = None):
    from music_workspace_paths import music_data_path

    ws = _resolve_workspace_id(st=st)
    return music_data_path("practice_history", ws)


def _append_trace(st: Any | None, event: dict[str, Any]) -> None:
    if st is None:
        return
    try:
        ss = st.session_state if hasattr(st, "session_state") else st
        if not isinstance(ss, dict):
            return
        trace = ss.get(_TRACE_KEY)
        if not isinstance(trace, list):
            trace = []
        trace.append(dict(event))
        ss[_TRACE_KEY] = trace[-12:]
    except Exception:
        pass


def _load_local_logs(*, st: Any | None = None) -> list[dict[str, Any]]:
    path = _local_path(st=st)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def _save_local_logs(logs: list[dict[str, Any]], *, st: Any | None = None) -> int:
    path = _local_path(st=st)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    return len(logs)


def _parse_updated_at(entry: dict[str, Any]) -> str:
    return str(entry.get("updated_at") or entry.get("created_at") or entry.get("date") or "")


def _entry_session_id(entry: dict[str, Any]) -> str:
    sid = str(entry.get("session_id") or "").strip()
    if sid:
        return sid
    try:
        from practice_log_state import deterministic_session_id, migrate_practice_log_entry

        return str(migrate_practice_log_entry(entry).get("session_id") or deterministic_session_id(entry))
    except Exception:
        return ""


def _merge_logs(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge by session_id; higher updated_at wins. Migrate legacy rows first."""
    try:
        from practice_log_state import migrate_practice_log_entry
    except ImportError:
        migrate_practice_log_entry = lambda e: dict(e)  # type: ignore[misc,assignment]

    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            row = migrate_practice_log_entry(entry)
            sid = _entry_session_id(row)
            if not sid:
                sid = json.dumps(row, sort_keys=True, default=str)
            prev = merged.get(sid)
            if prev is None or _parse_updated_at(row) >= _parse_updated_at(prev):
                merged[sid] = row

    out = list(merged.values())
    out.sort(
        key=lambda e: (
            str(e.get("date") or ""),
            _parse_updated_at(e),
            str(e.get("session_id") or ""),
        ),
        reverse=True,
    )
    return out


def _load_cloud_logs(*, st: Any | None = None) -> list[dict[str, Any]]:
    cloud: list[dict[str, Any]] = []
    try:
        from studio_history_cloud import cloud_enabled, list_history_items

        if not cloud_enabled():
            return []
        rows, _err = list_history_items(item_type=PRACTICE_LOG_ITEM_TYPE, st=st, limit=5)
        for row in rows or []:
            payload = row.get("payload")
            if isinstance(payload, dict):
                entries = payload.get("entries")
                if isinstance(entries, list):
                    cloud.extend(e for e in entries if isinstance(e, dict))
    except Exception:
        pass
    return cloud


def load_practice_logs(*, st: Any | None = None) -> list[dict[str, Any]]:
    """Load practice log entries from local disk and cloud (merged, deduped)."""
    ws = _resolve_workspace_id(st=st)
    local = _load_local_logs(st=st)
    cloud = _load_cloud_logs(st=st)
    merged = _merge_logs(local, cloud)
    try:
        from practice_log_state import is_tombstone, normalize_practice_log_entries

        visible = normalize_practice_log_entries(merged)
        tombstone_count = sum(1 for row in merged if is_tombstone(row))
    except Exception:
        visible = merged
        tombstone_count = 0
    _append_trace(
        st,
        {
            "phase": "load",
            "workspace_id": ws,
            "local_path": str(_local_path(st=st)),
            "local_raw_count": len(local),
            "cloud_raw_count": len(cloud),
            "merged_raw_count": len(merged),
            "visible_count": len(visible),
            "tombstone_count": tombstone_count,
        },
    )
    return merged


def save_practice_logs(logs: list[dict[str, Any]], *, st: Any | None = None) -> tuple[bool, str]:
    """Persist practice log to local disk and cloud saved_item."""
    ws = _resolve_workspace_id(st=st)
    incoming = [e for e in (logs or []) if isinstance(e, dict)]
    local_before = _load_local_logs(st=st)
    safe = _merge_logs(local_before, incoming)
    local_path = _local_path(st=st)
    try:
        written_count = _save_local_logs(safe, st=st)
    except Exception as exc:
        _append_trace(
            st,
            {
                "phase": "save",
                "workspace_id": ws,
                "local_path": str(local_path),
                "before_count": len(local_before),
                "incoming_count": len(incoming),
                "merged_count": len(safe),
                "local_write_count": 0,
                "local_ok": False,
                "error": str(exc),
            },
        )
        return False, f"local_write_failed:{exc}"
    cloud_ok = True
    cloud_err = ""
    cloud_count = 0
    try:
        from studio_history_cloud import active_workspace_id, cloud_enabled, save_history_item

        if cloud_enabled():
            ok, err = save_history_item(
                item_type=PRACTICE_LOG_ITEM_TYPE,
                item_key=PRACTICE_LOG_ITEM_KEY,
                title="Practice Log",
                payload={
                    "workspace_id": active_workspace_id(st=st),
                    "entries": safe,
                },
            )
            cloud_ok = bool(ok)
            cloud_err = str(err or "")
            cloud_count = len(safe) if cloud_ok else 0
    except Exception as exc:
        cloud_ok = False
        cloud_err = str(exc)
    _append_trace(
        st,
        {
            "phase": "save",
            "workspace_id": ws,
            "local_path": str(local_path),
            "before_count": len(local_before),
            "incoming_count": len(incoming),
            "merged_count": len(safe),
            "local_write_count": written_count,
            "local_ok": True,
            "cloud_ok": cloud_ok,
            "cloud_write_count": cloud_count,
            "cloud_error": cloud_err or None,
        },
    )
    if st is not None:
        try:
            ss = st.session_state if hasattr(st, "session_state") else st
            if isinstance(ss, dict):
                ss["_practice_log_last_save_cloud"] = cloud_ok
                ss["_practice_log_last_save_cloud_error"] = cloud_err or None
                ss["_practice_log_last_save_local_path"] = str(local_path)
                ss["_practice_log_last_save_workspace"] = ws
        except Exception:
            pass
    if not cloud_ok and cloud_err:
        return cloud_ok, cloud_err
    return True, cloud_err

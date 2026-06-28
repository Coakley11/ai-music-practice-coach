"""Practice Log — local file + Supabase saved_item for cross-device / reboot survival."""

from __future__ import annotations

import json
import os
from typing import Any

APP_ID = "music"
PRACTICE_LOG_ITEM_TYPE = "practice_log"
PRACTICE_LOG_ITEM_KEY = "workspace_practice_log"
PRACTICE_LOG_PERSIST_VERSION = "practice-log-persist-v3-cloud-readback-2026-06-27"
_TRACE_KEY = "_practice_log_persist_trace"


def _resolve_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import resolve_workspace_id

        return resolve_workspace_id(st=st)
    except Exception:
        return "daniel"


def _cloud_authoritative() -> bool:
    """When Supabase is configured, cloud is the durable store (Streamlit Cloud local disk is unreliable)."""
    try:
        from studio_history_cloud import cloud_enabled

        return bool(cloud_enabled())
    except Exception:
        return False


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


def _save_local_logs(logs: list[dict[str, Any]], *, st: Any | None = None) -> tuple[int, str]:
    path = _local_path(st=st)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(logs, indent=2)
        path.write_text(payload, encoding="utf-8")
        try:
            with path.open("r+", encoding="utf-8") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        readback = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(readback, list):
            return 0, "local_readback_not_list"
        if len(readback) < len(logs):
            return len(readback), "local_readback_short"
        return len(readback), ""
    except Exception as exc:
        return 0, str(exc)


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


def _load_cloud_logs(*, st: Any | None = None) -> tuple[list[dict[str, Any]], str | None]:
    cloud: list[dict[str, Any]] = []
    try:
        from studio_history_cloud import cloud_enabled, list_history_items

        if not cloud_enabled():
            return [], None
        rows, err = list_history_items(item_type=PRACTICE_LOG_ITEM_TYPE, st=st, limit=20)
        for row in rows or []:
            payload = row.get("payload")
            if isinstance(payload, dict):
                entries = payload.get("entries")
                if isinstance(entries, list):
                    cloud.extend(e for e in entries if isinstance(e, dict))
        return cloud, err
    except Exception as exc:
        return [], str(exc)


def load_practice_logs(*, st: Any | None = None) -> list[dict[str, Any]]:
    """Load practice log entries from local disk and cloud (merged, deduped)."""
    ws = _resolve_workspace_id(st=st)
    ss = None
    if st is not None and hasattr(st, "session_state") and isinstance(st.session_state, dict):
        ss = st.session_state
        if ss.get("_practice_log_load_workspace_before_restore") in (None, ""):
            ss["_practice_log_load_workspace_before_restore"] = ws
        ss["_practice_log_load_workspace_after_restore"] = ws

    local = _load_local_logs(st=st)
    cloud, cloud_load_err = _load_cloud_logs(st=st)
    merged = _merge_logs(local, cloud)
    try:
        from practice_log_state import is_tombstone, normalize_practice_log_entries

        visible = normalize_practice_log_entries(merged)
        tombstone_count = sum(1 for row in merged if is_tombstone(row))
    except Exception:
        visible = merged
        tombstone_count = 0

    cloud_enabled_flag = False
    cloud_block = None
    try:
        from studio_history_cloud import cloud_block_reason, cloud_enabled

        cloud_enabled_flag = bool(cloud_enabled())
        cloud_block = cloud_block_reason()
    except Exception:
        pass

    _append_trace(
        st,
        {
            "phase": "load",
            "persist_version": PRACTICE_LOG_PERSIST_VERSION,
            "workspace_id": ws,
            "local_path": str(_local_path(st=st)),
            "local_raw_count": len(local),
            "cloud_raw_count": len(cloud),
            "cloud_load_error": cloud_load_err,
            "cloud_enabled": cloud_enabled_flag,
            "cloud_block_reason": cloud_block,
            "merged_raw_count": len(merged),
            "visible_count": len(visible),
            "tombstone_count": tombstone_count,
            "workspace_ready": bool(ss.get("_suite_workspace_initialized")) if ss else None,
            "restore_phase_complete": bool(ss.get("_music_restore_phase_complete")) if ss else None,
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
    written_count, local_err = _save_local_logs(safe, st=st)
    local_ok = written_count >= len(safe) and not local_err

    cloud_ok = True
    cloud_err = ""
    cloud_count = 0
    cloud_readback_count = 0
    cloud_enabled_flag = False
    cloud_block = None
    try:
        from studio_history_cloud import cloud_block_reason, cloud_enabled, save_history_item

        cloud_enabled_flag = bool(cloud_enabled())
        cloud_block = cloud_block_reason()
        if cloud_enabled_flag:
            ok, err = save_history_item(
                item_type=PRACTICE_LOG_ITEM_TYPE,
                item_key=PRACTICE_LOG_ITEM_KEY,
                title="Practice Log",
                payload={
                    "workspace_id": ws,
                    "entries": safe,
                },
            )
            cloud_ok = bool(ok)
            cloud_err = str(err or "")
            if cloud_ok:
                cloud_count = len(safe)
                cloud_after, cloud_load_err = _load_cloud_logs(st=st)
                cloud_readback_count = len(cloud_after)
                if cloud_readback_count < len(safe):
                    cloud_err = cloud_load_err or f"cloud_readback_short:{cloud_readback_count}<{len(safe)}"
    except Exception as exc:
        cloud_ok = False
        cloud_err = str(exc)

    if _cloud_authoritative():
        overall_ok = bool(cloud_ok)
        overall_err = cloud_err or ("" if overall_ok else "cloud_save_failed")
    else:
        overall_ok = bool(local_ok)
        overall_err = local_err or (cloud_err if not cloud_ok and cloud_err else "")

    _append_trace(
        st,
        {
            "phase": "save",
            "persist_version": PRACTICE_LOG_PERSIST_VERSION,
            "workspace_id": ws,
            "local_path": str(local_path),
            "before_count": len(local_before),
            "incoming_count": len(incoming),
            "merged_count": len(safe),
            "local_write_count": written_count,
            "local_ok": local_ok,
            "local_error": local_err or None,
            "cloud_enabled": cloud_enabled_flag,
            "cloud_block_reason": cloud_block,
            "cloud_ok": cloud_ok,
            "cloud_write_count": cloud_count,
            "cloud_readback_count": cloud_readback_count,
            "cloud_error": cloud_err or None,
            "overall_ok": overall_ok,
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
                ss["_practice_log_last_save_local_ok"] = local_ok
                ss["_practice_log_last_save_local_error"] = local_err or None
                ss["_practice_log_last_save_entry_count"] = len(safe)
                last_sid = ""
                for row in safe:
                    sid = str(row.get("session_id") or "").strip()
                    if sid:
                        last_sid = sid
                ss["_practice_log_last_save_session_id"] = last_sid
        except Exception:
            pass
    return overall_ok, overall_err

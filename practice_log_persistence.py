"""Practice Log — local file + Supabase saved_item for cross-device / reboot survival."""

from __future__ import annotations

import json
from typing import Any

APP_ID = "music"
PRACTICE_LOG_ITEM_TYPE = "practice_log"
PRACTICE_LOG_ITEM_KEY = "workspace_practice_log"


def _local_path():
    from music_workspace_paths import music_data_path

    return music_data_path("practice_history")


def _load_local_logs() -> list[dict[str, Any]]:
    path = _local_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def _save_local_logs(logs: list[dict[str, Any]]) -> None:
    path = _local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(logs, indent=2), encoding="utf-8")


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
        from practice_log_state import is_tombstone, migrate_practice_log_entry
    except ImportError:
        migrate_practice_log_entry = lambda e: dict(e)  # type: ignore[misc,assignment]
        is_tombstone = lambda e: bool(e.get("deleted"))  # type: ignore[misc,assignment]

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


def load_practice_logs(*, st: Any | None = None) -> list[dict[str, Any]]:
    """Load practice log entries from local disk and cloud (merged, deduped)."""
    local = _load_local_logs()
    cloud: list[dict[str, Any]] = []
    try:
        from studio_history_cloud import cloud_enabled, list_history_items

        if cloud_enabled():
            rows, _err = list_history_items(item_type=PRACTICE_LOG_ITEM_TYPE, st=st, limit=5)
            for row in rows or []:
                payload = row.get("payload")
                if isinstance(payload, dict):
                    entries = payload.get("entries")
                    if isinstance(entries, list):
                        cloud.extend(e for e in entries if isinstance(e, dict))
    except Exception:
        pass
    return _merge_logs(local, cloud)


def save_practice_logs(logs: list[dict[str, Any]], *, st: Any | None = None) -> tuple[bool, str]:
    """Persist practice log to local disk and cloud saved_item."""
    safe = _merge_logs([e for e in (logs or []) if isinstance(e, dict)])
    try:
        _save_local_logs(safe)
    except Exception as exc:
        return False, f"local_write_failed:{exc}"
    cloud_ok = True
    cloud_err = ""
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
    except Exception as exc:
        cloud_ok = False
        cloud_err = str(exc)
    if st is not None:
        try:
            st.session_state["_practice_log_last_save_cloud"] = cloud_ok
            st.session_state["_practice_log_last_save_cloud_error"] = cloud_err or None
        except Exception:
            pass
    return cloud_ok, cloud_err

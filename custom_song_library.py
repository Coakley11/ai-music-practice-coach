"""Workspace-scoped Supabase library for saved custom songs (CPL progressions)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from studio_history_cloud import active_workspace_id, cloud_block_reason, cloud_enabled, widget_key_suffix

APP_ID = "music"
ITEM_TYPE = "custom_song"
FLASH_KEY = "custom_song_library_flash"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _song_item_key(song_id: str) -> str:
    sid = str(song_id or "").strip()
    return f"custom_{sid}" if sid else ""


def _format_saved_at(ts: float | int | str | None) -> str:
    if ts is None:
        return ""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        else:
            raw = str(ts).strip()
            if not raw:
                return ""
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(ts or "")


def progression_row_summary(data: dict[str, Any]) -> str:
    key = str(data.get("original_key_center") or "C").strip() or "C"
    style = str(data.get("progression_style") or "Custom").strip() or "Custom"
    bpm = int(data.get("bpm") or 0)
    parts = [key, style]
    if bpm:
        parts.append(f"{bpm} BPM")
    tags = data.get("tags")
    if isinstance(tags, list) and tags:
        parts.append(", ".join(str(t) for t in tags[:3]))
    return " · ".join(parts)


def list_cloud_custom_songs(*, st: Any | None = None, limit: int = 200) -> tuple[list[dict[str, Any]], str | None]:
    if not cloud_enabled():
        return [], cloud_block_reason()
    try:
        from suite_account import load_saved_items

        rows = load_saved_items(app=APP_ID, item_type=ITEM_TYPE, limit=limit)
        ws = active_workspace_id(st=st).lower()
        out: list[dict[str, Any]] = []
        for row in rows or []:
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            row_ws = str(payload.get("workspace_id") or "daniel").strip().lower()
            if row_ws != ws:
                continue
            song = payload.get("progression") if isinstance(payload.get("progression"), dict) else {}
            if not song.get("name"):
                continue
            out.append(
                {
                    "item_key": str(row.get("item_key") or ""),
                    "title": str(row.get("title") or song.get("name") or ""),
                    "payload": payload,
                    "updated_at": row.get("updated_at"),
                }
            )
        out.sort(
            key=lambda r: float((r.get("payload") or {}).get("progression", {}).get("updated_at") or 0),
            reverse=True,
        )
        return out, None
    except Exception as exc:
        return [], str(exc)


def upsert_custom_song_to_cloud(
    name: str,
    progression: dict[str, Any],
    *,
    st: Any | None = None,
    tags: list[str] | None = None,
) -> tuple[bool, str, str | None]:
    """Save one custom song to the workspace cloud library."""
    if not cloud_enabled():
        return False, "", cloud_block_reason() or "cloud_disabled"
    prog = _json_safe(progression if isinstance(progression, dict) else {})
    save_name = str(prog.get("name") or name or "").strip()
    if not save_name:
        return False, "", "missing_title"
    song_id = str(prog.get("id") or "").strip()
    if not song_id:
        return False, "", "missing_song_id"
    if tags:
        prog["tags"] = list(tags)
    item_key = _song_item_key(song_id)
    if not item_key:
        return False, "", "missing_item_key"
    payload = {
        "workspace_id": active_workspace_id(st=st),
        "progression": prog,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from suite_account import remember_saved_item

        remember_saved_item(
            APP_ID,
            ITEM_TYPE,
            item_key,
            title=save_name,
            payload=payload,
        )
        return True, item_key, None
    except Exception as exc:
        return False, "", str(exc)


def delete_custom_song_from_cloud(song_id: str, *, st: Any | None = None) -> tuple[bool, str | None]:
    if not cloud_enabled():
        return False, cloud_block_reason() or "cloud_disabled"
    item_key = _song_item_key(song_id)
    if not item_key:
        return False, "missing_item_key"
    try:
        from suite_account import forget_saved_item

        forget_saved_item(APP_ID, ITEM_TYPE, item_key)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _merge_progression_store(local: dict[str, Any], cloud_rows: list[dict[str, Any]]) -> dict[str, Any]:
    merged = copy.deepcopy(local if isinstance(local, dict) else {})
    for row in cloud_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        prog = payload.get("progression") if isinstance(payload.get("progression"), dict) else {}
        name = str(prog.get("name") or row.get("title") or "").strip()
        if not name:
            continue
        local_row = merged.get(name) if isinstance(merged.get(name), dict) else {}
        cloud_ts = float(prog.get("updated_at") or 0)
        local_ts = float(local_row.get("updated_at") or 0) if isinstance(local_row, dict) else 0.0
        if not local_row or cloud_ts >= local_ts:
            merged[name] = copy.deepcopy(prog)
    return merged


def merge_custom_songs_from_cloud(session_state: dict[str, Any], *, st: Any | None = None) -> bool:
    """Hydrate ``cpl_saved_progressions`` from the cloud custom-song library."""
    if not cloud_enabled():
        return False
    rows, _err = list_cloud_custom_songs(st=st)
    if not rows:
        return False
    from custom_progression_lab import CPL_SAVED_KEY

    local = session_state.get(CPL_SAVED_KEY) if isinstance(session_state.get(CPL_SAVED_KEY), dict) else {}
    merged = _merge_progression_store(local, rows)
    if merged != local:
        session_state[CPL_SAVED_KEY] = merged
        return True
    return False


def sync_custom_songs_to_cloud(session_state: dict[str, Any], *, st: Any | None = None) -> int:
    """Push all in-session custom songs to cloud (best-effort). Returns upsert count."""
    if not cloud_enabled():
        return 0
    from custom_progression_lab import CPL_SAVED_KEY

    store = session_state.get(CPL_SAVED_KEY) if isinstance(session_state.get(CPL_SAVED_KEY), dict) else {}
    count = 0
    for _name, data in store.items():
        if not isinstance(data, dict):
            continue
        ok, _key, _err = upsert_custom_song_to_cloud(str(data.get("name") or _name), data, st=st)
        if ok:
            count += 1
    return count


def row_widget_suffix(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    prog = payload.get("progression") if isinstance(payload.get("progression"), dict) else {}
    song_id = str(prog.get("id") or row.get("item_key") or "")
    return widget_key_suffix(song_id)

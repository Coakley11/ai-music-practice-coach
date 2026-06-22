"""Workspace-scoped Supabase history library helpers (Upload + Multitrack)."""

from __future__ import annotations

import base64
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

APP_ID = "music"
MAX_EMBED_AUDIO_BYTES = 512_000
MAX_PER_TRACK_EMBED_BYTES = 256_000
MAX_TOTAL_TRACK_EMBED_BYTES = 512_000


def active_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import get_active_workspace_id, normalize_workspace_id

        return normalize_workspace_id(get_active_workspace_id(st))
    except Exception:
        return "daniel"


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def new_history_item_key(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def widget_key_suffix(item_key: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(item_key or "item"))[:48]


def encode_audio_if_safe(data: bytes | bytearray | None, *, max_bytes: int = MAX_EMBED_AUDIO_BYTES) -> tuple[str | None, str | None]:
    if not data:
        return None, None
    raw = bytes(data)
    if len(raw) > max_bytes:
        return None, f"audio_too_large_{len(raw)}"
    return base64.b64encode(raw).decode("ascii"), None


def decode_audio_b64(b64: str | None) -> bytes | None:
    if not isinstance(b64, str) or not b64.strip():
        return None
    try:
        return base64.b64decode(b64.encode("ascii"))
    except Exception:
        return None


def cloud_enabled() -> bool:
    try:
        from suite_storage_config import cloud_storage_enabled
    except ImportError:
        return False
    return bool(cloud_storage_enabled())


def cloud_block_reason() -> str | None:
    if cloud_enabled():
        return None
    try:
        from suite_storage_config import cloud_storage_enabled, get_cloud_config

        cfg = get_cloud_config()
        if cfg is None:
            return "Supabase is not configured on this deployment."
    except Exception:
        pass
    return "Cloud storage is disabled. Sign in to save history items."


def _workspace_rows(rows: list[dict[str, Any]] | None, *, workspace_id: str) -> list[dict[str, Any]]:
    ws = str(workspace_id or "daniel").strip().lower()
    out: list[dict[str, Any]] = []
    for row in rows or []:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        row_ws = str(payload.get("workspace_id") or "daniel").strip().lower()
        if row_ws != ws:
            continue
        out.append(row)
    return out


def list_history_items(*, item_type: str, st: Any | None = None, limit: int = 50) -> tuple[list[dict[str, Any]], str | None]:
    if not cloud_enabled():
        return [], cloud_block_reason()
    try:
        from suite_account import load_saved_items

        rows = load_saved_items(app=APP_ID, item_type=item_type, limit=limit)
    except Exception as exc:
        return [], str(exc)
    ws = active_workspace_id(st=st)
    filtered = _workspace_rows(rows, workspace_id=ws)
    filtered.sort(key=lambda r: str(r.get("updated_at") or r.get("payload", {}).get("saved_at") or ""), reverse=True)
    return filtered, None


def save_history_item(
    *,
    item_type: str,
    item_key: str,
    title: str,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    if not cloud_enabled():
        return False, cloud_block_reason() or "cloud_disabled"
    title_clean = str(title or "").strip()
    key_clean = str(item_key or "").strip()
    if not title_clean:
        return False, "missing_title"
    if not key_clean:
        return False, "missing_item_key"
    try:
        from suite_account import remember_saved_item

        safe_payload = json_safe(payload)
        result = remember_saved_item(
            APP_ID,
            item_type,
            key_clean,
            title=title_clean[:120],
            payload=safe_payload,
        )
        if isinstance(result, dict) and str(result.get("write_mode") or "") == "skipped":
            return False, "cloud_write_skipped"
        return True, ""
    except Exception as exc:
        return False, str(exc)


def delete_history_item(*, item_type: str, item_key: str) -> tuple[bool, str]:
    if not item_key:
        return False, "missing_item_key"
    try:
        from suite_account import forget_saved_item

        forget_saved_item(APP_ID, item_type, item_key)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def format_saved_at(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw[:19]

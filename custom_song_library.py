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


# What the last cloud read found (shown in the library so a missing song is explainable).
LAST_CLOUD_MERGE: dict[str, Any] = {"error": "", "found": 0, "other_workspace": 0, "truncated": False}

# Upper bound on rows read for one listing. Reached only by an unusually large library, in
# which case the listing says so (``truncated``) instead of silently hiding songs.
MAX_LISTED_ROWS = 2000
_PAGE_SIZE_CAP = 200

# Song ids seen in the last cloud listing regardless of workspace tag; a re-upload must never
# write over a row that exists under a mismatched tag.
LAST_CLOUD_ALL_IDS: set[str] = set()


def cloud_storage_status() -> dict[str, Any]:
    """Is a save right now durable? ``durable`` is True only when the cloud will really hold it.

    ``state`` is one of ``durable``, ``not_configured`` (no Supabase config on this
    deployment) or ``identity_unavailable`` (configured, but the account row could not be
    resolved, so writes would fail).
    """
    if not cloud_enabled():
        return {
            "state": "not_configured",
            "durable": False,
            "message": (
                "Cloud storage is not configured on this deployment. Custom songs are kept on this "
                "server only and are lost when the app restarts."
            ),
        }
    try:
        from suite_user import account_mode, last_account_error

        if account_mode() != "cloud":
            reason = last_account_error()
            return {
                "state": "identity_unavailable",
                "durable": False,
                "message": (
                    "Cloud storage is configured but your account could not be reached"
                    + (f" ({reason})" if reason else "")
                    + ". Songs are kept on this server only until it reconnects."
                ),
            }
    except ImportError:
        pass
    return {"state": "durable", "durable": True, "message": "Custom songs are saved to your cloud library."}


def describe_save_status(state: str, error: str = "") -> tuple[str, str]:
    """``(level, text)`` for what the user is told after a save. Only ``durable`` is success."""
    detail = str(error or "").strip()
    if state == "durable":
        return "success", "Saved to your custom library and your cloud library."
    if state == "failed":
        return (
            "error",
            "Not saved durably: the cloud copy failed"
            + (f" ({detail})" if detail else "")
            + ". This song is only on this server for now and will be lost when the app restarts. "
            "Save again once the connection is back.",
        )
    if state == "identity_unavailable":
        return (
            "warning",
            "Saved on this server only: cloud storage is configured but your account could not be "
            "reached, so this song is not durable yet.",
        )
    if state == "not_configured":
        return (
            "warning",
            "Saved on this server only: cloud storage is not configured here, so this song will be "
            "lost when the app restarts.",
        )
    return "info", "Saved on this server. Cloud status unknown."


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


def _load_all_cloud_rows(*, st: Any | None, page_size: int) -> tuple[list[dict[str, Any]], bool]:
    """Every valid custom-song row for this account/workspace app, read page by page.

    The row limit is a *page* size, never a ceiling on how many songs are visible. Returns
    ``(rows, truncated)``; ``truncated`` is True only if ``MAX_LISTED_ROWS`` was reached.
    """
    from suite_account import load_saved_items

    rows: list[dict[str, Any]] = []
    page_size = max(1, min(int(page_size), _PAGE_SIZE_CAP))
    offset = 0
    while len(rows) < MAX_LISTED_ROWS:
        try:
            page = load_saved_items(
                app=APP_ID, item_type=ITEM_TYPE, limit=page_size, offset=offset, stable_order=True
            )
        except TypeError:
            # A storage backend without paging support: one page is all we can read.
            page = load_saved_items(app=APP_ID, item_type=ITEM_TYPE, limit=page_size)
            rows.extend(page or [])
            return rows, len(page or []) >= page_size
        page = list(page or [])
        rows.extend(page)
        if len(page) < page_size:
            return rows, False
        offset += page_size
    return rows, True


def list_cloud_custom_songs(*, st: Any | None = None, limit: int = 200) -> tuple[list[dict[str, Any]], str | None]:
    LAST_CLOUD_MERGE.update({"error": "", "found": 0, "other_workspace": 0, "truncated": False})
    if not cloud_enabled():
        return [], cloud_block_reason()
    try:
        from music_egress_config import saved_items_list_limit

        page_size = saved_items_list_limit(default=int(limit), st=st)
    except ImportError:
        page_size = int(limit)
    try:
        rows, truncated = _load_all_cloud_rows(st=st, page_size=page_size)
        LAST_CLOUD_ALL_IDS.clear()
        for _r in rows or []:
            _pl = _r.get("payload") if isinstance(_r.get("payload"), dict) else {}
            _pg = _pl.get("progression") if isinstance(_pl.get("progression"), dict) else {}
            _sid = str(_pg.get("id") or "").strip()
            if _sid:
                LAST_CLOUD_ALL_IDS.add(_sid)
        ws = active_workspace_id(st=st).lower()
        out: list[dict[str, Any]] = []
        other_workspace = 0
        for row in rows or []:
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            row_ws = str(payload.get("workspace_id") or "daniel").strip().lower()
            if row_ws != ws:
                other_workspace += 1
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
        LAST_CLOUD_MERGE.update({"found": len(out), "other_workspace": other_workspace, "truncated": truncated})
        return out, None
    except Exception as exc:
        LAST_CLOUD_MERGE["error"] = str(exc)[:200]
        return [], str(exc)


def discover_other_workspace_songs(*, st: Any | None = None) -> dict[str, int]:
    """Read-only: ``{workspace id: custom-song count}`` for this account's *other* workspaces.

    Explains an empty library after a restart: the workspace is recovered from a file that a
    restart can lose, so songs saved under another workspace look missing. Nothing is moved.
    Only rows of the signed-in account are counted (the query is scoped to its user id).
    """
    if not cloud_enabled():
        return {}
    try:
        from suite_account import count_saved_items_by_storage_app

        counts = count_saved_items_by_storage_app(ITEM_TYPE, app_prefix=APP_ID)
    except Exception:
        return {}
    active = active_workspace_id(st=st).lower()
    out: dict[str, int] = {}
    for storage_app, n in counts.items():
        ws = "daniel" if storage_app == APP_ID else storage_app.split("__", 1)[1].lower()
        if ws != active and n:
            out[ws] = int(n)
    return out


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
    status = cloud_storage_status()
    if not status["durable"]:
        return False, "", str(status["state"])
    try:
        from suite_account import remember_saved_item

        result = remember_saved_item(
            APP_ID,
            ITEM_TYPE,
            item_key,
            title=save_name,
            payload=payload,
        )
        if isinstance(result, dict) and str(result.get("write_mode") or "") == "skipped":
            return False, "", "cloud_write_skipped"
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

    def _prog_id(prog: dict[str, Any]) -> str:
        return str(prog.get("id") or "").strip()

    def _local_key_for_id(song_id: str) -> str | None:
        if not song_id:
            return None
        for key, row in merged.items():
            if isinstance(row, dict) and _prog_id(row) == song_id:
                return str(key)
        return None

    for row in cloud_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        prog = payload.get("progression") if isinstance(payload.get("progression"), dict) else {}
        name = str(prog.get("name") or row.get("title") or "").strip()
        if not name:
            continue
        song_id = _prog_id(prog)
        store_key = _local_key_for_id(song_id) if song_id else None
        if not store_key:
            store_key = name
            held = merged.get(store_key)
            held_id = _prog_id(held) if isinstance(held, dict) else ""
            if held_id and song_id and held_id != song_id:
                # A different song already uses this title here. Keep both (as saving does)
                # instead of letting the cloud copy replace the local one.
                n = 2
                while isinstance(merged.get(f"{name} ({n})"), dict) and _prog_id(merged[f"{name} ({n})"]) not in ("", song_id):
                    n += 1
                store_key = f"{name} ({n})"
        local_row = merged.get(store_key) if isinstance(merged.get(store_key), dict) else {}
        cloud_ts = float(prog.get("updated_at") or 0)
        local_ts = float(local_row.get("updated_at") or 0) if isinstance(local_row, dict) else 0.0
        if not local_row or cloud_ts >= local_ts:
            merged[store_key] = copy.deepcopy(prog)
    return merged


def merge_custom_songs_from_cloud(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    force: bool = False,
) -> bool:
    """Hydrate ``cpl_saved_progressions`` from the cloud custom-song library."""
    try:
        from music_egress_config import note_custom_song_cloud_merged, should_merge_custom_songs_from_cloud

        if not should_merge_custom_songs_from_cloud(session_state, force=force):
            return False
    except ImportError:
        pass
    if not cloud_enabled():
        return False
    rows, _err = list_cloud_custom_songs(st=st)
    if _err:
        LAST_CLOUD_MERGE["error"] = str(_err)[:200]
    if not rows:
        return False
    from custom_progression_lab import CPL_SAVED_KEY

    local = session_state.get(CPL_SAVED_KEY) if isinstance(session_state.get(CPL_SAVED_KEY), dict) else {}
    merged = _merge_progression_store(local, rows)
    if merged != local:
        session_state[CPL_SAVED_KEY] = merged
        try:
            from music_egress_config import note_custom_song_cloud_merged

            note_custom_song_cloud_merged(session_state)
        except ImportError:
            pass
        return True
    try:
        from music_egress_config import note_custom_song_cloud_merged

        note_custom_song_cloud_merged(session_state)
    except ImportError:
        pass
    return False


def push_unsynced_custom_songs(session_state: dict[str, Any], *, st: Any | None = None) -> tuple[int, str | None]:
    """Upload local custom songs the cloud does not have yet. Additive only.

    A song saved while the cloud was unreachable would otherwise exist only in this server's
    memory/disk. This never overwrites or removes anything in the cloud: only ids that are
    absent from a successful cloud listing are written. Returns ``(uploaded, error)``.
    """
    status = cloud_storage_status()
    if not status["durable"]:
        return 0, str(status["state"])
    rows, err = list_cloud_custom_songs(st=st, limit=_PAGE_SIZE_CAP)
    if err:
        return 0, err
    if LAST_CLOUD_MERGE.get("truncated"):
        # Not every cloud id is known, so "absent from the cloud" cannot be trusted.
        return 0, "cloud_listing_truncated"
    cloud_ids = set(LAST_CLOUD_ALL_IDS)
    from custom_progression_lab import CPL_SAVED_KEY

    store = session_state.get(CPL_SAVED_KEY) if isinstance(session_state.get(CPL_SAVED_KEY), dict) else {}
    uploaded = 0
    last_error: str | None = None
    for name, data in store.items():
        if not isinstance(data, dict):
            continue
        sid = str(data.get("id") or "").strip()
        if not sid or sid in cloud_ids:
            continue
        ok, _key, e = upsert_custom_song_to_cloud(str(data.get("name") or name), data, st=st)
        if ok:
            uploaded += 1
        else:
            last_error = e or last_error
    return uploaded, last_error


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

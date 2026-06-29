"""Media catalog — local JSON cache + Supabase saved_item (metadata only, no blobs in envelope)."""

from __future__ import annotations

import json
import os
from typing import Any

from media_state import (
    MEDIA_CATALOG_VERSION,
    build_media_ami_payload_from_catalog,
    is_multitrack_tombstone,
    is_recording_tombstone,
    is_tone_take_tombstone,
    merge_catalog,
    migrate_multitrack_session,
    migrate_tone_take,
    migrate_uploaded_recording,
    new_multitrack_id,
    new_recording_id,
    new_tone_take_id,
    normalize_multitrack_sessions,
    normalize_tone_takes,
    normalize_uploaded_recordings,
    _utc_now_iso,
)

APP_ID = "music"
MEDIA_ITEM_TYPE = "music_media"
MEDIA_ITEM_KEY = "workspace_media_catalog"
MEDIA_PERSIST_VERSION = "media-persist-v1-2026-06-27"
_TRACE_KEY = "_media_persist_trace"
_CATALOG_SESSION_KEY = "_media_catalog_cache"


def _resolve_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import resolve_workspace_id

        return resolve_workspace_id(st=st)
    except Exception:
        return "daniel"


def _cloud_authoritative() -> bool:
    try:
        from studio_history_cloud import cloud_enabled

        return bool(cloud_enabled())
    except Exception:
        return False


def _local_path(*, st: Any | None = None):
    from music_workspace_paths import music_data_path

    ws = _resolve_workspace_id(st=st)
    return music_data_path("media_catalog", ws)


def _empty_catalog(*, workspace_id: str) -> dict[str, Any]:
    return {
        "version": MEDIA_CATALOG_VERSION,
        "workspace_id": workspace_id,
        "updated_at": _utc_now_iso(),
        "uploaded_recordings": [],
        "multitrack_sessions": [],
        "tone_takes": [],
    }


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


def _load_local_catalog(*, st: Any | None = None) -> dict[str, Any]:
    path = _local_path(st=st)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_local_catalog(catalog: dict[str, Any], *, st: Any | None = None) -> tuple[bool, str]:
    path = _local_path(st=st)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(catalog, indent=2)
        path.write_text(payload, encoding="utf-8")
        try:
            with path.open("r+", encoding="utf-8") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        readback = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(readback, dict):
            return False, "local_readback_not_dict"
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _load_cloud_catalog(*, st: Any | None = None) -> tuple[dict[str, Any], str | None]:
    try:
        from studio_history_cloud import cloud_enabled, list_history_items

        if not cloud_enabled():
            return {}, None
        rows, err = list_history_items(item_type=MEDIA_ITEM_TYPE, st=st, limit=10)
        for row in rows or []:
            if str(row.get("item_key") or "") != MEDIA_ITEM_KEY:
                continue
            payload = row.get("payload")
            if isinstance(payload, dict):
                return payload, err
        return {}, err
    except Exception as exc:
        return {}, str(exc)


def _save_cloud_catalog(catalog: dict[str, Any], *, st: Any | None = None) -> tuple[bool, str]:
    try:
        from studio_history_cloud import cloud_enabled, save_history_item

        if not cloud_enabled():
            return False, "cloud_disabled"
        ok, err = save_history_item(
            item_type=MEDIA_ITEM_TYPE,
            item_key=MEDIA_ITEM_KEY,
            title="Music media catalog",
            payload=catalog,
        )
        return bool(ok), str(err or "")
    except Exception as exc:
        return False, str(exc)


def load_media_catalog(*, st: Any | None = None) -> dict[str, Any]:
    """Load merged media catalog from local cache and cloud saved_item."""
    ws = _resolve_workspace_id(st=st)
    local = _load_local_catalog(st=st)
    cloud, cloud_load_err = _load_cloud_catalog(st=st)

    # Empty cloud must not erase local-only data on merge.
    if not cloud and local:
        merged = merge_catalog(local, _empty_catalog(workspace_id=ws))
    else:
        merged = merge_catalog(local, cloud)

    if not merged.get("workspace_id"):
        merged["workspace_id"] = ws

    uploads_raw = merged.get("uploaded_recordings") if isinstance(merged.get("uploaded_recordings"), list) else []
    mt_raw = merged.get("multitrack_sessions") if isinstance(merged.get("multitrack_sessions"), list) else []
    tone_raw = merged.get("tone_takes") if isinstance(merged.get("tone_takes"), list) else []
    tomb_rec = sum(1 for row in uploads_raw if isinstance(row, dict) and is_recording_tombstone(row))
    tomb_mt = sum(1 for row in mt_raw if isinstance(row, dict) and is_multitrack_tombstone(row))
    tomb_tone = sum(1 for row in tone_raw if isinstance(row, dict) and is_tone_take_tombstone(row))

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
            "persist_version": MEDIA_PERSIST_VERSION,
            "workspace_id": ws,
            "local_path": str(_local_path(st=st)),
            "local_upload_count": len(local.get("uploaded_recordings") or []) if isinstance(local.get("uploaded_recordings"), list) else 0,
            "local_multitrack_count": len(local.get("multitrack_sessions") or []) if isinstance(local.get("multitrack_sessions"), list) else 0,
            "local_tone_take_count": len(local.get("tone_takes") or []) if isinstance(local.get("tone_takes"), list) else 0,
            "cloud_upload_count": len(cloud.get("uploaded_recordings") or []) if isinstance(cloud.get("uploaded_recordings"), list) else 0,
            "cloud_multitrack_count": len(cloud.get("multitrack_sessions") or []) if isinstance(cloud.get("multitrack_sessions"), list) else 0,
            "cloud_tone_take_count": len(cloud.get("tone_takes") or []) if isinstance(cloud.get("tone_takes"), list) else 0,
            "cloud_load_error": cloud_load_err,
            "cloud_enabled": cloud_enabled_flag,
            "cloud_block_reason": cloud_block,
            "merged_upload_count": len(uploads_raw),
            "merged_multitrack_count": len(mt_raw),
            "merged_tone_take_count": len(tone_raw),
            "visible_upload_count": len(normalize_uploaded_recordings(uploads_raw)),
            "visible_multitrack_count": len(normalize_multitrack_sessions(mt_raw)),
            "visible_tone_take_count": len(normalize_tone_takes(tone_raw)),
            "tombstone_recording_count": tomb_rec,
            "tombstone_multitrack_count": tomb_mt,
            "tombstone_tone_take_count": tomb_tone,
        },
    )

    if st is not None:
        try:
            ss = st.session_state if hasattr(st, "session_state") else st
            if isinstance(ss, dict):
                ss[_CATALOG_SESSION_KEY] = merged
        except Exception:
            pass

    return merged


def save_media_catalog(catalog: dict[str, Any], *, st: Any | None = None) -> dict[str, Any]:
    """Persist catalog to local cache and cloud; merge with existing local first."""
    ws = _resolve_workspace_id(st=st)
    local_before = _load_local_catalog(st=st)
    incoming = dict(catalog or {})
    incoming.setdefault("workspace_id", ws)
    incoming.setdefault("version", MEDIA_CATALOG_VERSION)
    incoming["updated_at"] = _utc_now_iso()

    safe = merge_catalog(local_before, incoming)
    safe["workspace_id"] = ws
    safe["updated_at"] = _utc_now_iso()

    local_ok, local_err = _save_local_catalog(safe, st=st)
    cloud_ok, cloud_err = _save_cloud_catalog(safe, st=st)

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
            "persist_version": MEDIA_PERSIST_VERSION,
            "workspace_id": ws,
            "local_path": str(_local_path(st=st)),
            "local_ok": local_ok,
            "local_error": local_err or None,
            "cloud_ok": cloud_ok,
            "cloud_error": cloud_err or None,
            "overall_ok": overall_ok,
            "overall_error": overall_err or None,
            "upload_count": len(safe.get("uploaded_recordings") or []),
            "multitrack_count": len(safe.get("multitrack_sessions") or []),
        },
    )

    if st is not None:
        try:
            ss = st.session_state if hasattr(st, "session_state") else st
            if isinstance(ss, dict):
                ss[_CATALOG_SESSION_KEY] = safe
                ss["_media_last_save_ok"] = overall_ok
                ss["_media_last_save_error"] = overall_err or None
        except Exception:
            pass

    return {
        "ok": overall_ok,
        "error": overall_err,
        "catalog": safe,
        "local_ok": local_ok,
        "cloud_ok": cloud_ok,
    }


def _catalog_from_st(st: Any | None, catalog: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(catalog, dict) and catalog:
        return catalog
    if st is not None:
        try:
            ss = st.session_state if hasattr(st, "session_state") else st
            if isinstance(ss, dict):
                cached = ss.get(_CATALOG_SESSION_KEY)
                if isinstance(cached, dict) and cached:
                    return cached
        except Exception:
            pass
    return load_media_catalog(st=st)


def _replace_recording(catalog: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(catalog)
    rows = list(out.get("uploaded_recordings") or [])
    rid = str(row.get("recording_id") or "")
    rows = [r for r in rows if str(r.get("recording_id") or "") != rid]
    rows.append(row)
    out["uploaded_recordings"] = rows
    return out


def _replace_multitrack(catalog: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(catalog)
    rows = list(out.get("multitrack_sessions") or [])
    mid = str(row.get("multitrack_id") or "")
    rows = [r for r in rows if str(r.get("multitrack_id") or "") != mid]
    rows.append(row)
    out["multitrack_sessions"] = rows
    return out


def _replace_tone_take(catalog: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = dict(catalog)
    rows = list(out.get("tone_takes") or [])
    tid = str(row.get("tone_take_id") or "")
    rows = [r for r in rows if str(r.get("tone_take_id") or "") != tid]
    rows.append(row)
    out["tone_takes"] = rows
    return out


def add_uploaded_recording(st: Any | None, fields: dict[str, Any]) -> dict[str, Any]:
    catalog = _catalog_from_st(st, None)
    now = _utc_now_iso()
    ws = _resolve_workspace_id(st=st)
    row = migrate_uploaded_recording(
        {
            **dict(fields or {}),
            "recording_id": new_recording_id(),
            "created_at": now,
            "updated_at": now,
            "workspace_id": ws,
            "deleted": False,
        }
    )
    updated = _replace_recording(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def update_uploaded_recording(
    st: Any | None,
    recording_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    rid = str(recording_id or "").strip()
    if not rid:
        return {}
    catalog = _catalog_from_st(st, None)
    rows = catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    existing = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("recording_id") or "") == rid:
            existing = migrate_uploaded_recording(row)
            break
    if not existing or is_recording_tombstone(existing):
        return {}
    merged = {**existing, **dict(updates or {}), "recording_id": rid, "updated_at": _utc_now_iso()}
    row = migrate_uploaded_recording(merged)
    updated = _replace_recording(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def delete_uploaded_recording(st: Any | None, recording_id: str) -> bool:
    rid = str(recording_id or "").strip()
    if not rid:
        return False
    catalog = _catalog_from_st(st, None)
    tomb = {
        "recording_id": rid,
        "deleted": True,
        "updated_at": _utc_now_iso(),
        "workspace_id": _resolve_workspace_id(st=st),
    }
    updated = _replace_recording(catalog, tomb)
    result = save_media_catalog(updated, st=st)
    return bool(result.get("ok"))


def add_multitrack_session(st: Any | None, fields: dict[str, Any]) -> dict[str, Any]:
    catalog = _catalog_from_st(st, None)
    now = _utc_now_iso()
    ws = _resolve_workspace_id(st=st)
    row = migrate_multitrack_session(
        {
            **dict(fields or {}),
            "multitrack_id": new_multitrack_id(),
            "created_at": now,
            "updated_at": now,
            "workspace_id": ws,
            "deleted": False,
        }
    )
    updated = _replace_multitrack(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def update_multitrack_session(
    st: Any | None,
    multitrack_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    mid = str(multitrack_id or "").strip()
    if not mid:
        return {}
    catalog = _catalog_from_st(st, None)
    rows = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    existing = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("multitrack_id") or "") == mid:
            existing = migrate_multitrack_session(row)
            break
    if not existing or is_multitrack_tombstone(existing):
        return {}
    merged = {**existing, **dict(updates or {}), "multitrack_id": mid, "updated_at": _utc_now_iso()}
    row = migrate_multitrack_session(merged)
    updated = _replace_multitrack(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def delete_multitrack_session(st: Any | None, multitrack_id: str) -> bool:
    mid = str(multitrack_id or "").strip()
    if not mid:
        return False
    catalog = _catalog_from_st(st, None)
    tomb = {
        "multitrack_id": mid,
        "deleted": True,
        "updated_at": _utc_now_iso(),
        "workspace_id": _resolve_workspace_id(st=st),
    }
    updated = _replace_multitrack(catalog, tomb)
    result = save_media_catalog(updated, st=st)
    return bool(result.get("ok"))


def add_tone_take(st: Any | None, fields: dict[str, Any]) -> dict[str, Any]:
    catalog = _catalog_from_st(st, None)
    now = _utc_now_iso()
    ws = _resolve_workspace_id(st=st)
    row = migrate_tone_take(
        {
            **dict(fields or {}),
            "tone_take_id": new_tone_take_id(),
            "created_at": now,
            "updated_at": now,
            "workspace_id": ws,
            "deleted": False,
        }
    )
    updated = _replace_tone_take(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def update_tone_take(
    st: Any | None,
    tone_take_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    tid = str(tone_take_id or "").strip()
    if not tid:
        return {}
    catalog = _catalog_from_st(st, None)
    rows = catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else []
    existing = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("tone_take_id") or "") == tid:
            existing = migrate_tone_take(row)
            break
    if not existing or is_tone_take_tombstone(existing):
        return {}
    merged = {**existing, **dict(updates or {}), "tone_take_id": tid, "updated_at": _utc_now_iso()}
    row = migrate_tone_take(merged)
    updated = _replace_tone_take(catalog, row)
    save_media_catalog(updated, st=st)
    return row


def delete_tone_take(st: Any | None, tone_take_id: str) -> bool:
    tid = str(tone_take_id or "").strip()
    if not tid:
        return False
    catalog = _catalog_from_st(st, None)
    now = _utc_now_iso()
    tomb = {
        "tone_take_id": tid,
        "deleted": True,
        "deleted_at": now,
        "updated_at": now,
        "workspace_id": _resolve_workspace_id(st=st),
    }
    updated = _replace_tone_take(catalog, tomb)
    result = save_media_catalog(updated, st=st)
    return bool(result.get("ok"))


def build_media_ami_payload(
    st: Any | None,
    catalog: dict[str, Any] | None = None,
    *,
    window_days: int = 30,
) -> dict[str, Any]:
    cat = _catalog_from_st(st, catalog)
    return build_media_ami_payload_from_catalog(cat, window_days=window_days)


# Re-export merge for tests
from media_state import merge_media_records  # noqa: E402

__all__ = [
    "MEDIA_ITEM_TYPE",
    "MEDIA_ITEM_KEY",
    "MEDIA_PERSIST_VERSION",
    "load_media_catalog",
    "save_media_catalog",
    "add_uploaded_recording",
    "update_uploaded_recording",
    "delete_uploaded_recording",
    "add_multitrack_session",
    "update_multitrack_session",
    "delete_multitrack_session",
    "add_tone_take",
    "update_tone_take",
    "delete_tone_take",
    "build_media_ami_payload",
    "merge_media_records",
]

"""Canonical media catalog schema — uploaded recordings and multitrack sessions."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

MEDIA_CATALOG_VERSION = 1

MEDIA_TYPES: tuple[str, ...] = ("audio", "video")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso_ts(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def new_recording_id() -> str:
    return str(uuid.uuid4())


def new_multitrack_id() -> str:
    return str(uuid.uuid4())


def new_track_id() -> str:
    return str(uuid.uuid4())


def _legacy_recording_fingerprint(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("saved_at") or entry.get("created_at") or ""),
        str(entry.get("title") or entry.get("source_label") or entry.get("filename") or ""),
        str(entry.get("workspace_id") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _legacy_multitrack_fingerprint(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("saved_at") or entry.get("created_at") or ""),
        str(entry.get("project_name") or entry.get("title") or ""),
        str(entry.get("song_title") or entry.get("song") or ""),
        str(entry.get("workspace_id") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def is_recording_tombstone(entry: dict[str, Any]) -> bool:
    return bool(entry.get("deleted")) and bool(str(entry.get("recording_id") or "").strip())


def is_multitrack_tombstone(entry: dict[str, Any]) -> bool:
    return bool(entry.get("deleted")) and bool(str(entry.get("multitrack_id") or "").strip())


def _recording_id(entry: dict[str, Any]) -> str:
    rid = str(entry.get("recording_id") or entry.get("item_key") or "").strip()
    if rid:
        return rid
    return f"legacy-rec-{_legacy_recording_fingerprint(entry)}"


def _multitrack_id(entry: dict[str, Any]) -> str:
    mid = str(entry.get("multitrack_id") or entry.get("item_key") or "").strip()
    if mid:
        return mid
    return f"legacy-mt-{_legacy_multitrack_fingerprint(entry)}"


def _compact_analysis_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in (
        "coach_summary",
        "scores",
        "layer_scores",
        "weakest_category",
        "strongest_category",
        "next_focus",
        "practice_plan",
        "overall_improv_score",
        "multitrack",
    ):
        if key in raw and raw[key] not in (None, "", [], {}):
            out[key] = raw[key]
    if out.get("coach_summary"):
        out["coach_summary"] = str(out["coach_summary"])[:500]
    return out


def migrate_track_entry(track: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(track, dict):
        return {}
    now = _utc_now_iso()
    tid = str(track.get("track_id") or "").strip() or new_track_id()
    created = str(track.get("created_at") or now)
    updated = str(track.get("updated_at") or created)
    if track.get("deleted"):
        return {
            "track_id": tid,
            "deleted": True,
            "updated_at": updated,
        }
    raw_summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
    summary = _compact_analysis_summary(raw_summary)
    for key in ("has_audio", "volume", "delay", "mute", "solo"):
        if key in raw_summary and key not in summary:
            summary[key] = raw_summary[key]
    return {
        "track_id": tid,
        "slot": str(track.get("slot") or "").strip(),
        "name": str(track.get("name") or track.get("layer_name") or track.get("filename") or "Take").strip()[:120],
        "instrument": str(track.get("instrument") or "").strip(),
        "role": str(track.get("role") or track.get("slot") or "").strip()[:80],
        "storage_ref": track.get("storage_ref"),
        "local_path": track.get("local_path"),
        "duration_seconds": _coerce_int(track.get("duration_seconds")),
        "playback_status": str(track.get("playback_status") or "").strip(),
        "created_at": created,
        "updated_at": updated,
        "analysis_summary": summary,
        "deleted": False,
    }


def is_real_multitrack_track(track: dict[str, Any]) -> bool:
    """True for a saved layer; false for empty slot placeholders in legacy catalogs."""
    if not isinstance(track, dict) or track.get("deleted"):
        return False
    if str(track.get("storage_ref") or "").strip() or str(track.get("local_path") or "").strip():
        return True
    summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
    if summary.get("has_audio"):
        return True
    status = str(track.get("playback_status") or "").strip()
    if status in ("playable", "metadata_only", "missing_file", "upload_failed"):
        return True
    return False


def real_multitrack_tracks(tracks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [t for t in (tracks or []) if isinstance(t, dict) and is_real_multitrack_track(t)]


def migrate_uploaded_recording(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single uploaded recording row (canonical or legacy upload_history)."""
    if not isinstance(entry, dict):
        return {}

    if is_recording_tombstone(entry):
        return {
            "recording_id": _recording_id(entry),
            "deleted": True,
            "updated_at": str(entry.get("updated_at") or _utc_now_iso()),
        }

    out = dict(entry)
    # Legacy upload_history row wrapper: { item_key, payload: {...} }
    payload = out.get("payload") if isinstance(out.get("payload"), dict) else {}
    if payload and not out.get("analysis_summary") and not out.get("filename"):
        merged = {**payload, **{k: v for k, v in out.items() if k not in ("payload",)}}
        out = merged

    rid = _recording_id(out)
    now = _utc_now_iso()
    created = str(out.get("created_at") or out.get("saved_at") or now)
    updated = str(out.get("updated_at") or out.get("saved_at") or created)

    analysis = out.get("analysis_summary")
    if not isinstance(analysis, dict) or not analysis:
        scores = out.get("scores_summary") if isinstance(out.get("scores_summary"), dict) else {}
        result = out.get("analysis_result") if isinstance(out.get("analysis_result"), dict) else {}
        analysis = _compact_analysis_summary({**result, **scores})

    media_type = str(out.get("media_type") or "audio").strip().lower()
    if media_type not in MEDIA_TYPES:
        media_type = "video" if "video" in str(out.get("recording_type") or "").lower() else "audio"

    filename = str(
        out.get("filename")
        or out.get("source_label")
        or out.get("title")
        or ""
    ).strip()[:200]

    song = str(out.get("song") or out.get("active_song") or out.get("title") or "").strip()
    if not song and filename:
        song = filename.rsplit(".", 1)[0][:120]

    return {
        "recording_id": rid,
        "created_at": created,
        "updated_at": updated,
        "workspace_id": str(out.get("workspace_id") or "daniel").strip(),
        "source_device": str(out.get("source_device") or "").strip(),
        "filename": filename,
        "media_type": media_type,
        "mime_type": str(out.get("mime_type") or "").strip(),
        "duration_seconds": _coerce_int(out.get("duration_seconds")),
        "song": song,
        "instrument": str(out.get("instrument") or "").strip(),
        "instrument_family": str(out.get("instrument_family") or "").strip(),
        "practice_concert_key": str(out.get("practice_concert_key") or out.get("display_key") or "").strip(),
        "written_key": str(out.get("written_key") or "").strip(),
        "shape_key": str(out.get("shape_key") or out.get("guitar_shape_key") or "").strip(),
        "original_key": str(out.get("original_key") or "").strip(),
        "bpm": _coerce_int(out.get("bpm")),
        "bpm_source": str(out.get("bpm_source") or "").strip(),
        "storage_ref": out.get("storage_ref"),
        "local_path": out.get("local_path"),
        "analysis_summary": analysis if isinstance(analysis, dict) else {},
        "notes": str(out.get("notes") or "").strip()[:2000],
        "linked_practice_session_id": str(out.get("linked_practice_session_id") or "").strip() or None,
        "legacy_item_key": str(out.get("legacy_item_key") or out.get("item_key") or "").strip(),
        "legacy_recording_type": str(out.get("legacy_recording_type") or out.get("recording_type") or "").strip(),
        "playback_status": str(out.get("playback_status") or "").strip(),
        "storage_error": str(out.get("storage_error") or "").strip(),
        "deleted": False,
    }


def migrate_multitrack_session(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single multitrack session row (canonical or legacy multitrack_history)."""
    if not isinstance(entry, dict):
        return {}

    if is_multitrack_tombstone(entry):
        return {
            "multitrack_id": _multitrack_id(entry),
            "deleted": True,
            "updated_at": str(entry.get("updated_at") or _utc_now_iso()),
        }

    out = dict(entry)
    payload = out.get("payload") if isinstance(out.get("payload"), dict) else {}
    if payload and not out.get("tracks") and payload.get("tracks"):
        merged = {**payload, **{k: v for k, v in out.items() if k not in ("payload",)}}
        out = merged

    mid = _multitrack_id(out)
    now = _utc_now_iso()
    created = str(out.get("created_at") or out.get("saved_at") or now)
    updated = str(out.get("updated_at") or out.get("saved_at") or created)

    raw_tracks = out.get("tracks") if isinstance(out.get("tracks"), list) else []
    tracks = [migrate_track_entry(t) for t in raw_tracks if isinstance(t, dict)]
    tracks = [t for t in tracks if t]

    analysis = _compact_analysis_summary(out.get("analysis_summary"))

    return {
        "multitrack_id": mid,
        "created_at": created,
        "updated_at": updated,
        "workspace_id": str(out.get("workspace_id") or "daniel").strip(),
        "title": str(out.get("title") or out.get("project_name") or "Multitrack session").strip()[:120],
        "song": str(out.get("song") or out.get("song_title") or "").strip(),
        "instrument": str(out.get("instrument") or "").strip(),
        "instrument_family": str(out.get("instrument_family") or "").strip(),
        "practice_concert_key": str(out.get("practice_concert_key") or "").strip(),
        "written_key": str(out.get("written_key") or "").strip(),
        "shape_key": str(out.get("shape_key") or "").strip(),
        "original_key": str(out.get("original_key") or "").strip(),
        "bpm": _coerce_int(out.get("bpm") or out.get("session_bpm")),
        "bpm_source": str(out.get("bpm_source") or "").strip(),
        "tracks": tracks,
        "mix_storage_ref": out.get("mix_storage_ref"),
        "mix_local_path": out.get("mix_local_path"),
        "analysis_summary": analysis,
        "notes": str(out.get("notes") or "").strip()[:2000],
        "linked_practice_session_id": str(out.get("linked_practice_session_id") or "").strip() or None,
        "legacy_item_key": str(out.get("legacy_item_key") or out.get("item_key") or "").strip(),
        "track_controls": out.get("track_controls") if isinstance(out.get("track_controls"), dict) else {},
        "deleted": False,
    }


def _parse_updated_at(entry: dict[str, Any]) -> str:
    return str(entry.get("updated_at") or entry.get("created_at") or "")


def merge_media_records(
    *groups: list[dict[str, Any]],
    migrate: Callable[[dict[str, Any]], dict[str, Any]],
    id_key: str,
) -> list[dict[str, Any]]:
    """Merge record lists by ID; newer updated_at wins."""
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            row = migrate(entry)
            rid = str(row.get(id_key) or "").strip()
            if not rid:
                continue
            prev = merged.get(rid)
            if prev is None or _parse_updated_at(row) >= _parse_updated_at(prev):
                merged[rid] = row
    out = list(merged.values())
    out.sort(key=lambda e: (_parse_updated_at(e), str(e.get(id_key) or "")), reverse=True)
    return out


def _apply_tombstones(
    entries: list[dict[str, Any]],
    *,
    id_key: str,
    is_tombstone: Callable[[dict[str, Any]], bool],
    migrate: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[dict[str, Any]]:
    migrated = [migrate(e) for e in (entries or []) if isinstance(e, dict)]

    tombstones: dict[str, datetime] = {}
    for row in migrated:
        rid = str(row.get(id_key) or "").strip()
        if not rid or not is_tombstone(row):
            continue
        ts = _parse_iso_ts(row.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        prev = tombstones.get(rid)
        if prev is None or ts > prev:
            tombstones[rid] = ts

    visible: dict[str, dict[str, Any]] = {}
    for row in migrated:
        if is_tombstone(row):
            continue
        rid = str(row.get(id_key) or "").strip()
        if not rid:
            continue
        ts = _parse_iso_ts(row.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        tomb = tombstones.get(rid)
        if tomb is not None and tomb >= ts:
            continue
        prev = visible.get(rid)
        if prev is None:
            visible[rid] = row
            continue
        prev_ts = _parse_iso_ts(prev.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if ts >= prev_ts:
            visible[rid] = row

    out = list(visible.values())
    out.sort(key=lambda e: (_parse_updated_at(e), str(e.get(id_key) or "")), reverse=True)
    return out


def normalize_uploaded_recordings(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply tombstones; return visible uploaded recordings newest-first."""
    return _apply_tombstones(
        entries,
        id_key="recording_id",
        is_tombstone=is_recording_tombstone,
        migrate=migrate_uploaded_recording,
    )


def normalize_multitrack_sessions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply tombstones; return visible multitrack sessions newest-first."""
    return _apply_tombstones(
        entries,
        id_key="multitrack_id",
        is_tombstone=is_multitrack_tombstone,
        migrate=migrate_multitrack_session,
    )


def merge_catalog(local: dict[str, Any] | None, cloud: dict[str, Any] | None) -> dict[str, Any]:
    """Merge local and cloud catalog payloads."""
    loc = dict(local or {})
    cld = dict(cloud or {})
    ws = str(loc.get("workspace_id") or cld.get("workspace_id") or "daniel").strip()

    uploads = merge_media_records(
        loc.get("uploaded_recordings") if isinstance(loc.get("uploaded_recordings"), list) else [],
        cld.get("uploaded_recordings") if isinstance(cld.get("uploaded_recordings"), list) else [],
        migrate=migrate_uploaded_recording,
        id_key="recording_id",
    )
    multitracks = merge_media_records(
        loc.get("multitrack_sessions") if isinstance(loc.get("multitrack_sessions"), list) else [],
        cld.get("multitrack_sessions") if isinstance(cld.get("multitrack_sessions"), list) else [],
        migrate=migrate_multitrack_session,
        id_key="multitrack_id",
    )
    updated = max(
        (_parse_updated_at(loc), _parse_updated_at(cld)),
        default="",
    )
    return {
        "version": MEDIA_CATALOG_VERSION,
        "workspace_id": ws,
        "updated_at": updated or _utc_now_iso(),
        "uploaded_recordings": uploads,
        "multitrack_sessions": multitracks,
    }


def _within_window(entry: dict[str, Any], *, window_days: int, today: date | None = None) -> bool:
    if window_days <= 0:
        return True
    ref = today or date.today()
    start = ref - timedelta(days=window_days - 1)
    for key in ("updated_at", "created_at"):
        ts = _parse_iso_ts(entry.get(key))
        if ts is not None:
            d = ts.date()
            if start <= d <= ref:
                return True
    return False


def compact_recording_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    row = migrate_uploaded_recording(entry)
    if is_recording_tombstone(row):
        return {}
    summary = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    return {
        "recording_id": row.get("recording_id"),
        "created_at": row.get("created_at"),
        "filename": row.get("filename"),
        "song": row.get("song"),
        "instrument": row.get("instrument"),
        "duration_seconds": row.get("duration_seconds"),
        "practice_concert_key": row.get("practice_concert_key"),
        "written_key": row.get("written_key"),
        "bpm": row.get("bpm"),
        "notes": row.get("notes"),
        "coach_summary": summary.get("coach_summary"),
        "scores": summary.get("scores"),
        "weakest_category": summary.get("weakest_category"),
        "strongest_category": summary.get("strongest_category"),
        "linked_practice_session_id": row.get("linked_practice_session_id"),
    }


def compact_multitrack_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    row = migrate_multitrack_session(entry)
    if is_multitrack_tombstone(row):
        return {}
    summary = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    tracks = real_multitrack_tracks(row.get("tracks") if isinstance(row.get("tracks"), list) else [])
    return {
        "multitrack_id": row.get("multitrack_id"),
        "created_at": row.get("created_at"),
        "title": row.get("title"),
        "song": row.get("song"),
        "instrument": row.get("instrument"),
        "bpm": row.get("bpm"),
        "notes": row.get("notes"),
        "track_count": len(tracks),
        "track_names": [str(t.get("name") or "") for t in tracks][:8],
        "coach_summary": summary.get("coach_summary"),
        "scores": summary.get("scores"),
        "linked_practice_session_id": row.get("linked_practice_session_id"),
    }


def build_media_ami_payload_from_catalog(
    catalog: dict[str, Any],
    *,
    window_days: int = 30,
) -> dict[str, Any]:
    uploads = normalize_uploaded_recordings(
        catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    )
    multitracks = normalize_multitrack_sessions(
        catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    )
    uploads = [u for u in uploads if _within_window(u, window_days=window_days)]
    multitracks = [m for m in multitracks if _within_window(m, window_days=window_days)]

    upload_compact = [c for c in (compact_recording_for_ami(u) for u in uploads) if c]
    mt_compact = [c for c in (compact_multitrack_for_ami(m) for m in multitracks) if c]

    recording_context: list[dict[str, Any]] = []
    for row in upload_compact:
        recording_context.append(
            {
                "date": row.get("created_at"),
                "song": row.get("song"),
                "instrument": row.get("instrument"),
                "coach_summary": row.get("coach_summary"),
                "weakest_category": row.get("weakest_category"),
                "strongest_category": row.get("strongest_category"),
                "source": "uploaded_recording",
            }
        )
    for row in mt_compact:
        recording_context.append(
            {
                "date": row.get("created_at"),
                "song": row.get("song"),
                "instrument": row.get("instrument"),
                "coach_summary": row.get("coach_summary"),
                "source": "multitrack_session",
            }
        )

    return {
        "uploaded_recordings": upload_compact,
        "multitrack_sessions": mt_compact,
        "recording_analysis_context": recording_context[:16],
        "media_summary": {
            "upload_count": len(upload_compact),
            "multitrack_count": len(mt_compact),
            "window_days": window_days,
        },
    }

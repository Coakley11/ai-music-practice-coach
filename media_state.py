"""Canonical media catalog schema — uploaded recordings, multitrack sessions, tone takes."""

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


def new_tone_take_id() -> str:
    return str(uuid.uuid4())


def new_multitrack_export_id() -> str:
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


def is_tone_take_tombstone(entry: dict[str, Any]) -> bool:
    return bool(entry.get("deleted")) and bool(str(entry.get("tone_take_id") or "").strip())


def is_multitrack_export_tombstone(entry: dict[str, Any]) -> bool:
    return bool(entry.get("deleted")) and bool(str(entry.get("export_id") or "").strip())


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


def _tone_take_id(entry: dict[str, Any]) -> str:
    return str(entry.get("tone_take_id") or "").strip()


def _multitrack_export_id(entry: dict[str, Any]) -> str:
    return str(entry.get("export_id") or "").strip()


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

    result = {
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
    # Keep durable Upload analysis-context for Practice Log / AMI (no audio blobs).
    snap = out.get("analysis_context_snapshot")
    if isinstance(snap, dict) and snap:
        result["analysis_context_snapshot"] = dict(snap)
    return result


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
        "backing_volume": out.get("backing_volume"),
        "backing_scope": str(out.get("backing_scope") or "").strip(),
        "backing_single_section": str(out.get("backing_single_section") or "").strip(),
        "backing_multi_sections": out.get("backing_multi_sections")
        if isinstance(out.get("backing_multi_sections"), list)
        else [],
        "backing_loops": _coerce_int(out.get("backing_loops")),
        "backing_groove": str(out.get("backing_groove") or "").strip(),
        "backing_meter": str(out.get("backing_meter") or "").strip(),
        "backing_count_in_bars": _coerce_int(out.get("backing_count_in_bars")),
        "backing_use_monitor": out.get("backing_use_monitor"),
        "backing_include_in_mix": out.get("backing_include_in_mix"),
        "backing_metronome": out.get("backing_metronome"),
        "backing_loop_section": out.get("backing_loop_section"),
        "backing_scope_label": str(out.get("backing_scope_label") or "").strip(),
        "backing_prepared_at": str(out.get("backing_prepared_at") or "").strip() or None,
        "backing_storage_ref": out.get("backing_storage_ref"),
        "backing_local_path": out.get("backing_local_path"),
        "backing_playback_status": str(out.get("backing_playback_status") or "").strip(),
        "backing_storage_error": str(out.get("backing_storage_error") or "").strip(),
        "transport_loop_backing": out.get("transport_loop_backing"),
        "transport_metronome": out.get("transport_metronome"),
        "transport_use_backing_monitor": out.get("transport_use_backing_monitor"),
        "transport_include_backing_in_mix": out.get("transport_include_backing_in_mix"),
        "analysis_summary": analysis,
        "notes": str(out.get("notes") or "").strip()[:2000],
        "linked_practice_session_id": str(out.get("linked_practice_session_id") or "").strip() or None,
        "legacy_item_key": str(out.get("legacy_item_key") or out.get("item_key") or "").strip(),
        "track_controls": out.get("track_controls") if isinstance(out.get("track_controls"), dict) else {},
        "deleted": False,
    }


def migrate_tone_take(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single tone/tuner practice take row."""
    if not isinstance(entry, dict):
        return {}

    if is_tone_take_tombstone(entry):
        deleted_at = str(entry.get("deleted_at") or entry.get("updated_at") or _utc_now_iso())
        return {
            "tone_take_id": _tone_take_id(entry),
            "deleted": True,
            "deleted_at": deleted_at,
            "updated_at": deleted_at,
        }

    out = dict(entry)
    tid = _tone_take_id(out) or new_tone_take_id()
    now = _utc_now_iso()
    created = str(out.get("created_at") or now)
    updated = str(out.get("updated_at") or created)

    feedback = out.get("feedback")
    if isinstance(feedback, list):
        feedback_lines = [str(x).strip() for x in feedback if str(x).strip()]
    else:
        feedback_lines = [str(feedback).strip()] if str(feedback or "").strip() else []

    coach = str(out.get("coach_summary") or out.get("coach_report") or "").strip()
    if not coach and feedback_lines:
        coach = " · ".join(x.replace("**", "") for x in feedback_lines[:4])[:500]

    pitch_score = _coerce_float(out.get("pitch_stability_score") or out.get("pitch_stability"))
    vol_score = _coerce_float(out.get("volume_stability_score") or out.get("sustain_steadiness"))
    mean_cents = _coerce_float(out.get("mean_cents") or out.get("average_cents"))
    tone_consistency = _coerce_float(out.get("tone_consistency_score"))
    if tone_consistency is None and pitch_score is not None and vol_score is not None:
        tone_consistency = round((pitch_score + vol_score) / 2.0, 1)

    sustain_seconds = _coerce_float(out.get("sustain_seconds"))
    max_drift = _coerce_float(out.get("max_cents_drift"))
    user_notes = str(out.get("notes") or out.get("user_notes") or "").strip()[:2000]

    raw_analysis = out.get("analysis_summary")
    if isinstance(raw_analysis, dict) and raw_analysis:
        analysis_summary = dict(raw_analysis)
    else:
        analysis_summary = {
            "pitch_stability_score": pitch_score,
            "volume_stability_score": vol_score,
            "sustain_steadiness": vol_score,
            "mean_cents": mean_cents,
            "max_cents_drift": max_drift,
            "sustain_seconds": sustain_seconds,
            "tone_consistency_score": tone_consistency,
            "attack_quality": out.get("attack_quality"),
            "feedback": feedback_lines,
        }
        analysis_summary = {k: v for k, v in analysis_summary.items() if v not in (None, "", [], {})}

    return {
        "tone_take_id": tid,
        "created_at": created,
        "updated_at": updated,
        "workspace_id": str(out.get("workspace_id") or "daniel").strip(),
        "instrument": str(out.get("instrument") or "").strip(),
        "instrument_family": str(out.get("instrument_family") or "").strip(),
        "transposing_type": str(out.get("transposing_type") or "").strip(),
        "target_note": str(out.get("target_note") or "").strip() or None,
        "selected_pitch_class": str(out.get("selected_pitch_class") or "").strip(),
        "detected_note": str(out.get("detected_note") or "").strip() or None,
        "written_note": str(out.get("written_note") or "").strip() or None,
        "concert_note": str(out.get("concert_note") or "").strip() or None,
        "written_key": str(out.get("written_key") or "").strip(),
        "practice_concert_key": str(out.get("practice_concert_key") or out.get("display_key") or "").strip(),
        "duration_seconds": _coerce_float(out.get("duration_seconds") or out.get("duration_sec")),
        "median_note": str(out.get("median_note") or out.get("detected_note") or "").strip() or None,
        "mean_cents": mean_cents,
        "average_cents": mean_cents,
        "max_cents_drift": max_drift,
        "pitch_stability_score": pitch_score,
        "pitch_stability": pitch_score,
        "volume_stability_score": vol_score,
        "sustain_steadiness": vol_score,
        "sustain_seconds": sustain_seconds,
        "tone_consistency_score": tone_consistency,
        "attack_quality": str(out.get("attack_quality") or "").strip() or None,
        "feedback": feedback_lines,
        "coach_summary": coach[:500] if coach else "",
        "coach_report": coach[:500] if coach else "",
        "analysis_summary": analysis_summary,
        "notes": user_notes,
        "user_notes": user_notes,
        "mime_type": str(out.get("mime_type") or "audio/wav").strip(),
        "local_path": out.get("local_path"),
        "storage_ref": out.get("storage_ref"),
        "playback_status": str(out.get("playback_status") or "").strip(),
        "storage_error": str(out.get("storage_error") or "").strip(),
        "deleted": False,
        "deleted_at": None,
    }


def migrate_multitrack_export(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a saved multitrack mix export row."""
    if not isinstance(entry, dict):
        return {}

    if is_multitrack_export_tombstone(entry):
        deleted_at = str(entry.get("deleted_at") or entry.get("updated_at") or _utc_now_iso())
        return {
            "export_id": _multitrack_export_id(entry) or new_multitrack_export_id(),
            "deleted": True,
            "deleted_at": deleted_at,
            "updated_at": deleted_at,
        }

    out = dict(entry)
    eid = _multitrack_export_id(out) or new_multitrack_export_id()
    now = _utc_now_iso()
    created = str(out.get("created_at") or now)
    updated = str(out.get("updated_at") or created)

    included = out.get("included_tracks")
    if isinstance(included, list):
        included_tracks = [dict(x) for x in included if isinstance(x, dict)]
    else:
        included_tracks = []

    mix_settings = out.get("mix_settings")
    if not isinstance(mix_settings, dict):
        mix_settings = {}

    snapshot = out.get("source_multitrack_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}

    analysis = out.get("analysis_summary")
    if not isinstance(analysis, dict):
        analysis = {}

    fmt = str(out.get("format") or out.get("mime_type") or "wav").strip().lower()
    if fmt.startswith("audio/"):
        fmt = fmt.split("/", 1)[-1]
    if not fmt:
        fmt = "wav"

    return {
        "export_id": eid,
        "multitrack_id": str(out.get("multitrack_id") or out.get("project_id") or "").strip() or None,
        "export_name": str(out.get("export_name") or out.get("title") or "Multitrack export").strip()[:120],
        "song": str(out.get("song") or out.get("song_title") or "").strip(),
        "song_title": str(out.get("song_title") or out.get("song") or "").strip(),
        "active_song_id": str(out.get("active_song_id") or "").strip() or None,
        "created_at": created,
        "updated_at": updated,
        "workspace_id": str(out.get("workspace_id") or "daniel").strip(),
        "instrument": str(out.get("instrument") or "").strip(),
        "bpm": _coerce_int(out.get("bpm")),
        "duration_seconds": _coerce_float(out.get("duration_seconds")),
        "format": fmt,
        "sample_rate": _coerce_int(out.get("sample_rate")),
        "track_count": _coerce_int(out.get("track_count")) or len(included_tracks),
        "included_tracks": included_tracks,
        "mix_settings": mix_settings,
        "source_multitrack_snapshot": snapshot,
        "analysis_status": str(out.get("analysis_status") or "").strip(),
        "analysis_summary": analysis,
        "playback_status": str(out.get("playback_status") or "").strip(),
        "storage_ref": out.get("storage_ref"),
        "local_path": out.get("local_path"),
        "storage_error": str(out.get("storage_error") or "").strip(),
        "linked_recording_id": str(out.get("linked_recording_id") or "").strip() or None,
        "linked_practice_session_id": str(out.get("linked_practice_session_id") or "").strip() or None,
        "notes": str(out.get("notes") or "").strip()[:2000],
        "deleted": False,
        "deleted_at": None,
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


def normalize_tone_takes(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply tombstones; return visible tone takes newest-first."""
    return _apply_tombstones(
        entries,
        id_key="tone_take_id",
        is_tombstone=is_tone_take_tombstone,
        migrate=migrate_tone_take,
    )


def normalize_multitrack_exports(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply tombstones; return visible multitrack exports newest-first."""
    return _apply_tombstones(
        entries,
        id_key="export_id",
        is_tombstone=is_multitrack_export_tombstone,
        migrate=migrate_multitrack_export,
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
    tone_takes = merge_media_records(
        loc.get("tone_takes") if isinstance(loc.get("tone_takes"), list) else [],
        cld.get("tone_takes") if isinstance(cld.get("tone_takes"), list) else [],
        migrate=migrate_tone_take,
        id_key="tone_take_id",
    )
    multitrack_exports = merge_media_records(
        loc.get("multitrack_exports") if isinstance(loc.get("multitrack_exports"), list) else [],
        cld.get("multitrack_exports") if isinstance(cld.get("multitrack_exports"), list) else [],
        migrate=migrate_multitrack_export,
        id_key="export_id",
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
        "tone_takes": tone_takes,
        "multitrack_exports": multitrack_exports,
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


def _ami_analysis_context_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Preserve Upload analysis-context intent for Practice Log / AMI (no audio blobs)."""
    snap = entry.get("analysis_context_snapshot")
    if not isinstance(snap, dict):
        summary = entry.get("analysis_summary") if isinstance(entry.get("analysis_summary"), dict) else {}
        snap = summary.get("analysis_context_snapshot") if isinstance(summary, dict) else None
    if not isinstance(snap, dict):
        snap = {}
    instruments = snap.get("instruments")
    if not isinstance(instruments, list):
        instruments = [entry.get("instrument")] if entry.get("instrument") else []
    instruments = [str(x) for x in instruments if str(x).strip()]
    criteria_ids = list(snap.get("evaluating_criteria_ids") or [])
    criteria_labels = list(snap.get("evaluating_criteria_labels") or [])
    return {
        "workflow": str(snap.get("workflow") or entry.get("workflow") or ""),
        "recording_type": str(snap.get("recording_type") or entry.get("recording_type") or ""),
        "instruments": instruments,
        "level": str(snap.get("level") or entry.get("level") or ""),
        "practice_focus": str(snap.get("practice_focus") or entry.get("practice_focus") or ""),
        "practice_focuses": [
            str(x).strip()
            for x in list(snap.get("practice_focuses") or [])
            if str(x).strip()
        ]
        if isinstance(snap.get("practice_focuses"), list)
        else (
            [str(snap.get("practice_focus")).strip()]
            if str(snap.get("practice_focus") or entry.get("practice_focus") or "").strip()
            else []
        ),
        "instrument_focuses": {
            str(k).strip(): (
                [str(x).strip() for x in v if str(x).strip()]
                if isinstance(v, (list, tuple))
                else ([str(v).strip()] if str(v).strip() else [])
            )
            for k, v in dict(snap.get("instrument_focuses") or {}).items()
            if str(k).strip()
            and (
                (isinstance(v, (list, tuple)) and any(str(x).strip() for x in v))
                or (not isinstance(v, (list, tuple)) and str(v).strip())
            )
        }
        if isinstance(snap.get("instrument_focuses"), dict)
        else {},
        "evaluating_criteria_ids": [str(x) for x in criteria_ids if str(x).strip()],
        "evaluating_criteria_labels": [str(x) for x in criteria_labels if str(x).strip()],
        "song_source_type": str(snap.get("song_source_type") or entry.get("song_source_type") or ""),
        "song_source_id": str(snap.get("song_source_id") or entry.get("song_source_id") or ""),
        "song_source_name": str(
            snap.get("song_source_name") or entry.get("song_source_name") or entry.get("song") or ""
        ),
        "mission_type": str(snap.get("mission_type") or entry.get("mission_type") or ""),
        "mission_constraint": str(
            snap.get("mission_constraint") or entry.get("mission_constraint") or ""
        ),
        "mission_parameters": dict(snap.get("mission_parameters") or {})
        if isinstance(snap.get("mission_parameters"), dict)
        else {},
        "multitrack_project_id": str(snap.get("multitrack_project_id") or ""),
        "multitrack_project_name": str(snap.get("multitrack_project_name") or ""),
        "target_layer": str(snap.get("target_layer") or entry.get("target_layer") or ""),
        "target_instruments": list(snap.get("target_instruments") or [])
        if isinstance(snap.get("target_instruments"), list)
        else [],
    }


def compact_recording_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    row = migrate_uploaded_recording(entry)
    if is_recording_tombstone(row):
        return {}
    summary = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    ctx_fields = _ami_analysis_context_fields(row)
    return {
        "recording_id": row.get("recording_id"),
        "created_at": row.get("created_at"),
        "filename": row.get("filename"),
        "song": row.get("song") or ctx_fields.get("song_source_name"),
        "instrument": row.get("instrument")
        or ((ctx_fields.get("instruments") or [None])[0]),
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
        **ctx_fields,
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
        "has_backing": bool(row.get("backing_storage_ref") or row.get("backing_local_path") or row.get("backing_prepared_at")),
        "coach_summary": summary.get("coach_summary"),
        "scores": summary.get("scores"),
        "linked_practice_session_id": row.get("linked_practice_session_id"),
    }


def compact_tone_take_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    row = migrate_tone_take(entry)
    if is_tone_take_tombstone(row):
        return {}
    audio_available = bool(row.get("storage_ref") or row.get("local_path"))
    analysis = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    return {
        "tone_take_id": row.get("tone_take_id"),
        "created_at": row.get("created_at"),
        "instrument": row.get("instrument"),
        "instrument_family": row.get("instrument_family"),
        "target_note": row.get("target_note"),
        "detected_note": row.get("detected_note"),
        "written_note": row.get("written_note"),
        "concert_note": row.get("concert_note"),
        "duration_seconds": row.get("duration_seconds"),
        "average_cents": row.get("average_cents") or row.get("mean_cents"),
        "mean_cents": row.get("mean_cents"),
        "pitch_stability": row.get("pitch_stability") or row.get("pitch_stability_score"),
        "pitch_stability_score": row.get("pitch_stability_score"),
        "sustain_steadiness": row.get("sustain_steadiness") or row.get("volume_stability_score"),
        "tone_consistency_score": row.get("tone_consistency_score"),
        "attack_quality": row.get("attack_quality"),
        "sustain_seconds": row.get("sustain_seconds"),
        "coach_report": row.get("coach_report") or row.get("coach_summary"),
        "analysis_summary": analysis,
        "user_notes": row.get("user_notes") or row.get("notes"),
        "playback_status": row.get("playback_status"),
        "audio_available": audio_available,
    }


def _tone_take_quality_label(row: dict[str, Any]) -> str:
    score = _coerce_float(row.get("pitch_stability_score")) or 0.0
    cents = abs(_coerce_float(row.get("mean_cents")) or 0.0)
    if score >= 78 and cents <= 10:
        return "best"
    if score < 55 or cents > 20:
        return "needs_work"
    return "steady"


def _tone_improvement_trends(takes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in takes:
        inst = str(row.get("instrument") or "").strip()
        note = str(row.get("written_note") or row.get("concert_note") or row.get("target_note") or "").strip()
        if not inst or not note:
            continue
        groups[(inst, note)].append(row)

    trends: list[dict[str, Any]] = []
    for (inst, note), rows in groups.items():
        if len(rows) < 2:
            continue
        ordered = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
        recent = ordered[-3:]
        older = ordered[:-3] or ordered[:1]

        def _avg_cents(group: list[dict[str, Any]]) -> float | None:
            vals = [_coerce_float(r.get("mean_cents")) for r in group]
            vals = [v for v in vals if v is not None]
            if not vals:
                return None
            return sum(vals) / len(vals)

        def _avg_stability(group: list[dict[str, Any]]) -> float | None:
            vals = [_coerce_float(r.get("pitch_stability_score")) for r in group]
            vals = [v for v in vals if v is not None]
            if not vals:
                return None
            return sum(vals) / len(vals)

        old_cents = _avg_cents(older)
        new_cents = _avg_cents(recent)
        old_stab = _avg_stability(older)
        new_stab = _avg_stability(recent)
        if old_cents is None or new_cents is None:
            continue
        trends.append(
            {
                "instrument": inst,
                "note": note,
                "take_count": len(rows),
                "mean_cents_delta": round(new_cents - old_cents, 1),
                "pitch_stability_delta": round((new_stab or 0) - (old_stab or 0), 1)
                if new_stab is not None and old_stab is not None
                else None,
                "recent_mean_cents": round(new_cents, 1),
                "older_mean_cents": round(old_cents, 1),
            }
        )
    trends.sort(key=lambda t: abs(t.get("mean_cents_delta") or 0), reverse=True)
    return trends[:12]


def _best_worst_pitch_by_instrument(
    compact: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    from collections import defaultdict

    by_inst: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compact:
        inst = str(row.get("instrument") or "Unknown").strip() or "Unknown"
        by_inst[inst].append(row)

    best: dict[str, dict[str, Any]] = {}
    worst: dict[str, dict[str, Any]] = {}
    for inst, rows in by_inst.items():
        scored = [r for r in rows if r.get("pitch_stability_score") is not None or r.get("pitch_stability") is not None]
        if not scored:
            continue
        best[inst] = max(
            scored,
            key=lambda r: (_coerce_float(r.get("pitch_stability_score") or r.get("pitch_stability")) or 0),
        )
        worst[inst] = min(
            scored,
            key=lambda r: (_coerce_float(r.get("pitch_stability_score") or r.get("pitch_stability")) or 0),
        )
    return best, worst


def build_tone_ami_summary(takes: list[dict[str, Any]], *, window_days: int = 30) -> dict[str, Any]:
    """Structured tone/tuner summaries for AMI — metadata only, no audio blobs."""
    compact = [c for c in (compact_tone_take_for_ami(t) for t in takes) if c]
    by_instrument: dict[str, int] = {}
    recent_by_instrument: dict[str, list[dict[str, Any]]] = {}
    for row in compact:
        inst = str(row.get("instrument") or "Unknown").strip() or "Unknown"
        by_instrument[inst] = by_instrument.get(inst, 0) + 1
        recent_by_instrument.setdefault(inst, []).append(row)

    for inst in recent_by_instrument:
        recent_by_instrument[inst] = sorted(
            recent_by_instrument[inst],
            key=lambda r: str(r.get("created_at") or ""),
            reverse=True,
        )[:8]

    scored = [r for r in compact if r.get("pitch_stability_score") is not None]
    best = sorted(scored, key=lambda r: (_coerce_float(r.get("pitch_stability_score")) or 0), reverse=True)[:5]
    worst = sorted(scored, key=lambda r: (_coerce_float(r.get("pitch_stability_score")) or 0))[:5]
    best_by_inst, worst_by_inst = _best_worst_pitch_by_instrument(compact)
    trends = _tone_improvement_trends(compact)
    audio_available_count = sum(1 for r in compact if r.get("audio_available"))

    return {
        "tone_take_count_total": len(compact),
        "tone_take_count_by_instrument": by_instrument,
        "recent_tone_takes_by_instrument": recent_by_instrument,
        "recent_tone_reports": compact[:16],
        "best_pitch_stability": best,
        "worst_pitch_stability": worst,
        "best_pitch_stability_by_instrument": best_by_inst,
        "worst_pitch_stability_by_instrument": worst_by_inst,
        "improvement_trends": trends,
        "improvement_trends_by_instrument_and_note": trends,
        "audio_available": audio_available_count > 0,
        "audio_available_count": audio_available_count,
        "window_days": window_days,
    }


def compact_multitrack_export_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    row = migrate_multitrack_export(entry)
    if is_multitrack_export_tombstone(row):
        return {}
    audio_available = bool(row.get("storage_ref") or row.get("local_path"))
    summary = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    included = row.get("included_tracks") if isinstance(row.get("included_tracks"), list) else []
    return {
        "export_id": row.get("export_id"),
        "created_at": row.get("created_at"),
        "export_name": row.get("export_name"),
        "song": row.get("song") or row.get("song_title"),
        "multitrack_id": row.get("multitrack_id"),
        "duration_seconds": row.get("duration_seconds"),
        "format": row.get("format"),
        "track_count": row.get("track_count") or len(included),
        "included_tracks": [str(t.get("name") or "") for t in included if isinstance(t, dict)][:8],
        "analysis_status": row.get("analysis_status"),
        "coach_summary": summary.get("coach_summary"),
        "scores": summary.get("scores"),
        "playback_status": row.get("playback_status"),
        "audio_available": audio_available,
        "linked_recording_id": row.get("linked_recording_id"),
        "source": "multitrack_export",
    }


def build_multitrack_export_ami_summary(exports: list[dict[str, Any]], *, window_days: int = 30) -> dict[str, Any]:
    compact = [c for c in (compact_multitrack_export_for_ami(e) for e in exports) if c]
    by_song: dict[str, int] = {}
    by_project: dict[str, int] = {}
    for row in compact:
        song = str(row.get("song") or "Unknown").strip() or "Unknown"
        by_song[song] = by_song.get(song, 0) + 1
        pid = str(row.get("multitrack_id") or "").strip()
        if pid:
            by_project[pid] = by_project.get(pid, 0) + 1
    analysis_ready = [r for r in compact if r.get("analysis_status") == "analyzed" or r.get("coach_summary")]
    audio_available_count = sum(1 for r in compact if r.get("audio_available"))
    return {
        "multitrack_export_count_total": len(compact),
        "recent_multitrack_exports": compact[:16],
        "exports_by_song": by_song,
        "exports_by_project": by_project,
        "analysis_ready_exports": analysis_ready[:12],
        "audio_available": audio_available_count > 0,
        "audio_available_count": audio_available_count,
        "window_days": window_days,
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
    tone_takes = normalize_tone_takes(
        catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else []
    )
    multitrack_exports = normalize_multitrack_exports(
        catalog.get("multitrack_exports") if isinstance(catalog.get("multitrack_exports"), list) else []
    )
    uploads = [u for u in uploads if _within_window(u, window_days=window_days)]
    multitracks = [m for m in multitracks if _within_window(m, window_days=window_days)]
    tone_takes = [t for t in tone_takes if _within_window(t, window_days=window_days)]
    multitrack_exports = [e for e in multitrack_exports if _within_window(e, window_days=window_days)]

    upload_compact = [c for c in (compact_recording_for_ami(u) for u in uploads) if c]
    mt_compact = [c for c in (compact_multitrack_for_ami(m) for m in multitracks) if c]
    export_compact = [c for c in (compact_multitrack_export_for_ami(e) for e in multitrack_exports) if c]
    tone_summary = build_tone_ami_summary(tone_takes, window_days=window_days)
    export_summary = build_multitrack_export_ami_summary(multitrack_exports, window_days=window_days)

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
                "workflow": row.get("workflow"),
                "recording_type": row.get("recording_type"),
                "instruments": list(row.get("instruments") or []),
                "level": row.get("level"),
                "practice_focus": row.get("practice_focus"),
                "practice_focuses": list(row.get("practice_focuses") or [])
                if isinstance(row.get("practice_focuses"), list)
                else [],
                "instrument_focuses": dict(row.get("instrument_focuses") or {})
                if isinstance(row.get("instrument_focuses"), dict)
                else {},
                "evaluating_criteria_ids": list(row.get("evaluating_criteria_ids") or []),
                "evaluating_criteria_labels": list(row.get("evaluating_criteria_labels") or []),
                "song_source_type": row.get("song_source_type"),
                "song_source_id": row.get("song_source_id"),
                "song_source_name": row.get("song_source_name"),
                "mission_type": row.get("mission_type"),
                "mission_constraint": row.get("mission_constraint"),
                "mission_parameters": dict(row.get("mission_parameters") or {})
                if isinstance(row.get("mission_parameters"), dict)
                else {},
                "multitrack_project_id": row.get("multitrack_project_id"),
                "multitrack_project_name": row.get("multitrack_project_name"),
                "target_layer": row.get("target_layer"),
                "target_instruments": list(row.get("target_instruments") or []),
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
    for row in tone_summary.get("recent_tone_reports") or []:
        if not isinstance(row, dict):
            continue
        recording_context.append(
            {
                "date": row.get("created_at"),
                "instrument": row.get("instrument"),
                "written_note": row.get("written_note"),
                "concert_note": row.get("concert_note"),
                "coach_summary": row.get("coach_summary"),
                "pitch_stability_score": row.get("pitch_stability_score"),
                "mean_cents": row.get("mean_cents"),
                "source": "tone_take",
            }
        )

    for row in export_summary.get("recent_multitrack_exports") or []:
        if not isinstance(row, dict):
            continue
        recording_context.append(
            {
                "date": row.get("created_at"),
                "song": row.get("song"),
                "coach_summary": row.get("coach_summary"),
                "source": "multitrack_export",
            }
        )

    return {
        "uploaded_recordings": upload_compact,
        "multitrack_sessions": mt_compact,
        "multitrack_exports": export_summary,
        "tone_history": tone_summary,
        "recording_analysis_context": recording_context[:20],
        "media_summary": {
            "upload_count": len(upload_compact),
            "multitrack_count": len(mt_compact),
            "multitrack_export_count": export_summary.get("multitrack_export_count_total", 0),
            "tone_take_count": tone_summary.get("tone_take_count_total", 0),
            "window_days": window_days,
        },
    }

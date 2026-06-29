"""Multitrack Export Library — saved mix exports ↔ canonical media catalog."""

from __future__ import annotations

import hashlib
import io
import wave
from datetime import datetime, timezone
from typing import Any

from media_persistence import (
    add_multitrack_export,
    delete_multitrack_export,
    load_media_catalog,
    update_multitrack_export,
)
from media_state import migrate_multitrack_export, normalize_multitrack_exports
from media_storage import (
    PLAYBACK_METADATA_ONLY,
    PLAYBACK_PLAYABLE,
    delete_mix_export_files,
    load_mix_export_audio,
    mix_export_playback_status,
    persist_mix_export_audio,
    playback_status_label,
)

_LAST_EXPORT_SAVE_STATUS_KEY = "_multitrack_export_last_save_status"
_LAST_EXPORT_LOAD_STATUS_KEY = "_multitrack_export_last_load_status"
_LAST_EXPORT_PLAYBACK_STATUS_KEY = "_multitrack_export_last_playback_status"
_LAST_SEND_TO_ANALYSIS_STATUS_KEY = "_multitrack_export_last_send_analysis_status"
PENDING_EXPORT_ANALYSIS_KEY = "_pending_multitrack_export_analysis"
ANALYSIS_EXPORT_LOADED_LABEL_KEY = "analysis_multitrack_export_loaded_label"
ANALYSIS_EXPORT_HANDOFF_ID_KEY = "_analysis_export_handoff_id"
ANALYSIS_EXPORT_HANDOFF_META_KEY = "_analysis_export_handoff_meta"
ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX = "Multitrack mix"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_state(st: Any | None) -> dict[str, Any] | None:
    if st is None:
        return None
    try:
        ss = st.session_state if hasattr(st, "session_state") else st
        return ss if isinstance(ss, dict) else None
    except Exception:
        return None


def wav_duration_seconds(audio: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as wf:
            rate = wf.getframerate()
            if rate <= 0:
                return None
            return wf.getnframes() / float(rate)
    except Exception:
        return None


def wav_sample_rate(audio: bytes) -> int | None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as wf:
            return int(wf.getframerate())
    except Exception:
        return None


def format_export_duration(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    total = int(round(seconds))
    mins, secs = divmod(total, 60)
    if mins:
        return f"{mins}:{secs:02d}"
    return f"0:{secs:02d}"


def format_export_display_time(created_at: str) -> str:
    text = str(created_at or "").strip()
    if not text:
        return "—"
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        ts = datetime.fromisoformat(text)
        hour = ts.strftime("%I").lstrip("0") or "12"
        return f"{ts.strftime('%Y-%m-%d')} {hour}:{ts.strftime('%M %p')}"
    except ValueError:
        return text[:16]


def suggest_export_name(*, song_title: str = "", project_title: str = "") -> str:
    song = str(song_title or "").strip()
    project = str(project_title or "").strip()
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M %p").lstrip("0").replace(" 0", " ")
    if song:
        return f"{song} mix {stamp}"
    if project:
        return f"{project} export {stamp}"
    return f"Multitrack mix {stamp}"


def build_included_tracks_from_mix_items(track_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    included: list[dict[str, Any]] = []
    for item in track_items or []:
        if not isinstance(item, dict):
            continue
        included.append(
            {
                "slot": str(item.get("slot") or ""),
                "name": str(item.get("name") or item.get("layer_name") or "")[:120],
                "volume": float(item.get("volume", 1.0)),
                "delay": float(item.get("delay", 0.0)),
                "mute": bool(item.get("mute", False)),
                "solo": bool(item.get("solo", False)),
            }
        )
    return included


def build_multitrack_export_fields(
    session_state: dict[str, Any],
    audio_bytes: bytes,
    *,
    export_name: str = "",
    song_title: str = "",
    track_items: list[dict[str, Any]] | None = None,
    include_backing: bool = False,
    backing_volume: float = 0.75,
    st: Any | None = None,
) -> dict[str, Any]:
    included = build_included_tracks_from_mix_items(track_items or [])
    if include_backing:
        included.append(
            {
                "slot": "backing",
                "name": "Backing track",
                "volume": float(backing_volume),
                "delay": 0.0,
                "mute": False,
                "solo": False,
            }
        )

    multitrack_id = ""
    try:
        from media_multitrack_catalog import active_catalog_multitrack_id

        multitrack_id = active_catalog_multitrack_id(session_state)
    except ImportError:
        multitrack_id = str(session_state.get("multitrack_catalog_active_id") or "").strip()

    song = str(song_title or session_state.get("active_song_title") or "").strip()
    active_song_id = str(session_state.get("active_song_id") or session_state.get("selected_song_id") or "").strip()
    instrument = str(session_state.get("instrument") or "").strip()
    bpm = session_state.get("multitrack_bpm") or session_state.get("backing_track_bpm")

    snapshot: dict[str, Any] = {
        "multitrack_id": multitrack_id or None,
        "song": song,
        "bpm": bpm,
        "include_backing_in_mix": bool(include_backing),
        "backing_volume": float(backing_volume),
        "track_count": len(included),
    }

    name = str(export_name or "").strip() or suggest_export_name(song_title=song)

    return {
        "export_name": name[:120],
        "multitrack_id": multitrack_id or None,
        "song": song,
        "song_title": song,
        "active_song_id": active_song_id or None,
        "instrument": instrument,
        "bpm": bpm,
        "duration_seconds": wav_duration_seconds(audio_bytes),
        "format": "wav",
        "sample_rate": wav_sample_rate(audio_bytes),
        "track_count": len(included),
        "included_tracks": included,
        "mix_settings": {
            "include_backing_in_mix": bool(include_backing),
            "backing_volume": float(backing_volume),
        },
        "source_multitrack_snapshot": snapshot,
        "analysis_status": "pending",
        "playback_status": PLAYBACK_METADATA_ONLY,
    }


def save_multitrack_export_from_session(
    session_state: dict[str, Any],
    audio_bytes: bytes,
    *,
    export_name: str = "",
    song_title: str = "",
    track_items: list[dict[str, Any]] | None = None,
    include_backing: bool = False,
    backing_volume: float = 0.75,
    st: Any | None = None,
) -> tuple[bool, str, str]:
    if not audio_bytes:
        ss = _session_state(st) or session_state
        ss[_LAST_EXPORT_SAVE_STATUS_KEY] = {"ok": False, "error": "missing_audio"}
        return False, "", "missing_audio"

    fields = build_multitrack_export_fields(
        session_state,
        audio_bytes,
        export_name=export_name,
        song_title=song_title,
        track_items=track_items,
        include_backing=include_backing,
        backing_volume=backing_volume,
        st=st,
    )
    row = add_multitrack_export(st, fields)
    eid = str(row.get("export_id") or "")
    if not eid:
        ss = _session_state(st) or session_state
        ss[_LAST_EXPORT_SAVE_STATUS_KEY] = {"ok": False, "error": "catalog_save_failed"}
        return False, "", "catalog_save_failed"

    stored = persist_mix_export_audio(
        st,
        eid,
        audio_bytes,
        filename=f"{fields.get('export_name') or 'export'}.wav",
        mime_type="audio/wav",
    )
    if stored.get("local_path") or stored.get("storage_ref"):
        row = update_multitrack_export(
            st,
            eid,
            {
                "local_path": stored.get("local_path"),
                "storage_ref": stored.get("storage_ref"),
                "playback_status": stored.get("playback_status"),
                "storage_error": stored.get("storage_error") or "",
                "updated_at": _utc_now_iso(),
            },
        )

    ss = _session_state(st) or session_state
    ss[_LAST_EXPORT_SAVE_STATUS_KEY] = {
        "ok": True,
        "export_id": eid,
        "playback_status": row.get("playback_status"),
        "storage_ref": bool(row.get("storage_ref")),
        "local_path": bool(row.get("local_path")),
    }
    return True, eid, ""


def list_multitrack_exports(
    *,
    st: Any | None = None,
    song_title: str = "",
    multitrack_id: str = "",
) -> list[dict[str, Any]]:
    catalog = load_media_catalog(st=st)
    rows = normalize_multitrack_exports(
        catalog.get("multitrack_exports") if isinstance(catalog.get("multitrack_exports"), list) else []
    )
    if song_title:
        song_low = song_title.strip().lower()
        rows = [r for r in rows if str(r.get("song") or r.get("song_title") or "").strip().lower() == song_low]
    if multitrack_id:
        mid = multitrack_id.strip()
        rows = [r for r in rows if str(r.get("multitrack_id") or "") == mid]
    return rows


def export_row_summary(row: dict[str, Any]) -> str:
    row = migrate_multitrack_export(row)
    name = str(row.get("export_name") or "Export")
    song = str(row.get("song") or row.get("song_title") or "").strip()
    track_count = int(row.get("track_count") or 0)
    dur = format_export_duration(row.get("duration_seconds"))
    fmt = str(row.get("format") or "wav").upper()
    when = format_export_display_time(str(row.get("created_at") or ""))

    parts = [name]
    if song and song.lower() not in name.lower():
        parts.append(song)
    if track_count:
        parts.append(f"{track_count} track{'s' if track_count != 1 else ''}")
    parts.extend([dur, fmt, when])
    return " · ".join(parts)


def playback_label_for_export(row: dict[str, Any], *, st: Any | None = None) -> str:
    status = mix_export_playback_status(row, st=st)
    return playback_status_label(status)


def load_export_for_playback(
    export_id: str,
    *,
    st: Any | None = None,
) -> tuple[bytes | None, str, dict[str, Any]]:
    eid = str(export_id or "").strip()
    catalog = load_media_catalog(st=st)
    row: dict[str, Any] = {}
    for candidate in catalog.get("multitrack_exports") or []:
        if isinstance(candidate, dict) and str(candidate.get("export_id") or "") == eid:
            row = migrate_multitrack_export(candidate)
            break
    if not row or row.get("deleted"):
        ss = _session_state(st)
        if ss is not None:
            ss[_LAST_EXPORT_LOAD_STATUS_KEY] = {"ok": False, "export_id": eid, "error": "not_found"}
        return None, "not_found", {}

    data, err = load_mix_export_audio(row, st=st)
    ss = _session_state(st)
    if ss is not None:
        ss[_LAST_EXPORT_LOAD_STATUS_KEY] = {
            "ok": bool(data),
            "export_id": eid,
            "error": err or "",
            "bytes": len(data) if data else 0,
        }
        ss[_LAST_EXPORT_PLAYBACK_STATUS_KEY] = {
            "ok": bool(data),
            "export_id": eid,
            "playback_status": mix_export_playback_status(row, st=st),
        }
    return data, err or ("missing_file" if not data else ""), row


def delete_multitrack_export_entry(st: Any | None, export_id: str, *, row: dict[str, Any] | None = None) -> bool:
    eid = str(export_id or "").strip()
    if not eid:
        return False
    if row is None:
        catalog = load_media_catalog(st=st)
        for candidate in catalog.get("multitrack_exports") or []:
            if isinstance(candidate, dict) and str(candidate.get("export_id") or "") == eid:
                row = migrate_multitrack_export(candidate)
                break
    if row:
        delete_mix_export_files(row, st=st)
    return delete_multitrack_export(st, eid)


def _export_filename_from_meta(meta: dict[str, Any]) -> str:
    name = str(meta.get("export_name") or "multitrack_export").strip()
    if not name.lower().endswith(".wav"):
        name = f"{name}.wav"
    return name


def _compact_export_handoff_meta(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "multitrack_export",
        "export_id": meta.get("export_id"),
        "export_name": meta.get("export_name"),
        "song_title": meta.get("song_title") or meta.get("song"),
        "duration_seconds": meta.get("duration_seconds"),
        "format": meta.get("format"),
        "storage_ref": meta.get("storage_ref"),
        "track_count": meta.get("track_count"),
        "included_tracks": meta.get("included_tracks"),
    }


def clear_multitrack_export_analysis_handoff(session_state: dict[str, Any]) -> None:
    session_state.pop(PENDING_EXPORT_ANALYSIS_KEY, None)
    session_state.pop(ANALYSIS_EXPORT_LOADED_LABEL_KEY, None)
    session_state.pop(ANALYSIS_EXPORT_HANDOFF_ID_KEY, None)
    session_state.pop(ANALYSIS_EXPORT_HANDOFF_META_KEY, None)
    session_state.pop("_analysis_export_handoff_name", None)


def apply_multitrack_export_analysis_handoff(
    session_state: dict[str, Any],
    meta: dict[str, Any],
    *,
    audio: bytes,
) -> tuple[bool, str]:
    """Wire saved export audio into Upload Analysis session keys the UI already reads."""
    if not audio:
        return False, "missing_audio"
    try:
        from upload_media import PreparedUpload
    except ImportError:
        return False, "upload_media_unavailable"

    raw = bytes(audio)
    filename = _export_filename_from_meta(meta)
    prepared = PreparedUpload(raw, filename)
    sig = (
        hashlib.sha256(raw[:65536] + str(len(raw)).encode()).hexdigest()[:20],
        filename,
    )
    compact = _compact_export_handoff_meta(meta)

    session_state["last_analysis_audio"] = raw
    session_state["last_analysis_source_label"] = filename
    session_state["analysis_mode"] = "Single recording"
    session_state["analysis_recording_type"] = ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX
    session_state["_analysis_prepared_upload"] = prepared
    session_state["_analysis_upload_prep_sig"] = sig
    session_state[ANALYSIS_EXPORT_LOADED_LABEL_KEY] = f"Loaded from Multitrack Export: {filename}"
    session_state[ANALYSIS_EXPORT_HANDOFF_ID_KEY] = str(meta.get("export_id") or "")
    session_state["_analysis_export_handoff_name"] = str(meta.get("export_name") or "")
    session_state[ANALYSIS_EXPORT_HANDOFF_META_KEY] = compact
    session_state.pop("last_analysis_result", None)
    session_state.pop(PENDING_EXPORT_ANALYSIS_KEY, None)
    return True, ""


def apply_pending_multitrack_export_analysis(session_state: dict[str, Any]) -> tuple[bool, str]:
    """Apply pending export handoff on Upload Analysis page load."""
    pending = session_state.get(PENDING_EXPORT_ANALYSIS_KEY)
    if isinstance(pending, dict) and pending.get("source") == "multitrack_export":
        audio = session_state.get("last_analysis_audio")
        if not audio:
            return False, "missing_audio"
        return apply_multitrack_export_analysis_handoff(session_state, pending, audio=bytes(audio))

    handoff_id = str(session_state.get(ANALYSIS_EXPORT_HANDOFF_ID_KEY) or "").strip()
    if handoff_id and not session_state.get("_analysis_prepared_upload"):
        audio = session_state.get("last_analysis_audio")
        if not audio:
            return False, "missing_audio"
        meta = session_state.get(ANALYSIS_EXPORT_HANDOFF_META_KEY)
        if not isinstance(meta, dict):
            meta = {
                "source": "multitrack_export",
                "export_id": handoff_id,
                "export_name": session_state.get("_analysis_export_handoff_name") or "",
            }
        return apply_multitrack_export_analysis_handoff(session_state, meta, audio=bytes(audio))
    return False, "no_pending"


def loaded_multitrack_export_analysis_banner(session_state: dict[str, Any]) -> str:
    return str(session_state.get(ANALYSIS_EXPORT_LOADED_LABEL_KEY) or "").strip()


def analysis_export_handoff_ready(session_state: dict[str, Any]) -> bool:
    return bool(session_state.get("_analysis_prepared_upload")) and bool(
        session_state.get(ANALYSIS_EXPORT_LOADED_LABEL_KEY)
    )


def send_export_to_upload_analysis(
    session_state: dict[str, Any],
    export_id: str,
    *,
    st: Any | None = None,
) -> tuple[bool, str]:
    data, err, row = load_export_for_playback(export_id, st=st)
    if not data:
        ss = _session_state(st) or session_state
        ss[_LAST_SEND_TO_ANALYSIS_STATUS_KEY] = {
            "ok": False,
            "export_id": export_id,
            "error": err or "missing_audio",
        }
        return False, err or "missing_audio"

    row = migrate_multitrack_export(row)
    filename = _export_filename_from_meta(row)
    session_state["last_analysis_audio"] = data
    session_state["last_analysis_source_label"] = filename
    session_state["analysis_mode"] = "Single recording"
    session_state["analysis_recording_type"] = ANALYSIS_RECORDING_TYPE_MULTITRACK_MIX
    session_state.pop("last_analysis_result", None)
    session_state[PENDING_EXPORT_ANALYSIS_KEY] = _compact_export_handoff_meta(
        {
            **row,
            "song_title": row.get("song") or row.get("song_title"),
        }
    )
    session_state[PENDING_EXPORT_ANALYSIS_KEY]["created_at"] = row.get("created_at")
    session_state[PENDING_EXPORT_ANALYSIS_KEY]["mix_settings"] = row.get("mix_settings")
    session_state[PENDING_EXPORT_ANALYSIS_KEY]["multitrack_id"] = row.get("multitrack_id")
    session_state[PENDING_EXPORT_ANALYSIS_KEY]["local_path"] = row.get("local_path")
    ss = _session_state(st) or session_state
    ss[_LAST_SEND_TO_ANALYSIS_STATUS_KEY] = {
        "ok": True,
        "export_id": export_id,
        "source": "multitrack_export",
    }
    return True, ""


def export_catalog_diagnostics(session_state: dict[str, Any], *, st: Any | None = None) -> dict[str, Any]:
    catalog = load_media_catalog(st=st)
    all_rows = catalog.get("multitrack_exports") if isinstance(catalog.get("multitrack_exports"), list) else []
    visible = list_multitrack_exports(st=st)
    deleted_count = sum(
        1
        for row in all_rows
        if isinstance(row, dict) and migrate_multitrack_export(row).get("deleted")
    )
    storage_ref_count = sum(1 for r in visible if r.get("storage_ref"))
    metadata_only = sum(1 for r in visible if not r.get("storage_ref") and not r.get("local_path"))
    missing_audio = sum(
        1 for r in visible if mix_export_playback_status(r, st=st) != PLAYBACK_PLAYABLE
    )
    ss = session_state or {}
    return {
        "export_count": len(visible),
        "deleted_tombstone_count": deleted_count,
        "storage_ref_count": storage_ref_count,
        "metadata_only_count": metadata_only,
        "missing_audio_count": missing_audio,
        "last_export_save_status": ss.get(_LAST_EXPORT_SAVE_STATUS_KEY),
        "last_export_load_status": ss.get(_LAST_EXPORT_LOAD_STATUS_KEY),
        "last_export_playback_status": ss.get(_LAST_EXPORT_PLAYBACK_STATUS_KEY),
        "last_send_to_upload_analysis_status": ss.get(_LAST_SEND_TO_ANALYSIS_STATUS_KEY),
        "ami_excludes_raw_audio": True,
    }

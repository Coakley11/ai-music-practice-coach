"""Upload Analysis ↔ canonical media catalog (Step C)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from media_persistence import (
    add_uploaded_recording,
    delete_uploaded_recording,
    load_media_catalog,
    save_media_catalog,
    update_uploaded_recording,
)
from media_state import (
    migrate_uploaded_recording,
    normalize_uploaded_recordings,
)
from media_storage import (
    PLAYBACK_METADATA_ONLY,
    delete_recording_files,
    load_recording_audio,
    persist_recording_audio,
    playback_status_label,
    recording_playback_status,
)
from upload_history import (
    compact_analysis_for_history,
    list_upload_history,
    save_upload_to_history as _save_legacy_upload_history,
    scores_summary_from_result,
)

_MIGRATION_FLAG = "_media_upload_history_migrated"
_LAST_CATALOG_RECORDING_KEY = "_last_catalog_recording_id"
_ACTIVE_CATALOG_RECORDING_KEY = "upload_catalog_active_recording_id"


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


def _analysis_summary_from_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = compact_analysis_for_history(result)
    scores = scores_summary_from_result(result)
    summary = {**compact, **scores}
    summary.pop("audio_b64", None)
    return summary


def build_upload_recording_fields(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    notes: str = "",
    title: str = "",
) -> dict[str, Any] | None:
    """Build canonical uploaded_recording fields from the current analysis session."""
    raw = session_state.get("last_analysis_result")
    if not isinstance(raw, dict) or not raw or raw.get("ok") is False:
        return None

    source_label = str(
        session_state.get("last_analysis_source_label")
        or session_state.get("analysis_source_filename")
        or ""
    ).strip()
    filename = source_label or str(title or "recording.wav").strip()
    recording_type = str(
        session_state.get("analysis_recording_type")
        or session_state.get("last_analysis_recording_type")
        or "Practice take"
    ).strip()

    media_type = "audio"
    if filename.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
        media_type = "video"

    song = str(session_state.get("active_song_title") or "").strip()
    instrument = ""
    instrument_family = ""
    try:
        from practice_setup_globals import (
            get_active_instrument,
            get_active_instrument_display_name,
        )

        instrument_family = str(get_active_instrument(session_state) or "").strip()
        instrument = str(get_active_instrument_display_name(session_state) or instrument_family).strip()
    except ImportError:
        instrument = str(session_state.get("instrument") or "").strip()

    key_fields: dict[str, str] = {}
    bpm: int | None = None
    bpm_source: str | None = None
    try:
        from practice_log_state import gather_practice_log_keys, resolve_practice_log_bpm

        key_fields = gather_practice_log_keys(session_state)
        bpm, bpm_source = resolve_practice_log_bpm(session_state)
    except ImportError:
        pass

    if not song:
        try:
            from active_song_state import gather_active_song_context

            ctx = gather_active_song_context(session_state)
            selected = ctx.get("selected_song") if isinstance(ctx.get("selected_song"), dict) else {}
            song = str(selected.get("title") or ctx.get("active_song_title") or "").strip()
        except ImportError:
            pass

    if title and not song:
        song = title.rsplit(".", 1)[0][:120]

    try:
        from studio_history_cloud import active_workspace_id

        workspace_id = active_workspace_id(st=st)
    except ImportError:
        workspace_id = "daniel"

    return {
        "workspace_id": workspace_id,
        "filename": filename[:200],
        "media_type": media_type,
        "mime_type": "audio/wav" if media_type == "audio" else "video/mp4",
        "song": song,
        "instrument": instrument,
        "instrument_family": instrument_family,
        "practice_concert_key": str(key_fields.get("practice_concert_key") or key_fields.get("display_key") or "").strip(),
        "written_key": str(key_fields.get("written_key") or "").strip(),
        "shape_key": str(key_fields.get("guitar_shape_key") or "").strip(),
        "original_key": str(key_fields.get("original_key") or "").strip(),
        "bpm": bpm,
        "bpm_source": str(bpm_source or "").strip().replace(" ", "_") if bpm_source else "",
        "analysis_summary": _analysis_summary_from_result(raw),
        "notes": str(notes or session_state.get("upload_history_loaded_notes") or "").strip()[:2000],
        "legacy_recording_type": recording_type[:80],
    }


def _session_audio_bytes(session_state: dict[str, Any]) -> bytes | None:
    raw = session_state.get("last_analysis_audio")
    if isinstance(raw, (bytes, bytearray)) and raw:
        return bytes(raw)
    return None


def _apply_storage_fields_to_recording(
    st: Any | None,
    recording_id: str,
    session_state: dict[str, Any],
    *,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Persist session audio and update catalog row with storage_ref/local_path."""
    rid = str(recording_id or "").strip()
    if not rid:
        return None
    audio = _session_audio_bytes(session_state)
    if not audio:
        return None
    meta = dict(fields or {})
    result = persist_recording_audio(
        st,
        rid,
        audio,
        filename=str(meta.get("filename") or session_state.get("last_analysis_source_label") or "recording.wav"),
        mime_type=str(meta.get("mime_type") or "audio/wav"),
        workspace_id=str(meta.get("workspace_id") or "").strip() or None,
    )
    if not result.get("local_path") and not result.get("storage_ref"):
        update_uploaded_recording(
            st,
            rid,
            {
                "playback_status": result.get("playback_status") or PLAYBACK_METADATA_ONLY,
                "storage_error": result.get("error") or result.get("storage_error") or "persist_failed",
                "updated_at": _utc_now_iso(),
            },
        )
        return result
    return update_uploaded_recording(
        st,
        rid,
        {
            "local_path": result.get("local_path"),
            "storage_ref": result.get("storage_ref"),
            "playback_status": result.get("playback_status"),
            "storage_error": result.get("storage_error") or "",
            "updated_at": _utc_now_iso(),
        },
    )


def register_upload_analysis_in_catalog(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    notes: str = "",
    title: str = "",
) -> dict[str, Any] | None:
    """Auto-add the current analysis to the media catalog and persist audio when available."""
    fields = build_upload_recording_fields(session_state, st=st, notes=notes, title=title)
    if not fields:
        return None
    row = add_uploaded_recording(st, fields)
    rid = str(row.get("recording_id") or "")
    if rid:
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
        stored = _apply_storage_fields_to_recording(st, rid, session_state, fields=fields)
        if stored:
            row = stored
    return row


def save_upload_recording_with_notes(
    session_state: dict[str, Any],
    *,
    title: str,
    notes: str = "",
    st: Any | None = None,
) -> tuple[bool, str, str]:
    """Save current analysis to catalog; optionally mirror legacy upload_history when cloud allows."""
    fields = build_upload_recording_fields(session_state, st=st, notes=notes, title=title)
    if not fields:
        return False, "", "no_analysis_result"
    if title:
        fields["song"] = str(title).strip()[:120] or fields.get("song") or ""

    active_rid = str(session_state.get(_LAST_CATALOG_RECORDING_KEY) or "").strip()
    if active_rid:
        row = update_uploaded_recording(st, active_rid, fields)
        if not row:
            row = add_uploaded_recording(st, fields)
    else:
        row = add_uploaded_recording(st, fields)

    rid = str(row.get("recording_id") or "")
    if rid:
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
        stored = _apply_storage_fields_to_recording(st, rid, session_state, fields=fields)
        if stored:
            row = stored

    legacy_ok, legacy_key, legacy_err = _save_legacy_upload_history(
        session_state,
        title=title,
        notes=notes,
        st=st,
    )
    if legacy_ok and legacy_key:
        update_uploaded_recording(
            st,
            rid,
            {"legacy_item_key": legacy_key, "updated_at": _utc_now_iso()},
        )

    if rid:
        return True, rid, legacy_err if not legacy_ok else ""
    return False, "", "catalog_save_failed"


def migrate_legacy_upload_history(*, st: Any | None = None) -> int:
    """Import legacy upload_history saved_items into the media catalog once per session."""
    ss = _session_state(st)
    if ss is not None and ss.get(_MIGRATION_FLAG):
        return 0

    rows, _err = list_upload_history(st=st)
    if not rows:
        if ss is not None:
            ss[_MIGRATION_FLAG] = True
        return 0

    catalog = load_media_catalog(st=st)
    existing = catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    known_legacy = {
        str(r.get("legacy_item_key") or "")
        for r in existing
        if isinstance(r, dict) and str(r.get("legacy_item_key") or "").strip()
    }
    known_ids = {str(r.get("recording_id") or "") for r in existing if isinstance(r, dict)}

    imported: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_key = str(row.get("item_key") or "").strip()
        if item_key and item_key in known_legacy:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        migrated = migrate_uploaded_recording({**payload, "item_key": item_key})
        rid = str(migrated.get("recording_id") or "")
        if rid in known_ids:
            continue
        if item_key:
            migrated["legacy_item_key"] = item_key
        try:
            from studio_history_cloud import decode_audio_b64

            audio = decode_audio_b64(payload.get("audio_b64"))
            if audio:
                store = persist_recording_audio(
                    st,
                    rid,
                    audio,
                    filename=str(migrated.get("filename") or "recording.wav"),
                    mime_type=str(migrated.get("mime_type") or "audio/wav"),
                    workspace_id=str(migrated.get("workspace_id") or ""),
                )
                if store.get("local_path"):
                    migrated["local_path"] = store.get("local_path")
                if store.get("storage_ref"):
                    migrated["storage_ref"] = store.get("storage_ref")
                if store.get("playback_status"):
                    migrated["playback_status"] = store.get("playback_status")
        except ImportError:
            pass
        imported.append(migrated)
        known_ids.add(rid)

    if not imported:
        if ss is not None:
            ss[_MIGRATION_FLAG] = True
        return 0

    merged_uploads = list(existing) + imported
    catalog["uploaded_recordings"] = merged_uploads
    save_media_catalog(catalog, st=st)
    if ss is not None:
        ss[_MIGRATION_FLAG] = True
    return len(imported)


def list_catalog_upload_recordings(*, st: Any | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """Return UI rows for saved upload recordings from the media catalog."""
    migrate_legacy_upload_history(st=st)
    catalog = load_media_catalog(st=st)
    visible = normalize_uploaded_recordings(
        catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    )
    rows: list[dict[str, Any]] = []
    for rec in visible:
        rid = str(rec.get("recording_id") or "")
        if not rid:
            continue
        rows.append(
            {
                "item_key": rid,
                "title": rec.get("filename") or rec.get("song") or "Upload analysis",
                "updated_at": rec.get("updated_at") or rec.get("created_at"),
                "payload": rec,
                "playback_status": recording_playback_status(rec, st=st),
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows, None


def catalog_upload_row_summary(row: dict[str, Any]) -> str:
    """Status-only summary; filename/timestamp are composed by the history list UI."""
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    title = str(row.get("title") or "").strip()
    song = str(payload.get("song") or "").strip()
    instrument = str(payload.get("instrument") or "").strip()
    bits: list[str] = []
    if song and song != title:
        bits.append(song[:40])
    if instrument:
        bits.append(instrument[:40])
    status = str(row.get("playback_status") or recording_playback_status(payload)).strip()
    if status:
        bits.append(playback_status_label(status))
    return " · ".join(bits)


def active_catalog_recording_id(session_state: dict[str, Any]) -> str:
    return str(
        session_state.get(_ACTIVE_CATALOG_RECORDING_KEY)
        or session_state.get("upload_hist_active_item")
        or session_state.get("upload_history_loaded_item_key")
        or ""
    ).strip()


def apply_upload_catalog_ui_state(session_state: dict[str, Any], row: dict[str, Any]) -> None:
    """Restore Upload History form fields and active-recording markers after load."""
    rec = migrate_uploaded_recording(row)
    rid = str(rec.get("recording_id") or "").strip()
    title = str(rec.get("title") or rec.get("filename") or "").strip()
    notes = str(rec.get("notes") or "").strip()
    if title:
        session_state["upload_history_save_title"] = title
    session_state["upload_history_save_notes"] = notes
    session_state["upload_history_loaded_notes"] = notes
    if rid:
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
        session_state["upload_hist_active_item"] = rid


def loaded_upload_recording_banner(session_state: dict[str, Any], *, st: Any | None = None) -> str:
    """Human-readable label for the currently loaded upload recording."""
    rid = active_catalog_recording_id(session_state)
    if not rid:
        return ""
    catalog = load_media_catalog(st=st)
    rows = normalize_uploaded_recordings(
        catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    )
    rec = next((r for r in rows if str(r.get("recording_id") or "") == rid), None)
    if not isinstance(rec, dict):
        return f"Loaded upload: {rid}"
    title = str(rec.get("title") or rec.get("filename") or "Saved upload").strip()
    song = str(rec.get("song") or "").strip()
    instrument = str(rec.get("instrument") or "").strip()
    notes = str(rec.get("notes") or "").strip()
    status = catalog_upload_row_summary({"payload": rec, "title": title})
    parts = [f"Loaded upload: {title}"]
    if song and song.lower() not in title.lower():
        parts.append(song)
    if instrument:
        parts.append(instrument)
    if status:
        parts.append(status)
    if notes:
        parts.append(f"notes: {notes[:80]}")
    return " · ".join(parts)


def load_upload_recording_from_catalog(
    session_state: dict[str, Any],
    recording_id: str,
    *,
    st: Any | None = None,
) -> tuple[bool, str]:
    """Reload catalog from cloud/disk and restore one saved upload recording."""
    rid = str(recording_id or "").strip()
    if not rid:
        return False, "missing_recording_id"
    catalog = load_media_catalog(st=st)
    rows = normalize_uploaded_recordings(
        catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    )
    row = next((r for r in rows if str(r.get("recording_id") or "") == rid), None)
    if not isinstance(row, dict):
        return False, "not_found"
    ok, msg = apply_catalog_recording_to_session(session_state, row, st=st)
    return ok, msg


def apply_catalog_recording_to_session(
    session_state: dict[str, Any],
    recording: dict[str, Any],
    *,
    st: Any | None = None,
) -> tuple[bool, str]:
    """Restore analysis metadata and playable audio when storage_ref/local_path exists."""
    rec = migrate_uploaded_recording(recording)
    summary = rec.get("analysis_summary") if isinstance(rec.get("analysis_summary"), dict) else {}
    if not summary:
        return False, "missing_analysis_summary"
    result = dict(summary)
    result.setdefault("ok", True)
    session_state["last_analysis_result"] = compact_analysis_for_history(result)
    session_state["last_analysis_source_label"] = str(rec.get("filename") or "")
    session_state["last_analysis_recording_type"] = str(rec.get("legacy_recording_type") or "Practice take")
    apply_upload_catalog_ui_state(session_state, rec)

    status = recording_playback_status(rec, st=st)
    session_state["upload_catalog_playback_status"] = status
    if status == PLAYBACK_METADATA_ONLY:
        session_state.pop("last_analysis_audio", None)
    else:
        audio, err = load_recording_audio(rec, st=st)
        if audio:
            session_state["last_analysis_audio"] = audio
        else:
            session_state.pop("last_analysis_audio", None)
            return True, err or "missing_file"

    rid = str(rec.get("recording_id") or "")
    if rid:
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
        session_state["upload_hist_active_item"] = rid
    return True, ""


def delete_catalog_upload_recording(recording_id: str, *, st: Any | None = None) -> tuple[bool, str]:
    rid = str(recording_id or "").strip()
    if not rid:
        return False, "missing_recording_id"
    catalog = load_media_catalog(st=st)
    rows = catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
    existing = next((r for r in rows if isinstance(r, dict) and str(r.get("recording_id") or "") == rid), None)
    if isinstance(existing, dict):
        delete_recording_files(existing, st=st)
    ok = delete_uploaded_recording(st, rid)
    return ok, "" if ok else "delete_failed"

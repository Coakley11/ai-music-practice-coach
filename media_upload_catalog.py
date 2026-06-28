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


def register_upload_analysis_in_catalog(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    notes: str = "",
    title: str = "",
) -> dict[str, Any] | None:
    """Auto-add the current analysis to the media catalog (metadata only)."""
    fields = build_upload_recording_fields(session_state, st=st, notes=notes, title=title)
    if not fields:
        return None
    row = add_uploaded_recording(st, fields)
    rid = str(row.get("recording_id") or "")
    if rid:
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
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
                "title": rec.get("song") or rec.get("filename") or "Upload analysis",
                "updated_at": rec.get("updated_at") or rec.get("created_at"),
                "payload": rec,
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows, None


def catalog_upload_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    summary = payload.get("analysis_summary") if isinstance(payload.get("analysis_summary"), dict) else {}
    coach = str(summary.get("coach_summary") or row.get("title") or "Upload analysis")
    instrument = str(payload.get("instrument") or "").strip()
    filename = str(payload.get("filename") or "").strip()
    bits = [coach[:100]]
    if instrument:
        bits.append(instrument[:40])
    elif filename:
        bits.append(filename[:40])
    return " · ".join(bits)


def apply_catalog_recording_to_session(session_state: dict[str, Any], recording: dict[str, Any]) -> bool:
    """Restore analysis metadata from a catalog recording (no audio blob)."""
    rec = migrate_uploaded_recording(recording)
    summary = rec.get("analysis_summary") if isinstance(rec.get("analysis_summary"), dict) else {}
    if not summary:
        return False
    result = dict(summary)
    result.setdefault("ok", True)
    session_state["last_analysis_result"] = compact_analysis_for_history(result)
    session_state["last_analysis_source_label"] = str(rec.get("filename") or "")
    session_state["last_analysis_recording_type"] = str(rec.get("legacy_recording_type") or "Practice take")
    if rec.get("notes"):
        session_state["upload_history_loaded_notes"] = str(rec.get("notes") or "")
    session_state.pop("last_analysis_audio", None)
    rid = str(rec.get("recording_id") or "")
    if rid:
        session_state[_ACTIVE_CATALOG_RECORDING_KEY] = rid
        session_state[_LAST_CATALOG_RECORDING_KEY] = rid
    return True


def delete_catalog_upload_recording(recording_id: str, *, st: Any | None = None) -> tuple[bool, str]:
    rid = str(recording_id or "").strip()
    if not rid:
        return False, "missing_recording_id"
    ok = delete_uploaded_recording(st, rid)
    return ok, "" if ok else "delete_failed"

"""Multitrack sessions ↔ canonical media catalog (Step D)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from media_persistence import (
    add_multitrack_session,
    delete_multitrack_session,
    load_media_catalog,
    save_media_catalog,
    update_multitrack_session,
)
from media_state import (
    is_real_multitrack_track,
    migrate_multitrack_session,
    new_track_id,
    normalize_multitrack_sessions,
    real_multitrack_tracks,
)
from media_storage import (
    PLAYBACK_METADATA_ONLY,
    PLAYBACK_PLAYABLE,
    delete_multitrack_session_files,
    load_track_audio,
    persist_track_audio,
    playback_status_label,
    track_playback_status,
)
from multitrack_history import (
    apply_multitrack_history,
    build_multitrack_history_payload,
    list_multitrack_history,
)
from multitrack_slots import MULTITRACK_SLOTS

_MIGRATION_FLAG = "_media_multitrack_history_migrated"
_LAST_CATALOG_MULTITRACK_KEY = "_last_catalog_multitrack_id"
_ACTIVE_CATALOG_MULTITRACK_KEY = "multitrack_catalog_active_id"


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


def _gather_key_fields(session_state: dict[str, Any]) -> dict[str, str]:
    try:
        from practice_log_state import gather_practice_log_keys

        return gather_practice_log_keys(session_state)
    except ImportError:
        return {}


def _gather_instrument(session_state: dict[str, Any]) -> tuple[str, str]:
    try:
        from practice_setup_globals import get_active_instrument, get_active_instrument_display_name

        family = str(get_active_instrument(session_state) or "").strip()
        display = str(get_active_instrument_display_name(session_state) or family).strip()
        return display, family
    except ImportError:
        instrument = str(session_state.get("instrument") or "").strip()
        return instrument, instrument


def catalog_row_to_history_payload(session: dict[str, Any]) -> dict[str, Any]:
    """Convert a canonical catalog row into legacy multitrack_history payload shape."""
    row = migrate_multitrack_session(session)
    tracks_meta: list[dict[str, Any]] = []
    for track in row.get("tracks") or []:
        if not isinstance(track, dict) or track.get("deleted"):
            continue
        if not is_real_multitrack_track(track):
            continue
        slot = str(track.get("slot") or "")
        if slot not in MULTITRACK_SLOTS:
            continue
        summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
        has_ref = bool(track.get("storage_ref") or track.get("local_path"))
        has_audio = bool(summary.get("has_audio") or has_ref)
        tracks_meta.append(
            {
                "slot": slot,
                "layer_name": str(track.get("name") or slot),
                "filename": str(track.get("name") or f"{slot.replace(' ', '_').lower()}.wav")[:200],
                "volume": float(summary.get("volume", 1.0)),
                "delay": float(summary.get("delay", 0.0)),
                "mute": bool(summary.get("mute", False)),
                "solo": bool(summary.get("solo", False)),
                "has_audio": has_audio,
                "audio_embedded": False,
            }
        )

    track_controls = session.get("track_controls")
    if not isinstance(track_controls, dict):
        track_controls = {}

    return {
        "version": 1,
        "workspace_id": row.get("workspace_id"),
        "saved_at": row.get("updated_at") or row.get("created_at"),
        "project_name": row.get("title"),
        "song_title": row.get("song"),
        "notes": row.get("notes"),
        "tracks": tracks_meta,
        "track_controls": track_controls,
        "embedded_tracks": {},
        "mixed_preview_b64": None,
        "session_bpm": row.get("bpm"),
        "analysis_summary": row.get("analysis_summary"),
    }


def build_multitrack_catalog_fields(
    session_state: dict[str, Any],
    *,
    project_name: str,
    notes: str = "",
    song_title: str = "",
    st: Any | None = None,
) -> dict[str, Any] | None:
    """Build canonical multitrack_sessions fields from the live session (metadata only)."""
    payload, _build_err = build_multitrack_history_payload(
        session_state,
        project_name=project_name,
        notes=notes,
        song_title=song_title,
        st=st,
    )
    if not payload:
        return None

    key_fields = _gather_key_fields(session_state)
    instrument, instrument_family = _gather_instrument(session_state)
    song = str(song_title or payload.get("song_title") or session_state.get("active_song_title") or "").strip()

    tracks: list[dict[str, Any]] = []
    controls = payload.get("track_controls") if isinstance(payload.get("track_controls"), dict) else {}
    for row in payload.get("tracks") or []:
        if not isinstance(row, dict):
            continue
        slot = str(row.get("slot") or "")
        if slot not in MULTITRACK_SLOTS:
            continue
        ctrl = controls.get(slot) if isinstance(controls.get(slot), dict) else {}
        if not ctrl:
            layer_name = str(row.get("layer_name") or slot)
            ctrl = controls.get(layer_name) if isinstance(controls.get(layer_name), dict) else {}
        if not row.get("has_audio"):
            continue
        tracks.append(
            {
                "track_id": str(row.get("track_id") or "").strip() or new_track_id(),
                "slot": slot,
                "name": str(row.get("layer_name") or slot)[:120],
                "instrument": str(session_state.get("instrument") or "").strip(),
                "role": slot,
                "duration_seconds": None,
                "local_path": None,
                "storage_ref": None,
                "playback_status": PLAYBACK_METADATA_ONLY if row.get("has_audio") else "",
                "analysis_summary": {
                    "volume": float(row.get("volume", ctrl.get("volume", 1.0))),
                    "delay": float(row.get("delay", ctrl.get("delay", 0.0))),
                    "mute": bool(row.get("mute", ctrl.get("mute", False))),
                    "solo": bool(row.get("solo", ctrl.get("solo", False))),
                    "has_audio": bool(row.get("has_audio")),
                },
            }
        )

    slot_controls: dict[str, dict[str, Any]] = {}
    for slot in MULTITRACK_SLOTS:
        ctrl = controls.get(slot) if isinstance(controls.get(slot), dict) else {}
        if not ctrl:
            layer_name = str(session_state.get(f"mt_name_{slot}") or slot)
            ctrl = controls.get(layer_name) if isinstance(controls.get(layer_name), dict) else {}
        slot_controls[slot] = {
            "volume": float(session_state.get(f"mt_vol_{slot}", ctrl.get("volume", 1.0))),
            "delay": float(session_state.get(f"mt_delay_{slot}", ctrl.get("delay", 0.0))),
            "mute": bool(ctrl.get("mute", False)),
            "solo": bool(ctrl.get("solo", False)),
        }

    try:
        from studio_history_cloud import active_workspace_id

        workspace_id = active_workspace_id(st=st)
    except ImportError:
        workspace_id = "daniel"

    bpm = payload.get("session_bpm") or session_state.get("multitrack_bpm") or session_state.get("backing_track_bpm")

    return {
        "workspace_id": workspace_id,
        "title": str(payload.get("project_name") or project_name or "Multitrack session").strip()[:120],
        "song": song,
        "instrument": instrument,
        "instrument_family": instrument_family,
        "practice_concert_key": str(key_fields.get("practice_concert_key") or key_fields.get("display_key") or "").strip(),
        "written_key": str(key_fields.get("written_key") or "").strip(),
        "shape_key": str(key_fields.get("guitar_shape_key") or "").strip(),
        "original_key": str(key_fields.get("original_key") or "").strip(),
        "bpm": bpm,
        "tracks": tracks,
        "track_controls": slot_controls,
        "mix_storage_ref": None,
        "mix_local_path": None,
        "analysis_summary": payload.get("analysis_summary") if isinstance(payload.get("analysis_summary"), dict) else {},
        "notes": str(notes or payload.get("notes") or "").strip()[:2000],
    }


def _merge_track_ids(fields: dict[str, Any], existing_session: dict[str, Any] | None) -> None:
    if not existing_session:
        return
    by_slot: dict[str, str] = {}
    for track in existing_session.get("tracks") or []:
        if isinstance(track, dict):
            slot = str(track.get("slot") or "")
            tid = str(track.get("track_id") or "")
            if slot and tid:
                by_slot[slot] = tid
    for track in fields.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        slot = str(track.get("slot") or "")
        if slot in by_slot:
            track["track_id"] = by_slot[slot]


def _persist_session_tracks(
    st: Any | None,
    session_state: dict[str, Any],
    multitrack_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Upload each live layer blob to durable storage; update track refs on fields."""
    mid = str(multitrack_id or "").strip()
    ws = str(fields.get("workspace_id") or "daniel").strip()
    mt_tracks = session_state.get("mt_tracks") if isinstance(session_state.get("mt_tracks"), dict) else {}
    filenames = session_state.get("mt_track_filenames") if isinstance(session_state.get("mt_track_filenames"), dict) else {}
    updated_tracks: list[dict[str, Any]] = []

    for track in fields.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        slot = str(track.get("slot") or "")
        tid = str(track.get("track_id") or "").strip() or new_track_id()
        track["track_id"] = tid
        audio = mt_tracks.get(slot)
        if not audio or not isinstance(audio, (bytes, bytearray)):
            updated_tracks.append(track)
            continue
        filename = str(filenames.get(slot) or f"{slot.replace(' ', '_').lower()}.wav")
        store = persist_track_audio(
            st,
            mid,
            tid,
            bytes(audio),
            filename=filename,
            workspace_id=ws,
        )
        if store.get("local_path"):
            track["local_path"] = store.get("local_path")
        if store.get("storage_ref"):
            track["storage_ref"] = store.get("storage_ref")
        track["playback_status"] = store.get("playback_status") or PLAYBACK_METADATA_ONLY
        if store.get("storage_error"):
            track["storage_error"] = store.get("storage_error")
        summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
        summary["has_audio"] = True
        track["analysis_summary"] = summary
        updated_tracks.append(track)

    fields["tracks"] = updated_tracks
    return fields


def save_multitrack_session_with_notes(
    session_state: dict[str, Any],
    *,
    project_name: str,
    notes: str = "",
    song_title: str = "",
    st: Any | None = None,
) -> tuple[bool, str, str]:
    """Save current multitrack project to catalog; optionally mirror legacy cloud history."""
    fields = build_multitrack_catalog_fields(
        session_state,
        project_name=project_name,
        notes=notes,
        song_title=song_title,
        st=st,
    )
    if not fields:
        return False, "", "no_layers_or_mix"

    active_mid = str(session_state.get(_LAST_CATALOG_MULTITRACK_KEY) or "").strip()
    existing_session: dict[str, Any] | None = None
    if active_mid:
        catalog = load_media_catalog(st=st)
        rows = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
        for row in rows:
            if isinstance(row, dict) and str(row.get("multitrack_id") or "") == active_mid:
                existing_session = migrate_multitrack_session(row)
                break
        _merge_track_ids(fields, existing_session)

    if active_mid:
        row = update_multitrack_session(st, active_mid, fields)
        if not row:
            row = add_multitrack_session(st, fields)
    else:
        row = add_multitrack_session(st, fields)

    mid = str(row.get("multitrack_id") or "")
    if mid:
        fields = _persist_session_tracks(st, session_state, mid, dict(row))
        row = update_multitrack_session(st, mid, fields)
        session_state[_LAST_CATALOG_MULTITRACK_KEY] = mid
        session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = mid

    legacy_ok, legacy_key, legacy_err = (False, "", "cloud_disabled")
    try:
        from studio_history_cloud import cloud_enabled
        from multitrack_history import save_multitrack_to_history

        if cloud_enabled():
            legacy_ok, legacy_key, legacy_err = save_multitrack_to_history(
                session_state,
                project_name=project_name,
                notes=notes,
                song_title=song_title,
                st=st,
            )
            if legacy_ok and legacy_key and mid:
                update_multitrack_session(st, mid, {"legacy_item_key": legacy_key, "updated_at": _utc_now_iso()})
    except ImportError:
        pass

    if mid:
        return True, mid, legacy_err if not legacy_ok else ""
    return False, "", "catalog_save_failed"


def migrate_legacy_multitrack_history(*, st: Any | None = None) -> int:
    """Import legacy multitrack_history saved_items into the media catalog once per session."""
    ss = _session_state(st)
    if ss is not None and ss.get(_MIGRATION_FLAG):
        return 0

    rows, _err = list_multitrack_history(st=st)
    if not rows:
        if ss is not None:
            ss[_MIGRATION_FLAG] = True
        return 0

    catalog = load_media_catalog(st=st)
    existing = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    known_legacy = {
        str(r.get("legacy_item_key") or "")
        for r in existing
        if isinstance(r, dict) and str(r.get("legacy_item_key") or "").strip()
    }
    known_ids = {str(r.get("multitrack_id") or "") for r in existing if isinstance(r, dict)}

    imported: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_key = str(row.get("item_key") or "").strip()
        if item_key and item_key in known_legacy:
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        merged = {**payload, "item_key": item_key}
        migrated = migrate_multitrack_session(merged)
        mid = str(migrated.get("multitrack_id") or "")
        if mid in known_ids:
            continue
        if item_key:
            migrated["legacy_item_key"] = item_key
        if payload.get("track_controls"):
            migrated["track_controls"] = payload.get("track_controls")
        imported.append(migrated)
        known_ids.add(mid)

    if not imported:
        if ss is not None:
            ss[_MIGRATION_FLAG] = True
        return 0

    catalog["multitrack_sessions"] = list(existing) + imported
    save_media_catalog(catalog, st=st)
    if ss is not None:
        ss[_MIGRATION_FLAG] = True
    return len(imported)


def list_catalog_multitrack_sessions(*, st: Any | None = None) -> tuple[list[dict[str, Any]], str | None]:
    migrate_legacy_multitrack_history(st=st)
    catalog = load_media_catalog(st=st)
    visible = normalize_multitrack_sessions(
        catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    )
    rows: list[dict[str, Any]] = []
    for session in visible:
        mid = str(session.get("multitrack_id") or "")
        if not mid:
            continue
        rows.append(
            {
                "item_key": mid,
                "title": session.get("title") or "Multitrack session",
                "updated_at": session.get("updated_at") or session.get("created_at"),
                "payload": session,
                "track_count": len(
                    real_multitrack_tracks(
                        session.get("tracks") if isinstance(session.get("tracks"), list) else []
                    )
                ),
                "storage_ref_count": sum(
                    1
                    for t in session.get("tracks") or []
                    if isinstance(t, dict) and not t.get("deleted") and t.get("storage_ref")
                ),
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows, None


def catalog_multitrack_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    name = str(payload.get("title") or row.get("title") or "Multitrack session")
    ws = str(payload.get("workspace_id") or "daniel")
    tracks = real_multitrack_tracks(payload.get("tracks") if isinstance(payload.get("tracks"), list) else [])
    loaded = sum(
        1
        for t in tracks
        if track_playback_status(t, session_workspace=ws) == PLAYBACK_PLAYABLE
    )
    meta_only = sum(
        1
        for t in tracks
        if track_playback_status(t, session_workspace=ws) == PLAYBACK_METADATA_ONLY
    )
    song = str(payload.get("song") or "").strip()
    bits = [name[:80]]
    if song:
        bits.append(song[:40])
    bits.append(f"{loaded} playable")
    if meta_only:
        bits.append(f"{meta_only} metadata-only")
    return " · ".join(bits)


def multitrack_session_stats(session: dict[str, Any], *, st: Any | None = None) -> dict[str, int]:
    row = migrate_multitrack_session(session)
    ws = str(row.get("workspace_id") or "daniel")
    tracks = real_multitrack_tracks(row.get("tracks") if isinstance(row.get("tracks"), list) else [])
    return {
        "track_count": len(tracks),
        "storage_ref_count": sum(1 for t in tracks if t.get("storage_ref")),
        "local_path_count": sum(1 for t in tracks if t.get("local_path")),
        "playable_count": sum(1 for t in tracks if track_playback_status(t, session_workspace=ws, st=st) == PLAYBACK_PLAYABLE),
        "metadata_only_count": sum(1 for t in tracks if track_playback_status(t, session_workspace=ws, st=st) == PLAYBACK_METADATA_ONLY),
    }


def apply_catalog_multitrack_to_session(
    session_state: dict[str, Any],
    session: dict[str, Any],
    *,
    st: Any | None = None,
    load_audio: bool = True,
) -> tuple[bool, str]:
    """Restore multitrack metadata; optionally lazy-load track audio blobs."""
    row = migrate_multitrack_session(session)
    payload = catalog_row_to_history_payload(row)
    if not payload.get("tracks"):
        return False, "no_tracks"

    apply_multitrack_history(session_state, payload)
    mid = str(row.get("multitrack_id") or "")
    if mid:
        session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = mid
        session_state[_LAST_CATALOG_MULTITRACK_KEY] = mid

    if not load_audio:
        session_state["_mt_catalog_metadata_only"] = True
        return True, "metadata_only"

    if "mt_tracks" not in session_state or not isinstance(session_state.get("mt_tracks"), dict):
        session_state["mt_tracks"] = {slot: None for slot in MULTITRACK_SLOTS}

    loaded = 0
    missing = 0
    ws = str(row.get("workspace_id") or "daniel")
    for track in row.get("tracks") or []:
        if not isinstance(track, dict) or track.get("deleted"):
            continue
        if not is_real_multitrack_track(track):
            continue
        slot = str(track.get("slot") or "")
        if slot not in MULTITRACK_SLOTS:
            continue
        status = track_playback_status(track, session_workspace=ws, st=st)
        if not status:
            continue
        if status != PLAYBACK_PLAYABLE:
            if status == PLAYBACK_METADATA_ONLY:
                missing += 1
            session_state["mt_tracks"][slot] = None
            continue
        audio, err = load_track_audio(track, session=row, st=st)
        if audio:
            session_state["mt_tracks"][slot] = audio
            loaded += 1
        else:
            session_state["mt_tracks"][slot] = None
            missing += 1

    session_state.pop("_mt_catalog_metadata_only", None)
    if loaded == 0 and missing > 0:
        return True, "metadata_only"
    if missing:
        return True, f"loaded_{loaded}_missing_{missing}"
    return True, ""


def delete_catalog_multitrack_session(multitrack_id: str, *, st: Any | None = None) -> tuple[bool, str]:
    mid = str(multitrack_id or "").strip()
    if not mid:
        return False, "missing_multitrack_id"
    catalog = load_media_catalog(st=st)
    rows = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    existing = next((r for r in rows if isinstance(r, dict) and str(r.get("multitrack_id") or "") == mid), None)
    if isinstance(existing, dict):
        delete_multitrack_session_files(existing, st=st)
    ok = delete_multitrack_session(st, mid)
    return ok, "" if ok else "delete_failed"

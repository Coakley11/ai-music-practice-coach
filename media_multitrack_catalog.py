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
from media_state import migrate_multitrack_session, normalize_multitrack_sessions
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
        tracks.append(
            {
                "slot": slot,
                "name": str(row.get("layer_name") or slot)[:120],
                "instrument": "",
                "duration_seconds": None,
                "local_path": None,
                "storage_ref": None,
                "analysis_summary": {
                    "volume": float(row.get("volume", ctrl.get("volume", 1.0))),
                    "delay": float(row.get("delay", ctrl.get("delay", 0.0))),
                    "mute": bool(row.get("mute", ctrl.get("mute", False))),
                    "solo": bool(row.get("solo", ctrl.get("solo", False))),
                    "has_audio": bool(row.get("has_audio")),
                    "metadata_only": bool(row.get("has_audio")) and not row.get("audio_embedded"),
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
    if active_mid:
        row = update_multitrack_session(st, active_mid, fields)
        if not row:
            row = add_multitrack_session(st, fields)
    else:
        row = add_multitrack_session(st, fields)

    mid = str(row.get("multitrack_id") or "")
    if mid:
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
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows, None


def catalog_multitrack_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    name = str(payload.get("title") or row.get("title") or "Multitrack session")
    tracks = payload.get("tracks") if isinstance(payload.get("tracks"), list) else []
    loaded = sum(
        1
        for t in tracks
        if isinstance(t, dict)
        and not t.get("deleted")
        and (t.get("storage_ref") or t.get("local_path") or (t.get("analysis_summary") or {}).get("has_audio"))
    )
    song = str(payload.get("song") or "").strip()
    if song:
        return f"{name[:80]} · {song[:40]} · {loaded} layer(s)"
    return f"{name[:100]} · {loaded} layer(s)"


def apply_catalog_multitrack_to_session(session_state: dict[str, Any], session: dict[str, Any]) -> bool:
    """Restore multitrack metadata from catalog (embedded audio only when present in legacy payload)."""
    payload = catalog_row_to_history_payload(session)
    if not payload.get("tracks"):
        return False
    apply_multitrack_history(session_state, payload)
    mid = str(migrate_multitrack_session(session).get("multitrack_id") or "")
    if mid:
        session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = mid
        session_state[_LAST_CATALOG_MULTITRACK_KEY] = mid
    return True


def delete_catalog_multitrack_session(multitrack_id: str, *, st: Any | None = None) -> tuple[bool, str]:
    mid = str(multitrack_id or "").strip()
    if not mid:
        return False, "missing_multitrack_id"
    ok = delete_multitrack_session(st, mid)
    return ok, "" if ok else "delete_failed"

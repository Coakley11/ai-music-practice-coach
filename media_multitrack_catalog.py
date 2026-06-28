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
    PLAYBACK_MISSING_FILE,
    PLAYBACK_PLAYABLE,
    PLAYBACK_UPLOAD_FAILED,
    backing_media_relpath,
    backing_playback_status,
    delete_multitrack_session_files,
    load_backing_audio,
    load_track_audio,
    persist_backing_audio,
    persist_track_audio,
    playback_status_label,
    recording_local_abs_path,
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

_MT_COUNT_IN_LABELS = ("None", "1 bar", "2 bars")
_MT_COUNT_IN_MAP = {"None": 0, "1 bar": 1, "2 bars": 2}
_MT_COUNT_IN_REVERSE = {0: "None", 1: "1 bar", 2: "2 bars"}


def active_catalog_multitrack_id(session_state: dict[str, Any]) -> str:
    """Resolved loaded/saved multitrack project id (one active project at a time)."""
    return str(
        session_state.get(_LAST_CATALOG_MULTITRACK_KEY)
        or session_state.get(_ACTIVE_CATALOG_MULTITRACK_KEY)
        or session_state.get("multitrack_catalog_active_id")
        or ""
    ).strip()


def _backing_bytes_from_session(session_state: dict[str, Any]) -> bytes | None:
    raw = session_state.get("multitrack_backing_music_wav")
    if isinstance(raw, bytearray):
        return bytes(raw) if raw else None
    if isinstance(raw, bytes) and raw:
        return raw
    return None


def _backing_bytes_from_local_path(
    workspace_id: str,
    local_path: str,
) -> bytes | None:
    rel = str(local_path or "").strip()
    if not rel:
        return None
    try:
        path = recording_local_abs_path(workspace_id, rel)
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
    except Exception:
        return None
    return None


def resolve_multitrack_slot_bytes(session_state: dict[str, Any], slot: str) -> bytes | None:
    try:
        from multitrack_session_persistence import resolve_multitrack_slot_bytes as _resolve

        return _resolve(session_state, slot)
    except ImportError:
        return None


def session_has_saveable_multitrack_content(session_state: dict[str, Any]) -> bool:
    """True when the session has layer audio, a mix, or prepared backing to save."""
    try:
        from multitrack_session_persistence import session_has_layer_audio
    except ImportError:
        session_has_layer_audio = lambda _ss, **kw: False  # type: ignore[assignment]

    if session_has_layer_audio(session_state):
        return True
    if isinstance(session_state.get("mixed_track_wav"), (bytes, bytearray)) and session_state.get("mixed_track_wav"):
        return True
    if _backing_bytes_from_session(session_state):
        return True
    if str(session_state.get("mt_backing_prepared_at") or "").strip():
        return True
    return False


def resolve_multitrack_backing_bytes(
    session_state: dict[str, Any],
    multitrack_id: str,
    *,
    existing_session: dict[str, Any] | None = None,
    workspace_id: str = "daniel",
) -> bytes | None:
    """Resolve prepared monitor backing bytes from session or durable local cache."""
    live = _backing_bytes_from_session(session_state)
    if live:
        return live
    ws = str(workspace_id or "daniel").strip() or "daniel"
    mid = str(multitrack_id or "").strip()
    row = migrate_multitrack_session(existing_session) if isinstance(existing_session, dict) else {}
    for rel in (
        str(row.get("backing_local_path") or "").strip(),
        backing_media_relpath(mid) if mid else "",
    ):
        cached = _backing_bytes_from_local_path(ws, rel)
        if cached:
            session_state["multitrack_backing_music_wav"] = cached
            return cached
    return None


def _record_backing_upload_diag(session_state: dict[str, Any], store: dict[str, Any]) -> None:
    err = str(store.get("cloud_error") or store.get("storage_error") or store.get("error") or "").strip()
    session_state["_mt_backing_last_upload_error"] = err or None
    session_state["_mt_backing_last_upload_ok"] = bool(store.get("ok"))
    session_state["_mt_backing_last_upload_cloud_ok"] = bool(store.get("cloud_ok"))
    session_state["_mt_backing_last_upload_storage_ref"] = store.get("storage_ref")


def _record_backing_load_diag(
    session_state: dict[str, Any],
    *,
    status: str,
    error: str = "",
    byte_count: int = 0,
) -> None:
    session_state["_mt_backing_playback_status"] = status
    session_state["_mt_backing_load_error"] = str(error or "").strip() or None
    session_state["_mt_backing_bytes_in_session"] = byte_count
    if error:
        session_state["_mt_backing_last_download_error"] = error


def _normalize_mt_backing_volume(val: Any, *, default: float = 0.75) -> float:
    try:
        from backing_track_state import normalize_backing_volume

        return normalize_backing_volume(val, default=default)
    except ImportError:
        try:
            n = float(val)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.5, round(n, 2)))


def gather_multitrack_backing_fields(session_state: dict[str, Any]) -> dict[str, Any]:
    """Collect multitrack session backing settings from live widget/session keys."""
    count_label = str(session_state.get("mt_count_in_bars") or "1 bar")
    count_bars = _MT_COUNT_IN_MAP.get(count_label, 1)
    multi = session_state.get("mt_multi_sections")
    return {
        "backing_volume": _normalize_mt_backing_volume(session_state.get("mt_backing_volume")),
        "backing_scope": str(session_state.get("mt_playback_scope") or "Full song").strip(),
        "backing_single_section": str(session_state.get("mt_single_section") or "").strip(),
        "backing_multi_sections": [str(x).strip() for x in multi if str(x).strip()]
        if isinstance(multi, list)
        else [],
        "backing_loops": int(session_state.get("mt_section_loops") or 2),
        "backing_groove": str(session_state.get("mt_groove_style") or "Auto").strip(),
        "backing_meter": str(session_state.get("mt_time_signature") or session_state.get("backing_time_signature") or "").strip(),
        "backing_count_in_bars": count_bars,
        "backing_use_monitor": bool(session_state.get("mt_use_backing_monitor", True)),
        "backing_include_in_mix": bool(session_state.get("include_backing_mix", False)),
        "backing_metronome": bool(session_state.get("mt_metronome_playback", False)),
        "backing_loop_section": bool(session_state.get("mt_loop_backing", True)),
        "backing_scope_label": str(session_state.get("mt_backing_scope") or "").strip(),
        "backing_prepared_at": str(session_state.get("mt_backing_prepared_at") or "").strip() or None,
    }


def apply_multitrack_backing_fields(session_state: dict[str, Any], row: dict[str, Any]) -> None:
    """Restore multitrack backing widget keys from a catalog row before widgets render."""
    migrated = migrate_multitrack_session(row)
    vol = migrated.get("backing_volume")
    if vol is not None:
        session_state["mt_backing_volume"] = _normalize_mt_backing_volume(vol)
    scope = str(migrated.get("backing_scope") or "").strip()
    if scope:
        session_state["mt_playback_scope"] = scope
    single = str(migrated.get("backing_single_section") or "").strip()
    if single:
        session_state["mt_single_section"] = single
    multi = migrated.get("backing_multi_sections")
    if isinstance(multi, list) and multi:
        session_state["mt_multi_sections"] = [str(x).strip() for x in multi if str(x).strip()]
    loops = migrated.get("backing_loops")
    if loops is not None:
        session_state["mt_section_loops"] = int(loops)
    groove = str(migrated.get("backing_groove") or "").strip()
    if groove:
        session_state["mt_groove_style"] = groove
    meter = str(migrated.get("backing_meter") or "").strip()
    if meter:
        session_state["mt_time_signature"] = meter
    count_bars = migrated.get("backing_count_in_bars")
    if count_bars is not None:
        session_state["mt_count_in_bars"] = _MT_COUNT_IN_REVERSE.get(int(count_bars), "1 bar")
    if "backing_use_monitor" in migrated:
        session_state["mt_use_backing_monitor"] = bool(migrated.get("backing_use_monitor"))
    if "backing_include_in_mix" in migrated:
        session_state["include_backing_mix"] = bool(migrated.get("backing_include_in_mix"))
    if "backing_metronome" in migrated:
        session_state["mt_metronome_playback"] = bool(migrated.get("backing_metronome"))
    if "backing_loop_section" in migrated:
        session_state["mt_loop_backing"] = bool(migrated.get("backing_loop_section"))
    scope_label = str(migrated.get("backing_scope_label") or "").strip()
    if scope_label:
        session_state["mt_backing_scope"] = scope_label
    prepared_at = str(migrated.get("backing_prepared_at") or "").strip()
    if prepared_at:
        session_state["mt_backing_prepared_at"] = prepared_at
    bpm = migrated.get("bpm")
    if bpm is not None:
        session_state["multitrack_bpm"] = int(bpm)


def multitrack_has_saved_backing(row: dict[str, Any]) -> bool:
    migrated = migrate_multitrack_session(row)
    return bool(
        str(migrated.get("backing_storage_ref") or "").strip()
        or str(migrated.get("backing_local_path") or "").strip()
    )


def seed_multitrack_backing_volume(session_state: dict[str, Any]) -> None:
    if "mt_backing_volume" in session_state:
        return
    session_state["mt_backing_volume"] = _normalize_mt_backing_volume(
        session_state.get("backing_volume"),
        default=0.75,
    )


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
        "backing_settings": {
            k: row.get(k)
            for k in (
                "backing_volume",
                "backing_scope",
                "backing_single_section",
                "backing_multi_sections",
                "backing_loops",
                "backing_groove",
                "backing_meter",
                "backing_count_in_bars",
                "backing_use_monitor",
                "backing_include_in_mix",
                "backing_metronome",
                "backing_loop_section",
                "backing_scope_label",
                "backing_prepared_at",
            )
            if row.get(k) is not None or k in row
        },
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
            "mute": bool(session_state.get(f"mt_mute_{slot}", ctrl.get("mute", False))),
            "solo": bool(session_state.get(f"mt_solo_{slot}", ctrl.get("solo", False))),
        }

    try:
        from studio_history_cloud import active_workspace_id

        workspace_id = active_workspace_id(st=st)
    except ImportError:
        workspace_id = "daniel"

    bpm = payload.get("session_bpm") or session_state.get("multitrack_bpm") or session_state.get("backing_track_bpm")
    backing_fields = gather_multitrack_backing_fields(session_state)
    try:
        from multitrack_mixer_state import gather_multitrack_transport_fields

        transport_fields = gather_multitrack_transport_fields(session_state)
    except ImportError:
        transport_fields = {}

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
        **backing_fields,
        **transport_fields,
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
        audio = resolve_multitrack_slot_bytes(session_state, slot)
        if not audio:
            summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
            summary["has_audio"] = True
            track["analysis_summary"] = summary
            track["playback_status"] = PLAYBACK_METADATA_ONLY
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


def _persist_session_backing(
    st: Any | None,
    session_state: dict[str, Any],
    multitrack_id: str,
    fields: dict[str, Any],
    *,
    audio: bytes | None = None,
    existing_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upload prepared monitor backing to durable storage; update refs on fields."""
    mid = str(multitrack_id or "").strip()
    ws = str(fields.get("workspace_id") or "daniel").strip()
    data = audio if isinstance(audio, (bytes, bytearray)) and audio else None
    if data is None:
        data = resolve_multitrack_backing_bytes(
            session_state,
            mid,
            existing_session=existing_session,
            workspace_id=ws,
        )
    if not data:
        if fields.get("backing_prepared_at"):
            fields["backing_playback_status"] = PLAYBACK_METADATA_ONLY
        return fields

    store = persist_backing_audio(st, mid, bytes(data), workspace_id=ws)
    _record_backing_upload_diag(session_state, store)
    if store.get("local_path"):
        fields["backing_local_path"] = store.get("local_path")
    if store.get("storage_ref"):
        fields["backing_storage_ref"] = store.get("storage_ref")
    elif fields.get("backing_prepared_at"):
        fields.pop("backing_storage_ref", None)
    if not fields.get("backing_prepared_at"):
        fields["backing_prepared_at"] = _utc_now_iso()
    fields["backing_playback_status"] = store.get("playback_status") or (
        PLAYBACK_PLAYABLE if store.get("ok") else PLAYBACK_UPLOAD_FAILED
    )
    err = str(store.get("cloud_error") or store.get("storage_error") or store.get("error") or "").strip()
    fields["backing_storage_error"] = err
    if store.get("ok"):
        session_state["multitrack_backing_music_wav"] = bytes(data)
    return fields


def _merge_backing_refs(fields: dict[str, Any], existing_session: dict[str, Any] | None) -> None:
    """Preserve durable refs only when the live session has no newer prepared backing."""
    if not existing_session:
        return
    if fields.get("backing_prepared_at") and str(fields.get("backing_prepared_at")) >= str(
        existing_session.get("backing_prepared_at") or ""
    ):
        return
    for key in ("backing_storage_ref", "backing_local_path", "backing_prepared_at", "backing_playback_status"):
        if not fields.get(key) and existing_session.get(key):
            fields[key] = existing_session.get(key)


def persist_prepared_multitrack_backing(
    session_state: dict[str, Any],
    monitor_wav: bytes,
    *,
    st: Any | None = None,
    scope_label: str = "",
) -> tuple[bool, str]:
    """Store prepared backing in session; update active catalog project when one is loaded."""
    session_state["multitrack_backing_music_wav"] = monitor_wav
    session_state["mt_backing_prepared_at"] = _utc_now_iso()
    if scope_label:
        session_state["mt_backing_scope"] = scope_label

    active_mid = active_catalog_multitrack_id(session_state)
    if not active_mid:
        session_state.pop("_mt_loaded_backing_project_id", None)
        return True, "session_only"

    catalog = load_media_catalog(st=st)
    rows = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    existing: dict[str, Any] | None = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("multitrack_id") or "") == active_mid:
            existing = migrate_multitrack_session(row)
            break

    fields = gather_multitrack_backing_fields(session_state)
    if existing:
        fields = {**existing, **fields, "updated_at": _utc_now_iso()}
    else:
        fields["updated_at"] = _utc_now_iso()
    fields = _persist_session_backing(
        st,
        session_state,
        active_mid,
        fields,
        audio=monitor_wav,
        existing_session=existing,
    )
    row = update_multitrack_session(st, active_mid, fields)
    if not row:
        return False, "catalog_update_failed"
    session_state[_LAST_CATALOG_MULTITRACK_KEY] = active_mid
    session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = active_mid
    return True, "updated_project"


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
        if not session_has_saveable_multitrack_content(session_state):
            return False, "", "nothing_to_save"
        try:
            from studio_history_cloud import active_workspace_id
        except ImportError:
            active_workspace_id = lambda *, st=None: "daniel"  # type: ignore[assignment]
        fields = {
            "workspace_id": active_workspace_id(st=st),
            "title": str(project_name or "Multitrack session").strip()[:120],
            "song": str(song_title or session_state.get("active_song_title") or "").strip(),
            "tracks": [],
            "track_controls": {},
            **gather_multitrack_backing_fields(session_state),
        }
        try:
            from multitrack_mixer_state import gather_multitrack_transport_fields

            fields.update(gather_multitrack_transport_fields(session_state))
        except ImportError:
            pass

    active_mid = active_catalog_multitrack_id(session_state)
    existing_session: dict[str, Any] | None = None
    if active_mid:
        catalog = load_media_catalog(st=st)
        rows = catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
        for row in rows:
            if isinstance(row, dict) and str(row.get("multitrack_id") or "") == active_mid:
                existing_session = migrate_multitrack_session(row)
                break
        _merge_track_ids(fields, existing_session)
        _merge_backing_refs(fields, existing_session)

    if active_mid:
        row = update_multitrack_session(st, active_mid, fields)
        if not row:
            row = add_multitrack_session(st, fields)
    else:
        row = add_multitrack_session(st, fields)

    mid = str(row.get("multitrack_id") or "")
    if mid:
        fields = _persist_session_tracks(st, session_state, mid, dict(row))
        fields = _persist_session_backing(
            st,
            session_state,
            mid,
            fields,
            existing_session=existing_session if active_mid == mid else migrate_multitrack_session(dict(row)),
        )
        row = update_multitrack_session(st, mid, fields)
        session_state[_LAST_CATALOG_MULTITRACK_KEY] = mid
        session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = mid
        session_state["multitrack_catalog_active_id"] = mid

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
                "backing_storage_ref": str(session.get("backing_storage_ref") or "").strip() or None,
                "backing_playable": backing_playback_status(session, session_workspace=str(session.get("workspace_id") or "daniel"), st=st)
                == PLAYBACK_PLAYABLE,
            }
        )
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows, None


def multitrack_layer_status_counts(
    payload: dict[str, Any],
    *,
    session_workspace: str = "",
    st: Any | None = None,
) -> tuple[int, int]:
    """Return (playable_layers, metadata_only_layers) for saved project summary."""
    ws = str(session_workspace or payload.get("workspace_id") or "daniel")
    tracks = real_multitrack_tracks(payload.get("tracks") if isinstance(payload.get("tracks"), list) else [])
    playable = 0
    meta_only = 0
    for track in tracks:
        status = track_playback_status(track, session_workspace=ws, st=st)
        if status == PLAYBACK_PLAYABLE:
            playable += 1
        elif status in (PLAYBACK_METADATA_ONLY, PLAYBACK_MISSING_FILE, PLAYBACK_UPLOAD_FAILED):
            summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
            if summary.get("has_audio") or track.get("storage_ref") or track.get("local_path"):
                meta_only += 1
    return playable, meta_only


def _multitrack_backing_summary_part(payload: dict[str, Any], *, session_workspace: str = "", st: Any | None = None) -> str:
    ws = str(session_workspace or payload.get("workspace_id") or "daniel")
    if multitrack_has_saved_backing(payload):
        prepared = str(payload.get("backing_prepared_at") or "").strip()
        if prepared:
            return f"backing ready · {prepared[:16]}"
        return "backing ready"
    has_settings = bool(
        payload.get("backing_prepared_at")
        or payload.get("backing_volume") is not None
        or str(payload.get("backing_scope") or "").strip()
        or payload.get("backing_loops") is not None
    )
    if not has_settings:
        return ""
    status = backing_playback_status(payload, session_workspace=ws, st=st)
    if status == PLAYBACK_PLAYABLE:
        return "backing ready"
    if status == PLAYBACK_METADATA_ONLY:
        return "backing settings saved · backing audio missing"
    return "backing settings saved · backing audio missing"


def catalog_multitrack_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    name = str(payload.get("title") or row.get("title") or "Multitrack session")
    ws = str(payload.get("workspace_id") or "daniel")
    playable, meta_only = multitrack_layer_status_counts(payload, session_workspace=ws)
    song = str(payload.get("song") or "").strip()
    bits = [name[:80]]
    if song:
        bits.append(song[:40])
    if playable:
        bits.append(f"{playable} playable")
    if meta_only:
        bits.append(f"{meta_only} recorded layer(s) · audio missing")
    if not playable and not meta_only:
        bits.append("0 recorded layers")
    backing_part = _multitrack_backing_summary_part(payload, session_workspace=ws)
    if backing_part:
        bits.append(backing_part)
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


def clear_multitrack_page_snapshot_backing(session_state: dict[str, Any]) -> None:
    """Drop stale monitor backing bytes from the stored multitrack page snapshot."""
    store = session_state.get("_studio_page_snapshots")
    if not isinstance(store, dict):
        return
    snap = store.get("multitrack")
    if not isinstance(snap, dict):
        return
    updated = dict(snap)
    updated.pop("multitrack_backing_music_wav", None)
    store["multitrack"] = updated


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

    mid = str(row.get("multitrack_id") or "")
    session_state.pop("multitrack_backing_music_wav", None)
    session_state.pop("_mt_loaded_backing_project_id", None)
    clear_multitrack_page_snapshot_backing(session_state)

    apply_multitrack_backing_fields(session_state, row)
    try:
        from multitrack_mixer_state import apply_multitrack_transport_fields

        apply_multitrack_transport_fields(session_state, row)
    except ImportError:
        pass
    apply_multitrack_history(session_state, payload)
    try:
        from multitrack_mixer_state import sync_mixer_widgets_from_canonical

        sync_mixer_widgets_from_canonical(session_state)
    except ImportError:
        pass
    if mid:
        session_state[_ACTIVE_CATALOG_MULTITRACK_KEY] = mid
        session_state[_LAST_CATALOG_MULTITRACK_KEY] = mid
        session_state["multitrack_catalog_active_id"] = mid

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

    backing_ref = str(row.get("backing_storage_ref") or "").strip()
    backing_local = str(row.get("backing_local_path") or "").strip()
    has_backing_meta = bool(row.get("backing_prepared_at") or backing_ref or backing_local)
    if load_audio and has_backing_meta:
        status = backing_playback_status(row, session_workspace=ws, st=st)
        if backing_ref or backing_local:
            audio, err = load_backing_audio(row, st=st)
            if audio:
                session_state["multitrack_backing_music_wav"] = audio
                session_state["_mt_loaded_backing_project_id"] = mid
                _record_backing_load_diag(session_state, status=PLAYBACK_PLAYABLE, byte_count=len(audio))
            else:
                session_state.pop("multitrack_backing_music_wav", None)
                if mid:
                    session_state["_mt_loaded_backing_project_id"] = mid
                load_status = PLAYBACK_METADATA_ONLY if status == PLAYBACK_METADATA_ONLY else PLAYBACK_MISSING_FILE
                _record_backing_load_diag(session_state, status=load_status, error=err or "missing_file")
        elif row.get("backing_prepared_at"):
            session_state.pop("multitrack_backing_music_wav", None)
            if mid:
                session_state["_mt_loaded_backing_project_id"] = mid
            _record_backing_load_diag(session_state, status=PLAYBACK_METADATA_ONLY, error="no_backing_ref")
    elif mid:
        session_state["_mt_loaded_backing_project_id"] = mid

    if loaded == 0 and missing > 0:
        return True, "metadata_only"
    if missing:
        return True, f"loaded_{loaded}_missing_{missing}"
    return True, ""


def load_multitrack_project_from_catalog(
    session_state: dict[str, Any],
    multitrack_id: str,
    *,
    st: Any | None = None,
    load_audio: bool = True,
) -> tuple[bool, str]:
    """Reload catalog from cloud/disk and restore one saved multitrack project."""
    mid = str(multitrack_id or "").strip()
    if not mid:
        return False, "missing_multitrack_id"
    catalog = load_media_catalog(st=st)
    rows = normalize_multitrack_sessions(
        catalog.get("multitrack_sessions") if isinstance(catalog.get("multitrack_sessions"), list) else []
    )
    row = next((r for r in rows if str(r.get("multitrack_id") or "") == mid), None)
    if not isinstance(row, dict):
        return False, "not_found"
    try:
        from multitrack_history import clear_multitrack_widget_keys

        clear_multitrack_widget_keys(session_state)
    except ImportError:
        pass
    ok, msg = apply_catalog_multitrack_to_session(session_state, row, st=st, load_audio=load_audio)
    if ok:
        clear_multitrack_page_snapshot_backing(session_state)
        try:
            from multitrack_mixer_state import prepare_multitrack_transport_widgets

            prepare_multitrack_transport_widgets(session_state)
        except ImportError:
            pass
        try:
            from studio_page_persistence import flush_current_page_snapshot

            flush_current_page_snapshot(session_state)
        except Exception:
            pass
    return ok, msg


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

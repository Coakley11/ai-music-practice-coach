"""Multitrack working-session persistence (layer audio + filenames)."""

from __future__ import annotations

import base64
import copy
from typing import Any

from studio_page_persistence import _B64_MARKER, _decode_snapshot_value, _encode_snapshot_value

MAX_MT_TRACK_BYTES = 2_097_152
MAX_MT_MIXED_BYTES = 2_621_440
DIAG_KEY = "_multitrack_persist_diag"


def _track_has_audio(value: Any) -> bool:
    return bool(value) and isinstance(value, (bytes, bytearray))


def count_mt_layers(mt: dict[str, Any] | None) -> int:
    if not isinstance(mt, dict):
        return 0
    return sum(1 for v in mt.values() if _track_has_audio(v))


def resolve_multitrack_slot_bytes(session_state: dict[str, Any], slot: str) -> bytes | None:
    """Resolve one layer's audio bytes from live session, persist blob, or page snapshot."""
    def _bytes_from_map(mt: Any) -> bytes | None:
        if not isinstance(mt, dict):
            return None
        raw = mt.get(slot)
        if _track_has_audio(raw):
            return bytes(raw)
        decoded = decode_mt_tracks_from_persist(mt)
        if isinstance(decoded, dict):
            cached = decoded.get(slot)
            if _track_has_audio(cached):
                return bytes(cached)
        return None

    live = _bytes_from_map(session_state.get("mt_tracks"))
    if live:
        return live
    blob = _bytes_from_map(session_state.get("_mt_tracks_persist_blob"))
    if blob:
        return blob
    store = session_state.get("_studio_page_snapshots")
    if isinstance(store, dict):
        snap = store.get("multitrack")
        if isinstance(snap, dict):
            cached = _bytes_from_map(snap.get("mt_tracks"))
            if cached:
                return cached
    return None


def session_has_layer_audio(session_state: dict[str, Any], *, slots: tuple[str, ...] | None = None) -> bool:
    try:
        from multitrack_slots import MULTITRACK_SLOTS
    except ImportError:
        MULTITRACK_SLOTS = ()  # type: ignore[assignment]
    target = slots if slots is not None else MULTITRACK_SLOTS
    return any(resolve_multitrack_slot_bytes(session_state, slot) for slot in target)


def reset_multitrack_working_session(session_state: dict[str, Any]) -> None:
    """Clear live multitrack layers/mixer widgets before loading a different saved project."""
    try:
        from multitrack_history import clear_multitrack_widget_keys
        from multitrack_slots import MULTITRACK_SLOTS
    except ImportError:
        MULTITRACK_SLOTS = ()  # type: ignore[assignment]
        clear_multitrack_widget_keys = lambda _ss: None  # type: ignore[assignment]
    clear_multitrack_widget_keys(session_state)
    session_state["mt_tracks"] = {slot: None for slot in MULTITRACK_SLOTS}
    session_state["mt_track_filenames"] = {
        slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MULTITRACK_SLOTS
    }
    session_state["mixed_track_wav"] = None
    session_state["mt_track_controls"] = {}
    session_state.pop("multitrack_history_loaded_notes", None)
    session_state.pop("multitrack_backing_music_wav", None)
    session_state.pop("_mt_loaded_backing_project_id", None)
    session_state.pop("_mt_tracks_persist_blob", None)
    session_state.pop("_mt_backing_playback_status", None)
    session_state.pop("_mt_backing_load_error", None)
    for key in list(session_state.keys()):
        if key.startswith(("mt_vol_", "mt_delay_", "mt_name_", "mt_mute_", "mt_solo_")):
            session_state.pop(key, None)
    try:
        clear_multitrack_page_snapshot(session_state)
    except Exception:
        pass


def clear_multitrack_page_snapshot(session_state: dict[str, Any]) -> None:
    """Replace the multitrack page snapshot with an empty working session."""
    try:
        from multitrack_slots import MULTITRACK_SLOTS
    except ImportError:
        MULTITRACK_SLOTS = ()  # type: ignore[assignment]
    store = session_state.get("_studio_page_snapshots")
    if not isinstance(store, dict):
        session_state["_studio_page_snapshots"] = {}
        store = session_state["_studio_page_snapshots"]
    store["multitrack"] = {
        "mt_tracks": {slot: None for slot in MULTITRACK_SLOTS},
        "mt_track_filenames": {
            slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MULTITRACK_SLOTS
        },
        "mt_track_controls": {},
        "mixed_track_wav": None,
    }
    store["multitrack"].pop("multitrack_backing_music_wav", None)


def encode_mt_tracks_for_persist(mt: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Encode ``mt_tracks`` slot map for JSON/cloud save with size guards."""
    diag: dict[str, Any] = {
        "tracks_before": 0,
        "tracks_persisted": 0,
        "audio_persisted": False,
        "skipped_due_to_size": [],
    }
    if not isinstance(mt, dict):
        return {}, diag
    out: dict[str, Any] = {}
    for slot, raw in mt.items():
        if not _track_has_audio(raw):
            out[str(slot)] = None
            continue
        diag["tracks_before"] += 1
        data = bytes(raw)
        if len(data) > MAX_MT_TRACK_BYTES:
            out[str(slot)] = None
            diag["skipped_due_to_size"].append({"slot": str(slot), "bytes": len(data)})
            continue
        out[str(slot)] = _encode_snapshot_value(data)
        diag["tracks_persisted"] += 1
    diag["audio_persisted"] = diag["tracks_persisted"] > 0
    return out, diag


def decode_mt_tracks_from_persist(encoded: Any) -> dict[str, Any | None]:
    if not isinstance(encoded, dict):
        return {}
    out: dict[str, Any | None] = {}
    for slot, raw in encoded.items():
        if raw is None:
            out[str(slot)] = None
            continue
        decoded = _decode_snapshot_value(raw)
        out[str(slot)] = decoded if _track_has_audio(decoded) else None
    return out


def encode_mixed_track_for_persist(data: Any) -> tuple[Any, dict[str, Any]]:
    if not _track_has_audio(data):
        return None, {"mixed_persisted": False, "mixed_skipped_bytes": 0}
    raw = bytes(data)
    if len(raw) > MAX_MT_MIXED_BYTES:
        return None, {"mixed_persisted": False, "mixed_skipped_bytes": len(raw)}
    return _encode_snapshot_value(raw), {"mixed_persisted": True, "mixed_skipped_bytes": 0}


def decode_mixed_track_from_persist(value: Any) -> bytes | None:
    if value is None:
        return None
    decoded = _decode_snapshot_value(value)
    return bytes(decoded) if _track_has_audio(decoded) else None


def record_multitrack_persist_diag(session_state: dict[str, Any], diag: dict[str, Any]) -> None:
    prior = session_state.get(DIAG_KEY) if isinstance(session_state.get(DIAG_KEY), dict) else {}
    merged = dict(prior)
    merged.update(diag)
    merged["mt_tracks_count_after_save"] = count_mt_layers(session_state.get("mt_tracks"))
    session_state[DIAG_KEY] = merged


def record_multitrack_restore_diag(session_state: dict[str, Any], *, source: str) -> None:
    session_state[DIAG_KEY] = {
        "restore_source": source,
        "mt_tracks_count_after_restore": count_mt_layers(session_state.get("mt_tracks")),
        "mixed_track_restored": bool(session_state.get("mixed_track_wav")),
    }


def restore_multitrack_session_if_needed(session_state: dict[str, Any]) -> bool:
    """Apply top-level persisted multitrack blobs when slots are empty after refresh."""
    mt = session_state.get("mt_tracks")
    if count_mt_layers(mt) > 0 or session_state.get("mixed_track_wav"):
        record_multitrack_restore_diag(session_state, source="session_already_hydrated")
        return False
    encoded = session_state.get("_mt_tracks_persist_blob")
    if isinstance(encoded, dict) and encoded:
        session_state["mt_tracks"] = decode_mt_tracks_from_persist(encoded)
        record_multitrack_restore_diag(session_state, source="mt_tracks_persist_blob")
        return True
    return False


def clear_multitrack_persisted_state(session_state: dict[str, Any]) -> None:
    """Clear live multitrack layers and persisted blobs so stale audio cannot restore."""
    try:
        from multitrack_history import clear_multitrack_widget_keys
        from multitrack_slots import MULTITRACK_SLOTS
    except ImportError:
        MULTITRACK_SLOTS = (  # type: ignore[misc, assignment]
            "Guitar",
            "Bass",
            "Piano / Keys",
            "Vocals",
            "Sax / winds",
            "Extra layer",
        )
        clear_multitrack_widget_keys = lambda _ss: None  # type: ignore[misc, assignment]

    clear_multitrack_widget_keys(session_state)
    session_state["mt_tracks"] = {slot: None for slot in MULTITRACK_SLOTS}
    session_state["mt_track_filenames"] = {
        slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MULTITRACK_SLOTS
    }
    session_state["mixed_track_wav"] = None
    session_state.pop("multitrack_backing_music_wav", None)
    session_state.pop("mt_backing_prepared_at", None)
    session_state.pop("mt_backing_volume", None)
    session_state["mt_track_controls"] = {}
    session_state.pop("_mt_tracks_persist_blob", None)

    for key in list(session_state.keys()):
        if key.startswith(("mt_vol_", "mt_delay_", "mt_name_", "mt_mute_", "mt_solo_")):
            session_state.pop(key, None)

    store = session_state.get("_studio_page_snapshots")
    if isinstance(store, dict) and isinstance(store.get("multitrack"), dict):
        snap = dict(store["multitrack"])
        snap["mt_tracks"] = {slot: None for slot in MULTITRACK_SLOTS}
        snap.pop("mixed_track_wav", None)
        snap.pop("multitrack_backing_music_wav", None)
        snap.pop("_mt_tracks_persist_blob", None)
        store["multitrack"] = snap


def restore_multitrack_layers_from_workspace(session_state: dict[str, Any]) -> bool:
    """Hydrate multitrack layers from cloud/disk payload (top-level blob or page snapshot)."""
    if session_state.pop("_mt_skip_layer_restore_once", None):
        return False
    if count_mt_layers(session_state.get("mt_tracks")) > 0 or session_state.get("mixed_track_wav"):
        record_multitrack_restore_diag(session_state, source="session_already_hydrated")
        return False
    if restore_multitrack_session_if_needed(session_state):
        return True

    store = session_state.get("_studio_page_snapshots")
    snap = store.get("multitrack") if isinstance(store, dict) else None
    if isinstance(snap, dict):
        mt = snap.get("mt_tracks")
        if isinstance(mt, dict):
            decoded = decode_mt_tracks_from_persist(mt)
            if count_mt_layers(decoded) > 0:
                session_state["mt_tracks"] = decoded
                filenames = snap.get("mt_track_filenames")
                if isinstance(filenames, dict):
                    session_state["mt_track_filenames"] = copy.deepcopy(filenames)
                record_multitrack_restore_diag(session_state, source="multitrack_page_snapshot")
                return True
    return False

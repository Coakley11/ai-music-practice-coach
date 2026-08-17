"""Multitrack project history library — metadata-first, cloud-backed."""

from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
from typing import Any

from analysis_session_persistence import sanitize_analysis_result_for_persist
from multitrack_slots import MULTITRACK_SLOTS
from studio_history_cloud import (
    MAX_PER_TRACK_EMBED_BYTES,
    MAX_TOTAL_TRACK_EMBED_BYTES,
    active_workspace_id,
    decode_audio_b64,
    encode_audio_if_safe,
    json_safe,
    list_history_items,
    new_history_item_key,
    save_history_item,
)

ITEM_TYPE = "multitrack_history"
PAYLOAD_VERSION = 1
PENDING_LOAD_KEY = "_pending_multitrack_history_payload"
FLASH_KEY = "_multitrack_history_flash"

def _control_for_slot(
    controls: dict[str, Any],
    session_state: dict[str, Any],
    slot: str,
) -> tuple[dict[str, Any], str]:
    layer_name = str(session_state.get(f"mt_name_{slot}") or slot)
    if isinstance(controls.get(slot), dict):
        return controls[slot], layer_name
    if isinstance(controls.get(layer_name), dict):
        return controls[layer_name], layer_name
    return {}, layer_name


def clear_multitrack_widget_keys(session_state: dict[str, Any]) -> None:
    """Drop widget-backed keys before restoring a saved project on the next run."""
    for slot in MULTITRACK_SLOTS:
        for key in (
            f"mt_name_{slot}",
            f"mt_vol_{slot}",
            f"mt_vol_slider_{slot}",
            f"mt_delay_{slot}",
            f"mt_delay_slider_{slot}",
            f"mt_mute_{slot}",
            f"mt_solo_{slot}",
            f"mt_upload_{slot}",
            f"mt_record_{slot}",
        ):
            session_state.pop(key, None)
    for key in (
        "mt_loop_backing",
        "mt_metronome_playback",
        "mt_use_backing_monitor",
        "include_backing_mix",
        "mt_backing_volume",
        "mt_playback_scope",
        "mt_single_section",
        "mt_multi_sections",
        "mt_section_loops",
        "mt_groove_style",
        "mt_time_signature",
        "mt_count_in_bars",
        "mt_backing_scope",
        "mt_backing_prepared_at",
        "multitrack_bpm",
    ):
        session_state.pop(key, None)


def _analysis_summary(session_state: dict[str, Any]) -> dict[str, Any] | None:
    raw = session_state.get("last_analysis_result")
    if not isinstance(raw, dict) or not raw.get("multitrack"):
        return None
    clean = sanitize_analysis_result_for_persist(raw)
    out: dict[str, Any] = {
        "coach_summary": str(clean.get("coach_summary") or "")[:500],
        "scores": clean.get("scores") if isinstance(clean.get("scores"), dict) else {},
        "layer_scores": clean.get("layer_scores") if isinstance(clean.get("layer_scores"), list) else [],
        "findings": clean.get("findings") if isinstance(clean.get("findings"), list) else [],
        "tips": clean.get("tips") if isinstance(clean.get("tips"), list) else [],
        "layers": clean.get("layers") if isinstance(clean.get("layers"), list) else [],
        "instrument": clean.get("instrument") or "",
    }
    for key in (
        "practice_focus_snapshot",
        "practice_focus_at_analysis",
        "practice_focus_evaluation",
        "measured_comparisons",
    ):
        if key in clean:
            out[key] = clean[key]
    return out


def default_project_name(session_state: dict[str, Any], *, song_title: str = "") -> str:
    song = str(song_title or session_state.get("active_song_title") or "Multitrack").strip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    loaded = [s for s in MULTITRACK_SLOTS if session_state.get("mt_tracks", {}).get(s)]
    if loaded:
        return f"{song} — {len(loaded)} layer(s) — {stamp}"
    return f"{song} — {stamp}"


def build_multitrack_history_payload(
    session_state: dict[str, Any],
    *,
    project_name: str,
    notes: str = "",
    song_title: str = "",
    st: Any | None = None,
) -> tuple[dict[str, Any] | None, str]:
    mt_tracks = session_state.get("mt_tracks")
    if not isinstance(mt_tracks, dict):
        mt_tracks = {}
    filenames = session_state.get("mt_track_filenames")
    if not isinstance(filenames, dict):
        filenames = {}
    controls = session_state.get("mt_track_controls")
    if not isinstance(controls, dict):
        controls = {}

    has_any = any(mt_tracks.get(slot) for slot in MULTITRACK_SLOTS) or session_state.get("mixed_track_wav")
    if not has_any:
        try:
            from multitrack_session_persistence import session_has_layer_audio

            has_any = session_has_layer_audio(session_state)
        except ImportError:
            pass
    if not has_any:
        try:
            from media_multitrack_catalog import session_has_saveable_multitrack_content

            if not session_has_saveable_multitrack_content(session_state):
                return None, "no_layers_or_mix"
        except ImportError:
            return None, "no_layers_or_mix"

    tracks_meta: list[dict[str, Any]] = []
    embedded_tracks: dict[str, str] = {}
    embed_budget = MAX_TOTAL_TRACK_EMBED_BYTES
    slot_controls: dict[str, dict[str, Any]] = {}

    for slot in MULTITRACK_SLOTS:
        try:
            from multitrack_session_persistence import resolve_multitrack_slot_bytes
        except ImportError:
            resolve_multitrack_slot_bytes = lambda _ss, _slot: None  # type: ignore[assignment]
        audio = resolve_multitrack_slot_bytes(session_state, slot)
        ctrl, layer_name = _control_for_slot(controls, session_state, slot)
        volume = session_state.get(f"mt_vol_{slot}", session_state.get(f"mt_vol_slider_{slot}", ctrl.get("volume", 1.0)))
        delay = session_state.get(f"mt_delay_{slot}", session_state.get(f"mt_delay_slider_{slot}", ctrl.get("delay", 0.0)))
        mute = bool(session_state.get(f"mt_mute_{slot}", ctrl.get("mute", False)))
        solo = bool(session_state.get(f"mt_solo_{slot}", ctrl.get("solo", False)))
        slot_controls[slot] = {
            "volume": float(volume) if volume is not None else 1.0,
            "delay": float(delay) if delay is not None else 0.0,
            "mute": mute,
            "solo": solo,
        }
        filename = str(filenames.get(slot) or f"{slot.replace(' ', '_').lower()}.wav")
        has_audio = isinstance(audio, (bytes, bytearray)) and bool(audio)
        if not has_audio:
            continue
        meta: dict[str, Any] = {
            "slot": slot,
            "layer_name": layer_name[:80],
            "filename": filename[:200],
            "volume": float(volume) if volume is not None else 1.0,
            "delay": float(delay) if delay is not None else 0.0,
            "mute": mute,
            "solo": solo,
            "has_audio": True,
            "audio_embedded": False,
        }
        raw = bytes(audio)
        if len(raw) <= MAX_PER_TRACK_EMBED_BYTES and len(raw) <= embed_budget:
            embedded_tracks[slot] = base64.b64encode(raw).decode("ascii")
            meta["audio_embedded"] = True
            embed_budget -= len(raw)
        tracks_meta.append(meta)

    mixed_b64, mixed_skip = encode_audio_if_safe(session_state.get("mixed_track_wav"))

    payload = json_safe(
        {
            "version": PAYLOAD_VERSION,
            "workspace_id": active_workspace_id(st=st),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "project_name": str(project_name or default_project_name(session_state, song_title=song_title)).strip()[:120],
            "song_title": str(song_title or "")[:120],
            "notes": str(notes or "").strip()[:2000],
            "tracks": tracks_meta,
            "track_controls": slot_controls,
            "embedded_tracks": embedded_tracks,
            "mixed_preview_b64": mixed_b64,
            "mixed_skip_reason": mixed_skip,
            "session_bpm": session_state.get("multitrack_bpm") or session_state.get("backing_track_bpm"),
            "session_groove": str(session_state.get("backing_groove_style") or ""),
            "analysis_summary": _analysis_summary(session_state),
        }
    )
    return payload, ""


def save_multitrack_to_history(
    session_state: dict[str, Any],
    *,
    project_name: str,
    notes: str = "",
    song_title: str = "",
    st: Any | None = None,
) -> tuple[bool, str, str]:
    payload, build_err = build_multitrack_history_payload(
        session_state,
        project_name=project_name,
        notes=notes,
        song_title=song_title,
        st=st,
    )
    if not payload:
        return False, "", build_err or "build_failed"
    item_key = new_history_item_key("mt")
    ok, err = save_history_item(
        item_type=ITEM_TYPE,
        item_key=item_key,
        title=str(payload.get("project_name") or "Multitrack project"),
        payload=payload,
    )
    return ok, item_key if ok else "", err


def list_multitrack_history(*, st: Any | None = None, limit: int = 40) -> tuple[list[dict[str, Any]], str | None]:
    return list_history_items(item_type=ITEM_TYPE, st=st, limit=limit)


def queue_multitrack_history_load(session_state: dict[str, Any], payload: dict[str, Any]) -> None:
    session_state[PENDING_LOAD_KEY] = copy.deepcopy(payload)


def apply_pending_multitrack_history(session_state: dict[str, Any]) -> dict[str, Any] | None:
    payload = session_state.pop(PENDING_LOAD_KEY, None)
    if not isinstance(payload, dict):
        return None
    clear_multitrack_widget_keys(session_state)
    return apply_multitrack_history(session_state, payload)


def apply_multitrack_history(session_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Restore project metadata and any embedded audio. Returns info flags for UI."""
    info = {"restored_layers": 0, "metadata_only_layers": 0, "mixed_restored": False}

    if "mt_tracks" not in session_state or not isinstance(session_state.get("mt_tracks"), dict):
        session_state["mt_tracks"] = {slot: None for slot in MULTITRACK_SLOTS}
    if "mt_track_filenames" not in session_state or not isinstance(session_state.get("mt_track_filenames"), dict):
        session_state["mt_track_filenames"] = {
            slot: f"{slot.replace(' ', '_').lower()}.wav" for slot in MULTITRACK_SLOTS
        }

    embedded = payload.get("embedded_tracks") if isinstance(payload.get("embedded_tracks"), dict) else {}
    tracks = payload.get("tracks") if isinstance(payload.get("tracks"), list) else []

    for row in tracks:
        if not isinstance(row, dict):
            continue
        slot = str(row.get("slot") or "")
        if slot not in MULTITRACK_SLOTS:
            continue
        session_state["mt_track_filenames"][slot] = str(
            row.get("filename") or session_state["mt_track_filenames"].get(slot, "")
        )
        session_state[f"mt_name_{slot}"] = str(row.get("layer_name") or slot)
        session_state[f"mt_vol_{slot}"] = float(row.get("volume", 1.0))
        session_state[f"mt_delay_{slot}"] = float(row.get("delay", 0.0))
        session_state[f"mt_mute_{slot}"] = bool(row.get("mute", False))
        session_state[f"mt_solo_{slot}"] = bool(row.get("solo", False))
        b64 = embedded.get(slot)
        audio = decode_audio_b64(b64) if isinstance(b64, str) else None
        if audio:
            session_state["mt_tracks"][slot] = audio
            info["restored_layers"] += 1
        elif row.get("has_audio"):
            session_state["mt_tracks"][slot] = None
            info["metadata_only_layers"] += 1
        else:
            session_state["mt_tracks"][slot] = None

    controls_src = payload.get("track_controls") if isinstance(payload.get("track_controls"), dict) else {}
    slot_controls: dict[str, dict[str, Any]] = {}
    for row in tracks:
        if not isinstance(row, dict):
            continue
        slot = str(row.get("slot") or "")
        if slot not in MULTITRACK_SLOTS:
            continue
        layer_name = str(row.get("layer_name") or slot)
        base = controls_src.get(slot) if isinstance(controls_src.get(slot), dict) else {}
        if not base and isinstance(controls_src.get(layer_name), dict):
            base = controls_src[layer_name]
        slot_controls[slot] = {
            "volume": float(row.get("volume", base.get("volume", 1.0))),
            "delay": float(row.get("delay", base.get("delay", 0.0))),
            "mute": bool(row.get("mute", base.get("mute", False))),
            "solo": bool(row.get("solo", base.get("solo", False))),
        }
    if slot_controls:
        session_state["mt_track_controls"] = copy.deepcopy(slot_controls)
        try:
            from multitrack_mixer_state import prepare_multitrack_mixer_widgets

            prepare_multitrack_mixer_widgets(session_state)
        except ImportError:
            pass

    mixed = decode_audio_b64(payload.get("mixed_preview_b64"))
    if mixed:
        session_state["mixed_track_wav"] = mixed
        info["mixed_restored"] = True

    if payload.get("notes"):
        notes = str(payload.get("notes") or "")
        session_state["multitrack_history_loaded_notes"] = notes
        session_state["mt_history_save_notes"] = notes

    session_bpm = payload.get("session_bpm")
    if session_bpm is not None:
        session_state["multitrack_bpm"] = int(session_bpm)

    backing_settings = payload.get("backing_settings")
    if isinstance(backing_settings, dict) and backing_settings:
        apply_row = {**backing_settings}
        if session_bpm is not None:
            apply_row["bpm"] = int(session_bpm)
        try:
            from media_multitrack_catalog import apply_multitrack_backing_fields

            apply_multitrack_backing_fields(session_state, apply_row)
        except ImportError:
            vol = backing_settings.get("backing_volume")
            if vol is not None:
                session_state["mt_backing_volume"] = float(vol)

    analysis = payload.get("analysis_summary")
    if isinstance(analysis, dict) and analysis.get("coach_summary"):
        restored: dict[str, Any] = {
            "ok": True,
            "multitrack": True,
            "coach_summary": analysis.get("coach_summary"),
            "scores": analysis.get("scores") or {},
            "layer_scores": analysis.get("layer_scores") or [],
            "findings": analysis.get("findings") or [],
            "tips": analysis.get("tips") or [],
            "layers": analysis.get("layers") or [],
            "instrument": analysis.get("instrument") or "",
        }
        for key in (
            "practice_focus_snapshot",
            "practice_focus_at_analysis",
            "practice_focus_evaluation",
            "measured_comparisons",
        ):
            if key in analysis:
                restored[key] = analysis[key]
        session_state["last_analysis_result"] = restored

    return info


def history_row_summary(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    name = str(payload.get("project_name") or row.get("title") or "Multitrack project")
    tracks = payload.get("tracks") if isinstance(payload.get("tracks"), list) else []
    loaded = sum(1 for t in tracks if isinstance(t, dict) and t.get("has_audio"))
    song = str(payload.get("song_title") or "").strip()
    if song:
        return f"{name[:80]} · {song[:40]} · {loaded} layer(s)"
    return f"{name[:100]} · {loaded} layer(s)"

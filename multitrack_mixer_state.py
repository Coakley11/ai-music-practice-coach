"""Canonical per-slot multitrack mixer state shared by Step 2 and Step 3."""

from __future__ import annotations

import copy
from typing import Any

from multitrack_slots import MULTITRACK_SLOTS

DEFAULT_SLOT_CONTROL: dict[str, Any] = {
    "volume": 1.0,
    "mute": False,
    "solo": False,
    "delay": 0.0,
}

CONTROLS_KEY = "mt_track_controls"


def _controls_map(session_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = session_state.get(CONTROLS_KEY)
    if not isinstance(raw, dict):
        raw = {}
        session_state[CONTROLS_KEY] = raw
    return raw


def slot_has_audio(session_state: dict[str, Any], slot: str) -> bool:
    mt = session_state.get("mt_tracks")
    if not isinstance(mt, dict):
        return False
    audio = mt.get(slot)
    return bool(audio) and isinstance(audio, (bytes, bytearray))


def slots_with_audio(session_state: dict[str, Any]) -> list[str]:
    return [slot for slot in MULTITRACK_SLOTS if slot_has_audio(session_state, slot)]


def _normalize_control(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    return {
        "volume": float(src.get("volume", 1.0)),
        "delay": float(src.get("delay", 0.0)),
        "mute": bool(src.get("mute", False)),
        "solo": bool(src.get("solo", False)),
    }


def resolve_slot_control(
    session_state: dict[str, Any],
    slot: str,
    *,
    layer_name: str | None = None,
) -> dict[str, Any]:
    """Return canonical mixer control for a slot, migrating legacy layer-name keys."""
    controls = _controls_map(session_state)
    if isinstance(controls.get(slot), dict):
        return _normalize_control(controls[slot])
    name = str(layer_name or session_state.get(f"mt_name_{slot}") or slot).strip()
    if name and isinstance(controls.get(name), dict):
        normalized = _normalize_control(controls[name])
        controls[slot] = normalized
        return normalized
    normalized = _normalize_control(DEFAULT_SLOT_CONTROL)
    controls[slot] = normalized
    return normalized


def prepare_multitrack_mixer_widgets(
    session_state: dict[str, Any],
    *,
    slots: list[str] | None = None,
) -> None:
    """Seed widget keys from canonical slot controls before widgets render."""
    target_slots = slots if slots is not None else list(MULTITRACK_SLOTS)
    for slot in target_slots:
        if not slot_has_audio(session_state, slot):
            continue
        ctrl = resolve_slot_control(session_state, slot)
        session_state[f"mt_vol_{slot}"] = float(ctrl["volume"])
        session_state[f"mt_delay_{slot}"] = float(ctrl["delay"])
        session_state[f"mt_mute_{slot}"] = bool(ctrl["mute"])
        session_state[f"mt_solo_{slot}"] = bool(ctrl["solo"])


def _widget_volume(session_state: dict[str, Any], slot: str) -> float:
    for key in (f"mt_vol_{slot}", f"mt_vol_slider_{slot}"):
        val = session_state.get(key)
        if val is not None:
            return float(val)
    return 1.0


def _widget_delay(session_state: dict[str, Any], slot: str) -> float:
    for key in (f"mt_delay_{slot}", f"mt_delay_slider_{slot}"):
        val = session_state.get(key)
        if val is not None:
            return float(val)
    return 0.0


def commit_multitrack_mixer_widget(
    session_state: dict[str, Any],
    slot: str,
    *,
    layer_name: str | None = None,
) -> dict[str, Any]:
    """Write live widget keys back into canonical slot control."""
    if not slot_has_audio(session_state, slot):
        return resolve_slot_control(session_state, slot, layer_name=layer_name)
    ctrl = resolve_slot_control(session_state, slot, layer_name=layer_name)
    ctrl["volume"] = _widget_volume(session_state, slot)
    ctrl["delay"] = _widget_delay(session_state, slot)
    ctrl["mute"] = bool(session_state.get(f"mt_mute_{slot}", False))
    ctrl["solo"] = bool(session_state.get(f"mt_solo_{slot}", False))
    if layer_name:
        ctrl["layer_name"] = str(layer_name).strip()[:120]
    _controls_map(session_state)[slot] = ctrl
    return ctrl


def commit_all_multitrack_mixer_widgets(session_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Commit mixer widget values for every slot with audio."""
    out: dict[str, dict[str, Any]] = {}
    for slot in slots_with_audio(session_state):
        layer_name = str(session_state.get(f"mt_name_{slot}") or slot)
        out[slot] = commit_multitrack_mixer_widget(session_state, slot, layer_name=layer_name)
    session_state[CONTROLS_KEY] = copy.deepcopy(_controls_map(session_state))
    return out


def ensure_multitrack_track_controls(
    session_state: dict[str, Any],
    *,
    slots: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Ensure canonical slot controls exist for active layers."""
    controls = _controls_map(session_state)
    for slot in slots if slots is not None else slots_with_audio(session_state):
        resolve_slot_control(session_state, slot)
    return controls


def control_for_track_item(
    session_state: dict[str, Any],
    *,
    slot: str,
    layer_name: str,
) -> dict[str, Any]:
    """Resolve mixer control for Step 3 payloads using slot first, then layer name."""
    controls = _controls_map(session_state)
    if isinstance(controls.get(slot), dict):
        return _normalize_control(controls[slot])
    if isinstance(controls.get(layer_name), dict):
        return _normalize_control(controls[layer_name])
    return resolve_slot_control(session_state, slot, layer_name=layer_name)


def merge_mt_track_controls(
    snapshot_controls: Any,
    live_controls: Any,
) -> dict[str, dict[str, Any]]:
    """Merge page snapshot controls with live session controls; live wins for active slots."""
    merged: dict[str, dict[str, Any]] = {}
    snap = snapshot_controls if isinstance(snapshot_controls, dict) else {}
    live = live_controls if isinstance(live_controls, dict) else {}
    for slot in MULTITRACK_SLOTS:
        live_ctrl = live.get(slot) if isinstance(live.get(slot), dict) else None
        snap_ctrl = snap.get(slot) if isinstance(snap.get(slot), dict) else None
        if live_ctrl:
            merged[slot] = _normalize_control(live_ctrl)
        elif snap_ctrl:
            merged[slot] = _normalize_control(snap_ctrl)
    for key, val in live.items():
        if key in MULTITRACK_SLOTS:
            continue
        if isinstance(val, dict):
            merged[str(key)] = _normalize_control(val)
    for key, val in snap.items():
        if key in merged or key in MULTITRACK_SLOTS:
            continue
        if isinstance(val, dict):
            merged[str(key)] = _normalize_control(val)
    return merged

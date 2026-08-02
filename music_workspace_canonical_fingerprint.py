"""Stable workspace content fingerprint (excludes revision and volatile metadata)."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

_VOLATILE_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {
        "workspace_revision",
        "updated_at",
        "save_reason",
        "device_id",
        "schema_version",
        "workspace_id",
        "page",
    }
)

_VOLATILE_KEY_PREFIXES: tuple[str, ...] = (
    "_music_",
    "_suite_",
    "_ami_",
    "_cloud_",
    "_studio_",
    "_backing_",
    "_practice_",
    "_multitrack_",
    "_cpl_",
    "_genre_",
    "_picker_",
    "_analysis_",
    "_music_coach_",
)

_VOLATILE_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "workspace_revision",
        "picker_song_editor_open",
        "composer_preview_wav",
        "composer_preview_signature",
        "last_analysis_audio",
        "mixed_track_wav",
        "multitrack_backing_music_wav",
        "_last_backing_wav",
        "_last_backing_timeline",
    }
)

_PERSIST_CANONICAL_TOP_KEYS: frozenset[str] = frozenset(
    {
        "core",
        "active_song_state",
        "studio_nav_state",
        "practice_state",
        "backing_track_state",
        "practice_workspace_state",
        "music_workspace_state",
    }
)

_DROP_NESTED_KEYS: frozenset[str] = frozenset(
    {
        "last_write_reason",
        "backing_transport_status",
        "label",
    }
)

_GUITAR_CAPO_KEYS: frozenset[str] = frozenset(
    {
        "guitar_capo_enabled",
        "guitar_capo_sounding_key",
        "guitar_capo_shape_key",
        "guitar_capo_last_concert_key",
    }
)


def _is_volatile_key(key: str) -> bool:
    if key in _VOLATILE_EXACT_KEYS:
        return True
    if key.startswith("_"):
        return True
    for prefix in _VOLATILE_KEY_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


def _strip_volatile_mapping(data: dict[str, Any], *, drop_keys: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in data.items():
        if key in drop_keys or key in _DROP_NESTED_KEYS or _is_volatile_key(key):
            continue
        if isinstance(val, dict):
            out[key] = _strip_volatile_mapping(val, drop_keys=drop_keys)
        elif isinstance(val, list):
            out[key] = val
        else:
            out[key] = val
    return out


def _instrument_from_root(state: dict[str, Any]) -> str:
    for blob in (
        state.get("active_song_state"),
        state.get("core"),
        state,
    ):
        if isinstance(blob, dict):
            inst = str(blob.get("instrument") or "").strip()
            if inst:
                return inst
    return ""


def _guitar_capo_active(state: dict[str, Any]) -> bool:
    if _instrument_from_root(state) != "Guitar":
        return False
    try:
        from guitar_capo import CAPO_ENABLED_KEY

        return bool(state.get(CAPO_ENABLED_KEY))
    except ImportError:
        ass = state.get("active_song_state")
        if isinstance(ass, dict):
            return bool(ass.get("guitar_capo_enabled"))
        return False


def _normalize_source_aliases(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        return
    src = str(data.get("music_source") or data.get("source_type") or "").strip()
    if src:
        data["music_source"] = src
    data.pop("source_type", None)


def _normalize_canonical_tree(state: dict[str, Any], canonical: dict[str, Any]) -> None:
    capo_active = _guitar_capo_active(state)

    ass = canonical.get("active_song_state")
    if isinstance(ass, dict):
        if not capo_active:
            for key in _GUITAR_CAPO_KEYS:
                ass.pop(key, None)
        sel = ass.get("selected_song")
        if isinstance(sel, dict):
            sel.pop("label", None)
        _normalize_source_aliases(ass)

    bts = canonical.get("backing_track_state")
    if isinstance(bts, dict):
        bts.pop("backing_transport_status", None)
        bts.pop("last_write_reason", None)

    ps = canonical.get("practice_state")
    if isinstance(ps, dict):
        ps.pop("last_write_reason", None)

    nav = canonical.get("studio_nav_state")
    if isinstance(nav, dict):
        nav.pop("last_write_reason", None)

    pws = canonical.get("practice_workspace_state")
    if isinstance(pws, dict):
        pws.pop("updated_at", None)

    mws = canonical.get("music_workspace_state")
    if isinstance(mws, dict):
        active = mws.get("active_song")
        if isinstance(active, dict):
            _normalize_source_aliases(active)
        for filt_key in ("backing_filters", "practice_filters"):
            filt = mws.get(filt_key)
            if isinstance(filt, dict):
                filt.pop("backing_transport_status", None)
                filt.pop("last_write_reason", None)


def canonical_workspace_state_for_fingerprint(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    base: dict[str, Any] = {}
    for key in _PERSIST_CANONICAL_TOP_KEYS:
        if key not in state:
            continue
        val = state[key]
        if not isinstance(val, dict):
            continue
        if key == "music_workspace_state":
            base[key] = _strip_volatile_mapping(copy.deepcopy(val), drop_keys=_VOLATILE_ENVELOPE_KEYS)
        else:
            base[key] = _strip_volatile_mapping(copy.deepcopy(val), drop_keys=frozenset())
    _normalize_canonical_tree(state, base)
    return base


def workspace_canonical_content_fingerprint(state: dict[str, Any] | None) -> str:
    canonical = canonical_workspace_state_for_fingerprint(state)
    blob = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def diff_canonical_paths(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    *,
    prefix: str = "",
    limit: int = 24,
) -> list[str]:
    """Human-readable paths where canonical persist slices differ."""
    a = canonical_workspace_state_for_fingerprint(left if isinstance(left, dict) else {})
    b = canonical_workspace_state_for_fingerprint(right if isinstance(right, dict) else {})
    paths: list[str] = []

    def _walk(path: str, x: Any, y: Any) -> None:
        if len(paths) >= limit:
            return
        if type(x) != type(y):
            paths.append(path or "(root)")
            return
        if isinstance(x, dict):
            keys = sorted(set(x.keys()) | set(y.keys()))
            for key in keys:
                _walk(f"{path}.{key}" if path else key, x.get(key), y.get(key))
            return
        if x != y:
            paths.append(path or "(root)")

    _walk(prefix, a, b)
    return paths


__all__ = [
    "canonical_workspace_state_for_fingerprint",
    "diff_canonical_paths",
    "workspace_canonical_content_fingerprint",
]

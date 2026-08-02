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
        if key in drop_keys or _is_volatile_key(key):
            continue
        if isinstance(val, dict):
            out[key] = _strip_volatile_mapping(val, drop_keys=drop_keys)
        elif isinstance(val, list):
            out[key] = val
        else:
            out[key] = val
    return out


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

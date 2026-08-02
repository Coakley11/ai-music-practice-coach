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
    }
)

_VOLATILE_TOP_KEYS: frozenset[str] = frozenset(
    {
        "workspace_revision",
    }
)


def _strip_volatile_mapping(data: dict[str, Any], *, drop_keys: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in data.items():
        if key in drop_keys:
            continue
        if key.startswith("_music_") and key.endswith("_trace"):
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
    base = copy.deepcopy(state)
    for key in _VOLATILE_TOP_KEYS:
        base.pop(key, None)
    ws = base.get("music_workspace_state")
    if isinstance(ws, dict):
        base["music_workspace_state"] = _strip_volatile_mapping(ws, drop_keys=_VOLATILE_ENVELOPE_KEYS)
    return base


def workspace_canonical_content_fingerprint(state: dict[str, Any] | None) -> str:
    canonical = canonical_workspace_state_for_fingerprint(state)
    blob = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


__all__ = [
    "canonical_workspace_state_for_fingerprint",
    "workspace_canonical_content_fingerprint",
]

"""Block legacy/CWS projection from overwriting authoritatively restored workflow fields."""

from __future__ import annotations

import time
from typing import Any

WORKFLOW_RESTORE_GUARD_KEY = "_music_workflow_authoritative_restore_guard"

PROTECTED_WORKFLOW_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "_music_active_workflow",
        "_music_workflow_state_store",
        "display_key",
        "concert_key",
        "_pending_display_key",
        "improv_song_concert_sections",
        "improv_generated_sections",
        "improv_jam_session",
        "improv_style_key",
        "improv_jam_key",
        "ii_selected_chord",
        "II_SELECTED_CHORD",
        "ii_selected_section",
        "ii_selected_chord_index",
        "improv_active_mission",
        "improv_mission_recording_seal",
    }
)


def activate_workflow_restore_guard(session: dict[str, Any], *, source: str = "canonical_restore") -> None:
    session[WORKFLOW_RESTORE_GUARD_KEY] = {
        "authoritative_restore_guard_active": True,
        "canonical_restore_source": str(source or ""),
        "activated_at": time.time(),
        "fields_protected": sorted(PROTECTED_WORKFLOW_SESSION_KEYS),
        "legacy_overwrite_attempts_blocked": [],
    }


def deactivate_workflow_restore_guard(session: dict[str, Any]) -> None:
    session.pop(WORKFLOW_RESTORE_GUARD_KEY, None)


def restore_guard_active(session: dict[str, Any]) -> bool:
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    return isinstance(g, dict) and bool(g.get("authoritative_restore_guard_active"))


def block_legacy_overwrite(session: dict[str, Any], key: str, *, caller: str) -> bool:
    if not restore_guard_active(session):
        return False
    if key not in PROTECTED_WORKFLOW_SESSION_KEYS:
        return False
    g = session.get(WORKFLOW_RESTORE_GUARD_KEY)
    if isinstance(g, dict):
        bucket = g.setdefault("legacy_overwrite_attempts_blocked", [])
        if isinstance(bucket, list):
            bucket.append({"key": key, "caller": caller})
    return True


__all__ = [
    "PROTECTED_WORKFLOW_SESSION_KEYS",
    "WORKFLOW_RESTORE_GUARD_KEY",
    "activate_workflow_restore_guard",
    "block_legacy_overwrite",
    "deactivate_workflow_restore_guard",
    "restore_guard_active",
]

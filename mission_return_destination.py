"""Immutable exact return destination for Mission Backing → Creative."""

from __future__ import annotations

import copy
from typing import Any

MISSION_CANONICAL_RETURN_DESTINATION_KEY = "_music_mission_canonical_return_destination"


def build_mission_return_destination(
    alignment: dict[str, Any],
    *,
    handoff_mode: str,
    with_practice_lick: bool,
    request_seq: int | None = None,
) -> dict[str, Any]:
    dest = copy.deepcopy(alignment)
    dest["destination_page"] = "creative"
    dest["creative_tab"] = "Missions"
    dest["workflow_owner"] = "mission_jam"
    dest["handoff_mode"] = str(handoff_mode or ("practice_in_jam" if with_practice_lick else "mission_backing"))
    dest["with_practice_lick"] = bool(with_practice_lick)
    fp = str(dest.get("alignment_fingerprint") or "")
    seq = int(request_seq or 0)
    dest["return_token"] = f"{seq}:{fp}:{dest['handoff_mode']}:lick={int(with_practice_lick)}"
    return dest


def seal_mission_return_destination(session: dict[str, Any], destination: dict[str, Any]) -> None:
    if isinstance(destination, dict) and str(destination.get("mission_id") or "").strip():
        session[MISSION_CANONICAL_RETURN_DESTINATION_KEY] = copy.deepcopy(destination)


def peek_mission_return_destination(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY)
    return copy.deepcopy(raw) if isinstance(raw, dict) else None


def apply_sealed_mission_return_destination(session: dict[str, Any], dest: dict[str, Any] | None = None) -> bool:
    """Restore exact mission identity from sealed return destination (Backing → Missions)."""
    sealed = dest if isinstance(dest, dict) else peek_mission_return_destination(session)
    if not isinstance(sealed, dict) or not str(sealed.get("mission_id") or "").strip():
        return False
    try:
        from mission_backing_alignment import apply_pending_mission_backing_alignment

        apply_pending_mission_backing_alignment(session, sealed)
    except ImportError:
        pass
    try:
        from music_workflow_pending_mission_return import _apply_return_destination_session_fields

        _apply_return_destination_session_fields(session, sealed)
    except ImportError:
        mission_id = str(sealed.get("mission_id") or "").strip()
        if mission_id:
            session["improv_active_mission"] = mission_id
            session["improv_mission_pick"] = mission_id
    try:
        from mission_practice_context import refresh_mission_practice_context

        refresh_mission_practice_context(session)
    except ImportError:
        pass
    return True


def seal_mission_return_destination_from_handoff(session: dict[str, Any], pending: dict[str, Any]) -> None:
    align = pending.get("mission_alignment")
    if not isinstance(align, dict):
        return
    dest = build_mission_return_destination(
        align,
        handoff_mode=str(pending.get("handoff_mode") or "mission_backing"),
        with_practice_lick=bool(pending.get("with_practice_lick")),
        request_seq=int(pending.get("request_seq") or 0),
    )
    seal_mission_return_destination(session, dest)


__all__ = [
    "MISSION_CANONICAL_RETURN_DESTINATION_KEY",
    "apply_sealed_mission_return_destination",
    "build_mission_return_destination",
    "peek_mission_return_destination",
    "seal_mission_return_destination",
    "seal_mission_return_destination_from_handoff",
]

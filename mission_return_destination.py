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
    "build_mission_return_destination",
    "peek_mission_return_destination",
    "seal_mission_return_destination",
    "seal_mission_return_destination_from_handoff",
]

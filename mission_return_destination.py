"""Immutable exact return destination for Mission Backing → Creative."""

from __future__ import annotations

import copy
from typing import Any

MISSION_CANONICAL_RETURN_DESTINATION_KEY = "_music_mission_canonical_return_destination"
MISSION_RETURN_DESTINATION_BLOB_KEY = "mission_return_destination"


def _backing_context_blob(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from backing_context import BACKING_CONTEXT_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
    except ImportError:
        raw = session.get("backing_context")
    return raw if isinstance(raw, dict) else None


def _valid_dest(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict) and str(raw.get("mission_id") or "").strip():
        return copy.deepcopy(raw)
    return None


def recover_mission_return_destination_from_backing_session(
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Recover the sealed Mission launch identity from the Mission Backing session.

    Does not mint a new Mission. Uses dest stamped on ``backing_context``, then
    the sealed ``creative_return_route`` + ctx ``mission_id`` from that same session.
    """
    blob = _backing_context_blob(session)
    if blob is None:
        return None
    dest = _valid_dest(blob.get(MISSION_RETURN_DESTINATION_BLOB_KEY))
    if dest is not None:
        return dest
    if str(blob.get("source") or "").strip() != "mission":
        return None
    route = blob.get("creative_return_route")
    route = route if isinstance(route, dict) else {}
    mission_id = str(route.get("mission_id") or blob.get("mission_id") or "").strip()
    if not mission_id:
        return None
    recovered = {
        "destination_page": "creative",
        "creative_tab": "Missions",
        "workflow_owner": "mission_jam",
        "handoff_mode": str(route.get("handoff_mode") or "mission_backing"),
        "with_practice_lick": bool(route.get("with_practice_lick")),
        "mission_id": mission_id,
        "section_label": str(route.get("mission_section") or blob.get("section") or "").strip(),
        "chord_symbol": str(route.get("mission_chord") or "").strip(),
        "song_pick_key": str(route.get("song_pick_key") or blob.get("bound_pick_key") or "").strip(),
        "concert_key": str(blob.get("concert_key") or blob.get("key") or "").strip(),
        "display_key": str(blob.get("display_key") or blob.get("concert_key") or blob.get("key") or "").strip(),
        "return_route": "creative",
    }
    chord = str(recovered.get("chord_symbol") or "").strip()
    section = str(recovered.get("section_label") or "").strip()
    if section or chord:
        recovered["chord_display_label"] = f"{section} · {chord}".strip(" ·")
    return recovered


def stamp_mission_return_destination_on_backing_context(
    session: dict[str, Any],
    destination: dict[str, Any] | None = None,
) -> None:
    dest = _valid_dest(destination) or _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    blob = _backing_context_blob(session)
    if dest is None or blob is None:
        return
    blob[MISSION_RETURN_DESTINATION_BLOB_KEY] = copy.deepcopy(dest)


def rehydrate_mission_return_destination_from_backing_context(session: dict[str, Any]) -> dict[str, Any] | None:
    """Restore the session dest key from the Mission Backing session after Upload/refresh."""
    existing = _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    if existing is not None:
        stamp_mission_return_destination_on_backing_context(session, existing)
        return existing
    recovered = recover_mission_return_destination_from_backing_session(session)
    if recovered is None:
        return None
    session[MISSION_CANONICAL_RETURN_DESTINATION_KEY] = copy.deepcopy(recovered)
    stamp_mission_return_destination_on_backing_context(session, recovered)
    return copy.deepcopy(recovered)


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
    dest = _valid_dest(destination)
    if dest is None:
        return
    session[MISSION_CANONICAL_RETURN_DESTINATION_KEY] = dest
    stamp_mission_return_destination_on_backing_context(session, dest)


def peek_mission_return_destination(session: dict[str, Any]) -> dict[str, Any] | None:
    existing = _valid_dest(session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY))
    if existing is not None:
        return existing
    return rehydrate_mission_return_destination_from_backing_context(session)


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
    "MISSION_RETURN_DESTINATION_BLOB_KEY",
    "apply_sealed_mission_return_destination",
    "build_mission_return_destination",
    "peek_mission_return_destination",
    "recover_mission_return_destination_from_backing_session",
    "rehydrate_mission_return_destination_from_backing_context",
    "seal_mission_return_destination",
    "seal_mission_return_destination_from_handoff",
    "stamp_mission_return_destination_on_backing_context",
]

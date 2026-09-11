"""Legacy improv_jam_session is a derived projection of the active jam workflow blob."""

from __future__ import annotations

import copy
from typing import Any

IMPROV_JAM_SESSION_MUTATION_TRACE_KEY = "_improv_jam_session_mutation_trace"
_GENERATED_OWNER = "jam_session_generator"


def _progression_head(section_map: dict[str, list[str]] | None, n: int = 6) -> list[str]:
    if not isinstance(section_map, dict):
        return []
    flat: list[str] = []
    for chords in section_map.values():
        if isinstance(chords, list):
            flat.extend(str(c).strip() for c in chords if str(c).strip())
    return flat[:n]


def jam_session_fingerprint(jam: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(jam, dict):
        return {"key": "", "head": []}
    sections = jam.get("sections") if isinstance(jam.get("sections"), dict) else {}
    return {
        "key": str(jam.get("key") or "").strip(),
        "head": _progression_head(sections),
        "id": str(jam.get("id") or "")[:36],
    }


def _active_jam_blob(session: dict[str, Any]):
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == _GENERATED_OWNER:
            return ptr, get_workflow_blob(session, _GENERATED_OWNER, str(ptr.workflow_session_id or ""))
    except ImportError:
        pass
    return None, None


def build_improv_jam_session_from_blob(blob: Any, *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build sealed legacy jam dict from authoritative workflow blob."""
    base = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    k = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "C").strip() or "C"
    mode = str(getattr(getattr(blob, "keys", None), "practice_mode", "") or "major").strip() or "major"
    if mode == "minor" and not k.endswith("m"):
        key_center = f"{k}m"
    else:
        key_center = k
    sections = copy.deepcopy(getattr(blob, "section_map", None) or {})
    if not isinstance(sections, dict):
        sections = {}
    sid = str(getattr(blob, "generated_session_id", "") or base.get("id") or "").strip()
    if sid:
        base["id"] = sid
    base["style"] = str(getattr(blob, "style", "") or base.get("style") or "Jazz Swing").strip() or "Jazz Swing"
    base["ensemble"] = str(base.get("ensemble") or "Jazz trio")
    base["bpm"] = int(getattr(blob, "tempo_bpm", None) or base.get("bpm") or 110)
    base["mood"] = str(getattr(blob, "mood", "") or base.get("mood") or "Mellow")
    base["atmosphere"] = str(base.get("atmosphere") or base.get("mood") or "Mellow")
    try:
        from music_workflow_generated_session import seal_jam_session_musical_context

        return seal_jam_session_musical_context(
            base,
            key_center=key_center,
            sections=sections if sections else None,
        )
    except ImportError:
        base["key"] = key_center
        base["sections"] = sections
        return base


def authoritative_jam_section_map(session: dict[str, Any]) -> dict[str, list[str]]:
    """Section map for Creative sync — blob wins over stale improv_jam_session."""
    _ptr, blob = _active_jam_blob(session)
    if blob is not None and isinstance(getattr(blob, "section_map", None), dict) and blob.section_map:
        return copy.deepcopy(blob.section_map)
    jam = session.get("improv_jam_session")
    if isinstance(jam, dict):
        raw = jam.get("sections")
        if isinstance(raw, dict) and raw:
            return {
                str(name): [str(c) for c in chords if str(c).strip()]
                for name, chords in raw.items()
                if isinstance(chords, list)
            }
    return {}


def sync_improv_jam_session_from_active_blob(session: dict[str, Any], *, writer: str, phase: str = "") -> bool:
    """Re-project legacy jam from active blob when jam_session_generator owns workflow."""
    _ptr, blob = _active_jam_blob(session)
    if blob is None:
        return False
    existing = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else {}
    jam = build_improv_jam_session_from_blob(blob, existing=existing)
    set_improv_jam_session(session, jam, writer=writer, phase=phase or "sync_from_blob")
    return True


def set_improv_jam_session(
    session: dict[str, Any],
    jam: dict[str, Any],
    *,
    writer: str,
    phase: str = "",
) -> None:
    """Assign improv_jam_session with mutation trace; block stale regression vs active blob."""
    old = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else None
    new_fp = jam_session_fingerprint(jam if isinstance(jam, dict) else None)
    old_fp = jam_session_fingerprint(old)
    blocked = False
    _ptr, blob = _active_jam_blob(session)
    if blob is not None and isinstance(jam, dict):
        auth = build_improv_jam_session_from_blob(blob, existing=jam)
        auth_fp = jam_session_fingerprint(auth)
        if auth_fp["head"] and new_fp["head"] and auth_fp["head"] != new_fp["head"]:
            jam = auth
            new_fp = auth_fp
            writer = f"{writer}:coerced_from_blob"
        elif auth_fp["key"] and new_fp["key"] and auth_fp["key"] != new_fp["key"] and auth_fp["head"]:
            jam = auth
            new_fp = auth_fp
            writer = f"{writer}:coerced_from_blob"
    try:
        from music_workflow_restore_guard import block_legacy_overwrite

        if block_legacy_overwrite(
            session,
            "improv_jam_session",
            caller=writer,
            value=jam,
            authoritative_projection=writer.endswith("_from_blob") or "workflow_restore" in writer,
        ):
            blocked = True
    except ImportError:
        pass
    if blocked:
        return
    bucket = session.get(IMPROV_JAM_SESSION_MUTATION_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append(
        {
            "writer": writer,
            "phase": phase,
            "old": old_fp,
            "new": new_fp,
            "blocked": False,
        }
    )
    session[IMPROV_JAM_SESSION_MUTATION_TRACE_KEY] = bucket[-48:]
    session["improv_jam_session"] = jam


__all__ = [
    "IMPROV_JAM_SESSION_MUTATION_TRACE_KEY",
    "authoritative_jam_section_map",
    "build_improv_jam_session_from_blob",
    "jam_session_fingerprint",
    "set_improv_jam_session",
    "sync_improv_jam_session_from_active_blob",
]

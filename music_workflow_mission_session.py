"""Deterministic mission workflow session identity (Commit 6)."""

from __future__ import annotations

from typing import Any

from music_workflow_song_practice import song_practice_storage_id


def mission_blob_session_id(session: dict[str, Any]) -> str:
    """mission|{source_type}|{stable_song_id}"""
    src, sid = song_practice_storage_id(session)
    return f"mission|{src}|{sid}"


def mission_blob_session_id_for_song(source_type: str, song_id: str) -> str:
    st = str(source_type or "catalog").strip() or "catalog"
    sid = str(song_id or "").strip() or "song"
    return f"mission|{st}|{sid}"


def legacy_mission_session_aliases(canonical_session_id: str) -> tuple[str, ...]:
    """Older mission|pick and mission|custom|id forms for the same song."""
    if not canonical_session_id.startswith("mission|"):
        return ()
    parts = canonical_session_id.split("|")
    if len(parts) == 3:
        _m, src, sid = parts[0], parts[1], parts[2]
        if src == "catalog":
            return (f"mission|{sid}",)
        if src == "custom":
            return (f"mission|custom|{sid}", f"custom|{sid}")
    if len(parts) == 2:
        return ()
    return ()


def normalize_requested_mission_session_id(session: dict[str, Any], requested: str) -> str:
    canonical = mission_blob_session_id(session)
    req = str(requested or "").strip()
    if not req or req == canonical:
        return canonical
    aliases = legacy_mission_session_aliases(canonical)
    if req in aliases:
        return canonical
    if req.startswith("mission|") and req.count("|") == 1:
        tail = req.split("|", 1)[1]
        src, sid = song_practice_storage_id(session)
        if tail == sid:
            return canonical
    return req


__all__ = [
    "legacy_mission_session_aliases",
    "mission_blob_session_id",
    "mission_blob_session_id_for_song",
    "normalize_requested_mission_session_id",
]

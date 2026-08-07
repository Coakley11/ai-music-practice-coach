"""Per-song practice key identity — separate from generated workflow keys (Commit 4)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_state_store import KeyAuthority, WorkflowStateBlob, get_workflow_blob, save_workflow_blob


def song_practice_storage_id(session: dict[str, Any]) -> tuple[str, str]:
    """Stable song identity: (source_type, song_id)."""
    pick = str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    try:
        from studio_page_state import resolve_improv_song_source

        if str(resolve_improv_song_source(session) or "") == "Custom progression":
            custom = str(session.get("custom_progression_id") or session.get("cpl_active_id") or "custom").strip()
            return "custom", custom or "custom"
    except ImportError:
        pass
    if not pick:
        pick = "song"
    return "catalog", pick


def song_based_blob_session_id(session: dict[str, Any]) -> str:
    src, sid = song_practice_storage_id(session)
    return sid if src == "catalog" else f"custom|{sid}"


def mission_blob_session_id(session: dict[str, Any]) -> str:
    from music_workflow_mission_session import mission_blob_session_id as _canonical_mission_sid

    return _canonical_mission_sid(session)


def resolve_song_practice_key_token(session: dict[str, Any]) -> str:
    """Authoritative parent practice key from song_based blob (not mission/session projection)."""
    sid = song_based_blob_session_id(session)
    blob = get_workflow_blob(session, "song_based_improvisation", sid)
    if blob is None:
        return ""
    tonic = str(blob.keys.practice_tonic or "C").strip() or "C"
    mode = str(blob.keys.practice_mode or "major").strip().lower()
    if mode == "minor":
        return f"{tonic}m" if not tonic.lower().endswith("m") else tonic
    return tonic


def song_practice_blob(session: dict[str, Any]) -> WorkflowStateBlob | None:
    sid = song_based_blob_session_id(session)
    return get_workflow_blob(session, "song_based_improvisation", sid)


def mirror_mission_keys_from_song_blob(session: dict[str, Any]) -> bool:
    """Before mission chord/example mutations — mission blob must not own practice key."""
    song = song_practice_blob(session)
    if song is None:
        return False
    mirror_song_practice_key_to_mission_blob(session, song)
    return True


def sync_session_practice_key_from_song_blob(session: dict[str, Any], *, source: str = "song_blob_sync") -> str:
    """Project display/concert key + concert sections from song_based blob only."""
    song = song_practice_blob(session)
    if song is None:
        return ""
    try:
        from music_workflow_legacy_projection import _practice_key_token

        token = _practice_key_token(song)
    except ImportError:
        token = resolve_song_practice_key_token(session)
    if song.section_map:
        session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
    try:
        from music_workflow_legacy_projection import _project_session_field

        _project_session_field(session, "display_key", token)
        _project_session_field(session, "concert_key", token)
        session["_pending_display_key"] = token
    except ImportError:
        session["display_key"] = token
        session["concert_key"] = token
        session["_pending_display_key"] = token
    session["_music_practice_key_sync_source"] = source
    return token


def mirror_song_practice_key_to_mission_blob(session: dict[str, Any], song_blob: WorkflowStateBlob) -> None:
    """Keep mission_jam blob practice key aligned with the active song blob."""
    sid = mission_blob_session_id(session)
    mission = get_workflow_blob(session, "mission_jam", sid)
    if mission is None:
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id=sid,
            song_id=song_blob.song_id,
            song_title=song_blob.song_title,
            source_type=song_blob.source_type,
        )
    mission.keys = KeyAuthority(
        original_tonic=song_blob.keys.original_tonic,
        original_mode=song_blob.keys.original_mode,
        practice_tonic=song_blob.keys.practice_tonic,
        practice_mode=song_blob.keys.practice_mode,
        written_tonic=song_blob.keys.written_tonic,
        written_mode=song_blob.keys.written_mode,
        instrument=song_blob.keys.instrument,
        key_owner="mission_jam",
    )
    if song_blob.section_map:
        mission.section_map = copy.deepcopy(song_blob.section_map)
    save_workflow_blob(session, mission, source="mirror_song_practice_key")


def ensure_missions_parent_practice_key_hydrated(session: dict[str, Any]) -> str:
    """Same-run Missions parent key from song blob — never re-transpose from catalog on tab entry."""
    token = resolve_song_practice_key_token(session)
    if not token:
        return ""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    blob = song_practice_blob(session)
    if live != token:
        sync_session_practice_key_from_song_blob(session, source="missions_tab_parent_key")
    elif blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
        session["improv_song_concert_sections"] = copy.deepcopy(blob.section_map)
    return token


__all__ = [
    "mirror_mission_keys_from_song_blob",
    "mirror_song_practice_key_to_mission_blob",
    "mission_blob_session_id",
    "resolve_song_practice_key_token",
    "song_based_blob_session_id",
    "song_practice_blob",
    "song_practice_storage_id",
    "sync_session_practice_key_from_song_blob",
    "ensure_missions_parent_practice_key_hydrated",
]

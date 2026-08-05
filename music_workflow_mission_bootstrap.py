"""Mission blob bootstrap from song practice state — never from Style Jam / Generator keys."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_compatibility import _tonic_mode_from_token
from music_workflow_song_practice import (
    mission_blob_session_id,
    song_based_blob_session_id,
    song_practice_storage_id,
)
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    record_compat_fallback,
    save_workflow_blob,
)

WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY = "_music_workflow_mission_bootstrap_diag"

VIOLATION_MISSION_BOOTSTRAP_FROM_NONSONG_KEY = "MISSION_BOOTSTRAP_FROM_NONSONG_KEY"
VIOLATION_MISSION_SONG_IDENTITY_MISMATCH = "MISSION_SONG_IDENTITY_MISMATCH"


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.setdefault(WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY, {})
    if not isinstance(d, dict):
        d = {}
        session[WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY] = d
    return d


def ensure_mission_blob_from_song(session: dict[str, Any], mission_session_id: str) -> WorkflowStateBlob | None:
    """
    Bootstrap precedence:
    1. existing valid mission blob (caller may skip)
    2. active song-practice blob for this song
    3. song sections from catalog/custom at saved song key
    4. original/default catalog song key
    5. fail closed (None)
    """
    expected_sid = mission_blob_session_id(session)
    trace = {
        "expected_session_id": expected_sid,
        "requested_session_id": mission_session_id,
        "song_identity": song_practice_storage_id(session),
    }
    if mission_session_id and mission_session_id != expected_sid:
        record_compat_fallback(session, VIOLATION_MISSION_SONG_IDENTITY_MISMATCH, mission_session_id)
        mission_session_id = expected_sid
    trace["mission_session_id"] = mission_session_id

    existing = get_workflow_blob(session, "mission_jam", mission_session_id)
    if existing is not None and str(existing.keys.practice_mode or "").strip():
        trace["source"] = "existing_mission_blob"
        _diag(session).update(trace)
        return existing

    src_type, song_id = song_practice_storage_id(session)
    if mission_session_id.startswith("mission|"):
        sid_song = mission_session_id.split("|", 1)[1].strip()
        if sid_song and sid_song not in {"", "song"}:
            song_id = sid_song
            src_type = "catalog"
    song_sid = song_id if src_type == "catalog" else f"custom|{song_id}"
    song_blob = get_workflow_blob(session, "song_based_improvisation", song_sid)
    if song_blob is not None and str(song_blob.keys.practice_mode or "").strip():
        trace["source"] = "song_practice_blob"
        mission = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id=mission_session_id,
            keys=copy.deepcopy(song_blob.keys),
            section_map=copy.deepcopy(song_blob.section_map),
            song_id=song_blob.song_id or song_id,
            song_title=song_blob.song_title,
            source_type=song_blob.source_type or src_type,
        )
        mission.keys.key_owner = "mission_jam"
        _apply_mission_selection_from_legacy_mission_fields(session, mission)
        save_workflow_blob(session, mission, source="mission_bootstrap_song_blob")
        _diag(session).update(trace)
        return mission

    sections: dict[str, list[str]] = {}
    practice_tonic, practice_mode = "", ""
    original_tonic, original_mode = "", ""
    title = str(session.get("song") or "").strip()

    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        synced = sync_song_improv_sections_to_practice_key(session)
        if isinstance(synced, dict) and synced:
            sections = {str(k): list(v) for k, v in synced.items() if isinstance(v, list)}
    except ImportError:
        pass

    if not sections and isinstance(session.get("improv_song_concert_sections"), dict):
        sec = session.get("improv_song_concert_sections")
        sections = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}

    try:
        from backing_context import _current_pick_key
        from songs.music_source import resolve_catalog_song_for_pick

        pick = _current_pick_key(session)
        if song_id and song_id != "song":
            pick = song_id
        selected, ok = resolve_catalog_song_for_pick(session, pick)
        if ok and isinstance(selected, dict):
            orig_key = str(selected.get("key") or selected.get("original_key") or "").strip()
            if orig_key:
                original_tonic, original_mode = _tonic_mode_from_token(orig_key)
            if not title:
                title = str(selected.get("title") or selected.get("name") or "").strip()
            if not sections:
                raw_sec = selected.get("sections")
                if isinstance(raw_sec, dict):
                    sections = {
                        str(n): [str(c) for c in ch if str(c).strip()]
                        for n, ch in raw_sec.items()
                        if isinstance(ch, list)
                    }
            if not practice_tonic:
                practice_tonic, practice_mode = original_tonic, original_mode
    except ImportError:
        pass

    if not practice_tonic:
        record_compat_fallback(session, VIOLATION_MISSION_BOOTSTRAP_FROM_NONSONG_KEY, "no_song_key")
        trace["source"] = "fail_closed"
        _diag(session).update(trace)
        return None

    mission = WorkflowStateBlob(
        workflow_owner="mission_jam",
        workflow_session_id=mission_session_id,
        keys=KeyAuthority(
            original_tonic=original_tonic or practice_tonic,
            original_mode=original_mode or practice_mode,
            practice_tonic=practice_tonic,
            practice_mode=practice_mode,
            key_owner="mission_jam",
            instrument=str(session.get("instrument") or ""),
        ),
        section_map=copy.deepcopy(sections) if sections else {},
        song_id=song_id,
        song_title=title,
        source_type=src_type,
    )
    _apply_mission_selection_from_legacy_mission_fields(session, mission)
    trace["source"] = "catalog_song_practice"
    save_workflow_blob(session, mission, source="mission_bootstrap_catalog")
    _diag(session).update(trace)
    return mission


def _apply_mission_selection_from_legacy_mission_fields(session: dict[str, Any], mission: WorkflowStateBlob) -> None:
    chord = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "").strip()
    section = str(session.get("ii_selected_section") or session.get("II_SELECTED_SECTION") or "").strip()
    if chord:
        mission.selected_chord_symbol = chord
    if section:
        mission.selected_section = section
    mission.selected_chord_index = int(session.get("ii_selected_chord_index") or session.get("II_SELECTED_CHORD_INDEX") or 0)
    mt = str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "").strip()
    if mt:
        mission.mission_type = mt


__all__ = [
    "VIOLATION_MISSION_BOOTSTRAP_FROM_NONSONG_KEY",
    "VIOLATION_MISSION_SONG_IDENTITY_MISMATCH",
    "WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY",
    "ensure_mission_blob_from_song",
]

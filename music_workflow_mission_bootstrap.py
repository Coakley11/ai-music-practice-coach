"""Mission blob bootstrap from song practice state — fail closed, never default C major (Commit 6)."""

from __future__ import annotations

import copy
from typing import Any

from music_workflow_custom_key_derivation import (
    derive_key_from_progression_sections,
    load_persisted_song_practice_keys,
)
from music_workflow_mission_session import (
    mission_blob_session_id,
    normalize_requested_mission_session_id,
)
from music_workflow_song_practice import song_based_blob_session_id, song_practice_storage_id
from music_workflow_state_store import (
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    record_compat_fallback,
    save_workflow_blob,
)

WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY = "_music_workflow_mission_bootstrap_diag"

VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED = "MISSION_BOOTSTRAP_KEY_UNRESOLVED"
VIOLATION_MISSION_BOOTSTRAP_DEFAULT_KEY_FORBIDDEN = "MISSION_BOOTSTRAP_DEFAULT_KEY_FORBIDDEN"
VIOLATION_MISSION_BOOTSTRAP_SOURCE_ID_MISMATCH = "MISSION_BOOTSTRAP_SOURCE_ID_MISMATCH"
VIOLATION_MISSION_BOOTSTRAP_CUSTOM_KEY_AMBIGUOUS = "MISSION_BOOTSTRAP_CUSTOM_KEY_AMBIGUOUS"
VIOLATION_MISSION_BOOTSTRAP_FROM_GENERATED_OWNER = "MISSION_BOOTSTRAP_FROM_GENERATED_OWNER"
VIOLATION_MISSION_BOOTSTRAP_FROM_NONSONG_KEY = "MISSION_BOOTSTRAP_FROM_NONSONG_KEY"


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.setdefault(WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY, {})
    if not isinstance(d, dict):
        d = {}
        session[WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY] = d
    return d


def _fail(session: dict[str, Any], trace: dict[str, Any], code: str) -> None:
    record_compat_fallback(session, code, trace.get("mission_session_id", ""))
    trace["source"] = "fail_closed"
    trace["fail_code"] = code
    _diag(session).update(trace)


def ensure_mission_blob_from_song(session: dict[str, Any], mission_session_id: str) -> WorkflowStateBlob | None:
    expected_sid = mission_blob_session_id(session)
    mission_session_id = normalize_requested_mission_session_id(session, mission_session_id)
    trace = {
        "expected_session_id": expected_sid,
        "requested_session_id": mission_session_id,
        "song_identity": song_practice_storage_id(session),
        "mission_bootstrap_song_identity": song_practice_storage_id(session),
    }
    if mission_session_id != expected_sid:
        record_compat_fallback(session, VIOLATION_MISSION_BOOTSTRAP_SOURCE_ID_MISMATCH, mission_session_id)
        mission_session_id = expected_sid
    trace["mission_session_id"] = mission_session_id

    existing = get_workflow_blob(session, "mission_jam", mission_session_id)
    if existing is not None and str(existing.keys.practice_mode or "").strip():
        trace["source"] = "existing_mission_blob"
        _diag(session).update(trace)
        return existing

    src_type, song_id = song_practice_storage_id(session)
    song_sid = song_based_blob_session_id(session)
    song_blob = get_workflow_blob(session, "song_based_improvisation", song_sid)
    if song_blob is not None and str(song_blob.keys.practice_mode or "").strip():
        trace["source"] = "song_practice_blob"
        mission = _mission_from_song_blob(song_blob, mission_session_id, src_type, song_id)
        _apply_mission_selection_from_legacy_mission_fields(session, mission)
        save_workflow_blob(session, mission, source="mission_bootstrap_song_blob")
        _diag(session).update(trace)
        return mission

    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner in {"style_jam", "jam_session_generator"}:
            _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_FROM_GENERATED_OWNER)
            return None
    except ImportError:
        pass

    persisted = load_persisted_song_practice_keys(session, src_type, song_id)
    sections: dict[str, list[str]] = {}
    practice_tonic, practice_mode = "", ""
    original_tonic, original_mode = "", ""
    title = ""

    if src_type == "catalog":
        try:
            from backing_context import _current_pick_key
            from songs.music_source import resolve_catalog_song_for_pick

            pick = song_id if song_id not in {"", "song"} else _current_pick_key(session)
            selected, ok = resolve_catalog_song_for_pick(session, pick)
            if not ok or not isinstance(selected, dict):
                _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED)
                return None
            orig_key = str(selected.get("key") or selected.get("original_key") or "").strip()
            if not orig_key:
                _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED)
                return None
            from music_workflow_compatibility import _tonic_mode_from_token

            original_tonic, original_mode = _tonic_mode_from_token(orig_key)
            title = str(selected.get("title") or selected.get("name") or "").strip()
            raw_sec = selected.get("sections")
            if isinstance(raw_sec, dict):
                sections = {
                    str(n): [str(c) for c in ch if str(c).strip()]
                    for n, ch in raw_sec.items()
                    if isinstance(ch, list)
                }
            if persisted:
                practice_tonic, practice_mode = persisted
            else:
                practice_tonic, practice_mode = original_tonic, original_mode
        except ImportError:
            _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED)
            return None
    else:
        if isinstance(session.get("improv_song_concert_sections"), dict):
            sec = session.get("improv_song_concert_sections")
            sections = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}
        if persisted:
            practice_tonic, practice_mode = persisted
        elif sections:
            derived = derive_key_from_progression_sections(sections)
            if derived is None:
                session["_mission_bootstrap_key_notice"] = (
                    "Set a practice key for this custom song before opening Missions."
                )
                _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_CUSTOM_KEY_AMBIGUOUS)
                return None
            practice_tonic, practice_mode = derived
        else:
            _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED)
            return None
        title = str(session.get("song") or song_id).strip()

    if not practice_tonic or not practice_mode:
        _fail(session, trace, VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED)
        return None
    if practice_tonic == "C" and practice_mode == "major" and not persisted and src_type == "catalog":
        record_compat_fallback(session, VIOLATION_MISSION_BOOTSTRAP_DEFAULT_KEY_FORBIDDEN, song_id)

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
    trace["source"] = "catalog_or_custom_song_state"
    save_workflow_blob(session, mission, source="mission_bootstrap")
    _diag(session).update(trace)
    return mission


def _mission_from_song_blob(
    song_blob: WorkflowStateBlob,
    mission_session_id: str,
    src_type: str,
    song_id: str,
) -> WorkflowStateBlob:
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
    "VIOLATION_MISSION_BOOTSTRAP_CUSTOM_KEY_AMBIGUOUS",
    "VIOLATION_MISSION_BOOTSTRAP_DEFAULT_KEY_FORBIDDEN",
    "VIOLATION_MISSION_BOOTSTRAP_FROM_GENERATED_OWNER",
    "VIOLATION_MISSION_BOOTSTRAP_KEY_UNRESOLVED",
    "WORKFLOW_MISSION_BOOTSTRAP_DIAG_KEY",
    "ensure_mission_blob_from_song",
]

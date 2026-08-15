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


def ensure_song_practice_blob_for_active_song(
    session: dict[str, Any],
    *,
    practice_key: str,
    original_key: str = "",
) -> str:
    """Bind the active catalog song blob to a complete Practice Key on the same rerun."""
    from music_theory import key_center_token, split_key_center

    token = str(practice_key or "").strip()
    if not token:
        return ""
    pt, pm = split_key_center(token)
    token = key_center_token(pt, pm)
    orig = str(original_key or "").strip()
    ot, om = split_key_center(orig) if orig else (pt, pm)
    sid = song_based_blob_session_id(session)
    src, song_id = song_practice_storage_id(session)
    blob = get_workflow_blob(session, "song_based_improvisation", sid)
    if blob is None:
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=sid,
            source_type=src,
            song_id=song_id,
            keys=KeyAuthority(
                original_tonic=ot,
                original_mode=om,
                practice_tonic=pt,
                practice_mode=pm,
                key_owner="song_based_improvisation",
            ),
        )
    else:
        blob.keys = KeyAuthority(
            original_tonic=ot or blob.keys.original_tonic,
            original_mode=om or blob.keys.original_mode,
            practice_tonic=pt,
            practice_mode=pm,
            written_tonic=blob.keys.written_tonic,
            written_mode=blob.keys.written_mode,
            instrument=blob.keys.instrument,
            key_owner="song_based_improvisation",
        )
        blob.song_id = song_id or blob.song_id
        blob.source_type = src or blob.source_type
    save_workflow_blob(session, blob, source="ensure_song_practice_blob_for_active_song")
    return token


def song_practice_blob(session: dict[str, Any]) -> WorkflowStateBlob | None:
    sid = song_based_blob_session_id(session)
    return get_workflow_blob(session, "song_based_improvisation", sid)


def seed_song_practice_blob_from_live_practice_key(session: dict[str, Any]) -> str:
    """When song/mission owns Practice Key but the song blob is missing, seed from live identity.

    Live ``display_key`` (full tonic + mode) is the owner — not catalog original C and not
    leftover jam / mission_jam blob keys. Never overwrite an existing song blob.
    """
    existing = song_practice_blob(session)
    if existing is not None:
        return resolve_song_practice_key_token(session)
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return ""
    try:
        from music_workflow_compatibility import _tonic_mode_from_token
    except ImportError:
        from music_theory import split_key_center

        def _tonic_mode_from_token(key: str) -> tuple[str, str]:
            return split_key_center(str(key or "C"))

    pt, pm = _tonic_mode_from_token(live)
    if pm not in {"major", "minor"}:
        pm = "major"
    sid = song_based_blob_session_id(session)
    src, song_id = song_practice_storage_id(session)
    blob = WorkflowStateBlob(
        workflow_owner="song_based_improvisation",
        workflow_session_id=sid,
        source_type=src,
        song_id=song_id,
        keys=KeyAuthority(
            original_tonic=pt,
            original_mode=pm,
            practice_tonic=pt,
            practice_mode=pm,
            key_owner="song_based_improvisation",
        ),
    )
    save_workflow_blob(session, blob, source="seed_live_practice_key")
    return resolve_song_practice_key_token(session)


def _section_map_total_chords(section_map: dict[str, list[str]] | None) -> int:
    if not isinstance(section_map, dict) or not section_map:
        return 0
    return sum(len(v) for v in section_map.values() if isinstance(v, list))


def rehydrate_full_song_concert_sections(session: dict[str, Any], *, source: str = "song_concert_rehydrate") -> dict[str, list[str]]:
    """Restore full catalog section progression — never a one-chord mission backing slice."""
    try:
        from backing_context import _song_improv_sections_dict

        resolved = _song_improv_sections_dict(session)
        if _section_map_total_chords(resolved) > 1:
            session["improv_song_concert_sections"] = copy.deepcopy(resolved)
            session["_music_song_concert_sections_source"] = source
            return copy.deepcopy(resolved)
    except ImportError:
        pass
    song = song_practice_blob(session)
    if song is not None and isinstance(song.section_map, dict) and _section_map_total_chords(song.section_map) > 1:
        session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
        session["_music_song_concert_sections_source"] = source
        return copy.deepcopy(song.section_map)
    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        out = sync_song_improv_sections_to_practice_key(session)
        if _section_map_total_chords(out) > 1:
            session["_music_song_concert_sections_source"] = source
            return copy.deepcopy(out)
    except ImportError:
        pass
    raw = session.get("improv_song_concert_sections")
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    return {}


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
    """Missions tab — song practice blob owns parent key; never re-apply entry jam after reclaim."""
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        mission_active = tab == "Missions" or (ptr and str(ptr.workflow_owner or "") == "mission_jam")
    except ImportError:
        mission_active = tab == "Missions"
    if mission_active:
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session, pre_widget=True)
        except ImportError:
            pass
        seed_song_practice_blob_from_live_practice_key(session)
        mirror_mission_keys_from_song_blob(session)
        rehydrate_full_song_concert_sections(session, source="missions_tab_song_blob_reconcile")
        token = sync_session_practice_key_from_song_blob(session, source="missions_tab_song_blob_reconcile")
        try:
            from sidebar_key_identity import prime_sidebar_practice_key_from_identity

            prime_sidebar_practice_key_from_identity(session)
        except ImportError:
            pass
        return token or resolve_song_practice_key_token(session)
    try:
        from creative_key_sync import entry_jam_practice_key_authority_active

        if not entry_jam_practice_key_authority_active(session):
            mirror_mission_keys_from_song_blob(session)
            rehydrate_full_song_concert_sections(session, source="missions_tab_song_blob_reconcile")
            song_tok = resolve_song_practice_key_token(session)
            if song_tok:
                live = str(session.get("display_key") or session.get("concert_key") or "").strip()
                if live != song_tok:
                    sync_session_practice_key_from_song_blob(session, source="missions_tab_song_blob_reconcile")
                try:
                    from sidebar_key_identity import prime_sidebar_practice_key_from_identity

                    prime_sidebar_practice_key_from_identity(session)
                except ImportError:
                    pass
    except ImportError:
        pass
    token = resolve_song_practice_key_token(session)
    if not token:
        return ""
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    blob = song_practice_blob(session)
    if live != token:
        sync_session_practice_key_from_song_blob(session, source="missions_tab_parent_key")
    elif blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
        rehydrate_full_song_concert_sections(session, source="missions_tab_parent_key_sections")
    return token


__all__ = [
    "mirror_mission_keys_from_song_blob",
    "mirror_song_practice_key_to_mission_blob",
    "mission_blob_session_id",
    "rehydrate_full_song_concert_sections",
    "resolve_song_practice_key_token",
    "seed_song_practice_blob_from_live_practice_key",
    "song_based_blob_session_id",
    "song_practice_blob",
    "song_practice_storage_id",
    "sync_session_practice_key_from_song_blob",
    "ensure_missions_parent_practice_key_hydrated",
]

"""Catalog song identity handoff into Creative / song-based workflow activation."""

from __future__ import annotations

import copy
from typing import Any

CATALOG_HANDOFF_TRACE_KEY = "_music_catalog_handoff_trace"


def record_catalog_handoff_trace(session: dict[str, Any], phase: str, **fields: Any) -> None:
    bucket = session.get(CATALOG_HANDOFF_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **fields})
    session[CATALOG_HANDOFF_TRACE_KEY] = bucket[-32:]


def live_catalog_pick_key(session: dict[str, Any]) -> str:
    return str(session.get("active_catalog_pick_key") or session.get("song") or "").strip()


def song_based_session_id_for_live_pick(session: dict[str, Any]) -> str:
    try:
        from music_workflow_song_practice import song_based_blob_session_id

        return song_based_blob_session_id(session)
    except ImportError:
        pick = live_catalog_pick_key(session)
        return pick if pick else "song"


def reconcile_song_based_target_session_id(
    session: dict[str, Any],
    *,
    target_owner: str,
    target_session_id: str,
) -> str:
    """When the active catalog pick changed, bind song-based activation to the live song id."""
    owner = str(target_owner or "").strip()
    sid = str(target_session_id or "").strip()
    if owner != "song_based_improvisation":
        return sid
    live_sid = song_based_session_id_for_live_pick(session)
    if not live_sid or live_sid == "song":
        return sid
    if sid != live_sid:
        record_catalog_handoff_trace(
            session,
            "rebind_target_session",
            previous_sid=sid,
            live_sid=live_sid,
            live_pick=live_catalog_pick_key(session),
        )
    return live_sid


def workflow_blob_matches_live_catalog_parent(session: dict[str, Any], blob: Any) -> bool:
    """True when a song-based blob belongs to the currently selected catalog song."""
    if blob is None:
        return False
    owner = str(getattr(blob, "workflow_owner", "") or "").strip()
    if owner != "song_based_improvisation":
        return True
    live_sid = song_based_session_id_for_live_pick(session)
    if not live_sid or live_sid == "song":
        return True
    blob_sid = str(getattr(blob, "workflow_session_id", "") or "").strip()
    blob_song = str(getattr(blob, "song_id", "") or "").strip()
    if blob_sid and blob_sid == live_sid:
        return True
    if blob_song and blob_song == live_sid:
        return True
    return not blob_sid and not blob_song


def sync_song_based_sections_for_live_pick(session: dict[str, Any], *, source: str) -> bool:
    """Rebuild improv song sections from the active catalog pick (not a stale workflow parent)."""
    try:
        from workflow_musical_authority import sync_song_improv_sections_to_practice_key

        sections = sync_song_improv_sections_to_practice_key(session)
        try:
            from song_improv_scope_authority import apply_song_improv_entry_defaults

            apply_song_improv_entry_defaults(session, source="catalog_handoff")
        except ImportError:
            pass
        record_catalog_handoff_trace(
            session,
            "sync_sections_for_live_pick",
            source=source,
            pick=live_catalog_pick_key(session),
            chord_count=sum(len(v) for v in (sections or {}).values()),
        )
        return bool(sections)
    except ImportError:
        return False


def stale_song_based_parent_session_id(session: dict[str, Any], *, creative_session: Any | None = None) -> str:
    """Workflow/creative parent song id that may disagree with the live catalog pick."""
    bound = ""
    if creative_session is not None:
        bound = str(getattr(creative_session, "bound_song_id", "") or "").strip()
    if bound:
        return bound
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == "song_based_improvisation":
            return str(ptr.workflow_session_id or "").strip()
    except ImportError:
        pass
    store = session.get("_workflow_musical_states")
    if isinstance(store, dict):
        snap = store.get("song_based_improvisation")
        if isinstance(snap, dict):
            return str(snap.get("session_id") or "").strip()
    return ""


def ensure_song_based_workflow_matches_live_pick(session: dict[str, Any], *, source: str) -> bool:
    """Activate song-based workflow for the live catalog pick when pointer/blob parent is stale."""
    live_sid = song_based_session_id_for_live_pick(session)
    if not live_sid or live_sid == "song":
        return False
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        ptr_sid = str(ptr.workflow_session_id or "") if ptr else ""
        if ptr and str(ptr.workflow_owner or "") == "song_based_improvisation" and ptr_sid == live_sid:
            try:
                from music_workflow_state_store import get_workflow_blob

                blob = get_workflow_blob(session, ptr.workflow_owner, ptr_sid)
                last_act = session.get("_music_workflow_activation_last")
                if not isinstance(last_act, dict):
                    last_act = {}
                built_compat = bool(last_act.get("incoming_blob_built_compat"))
                restored_saved = bool(
                    last_act.get("incoming_blob_restored")
                    and not built_compat
                    and blob is not None
                    and workflow_blob_matches_live_catalog_parent(session, blob)
                    and isinstance(blob.section_map, dict)
                    and blob.section_map
                )
                if built_compat or not restored_saved:
                    sync_song_based_sections_for_live_pick(session, source=f"{source}_ptr_aligned")
                    try:
                        from workflow_musical_authority import save_workflow_snapshot

                        save_workflow_snapshot(session, "song_based_improvisation")
                    except ImportError:
                        pass
                elif isinstance(blob.section_map, dict) and blob.section_map:
                    session["improv_song_concert_sections"] = copy.deepcopy(blob.section_map)
            except ImportError:
                pass
            return False
    except ImportError:
        ptr_sid = ""
    try:
        from music_workflow_activation import activate_workflow_simple

        result = activate_workflow_simple(
            session,
            "song_based_improvisation",
            activation_source=str(source or "catalog_pick_handoff"),
            navigation_intent="creative_entry",
        )
        record_catalog_handoff_trace(
            session,
            "ensure_song_based_workflow",
            source=source,
            live_sid=live_sid,
            previous_ptr_sid=ptr_sid,
            ok=bool(result.ok),
        )
        return bool(result.ok)
    except ImportError:
        return False


def reconcile_song_based_progression_for_live_catalog_pick(
    session: dict[str, Any],
    *,
    source: str,
    song_picker_catalog: dict | None = None,
) -> None:
    """Run while picker catalog is available (canonical prepare) — align sections with live pick."""
    if str(session.get("studio_page") or "").strip() != "creative":
        return
    if str(session.get("improv_entry_mode") or "").strip() != "Song-Based Improvisation":
        return
    live_sid = song_based_session_id_for_live_pick(session)
    if not live_sid or live_sid == "song":
        return
    if isinstance(song_picker_catalog, dict) and song_picker_catalog:
        session["_reconcile_song_picker_catalog"] = song_picker_catalog
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        ptr_sid = str(ptr.workflow_session_id or "") if ptr else ""
        blob = (
            get_workflow_blob(session, str(ptr.workflow_owner or ""), ptr_sid)
            if ptr and ptr_sid
            else None
        )
        last_act = session.get("_music_workflow_activation_last")
        if not isinstance(last_act, dict):
            last_act = {}
        built_compat = bool(last_act.get("incoming_blob_built_compat"))
        restored_saved = bool(
            last_act.get("incoming_blob_restored")
            and not built_compat
            and blob is not None
            and workflow_blob_matches_live_catalog_parent(session, blob)
            and isinstance(blob.section_map, dict)
            and blob.section_map
        )
        if ptr_sid and ptr_sid != live_sid:
            ensure_song_based_workflow_matches_live_pick(session, source=source)
        elif built_compat or not restored_saved:
            sync_song_based_sections_for_live_pick(session, source=source)
            try:
                from workflow_musical_authority import save_workflow_snapshot

                save_workflow_snapshot(session, "song_based_improvisation")
            except ImportError:
                pass
        elif blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
            session["improv_song_concert_sections"] = copy.deepcopy(blob.section_map)
        record_catalog_handoff_trace(
            session,
            "reconcile_progression_for_live_pick",
            source=source,
            live_sid=live_sid,
            ptr_sid=ptr_sid,
        )
    except ImportError:
        pass


__all__ = [
    "CATALOG_HANDOFF_TRACE_KEY",
    "ensure_song_based_workflow_matches_live_pick",
    "reconcile_song_based_progression_for_live_catalog_pick",
    "live_catalog_pick_key",
    "record_catalog_handoff_trace",
    "reconcile_song_based_target_session_id",
    "song_based_session_id_for_live_pick",
    "stale_song_based_parent_session_id",
    "sync_song_based_sections_for_live_pick",
    "workflow_blob_matches_live_catalog_parent",
]

"""Live trace for catalog Song-Based sidebar practice key changes."""

from __future__ import annotations

from typing import Any

SONG_PRACTICE_KEY_TRACE_KEY = "_music_song_practice_key_change_trace"


def record_song_practice_key_trace(session: dict[str, Any], phase: str, **fields: Any) -> None:
    bucket = session.get(SONG_PRACTICE_KEY_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **fields})
    session[SONG_PRACTICE_KEY_TRACE_KEY] = bucket[-48:]


def collect_song_practice_key_snapshot(session: dict[str, Any], *, phase: str) -> dict[str, Any]:
    """Capture fields required for minor-key practice key lifecycle debugging."""
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    owner = ""
    wf_sid = ""
    blob_pt = ""
    blob_pm = ""
    blob_orig_t = ""
    blob_orig_m = ""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr:
            owner = str(ptr.workflow_owner or "")
            wf_sid = str(ptr.workflow_session_id or "")
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None:
                blob_pt = str(blob.keys.practice_tonic or "")
                blob_pm = str(blob.keys.practice_mode or "")
                blob_orig_t = str(blob.keys.original_tonic or "")
                blob_orig_m = str(blob.keys.original_mode or "")
    except ImportError:
        pass
    live_sid = pick
    try:
        from music_workflow_song_practice import song_based_blob_session_id

        live_sid = song_based_blob_session_id(session) or pick
    except ImportError:
        pass
    pending = session.get("_music_pending_generated_key_edit")
    pending_song = session.get("_music_pending_song_practice_key_edit")
    outcome = session.get("_music_generated_key_edit_outcome")
    song_outcome = session.get("_music_song_practice_key_edit_outcome")
    snap = {
        "phase": phase,
        "active_catalog_pick_key": pick,
        "live_song_based_session_id": live_sid,
        "workflow_owner": owner,
        "workflow_session_id": wf_sid,
        "original_tonic": blob_orig_t,
        "original_mode": blob_orig_m,
        "practice_tonic": blob_pt,
        "practice_mode": blob_pm,
        "display_key": str(session.get("display_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
        "display_key_change_source": str(session.get("display_key_change_source") or ""),
        "pending_generated_key_edit": pending if isinstance(pending, dict) else None,
        "pending_song_practice_key_edit": pending_song if isinstance(pending_song, dict) else None,
        "generated_key_edit_outcome": outcome if isinstance(outcome, dict) else None,
        "song_practice_key_edit_outcome": song_outcome if isinstance(song_outcome, dict) else None,
        "pre_widget_bootstrap_last": session.get("_music_pre_widget_bootstrap_last"),
    }
    try:
        from musical_context_authority import resolve_authoritative_practice_key

        pk = resolve_authoritative_practice_key(session)
        snap["authoritative_practice_tonic"] = pk.practice_tonic
        snap["authoritative_practice_mode"] = pk.practice_mode
        snap["authoritative_original_tonic"] = pk.original_tonic
        snap["authoritative_original_mode"] = pk.original_mode
    except ImportError:
        pass
    try:
        from sidebar_key_identity import resolve_sidebar_key_identity

        ident = resolve_sidebar_key_identity(session)
        snap["sidebar_selector_token"] = ident.selector_token
        snap["sidebar_label"] = ident.label
    except ImportError:
        pass
    sections = session.get("improv_song_concert_sections")
    if isinstance(sections, dict):
        snap["progression_chord_count"] = sum(len(v) for v in sections.values() if isinstance(v, list))
    record_song_practice_key_trace(session, phase, **{k: v for k, v in snap.items() if k != "phase"})
    return snap


__all__ = [
    "SONG_PRACTICE_KEY_TRACE_KEY",
    "collect_song_practice_key_snapshot",
    "record_song_practice_key_trace",
]

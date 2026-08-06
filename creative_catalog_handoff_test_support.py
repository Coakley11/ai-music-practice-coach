"""Test-only catalog handoff identity snapshots (repro + trace assertions)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

HANDOFF_TEST_TRACE_KEY = "_music_catalog_handoff_trace"


def record_handoff_phase_trace(session: dict[str, Any], phase: str, **fields: Any) -> None:
    bucket = session.get(HANDOFF_TEST_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **fields})
    session[HANDOFF_TEST_TRACE_KEY] = bucket[-48:]


def progression_fingerprint(sections: dict[str, list[str]] | None) -> str:
    if not isinstance(sections, dict) or not sections:
        return ""
    payload = json.dumps({k: list(v) for k, v in sorted(sections.items())}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def collect_handoff_identity(session: dict[str, Any]) -> dict[str, Any]:
    """Snapshot fields required at each handoff phase."""
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    title = str(session.get("song") or session.get("active_song_title") or "").strip()
    sel = session.get("selected_song")
    if isinstance(sel, dict) and not title:
        title = str(sel.get("title") or "").strip()
    live_sid = ""
    try:
        from music_workflow_song_practice import song_based_blob_session_id

        live_sid = song_based_blob_session_id(session)
    except ImportError:
        live_sid = pick

    ptr_sid = ""
    blob_parent = ""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr:
            ptr_sid = str(ptr.workflow_session_id or "").strip()
            blob = get_workflow_blob(session, str(ptr.workflow_owner or ""), ptr_sid)
            if blob is not None:
                blob_parent = str(blob.song_id or blob.workflow_session_id or "").strip()
    except ImportError:
        pass

    snap_parent = ""
    store = session.get("_workflow_musical_states")
    if isinstance(store, dict):
        snap = store.get("song_based_improvisation")
        if isinstance(snap, dict):
            snap_parent = str(snap.get("session_id") or "").strip()

    sections = session.get("improv_song_concert_sections")
    if not isinstance(sections, dict):
        sections = {}
    chord_count = sum(len(v) for v in sections.values() if isinstance(v, list))

    rendered_parent = live_sid or pick
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == "song_based_improvisation":
            rendered_parent = str(ptr.workflow_session_id or rendered_parent).strip()
    except ImportError:
        pass

    ident = {
        "active_catalog_pick_key": pick,
        "selected_song_title": title,
        "live_song_based_session_id": live_sid,
        "pointer_session_id": ptr_sid,
        "blob_parent_song_id": blob_parent,
        "snapshot_parent_session_id": snap_parent,
        "rendered_song_based_parent": rendered_parent,
        "progression_fingerprint": progression_fingerprint(sections),
        "progression_chord_count": chord_count,
    }
    record_handoff_phase_trace(session, "collect_identity", **ident)
    return ident


def assert_catalog_parent_chain_agrees(session: dict[str, Any], expected_pick: str) -> dict[str, Any]:
    """After explicit catalog selection, all parent ids must match the live pick."""
    ident = collect_handoff_identity(session)
    expected = str(expected_pick or "").strip()
    errors: list[str] = []
    if ident["active_catalog_pick_key"] != expected:
        errors.append(f"pick={ident['active_catalog_pick_key']!r} expected={expected!r}")
    if ident["live_song_based_session_id"] and ident["live_song_based_session_id"] != expected:
        errors.append(f"live_sid={ident['live_song_based_session_id']!r}")
    if ident["pointer_session_id"] and ident["pointer_session_id"] != expected:
        errors.append(f"pointer={ident['pointer_session_id']!r}")
    if ident["blob_parent_song_id"] and ident["blob_parent_song_id"] != expected:
        errors.append(f"blob_parent={ident['blob_parent_song_id']!r}")
    if ident["snapshot_parent_session_id"] and ident["snapshot_parent_session_id"] != expected:
        errors.append(f"snapshot_parent={ident['snapshot_parent_session_id']!r}")
    if ident["rendered_song_based_parent"] and ident["rendered_song_based_parent"] != expected:
        errors.append(f"rendered_parent={ident['rendered_song_based_parent']!r}")
    if errors:
        trace = session.get(HANDOFF_TEST_TRACE_KEY)
        raise AssertionError(
            "catalog parent chain mismatch: " + "; ".join(errors) + f" trace={trace!r}"
        )
    return ident


def say_stale_progression_fingerprint(section_count: int = 144) -> str:
    return progression_fingerprint({"Full Song": ["G"] * section_count})


__all__ = [
    "HANDOFF_TEST_TRACE_KEY",
    "assert_catalog_parent_chain_agrees",
    "collect_handoff_identity",
    "progression_fingerprint",
    "record_handoff_phase_trace",
    "say_stale_progression_fingerprint",
]

"""Dev diagnostics — fixed key family path (saved → applied → final)."""

from __future__ import annotations

from typing import Any

from music_theory import key_mode


def _str(v: Any) -> str:
    return str(v or "").strip()


def _active_object_mode(session: dict[str, Any]) -> str:
    """Major/minor from the active song or progression — not from the family label."""
    for key in ("original_key", "concert_key", "display_key"):
        raw = _str(session.get(key))
        if raw:
            return key_mode(raw)
    try:
        from songs.state import SELECTED_SONG_STATE_KEY

        sel = session.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict):
            ok = _str(sel.get("key") or sel.get("original_key"))
            if ok:
                return key_mode(ok)
    except ImportError:
        pass
    return "major"


def _active_object_source(session: dict[str, Any]) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            return _str(getattr(ctx, "source", "") or "backing_context")
    except ImportError:
        pass
    if session.get("improv_active_mission"):
        return "mission"
    if session.get("cpl_active_progression"):
        return "custom_progression"
    return "catalog_song"


def collect_key_family_persistence_trace(session: dict[str, Any]) -> dict[str, Any]:
    """Trace selected_key_family through concert/practice/display keys."""
    payload = session.get("_suite_last_cloud_fetch_payload")
    saved_session = payload.get("session") if isinstance(payload, dict) else {}
    if not isinstance(saved_session, dict):
        saved_session = {}
    core = payload.get("core") if isinstance(payload, dict) else {}
    if not isinstance(core, dict):
        core = {}

    restore_trace = session.get("_music_workspace_restore_trace")
    if not isinstance(restore_trace, dict):
        restore_trace = {}

    try:
        from practice_key_mode import (
            MODE_FIXED,
            is_fixed_practice_key_mode,
            normalize_stored_family_option_id,
            resolve_family_option_id,
            resolve_fixed_practice_concert_key_for_family,
            resolve_session_key_from_family,
        )
    except ImportError:
        return {"error": "practice_key_mode unavailable"}

    family_saved = _str(saved_session.get("fixed_practice_key_family_id"))
    family_hydrated = family_saved
    family_applied = _str(restore_trace.get("key_family_applied"))
    family_final = _str(session.get("fixed_practice_key_family_id"))
    family_resolved_id = resolve_family_option_id(session)
    family_normalized = normalize_stored_family_option_id(family_final or family_saved)

    fixed_saved = _str(saved_session.get("practice_key_mode"))
    fixed_applied = _str(restore_trace.get("practice_key_mode_applied"))
    fixed_final = _str(session.get("practice_key_mode"))

    object_mode = _active_object_mode(session)
    object_source = _active_object_source(session)

    original = _str(session.get("original_key") or core.get("original_key"))
    if not original:
        try:
            from songs.state import SELECTED_SONG_STATE_KEY

            sel = session.get(SELECTED_SONG_STATE_KEY)
            if isinstance(sel, dict):
                original = _str(sel.get("key"))
        except ImportError:
            pass
    original = original or "C"

    concert_before = _str(session.get("concert_key") or core.get("concert_key") or original)
    practice_before = _str(session.get("practice_key") or core.get("practice_key") or concert_before)

    resolved_tonal = ""
    concert_after = concert_before
    practice_after = practice_before
    if is_fixed_practice_key_mode(session):
        resolved_tonal = resolve_session_key_from_family(family_resolved_id, object_mode)
        concert_after = resolve_fixed_practice_concert_key_for_family(family_resolved_id, original)
        practice_after = resolved_tonal

    display_final = _str(session.get("display_key") or core.get("display_key"))

    instrument = _str(session.get("instrument") or core.get("instrument"))
    transposition_mode = _str(session.get("transposition_mode") or session.get("written_key_mode"))
    capo_enabled = session.get("guitar_capo_enabled")
    shape_key = _str(session.get("guitar_capo_shape_key"))

    overwrite_stage = _str(session.get("key_family_overwritten_by_stage"))

    return {
        "key_family_saved": family_saved or "(none)",
        "key_family_hydrated": family_hydrated or "(none)",
        "key_family_applied": family_applied or "(none)",
        "key_family_final": family_final or "(none)",
        "key_family_resolved_option_id": family_resolved_id or "(none)",
        "key_family_normalized": family_normalized or "(none)",
        "fixed_key_enabled_saved": fixed_saved or "(none)",
        "fixed_key_enabled_applied": fixed_applied or "(none)",
        "fixed_key_enabled_final": fixed_final or "(none)",
        "fixed_key_enabled": fixed_final == MODE_FIXED,
        "active_object_source": object_source,
        "active_object_mode": object_mode,
        "resolved_session_tonal_key": resolved_tonal or "(n/a)",
        "concert_key_before_family_override": concert_before or "(none)",
        "concert_key_after_family_override": concert_after or "(none)",
        "practice_key_before_family_override": practice_before or "(none)",
        "practice_key_after_family_override": practice_after or "(none)",
        "display_key_final": display_final or "(none)",
        "instrument": instrument or "(none)",
        "transposition_mode": transposition_mode or "(none)",
        "capo_mode_enabled": capo_enabled,
        "shape_key": shape_key or "(none)",
        "key_family_overwritten_by_stage": overwrite_stage or "(none)",
        "loaded_workspace_revision": session.get("_suite_cloud_fetch_revision")
        or session.get("_music_loaded_workspace_revision"),
        "applied_workspace_revision": session.get("_music_applied_workspace_revision")
        or session.get("_suite_applied_workspace_revision"),
    }


__all__ = ["collect_key_family_persistence_trace"]

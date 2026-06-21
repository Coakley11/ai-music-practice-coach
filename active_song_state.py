"""Canonical active song context — pick_key, instrument, display key, level, focus."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    chart_in_instrument_key,
    is_transposing_instrument,
    options_for_instrument,
    selected_transposing_type,
)
from songs.key_state import PENDING_DISPLAY_KEY
from songs.music_source import SOURCE_CATALOG, SOURCE_CUSTOM, custom_progression_is_active, is_custom_progression, LAST_CATALOG_STATE_KEY
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
)

ACTIVE_SONG_STATE_KEY = "active_song_state"
ACTIVE_SONG_DIRTY_KEY = "active_song_state_dirty"
ACTIVE_SONG_LOCAL_EDIT_TS_KEY = "active_song_state_last_local_edit_ts"
ACTIVE_SONG_PENDING_SYNC_KEY = "_active_song_pending_sync"

ACTIVE_SONG_SCALAR_KEYS = (
    "pick_key",
    "display_key",
    "instrument",
    "level",
    "focus",
    "music_source",
    "custom_progression_name",
    "custom_home_key",
)

TRANSPOSING_WIDGET_SESSION_KEYS: tuple[str, ...] = (
    CHART_IN_INSTRUMENT_KEY_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
)

__all__ = (
    "ACTIVE_SONG_DIRTY_KEY",
    "ACTIVE_SONG_PENDING_SYNC_KEY",
    "ACTIVE_SONG_SCALAR_KEYS",
    "ACTIVE_SONG_STATE_KEY",
    "apply_active_song_source_state_from_ami",
    "apply_cloud_active_song_state_if_allowed",
    "canonical_active_song_context",
    "clear_active_song_local_edit",
    "collect_transposing_save_trace_fields",
    "commit_active_song_state_from_session",
    "finalize_transposing_receive_restore",
    "flush_active_song_edits",
    "gather_active_song_context",
    "is_active_song_locally_dirty",
    "mark_active_song_local_edit",
    "mark_active_song_pending_sync",
    "prepare_active_song_context",
    "render_active_song_state_debug",
    "sync_active_song_context_from_core",
    "TRANSPOSING_WIDGET_SESSION_KEYS",
    "transposing_subtype_from_blob",
    "written_key_mode_from_blob",
    "write_canonical_active_song_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_active_song_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(ACTIVE_SONG_DIRTY_KEY))


def mark_active_song_local_edit(session: dict[str, Any]) -> None:
    session[ACTIVE_SONG_DIRTY_KEY] = True
    session[ACTIVE_SONG_LOCAL_EDIT_TS_KEY] = _utc_now_iso()


def clear_active_song_local_edit(session: dict[str, Any]) -> None:
    session.pop(ACTIVE_SONG_DIRTY_KEY, None)
    session.pop(ACTIVE_SONG_LOCAL_EDIT_TS_KEY, None)
    session.pop(ACTIVE_SONG_PENDING_SYNC_KEY, None)


def mark_active_song_pending_sync(session: dict[str, Any]) -> None:
    session[ACTIVE_SONG_PENDING_SYNC_KEY] = True


def _normalize_selected_song(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out = copy.deepcopy(raw)
    if out.get("pick_key"):
        out["pick_key"] = str(out["pick_key"]).strip()
    if out.get("title"):
        out["title"] = str(out["title"]).strip()
    if out.get("artist") is not None:
        out["artist"] = str(out["artist"]).strip()
    return out


def _written_key_is_set(raw: dict[str, Any]) -> bool:
    return CHART_IN_INSTRUMENT_KEY_KEY in raw and raw[CHART_IN_INSTRUMENT_KEY_KEY] is not None


def _written_key_fields_from_raw(src: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if _written_key_is_set(src):
        out[CHART_IN_INSTRUMENT_KEY_KEY] = bool(src[CHART_IN_INSTRUMENT_KEY_KEY])
    anchor = str(src.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        out[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    return out


def _transposing_subtype_fields_from_raw(src: dict[str, Any]) -> dict[str, Any]:
    subtype = str(src.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
    if subtype:
        return {SELECTED_TRANSPOSING_INSTRUMENT_KEY: subtype}
    return {}


def _transposing_fields_from_raw(src: dict[str, Any]) -> dict[str, Any]:
    return {
        **_written_key_fields_from_raw(src),
        **_transposing_subtype_fields_from_raw(src),
    }


def _normalize_context(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    sel = _normalize_selected_song(src.get("selected_song"))
    pick_key = str(src.get("pick_key") or sel.get("pick_key") or "").strip()
    if pick_key and not sel.get("pick_key"):
        sel["pick_key"] = pick_key
    return {
        "pick_key": pick_key,
        "display_key": str(src.get("display_key") or "").strip(),
        "instrument": str(src.get("instrument") or "").strip(),
        "level": str(src.get("level") or "").strip(),
        "focus": str(src.get("focus") or "").strip(),
        "selected_song": sel,
        "music_source": str(src.get("music_source") or "").strip(),
        "custom_progression_name": str(src.get("custom_progression_name") or "").strip(),
        "custom_home_key": str(src.get("custom_home_key") or "").strip(),
        **_transposing_fields_from_raw(src),
    }


def _live_written_key_for_save(session: dict[str, Any]) -> bool:
    """Save path: widget → canonical meta → default False (never invent True)."""
    if CHART_IN_INSTRUMENT_KEY_KEY in session:
        return bool(session[CHART_IN_INSTRUMENT_KEY_KEY])
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict) and _written_key_is_set(meta):
        return bool(meta[CHART_IN_INSTRUMENT_KEY_KEY])
    return chart_in_instrument_key(session)


def _live_subtype_for_save(session: dict[str, Any], instrument_name: str) -> str:
    """Save path: widget → canonical meta → default type (avoid stale Alto on commit)."""
    if not is_transposing_instrument(instrument_name):
        return ""
    opts = options_for_instrument(instrument_name)
    if SELECTED_TRANSPOSING_INSTRUMENT_KEY in session:
        pick = str(session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if pick in opts:
            return pick
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        pick = str(meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if pick in opts:
            return pick
    return selected_transposing_type(session, instrument_name)


def _transposing_values_from_payload_sources(
    payload: dict[str, Any],
) -> tuple[bool | None, str | None]:
    """Read written-key + subtype from a disk/cloud music payload."""
    if not isinstance(payload, dict):
        return None, None
    written: bool | None = None
    subtype: str | None = None
    sources: list[dict[str, Any]] = []
    meta = payload.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        sources.append(meta)
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("active_song"), dict):
        sources.append(ws["active_song"])
    session_blob = payload.get("session")
    if isinstance(session_blob, dict):
        sources.append(session_blob)
    for src in sources:
        if written is None and _written_key_is_set(src):
            written = bool(src[CHART_IN_INSTRUMENT_KEY_KEY])
    for src in sources:
        st_val = str(src.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if st_val:
            subtype = st_val
            break
    return written, subtype


def collect_transposing_save_trace_fields(
    session: dict[str, Any],
    payload: dict[str, Any] | None = None,
    *,
    phase: str = "",
) -> dict[str, Any]:
    """Canonical vs payload vs widget transposing fields for save diagnostics."""
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict):
        meta = {}
    widget_written = (
        bool(session[CHART_IN_INSTRUMENT_KEY_KEY])
        if CHART_IN_INSTRUMENT_KEY_KEY in session
        else None
    )
    widget_subtype = (
        str(session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip() or None
        if SELECTED_TRANSPOSING_INSTRUMENT_KEY in session
        else None
    )
    canonical_written = (
        bool(meta[CHART_IN_INSTRUMENT_KEY_KEY]) if _written_key_is_set(meta) else None
    )
    canonical_subtype = str(meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip() or None
    payload_written: bool | None = None
    payload_subtype: str | None = None
    if isinstance(payload, dict):
        payload_written, payload_subtype = _transposing_values_from_payload_sources(payload)
    out = {
        "save_phase": phase or None,
        "save_written_key_widget": widget_written,
        "save_written_key_canonical": canonical_written,
        "save_written_key_payload": payload_written,
        "save_transposing_subtype_widget": widget_subtype,
        "save_transposing_subtype_canonical": canonical_subtype,
        "save_transposing_subtype_payload": payload_subtype,
        "save_reason": str(session.get("_music_build_save_reason") or session.get("_suite_pending_save_reason") or "").strip()
        or None,
    }
    return out


def _session_has_live_global_controls(session: dict[str, Any]) -> bool:
    return any(
        str(session.get(key) or "").strip()
        for key in ("instrument", "level", "focus", "display_key")
    )


def _merge_live_global_controls(
    session: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Session globals win over stale canonical values on normal reruns."""
    live = gather_active_song_context(session)
    merged = dict(ctx)
    live_pick = str(live.get("pick_key") or "").strip()
    ctx_pick = str(ctx.get("pick_key") or "").strip()
    song_changed = bool(live_pick and ctx_pick and live_pick != ctx_pick)
    if custom_progression_is_active(session) or str(ctx.get("music_source") or "") == SOURCE_CUSTOM:
        home_key = str(
            ctx.get("custom_home_key")
            or live.get("custom_home_key")
            or (ctx.get("selected_song") or {}).get("key")
            or "C"
        ).strip() or "C"
        merged["display_key"] = _resolve_custom_display_key_for_session(session, home_key)
        for key in ("instrument", "level", "focus"):
            live_val = str(live.get(key) or "").strip()
            if live_val:
                merged[key] = live_val
        if song_changed and live_pick:
            merged["pick_key"] = live_pick
        return merged
    for key in ("instrument", "level", "focus", "display_key"):
        if key == "display_key" and song_changed:
            continue
        live_val = str(live.get(key) or "").strip()
        if live_val:
            merged[key] = live_val
    if song_changed and live_pick:
        merged["pick_key"] = live_pick
    return merged


def _resolve_display_key_from_music_blob(
    state: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
    home_key: str = "C",
) -> str:
    """Resolve persisted display/practice key from cloud/disk payload layers."""
    candidates: list[Any] = []
    if isinstance(ctx, dict):
        candidates.append(ctx.get("display_key"))
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        candidates.append(meta.get("display_key"))
    core = state.get("core")
    if isinstance(core, dict):
        candidates.append(core.get("display_key"))
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict):
        candidates.append(ws.get("display_key"))
        active = ws.get("active_song")
        if isinstance(active, dict):
            candidates.append(active.get("display_key"))
    session_blob = state.get("session")
    if isinstance(session_blob, dict):
        candidates.append(session_blob.get("display_key"))
    for val in candidates:
        resolved = str(val or "").strip()
        if resolved:
            return resolved
    return str(home_key or "C").strip() or "C"


def _resolve_custom_display_key_for_session(
    session: dict[str, Any],
    home_key: str,
) -> str:
    """Resolve custom display key: user override, then canonical, then session, then home."""
    home = str(home_key or "C").strip() or "C"
    live = str(session.get("display_key") or "").strip()
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    canonical = ""
    if isinstance(meta, dict):
        canonical = str(meta.get("display_key") or "").strip()
    change_source = str(session.get("display_key_change_source") or "").strip()
    user_override = bool(live and live != home and change_source)
    if user_override:
        return live
    if canonical:
        return canonical
    if live:
        return live
    return home


def _push_resolved_display_key_to_session(
    session: dict[str, Any],
    ctx: dict[str, Any],
) -> None:
    """Apply canonical/custom display key to session before sidebar widgets render."""
    from songs.music_source import cpl_session_is_active

    if cpl_session_is_active(session) or str(ctx.get("music_source") or "") == SOURCE_CUSTOM:
        home_key = str(
            ctx.get("custom_home_key")
            or (ctx.get("selected_song") or {}).get("key")
            or "C"
        ).strip() or "C"
        resolved = str(ctx.get("display_key") or "").strip() or _resolve_custom_display_key_for_session(
            session,
            home_key,
        )
    else:
        resolved = str(ctx.get("display_key") or "").strip()
    if not resolved:
        return
    live = str(session.get("display_key") or "").strip()
    if resolved == live:
        return
    session[PENDING_DISPLAY_KEY] = resolved
    try:
        session["display_key"] = resolved
    except Exception:
        pass


def gather_active_song_context(session: dict[str, Any]) -> dict[str, Any]:
    """Read active song context from live session keys."""
    if custom_progression_is_active(session):
        from custom_progression_lab import (
            default_active_progression,
            ensure_original_structure,
            cpl_draft_written_key,
        )
        from songs.music_source import custom_pick_key_for, custom_selected_song_record

        active = ensure_original_structure(
            session.get("cpl_active_progression") or default_active_progression()
        )
        selected = custom_selected_song_record(active)
        home_key = cpl_draft_written_key(active)
        pick_key = str(selected.get("pick_key") or custom_pick_key_for(active)).strip()
        instrument_name = str(session.get("instrument") or "").strip()
        display_key = _resolve_custom_display_key_for_session(session, home_key)
        ctx = {
            "pick_key": pick_key,
            "display_key": display_key,
            "instrument": instrument_name,
            "level": str(session.get("level") or "").strip(),
            "focus": str(session.get("focus") or "").strip(),
            "selected_song": selected,
            "music_source": SOURCE_CUSTOM,
            "custom_progression_name": str(selected.get("title") or "").strip(),
            "custom_home_key": home_key,
            CHART_IN_INSTRUMENT_KEY_KEY: _live_written_key_for_save(session),
        }
        anchor = str(session.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
        if anchor:
            ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
        if is_transposing_instrument(instrument_name):
            subtype = _live_subtype_for_save(session, instrument_name)
            if subtype:
                ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
        return ctx

    sel = session.get(SELECTED_SONG_STATE_KEY)
    selected = _normalize_selected_song(sel)
    pick_key = str(
        session.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
    ).strip()
    if pick_key and not selected.get("pick_key"):
        selected["pick_key"] = pick_key
    instrument_name = str(session.get("instrument") or "").strip()
    ctx = {
        "pick_key": pick_key,
        "display_key": str(session.get("display_key") or "").strip(),
        "instrument": instrument_name,
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
        "selected_song": selected,
        "music_source": SOURCE_CATALOG,
        CHART_IN_INSTRUMENT_KEY_KEY: _live_written_key_for_save(session),
    }
    anchor = str(session.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    if is_transposing_instrument(instrument_name):
        subtype = _live_subtype_for_save(session, instrument_name)
        if subtype:
            ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    return ctx


def canonical_active_song_context(session: dict[str, Any]) -> dict[str, Any] | None:
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict):
        return None
    ctx = _normalize_context(meta)
    if ctx.get("music_source") == SOURCE_CUSTOM:
        return ctx
    if not ctx.get("pick_key") and not ctx.get("instrument") and not ctx.get("display_key"):
        if not ctx.get("selected_song"):
            return None
    return ctx


def _merge_live_transposing_fields(
    session: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Fold live written-key + transposing subtype into canonical context before save."""
    instrument_name = str(
        session.get("instrument") or ctx.get("instrument") or ""
    ).strip()
    ctx[CHART_IN_INSTRUMENT_KEY_KEY] = _live_written_key_for_save(session)
    anchor = str(session.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if not anchor:
        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            anchor = str(meta.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    else:
        ctx.pop(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY, None)
    subtype = _live_subtype_for_save(session, instrument_name)
    if subtype:
        ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    else:
        ctx.pop(SELECTED_TRANSPOSING_INSTRUMENT_KEY, None)
    return ctx


def _transposing_receive_source_dicts(
    state: dict[str, Any],
    *,
    deferred_session: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ordered cloud receive sources — deferred session, workspace, session extra, canonical meta."""
    sources: list[dict[str, Any]] = []
    if isinstance(deferred_session, dict) and deferred_session:
        sources.append(deferred_session)
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("active_song"), dict):
        sources.append(ws["active_song"])
    session_blob = state.get("session")
    if isinstance(session_blob, dict):
        sources.append(session_blob)
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        sources.append(meta)
    return sources


def _resolve_written_key_from_receive_sources(
    sources: list[dict[str, Any]],
) -> bool | None:
    """Any explicit True wins; otherwise first explicit False; else unset."""
    saw_false = False
    for src in sources:
        if not _written_key_is_set(src):
            continue
        if bool(src[CHART_IN_INSTRUMENT_KEY_KEY]):
            return True
        saw_false = True
    return False if saw_false else None


def _resolve_subtype_from_receive_sources(
    sources: list[dict[str, Any]],
) -> str | None:
    for src in sources:
        subtype = str(src.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if subtype:
            return subtype
    return None


def _resolve_written_key_anchor_from_receive_sources(
    sources: list[dict[str, Any]],
) -> str | None:
    for src in sources:
        anchor = str(src.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
        if anchor:
            return anchor
    return None


def _merge_transposing_from_blob_sources(
    ctx: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Prefer workspace/session transposing fields over stale canonical active_song_state."""
    sources = _transposing_receive_source_dicts(state)
    written = _resolve_written_key_from_receive_sources(sources)
    if written is not None:
        ctx[CHART_IN_INSTRUMENT_KEY_KEY] = written
    subtype = _resolve_subtype_from_receive_sources(sources)
    if subtype:
        ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    anchor = _resolve_written_key_anchor_from_receive_sources(sources)
    if anchor:
        ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    return ctx


def finalize_transposing_receive_restore(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    deferred_session: dict[str, Any] | None = None,
    source: str = "receive_finalize",
) -> None:
    """Phone receive path — bind written-key + subtype from cloud payload after restore."""
    if not isinstance(payload, dict):
        return
    sources = _transposing_receive_source_dicts(payload, deferred_session=deferred_session)
    written = _resolve_written_key_from_receive_sources(sources)
    subtype = _resolve_subtype_from_receive_sources(sources)
    anchor = _resolve_written_key_anchor_from_receive_sources(sources)
    if written is None and not subtype and not anchor:
        return

    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict):
        meta = {}
    updated = False
    if written is not None:
        meta[CHART_IN_INSTRUMENT_KEY_KEY] = written
        session[CHART_IN_INSTRUMENT_KEY_KEY] = written
        session["_written_key_mode_cloud"] = written
        session["_written_key_mode_restored"] = written
        session["_written_key_restore_source"] = source
        updated = True
    if anchor:
        meta[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
        updated = True
    if subtype:
        meta[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
        session["_transposing_subtype_cloud"] = subtype
        session["_transposing_subtype_restored"] = subtype
        session["_transposing_subtype_restore_source"] = source
        updated = True
    if updated:
        session[ACTIVE_SONG_STATE_KEY] = meta
    rehydrate_transposing_sidebar_from_canonical(session)


def _record_transposing_restore_trace(
    session: dict[str, Any],
    ctx: dict[str, Any],
    *,
    source: str,
) -> None:
    if _written_key_is_set(ctx):
        session["_written_key_mode_restored"] = bool(ctx[CHART_IN_INSTRUMENT_KEY_KEY])
        session["_written_key_restore_source"] = source
    subtype = str(ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
    if subtype:
        session["_transposing_subtype_restored"] = subtype
        session["_transposing_subtype_restore_source"] = source


def rehydrate_transposing_sidebar_from_canonical(session: dict[str, Any]) -> None:
    """Bind written-key + subtype widget keys from canonical blob before sidebar render."""
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict):
        return
    if _written_key_is_set(meta):
        session[CHART_IN_INSTRUMENT_KEY_KEY] = bool(meta[CHART_IN_INSTRUMENT_KEY_KEY])
    anchor = str(meta.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    subtype = str(meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
    if subtype:
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype


def _log_widget_bound_session_mutation_blocked(
    key: str,
    source: str,
    exc: Exception,
) -> None:
    """Best-effort trace when a widget-bound session key cannot be mutated late in a run."""
    msg = (
        f"Blocked session mutation for widget-bound key `{key}` "
        f"(source={source or 'unknown'}): {exc}"
    )
    try:
        import streamlit as st

        trace = st.session_state.setdefault("_widget_bound_mutation_trace", [])
        if isinstance(trace, list):
            trace.append(msg)
            if len(trace) > 12:
                del trace[:-12]
    except Exception:
        pass


def _apply_context_to_session_keys(
    session: dict[str, Any],
    ctx: dict[str, Any],
    *,
    mutate_display_key: bool = True,
    mutate_written_key: bool = True,
    mutate_transposing_subtype: bool = True,
    apply_global_controls: bool = True,
    global_control_source: str = "",
) -> None:
    try:
        from practice_setup_globals import record_global_control_change
    except ImportError:
        record_global_control_change = None  # type: ignore[assignment,misc]

    pick_key = str(ctx.get("pick_key") or "").strip()
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key
    display_key = str(ctx.get("display_key") or "").strip()
    if display_key and apply_global_controls:
        session[PENDING_DISPLAY_KEY] = display_key
        if mutate_display_key:
            if record_global_control_change is not None:
                record_global_control_change(
                    session,
                    "display_key",
                    global_control_source or "canonical_apply",
                    overwrite=True,
                )
            session["display_key"] = display_key
    for key in ("instrument", "level", "focus"):
        val = str(ctx.get(key) or "").strip()
        if val and apply_global_controls:
            if record_global_control_change is not None:
                record_global_control_change(
                    session,
                    key,
                    global_control_source or "canonical_apply",
                    overwrite=True,
                )
            try:
                session[key] = val
            except Exception as exc:
                _log_widget_bound_session_mutation_blocked(key, global_control_source, exc)
                raise
    selected = _normalize_selected_song(ctx.get("selected_song"))
    if selected:
        if pick_key:
            selected.setdefault("pick_key", pick_key)
        session[SELECTED_SONG_STATE_KEY] = selected
    if mutate_written_key and _written_key_is_set(ctx):
        session[CHART_IN_INSTRUMENT_KEY_KEY] = bool(ctx[CHART_IN_INSTRUMENT_KEY_KEY])
    anchor = str(ctx.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if mutate_written_key and anchor:
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    subtype = str(ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
    if mutate_transposing_subtype and subtype:
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype


def write_canonical_active_song_state(
    session: dict[str, Any],
    context: dict[str, Any],
    *,
    reason: str = "",
    local_edit: bool = False,
    mutate_display_key: bool | None = None,
    mutate_written_key: bool | None = None,
    mutate_transposing_subtype: bool | None = None,
    apply_global_controls_to_session: bool | None = None,
) -> dict[str, Any]:
    """Single write path for active song context."""
    ctx = _normalize_context(context)
    session[ACTIVE_SONG_STATE_KEY] = {
        **ctx,
        "last_write_reason": reason or None,
    }
    music_source = str(ctx.get("music_source") or "").strip()
    if music_source == SOURCE_CUSTOM:
        session["active_music_source"] = SOURCE_CUSTOM
    elif music_source == SOURCE_CATALOG:
        session["active_music_source"] = SOURCE_CATALOG
    mutate_wk = True if mutate_written_key is None else mutate_written_key
    mutate_subtype = True if mutate_transposing_subtype is None else mutate_transposing_subtype
    if apply_global_controls_to_session is None:
        apply_global_controls_to_session = reason not in (
            "canonical_preserve",
            "autosave",
        )
    _apply_context_to_session_keys(
        session,
        ctx,
        mutate_display_key=True if mutate_display_key is None else mutate_display_key,
        mutate_written_key=mutate_wk,
        mutate_transposing_subtype=mutate_subtype,
        apply_global_controls=apply_global_controls_to_session,
        global_control_source=reason or "canonical_write",
    )
    if local_edit:
        mark_active_song_local_edit(session)
    session.pop(ACTIVE_SONG_PENDING_SYNC_KEY, None)
    return ctx


def prepare_active_song_context(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile session keys with canonical blob before widgets render."""
    try:
        from songs.music_source import ensure_active_music_source_from_canonical

        ensure_active_music_source_from_canonical(session)
    except ImportError:
        pass
    restored_this_run = bool(
        session.get("_cloud_workspace_restored_this_run")
        or session.get(SUITE_LOCAL_STATE_RESTORED_KEY)
    )
    if is_active_song_locally_dirty(session) and restored_this_run:
        clear_active_song_local_edit(session)
    elif is_active_song_locally_dirty(session):
        ctx = gather_active_song_context(session)
        return write_canonical_active_song_state(
            session,
            ctx,
            reason="local_edit_preserve",
            local_edit=True,
        )

    canonical = canonical_active_song_context(session)
    if canonical is not None:
        ctx = dict(canonical)
        apply_globals = restored_this_run or not _session_has_live_global_controls(session)
        if not restored_this_run:
            live = gather_active_song_context(session)
            live_pick = str(live.get("pick_key") or "").strip()
            canon_pick = str(ctx.get("pick_key") or "").strip()
            if is_custom_progression(session):
                ctx["music_source"] = SOURCE_CUSTOM
                if live.get("selected_song"):
                    ctx["selected_song"] = live["selected_song"]
                home_key = str(
                    ctx.get("custom_home_key")
                    or live.get("custom_home_key")
                    or (live.get("selected_song") or {}).get("key")
                    or "C"
                ).strip() or "C"
                ctx["display_key"] = _resolve_custom_display_key_for_session(session, home_key)
                if live_pick:
                    ctx["pick_key"] = live_pick
                if live.get("custom_progression_name"):
                    ctx["custom_progression_name"] = live["custom_progression_name"]
                if live.get("custom_home_key"):
                    ctx["custom_home_key"] = live["custom_home_key"]
            elif str(ctx.get("music_source") or "") == SOURCE_CUSTOM and not is_custom_progression(session):
                snap = session.get(LAST_CATALOG_STATE_KEY)
                if isinstance(snap, dict) and snap.get("pick_key"):
                    ctx.update(
                        {
                            "pick_key": str(snap.get("pick_key") or "").strip(),
                            "display_key": str(snap.get("display_key") or "").strip(),
                            "instrument": str(live.get("instrument") or ctx.get("instrument") or "").strip(),
                            "level": str(live.get("level") or ctx.get("level") or "").strip(),
                            "focus": str(live.get("focus") or ctx.get("focus") or "").strip(),
                            "selected_song": snap.get("selected_song") or ctx.get("selected_song") or {},
                            "music_source": SOURCE_CATALOG,
                        }
                    )
                    ctx.pop("custom_home_key", None)
                    ctx.pop("custom_progression_name", None)
                elif live_pick and not live_pick.startswith("custom::"):
                    ctx.update(
                        {
                            "pick_key": live_pick,
                            "display_key": str(live.get("display_key") or "").strip(),
                            "instrument": str(live.get("instrument") or ctx.get("instrument") or "").strip(),
                            "level": str(live.get("level") or ctx.get("level") or "").strip(),
                            "focus": str(live.get("focus") or ctx.get("focus") or "").strip(),
                            "selected_song": live.get("selected_song") or ctx.get("selected_song") or {},
                            "music_source": SOURCE_CATALOG,
                        }
                    )
                    ctx.pop("custom_home_key", None)
                    ctx.pop("custom_progression_name", None)
            elif live_pick and live_pick != canon_pick:
                ctx["pick_key"] = live_pick
                if live.get("selected_song"):
                    ctx["selected_song"] = live["selected_song"]
                ctx.pop("display_key", None)
                song_key = str((live.get("selected_song") or {}).get("key") or "").strip()
                if song_key:
                    session[PENDING_DISPLAY_KEY] = song_key
            else:
                ctx = _merge_live_global_controls(session, ctx)
        ctx = write_canonical_active_song_state(
            session,
            ctx,
            reason="canonical_preserve",
            apply_global_controls_to_session=apply_globals,
        )
        _record_transposing_restore_trace(session, ctx, source="canonical_prepare")
        rehydrate_transposing_sidebar_from_canonical(session)
        _push_resolved_display_key_to_session(session, ctx)
        return ctx

    gathered = gather_active_song_context(session)
    if gathered.get("pick_key") or gathered.get("instrument") or gathered.get("display_key"):
        ctx = write_canonical_active_song_state(
            session,
            gathered,
            reason="reconcile_on_load",
        )
        rehydrate_transposing_sidebar_from_canonical(session)
        _push_resolved_display_key_to_session(session, ctx)
        return ctx
    _push_resolved_display_key_to_session(session, gathered)
    return gathered


def commit_active_song_state_from_session(
    session: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    """Persist canonical blob from current session without marking a new local edit."""
    ctx = canonical_active_song_context(session) or gather_active_song_context(session)
    ctx = _merge_live_transposing_fields(session, dict(ctx))
    ctx = _merge_live_global_controls(session, ctx)
    if custom_progression_is_active(session) or str(ctx.get("music_source") or "") == SOURCE_CUSTOM:
        home_key = str(
            ctx.get("custom_home_key")
            or (ctx.get("selected_song") or {}).get("key")
            or "C"
        ).strip() or "C"
        ctx["display_key"] = _resolve_custom_display_key_for_session(session, home_key)
    return write_canonical_active_song_state(
        session,
        ctx,
        reason=reason,
        local_edit=False,
        mutate_display_key=False,
        mutate_written_key=False,
        mutate_transposing_subtype=False,
        apply_global_controls_to_session=False,
    )


def flush_active_song_edits(session: dict[str, Any], *, reason: str = "song_edit") -> dict[str, Any]:
    """End-of-rerun flush after user changed song/instrument/key."""
    ctx = gather_active_song_context(session)
    return write_canonical_active_song_state(
        session,
        ctx,
        reason=reason,
        local_edit=True,
    )


def sync_active_song_context_from_core(session: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
    """Seed canonical active song from legacy ``core`` restore payload."""
    if not isinstance(core, dict) or not core:
        return gather_active_song_context(session)
    ctx = gather_active_song_context(session)
    for key in ACTIVE_SONG_SCALAR_KEYS:
        val = str(core.get(key) or "").strip()
        if val:
            ctx[key] = val
    if core.get("song") and isinstance(ctx.get("selected_song"), dict):
        ctx["selected_song"]["title"] = str(core.get("song") or ctx["selected_song"].get("title") or "")
        ctx["selected_song"]["artist"] = str(core.get("artist") or ctx["selected_song"].get("artist") or "")
    if core.get("pick_key"):
        ctx["pick_key"] = str(core["pick_key"]).strip()
    return write_canonical_active_song_state(session, ctx, reason="core_restore")


def _custom_context_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    source = str(session_extra.get("active_music_source") or "").strip()
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if not source and isinstance(meta, dict):
        source = str(meta.get("music_source") or "").strip()
    if source != SOURCE_CUSTOM:
        return None

    from custom_progression_lab import default_active_progression, ensure_original_structure, cpl_draft_written_key
    from songs.music_source import custom_pick_key_for, custom_selected_song_record

    cpl = session_extra.get("cpl_active_progression")
    if not isinstance(cpl, dict):
        cpl = default_active_progression()
    active = ensure_original_structure(cpl)
    selected = custom_selected_song_record(active)
    home_key = cpl_draft_written_key(active)
    ctx = _normalize_context(meta if isinstance(meta, dict) else {})
    ctx.update(
        {
            "pick_key": str(ctx.get("pick_key") or selected.get("pick_key") or custom_pick_key_for(active)).strip(),
            "display_key": _resolve_display_key_from_music_blob(
                state,
                ctx=ctx,
                home_key=home_key,
            ),
            "selected_song": selected,
            "music_source": SOURCE_CUSTOM,
            "custom_progression_name": str(selected.get("title") or "").strip(),
            "custom_home_key": home_key,
        }
    )
    return _merge_transposing_from_blob_sources(ctx, state)


def _active_song_context_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:
    custom_ctx = _custom_context_from_blob(state)
    if custom_ctx is not None:
        return custom_ctx
    if not isinstance(state, dict):
        return None
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        ctx = _normalize_context(meta)
        if ctx.get("music_source") == SOURCE_CUSTOM:
            return _merge_transposing_from_blob_sources(ctx, state)
        if ctx.get("pick_key") or ctx.get("instrument") or ctx.get("display_key"):
            return _merge_transposing_from_blob_sources(ctx, state)
    core = state.get("core") if isinstance(state.get("core"), dict) else state
    if isinstance(core, dict) and (core.get("pick_key") or core.get("song")):
        sel: dict[str, Any] = {}
        if core.get("song"):
            sel["title"] = str(core.get("song") or "")
            sel["artist"] = str(core.get("artist") or "")
        return _normalize_context(
            {
                "pick_key": core.get("pick_key"),
                "display_key": core.get("display_key"),
                "instrument": core.get("instrument"),
                "level": core.get("level"),
                "focus": core.get("focus"),
                "practice_focus_section": core.get("practice_focus_section"),
                "selected_song": sel,
            }
        )
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("active_song"), dict):
        ctx = _normalize_context(ws["active_song"])
        if ctx.get("pick_key") or ctx.get("display_key"):
            return _merge_transposing_from_blob_sources(ctx, state)
    return None


def _transposing_value_from_blob_sources(
    state: dict[str, Any],
    key: str,
) -> Any | None:
    if not isinstance(state, dict):
        return None
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict) and key in meta and meta.get(key) is not None:
        return meta.get(key)
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict):
        active = ws.get("active_song")
        if isinstance(active, dict) and key in active and active.get(key) is not None:
            return active.get(key)
    session_blob = state.get("session")
    if isinstance(session_blob, dict) and key in session_blob and session_blob.get(key) is not None:
        return session_blob.get(key)
    return None


def written_key_mode_from_blob(state: dict[str, Any]) -> bool | None:
    """Read written-key checkbox from a disk/cloud music payload."""
    raw = _transposing_value_from_blob_sources(state, CHART_IN_INSTRUMENT_KEY_KEY)
    return bool(raw) if raw is not None else None


def transposing_subtype_from_blob(state: dict[str, Any]) -> str | None:
    """Read transposing subtype (e.g. Alto saxophone) from a disk/cloud music payload."""
    raw = _transposing_value_from_blob_sources(state, SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    subtype = str(raw or "").strip()
    return subtype or None


def apply_cloud_active_song_state_if_allowed(
    session: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    """Apply cloud/disk active song only when this device has no local song edits."""
    if is_active_song_locally_dirty(session):
        session["_active_song_restore_skipped_reason"] = "local_dirty"
        return False
    custom_ctx = _custom_context_from_blob(state)
    if custom_ctx is not None:
        session["active_music_source"] = SOURCE_CUSTOM
        session["_written_key_mode_cloud"] = (
            bool(custom_ctx[CHART_IN_INSTRUMENT_KEY_KEY])
            if _written_key_is_set(custom_ctx)
            else None
        )
        session["_transposing_subtype_cloud"] = (
            str(custom_ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip() or None
        )
        write_canonical_active_song_state(session, custom_ctx, reason="cloud_restore_custom")
        _record_transposing_restore_trace(session, custom_ctx, source="cloud_restore_custom")
        _push_resolved_display_key_to_session(session, custom_ctx)
        rehydrate_transposing_sidebar_from_canonical(session)
        clear_active_song_local_edit(session)
        return True
    ctx = _active_song_context_from_blob(state)
    if not ctx or not ctx.get("pick_key"):
        return False
    session["_written_key_mode_cloud"] = (
        bool(ctx[CHART_IN_INSTRUMENT_KEY_KEY]) if _written_key_is_set(ctx) else None
    )
    session["_transposing_subtype_cloud"] = (
        str(ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip() or None
    )
    write_canonical_active_song_state(session, ctx, reason="cloud_restore")
    _record_transposing_restore_trace(session, ctx, source="cloud_restore")
    _push_resolved_display_key_to_session(session, ctx)
    rehydrate_transposing_sidebar_from_canonical(session)
    clear_active_song_local_edit(session)
    return True


def apply_active_song_source_state_from_ami(
    session: dict[str, Any],
    source_state: dict[str, Any],
) -> None:
    """Restore active song fields from Music Coach / AMI return payload."""
    if not isinstance(source_state, dict):
        return
    entity = source_state.get("entity_params")
    widgets = source_state.get("widget_params")
    ctx = gather_active_song_context(session)
    if isinstance(entity, dict):
        pick_key = str(entity.get("pick_key") or "").strip()
        if pick_key:
            ctx["pick_key"] = pick_key
        title = str(entity.get("song_title") or "").strip()
        artist = str(entity.get("song_artist") or "").strip()
        if title:
            sel = dict(ctx.get("selected_song") or {})
            sel["title"] = title
            if artist:
                sel["artist"] = artist
            if pick_key:
                sel["pick_key"] = pick_key
            ctx["selected_song"] = sel
    if isinstance(widgets, dict):
        for key in ACTIVE_SONG_SCALAR_KEYS:
            if key in widgets and widgets[key]:
                ctx[key] = str(widgets[key]).strip()
        if CHART_IN_INSTRUMENT_KEY_KEY in widgets:
            ctx[CHART_IN_INSTRUMENT_KEY_KEY] = bool(widgets[CHART_IN_INSTRUMENT_KEY_KEY])
        anchor = str(widgets.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
        if anchor:
            ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
        subtype = str(widgets.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if subtype:
            ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    write_canonical_active_song_state(session, ctx, reason="ami_return")
    _record_transposing_restore_trace(session, ctx, source="ami_return")
    rehydrate_transposing_sidebar_from_canonical(session)
    clear_active_song_local_edit(session)


def render_active_song_state_debug(st: Any, session: dict[str, Any]) -> None:
    """?dev=1 sidebar panel for active song canonical state."""
    ctx = canonical_active_song_context(session) or {}
    dirty = is_active_song_locally_dirty(session)
    written_on = ctx.get(CHART_IN_INSTRUMENT_KEY_KEY) if _written_key_is_set(ctx) else None
    subtype = ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or ""
    canonical_display_key = str(ctx.get("display_key") or "").strip()
    restored_display_key = str(session.get("display_key") or "").strip()
    home_key = str(ctx.get("custom_home_key") or "").strip()
    if is_custom_progression(session):
        effective_display_key = _resolve_custom_display_key_for_session(
            session,
            home_key or "C",
        )
    else:
        effective_display_key = restored_display_key or canonical_display_key
    st.sidebar.caption(
        f"**active_song_state:** dirty=`{dirty}` pick=`{ctx.get('pick_key', '')}` "
        f"key=`{canonical_display_key}` inst=`{ctx.get('instrument', '')}` "
        f"written=`{written_on}` subtype=`{subtype}`"
    )
    st.sidebar.caption(
        "**display_key trace:** "
        f"canonical=`{canonical_display_key}` "
        f"restored=`{restored_display_key}` "
        f"effective=`{effective_display_key}`"
    )
    reason = ctx.get("last_write_reason")
    if reason:
        st.sidebar.caption(f"**active_song last_write:** `{reason}`")
    skipped = session.get("_active_song_restore_skipped_reason")
    if skipped:
        st.sidebar.caption(f"**active_song restore skipped:** `{skipped}`")
    st.sidebar.caption(
        "**global controls:** "
        f"inst=`{session.get('instrument', '')}` "
        f"({session.get('instrument_change_source', '')}) · "
        f"lvl=`{session.get('level', '')}` "
        f"({session.get('level_change_source', '')}) · "
        f"focus=`{session.get('focus', '')}` "
        f"({session.get('focus_change_source', '')}) · "
        f"key=`{session.get('display_key', '')}` "
        f"({session.get('display_key_change_source', '')})"
    )
    overwrite = session.get("global_control_overwrite_source")
    if overwrite:
        st.sidebar.caption(f"**global_control_overwrite_source:** `{overwrite}`")
    trace = session.get("_global_control_widget_trace")
    if isinstance(trace, dict) and trace:
        st.sidebar.caption(
            "**global_control_widget_trace:** "
            f"name=`{trace.get('control_name', '')}` "
            f"widget=`{trace.get('widget_key', '')}` "
            f"attempt=`{trace.get('attempted_value', '')}` "
            f"after=`{trace.get('value_after_rerun', {})}` "
            f"canonical=`{trace.get('active_song_state', {})}` "
            f"overwrite=`{trace.get('overwrite_source') or ''}`"
        )

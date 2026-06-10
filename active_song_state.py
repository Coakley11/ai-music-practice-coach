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
    selected_transposing_type,
)
from songs.key_state import PENDING_DISPLAY_KEY
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

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
    "commit_active_song_state_from_session",
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
        **_transposing_fields_from_raw(src),
    }


def gather_active_song_context(session: dict[str, Any]) -> dict[str, Any]:
    """Read active song context from live session keys."""
    sel = session.get(SELECTED_SONG_STATE_KEY)
    selected = _normalize_selected_song(sel)
    pick_key = str(
        session.get(ACTIVE_CATALOG_PICK_KEY) or selected.get("pick_key") or ""
    ).strip()
    if pick_key and not selected.get("pick_key"):
        selected["pick_key"] = pick_key
    ctx = {
        "pick_key": pick_key,
        "display_key": str(session.get("display_key") or "").strip(),
        "instrument": str(session.get("instrument") or "").strip(),
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
        "selected_song": selected,
        CHART_IN_INSTRUMENT_KEY_KEY: chart_in_instrument_key(session),
    }
    anchor = str(session.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    instrument_name = str(ctx.get("instrument") or "").strip()
    if is_transposing_instrument(instrument_name):
        subtype = selected_transposing_type(session, instrument_name)
        if subtype:
            ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    return ctx


def canonical_active_song_context(session: dict[str, Any]) -> dict[str, Any] | None:
    meta = session.get(ACTIVE_SONG_STATE_KEY)
    if not isinstance(meta, dict):
        return None
    ctx = _normalize_context(meta)
    if not ctx.get("pick_key") and not ctx.get("instrument") and not ctx.get("display_key"):
        if not ctx.get("selected_song"):
            return None
    return ctx


def _merge_live_transposing_fields(
    session: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Fold live written-key + transposing subtype widgets into canonical context before save."""
    live = gather_active_song_context(session)
    ctx[CHART_IN_INSTRUMENT_KEY_KEY] = bool(live.get(CHART_IN_INSTRUMENT_KEY_KEY, False))
    anchor = str(live.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if anchor:
        ctx[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
    else:
        ctx.pop(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY, None)
    subtype = str(live.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
    if subtype:
        ctx[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    else:
        ctx.pop(SELECTED_TRANSPOSING_INSTRUMENT_KEY, None)
    return ctx


def _merge_transposing_from_blob_sources(
    ctx: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Prefer workspace/session transposing fields over stale canonical active_song_state."""
    sources: list[dict[str, Any]] = []
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("active_song"), dict):
        sources.append(ws["active_song"])
    session_blob = state.get("session")
    if isinstance(session_blob, dict):
        sources.append(session_blob)
    for src in sources:
        if _written_key_is_set(src):
            ctx.update(_written_key_fields_from_raw(src))
            break
    if not str(ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip():
        for src in sources:
            merged = _transposing_subtype_fields_from_raw(src)
            if merged:
                ctx.update(merged)
                break
    return ctx


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


def _apply_context_to_session_keys(
    session: dict[str, Any],
    ctx: dict[str, Any],
    *,
    mutate_display_key: bool = True,
    mutate_written_key: bool = True,
    mutate_transposing_subtype: bool = True,
) -> None:
    pick_key = str(ctx.get("pick_key") or "").strip()
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key
    display_key = str(ctx.get("display_key") or "").strip()
    if display_key:
        session[PENDING_DISPLAY_KEY] = display_key
        if mutate_display_key:
            session["display_key"] = display_key
    for key in ("instrument", "level", "focus"):
        val = str(ctx.get(key) or "").strip()
        if val:
            session[key] = val
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
) -> dict[str, Any]:
    """Single write path for active song context."""
    ctx = _normalize_context(context)
    session[ACTIVE_SONG_STATE_KEY] = {
        **ctx,
        "last_write_reason": reason or None,
    }
    mutate_wk = True if mutate_written_key is None else mutate_written_key
    mutate_subtype = True if mutate_transposing_subtype is None else mutate_transposing_subtype
    _apply_context_to_session_keys(
        session,
        ctx,
        mutate_display_key=True if mutate_display_key is None else mutate_display_key,
        mutate_written_key=mutate_wk,
        mutate_transposing_subtype=mutate_subtype,
    )
    if local_edit:
        mark_active_song_local_edit(session)
    session.pop(ACTIVE_SONG_PENDING_SYNC_KEY, None)
    return ctx


def prepare_active_song_context(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile session keys with canonical blob before widgets render."""
    if is_active_song_locally_dirty(session):
        ctx = gather_active_song_context(session)
        return write_canonical_active_song_state(
            session,
            ctx,
            reason="local_edit_preserve",
            local_edit=True,
        )

    canonical = canonical_active_song_context(session)
    if canonical is not None:
        ctx = write_canonical_active_song_state(
            session,
            canonical,
            reason="canonical_preserve",
        )
        _record_transposing_restore_trace(session, ctx, source="canonical_prepare")
        rehydrate_transposing_sidebar_from_canonical(session)
        return ctx

    gathered = gather_active_song_context(session)
    if gathered.get("pick_key") or gathered.get("instrument") or gathered.get("display_key"):
        ctx = write_canonical_active_song_state(
            session,
            gathered,
            reason="reconcile_on_load",
        )
        rehydrate_transposing_sidebar_from_canonical(session)
        return ctx
    return gathered


def commit_active_song_state_from_session(
    session: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    """Persist canonical blob from current session without marking a new local edit."""
    ctx = canonical_active_song_context(session) or gather_active_song_context(session)
    ctx = _merge_live_transposing_fields(session, dict(ctx))
    return write_canonical_active_song_state(
        session,
        ctx,
        reason=reason,
        local_edit=False,
        mutate_display_key=False,
        mutate_written_key=False,
        mutate_transposing_subtype=False,
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


def _active_song_context_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    meta = state.get(ACTIVE_SONG_STATE_KEY)
    if isinstance(meta, dict):
        ctx = _normalize_context(meta)
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
    write_canonical_active_song_state(session, ctx, reason="ami_return")
    clear_active_song_local_edit(session)


def render_active_song_state_debug(st: Any, session: dict[str, Any]) -> None:
    """?dev=1 sidebar panel for active song canonical state."""
    ctx = canonical_active_song_context(session) or {}
    dirty = is_active_song_locally_dirty(session)
    written_on = ctx.get(CHART_IN_INSTRUMENT_KEY_KEY) if _written_key_is_set(ctx) else None
    subtype = ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or ""
    st.sidebar.caption(
        f"**active_song_state:** dirty=`{dirty}` pick=`{ctx.get('pick_key', '')}` "
        f"key=`{ctx.get('display_key', '')}` inst=`{ctx.get('instrument', '')}` "
        f"written=`{written_on}` subtype=`{subtype}`"
    )
    reason = ctx.get("last_write_reason")
    if reason:
        st.sidebar.caption(f"**active_song last_write:** `{reason}`")
    skipped = session.get("_active_song_restore_skipped_reason")
    if skipped:
        st.sidebar.caption(f"**active_song restore skipped:** `{skipped}`")

"""Canonical Practice page filters — groove, section focus, notation prefs."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

PRACTICE_STATE_KEY = "practice_state"
PRACTICE_DIRTY_KEY = "practice_state_dirty"
PRACTICE_LOCAL_EDIT_TS_KEY = "practice_state_last_local_edit_ts"
PRACTICE_PENDING_SYNC_KEY = "_practice_filters_pending_sync"

PRACTICE_SCALAR_KEYS = (
    "practice_focus_section",
    "practice_groove_style",
    "practice_notation_lines",
    "practice_notation_difficulty",
    "last_practice_mode",
)

__all__ = (
    "PRACTICE_DIRTY_KEY",
    "PRACTICE_PENDING_SYNC_KEY",
    "PRACTICE_SCALAR_KEYS",
    "PRACTICE_STATE_KEY",
    "apply_cloud_practice_state_if_allowed",
    "apply_practice_source_state_from_ami",
    "canonical_practice_filters",
    "clear_practice_local_edit",
    "commit_practice_state_from_session",
    "flush_practice_edits",
    "gather_practice_filters",
    "is_practice_locally_dirty",
    "mark_practice_local_edit",
    "mark_practice_pending_sync",
    "prepare_practice_page",
    "render_practice_state_debug",
    "write_canonical_practice_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_practice_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(PRACTICE_DIRTY_KEY))


def mark_practice_local_edit(session: dict[str, Any]) -> None:
    session[PRACTICE_DIRTY_KEY] = True
    session[PRACTICE_LOCAL_EDIT_TS_KEY] = _utc_now_iso()


def clear_practice_local_edit(session: dict[str, Any]) -> None:
    session.pop(PRACTICE_DIRTY_KEY, None)
    session.pop(PRACTICE_LOCAL_EDIT_TS_KEY, None)
    session.pop(PRACTICE_PENDING_SYNC_KEY, None)


def mark_practice_pending_sync(session: dict[str, Any]) -> None:
    session[PRACTICE_PENDING_SYNC_KEY] = True


def _normalize_int(val: Any, default: int = 2) -> int:
    try:
        n = int(val)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _normalize_filters(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    return {
        "practice_focus_section": str(src.get("practice_focus_section") or "").strip(),
        "practice_groove_style": str(src.get("practice_groove_style") or "").strip(),
        "practice_notation_lines": _normalize_int(src.get("practice_notation_lines"), 2),
        "practice_notation_difficulty": str(src.get("practice_notation_difficulty") or "medium").strip()
        or "medium",
        "last_practice_mode": str(src.get("last_practice_mode") or "").strip(),
    }


def gather_practice_filters(session: dict[str, Any]) -> dict[str, Any]:
    """Read Practice page filters from live session keys."""
    return _normalize_filters(
        {
            "practice_focus_section": session.get("practice_focus_section"),
            "practice_groove_style": session.get("practice_groove_style"),
            "practice_notation_lines": session.get("practice_notation_lines"),
            "practice_notation_difficulty": session.get("practice_notation_difficulty"),
            "last_practice_mode": session.get("last_practice_mode"),
        }
    )


def canonical_practice_filters(session: dict[str, Any]) -> dict[str, Any] | None:
    meta = session.get(PRACTICE_STATE_KEY)
    if not isinstance(meta, dict):
        return None
    filters = _normalize_filters(meta)
    if not any(filters.values()):
        return None
    return filters


def _apply_filters_to_session_keys(session: dict[str, Any], filters: dict[str, Any]) -> None:
    section = str(filters.get("practice_focus_section") or "").strip()
    if section:
        session["practice_focus_section"] = section
    groove = str(filters.get("practice_groove_style") or "").strip()
    if groove:
        session["practice_groove_style"] = groove
    session["practice_notation_lines"] = _normalize_int(filters.get("practice_notation_lines"), 2)
    difficulty = str(filters.get("practice_notation_difficulty") or "").strip()
    if difficulty:
        session["practice_notation_difficulty"] = difficulty
    mode = str(filters.get("last_practice_mode") or "").strip()
    if mode:
        session["last_practice_mode"] = mode


def write_canonical_practice_state(
    session: dict[str, Any],
    filters: dict[str, Any],
    *,
    reason: str = "",
    local_edit: bool = False,
) -> dict[str, Any]:
    """Single write path for Practice page filters."""
    normalized = _normalize_filters(filters)
    session[PRACTICE_STATE_KEY] = {
        **normalized,
        "last_write_reason": reason or None,
    }
    _apply_filters_to_session_keys(session, normalized)
    if local_edit:
        mark_practice_local_edit(session)
    session.pop(PRACTICE_PENDING_SYNC_KEY, None)
    return normalized


def prepare_practice_page(session: dict[str, Any]) -> dict[str, Any]:
    """Reconcile Practice widgets with canonical blob before page widgets render."""
    if is_practice_locally_dirty(session):
        gathered = gather_practice_filters(session)
        return write_canonical_practice_state(
            session,
            gathered,
            reason="local_edit_preserve",
            local_edit=True,
        )

    canonical = canonical_practice_filters(session)
    if canonical is not None:
        return write_canonical_practice_state(session, canonical, reason="canonical_preserve")

    gathered = gather_practice_filters(session)
    if any(str(gathered.get(key) or "").strip() for key in PRACTICE_SCALAR_KEYS if key != "practice_notation_lines"):
        return write_canonical_practice_state(session, gathered, reason="reconcile_on_load")
    if gathered.get("practice_notation_lines", 0) > 0:
        return write_canonical_practice_state(session, gathered, reason="reconcile_on_load")
    return gathered


def commit_practice_state_from_session(session: dict[str, Any], *, reason: str = "autosave") -> dict[str, Any]:
    filters = gather_practice_filters(session)
    return write_canonical_practice_state(session, filters, reason=reason, local_edit=False)


def flush_practice_edits(session: dict[str, Any], *, reason: str = "practice_edit") -> dict[str, Any]:
    filters = gather_practice_filters(session)
    return write_canonical_practice_state(session, filters, reason=reason, local_edit=True)


def _practice_filters_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    meta = state.get(PRACTICE_STATE_KEY)
    if isinstance(meta, dict):
        filters = _normalize_filters(meta)
        if any(filters.values()):
            return filters
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get("practice_filters"), dict):
        filters = _normalize_filters(ws["practice_filters"])
        if any(filters.values()):
            return filters
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    if isinstance(session_extra, dict):
        filters = _normalize_filters(
            {key: session_extra.get(key) for key in PRACTICE_SCALAR_KEYS if key in session_extra}
        )
        if any(filters.values()):
            return filters
    return None


def apply_cloud_practice_state_if_allowed(session: dict[str, Any], state: dict[str, Any]) -> bool:
    """Apply cloud/disk Practice filters when this device has no local Practice edits."""
    if is_practice_locally_dirty(session):
        session["_practice_restore_skipped_reason"] = "local_dirty"
        return False
    filters = _practice_filters_from_blob(state)
    if not filters:
        return False
    write_canonical_practice_state(session, filters, reason="cloud_restore")
    clear_practice_local_edit(session)
    return True


def apply_practice_source_state_from_ami(
    session: dict[str, Any],
    source_state: dict[str, Any],
) -> None:
    """Restore Practice filters from Music Coach / AMI return payload."""
    if not isinstance(source_state, dict):
        return
    filters = gather_practice_filters(session)
    widgets = source_state.get("widget_params")
    if isinstance(widgets, dict):
        for key in PRACTICE_SCALAR_KEYS:
            if key in widgets and widgets[key] not in (None, ""):
                if key == "practice_notation_lines":
                    filters[key] = _normalize_int(widgets[key], filters.get("practice_notation_lines", 2))
                else:
                    filters[key] = str(widgets[key]).strip()
    write_canonical_practice_state(session, filters, reason="ami_return")
    clear_practice_local_edit(session)


def render_practice_state_debug(st: Any, session: dict[str, Any]) -> None:
    """?dev=1 sidebar panel for Practice canonical state."""
    filters = canonical_practice_filters(session) or {}
    dirty = is_practice_locally_dirty(session)
    st.sidebar.caption(
        f"**practice_state:** dirty=`{dirty}` section=`{filters.get('practice_focus_section', '')}` "
        f"groove=`{filters.get('practice_groove_style', '')}`"
    )
    reason = filters.get("last_write_reason")
    if reason:
        st.sidebar.caption(f"**practice last_write:** `{reason}`")
    skipped = session.get("_practice_restore_skipped_reason")
    if skipped:
        st.sidebar.caption(f"**practice restore skipped:** `{skipped}`")

"""Canonical studio page navigation state — ``studio_page`` ownership."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from studio_nav_history import STUDIO_PAGE_IDS

STUDIO_NAV_STATE_KEY = "studio_nav_state"
STUDIO_NAV_DIRTY_KEY = "studio_nav_state_dirty"
STUDIO_NAV_LOCAL_EDIT_TS_KEY = "studio_nav_state_last_local_edit_ts"

__all__ = (
    "STUDIO_NAV_DIRTY_KEY",
    "STUDIO_NAV_STATE_KEY",
    "apply_cloud_studio_nav_state_if_allowed",
    "apply_studio_nav_source_state_from_ami",
    "canonical_studio_page",
    "clear_studio_nav_local_edit",
    "commit_studio_nav_from_session",
    "is_studio_nav_locally_dirty",
    "mark_studio_nav_local_edit",
    "prepare_studio_nav",
    "render_studio_nav_state_debug",
    "resolve_studio_page_for_restore",
    "write_canonical_studio_nav_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_studio_nav_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(STUDIO_NAV_DIRTY_KEY))


def mark_studio_nav_local_edit(session: dict[str, Any]) -> None:
    session[STUDIO_NAV_DIRTY_KEY] = True
    session[STUDIO_NAV_LOCAL_EDIT_TS_KEY] = _utc_now_iso()
    session["_suite_page_user_nav"] = True


def clear_studio_nav_local_edit(session: dict[str, Any]) -> None:
    session.pop(STUDIO_NAV_DIRTY_KEY, None)
    session.pop(STUDIO_NAV_LOCAL_EDIT_TS_KEY, None)


def _normalize_page(page: Any) -> str:
    val = str(page or "").strip()
    return val if val in STUDIO_PAGE_IDS else ""


def canonical_studio_page(session: dict[str, Any]) -> str | None:
    meta = session.get(STUDIO_NAV_STATE_KEY)
    if isinstance(meta, dict):
        page = _normalize_page(meta.get("studio_page"))
        if page:
            return page
    return None


def write_canonical_studio_nav_state(
    session: dict[str, Any],
    page: str,
    *,
    reason: str = "",
    local_edit: bool = False,
) -> str:
    """Single write path for ``studio_page``."""
    normalized = _normalize_page(page) or _normalize_page(session.get("studio_page")) or "practice"
    session[STUDIO_NAV_STATE_KEY] = {
        "studio_page": normalized,
        "page": normalized,
        "last_write_reason": reason or None,
    }
    session["studio_page"] = normalized
    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(session)
    except Exception:
        pass
    if local_edit:
        mark_studio_nav_local_edit(session)
    return normalized


def prepare_studio_nav(session: dict[str, Any]) -> str:
    """Reconcile ``studio_page`` with canonical nav state before widgets render."""
    if is_studio_nav_locally_dirty(session):
        page = _normalize_page(session.get("studio_page")) or "practice"
        return write_canonical_studio_nav_state(
            session,
            page,
            reason="local_nav_preserve",
            local_edit=True,
        )

    canonical = canonical_studio_page(session)
    live_raw = session.get("studio_page")
    live = _normalize_page(live_raw) if live_raw is not None else ""
    if canonical and live and canonical != live:
        # Quick-nav set ``studio_page`` on the prior rerun; stale canonical still says picker/songs.
        return write_canonical_studio_nav_state(
            session,
            live,
            reason="session_page_wins",
            local_edit=True,
        )
    if canonical:
        return write_canonical_studio_nav_state(session, canonical, reason="canonical_preserve")

    page = _normalize_page(live_raw) or "practice"
    return write_canonical_studio_nav_state(session, page, reason="reconcile_on_load")


def commit_studio_nav_from_session(session: dict[str, Any], *, reason: str = "autosave") -> str:
    page = _normalize_page(session.get("studio_page")) or "practice"
    return write_canonical_studio_nav_state(session, page, reason=reason, local_edit=False)


def _studio_page_from_blob(state: dict[str, Any]) -> str:
    if not isinstance(state, dict):
        return ""
    ws = state.get("music_workspace_state")
    if isinstance(ws, dict):
        page = _normalize_page(ws.get("studio_page") or ws.get("page"))
        if page:
            return page
    meta = state.get(STUDIO_NAV_STATE_KEY)
    if isinstance(meta, dict):
        page = _normalize_page(meta.get("studio_page"))
        if page:
            return page
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    for src in (core, session_extra, state):
        if isinstance(src, dict):
            page = _normalize_page(src.get("studio_page") or src.get("page"))
            if page:
                return page
    return ""


def resolve_studio_page_for_restore(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    pre_restore_page: str = "",
    user_owns_page: bool = False,
    st: Any | None = None,
) -> tuple[str, str]:
    """Pick authoritative studio page after cloud restore (respects manual nav + AMI return)."""
    blob_page = _studio_page_from_blob(blob)
    pre = _normalize_page(pre_restore_page)
    try:
        from applied_math_return_insight import ami_return_navigation_active

        if (
            st is not None
            and ami_return_navigation_active(st, "music")
            and pre
            and (not blob_page or pre != blob_page)
        ):
            return pre, "ami_return_preserved"
    except ImportError:
        pass
    if user_owns_page and pre and blob_page and pre != blob_page:
        return pre, "user_page_preserved"
    if pre and not blob_page:
        return pre, "session_page_preserved"
    if blob_page:
        return blob_page, "workspace_blob"
    if pre:
        return pre, "session_page"
    return "practice", "default"


def apply_cloud_studio_nav_state_if_allowed(
    session: dict[str, Any],
    state: dict[str, Any],
    *,
    pre_restore_page: str = "",
    user_owns_page: bool = False,
) -> bool:
    """Apply cloud studio_page when manual nav has not claimed ownership."""
    if is_studio_nav_locally_dirty(session) or user_owns_page:
        session["_studio_nav_restore_skipped_reason"] = "local_dirty" if is_studio_nav_locally_dirty(session) else "user_nav"
        return False
    page, _source = resolve_studio_page_for_restore(
        session,
        state,
        pre_restore_page=pre_restore_page,
        user_owns_page=False,
    )
    if not page:
        return False
    write_canonical_studio_nav_state(session, page, reason="cloud_restore")
    clear_studio_nav_local_edit(session)
    return True


def apply_studio_nav_source_state_from_ami(
    session: dict[str, Any],
    source_state: dict[str, Any],
) -> str:
    """Restore studio page from AMI return (maps coach pages to studio ids)."""
    if not isinstance(source_state, dict):
        return str(session.get("studio_page") or "practice")
    coach_page = str(source_state.get("source_page") or "").strip()
    widgets = source_state.get("widget_params")
    studio_target = ""
    if isinstance(widgets, dict):
        studio_target = _normalize_page(widgets.get("studio_page"))
    if not studio_target:
        try:
            from music_coach_context import _coach_page_to_studio_page

            studio_target = _normalize_page(_coach_page_to_studio_page(coach_page))
        except Exception:
            studio_target = _normalize_page(coach_page)
    if not studio_target:
        studio_target = "practice"
    write_canonical_studio_nav_state(session, studio_target, reason="ami_return")
    clear_studio_nav_local_edit(session)
    return studio_target


def render_studio_nav_state_debug(st: Any, session: dict[str, Any]) -> None:
    meta = session.get(STUDIO_NAV_STATE_KEY) if isinstance(session.get(STUDIO_NAV_STATE_KEY), dict) else {}
    dirty = is_studio_nav_locally_dirty(session)
    st.sidebar.caption(
        f"**studio_nav_state:** dirty=`{dirty}` page=`{session.get('studio_page', '')}` "
        f"canonical=`{meta.get('studio_page', '')}`"
    )
    if meta.get("last_write_reason"):
        st.sidebar.caption(f"**studio_nav last_write:** `{meta.get('last_write_reason')}`")
    skipped = session.get("_studio_nav_restore_skipped_reason")
    if skipped:
        st.sidebar.caption(f"**studio_nav restore skipped:** `{skipped}`")

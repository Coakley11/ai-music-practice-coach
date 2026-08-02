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
    "bootstrap_studio_page_session",
    "write_canonical_studio_nav_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_studio_nav_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(STUDIO_NAV_DIRTY_KEY))


def mark_studio_nav_local_edit(session: dict[str, Any]) -> None:
    try:
        from music_workspace_restore_mode import should_record_user_local_dirty

        if not should_record_user_local_dirty(session):
            return
    except ImportError:
        pass
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
    old_page = session.get("studio_page")
    old_nav = session.get(STUDIO_NAV_STATE_KEY)
    old_nav_page = old_nav.get("studio_page") if isinstance(old_nav, dict) else None
    try:
        from music_phase1_write_journal import record_phase1_page_write

        record_phase1_page_write(
            session,
            key="studio_page",
            old_page=old_page,
            new_page=normalized,
            module="studio_nav_state",
            function="write_canonical_studio_nav_state",
            reason=reason or "",
            origin=reason or "canonical",
        )
        record_phase1_page_write(
            session,
            key="studio_nav_state.studio_page",
            old_page=old_nav_page,
            new_page=normalized,
            module="studio_nav_state",
            function="write_canonical_studio_nav_state",
            reason=reason or "",
            origin=reason or "canonical",
        )
    except ImportError:
        pass
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
    try:
        from music_page_save_pipeline_trace import prepare_studio_nav_impl_marker, record_pipeline_event

        record_pipeline_event(
            session,
            function="prepare_studio_nav",
            phase="entry",
            extra={"prepare_studio_nav_impl_marker": prepare_studio_nav_impl_marker},
        )
    except ImportError:
        pass

    def _finish(
        branch: str,
        page: str,
        *,
        reason: str,
        local_edit: bool = False,
        allow_detail: dict[str, Any] | None = None,
    ) -> str:
        try:
            from music_page_save_pipeline_trace import (
                prepare_studio_nav_impl_marker,
                record_pipeline_event,
            )

            extra: dict[str, Any] = {
                "prepare_studio_nav_impl_marker": prepare_studio_nav_impl_marker,
                "write_reason": reason,
            }
            if allow_detail:
                extra["branch_allow_detail"] = allow_detail
            record_pipeline_event(
                session,
                function="prepare_studio_nav",
                phase="exit",
                branch=branch,
                selected_target=page,
                extra=extra,
            )
        except ImportError:
            pass
        return write_canonical_studio_nav_state(session, page, reason=reason, local_edit=local_edit)

    try:
        from music_studio_page_diagnostics import record_studio_page_diag

        record_studio_page_diag(
            session,
            canonical_page_before_widget=canonical_studio_page(session),
            canonical_studio_page_before_widgets=canonical_studio_page(session),
            navigation_widget_value_before_render=str(session.get("studio_page") or "").strip() or None,
            page_restore_overwrite_function="studio_nav_state.prepare_studio_nav",
        )
    except ImportError:
        pass

    user_run = _normalize_page(session.get("_music_user_navigated_page_this_run"))
    if user_run:
        return _finish("user_nav_this_run", user_run, reason="user_nav_this_run", local_edit=True)
    try:
        from music_startup_save_suppression import get_page_change_origin

        if get_page_change_origin(session) == "user_navigation":
            live_nav = _normalize_page(session.get("studio_page"))
            if live_nav:
                return _finish(
                    "user_navigation_preserve",
                    live_nav,
                    reason="user_navigation_preserve",
                    local_edit=True,
                )
    except ImportError:
        pass

    if is_studio_nav_locally_dirty(session):
        page = _normalize_page(session.get("studio_page")) or "practice"
        try:
            from music_studio_page_diagnostics import record_studio_page_diag

            record_studio_page_diag(session, final_rendered_page=page)
        except ImportError:
            pass
        return _finish("local_nav_preserve", page, reason="local_nav_preserve", local_edit=True)

    try:
        from music_restore_phase import studio_page_restore_projection_complete

        if studio_page_restore_projection_complete(session) and not session.get(
            "_music_user_navigated_page_this_run"
        ):
            canonical = canonical_studio_page(session)
            if canonical:
                return _finish(
                    "canonical_post_restore",
                    canonical,
                    reason="canonical_post_restore",
                    allow_detail={
                        "user_run_marker": session.get("_music_user_navigated_page_this_run"),
                        "restore_projection_complete": True,
                    },
                )
    except ImportError:
        pass

    canonical = canonical_studio_page(session)
    live_raw = session.get("studio_page")
    live = _normalize_page(live_raw) if live_raw is not None else ""
    if canonical and live and canonical != live:
        user_nav = bool(session.get("_suite_page_user_nav")) or is_studio_nav_locally_dirty(session)
        restore_source = str(session.get("_suite_page_overwrite_source") or "").strip()
        if user_nav:
            return _finish(
                "session_page_wins",
                live,
                reason="session_page_wins",
                local_edit=True,
                allow_detail={"restore_source": restore_source, "canonical": canonical, "live": live},
            )
        if restore_source in ("workspace_blob", "cloud_restore", "session_page", "session_page_preserved"):
            if session.get("_music_user_navigated_page_this_run") or user_nav:
                return _finish(
                    "user_nav_over_stale_blob",
                    live,
                    reason="user_nav_over_stale_blob",
                    local_edit=True,
                    allow_detail={"restore_source": restore_source},
                )
            return _finish(
                "canonical_after_restore",
                canonical,
                reason="canonical_after_restore",
                allow_detail={
                    "restore_source": restore_source,
                    "why_blob_applied": "no user_run marker and not user_nav",
                    "canonical": canonical,
                    "live_session": live,
                    "user_run": session.get("_music_user_navigated_page_this_run"),
                    "_suite_page_user_nav": bool(session.get("_suite_page_user_nav")),
                },
            )
        try:
            from music_startup_save_suppression import get_page_change_origin

            if get_page_change_origin(session) == "cloud_restore":
                return _finish(
                    "canonical_after_cloud_restore",
                    canonical,
                    reason="canonical_after_cloud_restore",
                )
        except ImportError:
            pass
        if not user_nav:
            return _finish(
                "canonical_preserve_over_stale_live",
                canonical,
                reason="canonical_preserve_over_stale_live",
                allow_detail={"live": live, "canonical": canonical},
            )
    if canonical:
        return _finish("canonical_preserve", canonical, reason="canonical_preserve")

    page = _normalize_page(live_raw)
    if page:
        return _finish("reconcile_on_load", page, reason="reconcile_on_load")

    try:
        from music_workspace_hydration import workspace_empty_confirmed

        payload = session.get("_suite_last_cloud_fetch_payload")
        if isinstance(payload, dict):
            blob_page = _studio_page_from_blob(payload)
            if blob_page:
                return _finish(
                    "blob_before_default",
                    blob_page,
                    reason="blob_before_default",
                    allow_detail={"blob_page": blob_page},
                )
        hydrated = str(session.get("_music_hydrated_studio_page") or "").strip()
        if _normalize_page(hydrated):
            return _finish(
                "hydrated_page_before_default",
                hydrated,
                reason="hydrated_page_before_default",
                allow_detail={"hydrated": hydrated},
            )
        if not workspace_empty_confirmed(session):
            canonical = canonical_studio_page(session)
            if canonical:
                return _finish("canonical_before_default", canonical, reason="canonical_before_default")
            try:
                from music_page_save_pipeline_trace import record_pipeline_event

                record_pipeline_event(
                    session,
                    function="prepare_studio_nav",
                    phase="exit",
                    branch="return_live_without_write",
                    selected_target=str(session.get("studio_page") or ""),
                )
            except ImportError:
                pass
            return str(session.get("studio_page") or "")
    except ImportError:
        pass

    return _finish("empty_workspace_default", "practice", reason="empty_workspace_default")


def commit_studio_nav_from_session(session: dict[str, Any], *, reason: str = "autosave") -> str:
    page = _normalize_page(session.get("studio_page")) or "practice"
    try:
        from music_studio_page_diagnostics import record_studio_page_diag

        record_studio_page_diag(session, final_rendered_page=page)
    except ImportError:
        pass
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
    if session.get("_studio_nav_from_history") and pre:
        return pre, "history_nav_preserved"
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


def bootstrap_studio_page_session(session: dict[str, Any], *, default: str = "practice") -> str:
    """
    Hydration-aware studio page for early script bootstrap.

    Do not pin Practice while cloud workspace hydration is still pending.
    """
    try:
        from music_workspace_hydration import can_finalize_music_restore, workspace_empty_confirmed

        if can_finalize_music_restore(session):
            return prepare_studio_nav(session) or str(session.get("studio_page") or default)
    except ImportError:
        return str(session.setdefault("studio_page", default))

    page = _normalize_page(session.get("studio_page"))
    if page:
        session["studio_page"] = page
        return page

    canonical = canonical_studio_page(session)
    if canonical:
        session["studio_page"] = canonical
        return canonical

    hydrated = str(session.get("_music_hydrated_studio_page") or "").strip()
    if _normalize_page(hydrated):
        session["studio_page"] = hydrated
        return hydrated

    payload = session.get("_suite_last_cloud_fetch_payload")
    if isinstance(payload, dict):
        blob_page = _studio_page_from_blob(payload)
        if blob_page:
            session["studio_page"] = blob_page
            return blob_page

    try:
        from music_workspace_hydration import workspace_empty_confirmed

        if workspace_empty_confirmed(session):
            session.setdefault("studio_page", default)
            return str(session.get("studio_page") or default)
    except ImportError:
        pass

    return str(session.get("studio_page") or "")


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

"""Disk persistence for the Music Practice Coach app."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    SUITE_LOCAL_STATE_RESTORED_KEY,
    apply_saved_music_context,
    build_music_local_state,
    restore_saved_app_state_once,
)
from suite_user_persistence import (
    autosave_if_changed,
    clear_workspace_autosave_block,
    finalize_suite_reset,
    force_autosave,
    load_user_state,
    reset_user_state,
    restore_once,
    save_user_state,
    sync_workspace_protocol,
)

APP_ID = "music"
WORKSPACE_SCHEMA_VERSION = 1

# JSON-serializable session keys (never large blobs / widget-only keys).
_PERSIST_KEYS: tuple[str, ...] = (
    "studio_page",
    "chart_library_mode",
    "song_picker_chart_status",
    "song_search_text",
    "song_search_scope",
    "song_picker_level_filter",
    "workspace_genre_filter",
    "backing_track_scope",
    "backing_track_loops",
    "backing_track_single_section",
    "backing_groove_style",
    "backing_lead_sheet_open",
    "backing_track_bpm",
    "karaoke_countdown_enabled",
    "karaoke_auto_advance",
    "active_music_source",
    "chart_edit_mode",
    "picker_editor_tab",
    "picker_song_editor_open",
    "last_practice_mode",
    "improv_song_source",
    "creative_lab_analysis_mode",
    "improv_intelligence_tab",
    "song_picker_favorites_only",
    "cpl_active_progression",
    "cpl_saved_progressions",
    "cpl_builder_version",
    "cpl_edit_section",
    "cpl_finished",
    "_cpl_editing_display_key",
    "cpl_last_display_key",
)

_LIST_KEYS = (
    "workspace_genre_filters",
    "backing_track_multi_sections",
    "karaoke_queue",
    "catalog_favorite_pick_keys",
)

_INSIGHT_KEYS = (
    "_ami_pending_insight",
    "_ami_return_page",
    "_ami_return_context",
    "_ami_dismissed_insight_ids",
    "_ami_dismissed_insight_at",
)

# Phase C canonical modules (grow as migration proceeds).
_WORKSPACE_KEYS: tuple[str, ...] = (
    "active_song_state",
    "studio_nav_state",
    "practice_state",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_device_id(st: Any) -> str:
    try:
        from pathlib import Path

        path = Path("data") / "music_device_id.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip() or "unknown"
        import uuid

        device_id = str(uuid.uuid4())
        path.write_text(device_id, encoding="utf-8")
        return device_id
    except Exception:
        return "unknown"


def _normalize_studio_page_for_save(page: Any) -> str:
    val = str(page or "").strip()
    if not val:
        return ""
    try:
        from studio_nav_history import STUDIO_PAGE_IDS

        return val if val in STUDIO_PAGE_IDS else ""
    except ImportError:
        return val


def _studio_nav_page_from_session(ss: dict[str, Any]) -> str:
    nav = ss.get("studio_nav_state")
    if isinstance(nav, dict):
        return _normalize_studio_page_for_save(nav.get("studio_page") or nav.get("page"))
    return ""


def _page_change_save_ready(session: dict[str, Any], target_page: str) -> bool:
    """True when live session/nav/ownership/workspace all match the nav target."""
    target = _normalize_studio_page_for_save(target_page)
    if not target:
        return False
    if _normalize_studio_page_for_save(session.get("studio_page")) != target:
        return False
    if _studio_nav_page_from_session(session) != target:
        return False
    if not bool(session.get("_suite_page_user_nav")):
        return False
    ws = session.get("music_workspace_state")
    if isinstance(ws, dict):
        ws_page = _normalize_studio_page_for_save(ws.get("studio_page"))
        if ws_page and ws_page != target:
            return False
    return True


def prepare_page_change_save_state(
    session: dict[str, Any],
    target_page: str,
    *,
    st: Any | None = None,
) -> str:
    """Stamp live nav/workspace/ownership before page_change cloud save."""
    page = _normalize_studio_page_for_save(target_page) or _normalize_studio_page_for_save(
        session.get("studio_page")
    )
    if not page:
        return ""
    session["studio_page"] = page
    try:
        from studio_nav_state import write_canonical_studio_nav_state

        write_canonical_studio_nav_state(session, page, reason="page_change", local_edit=True)
    except ImportError:
        session["studio_nav_state"] = {
            "studio_page": page,
            "page": page,
            "last_write_reason": "page_change",
        }
        session["_suite_page_user_nav"] = True

    session["_suite_page_user_nav"] = True
    session["active_page_source"] = "user_sidebar"
    session["requested_page"] = page
    try:
        from suite_user_persistence import SESSION_USER_OWNED_PAGE_KEY

        session[SESSION_USER_OWNED_PAGE_KEY] = page
    except ImportError:
        session["_suite_user_owned_page"] = page

    if st is not None:
        try:
            from suite_user_persistence import claim_user_page_ownership

            claim_user_page_ownership(st, APP_ID, page)
        except Exception:
            pass

    ws = session.get("music_workspace_state")
    if isinstance(ws, dict):
        ws = copy.deepcopy(ws)
    else:
        ws = {}
    ws["studio_page"] = page
    try:
        from music_coach_context import resolve_coach_source_page

        ws["page"] = resolve_coach_source_page({**session, **ws})
    except Exception:
        ws["page"] = page
    session["music_workspace_state"] = ws
    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(session)
    except Exception:
        pass
    return page


def maybe_flush_deferred_page_change_save(st: Any) -> bool:
    """Run a deferred page_change save after canonical nav catches up (next rerun)."""
    ss = st.session_state
    deferred = _normalize_studio_page_for_save(ss.get("_suite_deferred_page_change_save"))
    if not deferred:
        return False
    prepare_page_change_save_state(ss, deferred, st=st)
    if not _page_change_save_ready(ss, deferred):
        return False
    ss.pop("_suite_deferred_page_change_save", None)
    ss["_suite_page_change_save_page"] = deferred
    build_ss = getattr(st, "session_state", ss)
    if build_ss is not ss:
        build_ss["_suite_page_change_save_page"] = deferred
    try:
        ok = force_save_music_state(st, reason="page_change")
    finally:
        ss.pop("_suite_page_change_save_page", None)
        if build_ss is not ss:
            build_ss.pop("_suite_page_change_save_page", None)
    if ok:
        try:
            from suite_user_persistence import _release_user_page_ownership_after_save

            _release_user_page_ownership_after_save(st, deferred)
        except ImportError:
            pass
        ss["_suite_last_persisted_page"] = deferred
    return ok


def _resolve_live_studio_page_for_save(ss: dict[str, Any], *, save_reason: str) -> tuple[str, str]:
    """Authoritative studio page for save payload (page_change must not use restored blob)."""
    if save_reason == "page_change":
        hinted = _normalize_studio_page_for_save(ss.get("_suite_page_change_save_page"))
        live = _normalize_studio_page_for_save(ss.get("studio_page"))
        nav = _studio_nav_page_from_session(ss)
        if hinted and live and hinted != live:
            if nav == live:
                return live, "session_state.studio_page"
            if nav == hinted:
                return hinted, "_suite_page_change_save_page"
            if bool(ss.get("_suite_page_user_nav")) and live:
                return live, "session_state.studio_page"
            return hinted, "_suite_page_change_save_page"
        if hinted:
            return hinted, "_suite_page_change_save_page"
        if live:
            return live, "session_state.studio_page"
        if nav:
            return nav, "studio_nav_state"
        return "", "missing"
    live = _normalize_studio_page_for_save(ss.get("studio_page"))
    return live, "session_state.studio_page" if live else "missing"


def _stamp_live_studio_page_into_save_payload(
    state: dict[str, Any],
    page: str,
    *,
    source: str = "session_state.studio_page",
    coach_page: str = "",
) -> dict[str, str]:
    """Force raw ``studio_page`` id into every cross-device sync field (not coach aliases)."""
    normalized = str(page or "").strip()
    trace: dict[str, str] = {
        "save_payload_source": source,
        "save_payload_core_page": "",
        "save_payload_session_page": "",
        "save_payload_workspace_page": "",
        "save_payload_studio_nav_page": "",
    }
    if not normalized:
        return trace
    core = state.get("core")
    if isinstance(core, dict):
        core["studio_page"] = normalized
        core["page"] = normalized
        trace["save_payload_core_page"] = normalized
    session_extra = state.get("session")
    if isinstance(session_extra, dict):
        session_extra["studio_page"] = normalized
        trace["save_payload_session_page"] = normalized
    meta = state.get("music_workspace_state")
    if isinstance(meta, dict):
        meta["studio_page"] = normalized
        meta["page"] = coach_page or normalized
        trace["save_payload_workspace_page"] = normalized
    nav_meta = state.get("studio_nav_state")
    if isinstance(nav_meta, dict):
        nav_meta["studio_page"] = normalized
        nav_meta["page"] = normalized
        trace["save_payload_studio_nav_page"] = normalized
    else:
        state["studio_nav_state"] = {
            "studio_page": normalized,
            "page": normalized,
            "last_write_reason": "page_change_save_stamp",
        }
        trace["save_payload_studio_nav_page"] = normalized
    state["studio_page"] = normalized
    return trace


def _sync_studio_page_into_music_blob(
    st: Any,
    state: dict[str, Any],
    *,
    save_reason: str = "autosave",
) -> dict[str, str]:
    if not hasattr(st, "session_state"):
        return {}
    ss = st.session_state
    page, source = _resolve_live_studio_page_for_save(ss, save_reason=save_reason)
    coach_page = ""
    if page and save_reason != "page_change":
        try:
            from music_coach_context import resolve_coach_source_page

            merged = {**ss}
            core = state.get("core")
            session_extra = state.get("session")
            if isinstance(core, dict):
                merged.update(core)
            if isinstance(session_extra, dict):
                merged.update(session_extra)
            coach_page = resolve_coach_source_page(merged)
        except Exception:
            coach_page = page
    elif page:
        coach_page = page
    return _stamp_live_studio_page_into_save_payload(
        state,
        page,
        source=source,
        coach_page=coach_page,
    )



def _build_workspace_envelope(st: Any, state: dict[str, Any], *, save_reason: str) -> dict[str, Any]:
    core = state.get("core") if isinstance(state.get("core"), dict) else {}
    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}
    coach_page = ""
    try:
        from music_coach_context import resolve_coach_source_page, sync_music_coach_workspace_page

        merged = {**core, **session_extra}
        if hasattr(st, "session_state"):
            merged = {**dict(st.session_state), **merged}
        sync_music_coach_workspace_page(merged)
        coach_page = resolve_coach_source_page(merged)
    except Exception:
        coach_page = str((core or {}).get("studio_page") or session_extra.get("studio_page") or "")
    active_song_meta = state.get("active_song_state") if isinstance(state.get("active_song_state"), dict) else {}
    studio_nav_meta = state.get("studio_nav_state") if isinstance(state.get("studio_nav_state"), dict) else {}
    practice_meta = state.get("practice_state") if isinstance(state.get("practice_state"), dict) else {}
    live_studio = ""
    if hasattr(st, "session_state"):
        ss_ref = st.session_state
        live_studio, _ = _resolve_live_studio_page_for_save(ss_ref, save_reason=save_reason)
    if save_reason == "page_change" and live_studio:
        coach_page = live_studio
    if save_reason == "page_change" and live_studio:
        studio_page = live_studio
    else:
        studio_page = (
            live_studio
            or studio_nav_meta.get("studio_page")
            or (core or {}).get("studio_page")
            or session_extra.get("studio_page")
        )

    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
        "device_id": _get_device_id(st),
        "save_reason": save_reason or "autosave",
        "page": coach_page or studio_page,
        "studio_page": studio_page,
        "pick_key": active_song_meta.get("pick_key") or (core or {}).get("pick_key"),
        "instrument": active_song_meta.get("instrument") or (core or {}).get("instrument"),
        "display_key": active_song_meta.get("display_key") or (core or {}).get("display_key"),
        "active_song": {
            "pick_key": active_song_meta.get("pick_key") or (core or {}).get("pick_key"),
            "display_key": active_song_meta.get("display_key") or (core or {}).get("display_key"),
            "instrument": active_song_meta.get("instrument") or (core or {}).get("instrument"),
            "level": active_song_meta.get("level") or (core or {}).get("level"),
            "focus": active_song_meta.get("focus") or (core or {}).get("focus"),
            "practice_focus_section": active_song_meta.get("practice_focus_section")
            or practice_meta.get("practice_focus_section")
            or (core or {}).get("practice_focus_section"),
        },
        "practice_filters": {
            "practice_focus_section": practice_meta.get("practice_focus_section")
            or active_song_meta.get("practice_focus_section"),
            "practice_groove_style": practice_meta.get("practice_groove_style"),
            "practice_minutes": practice_meta.get("practice_minutes"),
            "practice_notation_lines": practice_meta.get("practice_notation_lines"),
            "practice_notation_difficulty": practice_meta.get("practice_notation_difficulty"),
            "last_practice_mode": practice_meta.get("last_practice_mode"),
        },
    }


def build_music_disk_state(st: Any) -> dict[str, Any]:
    ss = st.session_state
    save_reason = str(ss.get("_suite_pending_save_reason") or "autosave")
    if save_reason == "page_change":
        live_page, _ = _resolve_live_studio_page_for_save(ss, save_reason=save_reason)
        if live_page:
            ss["studio_page"] = live_page
    try:
        from active_song_state import commit_active_song_state_from_session
        from practice_state import commit_practice_state_from_session
        from studio_nav_state import commit_studio_nav_from_session

        commit_active_song_state_from_session(ss, reason=save_reason)
        commit_studio_nav_from_session(ss, reason=save_reason)
        commit_practice_state_from_session(ss, reason=save_reason)
    except ImportError:
        pass
    core = build_music_local_state(st)
    extra: dict[str, Any] = {}
    for key in _PERSIST_KEYS:
        if key in ss:
            extra[key] = copy.deepcopy(ss[key])
    for key in _LIST_KEYS:
        if key in ss:
            val = ss[key]
            if isinstance(val, list):
                extra[key] = copy.deepcopy(val)
    snapshots = ss.get("_studio_page_snapshots")
    if isinstance(snapshots, dict) and snapshots:
        extra["_studio_page_snapshots"] = copy.deepcopy(snapshots)
    try:
        from custom_progression_lab import export_cpl_widget_state

        cpl_widgets = export_cpl_widget_state(ss)
        if cpl_widgets:
            extra["_cpl_widget_state"] = cpl_widgets
    except Exception:
        pass
    for key in _INSIGHT_KEYS:
        if key in ss:
            extra[key] = copy.deepcopy(ss[key])
    state: dict[str, Any] = {"core": core, "session": extra}
    for key in _WORKSPACE_KEYS:
        if key in ss:
            try:
                state[key] = copy.deepcopy(ss[key])
            except Exception:
                state[key] = ss[key]
    save_reason = str(ss.pop("_suite_pending_save_reason", None) or save_reason)
    if save_reason == "page_change":
        live_page, _ = _resolve_live_studio_page_for_save(ss, save_reason=save_reason)
        if live_page:
            core["studio_page"] = live_page
            core["page"] = live_page
            extra["studio_page"] = live_page
            nav_meta = state.get("studio_nav_state")
            if isinstance(nav_meta, dict):
                nav_meta["studio_page"] = live_page
                nav_meta["page"] = live_page
    state["music_workspace_state"] = _build_workspace_envelope(st, state, save_reason=save_reason)
    stamp_trace = _sync_studio_page_into_music_blob(st, state, save_reason=save_reason)
    if hasattr(st, "session_state"):
        if stamp_trace:
            ss["_music_save_payload_stamp_trace"] = stamp_trace
        ss["music_workspace_state"] = copy.deepcopy(state["music_workspace_state"])
        if isinstance(state.get("studio_nav_state"), dict):
            ss["studio_nav_state"] = copy.deepcopy(state["studio_nav_state"])
    return state



def apply_music_disk_state(
    st: Any,
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> None:
    """Apply disk/cloud payload with studio_page ownership protection."""
    ss = st.session_state
    pre_restore_studio_page = str(ss.get("studio_page") or "").strip()
    pre_restore_user_nav = bool(ss.get("_suite_page_user_nav"))
    pre_restore_coach_page = str(ss.get("_music_coach_workspace_page") or "").strip()

    core = payload.get("core") if isinstance(payload.get("core"), dict) else payload
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}

    preserve_insight = bool(ss.get("_ami_insight_return_preserve"))
    try:
        from applied_math_return_insight import local_ami_insight_should_preserve

        preserve_insight = preserve_insight or local_ami_insight_should_preserve(st)
    except ImportError:
        pass
    for key in _INSIGHT_KEYS:
        if key in session_extra and not preserve_insight:
            ss[key] = copy.deepcopy(session_extra[key])

    ss.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    applied = False
    if isinstance(core, dict) and core:
        applied = apply_saved_music_context(
            st,
            core,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )
        if applied:
            ss[SUITE_LOCAL_STATE_RESTORED_KEY] = True

    if not applied and not (isinstance(core, dict) and core):
        restore_saved_app_state_once(
            st,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    for key, val in session_extra.items():
        if key in _INSIGHT_KEYS and preserve_insight:
            continue
        if key == "_studio_page_snapshots" and isinstance(val, dict):
            ss[key] = copy.deepcopy(val)
        elif key == "_cpl_widget_state" and isinstance(val, dict):
            try:
                from custom_progression_lab import import_cpl_widget_state

                import_cpl_widget_state(ss, val)
            except Exception:
                pass
        elif key in _LIST_KEYS and isinstance(val, list):
            ss[key] = copy.deepcopy(val)
        elif key in _PERSIST_KEYS:
            ss[key] = copy.deepcopy(val)
        elif not str(key).startswith("_ami_"):
            ss[key] = copy.deepcopy(val)

    blob_studio = str((core or {}).get("studio_page") or session_extra.get("studio_page") or "").strip()
    meta = payload.get("music_workspace_state")
    if isinstance(meta, dict) and meta.get("studio_page"):
        blob_studio = str(meta.get("studio_page") or blob_studio).strip()

    for key in _WORKSPACE_KEYS:
        if key in payload:
            try:
                ss[key] = copy.deepcopy(payload[key])
            except Exception:
                ss[key] = payload[key]

    user_owns_page = bool(pre_restore_user_nav)
    active_studio, overwrite_source = blob_studio, "workspace_blob"
    try:
        from studio_nav_state import resolve_studio_page_for_restore

        active_studio, overwrite_source = resolve_studio_page_for_restore(
            ss,
            payload,
            pre_restore_page=pre_restore_studio_page,
            user_owns_page=user_owns_page,
            st=st,
        )
    except ImportError:
        last_persisted = str(ss.get("_suite_last_persisted_page") or "").strip()
        active_studio, overwrite_source = blob_studio or pre_restore_studio_page, "workspace_blob"
        try:
            from applied_math_return_insight import ami_return_navigation_active

            if (
                ami_return_navigation_active(st, APP_ID)
                and pre_restore_studio_page
                and (not blob_studio or pre_restore_studio_page != blob_studio)
            ):
                active_studio = pre_restore_studio_page
                overwrite_source = "ami_return_preserved"
                user_owns_page = True
        except ImportError:
            pass
        if user_owns_page and pre_restore_studio_page and blob_studio and pre_restore_studio_page != blob_studio:
            active_studio = pre_restore_studio_page
            overwrite_source = "user_page_preserved"
        elif pre_restore_studio_page and not blob_studio:
            active_studio = pre_restore_studio_page

    ss["_suite_page_overwrite_source"] = overwrite_source
    if active_studio:
        ss["studio_page"] = active_studio
        try:
            from studio_nav_state import write_canonical_studio_nav_state

            write_canonical_studio_nav_state(ss, active_studio, reason="workspace_restore")
        except ImportError:
            pass

    try:
        from active_song_state import (
            apply_cloud_active_song_state_if_allowed,
            clear_active_song_local_edit,
            is_active_song_locally_dirty,
            sync_active_song_context_from_core,
        )

        if is_active_song_locally_dirty(ss):
            ss["_active_song_restore_skipped_reason"] = "local_dirty"
        elif apply_cloud_active_song_state_if_allowed(ss, payload):
            clear_active_song_local_edit(ss)
        elif isinstance(core, dict) and core and applied:
            sync_active_song_context_from_core(ss, core)
            clear_active_song_local_edit(ss)
    except ImportError:
        pass

    try:
        from practice_state import (
            apply_cloud_practice_state_if_allowed,
            clear_practice_local_edit,
            is_practice_locally_dirty,
        )

        if is_practice_locally_dirty(ss):
            ss["_practice_restore_skipped_reason"] = "local_dirty"
        elif apply_cloud_practice_state_if_allowed(ss, payload):
            clear_practice_local_edit(ss)
        try:
            from practice_state import prepare_practice_page

            prepare_practice_page(ss)
        except ImportError:
            pass
    except ImportError:
        pass

    try:
        from music_coach_context import sync_music_coach_workspace_page

        sync_music_coach_workspace_page(ss)
    except Exception:
        pass

    ss["_suite_cloud_workspace_applied"] = True

    try:
        from music_coach_context import resolve_coach_source_page
        from music_persistence_trace import update_trace

        coach_page = resolve_coach_source_page(ss)
        ws_meta = payload.get("music_workspace_state")
        ws_studio = (
            str(ws_meta.get("studio_page") or "").strip()
            if isinstance(ws_meta, dict)
            else ""
        )
        practice_trace: dict[str, Any] = {}
        try:
            from practice_state import collect_practice_persistence_trace

            practice_trace = collect_practice_persistence_trace(ss, payload=payload)
        except ImportError:
            pass
        update_trace(
            st,
            studio_page_raw=pre_restore_studio_page or blob_studio,
            normalized_studio_page=coach_page,
            cloud_payload_studio_page=blob_studio or None,
            restored_studio_page=active_studio or blob_studio or None,
            restore_decision=overwrite_source,
            restore_skip_reason=ss.get("_suite_persist_restore_skip_reason"),
            final_studio_page=ss.get("studio_page"),
            page_owner_flag=bool(ss.get("_suite_page_user_nav")),
            music_workspace_state_studio_page=ws_studio or None,
            **practice_trace,
        )
    except Exception:
        pass


def after_studio_page_change(
    st: Any,
    session_state: dict | None = None,
    *,
    target_page: str | None = None,
) -> None:
    """Persist studio_page to disk/cloud immediately after manual navigation."""
    from suite_user_persistence import _release_user_page_ownership_after_save

    ss = session_state if session_state is not None else st.session_state
    page_id = (
        _normalize_studio_page_for_save(target_page)
        or _normalize_studio_page_for_save(ss.get("studio_page"))
        or "practice"
    )
    try:
        from applied_math_return_insight import ami_return_navigation_active, consume_ami_return_resume

        if ami_return_navigation_active(st, APP_ID):
            consume_ami_return_resume(st, APP_ID)
    except ImportError:
        pass
    prepare_page_change_save_state(ss, page_id, st=st)
    try:
        from music_persistence_trace import update_trace

        update_trace(
            st,
            pre_save_studio_page=ss.get("studio_page"),
            pre_save_nav_page=_studio_nav_page_from_session(ss),
            pre_save_page_owner=bool(ss.get("_suite_page_user_nav")),
        )
    except Exception:
        pass
    try:
        from local_nav_trace import record_local_nav_checkpoint

        record_local_nav_checkpoint(
            st,
            "post_navigate_before_save",
            session=ss,
            intent=page_id,
        )
    except ImportError:
        pass
    if not _page_change_save_ready(ss, page_id):
        ss["_suite_deferred_page_change_save"] = page_id
        return
    ss.pop("_suite_deferred_page_change_save", None)
    ss["_suite_page_change_save_page"] = page_id
    build_ss = getattr(st, "session_state", ss)
    if build_ss is not ss:
        build_ss["_suite_page_change_save_page"] = page_id
    try:
        force_save_music_state(st, reason="page_change")
    finally:
        ss.pop("_suite_page_change_save_page", None)
        if build_ss is not ss:
            build_ss.pop("_suite_page_change_save_page", None)
    _release_user_page_ownership_after_save(st, page_id)

    ss["_suite_last_persisted_page"] = page_id
    ss.pop("_suite_page_user_nav", None)


def claim_studio_page_ownership(
    st: Any,
    page_id: str,
    session_state: dict | None = None,
) -> None:
    """Manual sidebar navigation wins over stale cloud studio_page restore."""
    ss = session_state if session_state is not None else st.session_state
    page = prepare_page_change_save_state(ss, page_id, st=st)
    if page:
        ss["_suite_last_persisted_page"] = page


def prepare_canonical_music_page_state(session: dict[str, Any]) -> None:
    """Phase C: reconcile studio nav + active song + practice canonical blobs before widgets."""
    try:
        from active_song_state import prepare_active_song_context
        from practice_state import prepare_practice_page
        from studio_nav_state import prepare_studio_nav

        prepare_studio_nav(session)
        prepare_active_song_context(session)
        prepare_practice_page(session)
    except ImportError:
        pass


def mark_active_song_edit_pending(session: dict[str, Any]) -> None:
    try:
        from active_song_state import mark_active_song_pending_sync

        mark_active_song_pending_sync(session)
    except ImportError:
        pass


def _clear_canonical_dirty_after_save(session: dict[str, Any], *, reason: str = "") -> None:
    try:
        from active_song_state import clear_active_song_local_edit
        from practice_state import clear_practice_local_edit
        from studio_nav_state import clear_studio_nav_local_edit

        clear_active_song_local_edit(session)
        clear_practice_local_edit(session)
        if reason == "page_change":
            clear_studio_nav_local_edit(session)
    except ImportError:
        pass


def flush_practice_edits_and_save(st: Any, *, reason: str = "practice_edit") -> bool:
    """Canonical Practice flush + cross-device force save (Phase C)."""
    try:
        from practice_state import (
            PRACTICE_PENDING_SYNC_KEY,
            flush_practice_edits,
            is_practice_locally_dirty,
        )

        ss = st.session_state
        if ss.get(PRACTICE_PENDING_SYNC_KEY) or is_practice_locally_dirty(ss) or reason == "practice_edit":
            flush_practice_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _clear_canonical_dirty_after_save(st.session_state, reason=reason)
        _record_music_persist_trace(st, reason=reason)
    return ok


def maybe_flush_pending_practice_edits(st: Any) -> None:
    try:
        from practice_state import PRACTICE_PENDING_SYNC_KEY

        if st.session_state.get(PRACTICE_PENDING_SYNC_KEY):
            flush_practice_edits_and_save(st, reason="practice_edit")
    except ImportError:
        pass


def flush_active_song_edits_and_save(st: Any, *, reason: str = "song_edit") -> bool:
    """Canonical active-song flush + cross-device force save (Phase C)."""
    try:
        from active_song_state import (
            ACTIVE_SONG_PENDING_SYNC_KEY,
            flush_active_song_edits,
            is_active_song_locally_dirty,
        )

        ss = st.session_state
        if ss.get(ACTIVE_SONG_PENDING_SYNC_KEY) or is_active_song_locally_dirty(ss) or reason == "song_edit":
            flush_active_song_edits(ss, reason=reason)
    except ImportError:
        pass
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _clear_canonical_dirty_after_save(st.session_state, reason=reason)
        _record_music_persist_trace(st, reason=reason)
    return ok


def maybe_flush_pending_active_song_edits(st: Any) -> None:
    try:
        from active_song_state import ACTIVE_SONG_PENDING_SYNC_KEY

        if st.session_state.get(ACTIVE_SONG_PENDING_SYNC_KEY):
            flush_active_song_edits_and_save(st, reason="song_edit")
    except ImportError:
        pass


def prepare_music_workspace(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """Authoritative cloud/disk workspace sync before sidebar widgets."""
    try:
        from suite_cloud_state import (
            list_active_resume_query_params,
            reconcile_stale_resume_session_flags,
            should_skip_workspace_restore_for_resume,
        )
        from music_persistence_trace import record_music_resume_restore_trace

        cleared = reconcile_stale_resume_session_flags(st, APP_ID)
        live_params = list_active_resume_query_params(st, APP_ID)
        skip = should_skip_workspace_restore_for_resume(st, APP_ID, reconcile_first=False)
        ami_active = False
        try:
            from applied_math_return_insight import ami_return_navigation_active

            ami_active = ami_return_navigation_active(st, APP_ID)
        except ImportError:
            pass
        record_music_resume_restore_trace(
            st,
            live_resume_url_params=live_params,
            stale_resume_flags_cleared=cleared,
            has_resume_query_params_result=bool(live_params),
            should_skip_workspace_restore_for_resume=skip,
            ami_return_navigation_active=ami_active,
        )
    except Exception:
        pass

    def _apply(st_obj: Any, state: dict[str, Any]) -> None:
        apply_music_disk_state(
            st_obj,
            state,
            song_picker_catalog=song_picker_catalog,
            song_library=song_library,
        )

    return sync_workspace_protocol(
        st,
        APP_ID,
        apply_state=_apply,
        cloud_first=True,
    )


def _record_music_persist_trace(st: Any, *, reason: str = "") -> None:
    """Update ?dev=1 trace after force/autosave (phone→Dell page sync diagnostics)."""
    try:
        from music_persistence_trace import update_trace

        ss = st.session_state
        saved_studio = str(ss.get("studio_page") or "").strip()
        coach_page = ""
        try:
            from music_coach_context import resolve_coach_source_page

            coach_page = resolve_coach_source_page(ss)
        except Exception:
            coach_page = saved_studio
        ws_meta = ss.get("music_workspace_state")
        ws_studio = (
            str(ws_meta.get("studio_page") or "").strip()
            if isinstance(ws_meta, dict)
            else saved_studio
        )
        cloud_updated_at = None
        cloud_fetch_page = ""
        cloud_payload_page = saved_studio
        try:
            from suite_cloud_state import load_cloud_full_session

            cloud_state, cloud_ts = load_cloud_full_session(APP_ID)
            cloud_updated_at = cloud_ts
            if isinstance(cloud_state, dict) and cloud_state:
                cloud_meta = (
                    cloud_state.get("music_workspace_state")
                    if isinstance(cloud_state.get("music_workspace_state"), dict)
                    else {}
                )
                cloud_core = cloud_state.get("core") if isinstance(cloud_state.get("core"), dict) else {}
                cloud_fetch_page = str(
                    cloud_meta.get("studio_page")
                    or cloud_core.get("studio_page")
                    or ""
                ).strip()
                if cloud_fetch_page:
                    cloud_payload_page = cloud_fetch_page
                    ss["_suite_cloud_fetch_studio_page"] = cloud_fetch_page
        except Exception:
            cloud_state = {}
        practice_trace: dict[str, Any] = {}
        try:
            from practice_state import collect_practice_persistence_trace

            practice_trace = collect_practice_persistence_trace(ss, payload=cloud_state if isinstance(cloud_state, dict) else None)
        except ImportError:
            pass
        local_updated_at = ss.get("_suite_persist_debug_disk_ts") or ss.get("_suite_persist_last_save_at")
        stamp_trace = ss.get("_music_save_payload_stamp_trace")
        save_payload_trace: dict[str, Any] = (
            dict(stamp_trace) if isinstance(stamp_trace, dict) else {}
        )
        if reason == "page_change" and isinstance(ss.get("_suite_last_cloud_save_payload"), dict):
            last_payload = ss["_suite_last_cloud_save_payload"]
            payload_ws = last_payload.get("music_workspace_state")
            payload_core = last_payload.get("core") if isinstance(last_payload.get("core"), dict) else {}
            payload_sess = (
                last_payload.get("session") if isinstance(last_payload.get("session"), dict) else {}
            )
            payload_nav = (
                last_payload.get("studio_nav_state")
                if isinstance(last_payload.get("studio_nav_state"), dict)
                else {}
            )
            save_payload_trace.setdefault(
                "save_payload_source",
                save_payload_trace.get("save_payload_source") or "session_state.studio_page",
            )
            save_payload_trace["save_payload_core_page"] = str(
                save_payload_trace.get("save_payload_core_page")
                or payload_core.get("studio_page")
                or ""
            )
            save_payload_trace["save_payload_session_page"] = str(
                save_payload_trace.get("save_payload_session_page")
                or payload_sess.get("studio_page")
                or ""
            )
            save_payload_trace["save_payload_workspace_page"] = str(
                save_payload_trace.get("save_payload_workspace_page")
                or (
                    (payload_ws or {}).get("studio_page")
                    if isinstance(payload_ws, dict)
                    else ""
                )
                or ""
            )
            save_payload_trace["save_payload_studio_nav_page"] = str(
                save_payload_trace.get("save_payload_studio_nav_page")
                or payload_nav.get("studio_page")
                or payload_nav.get("page")
                or ""
            )
            if save_payload_trace.get("save_payload_workspace_page"):
                cloud_payload_page = str(save_payload_trace["save_payload_workspace_page"])
        update_trace(
            st,
            studio_page_raw=saved_studio or None,
            normalized_studio_page=coach_page,
            cloud_payload_studio_page=cloud_payload_page or None,
            music_workspace_state_studio_page=ws_studio or saved_studio or None,
            last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")),
            force_save_reason=reason or ss.get("_suite_persist_last_save_reason"),
            page_owner_flag=bool(ss.get("_suite_page_user_nav")),
            pre_save_studio_page=ss.get("studio_page"),
            pre_save_nav_page=_studio_nav_page_from_session(ss),
            pre_save_page_owner=bool(ss.get("_suite_page_user_nav")),
            cloud_fetch_studio_page=cloud_fetch_page or ss.get("_suite_cloud_fetch_studio_page"),
            cloud_updated_at=cloud_updated_at,
            local_updated_at=local_updated_at,
            final_studio_page=ss.get("studio_page"),
            **save_payload_trace,
            **practice_trace,
        )
    except Exception:
        pass


def force_save_music_state(st: Any, *, reason: str = "") -> bool:
    ok = force_autosave(st, APP_ID, build_state=build_music_disk_state, reason=reason)
    if ok:
        _clear_canonical_dirty_after_save(st.session_state, reason=reason)
    if ok or reason == "page_change":
        _record_music_persist_trace(st, reason=reason)
    return ok


def autosave_music_state(st: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "skipped": True,
        "disk_ok": False,
        "cloud_attempted": False,
        "cloud_ok": False,
        "cloud_error": None,
    }
    try:
        result = autosave_if_changed(st, APP_ID, build_state=build_music_disk_state)
    except Exception as exc:
        result["error"] = str(exc)
    try:
        from music_persistence_trace import get_trace, update_trace

        ss = st.session_state
        prior = get_trace(st)
        saved_studio = str(ss.get("studio_page") or "")
        coach_page = ""
        try:
            from music_coach_context import resolve_coach_source_page

            coach_page = resolve_coach_source_page(ss)
        except Exception:
            coach_page = saved_studio
        trace_fields: dict[str, Any] = {
            "autosave_ran": not result.get("skipped", True),
            "cloud_save_success": result.get("cloud_ok"),
            "cloud_save_attempted": result.get("cloud_attempted"),
            "cloud_save_error": result.get("cloud_error"),
            "last_save_source": result.get("last_save_source"),
            "persist_calls_autosave": True,
            "saved_studio_page": saved_studio,
            "studio_page_raw": ss.get("studio_page"),
            "normalized_studio_page": coach_page,
            "cloud_payload_studio_page": saved_studio or None,
            "last_save_cloud": bool(result.get("cloud_ok")),
            "force_save_reason": ss.get("_suite_persist_last_save_reason"),
            "final_studio_page": ss.get("studio_page"),
        }
        if ss.get("_suite_page_user_nav"):
            trace_fields["page_owner_flag"] = True
        elif prior.get("force_save_reason") != "page_change":
            trace_fields["page_owner_flag"] = False
        update_trace(st, **trace_fields)
        if result.get("cloud_ok") or result.get("disk_ok"):
            _clear_canonical_dirty_after_save(ss)
        try:
            from suite_cloud_state import load_cloud_full_session

            cloud_state, cloud_ts = load_cloud_full_session(APP_ID)
            if cloud_ts:
                update_trace(st, last_cloud_ts=cloud_ts)
            if isinstance(cloud_state, dict) and cloud_state:
                cloud_core = cloud_state.get("core") if isinstance(cloud_state.get("core"), dict) else {}
                cloud_sess = cloud_state.get("session") if isinstance(cloud_state.get("session"), dict) else {}
                cloud_meta = (
                    cloud_state.get("music_workspace_state")
                    if isinstance(cloud_state.get("music_workspace_state"), dict)
                    else {}
                )
                cloud_page = str(
                    cloud_meta.get("studio_page")
                    or cloud_core.get("studio_page")
                    or cloud_sess.get("studio_page")
                    or ""
                ).strip()
                if cloud_page:
                    st.session_state["_suite_cloud_fetch_studio_page"] = cloud_page
                    update_trace(st, cloud_fetch_studio_page=cloud_page)
        except Exception:
            pass
    except Exception:
        pass
    return result


def restore_music_disk_state_once(
    st: Any,
    *,
    song_picker_catalog: dict,
    song_library: dict | None,
) -> bool:
    """Deprecated — use prepare_music_workspace() instead."""
    return prepare_music_workspace(
        st,
        song_picker_catalog=song_picker_catalog,
        song_library=song_library,
    )


def persist_music_disk_state(st: Any) -> None:
    save_user_state(APP_ID, build_music_disk_state(st))


def reset_music_disk_state(st: Any) -> None:
    reset_user_state(APP_ID)
    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("_suite_") or str(key).startswith("_page_initialized"):
            st.session_state.pop(key, None)


def apply_music_session_defaults(st: Any) -> None:
    """Return music session to first-run defaults (not user chart override files)."""
    from picker_song_editor import PICKER_EDITOR_OPEN_KEY

    ss = st.session_state
    for key in (
        "studio_page",
        "instrument",
        "level",
        "focus",
        "display_key",
        "practice_focus_section",
        "backing_track_scope",
        "backing_lead_sheet_open",
        PICKER_EDITOR_OPEN_KEY,
        "chart_edit_mode",
        "_studio_page_snapshots",
        "chart_library_mode",
        "song_search_text",
        "song_search_scope",
        "song_picker_level_filter",
        "workspace_genre_filter",
        "backing_track_loops",
        "backing_track_single_section",
        "backing_groove_style",
        "backing_track_bpm",
        "karaoke_countdown_enabled",
        "karaoke_auto_advance",
        "active_music_source",
        "picker_editor_tab",
        "picker_song_editor_open",
        "last_practice_mode",
        "improv_song_source",
        "creative_lab_analysis_mode",
        "improv_intelligence_tab",
        "workspace_genre_filters",
        "backing_track_multi_sections",
        "karaoke_queue",
        "catalog_favorite_pick_keys",
        "song_picker_favorites_only",
        "cpl_active_progression",
        "cpl_saved_progressions",
        "cpl_builder_version",
        "cpl_finished",
        "_cpl_editing_display_key",
        "cpl_last_display_key",
        "_music_coach_workspace_page",
    ):
        ss.pop(key, None)
    try:
        from custom_progression_lab import clear_cpl_widget_state

        clear_cpl_widget_state(ss)
    except Exception:
        pass
    ss.pop(ACTIVE_CATALOG_PICK_KEY, None)
    ss.pop(SELECTED_SONG_STATE_KEY, None)
    ss.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    for key in _WORKSPACE_KEYS:
        ss.pop(key, None)
    try:
        from active_song_state import ACTIVE_SONG_DIRTY_KEY, clear_active_song_local_edit
        from practice_state import clear_practice_local_edit
        from studio_nav_state import clear_studio_nav_local_edit

        clear_active_song_local_edit(ss)
        clear_practice_local_edit(ss)
        clear_studio_nav_local_edit(ss)
        ss.pop(ACTIVE_SONG_DIRTY_KEY, None)
    except ImportError:
        pass
    for key in list(ss.keys()):
        if str(key).startswith("_suite_") or str(key).startswith("_page_initialized"):
            ss.pop(key, None)


def default_reset_music_session(st: Any) -> None:
    """Full music reset: session, disk, and cloud ``full_session`` when available."""
    apply_music_session_defaults(st)
    reset_user_state(APP_ID)
    fresh = build_music_disk_state(st)
    finalize_suite_reset(st, APP_ID, fresh)
    st.session_state.pop(SUITE_LOCAL_STATE_RESTORED_KEY, None)
    st.session_state.pop(f"_suite_autosave_fp::{APP_ID}", None)


def clear_music_workspace_autosave_block(st: Any) -> None:
    clear_workspace_autosave_block(st, APP_ID)

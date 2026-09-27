"""Back / forward navigation history for studio pages (session_state stacks).

Each stack entry stores ``page`` + **page-local** snapshot only (see
``studio_page_persistence``). Global instrument, level, focus, display key,
song, and transposition are never reverted by back/forward.

Creative Lab major workspaces (Improvisation Intelligence tabs, and Entry & Jam
entry modes SBI vs Jam/Style) are separate history destinations under
``studio_page=creative``.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from studio_page_persistence import (
    make_history_entry,
    restore_history_entry,
    save_page_snapshot,
)

STUDIO_PAGE_IDS: frozenset[str] = frozenset(
    {
        "practice",
        "picker",
        "backing",
        "custom",
        "composer",
        "creative",
        "multitrack",
        "analysis",
        "log",
        "openai",
    }
)

NAV_BACK_STACK = "studio_nav_back"
NAV_FORWARD_STACK = "studio_nav_forward"
_NAV_FROM_HISTORY = "_studio_nav_from_history"
_HISTORY_NAV_PENDING_SAVE = "_studio_history_nav_pending_save"
_HISTORY_NAV_REMOUNT_TARGET = "_studio_history_nav_remount_target"
# Creative workspace destination seal — survives Streamlit widget remount after
# history Back/Forward within studio_page=creative.
_HISTORY_CREATIVE_DEST_SEAL = "_studio_history_creative_dest_seal"
_HISTORY_CREATIVE_SEAL_MATCHES = "_studio_history_creative_seal_matches"
# Live Creative destination id for adjacent-dupe / workspace-change detection.
_LIVE_CREATIVE_DEST_KEY = "_history_live_creative_dest"

# Bump when verifying Streamlit Cloud picked up navigation UI changes.
NAVIGATION_UI_DEPLOY_MARKER = "studio-nav-float-gutter-v1"

__all__ = (
    "STUDIO_PAGE_IDS",
    "NAV_BACK_STACK",
    "NAV_FORWARD_STACK",
    "NAVIGATION_UI_DEPLOY_MARKER",
    "init_nav_history",
    "can_go_back",
    "can_go_forward",
    "navigate_studio_page",
    "go_back",
    "go_forward",
    "history_destination_id",
    "record_creative_workspace_change",
    "sync_live_creative_history_dest",
    "enforce_pending_creative_history_dest",
    "apply_creative_history_destination",
    "render_floating_nav_history",
    "render_studio_history_toolbar",
    "render_sidebar_nav_history",
    "render_nav_deploy_marker",
    "record_nav_history_trace",
    "consume_history_nav_startup_flag",
    "flush_deferred_history_nav_save",
    "history_nav_blocks_workspace_sync",
    "enforce_history_nav_remount_target",
)


def init_nav_history(session_state: dict) -> None:
    session_state.setdefault(NAV_BACK_STACK, [])
    session_state.setdefault(NAV_FORWARD_STACK, [])


def _normalize_stack_entry(entry: Any) -> dict[str, Any]:
    """Support legacy stacks that stored only a page id string."""
    if isinstance(entry, dict) and entry.get("page"):
        return entry
    if isinstance(entry, str) and entry in STUDIO_PAGE_IDS:
        return {"page": entry, "snapshot": {}}
    return {"page": "practice", "snapshot": {}}


def _creative_destination_id(tab: str, entry_mode: str = "") -> str:
    """Map Creative tab (+ Entry & Jam mode) to a stable history destination id."""
    tab_tok = str(tab or "").strip()
    if not tab_tok:
        return "creative"
    if tab_tok == "Entry & Jam":
        mode = str(entry_mode or "").strip()
        if mode == "Song-Based Improvisation" or not mode:
            return "creative::SBI"
        if mode in {"Style Jam Mode", "Jam Session Generator"}:
            return "creative::Entry Mode"
        return "creative::Entry & Jam"
    return f"creative::{tab_tok}"


def history_destination_id(
    session_state: dict[str, Any] | None = None,
    *,
    page: str = "",
    tab: str = "",
    entry_mode: str = "",
    entry: dict[str, Any] | None = None,
) -> str:
    """Identity for history adjacency / Creative workspace separation."""
    if entry is not None:
        norm = _normalize_stack_entry(entry)
        page_tok = str(norm.get("page") or "").strip()
        if page_tok != "creative":
            return page_tok or "practice"
        if norm.get("destination"):
            return str(norm.get("destination") or "")
        snap = norm.get("snapshot") if isinstance(norm.get("snapshot"), dict) else {}
        tab_tok = str(
            norm.get("workspace")
            or (snap or {}).get("improv_intelligence_tab")
            or (snap or {}).get("creative_improv_intelligence_tab")
            or ""
        ).strip()
        mode_tok = str((snap or {}).get("improv_entry_mode") or "").strip()
        return _creative_destination_id(tab_tok, mode_tok)
    page_tok = str(page or (session_state or {}).get("studio_page") or "").strip()
    if page_tok != "creative":
        return page_tok or "practice"
    ss = session_state or {}
    tab_tok = str(
        tab
        or ss.get("improv_intelligence_tab")
        or ss.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    mode_tok = str(entry_mode or ss.get("improv_entry_mode") or "").strip()
    return _creative_destination_id(tab_tok, mode_tok)


def _annotate_history_entry(session_state: dict, entry: dict[str, Any]) -> dict[str, Any]:
    """Attach destination/workspace labels for Creative stack entries."""
    page = str(entry.get("page") or "").strip()
    if page != "creative":
        entry["destination"] = page
        return entry
    snap = entry.get("snapshot") if isinstance(entry.get("snapshot"), dict) else {}
    tab = str(
        snap.get("improv_intelligence_tab")
        or snap.get("creative_improv_intelligence_tab")
        or session_state.get("improv_intelligence_tab")
        or ""
    ).strip()
    mode = str(snap.get("improv_entry_mode") or session_state.get("improv_entry_mode") or "").strip()
    entry["workspace"] = tab
    entry["destination"] = _creative_destination_id(tab, mode)
    return entry


def _make_annotated_entry(session_state: dict, page_id: str) -> dict[str, Any]:
    return _annotate_history_entry(session_state, make_history_entry(session_state, page_id))


def _append_back_if_new(session_state: dict, entry: dict[str, Any]) -> None:
    """Push back entry unless it duplicates the adjacent destination (rerun noise)."""
    back: list[Any] = session_state.setdefault(NAV_BACK_STACK, [])
    dest = history_destination_id(entry=entry)
    if back and history_destination_id(entry=_normalize_stack_entry(back[-1])) == dest:
        return
    back.append(entry)


def sync_live_creative_history_dest(session_state: dict) -> str:
    """Remember the live Creative destination after render (for next tab/mode change)."""
    seal = str(session_state.get(_HISTORY_CREATIVE_DEST_SEAL) or "").strip()
    if seal and str(session_state.get("studio_page") or "") == "creative":
        live = history_destination_id(session_state)
        if live != seal:
            apply_creative_history_destination(session_state, seal)
        else:
            matches = int(session_state.get(_HISTORY_CREATIVE_SEAL_MATCHES) or 0) + 1
            session_state[_HISTORY_CREATIVE_SEAL_MATCHES] = matches
            # Two settled frames after history restore → user may change tabs again.
            if matches >= 2 and not session_state.get(_NAV_FROM_HISTORY) and not session_state.get(
                _HISTORY_NAV_PENDING_SAVE
            ):
                session_state.pop(_HISTORY_CREATIVE_DEST_SEAL, None)
                session_state.pop(_HISTORY_CREATIVE_SEAL_MATCHES, None)
                seal = ""
    dest = history_destination_id(session_state)
    if str(session_state.get("studio_page") or "") == "creative":
        session_state[_LIVE_CREATIVE_DEST_KEY] = dest
    _gate1_trace(session_state, "H6_creative_dest_synced", live_dest=dest, creative_seal=seal or None)
    return dest


def clear_creative_history_seal(session_state: dict) -> None:
    session_state.pop(_HISTORY_CREATIVE_DEST_SEAL, None)
    session_state.pop(_HISTORY_CREATIVE_SEAL_MATCHES, None)


def set_creative_history_seal(session_state: dict, dest: str) -> None:
    dest = str(dest or "").strip()
    if not dest.startswith("creative::"):
        return
    session_state[_HISTORY_CREATIVE_DEST_SEAL] = dest
    session_state[_HISTORY_CREATIVE_SEAL_MATCHES] = 0
    session_state["_pending_history_creative_dest"] = dest


def apply_creative_history_destination(session_state: dict, dest: str) -> None:
    """Force Creative tab/mode from a history destination id (widget-proof)."""
    dest = str(dest or "").strip()
    if not dest.startswith("creative::"):
        return
    workspace = dest.split("::", 1)[1]
    if workspace == "SBI":
        tab = "Entry & Jam"
        mode = "Song-Based Improvisation"
    elif workspace == "Entry Mode":
        tab = "Entry & Jam"
        mode = "Jam Session Generator"
    elif workspace == "Entry & Jam":
        tab = "Entry & Jam"
        mode = str(session_state.get("improv_entry_mode") or "Song-Based Improvisation")
    else:
        tab = workspace
        # Non-Entry tabs should not keep a Jam mode that would mis-label dest on remount.
        mode = "Song-Based Improvisation"
    session_state["improv_intelligence_tab"] = tab
    session_state["creative_improv_intelligence_tab"] = tab
    session_state["_improv_tab_user_touched"] = True
    session_state["improv_entry_mode"] = mode
    session_state["_history_prev_entry_mode"] = mode
    try:
        session_state["improv_intelligence_tab_for_render"] = tab
    except Exception:
        pass
    if str(session_state.get("studio_page") or "") == "creative":
        session_state[_LIVE_CREATIVE_DEST_KEY] = dest


def enforce_pending_creative_history_dest(session_state: dict) -> str:
    """Apply pending/sealed Creative dest before Improvisation widgets instantiate."""
    pending = str(
        session_state.pop("_pending_history_creative_dest", None)
        or session_state.get(_HISTORY_CREATIVE_DEST_SEAL)
        or ""
    ).strip()
    if pending.startswith("creative::") and str(session_state.get("studio_page") or "") == "creative":
        apply_creative_history_destination(session_state, pending)
        if session_state.get(_HISTORY_CREATIVE_DEST_SEAL):
            session_state["_pending_history_creative_dest"] = pending
    return pending


def record_creative_workspace_change(
    session_state: dict,
    *,
    previous_tab: str = "",
    previous_entry_mode: str = "",
    previous_destination: str = "",
) -> bool:
    """Push the prior Creative workspace onto Back when the user changes tab/mode.

    Call from Improvisation Intelligence tab / Entry Mode on_change after the
    widget has already advanced to the new selection. Uses previous_* to build
    the leave snapshot. Clears Forward (genuine new navigation).
    """
    if str(session_state.get("studio_page") or "").strip() != "creative":
        return False
    init_nav_history(session_state)
    live_new = history_destination_id(session_state)
    seal = str(session_state.get(_HISTORY_CREATIVE_DEST_SEAL) or "").strip()
    if seal:
        matches = int(session_state.get(_HISTORY_CREATIVE_SEAL_MATCHES) or 0)
        if live_new != seal:
            if matches < 2:
                apply_creative_history_destination(session_state, seal)
                _gate1_trace(
                    session_state,
                    "H5_creative_workspace_noop",
                    requested=live_new,
                    previous_destination=seal,
                    classification="history_seal_blocked_remount",
                )
                return False
            clear_creative_history_seal(session_state)
        else:
            sync_live_creative_history_dest(session_state)
            _gate1_trace(
                session_state,
                "H5_creative_workspace_noop",
                requested=live_new,
                previous_destination=seal,
                classification="history_seal_same_target",
            )
            return False
    prev_dest = str(previous_destination or "").strip()
    if not prev_dest:
        prev_dest = _creative_destination_id(previous_tab, previous_entry_mode)
    if not prev_dest or prev_dest == live_new:
        sync_live_creative_history_dest(session_state)
        _gate1_trace(
            session_state,
            "H5_creative_workspace_noop",
            requested=live_new,
            previous_destination=prev_dest,
            classification="same_target_remount",
        )
        return False
    # Snapshot as the previous workspace (page-local only).
    saved_tab = session_state.get("improv_intelligence_tab")
    saved_canon = session_state.get("creative_improv_intelligence_tab")
    saved_mode = session_state.get("improv_entry_mode")
    try:
        if previous_tab:
            session_state["improv_intelligence_tab"] = previous_tab
            session_state["creative_improv_intelligence_tab"] = previous_tab
        if prev_dest.endswith("::SBI"):
            session_state["improv_entry_mode"] = "Song-Based Improvisation"
        elif "Entry Mode" in prev_dest:
            session_state["improv_entry_mode"] = "Jam Session Generator"
        elif previous_entry_mode:
            session_state["improv_entry_mode"] = previous_entry_mode
        save_page_snapshot(session_state, "creative")
        entry = _make_annotated_entry(session_state, "creative")
        entry["destination"] = prev_dest
        if previous_tab:
            entry["workspace"] = previous_tab
    finally:
        if saved_tab is not None:
            session_state["improv_intelligence_tab"] = saved_tab
        if saved_canon is not None:
            session_state["creative_improv_intelligence_tab"] = saved_canon
        if saved_mode is not None:
            session_state["improv_entry_mode"] = saved_mode
    _append_back_if_new(session_state, entry)
    # Genuine workspace navigation — discard Forward branch.
    session_state[NAV_FORWARD_STACK] = []
    # Pending history remount seal no longer applies after deliberate leave.
    session_state.pop(_HISTORY_NAV_PENDING_SAVE, None)
    session_state.pop(_HISTORY_NAV_REMOUNT_TARGET, None)
    clear_creative_history_seal(session_state)
    sync_live_creative_history_dest(session_state)
    _gate1_trace(
        session_state,
        "H5_creative_workspace_change",
        requested=live_new,
        previous_destination=prev_dest,
        classification="genuine_user_navigation",
        forward_after=[],
        forward_reason="genuine_navigation_branch",
    )
    return True


def can_go_back(session_state: dict) -> bool:
    return bool(session_state.get(NAV_BACK_STACK))


def can_go_forward(session_state: dict) -> bool:
    return bool(session_state.get(NAV_FORWARD_STACK))


def _stack_page_ids(session_state: dict, stack_key: str) -> list[str]:
    stack = session_state.get(stack_key) or []
    if not isinstance(stack, list):
        return []
    pages: list[str] = []
    for entry in stack:
        pages.append(history_destination_id(entry=_normalize_stack_entry(entry)))
    return pages


def _gate1_trace(session_state: dict, event: str, **extra: Any) -> None:
    """Append an opt-in Gate 1 lifecycle record for real-browser diagnosis."""
    path = str(os.environ.get("SLICE4B_GATE1_TRACE") or "").strip()
    if not path:
        return
    try:
        forward = _stack_page_ids(session_state, NAV_FORWARD_STACK)
        payload: dict[str, Any] = {
            "ts_ns": time.time_ns(),
            "event": event,
            "current": history_destination_id(session_state),
            "studio_page": session_state.get("studio_page"),
            "back": _stack_page_ids(session_state, NAV_BACK_STACK),
            "forward": forward,
            "forward_target": forward[-1] if forward else None,
            "cursor": None,
            "can_go_back": can_go_back(session_state),
            "can_go_forward": can_go_forward(session_state),
            "from_history": bool(session_state.get(_NAV_FROM_HISTORY)),
            "pending_save": session_state.get(_HISTORY_NAV_PENDING_SAVE),
            "remount_target": session_state.get(_HISTORY_NAV_REMOUNT_TARGET),
            "improv_tab": session_state.get("improv_intelligence_tab"),
            "improv_tab_canon": session_state.get("creative_improv_intelligence_tab"),
            "improv_entry_mode": session_state.get("improv_entry_mode"),
            "live_creative_dest": session_state.get(_LIVE_CREATIVE_DEST_KEY),
        }
        payload.update(extra)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def record_nav_history_trace(st: Any | None, session_state: dict, **extra: Any) -> None:
    """Update ?dev=1 trace fields for live back/forward diagnostics."""
    if st is None:
        return
    try:
        from music_persistence_trace import update_trace

        payload: dict[str, Any] = {
            "nav_history_stack": _stack_page_ids(session_state, NAV_BACK_STACK),
            "nav_forward_stack": _stack_page_ids(session_state, NAV_FORWARD_STACK),
            "nav_current_page": session_state.get("studio_page"),
            "final_studio_page": session_state.get("studio_page"),
            "page_overwrite_source": session_state.get("_suite_page_overwrite_source"),
            "active_page_source": session_state.get("active_page_source"),
            "nav_target_page": session_state.get("nav_target_page"),
        }
        payload.update(extra)
        update_trace(st, **payload)
    except Exception:
        pass


def consume_history_nav_startup_flag(session_state: dict) -> bool:
    """Clear one-shot history nav flag after workspace restore consumed it."""
    _gate1_trace(session_state, "H4_before_consume_history_flag")
    consumed = bool(session_state.pop(_NAV_FROM_HISTORY, False))
    _gate1_trace(session_state, "H4_after_consume_history_flag", consumed=consumed)
    return consumed


def history_nav_blocks_workspace_sync(session_state: dict) -> bool:
    """True when cloud workspace restore must not stomp a history Back/Forward target."""
    if session_state.get(_NAV_FROM_HISTORY):
        return True
    if session_state.get(_HISTORY_NAV_PENDING_SAVE):
        return True
    if str(session_state.get(_HISTORY_NAV_REMOUNT_TARGET) or "").strip():
        return True
    try:
        from studio_nav_state import is_studio_nav_locally_dirty

        if is_studio_nav_locally_dirty(session_state):
            return True
    except ImportError:
        pass
    return False


def enforce_history_nav_remount_target(session_state: dict) -> str:
    """Re-pin ``studio_page`` when a history remount/pending target was stomped.

    Streamlit remounts (and some Songs/picker widget trees) can rewrite
    ``studio_page`` back to the leave page while
    ``_studio_history_nav_remount_target`` / pending-save still name the
    Forward/Back destination.  Reassert before arrow render so H6 and the
    page body see the history target on the same run.
    """
    target = str(
        session_state.get(_HISTORY_NAV_REMOUNT_TARGET)
        or session_state.get(_HISTORY_NAV_PENDING_SAVE)
        or ""
    ).strip()
    current = str(session_state.get("studio_page") or "practice").strip() or "practice"
    if not target or target not in STUDIO_PAGE_IDS or target == current:
        return current
    previous = current
    session_state["studio_page"] = target
    session_state["nav_target_page"] = target
    try:
        from studio_nav_state import mark_studio_nav_local_edit, write_canonical_studio_nav_state

        write_canonical_studio_nav_state(
            session_state,
            target,
            reason="history_remount_reassert",
            local_edit=True,
        )
        mark_studio_nav_local_edit(session_state)
    except ImportError:
        pass
    _gate1_trace(
        session_state,
        "H3_remount_target_reasserted",
        target=target,
        previous=previous,
    )
    return target


def _claim_history_nav_ownership(session_state: dict, target_page: str, *, source: str) -> None:
    session_state[_NAV_FROM_HISTORY] = True
    session_state["active_page_source"] = source
    session_state["_suite_page_user_nav"] = True
    session_state["nav_target_page"] = target_page
    try:
        from studio_nav_state import mark_studio_nav_local_edit, write_canonical_studio_nav_state

        write_canonical_studio_nav_state(
            session_state,
            target_page,
            reason=source,
            local_edit=True,
        )
        mark_studio_nav_local_edit(session_state)
    except ImportError:
        pass


def _apply_history_nav_transition(session_state: dict, *, source: str) -> str:
    """Commit history target page before workspace restore runs on the next script pass."""
    target = str(session_state.get("studio_page") or "practice")
    _claim_history_nav_ownership(session_state, target, source=source)
    try:
        from studio_page_persistence import handle_studio_page_transition

        handle_studio_page_transition(session_state)
    except Exception:
        pass
    seal = str(session_state.get(_HISTORY_CREATIVE_DEST_SEAL) or "").strip()
    if seal.startswith("creative::") and str(session_state.get("studio_page") or "") == "creative":
        apply_creative_history_destination(session_state, seal)
        try:
            save_page_snapshot(session_state, "creative")
        except Exception:
            pass
    session_state[_HISTORY_NAV_PENDING_SAVE] = target
    # Saving is flushed at the end of this run, but Streamlit can remount the
    # restored page on a later run.  Keep a separate seal until that remount
    # arrives (or a genuine navigation to another destination cancels it).
    session_state[_HISTORY_NAV_REMOUNT_TARGET] = target
    _gate1_trace(session_state, "H3_history_target_marked", source=source, target=target)
    return target


def _on_history_back() -> None:
    import streamlit as st

    ss = st.session_state
    init_nav_history(ss)
    _gate1_trace(ss, "H2_back_requested")
    ss.pop("_history_nav_failed", None)
    if not go_back(ss):
        ss["_history_nav_failed"] = "empty_back_stack"
        record_nav_history_trace(st, ss, back_button_clicked=True, history_nav_failed="empty_back_stack")
        return
    target = _apply_history_nav_transition(ss, source="history_back")
    _gate1_trace(ss, "H3_back_selected", target=target)
    record_nav_history_trace(
        st,
        ss,
        back_button_clicked=True,
        nav_target_page=target,
        active_page_source="history_back",
    )


def _on_history_forward() -> None:
    import streamlit as st

    ss = st.session_state
    init_nav_history(ss)
    _gate1_trace(ss, "forward_requested")
    ss.pop("_history_nav_failed", None)
    if not go_forward(ss):
        ss["_history_nav_failed"] = "empty_forward_stack"
        record_nav_history_trace(st, ss, forward_button_clicked=True, history_nav_failed="empty_forward_stack")
        return
    target = _apply_history_nav_transition(ss, source="history_forward")
    _gate1_trace(ss, "forward_selected", target=target)
    record_nav_history_trace(
        st,
        ss,
        forward_button_clicked=True,
        nav_target_page=target,
        active_page_source="history_forward",
    )


def flush_deferred_history_nav_save(st: Any) -> bool:
    """Persist history navigation after the target page has rendered (post-workspace)."""
    ss = st.session_state
    _gate1_trace(ss, "history_save_flush_enter")
    pending = str(ss.pop(_HISTORY_NAV_PENDING_SAVE, None) or "").strip()
    if not pending:
        return False
    try:
        from music_persistent_state import after_studio_page_change

        after_studio_page_change(st, ss, target_page=pending)
    except Exception:
        try:
            from music_persistent_state import claim_studio_page_ownership

            claim_studio_page_ownership(st, pending, session_state=ss)
        except Exception:
            pass
    record_nav_history_trace(
        st,
        ss,
        nav_target_page=pending,
        final_studio_page=ss.get("studio_page"),
    )
    _gate1_trace(ss, "history_save_flush_exit", saved_target=pending)
    return True


def navigate_studio_page(session_state: dict, page_id: str) -> bool:
    """
    Set ``studio_page`` and record history (clears forward stack).
    Snapshots page state when leaving. Returns True if the page changed.
    """
    page_id = str(page_id).strip()
    if page_id not in STUDIO_PAGE_IDS:
        _gate1_trace(session_state, "H5_navigate_invalid", requested=page_id)
        return False
    current = str(session_state.get("studio_page", "practice"))
    if current == page_id:
        _gate1_trace(
            session_state,
            "H5_navigate_noop",
            requested=page_id,
            classification="same_page_remount_noop",
        )
        return False
    from_history = bool(session_state.get(_NAV_FROM_HISTORY))
    remount_before = str(session_state.get(_HISTORY_NAV_REMOUNT_TARGET) or "").strip()
    classification = (
        "history_restoration"
        if from_history
        else "history_target_remount"
        if remount_before and page_id == remount_before
        else "genuine_user_navigation"
    )
    forward_before = _stack_page_ids(session_state, NAV_FORWARD_STACK)
    _gate1_trace(
        session_state,
        "H5_navigate_enter",
        requested=page_id,
        current_before=current,
        classification=classification,
        forward_before=forward_before,
    )
    if current == "creative" and page_id != "creative":
        # Song source radio unmounts; a later remount must not look like an
        # Active click (seen leftover from the Custom visit).
        try:
            from source_session_state import SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY

            session_state.pop(SBI_FOLLOW_ACTIVE_WIDGET_SEEN_KEY, None)
        except ImportError:
            session_state.pop("_sbi_follow_active_widget_seen", None)
    if current == "backing" and page_id != "backing":
        try:
            from creative_key_sync import seal_mission_pk_on_leave_backing

            seal_mission_pk_on_leave_backing(session_state)
        except ImportError:
            pass
        try:
            from backing_play_session import expire_backing_play_session_on_page_exit

            expire_backing_play_session_on_page_exit(
                session_state, previous_page=current, new_page=page_id
            )
        except ImportError:
            pass
        try:
            from backing_key_cycle import end_key_cycle_on_page_leave

            end_key_cycle_on_page_leave(session_state)
        except ImportError:
            pass
    if page_id == "backing":
        try:
            from backing_source_navigation import (
                BACKING_INTENT_FROM_PRACTICE,
                BACKING_INTENT_RESTORE_LAST,
                BACKING_OPEN_INTENT_KEY,
                last_valid_backing_session_survives_ordinary_nav,
                mark_generic_catalog_backing_entry,
                prepare_global_backing_navigation,
                set_backing_open_intent,
            )
            from backing_source_navigation import explicit_specialized_backing_handoff_pending

            if not session_state.get(BACKING_OPEN_INTENT_KEY):
                prepare_global_backing_navigation(session_state, from_page=current)
            # Creative Backing restore-last for Mission/Jam when still unset
            if not session_state.get(BACKING_OPEN_INTENT_KEY):
                restore_last = last_valid_backing_session_survives_ordinary_nav(session_state)
                try:
                    from backing_source_navigation import backing_restore_eligible

                    if not backing_restore_eligible(session_state):
                        restore_last = False
                except ImportError:
                    pass
                if current == "practice":
                    if restore_last:
                        set_backing_open_intent(session_state, BACKING_INTENT_RESTORE_LAST)
                    else:
                        set_backing_open_intent(session_state, BACKING_INTENT_FROM_PRACTICE)
                elif current not in ("creative", "backing"):
                    prefer_catalog_over_custom_sbi = False
                    if current == "picker":
                        try:
                            from backing_source_navigation import (
                                stale_custom_sbi_overlay_blocks_catalog_backing,
                            )

                            prefer_catalog_over_custom_sbi = (
                                stale_custom_sbi_overlay_blocks_catalog_backing(session_state)
                            )
                        except ImportError:
                            pass
                    if prefer_catalog_over_custom_sbi:
                        mark_generic_catalog_backing_entry(session_state)
                    elif explicit_specialized_backing_handoff_pending(session_state) or restore_last:
                        set_backing_open_intent(session_state, BACKING_INTENT_RESTORE_LAST)
                    else:
                        mark_generic_catalog_backing_entry(session_state)
                elif explicit_specialized_backing_handoff_pending(session_state):
                    from backing_source_navigation import mark_specialized_backing_handoff_entry

                    mark_specialized_backing_handoff_entry(session_state)
                elif restore_last:
                    # Creative → Backing: restore only when last session matches
                    # the live active source (Mission/Jam/same catalog song).
                    set_backing_open_intent(session_state, BACKING_INTENT_RESTORE_LAST)
                else:
                    # Stale Country Roads (etc.) must not hijack Love Story PK/Capo.
                    set_backing_open_intent(session_state, BACKING_INTENT_FROM_PRACTICE)
        except ImportError:
            if not session_state.get("improv_mission_backing_handoff"):
                try:
                    from backing_source_navigation import (
                        BACKING_INTENT_FROM_PRACTICE,
                        BACKING_INTENT_RESTORE_LAST,
                        set_backing_open_intent,
                    )

                    if current == "practice":
                        set_backing_open_intent(session_state, BACKING_INTENT_FROM_PRACTICE)
                    else:
                        set_backing_open_intent(session_state, BACKING_INTENT_RESTORE_LAST)
                except ImportError:
                    pass
    preserved_forward = False
    forward_reason = "history_restoration"
    if not session_state.pop(_NAV_FROM_HISTORY, False):
        if current in STUDIO_PAGE_IDS:
            save_page_snapshot(session_state, current)
            entry = _make_annotated_entry(session_state, current)
            _append_back_if_new(session_state, entry)
        # Slice 4B: history Back/Forward seals Forward for the pending target.
        # Workspace remount may re-navigate to that same target after the
        # one-shot `_studio_nav_from_history` flag was consumed — keep Forward.
        # Genuine new navigation (page_id != pending) always discards Forward.
        remount_target = str(session_state.get(_HISTORY_NAV_REMOUNT_TARGET) or "").strip()
        if remount_target and page_id == remount_target:
            # A restored Streamlit destination can mount more than once across
            # consecutive reruns.  Keep the seal idempotent until navigation
            # genuinely branches to a different destination.
            preserved_forward = True
            forward_reason = "matching_history_target_remount"
        else:
            session_state[NAV_FORWARD_STACK] = []
            forward_reason = "genuine_navigation_branch"
            # Deliberate leave cancels a pending history remount seal.
            if remount_target and page_id != remount_target:
                session_state.pop(_HISTORY_NAV_REMOUNT_TARGET, None)
                session_state.pop(_HISTORY_NAV_PENDING_SAVE, None)
            if current == "creative" or page_id != "creative":
                clear_creative_history_seal(session_state)
    # Leaving Custom page: stamp LAST_CUSTOM from the live draft even when Catalog
    # still owns Global Active (return-to-Custom must not fall back to My Progression).
    if current == "custom" and page_id != "custom":
        try:
            from songs.music_source import snapshot_last_custom_state

            snapshot_last_custom_state(session_state)
        except ImportError:
            pass
    if current == "custom" and page_id == "picker":
        try:
            from songs.music_source import promote_last_custom_for_picker_entry

            promote_last_custom_for_picker_entry(session_state)
        except ImportError:
            pass
    session_state["studio_page"] = page_id
    try:
        from pending_upload_route_precedence import release_pending_upload_resume_route

        release_pending_upload_resume_route(session_state, new_page=page_id)
    except ImportError:
        pass
    if page_id == "creative":
        sync_live_creative_history_dest(session_state)
    try:
        from music_persistent_state import mark_user_navigated_page_this_run

        mark_user_navigated_page_this_run(session_state, page_id)
    except ImportError:
        pass
    try:
        from music_phase1_write_journal import record_phase1_page_write

        record_phase1_page_write(
            session_state,
            key="studio_page",
            old_page=current,
            new_page=page_id,
            module="studio_nav_history",
            function="navigate_studio_page",
            reason="user_navigation",
            origin="user_navigation",
        )
    except ImportError:
        pass
    try:
        from music_page_cloud_durability_trace import begin_navigation_page_change_transaction

        begin_navigation_page_change_transaction(
            session_state,
            clicked_page=page_id,
            prior_page=current,
            origin="user_navigation",
        )
    except Exception:
        pass
    _nav_ss = session_state

    class _St:
        session_state = _nav_ss

    try:
        from music_persistent_state import after_studio_page_change, prepare_page_change_save_state
        from music_startup_save_suppression import set_page_change_origin

        set_page_change_origin(session_state, "user_navigation")
        prepare_page_change_save_state(session_state, page_id, st=_St(), origin="user_navigation")
        try:
            from music_page_save_pipeline_trace import record_checkpoint

            record_checkpoint(session_state, "A_post_navigate_studio_page")
        except ImportError:
            pass
        try:
            from music_studio_page_diagnostics import record_studio_page_diag

            record_studio_page_diag(
                session_state,
                clicked_page=page_id,
                page_change_origin="user_navigation",
                canonical_page_after_click=page_id,
                session_page_after_click=session_state.get("studio_page"),
            )
        except ImportError:
            pass
        try:
            from local_nav_trace import record_local_nav_checkpoint

            record_local_nav_checkpoint(
                _St(),
                "post_navigate_before_save",
                session=session_state,
                intent=page_id,
            )
        except ImportError:
            pass
        after_studio_page_change(_St(), session_state, target_page=page_id)
    except Exception:
        try:
            from music_persistent_state import claim_studio_page_ownership

            claim_studio_page_ownership(_St(), page_id, session_state=session_state)
        except Exception:
            pass
    try:
        from music_page_save_pipeline_trace import (
            navigate_impl_marker,
            record_checkpoint,
            record_pipeline_event,
        )

        record_pipeline_event(
            session_state,
            function="navigate_studio_page",
            phase="exit",
            selected_target=page_id,
            branch="user_navigation",
            extra={"navigate_impl_marker": navigate_impl_marker},
        )
        record_checkpoint(
            session_state,
            "A_post_navigate_studio_page_complete",
            extra={
                "note": "after after_studio_page_change",
            },
        )
    except ImportError:
        pass
    _gate1_trace(
        session_state,
        "H5_navigate_exit",
        requested=page_id,
        current_before=current,
        classification=classification,
        forward_before=forward_before,
        forward_after=_stack_page_ids(session_state, NAV_FORWARD_STACK),
        forward_preserved=preserved_forward or from_history,
        forward_reason=forward_reason,
    )
    return True


def go_back(session_state: dict) -> bool:
    back: list[Any] = list(session_state.get(NAV_BACK_STACK) or [])
    if not back:
        return False
    entry = _normalize_stack_entry(back.pop())
    current = str(session_state.get("studio_page", "practice"))
    forward: list[Any] = session_state.setdefault(NAV_FORWARD_STACK, [])
    if current in STUDIO_PAGE_IDS:
        leave_dest = ""
        if current == "creative":
            # Prefer sealed / last-settled dest over a Streamlit widget remount snap.
            leave_dest = str(
                session_state.get(_HISTORY_CREATIVE_DEST_SEAL)
                or session_state.get(_LIVE_CREATIVE_DEST_KEY)
                or history_destination_id(session_state)
                or ""
            )
            if leave_dest.startswith("creative::"):
                apply_creative_history_destination(session_state, leave_dest)
        save_page_snapshot(session_state, current)
        fwd_entry = _make_annotated_entry(session_state, current)
        if leave_dest.startswith("creative::"):
            fwd_entry["destination"] = leave_dest
        # Avoid adjacent Forward duplicates from remount noise.
        if not forward or history_destination_id(entry=_normalize_stack_entry(forward[-1])) != history_destination_id(
            entry=fwd_entry
        ):
            forward.append(fwd_entry)
    session_state[NAV_BACK_STACK] = back
    session_state["_studio_history_restoring_workspace"] = True
    try:
        target = restore_history_entry(session_state, entry)
        session_state["studio_page"] = target
        session_state["nav_target_page"] = target
        dest = str(entry.get("destination") or history_destination_id(entry=entry) or "")
        if target == "creative":
            apply_creative_history_destination(session_state, dest)
            set_creative_history_seal(session_state, dest)
            save_page_snapshot(session_state, "creative")
    finally:
        session_state.pop("_studio_history_restoring_workspace", None)
    _gate1_trace(session_state, "H3_go_back_complete", previous=current, target=target)
    return True


def go_forward(session_state: dict) -> bool:
    forward: list[Any] = list(session_state.get(NAV_FORWARD_STACK) or [])
    if not forward:
        return False
    entry = _normalize_stack_entry(forward.pop())
    current = str(session_state.get("studio_page", "practice"))
    if current in STUDIO_PAGE_IDS:
        leave_dest = ""
        if current == "creative":
            leave_dest = str(
                session_state.get(_HISTORY_CREATIVE_DEST_SEAL)
                or session_state.get(_LIVE_CREATIVE_DEST_KEY)
                or history_destination_id(session_state)
                or ""
            )
            if leave_dest.startswith("creative::"):
                apply_creative_history_destination(session_state, leave_dest)
        save_page_snapshot(session_state, current)
        back_entry = _make_annotated_entry(session_state, current)
        if leave_dest.startswith("creative::"):
            back_entry["destination"] = leave_dest
        _append_back_if_new(session_state, back_entry)
    session_state[NAV_FORWARD_STACK] = forward
    session_state["_studio_history_restoring_workspace"] = True
    try:
        target = restore_history_entry(session_state, entry)
        session_state["studio_page"] = target
        session_state["nav_target_page"] = target
        dest = str(entry.get("destination") or history_destination_id(entry=entry) or "")
        if target == "creative":
            apply_creative_history_destination(session_state, dest)
            set_creative_history_seal(session_state, dest)
            save_page_snapshot(session_state, "creative")
    finally:
        session_state.pop("_studio_history_restoring_workspace", None)
    _gate1_trace(session_state, "go_forward_complete", previous=current, target=target)
    return True


def render_nav_deploy_marker(st_module: Any, *, developer_mode: bool = False) -> None:
    """Dev-only deploy marker — hidden from normal use and portfolio screenshots."""
    if not developer_mode:
        return
    label = f"Navigation UI version {NAVIGATION_UI_DEPLOY_MARKER} loaded"
    st_module.markdown(
        f'<p class="ui-nav-deploy-marker" title="Streamlit Cloud branch should be dev">'
        f"{label}</p>",
        unsafe_allow_html=True,
    )


def render_floating_nav_history(
    st_module: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None] | None = None,
) -> None:
    """Floating back / forward at viewport mid-height (sticky while scrolling).

    Buttons render early in the script; CSS + pin script place Back in the
    sidebar/main gutter and Forward at the main area's right edge.
    """
    _ = rerun_fn
    init_nav_history(session_state)
    enforce_history_nav_remount_target(session_state)
    _gate1_trace(session_state, "H6_before_arrow_render")
    back_ok = can_go_back(session_state)
    fwd_ok = can_go_forward(session_state)
    session_state["back_button_rendered"] = True
    session_state["forward_button_rendered"] = True
    session_state["back_button_disabled"] = not back_ok
    session_state["forward_button_disabled"] = not fwd_ok
    record_nav_history_trace(
        st_module,
        session_state,
        back_button_rendered=True,
        forward_button_rendered=True,
        back_button_disabled=not back_ok,
        forward_button_disabled=not fwd_ok,
    )

    st_module.button(
        "← Back",
        key="studio_nav_back_btn",
        disabled=not back_ok,
        use_container_width=False,
        type="secondary",
        help="Previous page in history",
        on_click=_on_history_back,
    )
    st_module.button(
        "Forward →",
        key="studio_nav_forward_btn",
        disabled=not fwd_ok,
        use_container_width=False,
        type="secondary",
        help="Next page in history",
        on_click=_on_history_forward,
    )


def render_studio_history_toolbar(
    st_module: Any,
    session_state: dict,
    *,
    center_slot: Callable[[Any], None] | None = None,
    rerun_fn: Callable[[], None] | None = None,
) -> None:
    """Deprecated — floating nav only; center_slot ignored."""
    _ = center_slot
    render_floating_nav_history(st_module, session_state, rerun_fn=rerun_fn)


def render_sidebar_nav_history(
    sidebar: Any,
    session_state: dict,
    *,
    rerun_fn: Callable[[], None],
) -> None:
    """Deprecated: use ``render_floating_nav_history`` in the main area instead."""
    render_floating_nav_history(sidebar, session_state, rerun_fn=rerun_fn)


# Backward-compatible alias if an older deploy imported only this name.
render_main_nav_history = render_floating_nav_history

"""Creative tab ↔ workflow owner activation (Commit 3)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from music_workflow_mutation import ACTIVE_CREATIVE_VIEW_KEY

CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY = "_creative_tab_workflow_rerun_for_seq"

_TAB_TO_VIEW: dict[str, str] = {
    "Missions": "Missions",
    "Entry & Jam": "Entry & Jam",
    "Phrase / Motif": "Motifs",
    "Metrics & AI": "Metrics & AI",
    "Live Coach": "Live Coach",
    "Harmony Map": "Harmony Map",
    "Deep Harmony": "Deep Harmony",
}


def _owner_for_tab_and_entry(session: dict[str, Any], tab: str) -> str | None:
    tab = str(tab or "").strip()
    if tab == "Missions":
        return "mission_jam"
    if tab in {"Metrics & AI", "Live Coach", "Harmony Map", "Deep Harmony"}:
        return "song_based_improvisation"
    if tab == "Phrase / Motif":
        return "song_based_improvisation"
    if tab == "Entry & Jam":
        entry = str(session.get("improv_entry_mode") or "").strip()
        mapping = {
            "Song-Based Improvisation": "song_based_improvisation",
            "Style Jam Mode": "style_jam",
            "Jam Session Generator": "jam_session_generator",
        }
        return mapping.get(entry)
    return None


def creative_tab_workflow_rerun_fingerprint(session: dict[str, Any], tab: str) -> str:
    owner = _owner_for_tab_and_entry(session, tab) or ""
    view = _TAB_TO_VIEW.get(str(tab or "").strip(), str(tab or "").strip())
    try:
        from music_workflow_pending_activation import peek_pending_workflow_activation

        pending = peek_pending_workflow_activation(session) or {}
        req_seq = pending.get("request_seq")
    except ImportError:
        req_seq = None
    blob = json.dumps(
        {
            "tab": str(tab or "").strip(),
            "owner": owner,
            "view": view,
            "request_seq": req_seq,
            "page": str(session.get("studio_page") or ""),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def should_request_creative_tab_workflow_rerun(session: dict[str, Any], tab: str) -> bool:
    """One guarded rerun per pending activation request_seq (page_dispatch)."""
    try:
        from music_workflow_pending_activation import peek_pending_workflow_activation

        pending = peek_pending_workflow_activation(session)
    except ImportError:
        pending = None
    seq = (pending or {}).get("request_seq")
    if seq is None:
        return True
    if session.get(CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY) == seq:
        return False
    session[CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY] = seq
    return True


def sync_workflow_for_creative_tab(session: dict[str, Any], tab: str | None = None) -> str:
    """B4 — re-activate musical owner when Creative tab changes (view separate from owner).

    Returns ``done``, ``queued``, ``already_queued``, ``skipped``, or ``failed``.
    """
    tab_name = str(tab or session.get("improv_intelligence_tab") or "").strip()
    view = _TAB_TO_VIEW.get(tab_name, tab_name)
    session[ACTIVE_CREATIVE_VIEW_KEY] = view
    owner = _owner_for_tab_and_entry(session, tab_name)
    if not owner:
        return "skipped"
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == owner:
            return "skipped"
    except ImportError:
        pass
    try:
        from music_workflow_pending_activation import peek_pending_workflow_activation

        pending = peek_pending_workflow_activation(session)
        if pending and str(pending.get("target_owner") or "") == owner:
            if str(pending.get("active_creative_view") or "") == view:
                return "already_queued"
    except ImportError:
        pass
    try:
        from music_workflow_pending_activation import request_or_activate_workflow

        status = request_or_activate_workflow(
            session,
            target_owner=owner,
            activation_source="creative_tab_change",
            navigation_intent="creative_tab",
            active_creative_view=view,
        )
        return status
    except ImportError:
        try:
            from workflow_musical_authority import switch_workflow_owner

            switch_workflow_owner(session, owner)  # type: ignore[arg-type]
            return "done"
        except ImportError:
            return "failed"


def ensure_creative_tab_workflow_before_widgets(session: dict[str, Any]) -> str:
    """Activate workflow for the current Creative tab before sidebar widgets render."""
    tab_name = str(session.get("improv_intelligence_tab") or "").strip()
    if not tab_name:
        return "skipped"
    view = _TAB_TO_VIEW.get(tab_name, tab_name)
    owner = _owner_for_tab_and_entry(session, tab_name)
    if not owner:
        return "skipped"
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == owner:
            session[ACTIVE_CREATIVE_VIEW_KEY] = view
            return "skipped"
    except ImportError:
        pass
    try:
        from music_workflow_pending_activation import peek_pending_workflow_activation

        pending = peek_pending_workflow_activation(session)
        if pending and str(pending.get("target_owner") or "") == owner:
            return "already_queued"
    except ImportError:
        pass
    try:
        from music_workflow_pending_activation import request_or_activate_workflow

        return request_or_activate_workflow(
            session,
            target_owner=owner,
            activation_source="creative_pre_widget",
            navigation_intent="creative_tab",
            active_creative_view=view,
        )
    except ImportError:
        return sync_workflow_for_creative_tab(session, tab_name)


__all__ = [
    "CREATIVE_TAB_WORKFLOW_RERUN_FOR_SEQ_KEY",
    "creative_tab_workflow_rerun_fingerprint",
    "should_request_creative_tab_workflow_rerun",
    "sync_workflow_for_creative_tab",
    "ensure_creative_tab_workflow_before_widgets",
]

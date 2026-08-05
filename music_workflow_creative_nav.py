"""Creative tab ↔ workflow owner activation (Commit 3)."""

from __future__ import annotations

from typing import Any

from music_workflow_mutation import ACTIVE_CREATIVE_VIEW_KEY

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


def sync_workflow_for_creative_tab(session: dict[str, Any], tab: str | None = None) -> str:
    """B4 — re-activate musical owner when Creative tab changes (view separate from owner).

    Returns ``done``, ``queued``, ``skipped``, or ``failed``.
    """
    tab_name = str(tab or session.get("improv_intelligence_tab") or "").strip()
    view = _TAB_TO_VIEW.get(tab_name, tab_name)
    session[ACTIVE_CREATIVE_VIEW_KEY] = view
    owner = _owner_for_tab_and_entry(session, tab_name)
    if not owner:
        return "skipped"
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


__all__ = ["sync_workflow_for_creative_tab", "ensure_creative_tab_workflow_before_widgets"]

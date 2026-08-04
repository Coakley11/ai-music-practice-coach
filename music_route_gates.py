"""Route-first gates — skip heavy work on inactive pages/workflows/tabs."""

from __future__ import annotations

from typing import Any

ROUTE_CONTEXT_KEY = "_music_active_route_context"
INACTIVE_HEAVY_PATHS_KEY = "_music_inactive_heavy_paths"


def resolve_route_context(session: dict[str, Any]) -> dict[str, Any]:
    """Lightweight snapshot of page + Creative workflow + tab for gating."""
    page = str(session.get("studio_page") or "practice").strip().lower()
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or session.get("_improv_intelligence_tab_for_render")
        or ""
    ).strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    wf = ""
    generated = False
    try:
        from backing_workflow_context import get_backing_workflow_envelope, workflow_is_generated

        env = get_backing_workflow_envelope(session) or {}
        wf = str(env.get("workflow_type") or "").strip()
        generated = bool(workflow_is_generated(session))
    except ImportError:
        pass
    if not wf and page in {"creative", "backing"}:
        if entry == "Jam Session Generator":
            wf = "jam_session_generator"
            generated = True
        elif entry == "Style Jam Mode":
            wf = "style_jam"
            generated = True
        elif entry == "Song-Based Improvisation" or tab == "Song-Based Improvisation":
            wf = "song_based_improvisation"
        elif tab == "Missions":
            wf = "mission_jam"
    ctx = {
        "page": page,
        "creative_tab": tab,
        "entry_mode": entry,
        "workflow_type": wf,
        "generated_active": generated,
    }
    session[ROUTE_CONTEXT_KEY] = ctx
    return ctx


def should_hydrate_catalog_on_creative_page(session: dict[str, Any]) -> bool:
    """Independent generated jams must not refresh full catalog song metadata every rerun."""
    if str(session.get("studio_page") or "").strip().lower() != "creative":
        return False
    ctx = resolve_route_context(session)
    if ctx.get("generated_active"):
        return False
    entry = str(ctx.get("entry_mode") or "")
    if entry in {"Style Jam Mode", "Jam Session Generator"}:
        return False
    tab = str(ctx.get("creative_tab") or "")
    if tab in {"Missions", "Phrase / Motif", "Metrics & AI"}:
        return True
    if entry == "Song-Based Improvisation" or tab == "Song-Based Improvisation":
        return True
    if tab in {"Entry & Jam", "Live Coach", "Harmony Map", "Deep Harmonic Analyzer"}:
        return entry == "Song-Based Improvisation" or not entry
    return True


def should_hydrate_creative_session_on_backing_page(session: dict[str, Any]) -> bool:
    """Mission/style/generator backing needs creative session; plain catalog backing often does not."""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is None:
            return False
        src = str(ctx.source or "").strip()
        if src == "regular_song":
            return False
        return src in {"entry_jam", "song_improv", "mission", "custom_progression"}
    except ImportError:
        return True


def creative_tab_is_active(session: dict[str, Any], tab_name: str) -> bool:
    ctx = resolve_route_context(session)
    active = str(ctx.get("creative_tab") or "Entry & Jam").strip()
    return active == tab_name or (
        tab_name == "Entry & Jam" and active in {"", "Live Coach"}
    )


def record_inactive_heavy_path(session: dict[str, Any], path_id: str) -> None:
    """Dev counter when heavy logic runs outside its owning route (should stay zero)."""
    ctx = resolve_route_context(session)
    try:
        from music_dev_nav import dev_count

        dev_count(session, f"inactive_heavy:{path_id}")
    except ImportError:
        pass
    bucket = session.setdefault(INACTIVE_HEAVY_PATHS_KEY, [])
    if isinstance(bucket, list):
        bucket.append({"path": path_id, "page": ctx.get("page"), "tab": ctx.get("creative_tab")})


def guard_creative_tab_heavy(session: dict[str, Any], owner_tab: str, path_id: str) -> bool:
    """Return True if heavy work for ``owner_tab`` may run."""
    if creative_tab_is_active(session, owner_tab):
        return True
    record_inactive_heavy_path(session, f"{owner_tab}:{path_id}")
    return False


def should_restore_upload_analysis_session(session: dict[str, Any]) -> bool:
    """One cloud/local restore attempt per browser session unless handoff pending."""
    if session.get("_analysis_session_restore_done"):
        return False
    try:
        from analysis_session_persistence import analysis_result_ready

        if analysis_result_ready(session.get("last_analysis_result")):
            return False
    except ImportError:
        if session.get("last_analysis_result"):
            return False
    return True


def mark_upload_analysis_restore_done(session: dict[str, Any]) -> None:
    session["_analysis_session_restore_done"] = True


__all__ = [
    "INACTIVE_HEAVY_PATHS_KEY",
    "ROUTE_CONTEXT_KEY",
    "creative_tab_is_active",
    "guard_creative_tab_heavy",
    "mark_upload_analysis_restore_done",
    "record_inactive_heavy_path",
    "resolve_route_context",
    "should_hydrate_catalog_on_creative_page",
    "should_hydrate_creative_session_on_backing_page",
    "should_restore_upload_analysis_session",
]

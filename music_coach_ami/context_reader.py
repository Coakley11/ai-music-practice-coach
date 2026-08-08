"""Build read-only CoachContext from session / AMI payload — no writes."""

from __future__ import annotations

from typing import Any

from music_coach_ami.types import CoachContext


def read_coach_context(
    session_state: dict[str, Any],
    *,
    ami_ctx: dict[str, Any] | None = None,
) -> CoachContext:
    """Aggregate coaching fields from existing Music AMI snapshot builders."""
    ctx = dict(ami_ctx or {})
    snap = ctx.get("practice_snapshot") if isinstance(ctx.get("practice_snapshot"), dict) else {}

    try:
        from music_ami_context import gather_practice_ami_snapshot

        if not snap:
            snap = gather_practice_ami_snapshot(session_state, include_practice_logs=False)
    except ImportError:
        snap = snap or {}

    try:
        from music_coach_context import resolve_coach_source_page

        coach_page = str(ctx.get("coach_page") or resolve_coach_source_page(session_state))
    except ImportError:
        coach_page = str(ctx.get("coach_page") or "practice")

    minutes = snap.get("practice_minutes") or ctx.get("practice_minutes")
    try:
        minutes_int = int(minutes) if minutes is not None else None
    except (TypeError, ValueError):
        minutes_int = None

    bpm = snap.get("bpm") or ctx.get("bpm")
    try:
        bpm_int = int(bpm) if bpm is not None else None
    except (TypeError, ValueError):
        bpm_int = None

    creative_tab = str(
        session_state.get("improv_intelligence_tab")
        or session_state.get("creative_improv_intelligence_tab")
        or ctx.get("creative_tab")
        or ""
    ).strip()
    entry_mode = str(session_state.get("improv_entry_mode") or "").strip()
    creative_mode = entry_mode or creative_tab

    mission = str(
        session_state.get("improv_active_mission")
        or session_state.get("improv_mission_pick")
        or ctx.get("active_mission")
        or ""
    ).strip()

    chord = str(session_state.get("ii_selected_chord") or ctx.get("current_chord") or "").strip()
    section = str(
        snap.get("practice_focus_section")
        or ctx.get("practice_focus_section")
        or session_state.get("ii_selected_section")
        or ""
    ).strip()

    active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else {}
    title = str(active.get("title") or snap.get("title") or "").strip()
    pick = str(ctx.get("pick_key") or snap.get("pick_key") or session_state.get("active_catalog_pick_key") or "")

    original_key = str(active.get("key") or active.get("default_key") or snap.get("genre") or "").strip()
    if not original_key:
        original_key = str(snap.get("display_key") or "")  # fallback only for display

    practice_key = str(snap.get("display_key") or ctx.get("display_key") or session_state.get("display_key") or "")

    evidence = ""
    summary = snap.get("practice_log_summary")
    if isinstance(summary, dict) and summary.get("session_count"):
        evidence = f"{summary.get('session_count')} recent log sessions (summary available)."

    instrument = str(ctx.get("instrument") or session_state.get("instrument") or "").strip()
    if not instrument:
        try:
            from practice_setup_globals import GLOBAL_INSTRUMENT_KEY

            if GLOBAL_INSTRUMENT_KEY in session_state:
                instrument = str(session_state.get(GLOBAL_INSTRUMENT_KEY) or "").strip()
        except ImportError:
            pass

    level = str(ctx.get("level") or session_state.get("level") or "").strip()
    if not level:
        try:
            from practice_setup_globals import GLOBAL_LEVEL_KEY

            if GLOBAL_LEVEL_KEY in session_state:
                level = str(session_state.get(GLOBAL_LEVEL_KEY) or "").strip()
        except ImportError:
            pass

    return CoachContext(
        instrument=instrument,
        level=level,
        practice_focus=str(snap.get("focus") or ctx.get("focus") or session_state.get("focus") or ""),
        available_practice_minutes=minutes_int,
        active_song_title=title,
        active_song_pick_key=pick,
        song_original_key=original_key,
        current_practice_key=practice_key,
        active_section=section,
        current_chord=chord,
        tempo_bpm=bpm_int,
        active_mission=mission,
        creative_mode=creative_mode,
        creative_tab=creative_tab,
        studio_page=str(session_state.get("studio_page") or ""),
        coach_page=coach_page,
        recent_practice_evidence=evidence,
        extra={"routing_hint": str(ctx.get("routing_hint") or "")},
    )

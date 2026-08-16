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
    if not active and isinstance(session_state.get("active_song"), dict):
        active = session_state["active_song"]
    title = str(active.get("title") or snap.get("title") or "").strip()
    pick = str(ctx.get("pick_key") or snap.get("pick_key") or "").strip()
    if not pick:
        try:
            from music_coach_ami.chart_context_reader import resolve_authoritative_pick_key

            pick, _ = resolve_authoritative_pick_key(session_state, ami_ctx=ctx, pick_key_hint="")
        except ImportError:
            try:
                from songs.state import ACTIVE_CATALOG_PICK_KEY, reconcile_active_pick_key

                pick = str(
                    session_state.get(ACTIVE_CATALOG_PICK_KEY)
                    or reconcile_active_pick_key(session_state)
                    or ""
                ).strip()
            except ImportError:
                pick = str(session_state.get("active_catalog_pick_key") or "").strip()
    progression_summary = str(active.get("progression_summary") or snap.get("progression_summary") or "").strip()

    original_key = str(active.get("key") or active.get("default_key") or "").strip()

    try:
        from music_coach_ami.chart_context_reader import resolve_live_coach_practice_key

        practice_key, practice_key_trace = resolve_live_coach_practice_key(
            session_state,
            ami_ctx=ctx,
            practice_key_hint="",
        )
    except ImportError:
        practice_key = str(
            session_state.get("display_key")
            or ctx.get("display_key")
            or snap.get("display_key")
            or ""
        ).strip()
        practice_key_trace = {"source": "legacy_fallback", "resolved": practice_key}

    evidence = ""
    practice_log_summary: dict[str, Any] = {}
    if isinstance(ctx.get("practice_log_summary"), dict):
        practice_log_summary = dict(ctx["practice_log_summary"])
    elif isinstance(snap.get("practice_log_summary"), dict):
        practice_log_summary = dict(snap["practice_log_summary"])
    if isinstance(practice_log_summary, dict) and practice_log_summary.get("session_count"):
        evidence = f"{practice_log_summary.get('session_count')} recent log sessions (summary available)."

    snap_inst = str(snap.get("instrument") or "").strip()
    ctx_inst = str(ctx.get("instrument") or "").strip()
    try:
        from music_coach_ami.coach_instrument import instrument_provenance_trace, resolve_coach_instrument

        instrument = resolve_coach_instrument(
            session_state,
            ctx_instrument=ctx_inst,
            snapshot_instrument=snap_inst,
        )
        prov = instrument_provenance_trace(
            session_state,
            ctx_instrument=ctx_inst,
            snapshot_instrument=snap_inst,
            resolved=instrument,
        )
    except ImportError:
        instrument = ctx_inst or snap_inst or str(session_state.get("instrument") or "").strip()
        prov = {}
    if not instrument:
        instrument = str(session_state.get("instrument") or ctx_inst or snap_inst).strip()

    level = str(ctx.get("level") or session_state.get("level") or "").strip()
    if not level:
        try:
            from practice_setup_globals import GLOBAL_LEVEL_KEY

            if GLOBAL_LEVEL_KEY in session_state:
                level = str(session_state.get(GLOBAL_LEVEL_KEY) or "").strip()
        except ImportError:
            pass

    try:
        from music_coach_ami.chart_context_reader import resolve_coach_chart_snapshot

        chart_snapshot = resolve_coach_chart_snapshot(
            session_state,
            ami_ctx=ctx,
            active_section=section,
            pick_key=pick,
            song_original_key=original_key,
            practice_key=practice_key,
        )
    except ImportError:
        chart_snapshot = {}

    if chart_snapshot.get("practice_key"):
        practice_key = str(chart_snapshot.get("practice_key") or practice_key)

    practice_focus = str(snap.get("focus") or ctx.get("focus") or session_state.get("focus") or "")
    extra = {
        "routing_hint": str(ctx.get("routing_hint") or ""),
        "instrument_provenance": prov,
        "snapshot_instrument": snap_inst,
        "practice_log_summary": practice_log_summary,
        "chart_snapshot": chart_snapshot,
        "practice_key_trace": practice_key_trace,
        # Read-only session handle for written-key / capo SSOT (no chart writes).
        "session_ref": session_state,
    }
    try:
        from practice_focus_policy import (
            category_for_focus,
            format_focus_prompt_block,
            profile_as_dict,
            resolve_focus_profile,
        )

        live_focus = ""
        if "focus" in session_state:
            try:
                from practice_setup_globals import get_active_focus

                live_focus = str(get_active_focus(session_state) or "").strip()
            except ImportError:
                live_focus = str(session_state.get("focus") or "").strip()
        if live_focus:
            practice_focus = live_focus
        inst_for_focus = instrument or str(session_state.get("instrument") or "")
        extra["practice_focus_prompt"] = format_focus_prompt_block(
            inst_for_focus, practice_focus, role="ami"
        )
        extra["practice_focus_category"] = category_for_focus(practice_focus)
        profile = resolve_focus_profile(inst_for_focus, practice_focus)
        extra["practice_focus_profile"] = {
            "label": profile.label,
            "category": profile.category,
            "preferred_metric_ids": list(profile.preferred_metric_ids),
            "score_keys": list(profile.score_keys),
        }
        extra["practice_focus_profile_full"] = profile_as_dict(profile)
    except ImportError:
        pass

    return CoachContext(
        instrument=instrument,
        level=level,
        practice_focus=practice_focus,
        available_practice_minutes=minutes_int,
        active_song_title=title,
        active_song_pick_key=pick,
        song_original_key=original_key,
        current_practice_key=practice_key,
        active_section=section,
        current_chord=chord,
        progression_summary=progression_summary,
        tempo_bpm=bpm_int,
        active_mission=mission,
        creative_mode=creative_mode,
        creative_tab=creative_tab,
        studio_page=str(session_state.get("studio_page") or ""),
        coach_page=coach_page,
        recent_practice_evidence=evidence,
        extra=extra,
    )

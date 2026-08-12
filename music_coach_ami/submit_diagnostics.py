"""Developer diagnostics for Music Coach submit → routed pipeline."""

from __future__ import annotations

from typing import Any

from music_coach_ami.types import CoachContext, CoachRequest, CoachResponse


def coach_context_fields_available(ctx: CoachContext) -> dict[str, Any]:
    """Non-empty CoachContext fields present for this submit (read-only snapshot)."""
    out: dict[str, Any] = {}
    # Avoid dataclasses.asdict — CoachContext.extra may hold a live session_ref
    # (Streamlit SessionStateProxy) that is unsafe to deep-copy into diagnostics.
    for key in (
        "instrument",
        "level",
        "practice_focus",
        "available_practice_minutes",
        "active_song_title",
        "active_song_pick_key",
        "song_original_key",
        "current_practice_key",
        "active_section",
        "current_chord",
        "progression_summary",
        "tempo_bpm",
        "active_mission",
        "creative_mode",
        "creative_tab",
        "studio_page",
        "coach_page",
        "recent_practice_evidence",
    ):
        val = getattr(ctx, key, None)
        if val is None or val == "" or val == []:
            continue
        out[key] = val
    extra = ctx.extra if isinstance(ctx.extra, dict) else {}
    if extra:
        safe_extra = {
            k: v
            for k, v in extra.items()
            if k != "session_ref" and not (k == "practice_log_summary" and not v)
        }
        # Keep compact chart + practice-key traces for ?dev=1.
        if safe_extra:
            out["extra"] = safe_extra
    return out


def _pipeline_success_flags(response: CoachResponse | None) -> dict[str, Any]:
    if response is None:
        return {
            "coach_response_success": False,
            "written_music_context_success": False,
            "composition_success": False,
            "notation_success": False,
            "instant_insight_staging_success": False,
        }
    diag = response.diagnostics if isinstance(response.diagnostics, dict) else {}
    chart = diag.get("chart_transport_at_solver") if isinstance(diag.get("chart_transport_at_solver"), dict) else {}
    wmc = diag.get("written_music_context") if isinstance(diag.get("written_music_context"), dict) else {}
    chords = list(diag.get("effective_concert_chords") or chart.get("active_section_chords") or [])[:5]
    return {
        "coach_response_success": True,
        "written_music_context_success": bool(wmc) or bool(diag.get("practice_concert_key")),
        "composition_success": bool(diag.get("bars_generated") or diag.get("notation_abc_present")),
        "composition_bar_count": diag.get("bars_generated"),
        "notation_success": bool(getattr(response, "notation_abc", None)),
        "chart_available": bool(chart.get("chart_available")),
        "chart_source": chart.get("chart_source"),
        "effective_chords": chords,
        "practice_key_trace": diag.get("practice_key_trace"),
        "abc_key_field": diag.get("abc_key_field"),
        "fallback_reason": diag.get("fallback_reason"),
    }



def build_music_coach_submit_diagnostics(
    req: CoachRequest,
    response: CoachResponse | None,
    *,
    result_path: str,
    session_state: dict[str, Any] | None = None,
    structured_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    solver_name = ""
    response_intent = ""
    if response is not None:
        solver_name = str(response.source_solver or "").strip()
        response_intent = response.intent.value

    scale_fields: dict[str, Any] = {}
    if response is not None and isinstance(response.diagnostics, dict):
        for key in (
            "tonic",
            "preferred_spelling",
            "scale_type",
            "notation_abc_present",
            "scale_practice_spec",
            "instrument_provenance",
            "chart_transport_at_solver",
            "fallback_reason",
            "practice_concert_key",
            "written_key",
            "abc_key_field",
            "composition_bar_count",
            "bars_generated",
            "written_music_context",
            "practice_key_trace",
            "effective_concert_chords",
        ):
            if key in response.diagnostics:
                scale_fields[key] = response.diagnostics[key]

    # Prefer context practice-key trace when solver did not echo it.
    extra = req.context.extra if isinstance(req.context.extra, dict) else {}
    if "practice_key_trace" not in scale_fields and isinstance(extra.get("practice_key_trace"), dict):
        scale_fields["practice_key_trace"] = dict(extra["practice_key_trace"])

    try:
        from music_coach_ami.chart_context_transport import (
            build_bass_line_chart_dev_summary,
            build_chart_context_lifecycle_trace,
            session_deploy_sha,
        )

        chart_lifecycle = build_chart_context_lifecycle_trace(req, session_state=session_state)
        bass_line_chart_dev = build_bass_line_chart_dev_summary(
            req,
            session_state=session_state,
            solver_diagnostics=response.diagnostics if response is not None else None,
        )
        deploy = session_deploy_sha(session_state)
    except ImportError:
        chart_lifecycle = {}
        bass_line_chart_dev = {}
        deploy = {}

    fail = dict(structured_failure or {})
    pipeline_flags = _pipeline_success_flags(response)

    return {
        "raw_question": req.raw_question,
        "normalized_question": req.normalized_question,
        "coach_intent": req.intent.value,
        "confidence": req.confidence,
        "entities": {
            "instrument": req.entities.instrument,
            "skill_topic": req.entities.skill_topic,
            "feature_id": req.entities.feature_id,
            "theory_topic": req.entities.theory_topic,
        },
        "constraints": {
            "requested_duration_minutes": req.constraints.requested_duration_minutes,
            "tone_focus": req.constraints.tone_focus,
            "improvisation_focus": req.constraints.improvisation_focus,
        },
        "solver": solver_name,
        "result_path": result_path,
        "response_intent": response_intent,
        "coach_context_used": coach_context_fields_available(req.context),
        "legacy_intent_hint": req.legacy_intent_hint,
        **scale_fields,
        "notation_abc_present": scale_fields.get(
            "notation_abc_present",
            bool(getattr(response, "notation_abc", None)) if response else False,
        ),
        "chart_context_lifecycle": chart_lifecycle,
        "bass_line_chart_dev": bass_line_chart_dev,
        "insight_staged": False,
        "insight_rendered_on_page": False,
        "duplicate_suppressed": False,
        "deploy_sha": deploy.get("deploy_sha_short") or deploy.get("repo_head_sha") or "",
        "deploy_sha_full": deploy.get("deploy_sha_full") or deploy.get("repo_head_sha") or "",
        "deploy_branch": deploy.get("deploy_branch") or "",
        **pipeline_flags,
        "structured_coach_failure_stage": fail.get("stage") or None,
        "structured_coach_exception_type": fail.get("exception_type") or None,
        "structured_coach_exception_message": fail.get("exception_message") or None,
    }

"""Reliable Command Center handoff for Analyze My Practice."""

from __future__ import annotations

from typing import Any

PRACTICE_ANALYSIS_CC_TITLE = "Music Practice Log Analysis"
PRACTICE_ANALYSIS_CC_EVENT = "practice_log_analysis"
PRACTICE_ANALYSIS_CC_ROUTE = "practice_history_analysis"

_LAST_CC_HANDOFF_TRACE_KEY = "_practice_log_cc_handoff_trace"


def enrich_practice_analysis_handoff_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Structured handoff fields Command Center and AMI Continue expect."""
    safety = payload.get("safety_checks") if isinstance(payload.get("safety_checks"), dict) else {}
    return {
        "analysis_type": PRACTICE_ANALYSIS_CC_ROUTE,
        "title": PRACTICE_ANALYSIS_CC_TITLE,
        "progress_report": payload.get("progress_report"),
        "practice_history_payload": {
            "practice_log_summary": payload.get("practice_log_summary"),
            "upload_analysis_summary": payload.get("upload_analysis_summary"),
            "tone_history_summary": payload.get("tone_history_summary"),
            "multitrack_export_summary": payload.get("multitrack_export_summary"),
            "recent_sessions": payload.get("recent_sessions"),
            "safety_checks": payload.get("safety_checks"),
            "diagnostics": payload.get("diagnostics"),
            "generated_at": payload.get("generated_at"),
        },
        "log_page_summary": payload.get("log_page_summary"),
        "recent_sessions": payload.get("recent_sessions"),
        "tone_history": payload.get("tone_history") or payload.get("tone_history_summary"),
        "upload_analysis_summary": payload.get("upload_analysis_summary"),
        "multitrack_export_summary": payload.get("multitrack_export_summary"),
        "practice_log_summary": payload.get("practice_log_summary"),
        "user_request": "analyze_practice",
        "routing_hint": PRACTICE_ANALYSIS_CC_ROUTE,
        "intent": PRACTICE_ANALYSIS_CC_ROUTE,
        "display_category": "analysis_handoff",
        "handoff_kind": PRACTICE_ANALYSIS_CC_EVENT,
        "handoff_title": PRACTICE_ANALYSIS_CC_TITLE,
        "raw_audio_excluded": bool(safety.get("raw_audio_excluded", True)),
        "base64_excluded": bool(safety.get("base64_excluded", True)),
        "blob_fields_excluded": bool(safety.get("blob_fields_excluded", True)),
    }


def _command_center_activity_count() -> int | None:
    try:
        from suite_storage_supabase import load_active_resume_items

        rows = load_active_resume_items(limit=40)
        return len(rows) if isinstance(rows, list) else None
    except Exception:
        return None


def _persist_handoff_trace(session_state: dict[str, Any], trace: dict[str, Any]) -> None:
    session_state[_LAST_CC_HANDOFF_TRACE_KEY] = trace


def submit_practice_analysis_command_center_handoff(
    st: Any,
    session_state: dict[str, Any],
    *,
    entries: list[dict[str, Any]] | None = None,
    window_days: int = 14,
) -> dict[str, Any]:
    """
    Build synthesis payload, cache Log-page summary, and write Command Center activity.

    Returns a result dict with ``handoff_success`` reflecting real write status.
    """
    from music_coach_context import build_source_state
    from practice_log_ami import build_practice_log_ami_payload
    from practice_history_synthesis import store_latest_practice_analysis
    from practice_log_state import load_entries
    from suite_analytical_question import (
        build_submit_context,
        submit_practice_log_analysis_handoff,
    )

    if entries is None:
        entries = load_entries(session_state)

    payload = build_practice_log_ami_payload(
        session_state,
        entries=entries,
        window_days=window_days,
        st=st,
    )
    session_state["_practice_log_ami_payload"] = payload
    session_state["practice_log_ami_payload"] = payload
    store_latest_practice_analysis(session_state, payload)

    question = (
        "Analyze my practice history. What patterns are showing up, what should I focus on next, "
        "and what should my next 30-minute session look like?"
    )
    handoff_ctx = enrich_practice_analysis_handoff_context(payload)
    ctx = build_submit_context(
        "music",
        "log",
        session_state,
        context_extra_builder=lambda: {**payload, **handoff_ctx},
    )
    try:
        from music_ami_context import build_music_applied_math_context, finalize_music_context_for_send

        full = build_music_applied_math_context("log", session_state, question=question)
        full.update(ctx)
        finalize_music_context_for_send(full, session_state, question=question, coach_page="log")
        ctx = full
    except Exception:
        pass

    source_state = None
    try:
        source_state = build_source_state("log", session_state)
    except Exception:
        pass

    result = submit_practice_log_analysis_handoff(
        source_page="log",
        question=question,
        context=ctx,
        context_summary=PRACTICE_ANALYSIS_CC_TITLE,
        source_state=source_state,
        session_state=session_state,
    )

    handoff_success = bool(result.get("handoff_success"))
    store_latest_practice_analysis(session_state, payload, handoff_result=result, handoff_success=handoff_success)

    cc_trace = {
        "attempted_at": result.get("submitted_at"),
        "success": handoff_success,
        "duplicate": bool(result.get("duplicate")),
        "activity_id": result.get("resume_key") or result.get("question_id"),
        "activity_key": result.get("resume_key"),
        "payload_title": PRACTICE_ANALYSIS_CC_TITLE,
        "route_type": PRACTICE_ANALYSIS_CC_ROUTE,
        "event_type": PRACTICE_ANALYSIS_CC_EVENT,
        "question_id": result.get("question_id"),
        "resume_upsert_ok": bool(result.get("resume_upsert_ok")),
        "activity_recorded": bool(result.get("activity_recorded")),
        "activity_skipped_reason": "duplicate_cooldown" if result.get("duplicate") and not result.get("activity_recorded") else "",
        "context_blob_stored": bool(result.get("context_blob_stored")),
        "analysis_run_id": result.get("analysis_run_id"),
        "insight_id": result.get("insight_id"),
        "action_url": result.get("action_url"),
        "updated_at": result.get("report_generated_at") or result.get("submitted_at"),
        "generated_at": result.get("report_generated_at"),
        "report_date": str(result.get("report_generated_at") or "")[:10],
        "resume_upsert_result": bool(result.get("resume_upsert_ok")),
        "music_resume_upsert_result": bool(result.get("music_resume_ok")),
        "activity_record_result": bool(result.get("activity_recorded")),
        "context_blob_id": result.get("analysis_run_id") or result.get("question_id"),
        "record_trace": result.get("record_trace") if isinstance(result.get("record_trace"), dict) else {},
        "error": str(result.get("handoff_error") or ""),
        "command_center_activity_count": _command_center_activity_count(),
    }
    _persist_handoff_trace(session_state, cc_trace)
    session_state["_practice_log_analyze_handoff_trace"] = {
        **cc_trace,
        "title": result.get("continue_title") or PRACTICE_ANALYSIS_CC_TITLE,
        "session_count": (
            (result.get("context") or {}).get("practice_log_summary") or {}
        ).get("session_count")
        if isinstance(result.get("context"), dict)
        else None,
    }
    return {**result, "handoff_success": handoff_success, "cc_trace": cc_trace}

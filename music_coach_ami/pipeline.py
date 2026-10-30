"""End-to-end coach pipeline: route → solve → compose."""

from __future__ import annotations

from typing import Any

from music_coach_ami.router import route_question
from music_coach_ami.solvers import SOLVER_REGISTRY
from music_coach_ami.types import CoachIntent, CoachRequest, CoachResponse

_PIPELINE_INTENTS = frozenset(SOLVER_REGISTRY.keys())


def run_coach_submit(
    question: str,
    session_state: dict[str, Any] | None = None,
    *,
    ami_ctx: dict[str, Any] | None = None,
) -> tuple[CoachRequest, CoachResponse | None]:
    """Route + solve; returns (request, response) where response is None → legacy Command Center path."""
    from music_coach_ami import conversation_state as _conv
    from music_coach_ami.exercise_revision import handle_revision
    from music_coach_ami.session_scope import ensure_owner

    ensure_owner(session_state)   # state remembered for another account / workspace is dropped before anything reads it
    from music_coach_ami.exercise_revision import stale_song_response

    revised, rewrite = stale_song_response(question, session_state, ami_ctx), ""
    if revised is None:
        revised, rewrite = handle_revision(question, session_state)
    if revised is not None:
        req = route_question(question, session_state, ami_ctx=ami_ctx)
        _conv.record_turn(session_state, question, revised.direct_answer, exercise_id=str(revised.diagnostics.get("generated_exercise_id") or ""))
        return req, revised
    if rewrite:
        question = rewrite   # bare "add accents" → "accent the downbeats", disclosed in the answer below
    ami_ctx = _with_working_tempo(question, session_state, ami_ctx)
    req, response = _run_coach_submit_routed(question, session_state, ami_ctx, rewritten=bool(rewrite))
    if rewrite and response is not None and response.diagnostics.get("generated_exercise_id"):
        response.direct_answer = (
            "_You didn't say which notes to accent, so I accented the downbeats — say “accent the guide tones” (or another group) to change that._"
            + chr(10) * 2 + response.direct_answer
        )
    _remember(question, session_state, response)
    return req, response


def _with_working_tempo(question: str, session_state: Any, ami_ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    """A follow-up on the working exercise keeps its tempo instead of falling back to the page's BPM."""
    try:
        from music_coach_ami import conversation_state as _conv
        from music_coach_ami.exercise_followup import parse_followup

        tempo = _conv.working_tempo(session_state)
        if tempo and parse_followup(question) is not None:
            return {**(ami_ctx or {}), "bpm": tempo}
    except Exception:
        pass
    return ami_ctx


def _remember(question: str, session_state: Any, response: CoachResponse | None) -> None:
    """Record the turn, and any structured exercise it produced as a new version of the working exercise."""
    try:
        from music_coach_ami import conversation_state as _conv

        if response is None:
            _conv.record_turn(session_state, question, "(answered by the general coach)")
            return
        diag = response.diagnostics or {}
        ex = diag.get("generated_exercise")
        ex_id = ""
        if isinstance(ex, dict) and ex.get("id") and diag.get("last_exercise_stored") and not diag.get("exercise_followup_failed"):
            ex_id = str(ex["id"])
            tempo = _conv.tempo_of_abc(response.notation_abc) or int(ex.get("tempo_bpm") or 0) or _conv.DEFAULT_BPM
            ex["tempo_bpm"] = tempo   # the structured exercise carries the tempo its notation was rendered at
            _conv.push_version(
                session_state, ex, tempo_bpm=tempo, abc=response.notation_abc, sections=list(response.notation_abc_sections or []),
                label=question, action=diag.get("open_in_missions") if isinstance(diag.get("open_in_missions"), dict) else None,
            )
        _conv.record_turn(session_state, question, response.direct_answer, exercise_id=ex_id)
    except Exception:
        pass


def _run_coach_submit_routed(
    question: str, session_state: dict[str, Any] | None, ami_ctx: dict[str, Any] | None, *, rewritten: bool = False,
) -> tuple[CoachRequest, CoachResponse | None]:
    req = route_question(question, session_state, ami_ctx=ami_ctx)
    if req.intent not in _PIPELINE_INTENTS or req.intent == CoachIntent.FALLBACK:
        return req, None
    solver = SOLVER_REGISTRY.get(req.intent)
    if solver is None:
        return req, None
    response = solver(req)
    if response is None:
        return req, None
    try:
        from music_coach_ami.song_grounding import attach_song_grounding

        response = attach_song_grounding(req, response)
    except Exception:
        pass
    response.diagnostics = {
        **response.diagnostics,
        "router_confidence": req.confidence,
        "entities": {
            "instrument": req.entities.instrument,
            "skill_topic": req.entities.skill_topic,
            "feature_id": req.entities.feature_id,
        },
        "constraints": {
            "requested_duration_minutes": req.constraints.requested_duration_minutes,
            "tone_focus": req.constraints.tone_focus,
            "improvisation_focus": req.constraints.improvisation_focus,
        },
        "context_coach_page": req.context.coach_page,
        "legacy_intent_hint": req.legacy_intent_hint,
    }
    try:
        from music_coach_ami.claude_enrichment import maybe_enrich_song_coaching

        response = maybe_enrich_song_coaching(req, response, {} if session_state is None else session_state)
    except Exception:
        pass
    return req, response


def run_coach_pipeline(
    question: str,
    session_state: dict[str, Any] | None = None,
    *,
    ami_ctx: dict[str, Any] | None = None,
) -> CoachResponse | None:
    """Run router + specialized solver; returns None to fall back to legacy instant solver."""
    _, response = run_coach_submit(question, session_state, ami_ctx=ami_ctx)
    return response


def coach_response_to_legacy_route(response: CoachResponse) -> tuple[str, str]:
    """Map CoachResponse to (problem_type, model_name) for Applied Math insight staging."""
    return response.intent.value, response.source_solver or "MusicCoachAMI"

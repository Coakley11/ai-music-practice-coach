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
    req = route_question(question, session_state, ami_ctx=ami_ctx)
    if req.intent not in _PIPELINE_INTENTS or req.intent == CoachIntent.FALLBACK:
        return req, None
    solver = SOLVER_REGISTRY.get(req.intent)
    if solver is None:
        return req, None
    response = solver(req)
    if response is None:
        return req, None
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

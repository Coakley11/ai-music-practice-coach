"""Developer diagnostics for Music Coach submit → routed pipeline."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from music_coach_ami.types import CoachContext, CoachRequest, CoachResponse


def coach_context_fields_available(ctx: CoachContext) -> dict[str, Any]:
    """Non-empty CoachContext fields present for this submit (read-only snapshot)."""
    out: dict[str, Any] = {}
    for key, val in asdict(ctx).items():
        if key == "extra":
            if isinstance(val, dict) and val:
                out[key] = val
            continue
        if val is None or val == "" or val == []:
            continue
        out[key] = val
    return out


def build_music_coach_submit_diagnostics(
    req: CoachRequest,
    response: CoachResponse | None,
    *,
    result_path: str,
) -> dict[str, Any]:
    solver_name = ""
    response_intent = ""
    if response is not None:
        solver_name = str(response.source_solver or "").strip()
        response_intent = response.intent.value

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
    }

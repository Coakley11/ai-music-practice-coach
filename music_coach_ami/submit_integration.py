"""Stage routed Music Coach answers into the existing AMI insight UI."""

from __future__ import annotations

from typing import Any

from music_coach_ami.types import CoachRequest, CoachResponse


def stage_routed_music_coach_insight(
    st: Any,
    session_state: dict[str, Any],
    *,
    question: str,
    source_page: str,
    coach_req: CoachRequest,
    coach_resp: CoachResponse,
    diagnostics: dict[str, Any],
    question_id: str = "",
    source_state: dict[str, Any] | None = None,
) -> str:
    """Persist pending insight for main-panel card; returns insight_id."""
    from applied_math_return_insight import (
        SESSION_PENDING_KEY,
        build_return_insight_payload,
        stage_pending_insight,
        store_applied_math_insight,
    )
    from music_ami_instant_solver import MusicSolverResult, MusicSolverRoute

    markdown = coach_resp.composed_markdown()
    problem_type = coach_resp.intent.value
    solver_name = str(coach_resp.source_solver or "MusicCoachAMI")

    route = MusicSolverRoute(
        problem_type=problem_type,
        model_name=solver_name,
        model_rationale=f"Routed coach intent `{coach_resp.intent.value}`.",
    )
    result = MusicSolverResult(
        short_answer=markdown,
        math_idea=f"Structured solver: {solver_name}",
        problem_type=problem_type,
        model_name=solver_name,
        variables=str(coach_resp.diagnostics),
        assumptions=[f"Router confidence: {coach_resp.diagnostics.get('router_confidence', coach_resp.confidence)}"],
        confidence_pct=int(min(95, max(60, coach_resp.confidence * 100))),
        computed=dict(coach_resp.diagnostics),
    )
    payload = build_return_insight_payload(
        question=question,
        source_app="music",
        source_page=source_page,
        question_id=question_id,
        route=route,
        result=result,
        context={"coach_page": coach_req.context.coach_page},
    )
    insight = payload.to_dict()
    insight["canonical_instant"] = True
    insight["coach_submit_diagnostics"] = dict(diagnostics)
    insight["model_name"] = solver_name
    insight["method"] = f"Structured solver: {solver_name}"
    if getattr(coach_resp, "notation_abc", None):
        insight["notation_abc"] = str(coach_resp.notation_abc or "")

    iid = store_applied_math_insight(
        insight,
        source_state=source_state,
        st=st,
    )
    if not iid:
        iid = str(insight.get("insight_id") or "").strip()
    try:
        if getattr(st, "session_state", None) is not session_state:
            st.session_state = session_state
    except Exception:
        pass
    stage_pending_insight(st, insight, return_context=source_state)
    session_state[SESSION_PENDING_KEY] = insight
    session_state["_ami_insight_return_preserve"] = True
    session_state["_ami_music_instant_canonical"] = {
        "insight_id": iid,
        "question_id": question_id,
        "result_path": diagnostics.get("result_path"),
    }
    session_state["_ami_submit_render_insight_this_run"] = True
    session_state["_ami_last_submit_source_page"] = source_page
    session_state["_ami_force_insight_render"] = True
    return iid

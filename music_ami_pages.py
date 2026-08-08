"""Music AMI send-time context promotion — dispatch by coach page."""

from __future__ import annotations

from typing import Any

from music_coach_context import COACH_PAGE_IDS, resolve_coach_source_page


def _coach_key(source_page: str) -> str:
    page = str(source_page or "").strip().lower()
    if page in COACH_PAGE_IDS:
        return page
    return resolve_coach_source_page({"studio_page": page})


def build_music_send_diagnostics(ctx: dict[str, Any], *, question: str = "") -> dict[str, Any]:
    from music_ami_context import detect_music_send_intent

    snap = ctx.get("practice_snapshot") if isinstance(ctx.get("practice_snapshot"), dict) else {}
    diag: dict[str, Any] = {
        "music_send_intent": detect_music_send_intent(question, ctx.get("coach_page") or ctx.get("source_page") or ""),
        "routing_hint": str(ctx.get("routing_hint") or ""),
        "question_song": str(ctx.get("question_song") or ""),
        "active_song_title": str((ctx.get("active_song") or {}).get("title") or snap.get("title") or ""),
        "pick_key": str(ctx.get("pick_key") or snap.get("pick_key") or ""),
        "practice_focus_section": str(ctx.get("practice_focus_section") or snap.get("practice_focus_section") or ""),
        "instrument": str(ctx.get("instrument") or ""),
        "practice_snapshot_present": bool(snap),
    }
    try:
        from music_coach_ami.pipeline import run_coach_submit

        req, resp = run_coach_submit(question, {}, ami_ctx=ctx)
        diag["coach_intent"] = req.intent.value
        diag["coach_confidence"] = req.confidence
        diag["coach_solver"] = str(resp.source_solver or "") if resp is not None else req.legacy_intent_hint
        diag["coach_entities"] = {
            "instrument": req.entities.instrument,
            "skill_topic": req.entities.skill_topic,
            "feature_id": req.entities.feature_id,
        }
    except ImportError:
        pass
    return diag


def promote_music_ami_context_at_send(
    ctx: dict[str, Any],
    session_state: dict[str, Any],
    *,
    source_page: str,
    question: str = "",
) -> dict[str, Any]:
    """Dispatch page-specific Music AMI context promotion at send time."""
    from music_ami_context import finalize_music_context_for_send

    coach = _coach_key(source_page)
    ctx["coach_page"] = coach
    finalize_music_context_for_send(ctx, session_state, question=question, coach_page=coach)
    diag = build_music_send_diagnostics(ctx, question=question)
    ctx["music_send_diagnostics"] = diag
    return diag

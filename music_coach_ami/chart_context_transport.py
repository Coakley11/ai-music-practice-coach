"""Chart-context lifecycle diagnostics for Music Coach submit (developer-only)."""

from __future__ import annotations

from typing import Any

from music_coach_ami.types import CoachContext, CoachRequest


def resolve_repo_head_sha() -> str:
    try:
        from suite_deploy_marker import resolve_git_commit_full

        return str(resolve_git_commit_full() or "").strip()
    except ImportError:
        return ""


def session_deploy_sha(session_state: dict[str, Any] | None) -> dict[str, str]:
    from music_coach_ami.session_access import as_session_mapping

    session = as_session_mapping(session_state)
    return {
        "deploy_sha_short": str(session.get("_studio_ui_release_sha") or "").strip(),
        "deploy_sha_full": str(session.get("_music_deploy_full_sha") or "").strip(),
        "deploy_branch": str(session.get("_music_deploy_branch") or "").strip(),
        "repo_head_sha": resolve_repo_head_sha(),
    }


def chart_snapshot_from_context(ctx: CoachContext | None) -> dict[str, Any]:
    if ctx is None:
        return {}
    extra = ctx.extra if isinstance(ctx.extra, dict) else {}
    snap = extra.get("chart_snapshot")
    return dict(snap) if isinstance(snap, dict) else {}


def build_chart_context_boundary_report(
    *,
    label: str,
    ctx: CoachContext | None,
) -> dict[str, Any]:
    snap = chart_snapshot_from_context(ctx)
    chords = list(snap.get("active_section_chords") or [])
    return {
        "boundary": label,
        "active_song_title": str(getattr(ctx, "active_song_title", "") or ""),
        "active_song_pick_key": str(getattr(ctx, "active_song_pick_key", "") or ""),
        "extra_present": isinstance(getattr(ctx, "extra", None), dict),
        "chart_snapshot_present": bool(snap),
        "chart_available": bool(snap.get("chart_available")),
        "chart_source": str(snap.get("chart_source") or ""),
        "resolved_pick_key": str(snap.get("resolved_pick_key") or ""),
        "section_names": list(snap.get("section_names") or []),
        "active_section": str(snap.get("active_section") or getattr(ctx, "active_section", "") or ""),
        "active_section_chord_count": len(chords),
        "active_section_chords_preview": chords[:4],
    }


def build_chart_context_lifecycle_trace(
    req: CoachRequest,
    *,
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot chart context at CoachRequest construction (post read_coach_context)."""
    snap = chart_snapshot_from_context(req.context)
    solver_entrance = {
        "extra_present": isinstance(req.context.extra, dict),
        "chart_snapshot_present": bool(snap),
        "chart_available": bool(snap.get("chart_available")),
        "active_section_chord_count": len(snap.get("active_section_chords") or []),
    }
    return {
        **session_deploy_sha(session_state),
        "context_reader_owner": "music_coach_ami.context_reader.read_coach_context",
        "after_read_coach_context": build_chart_context_boundary_report(
            label="after_read_coach_context",
            ctx=req.context,
        ),
        "at_coach_request": build_chart_context_boundary_report(
            label="at_coach_request",
            ctx=req.context,
        ),
        "at_solver_entrance_template": solver_entrance,
        "pick_key_trace": snap.get("pick_key_trace") if isinstance(snap.get("pick_key_trace"), dict) else {},
        "candidate_sources": snap.get("candidate_sources")
        if isinstance(snap.get("candidate_sources"), dict)
        else {},
    }


def build_bass_line_chart_dev_summary(
    req: CoachRequest,
    *,
    session_state: dict[str, Any] | None = None,
    solver_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact developer panel payload for bass-line chart transport."""
    snap = chart_snapshot_from_context(req.context)
    solver_diag = dict(solver_diagnostics or {})
    chords = list(snap.get("active_section_chords") or [])
    deploy = session_deploy_sha(session_state)
    return {
        **deploy,
        "title": req.context.active_song_title,
        "pick_key": req.context.active_song_pick_key or snap.get("resolved_pick_key"),
        "chart_source": snap.get("chart_source"),
        "chart_available": snap.get("chart_available"),
        "practice_key": snap.get("practice_key") or req.context.current_practice_key,
        "original_key": snap.get("original_key") or req.context.song_original_key,
        "sections_source_key": snap.get("sections_source_key"),
        "transposed_to_practice_key": snap.get("transposed_to_practice_key"),
        "active_section": snap.get("active_section") or req.context.active_section,
        "chord_count": len(chords),
        "chords_preview": chords[:6],
        "pick_key_trace": snap.get("pick_key_trace"),
        "candidate_sources": snap.get("candidate_sources"),
        "solver_chart_transport": solver_diag.get("chart_transport_at_solver"),
        "fallback_reason": solver_diag.get("fallback_reason"),
        "notation_abc_present": bool(solver_diag.get("notation_abc_present")),
        "resolved_instrument": solver_diag.get("resolved_instrument") or req.context.instrument,
        "written_key": solver_diag.get("written_key"),
        "written_chords_preview": list(solver_diag.get("written_chords") or [])[:6],
        "notation_clef": solver_diag.get("notation_clef"),
        "capo_fret": solver_diag.get("capo_fret"),
        "capo_shape_key": solver_diag.get("capo_shape_key"),
        "abc_key_field": solver_diag.get("abc_key_field"),
        "written_transposition_applied": solver_diag.get("written_transposition_applied"),
    }


def format_bass_line_chart_dev_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "**Bass-line chart context**",
        f"- deploy SHA: `{summary.get('deploy_sha_short') or '—'}` "
        f"(full `{str(summary.get('deploy_sha_full') or '—')[:12]}`)",
        f"- repo HEAD: `{str(summary.get('repo_head_sha') or '—')[:12]}`",
        f"- title: {summary.get('title') or '—'}",
        f"- instrument: `{summary.get('resolved_instrument') or '—'}`",
        f"- pick: `{summary.get('pick_key') or '—'}`",
        f"- practice/concert key: `{summary.get('practice_key') or '—'}` "
        f"(original `{summary.get('original_key') or '—'}`)",
        f"- sections_source_key: `{summary.get('sections_source_key') or '—'}` "
        f"transposed={summary.get('transposed_to_practice_key')}",
        f"- written key: `{summary.get('written_key') or '—'}` "
        f"clef=`{summary.get('notation_clef') or '—'}` "
        f"ABC `{summary.get('abc_key_field') or '—'}`",
        f"- source: `{summary.get('chart_source') or 'none'}`",
        f"- chart_available: **{summary.get('chart_available')}**",
        f"- section: {summary.get('active_section') or '—'}",
        f"- chord_count: {summary.get('chord_count', 0)}",
    ]
    preview = summary.get("chords_preview") or []
    if preview:
        lines.append(f"- concert chords: `{preview}`")
    wpreview = summary.get("written_chords_preview") or []
    if wpreview:
        lines.append(f"- written chords: `{wpreview}`")
    if summary.get("capo_shape_key") or summary.get("capo_fret") is not None:
        lines.append(
            f"- capo: fret={summary.get('capo_fret')} shape=`{summary.get('capo_shape_key') or '—'}`"
        )
    if not summary.get("chart_available"):
        lines.append(f"- candidate_sources: `{summary.get('candidate_sources')}`")
        lines.append(f"- pick_key_trace: `{summary.get('pick_key_trace')}`")
    solver = summary.get("solver_chart_transport")
    if isinstance(solver, dict):
        lines.append(f"- solver entrance: `{solver}`")
    if summary.get("fallback_reason"):
        lines.append(f"- fallback_reason: `{summary.get('fallback_reason')}`")
    return "\n".join(lines)

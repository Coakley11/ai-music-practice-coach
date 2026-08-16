"""Practice Focus → Upload / AI Coach evaluation bridge.

Consumes ``practice_focus_policy`` / snapshot. Does not own audio files,
takes, keys, or Creative/Backing state.

Practice Focus is a weighting signal:
  user-requested metrics
  + severe detected problems
  + focus-preferred *supported* dimensions
  + baseline scores

Never fabricate measurements the pipeline cannot support.
"""

from __future__ import annotations

from typing import Any, Mapping

from practice_focus_policy import (
    format_focus_prompt_block,
    resolve_focus_profile,
)
from practice_focus_snapshot import (
    ANALYSIS_FOCUS_LABEL_KEY,
    SNAPSHOT_KEY,
    read_practice_focus_snapshot,
    snapshot_from_historical_fields,
)

CAPABILITY_MEASURED = "measured"
CAPABILITY_DERIVED = "derived"
CAPABILITY_COACHING = "coaching_only"

SUPPORTED_SCORE_KEYS: tuple[str, ...] = (
    "timing",
    "pitch",
    "technique",
    "groove",
    "musicality",
    "confidence",
    "tone",
)

SEVERE_SCORE_THRESHOLD = 48
MISSION_ID_CAP = 18

_SCORE_LABELS = {
    "timing": "timing & rhythm",
    "pitch": "pitch & intonation",
    "technique": "technique",
    "groove": "groove",
    "musicality": "musicality",
    "confidence": "confidence",
    "tone": "tone stability",
}


def _supported_mission_ids() -> frozenset[str]:
    try:
        from mission_analysis import AI_IMPROV_METRIC_IDS

        return frozenset(AI_IMPROV_METRIC_IDS)
    except ImportError:
        return frozenset()


def capability_for_dimension(name: str) -> str:
    key = str(name or "").strip()
    if key in SUPPORTED_SCORE_KEYS:
        return CAPABILITY_MEASURED
    if key in _supported_mission_ids():
        return CAPABILITY_DERIVED
    return CAPABILITY_COACHING


def supported_preferred_metric_ids(instrument: str, focus: str) -> list[str]:
    profile = resolve_focus_profile(instrument, focus)
    allowed = _supported_mission_ids()
    return [mid for mid in profile.preferred_metric_ids if mid in allowed]


def supported_score_keys(instrument: str, focus: str) -> list[str]:
    profile = resolve_focus_profile(instrument, focus)
    return [k for k in profile.score_keys if k in SUPPORTED_SCORE_KEYS]


def freeze_focus_snapshot_for_analysis(
    session_state: Mapping[str, Any] | None,
    *,
    instrument: str = "",
    focus: str = "",
) -> dict[str, Any] | None:
    """Capture current Focus once. Empty focus → None (do not invent)."""
    ss = session_state if isinstance(session_state, Mapping) else None
    live_focus = str(focus or "").strip()
    live_inst = str(instrument or "").strip()
    if ss is not None:
        if "focus" in ss:
            live_focus = str(ss.get("focus") or live_focus).strip()
        if "instrument" in ss:
            live_inst = str(ss.get("instrument") or live_inst).strip()
        if not live_inst:
            try:
                from practice_setup_globals import get_active_instrument

                live_inst = str(get_active_instrument(ss) or "").strip()
            except ImportError:
                pass
    if not live_focus:
        return None
    return snapshot_from_historical_fields(
        instrument=live_inst,
        practice_focus=live_focus,
    )


def attach_frozen_focus_to_context(
    ctx: dict[str, Any],
    session_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Freeze Focus onto *ctx* once. Later live selector changes must not mix in."""
    existing = read_practice_focus_snapshot(ctx.get(SNAPSHOT_KEY))
    if existing is not None:
        ctx[SNAPSHOT_KEY] = existing
        ctx["focus"] = existing.get("practice_focus") or ctx.get("focus")
        if existing.get("instrument"):
            ctx["instrument"] = existing.get("instrument") or ctx.get("instrument")
        return ctx
    snap = freeze_focus_snapshot_for_analysis(
        session_state,
        instrument=str(ctx.get("instrument") or ""),
        focus=str(ctx.get("focus") or ""),
    )
    if snap is None:
        return ctx
    ctx[SNAPSHOT_KEY] = snap
    ctx["focus"] = snap.get("practice_focus") or ctx.get("focus")
    if snap.get("instrument"):
        ctx["instrument"] = snap.get("instrument") or ctx.get("instrument")
    return ctx


def merge_metric_ids_with_focus(
    user_metric_ids: list[str] | tuple[str, ...] | None,
    instrument: str,
    focus: str,
    *,
    cap: int = MISSION_ID_CAP,
) -> tuple[list[str], list[str]]:
    """Union user metrics with supported focus preferences. Never drops user IDs."""
    allowed = _supported_mission_ids()
    user: list[str] = []
    for mid in user_metric_ids or []:
        key = str(mid).strip()
        if key and key not in user and (not allowed or key in allowed or key == "custom"):
            user.append(key)
    preferred = supported_preferred_metric_ids(instrument, focus)
    merged = list(user)
    added: list[str] = []
    for mid in preferred:
        if mid in merged:
            continue
        if len(merged) >= cap:
            break
        merged.append(mid)
        added.append(mid)
    return merged[:cap], added


def severe_non_focus_scores(
    scores: Mapping[str, Any] | None,
    instrument: str,
    focus: str,
    *,
    threshold: int = SEVERE_SCORE_THRESHOLD,
) -> list[tuple[str, int]]:
    emphasized = set(supported_score_keys(instrument, focus))
    out: list[tuple[str, int]] = []
    for key, raw in (scores or {}).items():
        if key not in SUPPORTED_SCORE_KEYS:
            continue
        try:
            val = int(raw)
        except (TypeError, ValueError):
            continue
        if val < threshold and key not in emphasized:
            out.append((str(key), val))
    out.sort(key=lambda item: item[1])
    return out


def compact_analysis_focus_block(instrument: str, focus: str) -> str:
    """Short prompt/context for analysis — not the full policy dictionary."""
    inst = str(instrument or "").strip()
    label = str(focus or "").strip()
    if not label:
        return (
            "No Practice Focus was recorded for this analysis. "
            "Do not invent one from a later selector."
        )
    profile = resolve_focus_profile(inst, label)
    measured = ", ".join(supported_score_keys(inst, label)) or "none directly measured"
    derived = ", ".join(supported_preferred_metric_ids(inst, label)) or "none"
    base = format_focus_prompt_block(inst, label, role="analysis")
    if base and not base.endswith("\n"):
        base = f"{base}\n"
    return (
        f"{base}"
        f"- Measured score keys to emphasize: {measured}\n"
        f"- Derived mission metrics to emphasize (heuristic, not new sensors): {derived}\n"
        f"- Coaching-only next steps may use practice suggestions; "
        f"do not present them as measured defects.\n"
        f"- Exact Focus label to preserve: {profile.label}\n"
    )


def analysis_focus_display_label(result: Mapping[str, Any] | None) -> str:
    """Frozen analysis-time Focus for UI. Never reads the live selector."""
    if not isinstance(result, Mapping):
        return ""
    snap = read_practice_focus_snapshot(result.get(SNAPSHOT_KEY))
    if snap and snap.get("practice_focus"):
        return str(snap["practice_focus"])
    for key in (ANALYSIS_FOCUS_LABEL_KEY, "focus"):
        label = str(result.get(key) or "").strip()
        if label:
            return label
    return ""


def analysis_focus_caption(result: Mapping[str, Any] | None) -> str:
    label = analysis_focus_display_label(result)
    if label:
        return f"Practice Focus at analysis: {label}"
    return "Practice Focus at analysis: Not recorded"


def _focus_lead_sentence(instrument: str, focus: str) -> str:
    profile = resolve_focus_profile(instrument, focus)
    cat = profile.category
    inst = instrument or "your instrument"
    if cat == "rhythm_groove":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"rhythmic continuity, groove, and attack consistency from the timing "
            f"and onset evidence in this take — not stroke-by-stroke classification."
        )
    if cat == "timing":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"beat placement, subdivision, and tempo stability for **{inst}**."
        )
    if cat == "tone":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"sound stability and evenness from pitch-stability, dynamics, and "
            f"spectral evidence. This is not a fabricated resonance score."
        )
    if cat == "articulation":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"attack consistency and note separation from onset/articulation evidence."
        )
    if cat == "phrasing":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"phrase shape, space, and contour from pacing and dynamics evidence."
        )
    if cat == "harmony":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"chord-tone and voice-leading evidence where the analysis can support it."
        )
    if cat == "melody":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"line shape and target-tone evidence where it is supportable."
        )
    if cat == "improvisation":
        return (
            f"Your current focus is **{profile.label}**, so this review prioritizes "
            f"motif development, harmonic fit, and space."
        )
    return (
        f"Your current focus is **{profile.label}**. "
        "Coaching follows that goal using only supported measurements."
    )


def focus_next_exercises(instrument: str, focus: str, *, limit: int = 3) -> list[str]:
    profile = resolve_focus_profile(instrument, focus)
    lines = [str(s).strip() for s in profile.practice_suggestions if str(s).strip()]
    return lines[:limit]


def apply_focus_to_coach_outputs(
    *,
    scores: Mapping[str, Any],
    categories: Mapping[str, Any],
    practice_plan: list[str] | None,
    instrument: str,
    focus: str,
    baseline_summary: str = "",
    biggest_issue: str = "",
    most_improved: str = "",
    next_focus: str = "",
) -> dict[str, Any]:
    """Rewrite summary/plan emphasis. Does not change *scores*."""
    label = str(focus or "").strip()
    plan = list(practice_plan or [])
    if not label:
        return {
            "coach_summary": baseline_summary,
            "biggest_issue": biggest_issue,
            "most_improved": most_improved,
            "next_focus": next_focus,
            "practice_plan": plan[:8],
            "severe_non_focus_score_keys": [],
        }

    lead = _focus_lead_sentence(instrument, label)
    severe = severe_non_focus_scores(scores, instrument, label)
    severe_line = ""
    if severe:
        bits = [
            f"{_SCORE_LABELS.get(k, k)} ({v}/100)"
            for k, v in severe[:2]
        ]
        severe_line = (
            " A serious issue outside this focus still needs attention: "
            + "; ".join(bits)
            + "."
        )
    core = str(baseline_summary or "").strip()
    summary = f"{lead} {core}{severe_line}".strip()

    emphasized = supported_score_keys(instrument, label)
    ranked_focus = sorted(
        ((k, int(scores.get(k) or 0)) for k in emphasized if k in scores),
        key=lambda item: item[1],
    )
    if ranked_focus:
        weak_key, weak_score = ranked_focus[0]
        cat = (categories or {}).get(weak_key) or {}
        findings = cat.get("findings") or []
        if findings:
            biggest_issue = str(findings[0])
        tips = cat.get("tips") or []
        if tips:
            next_focus = str(tips[0])
        if severe and weak_score >= SEVERE_SCORE_THRESHOLD:
            sev_key, _sev_val = severe[0]
            sev_cat = (categories or {}).get(sev_key) or {}
            sev_findings = sev_cat.get("findings") or []
            if sev_findings:
                biggest_issue = (
                    f"{biggest_issue} Also notable: {sev_findings[0]}"
                    if biggest_issue
                    else str(sev_findings[0])
                )

    recs = focus_next_exercises(instrument, label, limit=3)
    merged_plan: list[str] = []
    for line in recs + plan:
        text = str(line).strip()
        if text and text not in merged_plan:
            merged_plan.append(text)
    return {
        "coach_summary": summary,
        "biggest_issue": biggest_issue,
        "most_improved": most_improved,
        "next_focus": next_focus,
        "practice_plan": merged_plan[:8],
        "severe_non_focus_score_keys": [k for k, _v in severe],
    }


def build_evaluation_debug(
    *,
    instrument: str,
    focus: str,
    user_metric_ids: list[str],
    merged_metric_ids: list[str],
    added_metric_ids: list[str],
    scores: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    emphasized = supported_score_keys(instrument, focus)
    preferred = supported_preferred_metric_ids(instrument, focus)
    capability = {k: CAPABILITY_MEASURED for k in emphasized}
    for mid in preferred:
        capability[mid] = CAPABILITY_DERIVED
    for rec in focus_next_exercises(instrument, focus):
        capability[rec[:48]] = CAPABILITY_COACHING
    return {
        "instrument": instrument,
        "practice_focus": focus,
        "preferred_metric_ids": preferred,
        "user_metric_ids": list(user_metric_ids),
        "focus_added_metric_ids": list(added_metric_ids),
        "merged_metric_ids": list(merged_metric_ids),
        "emphasized_score_keys": emphasized,
        "severe_non_focus_score_keys": [
            k for k, _v in severe_non_focus_scores(scores or {}, instrument, focus)
        ],
        "dimension_capability": capability,
        "analysis_prompt_block": compact_analysis_focus_block(instrument, focus),
    }


def stamp_result_with_frozen_snapshot(
    result: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    *,
    evaluation_debug: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(result or {})
    snap = read_practice_focus_snapshot(snapshot)
    if snap is None:
        return out
    out[SNAPSHOT_KEY] = snap
    out[ANALYSIS_FOCUS_LABEL_KEY] = snap.get("practice_focus") or ""
    if evaluation_debug:
        out["practice_focus_evaluation"] = dict(evaluation_debug)
    return out


def prepare_upload_analysis_context(
    session_state: Mapping[str, Any] | None,
    ctx: dict[str, Any],
    *,
    user_metric_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Call once at analysis start. Freezes Focus and unions supported metrics."""
    attach_frozen_focus_to_context(ctx, session_state)
    snap = read_practice_focus_snapshot(ctx.get(SNAPSHOT_KEY))
    inst = str((snap or {}).get("instrument") or ctx.get("instrument") or "")
    focus = str((snap or {}).get("practice_focus") or ctx.get("focus") or "")
    incoming = user_metric_ids if user_metric_ids is not None else list(ctx.get("mission_ids") or [])
    merged, added = merge_metric_ids_with_focus(incoming, inst, focus)
    ctx["mission_ids"] = merged
    ctx["practice_focus_user_metric_ids"] = list(incoming)
    ctx["practice_focus_added_metric_ids"] = added
    ctx["practice_focus_analysis_block"] = compact_analysis_focus_block(inst, focus)
    return ctx

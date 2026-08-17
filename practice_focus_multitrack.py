"""Practice Focus → Multitrack ensemble analysis adapter.

Consumes central Focus policy / evaluation helpers.
Does not invent chord transcription, stroke identity, or resonance scores.

Multitrack measured capabilities today:
  - nearest-onset gap vs reference track
  - RMS level ratio vs reference track

Placeholder (not measured): constant balance/sync score fields.
"""

from __future__ import annotations

from typing import Any, Mapping

from practice_focus_evaluation import (
    CAPABILITY_COACHING,
    CAPABILITY_DERIVED,
    CAPABILITY_MEASURED,
    attach_frozen_focus_to_context,
    compact_analysis_focus_block,
    freeze_focus_snapshot_for_analysis,
    stamp_result_with_frozen_snapshot,
)
from practice_focus_policy import resolve_focus_profile
from practice_focus_snapshot import read_practice_focus_snapshot

# Explicit Multitrack capability map (debug / tests; not a second rulebook).
MULTITRACK_CAPABILITY_MAP: dict[str, str] = {
    "onset_alignment": CAPABILITY_MEASURED,
    "rms_balance": CAPABILITY_MEASURED,
    "ensemble_score_heuristic": CAPABILITY_DERIVED,
    "balance_score_constant": CAPABILITY_COACHING,  # placeholder constant, not a measurement
    "sync_score_constant": CAPABILITY_COACHING,
    "stroke_direction": "unsupported",
    "resonance": "unsupported",
    "embouchure": "unsupported",
    "chord_identity": "unsupported",
    "note_transcription": "unsupported",
    "phrase_structure": CAPABILITY_COACHING,
    "tone_cross_take_stability": CAPABILITY_COACHING,  # features exist per layer but MT path does not compare them
    "harmony_fit": CAPABILITY_COACHING,
}

_TIMING_FINDING_MARKERS = (
    "timing differs",
    "onset gap",
    "rhythmically well locked",
    " ms ",
)
_BALANCE_FINDING_MARKERS = (
    "buried",
    "dominates",
    "balance",
)


def multitrack_capability_for(dimension: str) -> str:
    return MULTITRACK_CAPABILITY_MAP.get(str(dimension or "").strip(), CAPABILITY_COACHING)


def prepare_multitrack_analysis_context(
    session_state: Mapping[str, Any] | None,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Freeze Practice Focus once at Multitrack analysis start."""
    attach_frozen_focus_to_context(ctx, session_state)
    snap = read_practice_focus_snapshot(ctx.get("practice_focus_snapshot"))
    inst = str((snap or {}).get("instrument") or ctx.get("instrument") or "")
    focus = str((snap or {}).get("practice_focus") or ctx.get("focus") or "")
    ctx["practice_focus_analysis_block"] = compact_analysis_focus_block(inst, focus)
    return ctx


def _finding_is_timing(text: str) -> bool:
    low = str(text or "").lower()
    return any(m in low for m in _TIMING_FINDING_MARKERS)


def _finding_is_balance(text: str) -> bool:
    low = str(text or "").lower()
    return any(m in low for m in _BALANCE_FINDING_MARKERS)


def _severe_timing_findings(findings: list[str]) -> list[str]:
    out: list[str] = []
    for line in findings:
        low = str(line).lower()
        if "timing differs" in low or "onset gap" in low:
            out.append(str(line))
    return out


def _focus_lead_sentence(instrument: str, focus: str) -> str:
    profile = resolve_focus_profile(instrument, focus)
    cat = profile.category
    label = profile.label
    inst = instrument or "your instrument"
    if cat in ("timing", "rhythm_groove"):
        return (
            f"Your current focus is **{label}**, so this ensemble review prioritizes "
            f"onset alignment and rhythmic lock between layers — using the measured "
            f"onset-gap and level evidence available (not stroke-by-stroke classification)."
        )
    if cat == "tone":
        return (
            f"Your current focus is **{label}**, so next steps emphasize sound stability "
            f"for **{inst}**. This Multitrack path measures alignment and balance between "
            f"layers; it does not invent a resonance or embouchure score."
        )
    if cat == "phrasing":
        return (
            f"Your current focus is **{label}**, so coaching emphasizes entrances, space, "
            f"and continuity using available onset/duration evidence — not a full phrase parser."
        )
    if cat == "harmony":
        return (
            f"Your current focus is **{label}**. Multitrack does not transcribe chords; "
            f"use alignment/balance evidence plus ear-based harmonic listening goals."
        )
    if cat in ("melody", "improvisation"):
        return (
            f"Your current focus is **{label}**. Without note-level transcription, this "
            f"review still highlights rhythmic interaction and mix balance between layers."
        )
    if cat == "articulation":
        return (
            f"Your current focus is **{label}**, so listen for attack consistency where "
            f"onset evidence is available, then shape articulations in the next overdub."
        )
    return (
        f"Your current focus is **{label}**. Ensemble coaching follows that goal using "
        f"only supported Multitrack measurements (onset alignment and RMS balance)."
    )


def focus_multitrack_exercises(instrument: str, focus: str, *, limit: int = 3) -> list[str]:
    profile = resolve_focus_profile(instrument, focus)
    cat = profile.category
    extras: list[str] = []
    if cat in ("timing", "rhythm_groove"):
        extras = [
            "Record one anchor rhythm layer first, then overdub the second part at reduced tempo.",
            "Isolate entrances that drift; loop those bars with a click before re-layering.",
        ]
    elif cat == "tone":
        extras = [
            "Before the next overdub, do long tones or dynamic swells, then compare two takes by ear.",
            "Use the more stable take as a reference layer and match its sustain shape.",
        ]
    elif cat == "phrasing":
        extras = [
            "Record question/answer phrases on separate layers and leave intentional space.",
            "Match phrase endings between tracks before adding denser fills.",
        ]
    elif cat == "harmony":
        extras = [
            "Record a simple guide-tone or chord-tone layer to hear harmonic fit by ear.",
            "Simplify accompaniment so melody and harmony parts are easy to balance.",
        ]
    lines = [str(s).strip() for s in extras + list(profile.practice_suggestions) if str(s).strip()]
    # Dedupe preserve order
    out: list[str] = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out[:limit]


def apply_focus_to_multitrack_outputs(
    *,
    findings: list[str] | None,
    tips: list[str] | None,
    coach_summary: str,
    scores: Mapping[str, Any] | None,
    instrument: str,
    focus: str,
) -> dict[str, Any]:
    """Rewrite Multitrack coaching emphasis. Does not change raw scores or finding text."""
    finding_list = [str(x) for x in (findings or [])]
    tip_list = [str(x) for x in (tips or [])]
    label = str(focus or "").strip()
    scores_out = dict(scores or {})

    if not label:
        return {
            "findings": finding_list,
            "tips": tip_list[:8],
            "coach_summary": coach_summary,
            "scores": scores_out,
            "emphasized_dimensions": [],
            "severe_non_focus_findings": [],
            "capability_notes": [],
        }

    profile = resolve_focus_profile(instrument, label)
    cat = profile.category
    lead = _focus_lead_sentence(instrument, label)

    # Keep finding *text* identical; only reorder for emphasis.
    ordered = list(finding_list)
    if cat in ("timing", "rhythm_groove", "articulation", "phrasing"):
        ordered = sorted(ordered, key=lambda f: (0 if _finding_is_timing(f) else 1))
        emphasized = ["onset_alignment"]
    elif cat == "tone":
        # Tone: keep balance findings visible but do not hide timing problems.
        ordered = sorted(
            ordered,
            key=lambda f: (0 if _finding_is_balance(f) else (1 if _finding_is_timing(f) else 2)),
        )
        emphasized = ["rms_balance"]
    else:
        emphasized = ["onset_alignment", "rms_balance"]

    severe = []
    if cat not in ("timing", "rhythm_groove"):
        severe = _severe_timing_findings(finding_list)

    severe_line = ""
    if severe:
        severe_line = (
            " A serious timing/alignment issue outside this focus still needs attention: "
            + severe[0]
        )

    baseline = str(coach_summary or "").strip()
    summary = f"{lead} {baseline}{severe_line}".strip()

    recs = focus_multitrack_exercises(instrument, label, limit=3)
    baseline_tips = [
        "Mix check: solo each layer, then A/B with drums or click.",
        "Ensemble drill: record rhythm section first, overdub melody after 2 clean passes.",
    ]
    merged_tips: list[str] = []
    for line in recs + tip_list + baseline_tips:
        text = str(line).strip()
        if text and text not in merged_tips:
            merged_tips.append(text)

    capability_notes = [
        f"onset_alignment={multitrack_capability_for('onset_alignment')}",
        f"rms_balance={multitrack_capability_for('rms_balance')}",
        f"stroke_direction={multitrack_capability_for('stroke_direction')}",
        f"resonance={multitrack_capability_for('resonance')}",
        f"chord_identity={multitrack_capability_for('chord_identity')}",
    ]

    return {
        "findings": ordered,
        "tips": merged_tips[:8],
        "coach_summary": summary,
        "scores": scores_out,
        "emphasized_dimensions": emphasized,
        "severe_non_focus_findings": severe,
        "capability_notes": capability_notes,
        "focus_category": cat,
        "practice_focus": profile.label,
    }


def stamp_multitrack_result_with_focus(
    result: Mapping[str, Any] | None,
    ctx: Mapping[str, Any] | None,
    *,
    evaluation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(result or {})
    snap = None
    if isinstance(ctx, Mapping):
        snap = read_practice_focus_snapshot(ctx.get("practice_focus_snapshot"))
        if snap is None:
            snap = freeze_focus_snapshot_for_analysis(
                None,
                instrument=str(ctx.get("instrument") or ""),
                focus=str(ctx.get("focus") or ""),
            )
    debug = dict(evaluation or {})
    if snap:
        debug.setdefault("instrument", snap.get("instrument"))
        debug.setdefault("practice_focus", snap.get("practice_focus"))
    debug.setdefault("capability_map", dict(MULTITRACK_CAPABILITY_MAP))
    return stamp_result_with_frozen_snapshot(out, snap, evaluation_debug=debug or None)


def build_multitrack_evaluation_debug(
    *,
    instrument: str,
    focus: str,
    applied: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    applied = applied or {}
    return {
        "instrument": instrument,
        "practice_focus": focus,
        "emphasized_dimensions": list(applied.get("emphasized_dimensions") or []),
        "severe_non_focus_findings": list(applied.get("severe_non_focus_findings") or []),
        "capability_notes": list(applied.get("capability_notes") or []),
        "capability_map": dict(MULTITRACK_CAPABILITY_MAP),
        "analysis_prompt_block": compact_analysis_focus_block(instrument, focus),
        "raw_scores_unchanged": True,
    }

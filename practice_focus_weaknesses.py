"""Focus-aware Adaptive Weakness ranking (priority, not truth).

Ranks **existing** measured/derived weakness evidence. Never invents a
weakness solely because Practice Focus is set (e.g. no fake "Strumming"
defect). Current Focus changes presentation priority and next-exercise
language; historical evidence identity stays unchanged.

Consumes ``practice_focus_policy`` / ``practice_focus_evaluation`` /
``practice_focus_coaching``. Does not own audio, keys, or Creative state.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from practice_focus_coaching import practice_page_focus_lines
from practice_focus_evaluation import (
    CAPABILITY_COACHING,
    CAPABILITY_MEASURED,
    SEVERE_SCORE_THRESHOLD,
    SUPPORTED_SCORE_KEYS,
    capability_for_dimension,
    supported_score_keys,
)
from practice_focus_policy import (
    canonical_instrument_label,
    resolve_focus_profile,
)

_SCORE_LABELS = {
    "timing": "Timing & rhythm",
    "pitch": "Pitch & intonation",
    "technique": "Technique",
    "groove": "Groove / rhythmic continuity",
    "musicality": "Musicality",
    "confidence": "Confidence / consistency",
    "tone": "Tone stability",
}

# Soft relevance of measured score keys to Focus categories (0–1).
_CATEGORY_SCORE_RELEVANCE: dict[str, dict[str, float]] = {
    "tone": {"tone": 1.0, "pitch": 0.55, "technique": 0.35, "musicality": 0.25},
    "timing": {"timing": 1.0, "groove": 0.7, "confidence": 0.3},
    "rhythm_groove": {"groove": 1.0, "timing": 0.85, "technique": 0.4, "confidence": 0.25},
    "harmony": {"musicality": 0.55, "pitch": 0.4, "technique": 0.35},
    "melody": {"pitch": 0.7, "musicality": 0.65, "tone": 0.3},
    "phrasing": {"musicality": 0.8, "confidence": 0.4, "tone": 0.25},
    "articulation": {"technique": 0.75, "timing": 0.45, "tone": 0.35},
    "improvisation": {"musicality": 0.7, "groove": 0.45, "pitch": 0.35},
    "technique": {"technique": 1.0, "tone": 0.35, "timing": 0.3},
    "dynamics": {"tone": 0.55, "musicality": 0.45, "confidence": 0.3},
    "ear_training": {"pitch": 0.8, "musicality": 0.4},
    "general": {},
}

FOCUS_RELEVANCE_BOOST = 22.0
SEVERE_FLOOR_BOOST = 12.0
RECURRING_BOOST = 8.0


def _as_int_score(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def focus_relevance_for_score_key(instrument: str, focus: str, score_key: str) -> float:
    """0–1 relevance of a measured score key to the active Practice Focus."""
    profile = resolve_focus_profile(instrument, focus)
    key = str(score_key or "").strip()
    if key in supported_score_keys(instrument, focus):
        return 1.0
    table = _CATEGORY_SCORE_RELEVANCE.get(profile.category) or {}
    return float(table.get(key, 0.0))


def recommendation_for_weakness(
    instrument: str,
    focus: str,
    score_key: str,
) -> str:
    """Instrument/Focus-aware next drill from the central policy (not a local dictionary)."""
    lines = practice_page_focus_lines(instrument, focus)
    if lines:
        return lines[0]
    profile = resolve_focus_profile(instrument, focus)
    if profile.practice_suggestions:
        return str(profile.practice_suggestions[0])
    label = _SCORE_LABELS.get(score_key, score_key)
    return f"Isolate **{label}** at a controlled tempo, then re-check with a short recording."


def rank_measured_weaknesses(
    scores: Mapping[str, Any] | None,
    instrument: str,
    focus: str,
    *,
    recurring_keys: Sequence[str] | None = None,
    severe_threshold: int = SEVERE_SCORE_THRESHOLD,
    max_items: int = 8,
) -> list[dict[str, Any]]:
    """Rank existing score weaknesses. Empty scores → empty list (no invention).

    Priority ≈ severity + Focus relevance + severe floor + recurring boost.
    Severe non-Focus issues still rank highly via severity alone.
    """
    recurring = {
        str(k).strip().lower()
        for k in (recurring_keys or [])
        if str(k or "").strip()
    }
    ranked: list[dict[str, Any]] = []
    for key in SUPPORTED_SCORE_KEYS:
        score = _as_int_score((scores or {}).get(key))
        if score is None:
            continue
        # Only surface as weakness when below a soft "ok" band, or severe, or Focus-relevant low.
        relevance = focus_relevance_for_score_key(instrument, focus, key)
        severity = max(0, 100 - score)
        if score >= 78 and relevance < 0.5:
            continue
        if score >= 88:
            continue
        focus_boost = FOCUS_RELEVANCE_BOOST * relevance
        severe_boost = SEVERE_FLOOR_BOOST if score < severe_threshold else 0.0
        recurring_boost = RECURRING_BOOST if key.lower() in recurring else 0.0
        priority = float(severity) + focus_boost + severe_boost + recurring_boost
        ranked.append(
            {
                "id": key,
                "label": _SCORE_LABELS.get(key, key.replace("_", " ").title()),
                "score": score,
                "severity": severity,
                "focus_relevance": round(relevance, 3),
                "priority": round(priority, 2),
                "capability": CAPABILITY_MEASURED,
                "recommendation": recommendation_for_weakness(instrument, focus, key),
                "severe": score < severe_threshold,
                "focus_matched": relevance >= 0.85,
            }
        )
    ranked.sort(key=lambda row: (-float(row["priority"]), int(row["score"]), str(row["id"])))
    return ranked[: max(1, int(max_items))]


def coaching_only_focus_targets(instrument: str, focus: str, *, limit: int = 3) -> list[str]:
    """Practice suggestions when there is no measured weakness evidence.

    Labeled coaching-only — never presented as detected defects.
    """
    profile = resolve_focus_profile(instrument, focus)
    out: list[str] = []
    for tip in profile.practice_suggestions:
        text = str(tip).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def format_adaptive_weakness_markdown(
    instrument: str,
    focus: str,
    *,
    song: str = "",
    scores: Mapping[str, Any] | None = None,
    recurring_keys: Sequence[str] | None = None,
) -> str:
    """Creative Lab / Adaptive Weakness Detection body text."""
    profile = resolve_focus_profile(instrument, focus)
    inst = canonical_instrument_label(instrument) or (instrument or "your instrument")
    title_song = str(song or "").strip() or "current song"
    lines: list[str] = [
        f"# Adaptive Weakness Detection - {title_song}",
        "",
        f"**Instrument:** {inst}  ",
        f"**Current Practice Focus:** {profile.label}  ",
        "",
        "_Focus changes priority, not truth. Severe non-Focus issues still surface. "
        "Focus never invents a weakness without evidence._",
        "",
    ]
    ranked = rank_measured_weaknesses(
        scores,
        instrument,
        focus,
        recurring_keys=recurring_keys,
    )
    if ranked:
        lines.append("## Ranked weaknesses (measured)")
        for row in ranked:
            tags: list[str] = []
            if row.get("severe"):
                tags.append("severe")
            if row.get("focus_matched"):
                tags.append("Focus-aligned")
            tag_s = f" [{', '.join(tags)}]" if tags else ""
            lines.append(
                f"- **{row['label']}** — score {row['score']}/100 "
                f"(priority {row['priority']:.0f}){tag_s}"
            )
            lines.append(f"  - Evidence: `{row['capability']}`")
            lines.append(f"  - Next: {row['recommendation']}")
        lines.append("")
    else:
        lines.append("## Ranked weaknesses (measured)")
        lines.append(
            "- No measured score weaknesses available yet "
            "(upload a take on Upload Analysis, or open this tool after an analysis)."
        )
        lines.append(
            f"- Current Focus **{profile.label}** is noted for coaching, "
            "but is **not** recorded as a detected defect."
        )
        lines.append("")

    coaching = coaching_only_focus_targets(instrument, focus)
    if coaching:
        lines.append("## Focus practice targets (coaching-only)")
        lines.append(
            f"These follow Practice Focus **{profile.label}** for **{inst}**. "
            f"Capability: `{CAPABILITY_COACHING}` — not measured defects."
        )
        for tip in coaching:
            lines.append(f"- {tip}")
        lines.append("")

    lines.extend(
        [
            "## Generated drill",
            "- Pick the hardest section of the song.",
            "- Loop it slowly 5 times with today's Focus as the listening filter.",
            "- Record one take.",
            "- Re-check measured scores; do not invent Focus-specific defects the pipeline cannot measure.",
        ]
    )
    return "\n".join(lines)


def audit_weakness_sources() -> dict[str, Any]:
    """Document lifecycle for Phase 3A reports / tests (read-only metadata)."""
    return {
        "measured_score_keys": list(SUPPORTED_SCORE_KEYS),
        "severe_threshold": SEVERE_SCORE_THRESHOLD,
        "sources": [
            {
                "id": "upload_scores",
                "kind": "measured",
                "module": "recording_analysis / last_analysis_result.scores",
            },
            {
                "id": "upload_history_trends",
                "kind": "measured_aggregate",
                "module": "practice_log_insights._score_trends / ai_performance_history",
            },
            {
                "id": "practice_log_challenges",
                "kind": "heuristic_self_report",
                "module": "practice_log_insights / practice_history_synthesis",
            },
            {
                "id": "creative_lab_adaptive",
                "kind": "ranking_ui",
                "module": "practice_focus_weaknesses.format_adaptive_weakness_markdown",
            },
            {
                "id": "legacy_adaptive_stub",
                "kind": "replaced",
                "module": "creative_lab_text.adaptive_weakness_detection_text",
            },
        ],
        "ranking_principles": [
            "severity (100 - score)",
            "Practice Focus relevance boost",
            "severe non-focus floor",
            "recurring/repetition boost when keys provided",
            "never invent Focus-only weaknesses without scores",
        ],
        "capability_helper": capability_for_dimension.__name__,
    }


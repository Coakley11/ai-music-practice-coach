"""Local Music Coach instant solver — practice plans, chord work, tempo/key guidance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MUSIC_SOLVER_INTENTS = frozenset(
    {
        "practice_plan",
        "chord_transition",
        "section_focus",
        "tempo_key",
        "backing_track",
        "skill_technique",
        "difficulty",
    }
)


@dataclass
class MusicSolverRoute:
    problem_type: str
    model_name: str
    model_rationale: str = ""


@dataclass
class MusicSolverResult:
    short_answer: str
    math_idea: str = ""
    problem_type: str = ""
    model_name: str = ""
    variables: str = ""
    assumptions: list[str] = field(default_factory=list)
    confidence_pct: int | None = 85
    computed: dict[str, Any] = field(default_factory=dict)


def _ctx_value(ctx: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        val = ctx.get(key)
        if val is not None and str(val).strip() != "":
            return val
    snap = ctx.get("practice_snapshot")
    if isinstance(snap, dict):
        for key in keys:
            val = snap.get(key)
            if val is not None and str(val).strip() != "":
                return val
    active = ctx.get("active_song")
    if isinstance(active, dict):
        for key in keys:
            val = active.get(key)
            if val is not None and str(val).strip() != "":
                return val
    return default


def _session_minutes(ctx: dict[str, Any]) -> int:
    raw = _ctx_value(ctx, "practice_minutes", "session_minutes", "minutes", default=30)
    try:
        minutes = int(float(raw))
    except (TypeError, ValueError):
        minutes = 30
    return max(15, min(90, minutes))


def _allocate_minutes(total: int, weights: dict[str, float]) -> dict[str, int]:
    if not weights:
        return {}
    norm = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    raw = {k: total * max(0.0, float(v)) / norm for k, v in weights.items()}
    rounded = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(rounded.values())
    order = sorted(raw.keys(), key=lambda k: raw[k] - rounded[k], reverse=True)
    idx = 0
    while remainder > 0 and order:
        rounded[order[idx % len(order)]] += 1
        remainder -= 1
        idx += 1
    return rounded


def _practice_plan_answer(question: str, ctx: dict[str, Any], *, chord_focus: bool) -> MusicSolverResult:
    minutes = _session_minutes(ctx)
    section = str(_ctx_value(ctx, "practice_focus_section", "section_focus_named", default="")).strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    song = str(_ctx_value(ctx, "question_song", "song", default="")).strip()
    if chord_focus:
        weights = {
            "chord transitions": 0.40,
            "rhythm / groove": 0.30,
            "melody / licks": 0.20,
            "full run-through": 0.10,
        }
        focus_line = "Prioritize clean chord changes before speed."
    else:
        weights = {
            "technique / drills": 0.35,
            "rhythm / groove": 0.25,
            "repertoire section": 0.25,
            "full run-through": 0.15,
        }
        focus_line = "Balance technique, time feel, and musical run-throughs."
    blocks = _allocate_minutes(minutes, weights)
    lines = [f"Suggested {minutes}-minute practice split:"]
    for label, block_min in blocks.items():
        lines.append(f"- **{block_min} min** {label}")
    if section:
        lines.append(f"- Keep **{section}** as your primary section focus.")
    if song:
        lines.append(f"- Anchor the plan to **{song}**.")
    lines.append(f"- On **{instrument}**, {focus_line}")
    short = "\n".join(lines)
    return MusicSolverResult(
        short_answer=short,
        math_idea="Time-boxed practice blocks weighted toward the user's stated focus.",
        problem_type="practice_plan",
        model_name="Music Coach practice planner",
        variables=f"session_minutes={minutes}; chord_focus={chord_focus}",
        assumptions=[
            "Session length defaults to 30 minutes when not set in practice context.",
            "Adjust blocks ±2 minutes if your warmup or cooldown needs more time.",
        ],
        confidence_pct=82,
        computed={"session_minutes": minutes, **blocks},
    )


def _chord_transition_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    minutes = max(10, min(25, _session_minutes(ctx) // 2 or 15))
    bpm = _ctx_value(ctx, "bpm", "practice_bpm", default="")
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    lines = [
        f"Spend about **{minutes} minutes** on chord-change drills, then plug them into the song.",
        "- Loop pairs of chords slowly (metronome 60–70% of target tempo).",
        "- Practice common-finger anchors and lift only the fingers that must move.",
        "- Run 4-bar loops, then 8-bar loops, then add rhythm on **{inst}**.".format(inst=instrument),
    ]
    if bpm:
        lines.append(f"- Target tempo ladder: 70% → 85% → 100% of **{bpm} BPM**.")
    else:
        lines.append("- Target tempo ladder: comfortable → medium → performance tempo.")
    return MusicSolverResult(
        short_answer="\n".join(lines),
        math_idea="Isolated transition reps before tempo and groove integration.",
        problem_type="chord_transition",
        model_name="Music Coach chord transitions",
        variables=f"drill_minutes={minutes}",
        assumptions=["One chord pair at a time beats rushing the full progression."],
        confidence_pct=84,
        computed={"drill_minutes": minutes},
    )


def _section_focus_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    section = str(_ctx_value(ctx, "practice_focus_section", "section_focus_named", default="this section")).strip()
    minutes = _session_minutes(ctx)
    drill = max(8, minutes // 3)
    return MusicSolverResult(
        short_answer=(
            f"For **{section}**: loop **{drill} min** slow reps, **{drill} min** rhythm-focused reps, "
            f"then **{max(5, minutes - 2 * drill)} min** connecting into the full song."
        ),
        math_idea="Section loops with escalating tempo and context.",
        problem_type="section_focus",
        model_name="Music Coach section focus",
        confidence_pct=80,
        computed={"section": section, "loop_minutes": drill},
    )


def _tempo_key_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    bpm = str(_ctx_value(ctx, "bpm", "practice_bpm", default="")).strip()
    display_key = str(_ctx_value(ctx, "display_key", "key", default="")).strip()
    level = str(_ctx_value(ctx, "level", default="Intermediate")).strip()
    tempo_line = (
        f"Try **{int(float(bpm) * 0.75)} BPM** as a learning tempo (about 75% of {bpm})."
        if bpm
        else "Start 15–25% below performance tempo until transitions stay clean."
    )
    key_line = f"Written key **{display_key}** is fine for practice." if display_key else "Match the chart key you are reading."
    return MusicSolverResult(
        short_answer=f"{tempo_line}\n{key_line}\nFor **{level}** players, add +5 BPM only after two clean passes.",
        math_idea="Tempo ladder with key context from the active chart.",
        problem_type="tempo_key",
        model_name="Music Coach tempo & key",
        confidence_pct=78,
        computed={"suggested_bpm_pct": 75},
    )


def _skill_technique_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    level = str(_ctx_value(ctx, "level", default="your level")).strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    return MusicSolverResult(
        short_answer=(
            f"At **{level}** on **{instrument}**, build technique before full-tempo performance: "
            "slow reps with a metronome, short bursts at target tempo, then rest. "
            "If the song feels too hard, reduce tempo 20% and isolate the hardest bar."
        ),
        math_idea="Readiness check with technique-first progression.",
        problem_type="skill_technique",
        model_name="Music Coach technique roadmap",
        confidence_pct=76,
    )


def _backing_track_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    groove = str(_ctx_value(ctx, "groove", "practice_groove_style", "backing_groove_style", default="the groove")).strip()
    section = str(_ctx_value(ctx, "practice_focus_section", default="the chorus")).strip()
    return MusicSolverResult(
        short_answer=(
            f"Loop **{section}** with **{groove}** at a comfortable tempo. "
            "Practice chord changes first without the backing, then add the track for time feel."
        ),
        math_idea="Backing-track practice order: technique → groove integration.",
        problem_type="backing_track",
        model_name="Music Coach backing track",
        confidence_pct=77,
    )


def _route_for_intent(intent: str) -> MusicSolverRoute:
    labels = {
        "practice_plan": ("practice_plan", "Music Coach practice planner"),
        "chord_transition": ("chord_transition", "Music Coach chord transitions"),
        "section_focus": ("section_focus", "Music Coach section focus"),
        "tempo_key": ("tempo_key", "Music Coach tempo & key"),
        "backing_track": ("backing_track", "Music Coach backing track"),
        "skill_technique": ("skill_technique", "Music Coach technique roadmap"),
        "difficulty": ("skill_technique", "Music Coach technique roadmap"),
    }
    problem_type, model_name = labels.get(intent, ("music_general", "Music Coach"))
    return MusicSolverRoute(
        problem_type=problem_type,
        model_name=model_name,
        model_rationale=f"Routed from music intent `{intent}`.",
    )


def solve_instant_music_insight(
    question: str,
    context: dict[str, Any] | None,
) -> tuple[MusicSolverRoute, MusicSolverResult] | None:
    """Return (route, result) for supported music coaching questions."""
    q = str(question or "").strip()
    if not q:
        return None
    ctx = dict(context or {})
    try:
        from music_ami_context import detect_music_send_intent
    except ImportError:
        return None

    coach_page = str(ctx.get("coach_page") or ctx.get("source_page") or "").strip().lower()
    intent = detect_music_send_intent(q, coach_page)
    if intent not in _MUSIC_SOLVER_INTENTS:
        return None

    low = q.lower()
    chord_focus = intent in {"practice_plan", "chord_transition"} or any(
        p in low for p in ("chord change", "chord changes", "chord transition", "transitions")
    )

    if intent == "practice_plan":
        result = _practice_plan_answer(q, ctx, chord_focus=chord_focus)
    elif intent == "chord_transition":
        result = _chord_transition_answer(ctx)
    elif intent == "section_focus":
        result = _section_focus_answer(ctx)
    elif intent == "tempo_key":
        result = _tempo_key_answer(ctx)
    elif intent in {"skill_technique", "difficulty"}:
        result = _skill_technique_answer(ctx)
    elif intent == "backing_track":
        result = _backing_track_answer(ctx)
    else:
        return None

    route = _route_for_intent(intent)
    result.problem_type = route.problem_type
    result.model_name = route.model_name
    return route, result

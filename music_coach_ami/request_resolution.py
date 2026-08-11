"""Merge explicit question entities with CoachContext — shared across solvers."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.types import CoachContext, ExtractedEntities


def display_coach_instrument(instrument: str) -> str:
    name = str(instrument or "").strip()
    return name if name else "your instrument"


def resolve_instrument_for_request(
    session_state: dict[str, Any],
    *,
    entities: ExtractedEntities,
    context: CoachContext,
) -> tuple[str, dict[str, Any]]:
    from music_coach_ami.coach_instrument import instrument_provenance_trace, resolve_coach_instrument

    snap = str(context.extra.get("snapshot_instrument") or "") if isinstance(context.extra, dict) else ""
    ctx_inst = str(context.instrument or "").strip()
    resolved = resolve_coach_instrument(
        session_state,
        question_entity=entities.instrument,
        ctx_instrument=ctx_inst,
        snapshot_instrument=snap,
    )
    trace = instrument_provenance_trace(
        session_state,
        question_entity=entities.instrument,
        ctx_instrument=ctx_inst,
        snapshot_instrument=snap,
        resolved=resolved,
    )
    trace["resolution_priority"] = "question_entity>session>snapshot>empty"
    return resolved, trace


def parse_question_level(normalized: str) -> tuple[str, bool]:
    low = str(normalized or "").lower()
    if re.search(r"\b(beginner|beginning|easy)\b", low):
        return "beginner", True
    if re.search(r"\b(intermediate|medium level|medium)\b", low):
        return "intermediate", True
    if re.search(r"\b(advanced|difficult|hard|challenging|hardest)\b", low):
        return "advanced", True
    return "", False


def parse_question_focus(normalized: str) -> tuple[str, bool]:
    low = str(normalized or "").lower()
    if re.search(r"\bbass line\b|\bbass-line\b|\bwalking bass\b", low):
        return "bass line", True
    if re.search(r"\bfingerstyle\b|\bfinger style\b", low):
        return "fingerstyle", True
    if any(p in low for p in ("build tone", "for tone", "good to build tone", "tone exercise")):
        return "tone", True
    if "articulation" in low or ("slur" in low and "short" in low):
        return "articulation", True
    if any(p in low for p in ("finger technique", "finger speed", "technique", "fingerings")):
        return "technique", True
    if any(p in low for p in ("harmony", "chord voicing", "voicing")):
        return "harmony", True
    if any(p in low for p in ("rhythm", "timing", "groove")):
        return "rhythm", True
    return "", False


def resolve_level_for_request(
    *,
    question_level: str,
    question_level_explicit: bool,
    context_level: str,
    difficulty_requested: bool,
) -> tuple[str, str]:
    if question_level_explicit and question_level:
        return question_level, "question"
    if difficulty_requested and not question_level:
        return "intermediate", "question_difficulty_word"
    if str(context_level or "").strip():
        return str(context_level).strip(), "coach_context"
    return "", "none"


def resolve_focus_for_request(
    *,
    question_focus: str,
    question_focus_explicit: bool,
    context_focus: str,
    skill_topic: str,
) -> tuple[str, str]:
    if question_focus_explicit and question_focus:
        return question_focus, "question"
    if skill_topic:
        return skill_topic, "question_skill_topic"
    if str(context_focus or "").strip():
        return str(context_focus).strip(), "coach_context"
    return "", "none"

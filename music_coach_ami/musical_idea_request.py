"""Shared musical-idea request profile for AMI generators (bass line, future licks/riffs)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MusicalIdeaRequest:
    """Normalized generation intent — explicit wording beats saved context."""

    object_type: str  # bass_line | lick | riff | phrase | pattern
    style: str
    difficulty: str  # beginner | intermediate | advanced | ""
    register: str  # low | mid | high | ""
    rhythmic_character: str


def _clean(text: object) -> str:
    return str(text or "").strip()


def parse_musical_idea_request(
    question: str,
    *,
    default_object: str = "bass_line",
    practice_focus: str = "",
    level: str = "",
) -> MusicalIdeaRequest:
    low = _clean(question).lower()
    focus = _clean(practice_focus).lower()

    object_type = default_object
    if re.search(r"\b(lick|riff|phrase|pattern)\b", low):
        if "riff" in low:
            object_type = "riff"
        elif "lick" in low:
            object_type = "lick"
        elif "pattern" in low:
            object_type = "pattern"
        elif "phrase" in low:
            object_type = "phrase"

    style = ""
    if "walking" in low or "walking" in focus or "walk bass" in focus:
        style = "walking_bass"
    elif "blues" in low:
        style = "blues"
    elif focus:
        style = focus.replace(" ", "_")

    difficulty = ""
    if re.search(r"\b(very easy|super easy|easy|simple|beginner)\b", low):
        difficulty = "beginner"
    elif re.search(r"\b(difficult|hard|advanced|challenging)\b", low):
        difficulty = "advanced"
    elif re.search(r"\bintermediate\b", low):
        difficulty = "intermediate"

    register = ""
    if re.search(r"\b(high|upper[- ]?register|very high)\b", low):
        register = "high"
    elif re.search(r"\b(low|lower[- ]?register|low-register)\b", low):
        register = "low"

    rhythmic = ""
    if "walking" in style or "quarter" in low:
        rhythmic = "quarter_walk"
    elif "half note" in low:
        rhythmic = "half_notes"

    return MusicalIdeaRequest(
        object_type=object_type,
        style=style,
        difficulty=difficulty,
        register=register,
        rhythmic_character=rhythmic,
    )


def resolve_generation_level(idea: MusicalIdeaRequest, context_level: str) -> str:
    """Explicit request difficulty overrides saved context level."""
    if idea.difficulty:
        return idea.difficulty
    return _clean(context_level) or "Intermediate"

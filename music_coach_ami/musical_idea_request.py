"""Shared musical-idea request profile for AMI generators (bass line, future licks/riffs)."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class MusicalIdeaRequest:
    """Normalized generation intent — explicit wording beats saved context.

    ``object_type`` is the musical *role* (bass_line, lick, …), not the instrument.
    Instrument / level / focus are resolved realization constraints.
    """

    object_type: str  # bass_line | lick | riff | phrase | pattern | …
    style: str
    difficulty: str  # beginner | intermediate | advanced | ""
    register: str  # low | mid | high | ""
    rhythmic_character: str
    explicit_key: str = ""  # optional key center named in the question
    instrument: str = ""
    level: str = ""
    practice_focus: str = ""
    meter: str = ""
    tempo_bpm: int | None = None
    section: str = ""
    duration_minutes: int | None = None
    articulation: str = ""


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
    if re.search(r"\bbass[- ]?line\b|\bwalking bass\b|\bbassline\b", low):
        object_type = "bass_line"
    elif re.search(r"\b(lick|riff|phrase|pattern)\b", low):
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
    elif "phras" in low or "phras" in focus:
        style = "phrasing"
    elif "rhythm" in low or "rhythm" in focus:
        style = "rhythm"
    elif "articul" in low or "articul" in focus:
        style = "articulation"
    elif "harmon" in low or "harmon" in focus:
        style = "harmony"
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
    elif re.search(r"\bmid(?:dle)?[- ]?register\b", low):
        register = "mid"

    rhythmic = ""
    if "walking" in style or "quarter" in low:
        rhythmic = "quarter_walk"
    elif "half note" in low:
        rhythmic = "half_notes"
    elif "syncop" in low or style == "rhythm":
        rhythmic = "syncopated"
    elif style == "phrasing":
        rhythmic = "phrased"

    articulation = ""
    if "staccato" in low:
        articulation = "staccato"
    elif "legato" in low:
        articulation = "legato"
    elif style == "articulation":
        articulation = "articulated"

    explicit_key = ""
    key_match = re.search(
        r"\bin\s+(?:the\s+key\s+of\s+)?([A-Ga-g](?:#|b)?m?)\b(?:\s+(?:major|minor))?",
        low,
    )
    if key_match:
        token = key_match.group(1)
        explicit_key = token[0].upper() + token[1:]
        if "minor" in low[key_match.end() : key_match.end() + 12] and not explicit_key.lower().endswith("m"):
            # Keep token as written; spelling handled by theory layer.
            pass

    return MusicalIdeaRequest(
        object_type=object_type,
        style=style,
        difficulty=difficulty,
        register=register,
        rhythmic_character=rhythmic,
        explicit_key=explicit_key,
        practice_focus=_clean(practice_focus),
        level=_clean(level),
        articulation=articulation,
    )


def resolve_generation_level(idea: MusicalIdeaRequest, context_level: str) -> str:
    """Explicit request difficulty overrides saved context level."""
    if idea.difficulty:
        return idea.difficulty
    return _clean(context_level) or "Intermediate"


def resolve_musical_idea_request(
    question: str,
    *,
    default_object: str = "bass_line",
    instrument: str = "",
    level: str = "",
    practice_focus: str = "",
    meter: str = "",
    tempo_bpm: int | None = None,
    section: str = "",
    duration_minutes: int | None = None,
) -> MusicalIdeaRequest:
    """Parse question then attach realization context (instrument ≠ musical object)."""
    parsed = parse_musical_idea_request(
        question,
        default_object=default_object,
        practice_focus=practice_focus,
        level=level,
    )
    focus = _clean(parsed.practice_focus) or _clean(practice_focus)
    # Explicit style/focus from question already wins inside parse; else keep context focus.
    style = parsed.style or focus.replace(" ", "_").lower()
    return replace(
        parsed,
        instrument=_clean(instrument),
        level=resolve_generation_level(parsed, level),
        practice_focus=focus,
        style=style,
        meter=_clean(meter) or parsed.meter,
        tempo_bpm=tempo_bpm if tempo_bpm is not None else parsed.tempo_bpm,
        section=_clean(section) or parsed.section,
        duration_minutes=duration_minutes if duration_minutes is not None else parsed.duration_minutes,
    )


def musical_idea_to_diagnostics(idea: MusicalIdeaRequest) -> dict[str, Any]:
    return {
        "musical_object": idea.object_type,
        "idea_style": idea.style,
        "explicit_difficulty": idea.difficulty or None,
        "explicit_register": idea.register or None,
        "explicit_key": idea.explicit_key or None,
        "rhythmic_character": idea.rhythmic_character or None,
        "articulation": idea.articulation or None,
        "resolved_instrument": idea.instrument or None,
        "resolved_level": idea.level or None,
        "practice_focus": idea.practice_focus or None,
        "meter": idea.meter or None,
        "tempo_bpm": idea.tempo_bpm,
        "section": idea.section or None,
        "duration_minutes": idea.duration_minutes,
    }

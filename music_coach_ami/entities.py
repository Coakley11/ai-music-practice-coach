"""Entity and constraint extraction from normalized questions."""

from __future__ import annotations

import re

from music_coach_ami.app_knowledge import feature_by_question
from music_coach_ami.types import CoachConstraints, ExtractedEntities


_INSTRUMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bflute\b", "Flute"),
    (r"\bsax(ophone)?\b", "Saxophone"),
    (r"\bclarinet\b", "Clarinet"),
    (r"\btrumpet\b", "Trumpet"),
    (r"\bpiano\b", "Piano"),
    (r"\bguitar\b", "Guitar"),
    (r"\bvoice\b|\bvocal\b", "Voice"),
)


def normalize_musical_accidentals(text: str) -> str:
    """Unicode ♭/♯ → ASCII b/# for parsing; preserves letter names."""
    return (
        str(text or "")
        .replace("♭", "b")
        .replace("♯", "#")
        .replace("♮", "")
    )


def normalize_question(raw: str) -> str:
    text = normalize_musical_accidentals(str(raw or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text


def parse_duration_minutes(text: str) -> int | None:
    m = re.search(r"\b(\d{1,3})\s*[- ]?\s*minute", text, flags=re.I)
    if not m:
        return None
    try:
        return max(5, min(120, int(m.group(1))))
    except ValueError:
        return None


def extract_entities(normalized: str, context_instrument: str = "") -> ExtractedEntities:
    from music_coach_ami.request_resolution import parse_question_focus, parse_question_level

    low = normalized.lower()
    instrument = ""
    for pat, name in _INSTRUMENT_PATTERNS:
        if re.search(pat, low):
            instrument = name
            break
    if not instrument:
        instrument = str(context_instrument or "").strip()

    q_level, q_level_explicit = parse_question_level(normalized)
    q_focus, q_focus_explicit = parse_question_focus(normalized)

    skill = ""
    for topic, phrases in (
        ("tone", ("build tone", "for tone", "tone exercise", "tone", "airy", "breath support", "sound fuller")),
        ("articulation", ("articulation", "tonguing", "short notes", "slurs", "notes don't come out cleanly")),
        ("technique", ("finger technique", "finger speed", "fingerings", "technique")),
        ("transitions", ("transitions smoother", "smooth transitions")),
        ("improvisation", ("improv", "solo", "motif", "chord tone")),
    ):
        if any(p in low for p in phrases):
            skill = topic
            break

    theory = ""
    for tok in ("ii-v-i", "ii v i", "chord tone", "dorian", "motif", "syncopation", "phrasing", "transposition"):
        if tok in low:
            theory = tok
            break

    return ExtractedEntities(
        instrument=instrument,
        skill_topic=skill,
        feature_id=feature_by_question(low),
        theory_topic=theory,
        requested_level=q_level,
        requested_level_explicit=q_level_explicit,
        practice_focus=q_focus or (skill if skill in ("tone", "articulation", "technique", "rhythm", "harmony") else ""),
        practice_focus_explicit=q_focus_explicit or bool(skill),
    )


def extract_constraints(normalized: str, entities: ExtractedEntities) -> CoachConstraints:
    low = normalized.lower()
    duration = parse_duration_minutes(normalized)
    return CoachConstraints(
        requested_duration_minutes=duration,
        tone_focus=entities.skill_topic == "tone" or "tone" in low,
        improvisation_focus=entities.skill_topic == "improvisation" or "improv" in low,
    )

"""One Music Generation Engine — single entry for creative musical output.

The engine owns phrase generation, rhythm, difficulty scaling, theory integration,
key spelling, chord-tone selection, ABC/TAB/MIDI, and playback hooks. Pages are
*goals*, not separate generators:

- **Missions** — educational constraints (``apply_mission_rules``)
- **Phrase & Motif** — idea generator (variants + transforms on active motif)
- **Composition Studio** — songwriting constraints (migrate from text hints)
- **AI Coach** — analysis first; call here only to illustrate feedback
- **Practice** — performance examples

See ``cursor-prompts/plans/2026-07-31-unified-motif-engine-and-coaching-profile.md``
and ``.cursor/rules/unified-motif-engine.mdc``.
"""

from __future__ import annotations

import random
from typing import Any

from improvisation_mission_rules import apply_mission_rules
from improvisation_motif import (
    _normalize_motif_level,
    build_motif_abc,
    build_motif_guitar_tab,
    build_motif_notation_abc,
    generate_motif_for_chord,
    generate_motif_with_variant,
    sync_motif_midi,
    transform_motif,
)

__all__ = [
    "ConstraintKind",
    "generate_musical_phrase",
    "generate_mission_phrase",
    "apply_mission_rules",
    "generate_motif_for_chord",
    "generate_motif_with_variant",
    "transform_motif",
    "sync_motif_midi",
    "build_motif_abc",
    "build_motif_notation_abc",
    "build_motif_guitar_tab",
]

ConstraintKind = str  # "mission" | "creative" | "composition" | "practice" | "coach"


def generate_mission_phrase(
    mission: str,
    chord: str,
    *,
    key_center: str,
    level: str,
    variant: str,
    rng: random.Random,
    idea_variant: int = 0,
) -> dict[str, Any]:
    """Mission examples: base phrase + ``apply_mission_rules`` (canonical mission path)."""
    student_level = _normalize_motif_level(level)
    tier = variant if variant in ("easier", "normal", "harder") else "normal"
    idea = idea_variant % 12
    if variant == "easier":
        idea = 0
    elif variant == "harder":
        idea = (idea_variant * 5 + 7) % 12
    elif variant == "new":
        tier = "normal"
        idea = idea_variant % 12

    motif = generate_motif_for_chord(
        chord,
        key_center=key_center,
        level=student_level,
        rng=rng,
        idea_variant=idea,
        difficulty_tier=tier,
    )
    return apply_mission_rules(
        mission,
        motif,
        chord=chord,
        key_center=key_center,
        level=student_level,
        variant=variant,
        rng=rng,
    )


class MissionMotifValidationError(RuntimeError):
    """Raised when no mission-compliant phrase could be generated."""


def generate_mission_phrase_validated(
    mission: str,
    chord: str,
    *,
    key_center: str,
    level: str,
    variant: str,
    rng: random.Random,
    idea_variant: int = 0,
    max_attempts: int = 16,
) -> dict[str, Any]:
    """Generate under mission rules and return only validator-passing phrases."""
    from improvisation_mission_specs import validate_mission_motif

    last: dict[str, Any] | None = None
    for attempt in range(max_attempts):
        idea = (idea_variant + attempt * 5) % 12
        candidate = generate_mission_phrase(
            mission,
            chord,
            key_center=key_center,
            level=level,
            variant=variant,
            rng=random.Random(rng.randint(0, 2**30) ^ idea),
            idea_variant=idea,
        )
        last = candidate
        ok, _reason = validate_mission_motif(
            mission,
            candidate,
            chord=chord,
            key_center=key_center,
        )
        if ok:
            candidate["_mission_valid"] = True
            return candidate
    if last is not None:
        ok_last, reason_last = validate_mission_motif(
            mission,
            last,
            chord=chord,
            key_center=key_center,
        )
        if ok_last:
            last["_mission_valid"] = True
            return last
        raise MissionMotifValidationError(reason_last or "mission validation failed")
    raise MissionMotifValidationError("no mission phrase generated")


def generate_musical_phrase(
    chord: str,
    *,
    key_center: str = "C",
    level: str = "Intermediate",
    kind: ConstraintKind = "creative",
    mission: str = "",
    variant: str = "normal",
    session_state: dict | None = None,
    rng: random.Random | None = None,
    idea_variant: int = 0,
) -> dict[str, Any]:
    """Generate a phrase; apply mission rules when ``kind == \"mission\"``."""
    if kind == "mission" and mission:
        return generate_mission_phrase(
            mission,
            chord,
            key_center=key_center,
            level=level,
            variant=variant if variant in ("easier", "normal", "harder", "new") else "normal",
            rng=rng or random.Random(idea_variant),
            idea_variant=idea_variant,
        )
    if variant in ("easier", "harder", "new"):
        return generate_motif_with_variant(
            chord,
            key_center=key_center,
            level=level,
            variant=variant,
            session_state=session_state,
        )
    return generate_motif_for_chord(
        chord,
        key_center=key_center,
        level=level,
        rng=rng,
        idea_variant=idea_variant,
    )

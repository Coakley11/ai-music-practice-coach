"""Canonical AMI exercise objects: request intent, resolved context and the generated exercise.

``GeneratedExercise`` is the authority. ABC, TAB, Written Key output and AMI prose are all derived
from it (``exercise_bridge``); no rendered string is ever read back as musical truth.

Slice 1 carries articulation / dynamics only as empty per-note placeholders and keeps ``span`` on the
context as a reserved slot, so later slices add behaviour without changing these shapes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

EXERCISE_SCHEMA_VERSION = 1

# Vocabulary names (what the user asked for), not engine names.
VOCAB_DEGREE_PATTERN = "degree_pattern"   # AMI's own scale / interval / sequence / lick generators (legacy path)
VOCAB_PENTATONIC = "pentatonic"
VOCAB_BLUES = "blues"
VOCAB_CHORD_TONES = "chord_tones"
VOCAB_GUIDE_TONES = "guide_tones"

ROUTE_LEGACY = "legacy_ami"
ROUTE_BRIDGE = "mission_bridge"


def _from_dict(cls: Any, raw: Any) -> Any:
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in dict(raw or {}).items() if k in names})


@dataclass(frozen=True)
class ExerciseIntent:
    """What the user asked for, as structure. ``explicit_fields`` records what they actually said."""

    raw_question: str = ""
    vocabulary: str = VOCAB_DEGREE_PATTERN
    collection: str = ""            # minor pentatonic | major pentatonic | minor blues | major blues | ""
    both_thirds: bool = False       # blues: flat 3rd AND natural 3rd requested together
    form: str = ""                  # pattern | line | lick | phrase | motif | exercise | riff | idea
    scope: str = "single_chord"     # single_chord | section | span (a 2-/3-chord HarmonicSpan; guide tones in Slice 4)
    explicit_key: str = ""
    explicit_chord: str = ""
    level_override: str = ""
    length_bars: int | None = None
    rhythm_request: str = ""
    articulation_request: str = ""  # the words the user used (kept for provenance)
    dynamics_request: str = ""
    expression: dict = field(default_factory=dict)   # structured request (exercise_expression.parse_expression)
    transform: str = ""             # placeholder for follow-ups ("another", "easier", "move up" ...)
    variation_index: int = 0
    span_length: int = 0            # scope == "span": chords asked for (2 or 3); 0 = not stated ("these chords")
    span_relationship: str = ""     # scope == "span": the harmonic relationship asked for (ii_V | ii_V_I | V_I)
    span_cue: str = ""              # the words that asked for a span (kept for provenance)
    span_unsupported: str = ""      # scope == "span": why this vocabulary cannot be carried across chords yet
    engine_route: str = ROUTE_LEGACY
    route_reason: str = ""
    explicit_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActiveContext:
    """Everything resolved from the app, with where each important value came from."""

    concert_key: str = "C"
    key_source: str = "default"     # explicit_request | mission_practice_key | practice_chart_key | default
    key_candidates: dict[str, str] = field(default_factory=dict)  # losing candidates, for provenance
    written_key: str = ""
    written_transposition_applied: bool = False
    transposition_semitones: int = 0
    instrument: str = ""
    notation_instrument: str = ""
    song_title: str = ""
    section: str = ""
    selected_chord: str = ""        # concert chord the app has selected, if any
    chord_source: str = ""          # how the chord actually used was decided: explicit_request |
                                    # synthesized_from_collection | mission_chord_click | mission_selected_chord |
                                    # chart_active_section_first_chord | tonic_of_key | none
    mission_active: bool = False
    active_mission: str = ""
    mission_authority: dict[str, Any] = field(default_factory=dict)  # surface + evidence, or why it is not active
    level: str = "Intermediate"
    level_source: str = "default"
    style: str = ""
    meter: str = "4/4"
    tempo_bpm: int = 96
    practice_focus: str = ""
    span: dict[str, Any] | None = None   # scope == "span": how the HarmonicSpan was chosen (see exercise_span)
    field_sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GeneratedExercise:
    """The canonical AMI exercise. Concert pitch is the source; ``written`` is a derived projection."""

    id: str
    intent: ExerciseIntent
    context: ActiveContext
    engine: str                      # which generator produced the notes
    engine_detail: str = ""          # function / mission vocabulary used
    vocabulary: str = ""
    seed: int = 0
    attempts: int = 0
    collection_label: str = ""
    collection_notes: list[str] = field(default_factory=list)   # concert spelling, in scale order
    chord: str = ""                  # concert chord the line is built over
    tonic: str = ""                  # concert tonic of the collection / key
    mode: str = ""                   # major | minor
    notes: list[str] = field(default_factory=list)              # concert spelling
    midi: list[int] = field(default_factory=list)               # concert pitch
    rhythm_events: list[dict[str, Any]] = field(default_factory=list)
    rhythm_symbols: list[str] = field(default_factory=list)
    meter: str = "4/4"
    bars: int = 1
    roles: list[str] = field(default_factory=list)             # per note: scale-degree label (1, b3, 3, b5 ...)
    chord_roles: list[str] = field(default_factory=list)       # per note: R/3/5/7 when a chord tone, else ""
    chord_assignment: list[int] = field(default_factory=list)  # per note: index into ``chords`` (one chord now)
    chords: list[str] = field(default_factory=list)
    articulation: list[str] = field(default_factory=list)      # per note: "" | staccato | tenuto | tongued
    dynamics: list[str] = field(default_factory=list)          # per note: effective level pp..ff ("" = unmarked)
    accents: list[bool] = field(default_factory=list)          # per note: accented
    slur_groups: list[int] = field(default_factory=list)       # per note: 0 = none, equal ids are slurred together
    dynamic_marks: list[dict] = field(default_factory=list)    # notated level changes and hairpins (note indexes)
    expression: dict = field(default_factory=dict)             # request, rules applied, roles used, summary, capability
    validation: dict[str, Any] = field(default_factory=dict)
    written: dict[str, Any] = field(default_factory=dict)      # derived from concert: key, chord, notes, midi
    explanation_facts: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    parent_id: str = ""              # the exercise this one was transformed from ("" for a fresh request)
    transform: dict[str, Any] = field(default_factory=dict)   # kind, parameters, inherited / changed / overridden
    schema_version: int = EXERCISE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GeneratedExercise":
        """Rebuild the canonical object from its stored dict (older Slice 1 dicts have no parent / transform)."""
        data = dict(raw)
        data["intent"] = _from_dict(ExerciseIntent, data.get("intent"))
        data["context"] = _from_dict(ActiveContext, data.get("context"))
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})

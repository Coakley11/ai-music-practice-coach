"""Canonical AMI exercise objects: request intent, resolved context and the generated exercise.

``GeneratedExercise`` is the authority. ABC, TAB, Written Key output and AMI prose are all derived
from it (``exercise_bridge``); no rendered string is ever read back as musical truth.

Slice 1 carries articulation / dynamics only as empty per-note placeholders and keeps ``span`` on the
context as a reserved slot, so later slices add behaviour without changing these shapes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


@dataclass(frozen=True)
class ExerciseIntent:
    """What the user asked for, as structure. ``explicit_fields`` records what they actually said."""

    raw_question: str = ""
    vocabulary: str = VOCAB_DEGREE_PATTERN
    collection: str = ""            # minor pentatonic | major pentatonic | minor blues | major blues | ""
    both_thirds: bool = False       # blues: flat 3rd AND natural 3rd requested together
    form: str = ""                  # pattern | line | lick | phrase | motif | exercise | riff | idea
    scope: str = "single_chord"     # single_chord | section | span (span reserved for a later slice)
    explicit_key: str = ""
    explicit_chord: str = ""
    level_override: str = ""
    length_bars: int | None = None
    rhythm_request: str = ""
    articulation_request: str = ""  # placeholder: recorded, not applied in Slice 1
    dynamics_request: str = ""      # placeholder: recorded, not applied in Slice 1
    transform: str = ""             # placeholder for follow-ups ("another", "easier", "move up" ...)
    variation_index: int = 0
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
                                    # synthesized_from_collection | mission_selected_chord |
                                    # chart_current_chord | tonic_of_key | none
    mission_active: bool = False
    active_mission: str = ""
    level: str = "Intermediate"
    level_source: str = "default"
    style: str = ""
    meter: str = "4/4"
    tempo_bpm: int = 96
    practice_focus: str = ""
    span: dict[str, Any] | None = None   # reserved: HarmonicSpan record (a later slice)
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
    articulation: list[str] = field(default_factory=list)      # placeholder, one empty slot per note
    dynamics: list[str] = field(default_factory=list)          # placeholder, one empty slot per note
    validation: dict[str, Any] = field(default_factory=dict)
    written: dict[str, Any] = field(default_factory=dict)      # derived from concert: key, chord, notes, midi
    explanation_facts: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: int = EXERCISE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        return out

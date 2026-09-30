"""Structured data model for Practice Melody.

This is a new, independently-owned representation for the Practice page's
"Chart & Melody" tool. It is deliberately **not** the Motif/Phrase pattern
vocabulary (``improvisation_motif.py`` / ``motif_engine.py`` — flat note/
rhythm-symbol arrays with no bar/beat timeline, meant for short improvisation
patterns) and **not** Composition Studio's song-writing document
(``composition_document.py`` — a full song-authoring model with its own key/
tempo ownership and workflow phases).

The event shape below borrows the *shape* of Composition's melody event
(``pitch`` / ``midi`` / ``duration_beats`` / ``beat`` / ``measure`` /
``is_rest``) because it is already a proven, notation/sync-friendly wire
format — explicit measure/beat timeline, so downstream notation rendering,
Backing measure-highlighting, looping, and transposition all have something
concrete to walk. Practice Melody does not import or depend on
``composition_document`` or the Motif engine; it owns its own schema so it
can evolve against Catalog/Custom song charts without coupling to either.

Practice Melody never resolves or stores a canonical key of its own — the
``key_center`` on a ``PracticeMelody`` is a record of what key it was
generated *for* (supplied by the caller from ``songs/key_state.py``'s
resolver), not a new key owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1

# "original" is reserved for a future, legitimately-licensed/public-domain/
# authored melody source (see item 7 of the Practice Melody brief) and is not
# populated by any generator in this slice.
VALID_SOURCES = ("generated", "uploaded", "original")
VALID_LEVELS = ("Beginner", "Intermediate", "Advanced")
VALID_TONE_ROLES = ("chord_tone", "passing", "neighbor", "approach", "rest")


@dataclass(frozen=True)
class MelodyEvent:
    """One note or rest in a Practice Melody section.

    ``measure`` is 0-indexed within its owning section. ``beat`` is the
    offset (in beats) from the start of that measure. Rests carry
    ``pitch=None`` / ``midi=None``; sounding events always carry both.
    """

    measure: int
    beat: float
    duration_beats: float
    is_rest: bool
    pitch: str | None = None
    midi: int | None = None
    chord: str = ""
    tone_role: str = "rest"

    def to_dict(self) -> dict[str, Any]:
        return {
            "measure": self.measure,
            "beat": self.beat,
            "duration_beats": self.duration_beats,
            "is_rest": self.is_rest,
            "pitch": self.pitch,
            "midi": self.midi,
            "chord": self.chord,
            "tone_role": self.tone_role,
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "MelodyEvent":
        return MelodyEvent(
            measure=int(row["measure"]),
            beat=float(row["beat"]),
            duration_beats=float(row["duration_beats"]),
            is_rest=bool(row["is_rest"]),
            pitch=row.get("pitch"),
            midi=(int(row["midi"]) if row.get("midi") is not None else None),
            chord=str(row.get("chord") or ""),
            tone_role=str(row.get("tone_role") or "rest"),
        )


@dataclass(frozen=True)
class MelodySection:
    """A generated melody aligned to one chart section (e.g. "Verse 1").

    ``chords`` is one chord symbol per measure, mirroring the existing
    Catalog/Custom ``sections: dict[name, list[chord]]`` convention used
    throughout Practice/Backing — this keeps a Practice Melody section
    trivially re-alignable against the chart it was generated from.

    ``repeat_of`` is set when this section's chord progression exactly
    matched an earlier section in the same song: the generator deliberately
    reuses that section's melody rather than inventing a new one, so a
    repeated Verse/Chorus form stays melodically coherent instead of
    wandering.
    """

    section_id: str
    section_type: str
    measures: int
    beats_per_measure: float
    chords: tuple[str, ...]
    events: tuple[MelodyEvent, ...]
    repeat_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_type": self.section_type,
            "measures": self.measures,
            "beats_per_measure": self.beats_per_measure,
            "chords": list(self.chords),
            "events": [e.to_dict() for e in self.events],
            "repeat_of": self.repeat_of,
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "MelodySection":
        return MelodySection(
            section_id=str(row["section_id"]),
            section_type=str(row.get("section_type") or ""),
            measures=int(row["measures"]),
            beats_per_measure=float(row["beats_per_measure"]),
            chords=tuple(str(c) for c in row.get("chords") or ()),
            events=tuple(MelodyEvent.from_dict(e) for e in row.get("events") or ()),
            repeat_of=row.get("repeat_of"),
        )


@dataclass(frozen=True)
class PracticeMelody:
    """A complete Practice Melody for one song, at one level, one alternative.

    ``melody_id`` is stable for a given (song_id, level, alt_index, seed) —
    see ``practice_melody_generator._melody_id`` — so "Generate Another
    Melody" can be built on top of this later as a clean alt_index increment
    rather than uncontrolled randomness.
    """

    schema_version: int
    melody_id: str
    source: str
    song_id: str
    song_title: str
    level: str
    key_center: str
    meter: tuple[int, int]
    tempo_bpm: float
    style: str
    seed: int
    alt_index: int
    generator_version: str
    section_order: tuple[str, ...]
    sections: tuple[MelodySection, ...]

    def section_by_id(self, section_id: str) -> MelodySection | None:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "melody_id": self.melody_id,
            "source": self.source,
            "song_id": self.song_id,
            "song_title": self.song_title,
            "level": self.level,
            "key_center": self.key_center,
            "meter": list(self.meter),
            "tempo_bpm": self.tempo_bpm,
            "style": self.style,
            "seed": self.seed,
            "alt_index": self.alt_index,
            "generator_version": self.generator_version,
            "section_order": list(self.section_order),
            "sections": [s.to_dict() for s in self.sections],
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "PracticeMelody":
        meter_raw = row.get("meter") or (4, 4)
        return PracticeMelody(
            schema_version=int(row.get("schema_version") or SCHEMA_VERSION),
            melody_id=str(row["melody_id"]),
            source=str(row.get("source") or "generated"),
            song_id=str(row.get("song_id") or ""),
            song_title=str(row.get("song_title") or ""),
            level=str(row.get("level") or "Intermediate"),
            key_center=str(row.get("key_center") or "C"),
            meter=(int(meter_raw[0]), int(meter_raw[1])),
            tempo_bpm=float(row.get("tempo_bpm") or 100.0),
            style=str(row.get("style") or ""),
            seed=int(row.get("seed") or 0),
            alt_index=int(row.get("alt_index") or 0),
            generator_version=str(row.get("generator_version") or ""),
            section_order=tuple(str(s) for s in row.get("section_order") or ()),
            sections=tuple(MelodySection.from_dict(s) for s in row.get("sections") or ()),
        )


def validate_practice_melody(melody: PracticeMelody, *, tolerance: float = 1e-6) -> list[str]:
    """Structural validation only — never a judgment of musical quality.

    Checks: valid level/source, no duplicate section ids, each section's
    chord list length matches its measure count, and every measure's events
    tile it exactly (no gaps, no overlaps, no over/under-fill) via a running
    beat cursor. Returns a list of human-readable problems; empty means the
    melody is structurally sound.
    """
    problems: list[str] = []
    if melody.level not in VALID_LEVELS:
        problems.append(f"invalid level {melody.level!r}")
    if melody.source not in VALID_SOURCES:
        problems.append(f"invalid source {melody.source!r}")
    section_ids = [s.section_id for s in melody.sections]
    if len(section_ids) != len(set(section_ids)):
        problems.append("duplicate section_id values")

    for section in melody.sections:
        if len(section.chords) != section.measures:
            problems.append(
                f"{section.section_id}: chords length {len(section.chords)} "
                f"!= measures {section.measures}"
            )
        events_by_measure: dict[int, list[MelodyEvent]] = {}
        for ev in section.events:
            events_by_measure.setdefault(ev.measure, []).append(ev)
            if ev.measure < 0 or ev.measure >= section.measures:
                problems.append(f"{section.section_id}: event measure {ev.measure} out of range")
            if ev.tone_role not in VALID_TONE_ROLES:
                problems.append(f"{section.section_id}: invalid tone_role {ev.tone_role!r}")
            if ev.duration_beats <= 0:
                problems.append(
                    f"{section.section_id} m{ev.measure}: non-positive duration {ev.duration_beats}"
                )
            if ev.is_rest and (ev.pitch is not None or ev.midi is not None):
                problems.append(f"{section.section_id} m{ev.measure}: rest event carries a pitch")
            if not ev.is_rest and (ev.pitch is None or ev.midi is None):
                problems.append(f"{section.section_id} m{ev.measure}: sounding event missing pitch")

        for m_idx in range(section.measures):
            cursor = 0.0
            for ev in sorted(events_by_measure.get(m_idx, []), key=lambda e: e.beat):
                if abs(ev.beat - cursor) > tolerance:
                    problems.append(
                        f"{section.section_id} m{m_idx}: gap/overlap at beat {ev.beat}, "
                        f"expected {cursor}"
                    )
                cursor += ev.duration_beats
            if abs(cursor - section.beats_per_measure) > tolerance:
                problems.append(
                    f"{section.section_id} m{m_idx}: measure totals {cursor} beats, "
                    f"expected {section.beats_per_measure}"
                )
    return problems

"""Reusable melodic pattern vocabulary — data-driven practice cells for the motif engine.

Layering (see ``.cursor/rules/unified-motif-engine.mdc``)::

    music_theory            (keys, chord tones, spelling, pitch classes)
      → melodic_pattern_engine  (THIS MODULE: which notes, in what shape)
        → improvisation_motif   (register planning, sync_motif_midi, ABC, TAB)
          → motif_engine        (public facade for every page)

This module chooses **musical note content** only. It never renders notation,
never owns rhythm, and never decides guitar fingering.

Pattern families
----------------
A :class:`PatternFamily` is a small declarative record. Most families are a
*cell* of tokens evaluated against a harmonic context at an anchor pitch:

``S(k)``  k steps along the chord-scale from the anchor
``A(k)``  k steps along the chord tones from the anchor
``G(k)``  k steps along the guide tones (3rd / 7th) from the anchor
``N(t, d)``  chromatic approach: ``d`` semitones from the note at cell index ``t``
          (``t`` may itself be an ornament, forming a chromatic chain)
``D(t, d)``  diatonic neighbour: ``d`` chord-scale steps from the note at index ``t``
``P(t)``     chromatic passing tone strictly between the previous note and index ``t``

``N``/``D`` are *ornaments*: they always name the target they resolve to, so
a chromatic note can never appear without a musical reason. A few families
(bebop lines) use a ``builder`` instead of a static cell because their shape
depends on where chord tones fall.

Cells are sequenced through pitch levels (scale / chord / guide-tone / real
chromatic transposition / continuing line) with register planned for the
whole phrase before generation; direction reverses at the register limits
rather than octave-wrapping a note mid-pattern.

Output contract (pipeline safety)
---------------------------------
Every :class:`PatternNote` carries a spelled ``name`` and an absolute ``midi``
whose pitch class matches. Names are restricted to the ``NOTE_TO_MIDI``
vocabulary (no E#, Cb, or double accidentals) because
``improvisation_motif._midi_from_note`` falls back to C for unknown spellings,
which would break the pitch-class check in ``sync_motif_midi`` and discard the
planned register. Default register bounds match that module's
``_PATTERN_MIDI_LO``/``_PATTERN_MIDI_HI`` so ``_shift_phrase_into_bounds`` is a
no-op on this output.

Future AMI migration
--------------------
``music_coach_ami.musical_idea_engine`` (``_degree_cycle``,
``generate_scale_pattern``, ``generate_lick``) and ``music_coach_ami.melodic_motion``
keep a parallel degree/approach vocabulary. They can later call
:func:`generate_pattern` / :func:`generate_auto_pattern` and map each
:class:`PatternNote` (``name``, ``midi``, ``function``, ``target``) onto
``MusicalEvent`` while keeping their own rhythm packing. That migration is
intentionally out of scope here.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass
from typing import Any, Callable

from music_theory import (
    NOTE_TO_MIDI,
    classify_chord_quality,
    normalize_chord_for_theory,
    pitch_class_from_spelled_note,
    spell_chord_tones,
    spell_diatonic_scale_from_root,
    spell_pitch_class,
    split_chord,
    split_key_center,
)

DIFFICULTIES: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")
CATEGORIES: tuple[str, ...] = (
    "scalar",
    "interval",
    "chord_tone",
    "chromatic_approach",
    "enclosure",
    "arpeggio_scale",
    "bebop",
    "chromatic_sequence",
)
DIRECTIONS: tuple[str, ...] = ("ascending", "descending")

# Match improvisation_motif._PATTERN_MIDI_LO / _PATTERN_MIDI_HI (F3–E6).
DEFAULT_REGISTER: tuple[int, int] = (53, 88)
_REGISTER_CENTER = 67  # G4 — comfortable middle for staff and guitar

_LETTERS = "CDEFGAB"
_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_NATURAL_MINOR = (0, 2, 3, 5, 7, 8, 10)
# Chord-scale for chords whose root is outside the key (quality → mode).
_QUALITY_MODES: dict[str, tuple[int, ...]] = {
    "major": _MAJOR,
    "maj7": _MAJOR,
    "dom": (0, 2, 4, 5, 7, 9, 10),
    "sus": (0, 2, 4, 5, 7, 9, 10),
    "minor": (0, 2, 3, 5, 7, 9, 10),
    "m7": (0, 2, 3, 5, 7, 9, 10),
    "half-dim": (0, 1, 3, 5, 6, 8, 10),
    "dim": (0, 2, 3, 5, 6, 8, 9),
    "aug": (0, 2, 4, 6, 8, 9, 11),
}
_SEVENTH_QUALITIES = ("dom", "m7", "maj7", "half-dim", "dim")


# --------------------------------------------------------------------------- tokens

Token = tuple


def S(k: int) -> Token:
    return ("S", int(k))


def A(k: int) -> Token:
    return ("A", int(k))


def G(k: int) -> Token:
    return ("G", int(k))


def N(target: int, semitones: int) -> Token:
    return ("N", int(target), int(semitones))


def D(target: int, steps: int) -> Token:
    return ("D", int(target), int(steps))


def P(target: int) -> Token:
    return ("P", int(target))


_STRUCTURAL = ("S", "A", "G")


# --------------------------------------------------------------------------- data types


@dataclass(frozen=True)
class PatternFamily:
    """One reusable pattern concept (not a note list)."""

    id: str
    category: str
    name: str
    difficulty: str
    cell: tuple[Token, ...] = ()
    cell_desc: tuple[Token, ...] = ()  # explicit descending shape (else cell / mirror)
    builder: Callable[..., list[tuple[int, str, int | None]] | None] | None = None
    cell_size: int = 0  # builder families only
    start_roles: tuple[str, ...] = ("R", "3", "5")
    sequence: str = "scale"  # scale | chord | guide | real | continue
    sequence_step: int = 1  # collection steps (real: semitones)
    mirror: bool = False  # negate structural steps when moving downward
    chromatic: str = "none"  # none | targeted | required
    target_index: int | None = None  # landing chord tone within the cell
    qualities: tuple[str, ...] | None = None  # classify_chord_quality buckets
    directions: tuple[str, ...] = DIRECTIONS
    lengths: tuple[int, ...] = (8, 12, 16)
    description: str = ""

    @property
    def size(self) -> int:
        return self.cell_size if self.builder else len(self.cell)


@dataclass(frozen=True)
class PatternNote:
    name: str
    midi: int
    degree: str  # relative to the key tonic: "1", "b3", "#4"
    function: str  # chord_tone | scale | approach | neighbor | passing
    chromatic: bool  # outside the chord-scale
    chord_role: str  # R / 3 / 5 / 7 (or 2 / 4 / 6 for sus/6 frames) — "" if not a chord tone
    target: int | None = None  # cell index this ornament resolves to


@dataclass(frozen=True)
class HarmonicContext:
    key: str
    tonic: str
    mode: str
    key_pcs: tuple[int, ...]
    chord: str
    quality: str
    chord_names: tuple[str, ...]
    chord_pcs: tuple[int, ...]
    scale_names: tuple[str, ...]
    scale_pcs: tuple[int, ...]
    key_names: tuple[str, ...]
    guide_pcs: tuple[int, ...]
    bebop_frame_pcs: tuple[int, ...]

    def role_of(self, pc: int) -> str:
        pc %= 12
        if pc not in self.chord_pcs and pc not in self.bebop_frame_pcs:
            return ""
        root = self.chord_pcs[0]
        return _ROLE_BY_INTERVAL.get((pc - root) % 12, "")

    def pc_for_role(self, role: str) -> int | None:
        for pc in self.chord_pcs:
            if self.role_of(pc) == role:
                return pc
        return None

    def name_for_pc(self, pc: int) -> str | None:
        pc %= 12
        for names, pcs in (
            (self.chord_names, self.chord_pcs),
            (self.scale_names, self.scale_pcs),
            (self.key_names, self.key_pcs),
        ):
            if pc in pcs:
                return names[pcs.index(pc)]
        return None


@dataclass(frozen=True)
class PatternResult:
    family: PatternFamily
    context: HarmonicContext
    direction: str
    seed: int
    register: tuple[int, int]
    cells: tuple[tuple[PatternNote, ...], ...]

    @property
    def notes(self) -> list[str]:
        return [n.name for cell in self.cells for n in cell]

    @property
    def midi(self) -> list[int]:
        return [n.midi for cell in self.cells for n in cell]

    @property
    def degrees(self) -> list[str]:
        return [n.degree for cell in self.cells for n in cell]

    def targets(self) -> list[tuple[int, int, PatternNote]]:
        """(cell index, note index, note) for every resolution target in the pattern."""
        out: list[tuple[int, int, PatternNote]] = []
        for ci, cell in enumerate(self.cells):
            idxs = {n.target for n in cell if n.target is not None and cell[n.target].target is None}
            if self.family.target_index is not None:
                idxs.add(self.family.target_index)
            for ni in sorted(i for i in idxs if i is not None and i < len(cell)):
                out.append((ci, ni, cell[ni]))
        return out

    def display(self) -> str:
        return " | ".join(" – ".join(n.name for n in cell) for cell in self.cells)

    def to_motif_fields(self) -> dict[str, Any]:
        """Pitch fields for a motif dict (rhythm is owned elsewhere)."""
        first = self.cells[0] if self.cells else ()
        return {
            "chord": self.context.chord,
            "notes": self.notes,
            "midi": self.midi,
            "cells": [[n.name for n in cell] for cell in self.cells],
            "display": self.display(),
            "is_pattern": True,
            "pattern_family": self.family.id,
            "pattern_category": self.family.category,
            "pattern_difficulty": self.family.difficulty,
            "pattern_direction": self.direction,
            "pattern_length": len(self.cells),
            "base_motif_notes": [n.name for n in first],
            "base_motif_midi": [n.midi for n in first],
        }


# --------------------------------------------------------------------------- theory helpers

_ROLE_BY_INTERVAL: dict[int, str] = {
    0: "R",
    1: "b9",
    2: "2",
    3: "3",
    4: "3",
    5: "4",
    6: "5",
    7: "5",
    8: "5",
    9: "6",
    10: "7",
    11: "7",
}


def _safe_name(name: str) -> str:
    """Spell within the NOTE_TO_MIDI vocabulary (E#→F, Cb→B, Bbb→A)."""
    text = str(name or "").strip()
    if text in NOTE_TO_MIDI:
        return text
    pc = pitch_class_from_spelled_note(text)
    return spell_pitch_class(pc, mode="sharp" if "#" in text or "x" in text else "flat")


def _pc(name: str) -> int:
    return int(pitch_class_from_spelled_note(name)) % 12


def _chord_head(chord: str) -> str:
    head = normalize_chord_for_theory(chord).split("/", 1)[0].strip()
    return head or str(chord or "").split("/", 1)[0].strip()


def _chord_scale_raw(key_raw: list[str], key_pcs: list[int], chord: str, quality: str) -> list[str]:
    """Chord-scale spelled with letters.

    Chord root inside the key: keep the key scale but let each chord tone replace
    the same-letter scale degree (G7 in C minor → B natural; D7 in C → F#).
    Chord root outside the key: the default mode for the chord quality.
    """
    head = _chord_head(chord)
    root = split_chord(head)[0] or "C"
    tones = spell_chord_tones(head)
    if _pc(root) in key_pcs:
        by_letter = {t[0].upper(): t for t in tones}
        return [by_letter.get(n[0].upper(), n) for n in key_raw]
    return spell_diatonic_scale_from_root(root, _QUALITY_MODES.get(quality, _MAJOR))


def build_context(key: str, chord: str | None = None) -> HarmonicContext:
    """Harmonic frame for pattern generation. No chord → the key's tonic 7th chord."""
    tonic, mode = split_key_center(str(key or "C"))
    key_raw = spell_diatonic_scale_from_root(tonic, _NATURAL_MINOR if mode == "minor" else _MAJOR)
    key_pcs = [_pc(n) for n in key_raw]
    chord_sym = str(chord or "").strip() or f"{tonic}{'m7' if mode == 'minor' else 'maj7'}"
    quality = classify_chord_quality(chord_sym)
    chord_raw = spell_chord_tones(_chord_head(chord_sym))
    chord_pcs = [_pc(n) for n in chord_raw]
    scale_raw = _chord_scale_raw(key_raw, key_pcs, chord_sym, quality)
    scale_pcs = [_pc(n) for n in scale_raw]

    guide: list[int] = []
    if len(chord_pcs) >= 4:
        guide = [chord_pcs[1], chord_pcs[3]]
    if quality in ("major", "maj7", "aug"):
        # Bebop 6th-chord frame: R 3 5 6 (6 = chord-scale degree 6).
        frame = chord_pcs[:3] + [scale_pcs[5]]
    elif len(chord_pcs) >= 4:
        frame = chord_pcs[:4]
    else:
        frame = chord_pcs[:3] + [scale_pcs[6]]

    return HarmonicContext(
        key=str(key or "C"),
        tonic=tonic,
        mode=mode,
        key_pcs=tuple(key_pcs),
        chord=chord_sym,
        quality=quality,
        chord_names=tuple(_safe_name(n) for n in chord_raw),
        chord_pcs=tuple(chord_pcs),
        scale_names=tuple(_safe_name(n) for n in scale_raw),
        scale_pcs=tuple(scale_pcs),
        key_names=tuple(_safe_name(n) for n in key_raw),
        guide_pcs=tuple(guide),
        bebop_frame_pcs=tuple(dict.fromkeys(frame)),
    )


def _step(midi: int, steps: int, pcs: tuple[int, ...] | set[int]) -> int:
    """Walk ``steps`` members of a pitch-class collection in absolute register."""
    m = int(midi)
    if not steps or not pcs:
        return m
    direction = 1 if steps > 0 else -1
    for _ in range(abs(int(steps))):
        m += direction
        while m % 12 not in pcs:
            m += direction
    return m


def _nearest(pc: int, near: int) -> int:
    base = (int(near) // 12) * 12 + int(pc) % 12
    return min((base - 12, base, base + 12), key=lambda m: abs(m - near))


def _degree_label(name: str, pc: int, ctx: HarmonicContext) -> str:
    if pc in ctx.key_pcs:
        return str(ctx.key_pcs.index(pc) + 1)
    d = (_LETTERS.index(name[0].upper()) - _LETTERS.index(ctx.tonic[0].upper())) % 7
    delta = (pc - ctx.key_pcs[d]) % 12
    if delta == 1:
        return f"#{d + 1}"
    if delta == 11:
        return f"b{d + 1}"
    # Letter-safe spelling hid the degree (e.g. F for E#) — fall back to a semitone label.
    return f"+{(pc - ctx.key_pcs[0]) % 12}"


def _ornament_name(pc: int, *, above_target: bool, ctx: HarmonicContext) -> str:
    """Scale/chord spelling when available; else flats above a target, sharps below."""
    named = ctx.name_for_pc(pc)
    if named and (pc in ctx.scale_pcs or pc in ctx.chord_pcs):
        return named
    if pc == (ctx.chord_pcs[0] - 1) % 12:
        # Leading tone to the chord root (dominant-bebop major 7th): G7 → F#, not Gb.
        return spell_pitch_class(pc, mode="sharp")
    return spell_pitch_class(pc, mode="flat" if above_target else "sharp")


def _note(ctx: HarmonicContext, midi: int, function: str, target: int | None, name: str | None = None) -> PatternNote:
    pc = int(midi) % 12
    spelled = _safe_name(name or ctx.name_for_pc(pc) or spell_pitch_class(pc, mode="sharp"))
    return PatternNote(
        name=spelled,
        midi=int(midi),
        degree=_degree_label(spelled, pc, ctx),
        function=function,
        chromatic=pc not in ctx.scale_pcs,
        chord_role=ctx.role_of(pc),
        target=target,
    )


# --------------------------------------------------------------------------- builders (bebop)


def _bebop_run(ctx: HarmonicContext, start: int, sign: int, n: int) -> list[tuple[int, str, int | None]]:
    """Chord-scale line that inserts chromatic passing tones so frame tones land on even indices.

    This is the bebop-scale principle stated generally: whenever a frame tone
    (chord tone, or 6th for major chords) would fall on an off-beat, a chromatic
    passing tone is inserted between it and the previous note.
    """
    frame = set(ctx.bebop_frame_pcs)
    scale = set(ctx.scale_pcs)
    out: list[tuple[int, str, int | None]] = [(start, "chord_tone", None)]
    m = start
    while len(out) < n:
        nxt = _step(m, sign, scale)
        if (
            nxt % 12 in frame
            and len(out) % 2 == 1
            and abs(nxt - m) >= 2
            and len(out) + 2 <= n
        ):
            out.append((nxt - sign, "passing", len(out) + 1))
        out.append((nxt, "chord_tone" if nxt % 12 in ctx.chord_pcs else "scale", None))
        m = nxt
    return out[:n]


def _build_bebop_scale_run(ctx: HarmonicContext, anchor: int, sign: int) -> list[tuple[int, str, int | None]] | None:
    if anchor % 12 not in ctx.bebop_frame_pcs:
        return None
    return _bebop_run(ctx, anchor, sign, 8)


def _build_bebop_run_to_enclosure(ctx: HarmonicContext, anchor: int, sign: int) -> list[tuple[int, str, int | None]] | None:
    """Five-note bebop run, then enclose the next chord tone in the direction of travel."""
    if anchor % 12 not in ctx.bebop_frame_pcs:
        return None
    run = _bebop_run(ctx, anchor, sign, 5)
    last = run[-1][0]
    target = _step(last, sign, set(ctx.chord_pcs))
    upper = _step(target, 1, set(ctx.scale_pcs))
    lower = target - 1
    t_idx = len(run) + 2
    if upper != last:
        tail = [(upper, "neighbor", t_idx), (lower, "approach", t_idx)]
    elif target + 1 != last:
        # Run already ended on the upper scale neighbour: enclose chromatically from above.
        tail = [(target + 1, "approach", t_idx), (lower, "approach", t_idx)]
    else:
        tail = [(lower, "approach", t_idx), (upper, "neighbor", t_idx)]
    return run + tail + [(target, "chord_tone", None)]


# --------------------------------------------------------------------------- registry


def _fam(**kw: Any) -> PatternFamily:
    return PatternFamily(**kw)


_FAMILY_LIST: tuple[PatternFamily, ...] = (
    # ---- scalar (Beginner)
    _fam(id="scale_1234", category="scalar", name="Scale fragment 1-2-3-4", difficulty="Beginner",
         cell=(S(0), S(1), S(2), S(3)), mirror=True,
         description="Four stepwise notes, sequenced one scale step at a time."),
    _fam(id="scale_1235", category="scalar", name="Scale fragment 1-2-3-5", difficulty="Beginner",
         cell=(S(0), S(1), S(2), S(4)), mirror=True,
         description="Three steps then a skip to the fifth of the fragment."),
    _fam(id="scale_1232", category="scalar", name="Scale turn 1-2-3-2", difficulty="Beginner",
         cell=(S(0), S(1), S(2), S(1)), mirror=True,
         description="Up two steps and back — a small turn figure."),
    _fam(id="scale_12345", category="scalar", name="Five-note scale run", difficulty="Beginner",
         cell=(S(0), S(1), S(2), S(3), S(4)), mirror=True, sequence_step=2,
         description="Five-note run, each cell starting a third higher."),
    # ---- interval / permutation
    _fam(id="thirds_pairs", category="interval", name="Diatonic thirds", difficulty="Beginner",
         cell=(S(0), S(2)), mirror=True,
         description="Pairs of diatonic thirds moving stepwise."),
    _fam(id="perm_1324", category="interval", name="Permutation 1-3-2-4", difficulty="Intermediate",
         cell=(S(0), S(2), S(1), S(3)), mirror=True,
         description="Interlocked thirds: skip up, step back, skip up."),
    _fam(id="fourths_pairs", category="interval", name="Diatonic fourths", difficulty="Intermediate",
         cell=(S(0), S(3)), mirror=True,
         description="Pairs of diatonic fourths moving stepwise."),
    _fam(id="perm_1425", category="interval", name="Permutation 1-4-2-5", difficulty="Intermediate",
         cell=(S(0), S(3), S(1), S(4)), mirror=True,
         description="Interlocked fourths."),
    _fam(id="step_skip_1243", category="interval", name="Step-skip 1-2-4-3", difficulty="Intermediate",
         cell=(S(0), S(1), S(3), S(2)), mirror=True,
         description="Alternating step and skip with a turn back."),
    _fam(id="perm_1526", category="interval", name="Permutation 1-5-2-6", difficulty="Advanced",
         cell=(S(0), S(4), S(1), S(5)), mirror=True,
         description="Interlocked fifths — wide, pianistic permutation."),
    _fam(id="sixths_pairs", category="interval", name="Diatonic sixths", difficulty="Advanced",
         cell=(S(0), S(5), S(1), S(6)), mirror=True,
         description="Interlocked sixths across a wide span."),
    # ---- chord tones
    _fam(id="arpeggio_135", category="chord_tone", name="Triad arpeggio through inversions", difficulty="Beginner",
         cell=(A(0), A(1), A(2)), sequence="chord", mirror=True, start_roles=("R",),
         description="Arpeggio climbing through the chord's inversions."),
    _fam(id="arpeggio_1357", category="chord_tone", name="Seventh-chord arpeggio", difficulty="Intermediate",
         cell=(A(0), A(1), A(2), A(3)), sequence="chord", mirror=True, start_roles=("R", "3"),
         qualities=_SEVENTH_QUALITIES,
         description="Four-note arpeggio moving through inversions."),
    _fam(id="scale_into_chord_tone", category="chord_tone", name="Scale descent onto a chord tone", difficulty="Intermediate",
         cell=(S(3), S(2), S(1), A(0)), sequence="chord", target_index=3, start_roles=("R", "3", "5", "7"),
         description="Three scale steps falling onto each chord tone in turn."),
    _fam(id="guide_tone_leap", category="chord_tone", name="Guide tones: scale into 3rd/7th, leap to the other", difficulty="Intermediate",
         cell=(S(2), S(1), G(0), G(1)), sequence="guide", target_index=2, start_roles=("3", "7"),
         qualities=_SEVENTH_QUALITIES,
         description="Scale approach onto a guide tone, then leap to the other guide tone."),
    # ---- chromatic approaches
    _fam(id="lower_approach_arpeggio", category="chromatic_approach", name="Arpeggio with lower chromatic approach", difficulty="Intermediate",
         cell=(A(0), A(1), N(3, -1), A(2)), sequence="chord", chromatic="targeted", target_index=3,
         start_roles=("R", "3", "5"),
         description="Two chord tones, then a half step below the third chord tone resolving up."),
    _fam(id="upper_approach_cell", category="chromatic_approach", name="Upper chromatic approach", difficulty="Intermediate",
         cell=(A(1), N(2, 1), A(0), A(-1)), sequence="chord", chromatic="required", target_index=2,
         start_roles=("R", "5", "3", "7"),
         description="Chord tone above, half step above the target, target, chord tone below."),
    _fam(id="double_approach_below", category="chromatic_approach", name="Double approach from below", difficulty="Advanced",
         cell=(N(2, -2), N(2, -1), A(0), A(1)), sequence="chord", chromatic="required", target_index=2,
         start_roles=("3", "R", "5", "7"),
         description="Whole step then half step below a chord tone, resolving up."),
    _fam(id="double_approach_above", category="chromatic_approach", name="Double approach from above", difficulty="Advanced",
         cell=(N(2, 2), N(2, 1), A(0), A(-1)), sequence="chord", chromatic="required", target_index=2,
         start_roles=("5", "R", "3", "7"),
         description="Whole step then half step above a chord tone, resolving down."),
    _fam(id="chromatic_run_to_target", category="chromatic_approach", name="Chromatic run into a chord tone", difficulty="Advanced",
         cell=(N(1, -1), N(2, -1), N(3, -1), A(0)), cell_desc=(N(1, 1), N(2, 1), N(3, 1), A(0)),
         sequence="chord", chromatic="required", target_index=3, start_roles=("3", "5", "R", "7"),
         description="Three chromatic notes resolving onto a chord tone (from below ascending, above descending)."),
    # ---- enclosures
    _fam(id="enclosure_classic", category="enclosure", name="Enclosure: diatonic above, chromatic below", difficulty="Intermediate",
         cell=(D(2, 1), N(2, -1), A(0), A(1)), sequence="chord", chromatic="targeted", target_index=2,
         start_roles=("3", "5", "R", "7"),
         description="Scale tone above, half step below, target, next chord tone."),
    _fam(id="enclosure_below_first", category="enclosure", name="Enclosure: chromatic below, diatonic above", difficulty="Intermediate",
         cell=(N(2, -1), D(2, 1), A(0), A(1)), sequence="chord", chromatic="targeted", target_index=2,
         start_roles=("5", "3", "R", "7"),
         description="Half step below, scale tone above, target, next chord tone."),
    _fam(id="enclosure_chromatic", category="enclosure", name="Chromatic enclosure", difficulty="Intermediate",
         cell=(N(2, 1), N(2, -1), A(0), A(1)), sequence="chord", chromatic="required", target_index=2,
         start_roles=("R", "5", "3", "7"),
         description="Half step above, half step below, target, next chord tone."),
    _fam(id="enclosure_four_note", category="enclosure", name="Four-note enclosure", difficulty="Advanced",
         cell=(D(3, 1), D(3, -1), N(3, -1), A(0)), sequence="chord", chromatic="targeted", target_index=3,
         start_roles=("3", "5", "7", "R"),
         description="Scale above, scale below, half step below, target."),
    _fam(id="enclosure_double_chromatic", category="enclosure", name="Double-chromatic enclosure", difficulty="Advanced",
         cell=(N(3, 2), N(3, 1), N(3, -1), A(0)), sequence="chord", chromatic="required", target_index=3,
         start_roles=("3", "5", "R", "7"),
         description="Two half steps down from above, jump below, resolve up."),
    # ---- arpeggio + scale
    _fam(id="arpeggio_up_scale_down", category="arpeggio_scale", name="Diatonic 7th arpeggio up, scale down", difficulty="Intermediate",
         cell=(S(0), S(2), S(4), S(6), S(5), S(4), S(3), S(2)), mirror=True, start_roles=("R",),
         lengths=(8,),
         description="Arpeggiate the diatonic seventh chord on each degree, then walk back down."),
    _fam(id="scale_up_arpeggio_down", category="arpeggio_scale", name="Scale up, arpeggio down", difficulty="Intermediate",
         cell=(S(0), S(1), S(2), S(3), S(4), S(2), S(0), S(-1)), mirror=True, start_roles=("R",),
         lengths=(8,),
         description="Five-note scale run, then arpeggio back down past the start."),
    _fam(id="arpeggio_approach_ninth", category="arpeggio_scale", name="Arpeggio to the 9th with chromatic approach", difficulty="Advanced",
         cell=(S(0), S(2), S(4), S(6), N(5, -1), S(8)), chromatic="targeted",
         start_roles=("R",), lengths=(8, 12),
         description="Diatonic 7th arpeggio, then a half step below its 9th (a colour-tone target)."),
    # ---- bebop
    _fam(id="bebop_scale_run", category="bebop", name="Bebop-scale line", difficulty="Advanced",
         builder=_build_bebop_scale_run, cell_size=8, sequence="continue", chromatic="targeted",
         start_roles=("R", "3", "5", "7"), lengths=(8, 12),
         description="Chord-scale line with passing tones placing chord tones on the beat."),
    _fam(id="bebop_run_to_enclosure", category="bebop", name="Bebop run into an enclosure", difficulty="Advanced",
         builder=_build_bebop_run_to_enclosure, cell_size=8, sequence="continue", chromatic="targeted",
         target_index=7, start_roles=("R", "3", "5", "7"), lengths=(8, 12),
         description="Bebop-scale run, then enclose the next chord tone."),
    _fam(id="bebop_passing_descent", category="bebop", name="Chord tone, step, chromatic passing, chord tone", difficulty="Advanced",
         cell=(A(0), S(-1), P(3), A(-1)), sequence="guide", chromatic="required", target_index=3,
         start_roles=("7", "3"), qualities=_SEVENTH_QUALITIES,
         description="From a guide tone, step down, then a chromatic passing tone into the next chord tone."),
    # ---- chromatic (real) sequences
    _fam(id="chromatic_sequence_1235", category="chromatic_sequence", name="1-2-3-5 cell moved by half steps", difficulty="Advanced",
         cell=(S(0), S(1), S(2), S(4)), sequence="real", sequence_step=1, chromatic="required",
         start_roles=("R",),
         description="A diatonic cell transposed exactly by half steps (real sequence)."),
    _fam(id="chromatic_arpeggio_sequence", category="chromatic_sequence", name="Arpeggio cell moved by half steps", difficulty="Advanced",
         cell=(A(0), A(1), A(2), A(1)), sequence="real", sequence_step=1, chromatic="required",
         start_roles=("R",),
         description="Chord arpeggio cell transposed exactly by half steps."),
)

PATTERN_FAMILIES: dict[str, PatternFamily] = {f.id: f for f in _FAMILY_LIST}


def get_family(family_id: str) -> PatternFamily:
    try:
        return PATTERN_FAMILIES[str(family_id)]
    except KeyError as exc:
        raise KeyError(f"unknown pattern family: {family_id!r}") from exc


def list_families(*, category: str | None = None, difficulty: str | None = None) -> list[PatternFamily]:
    return [
        f
        for f in _FAMILY_LIST
        if (category is None or f.category == category)
        and (difficulty is None or f.difficulty == difficulty)
    ]


# --------------------------------------------------------------------------- realization


def _cell_tokens(family: PatternFamily, sign: int) -> tuple[Token, ...]:
    if sign < 0 and family.cell_desc:
        return family.cell_desc
    if sign < 0 and family.mirror:
        return tuple((t[0], -t[1]) if t[0] in _STRUCTURAL else t for t in family.cell)
    return family.cell


def _realize_cell(
    family: PatternFamily, ctx: HarmonicContext, anchor: int, sign: int
) -> list[PatternNote] | None:
    if family.builder is not None:
        raw = family.builder(ctx, anchor, sign)
        if not raw:
            return None
        cell = []
        for midi, function, target in raw:
            if function in ("approach", "neighbor", "passing") and target is not None:
                t_midi = raw[target][0]
                name = _ornament_name(midi % 12, above_target=midi > t_midi, ctx=ctx)
            else:
                name = None
            cell.append(_note(ctx, midi, function, target, name))
        return cell

    tokens = _cell_tokens(family, sign)
    scale, chord, guide = set(ctx.scale_pcs), set(ctx.chord_pcs), set(ctx.guide_pcs)
    midis: list[int | None] = [None] * len(tokens)
    for i, tok in enumerate(tokens):
        if tok[0] == "S":
            midis[i] = _step(anchor, tok[1], scale)
        elif tok[0] == "A":
            midis[i] = _step(anchor, tok[1], chord)
        elif tok[0] == "G":
            if not guide:
                return None
            midis[i] = _step(anchor, tok[1], guide)
    # Ornaments may target other ornaments (chromatic chains); resolve in dependency order.
    pending = [i for i, tok in enumerate(tokens) if tok[0] in ("N", "D", "P")]
    while pending:
        ready = [
            i
            for i in pending
            if midis[tokens[i][1]] is not None
            and (tokens[i][0] != "P" or (i > 0 and midis[i - 1] is not None))
        ]
        if not ready:
            return None
        for i in ready:
            tok = tokens[i]
            base = int(midis[tok[1]])
            if tok[0] == "N":
                midis[i] = base + tok[2]
            elif tok[0] == "D":
                midis[i] = _step(base, tok[2], scale)
            else:
                midis[i] = base + (1 if int(midis[i - 1]) > base else -1)
            pending.remove(i)

    cell: list[PatternNote] = []
    for i, tok in enumerate(tokens):
        m = int(midis[i])
        if tok[0] in _STRUCTURAL:
            fn = "chord_tone" if m % 12 in chord else "scale"
            cell.append(_note(ctx, m, fn, None))
        else:
            target = tok[1]
            above = m > int(midis[target])
            fn = {"N": "approach", "D": "neighbor", "P": "passing"}[tok[0]]
            cell.append(_note(ctx, m, fn, target, _ornament_name(m % 12, above_target=above, ctx=ctx)))
    return cell


def _transpose_cell(cell: list[PatternNote], semis: int, sign: int, ctx: HarmonicContext) -> list[PatternNote]:
    out = []
    for n in cell:
        m = n.midi + semis
        pc = m % 12
        name = ctx.key_names[ctx.key_pcs.index(pc)] if pc in ctx.key_pcs else spell_pitch_class(
            pc, mode="sharp" if sign > 0 else "flat"
        )
        fn = n.function if n.function != "scale" or pc in ctx.scale_pcs else "scale"
        out.append(_note(ctx, m, fn, n.target, name))
    return out


def cell_problems(cell: list[PatternNote] | tuple[PatternNote, ...], family: PatternFamily) -> list[str]:
    """Musical-validity problems for one realized cell (empty list = valid)."""
    probs: list[str] = []
    for i in range(1, len(cell)):
        if cell[i].midi == cell[i - 1].midi:
            probs.append(f"repeated pitch at {i}")
    for i, n in enumerate(cell):
        if n.target is None:
            if n.chromatic and family.sequence != "real":
                probs.append(f"untargeted chromatic note {n.name} at {i}")
            continue
        if not (i < n.target < len(cell)):
            probs.append(f"ornament {i} does not resolve forward")
            continue
        t = cell[n.target]
        dist = abs(n.midi - t.midi)
        limit = 3 if n.function == "neighbor" else 2
        if dist == 0 or dist > limit:
            probs.append(f"ornament {n.name} is {dist} semitones from target {t.name}")
        if n.function in ("approach", "passing") and i > 0 and cell[i - 1].midi == t.midi:
            probs.append(f"{n.name} is a neighbour figure around {t.name}, not an approach")
        if n.function == "passing":
            prev = cell[i - 1].midi if i > 0 else None
            if prev is None or not (min(prev, t.midi) < n.midi < max(prev, t.midi)):
                probs.append(f"passing tone {n.name} is not between its neighbours")
    if family.chromatic == "none" and any(n.chromatic for n in cell):
        probs.append("chromatic note in a diatonic family")
    if family.target_index is not None and family.target_index < len(cell):
        tgt = cell[family.target_index]
        if not tgt.chord_role:
            probs.append(f"target {tgt.name} is not a chord tone")
    if family.category == "enclosure" and family.target_index is not None:
        t_midi = cell[family.target_index].midi
        orn = [n.midi for n in cell if n.target == family.target_index]
        if not (any(m > t_midi for m in orn) and any(m < t_midi for m in orn)):
            probs.append("enclosure does not surround its target")
    return probs


def _next_anchor(family: PatternFamily, ctx: HarmonicContext, anchor: int, sign: int, prev_cell: list[PatternNote]) -> int:
    step = sign * max(1, family.sequence_step)
    if family.sequence == "chord":
        return _step(anchor, step, set(ctx.chord_pcs))
    if family.sequence == "guide":
        return _step(anchor, step, set(ctx.guide_pcs))
    if family.sequence == "continue":
        pool = set(ctx.bebop_frame_pcs) if family.builder else set(ctx.chord_pcs)
        return _step(prev_cell[-1].midi, sign, pool)
    return _step(anchor, step, set(ctx.scale_pcs))


def _advance(family: PatternFamily, ctx: HarmonicContext, anchor: int, sign: int) -> int:
    """Try the next member of the sequence collection when an anchor yields an invalid cell."""
    if family.sequence == "guide":
        return _step(anchor, sign, set(ctx.guide_pcs))
    if family.sequence in ("chord", "continue"):
        pool = set(ctx.bebop_frame_pcs) if family.builder else set(ctx.chord_pcs)
        return _step(anchor, sign, pool)
    return _step(anchor, sign, set(ctx.scale_pcs))


def _in_bounds(cell: list[PatternNote], sign: int, lo: int, hi: int) -> bool:
    del sign  # both edges matter: ornaments can sit below an ascending anchor
    return min(n.midi for n in cell) >= lo and max(n.midi for n in cell) <= hi


def _sequence(
    family: PatternFamily,
    ctx: HarmonicContext,
    anchor0: int,
    sign0: int,
    n_cells: int,
    bounds: tuple[int, int] | None,
) -> list[list[PatternNote]] | None:
    first = _realize_cell(family, ctx, anchor0, sign0)
    if first is None or cell_problems(first, family):
        return None
    cells = [first]
    if family.sequence == "real":
        offset, sign = 0, sign0
        for _ in range(1, n_cells):
            nxt = offset + sign * family.sequence_step
            cand = _transpose_cell(first, nxt, sign, ctx)
            if bounds and not _in_bounds(cand, sign, *bounds):
                sign = -sign
                nxt = offset + sign * family.sequence_step
                cand = _transpose_cell(first, nxt, sign, ctx)
            offset = nxt
            cells.append(cand)
        return cells

    anchor, sign = anchor0, sign0
    for _ in range(1, n_cells):
        placed = None
        for flip in (False, True):
            if flip:
                if not bounds:
                    break
                sign = -sign
            cand_anchor = _next_anchor(family, ctx, anchor, sign, cells[-1])
            for _try in range(6):
                cell = _realize_cell(family, ctx, cand_anchor, sign)
                ok = cell is not None and not cell_problems(cell, family)
                if ok and cell[0].midi == cells[-1][-1].midi:
                    ok = False  # no repeated pitch across the cell boundary
                if ok and (not bounds or _in_bounds(cell, sign, *bounds)):
                    placed = (cand_anchor, cell)
                    break
                cand_anchor = _advance(family, ctx, cand_anchor, sign)
            if placed:
                break
        if not placed:
            return None
        anchor, cell = placed
        cells.append(cell)
    return cells


def _shift_cells(cells: list[list[PatternNote]], semis: int) -> list[list[PatternNote]]:
    if not semis:
        return cells
    return [[PatternNote(**{**n.__dict__, "midi": n.midi + semis}) for n in cell] for cell in cells]


def _plan_register(
    family: PatternFamily,
    ctx: HarmonicContext,
    anchor_pc: int,
    sign: int,
    n_cells: int,
    register: tuple[int, int],
) -> tuple[list[list[PatternNote]], bool] | None:
    """Plan the whole phrase's register before committing (octave shifts only).

    Returns ``(cells, turned_around)``; ``turned_around`` is True when the phrase
    was too wide for the window and reversed direction at a register limit.
    """
    lo, hi = register
    free = _sequence(family, ctx, _nearest(anchor_pc, 60 if sign > 0 else 74), sign, n_cells, None)
    if free is not None:
        flat = [n.midi for c in free for n in c]
        if max(flat) - min(flat) <= hi - lo:
            options = [
                k * 12
                for k in range(-4, 5)
                if min(flat) + k * 12 >= lo and max(flat) + k * 12 <= hi
            ]
            if options:
                mid = (min(flat) + max(flat)) / 2
                best = min(options, key=lambda s: abs(mid + s - _REGISTER_CENTER))
                return _shift_cells(free, best), False

    # Too wide for the window: start at the extreme for the direction and let the
    # sequence turn around at the limits (never wrap a single note).
    anchor = _nearest(anchor_pc, lo + 6 if sign > 0 else hi - 6)
    for _ in range(4):
        cell = _realize_cell(family, ctx, anchor, sign)
        if cell is None:
            return None
        if sign > 0 and min(n.midi for n in cell) < lo:
            anchor += 12
        elif sign < 0 and max(n.midi for n in cell) > hi:
            anchor -= 12
        else:
            break
    cells = _sequence(family, ctx, anchor, sign, n_cells, register)
    return None if cells is None else (cells, True)


def _stable_seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


def _normalize_direction(direction: str) -> str:
    d = str(direction or "ascending").strip().lower()
    return d if d in DIRECTIONS else "ascending"


def family_supports(family: PatternFamily, ctx: HarmonicContext, direction: str) -> bool:
    if direction not in family.directions:
        return False
    if family.qualities is not None and ctx.quality not in family.qualities:
        return False
    if family.sequence == "guide" and len(ctx.guide_pcs) < 2:
        return False
    return True


def generate_pattern(
    family: str | PatternFamily,
    *,
    key: str = "C",
    chord: str | None = None,
    direction: str = "ascending",
    length: int = 8,
    seed: int = 0,
    register: tuple[int, int] = DEFAULT_REGISTER,
) -> PatternResult:
    """Realize one family as a sequenced practice pattern of ``length`` cells.

    Deterministic: the same family/context/seed always returns the same notes.
    Consecutive seeds rotate through the valid starting chord tones, so a
    "new idea" that increments the seed always visits every start in turn.
    Raises ``ValueError`` when the family cannot be realized in this context.
    """
    fam = family if isinstance(family, PatternFamily) else get_family(family)
    ctx = build_context(key, chord)
    direction = _normalize_direction(direction)
    if not family_supports(fam, ctx, direction):
        raise ValueError(f"{fam.id} does not support {ctx.chord} ({ctx.quality}) {direction}")
    sign = 1 if direction == "ascending" else -1
    n_cells = max(1, min(32, int(length or 8)))
    roles = [r for r in fam.start_roles if ctx.pc_for_role(r) is not None]
    if fam.builder is not None:
        roles = [r for r in roles if ctx.pc_for_role(r) in ctx.bebop_frame_pcs] or roles
    if not roles:
        roles = ["R"]
    k = (_stable_seed(fam.id, ctx.key, ctx.chord, direction, n_cells) + int(seed)) % len(roles)
    order = roles[k:] + roles[:k]

    # Prefer, in seeded order: a start that keeps the requested direction for the whole
    # phrase, then one that turns around at a register limit. "required" families
    # must actually produce chromatic vocabulary.
    turned: list[list[list[PatternNote]]] = []
    for role in order:
        planned = _plan_register(fam, ctx, int(ctx.pc_for_role(role)), sign, n_cells, register)
        if planned is None:
            continue
        cells, turned_around = planned
        if fam.chromatic == "required" and not any(n.chromatic for c in cells for n in c):
            continue
        if turned_around:
            turned.append(cells)
            continue
        return PatternResult(fam, ctx, direction, int(seed), tuple(register), tuple(tuple(c) for c in cells))
    if turned:
        return PatternResult(fam, ctx, direction, int(seed), tuple(register), tuple(tuple(c) for c in turned[0]))
    raise ValueError(f"{fam.id} could not be realized over {ctx.chord} in {ctx.key}")


_DIFF_RANK = {d: i for i, d in enumerate(DIFFICULTIES)}
# How much chromatic vocabulary Auto / Musical mixes in, per student level.
_CHROMATIC_WEIGHT = {"Beginner": 0.0, "Intermediate": 0.6, "Advanced": 1.0}


def normalize_difficulty(level: str) -> str:
    low = str(level or "").lower()
    if "begin" in low:
        return "Beginner"
    if "adv" in low:
        return "Advanced"
    return "Intermediate"


def eligible_families(
    *,
    key: str,
    chord: str | None = None,
    difficulty: str = "Intermediate",
    direction: str = "ascending",
    chromatic: str = "auto",
    exact_level: bool = False,
) -> list[tuple[PatternFamily, float]]:
    """Families Auto / Musical may choose from, with selection weights.

    ``chromatic``: ``auto`` (level-appropriate mix), ``none`` (diatonic only),
    or ``prefer`` (weight chromatic families up).

    ``exact_level``: only families whose difficulty exactly matches (rather than
    the usual "at or below") — a student's very first Auto idea at a level should
    demonstrate that level, not a simpler one that happened to win the weighted draw.
    """
    ctx = build_context(key, chord)
    level = normalize_difficulty(difficulty)
    direction = _normalize_direction(direction)
    out: list[tuple[PatternFamily, float]] = []
    for fam in _FAMILY_LIST:
        if exact_level:
            if fam.difficulty != level:
                continue
        elif _DIFF_RANK[fam.difficulty] > _DIFF_RANK[level]:
            continue
        if not family_supports(fam, ctx, direction):
            continue
        is_chrom = fam.chromatic != "none"
        if chromatic == "none" and is_chrom:
            continue
        w = 3.0 if fam.difficulty == level else 1.0
        if is_chrom:
            cw = 1.5 if chromatic == "prefer" else _CHROMATIC_WEIGHT[level]
            if cw <= 0:
                continue
            w *= cw
        out.append((fam, w))
    return out


def generate_auto_pattern(
    *,
    key: str = "C",
    chord: str | None = None,
    difficulty: str = "Intermediate",
    direction: str = "ascending",
    length: int = 8,
    seed: int = 0,
    chromatic: str = "auto",
    register: tuple[int, int] = DEFAULT_REGISTER,
    exact_level: bool = False,
) -> PatternResult:
    """Auto / Musical: choose a musically appropriate family, then realize it.

    Same seed + context → same pattern; different seeds may choose another family
    or starting chord tone. Falls through to the next weighted choice when a
    family cannot be realized in this harmonic context. ``exact_level`` restricts
    the choice to families at exactly ``difficulty`` (see :func:`eligible_families`);
    raises ``ValueError`` if none of those can be realized here.
    """
    weighted = eligible_families(
        key=key, chord=chord, difficulty=difficulty, direction=direction, chromatic=chromatic,
        exact_level=exact_level,
    )
    if length in (8, 12, 16):
        weighted = [(f, w * (1.0 if length in f.lengths else 0.4)) for f, w in weighted]
    rng = random.Random(
        _stable_seed("auto", key, chord, normalize_difficulty(difficulty), direction, length, chromatic,
                     exact_level, seed)
    )
    pool = list(weighted)
    while pool:
        total = sum(w for _, w in pool)
        pick = rng.random() * total
        idx = 0
        for idx, (_, w) in enumerate(pool):
            pick -= w
            if pick <= 0:
                break
        fam = pool.pop(idx)[0]
        try:
            return generate_pattern(
                fam, key=key, chord=chord, direction=direction, length=length, seed=seed, register=register
            )
        except ValueError:
            continue
    raise ValueError(f"no pattern family could be realized for {chord or key} ({difficulty}, {direction})")


def validate_pattern(result: PatternResult) -> list[str]:
    """All musical-validity and pipeline-contract problems for a realized pattern."""
    probs: list[str] = []
    lo, hi = result.register
    sizes = {len(c) for c in result.cells}
    if len(sizes) > 1:
        probs.append(f"non-uniform cell sizes {sorted(sizes)}")
    for ci, cell in enumerate(result.cells):
        probs.extend(f"cell {ci}: {p}" for p in cell_problems(cell, result.family))
        for n in cell:
            if n.name not in NOTE_TO_MIDI:
                probs.append(f"cell {ci}: {n.name} is not a pipeline-safe spelling")
            if _pc(n.name) != n.midi % 12:
                probs.append(f"cell {ci}: {n.name} does not match MIDI {n.midi}")
    flat = result.midi
    if flat and (min(flat) < lo or max(flat) > hi):
        probs.append(f"register {min(flat)}–{max(flat)} outside {lo}–{hi}")
    if result.family.chromatic == "required" and not any(n.chromatic for c in result.cells for n in c):
        probs.append("family requires chromatic vocabulary but none was produced")
    return probs


__all__ = [
    "CATEGORIES",
    "DEFAULT_REGISTER",
    "DIFFICULTIES",
    "DIRECTIONS",
    "HarmonicContext",
    "PATTERN_FAMILIES",
    "PatternFamily",
    "PatternNote",
    "PatternResult",
    "build_context",
    "cell_problems",
    "eligible_families",
    "family_supports",
    "generate_auto_pattern",
    "generate_pattern",
    "get_family",
    "list_families",
    "normalize_difficulty",
    "validate_pattern",
]

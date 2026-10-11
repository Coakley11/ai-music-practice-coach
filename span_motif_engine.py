"""MC2 — one connected motif across a harmonic span (2–3 contiguous chords).

Consumes an MC1 :class:`~harmonic_span_analyzer.HarmonicSpan` and returns a motif dict
the existing renderers already understand (``notes`` / ``midi`` / engine rhythm), plus
the harmony metadata that makes it a *span* motif: an explicit chord timeline, a chord
assignment for every note, the target note at each change, and how the idea develops.

Pipeline (pure and deterministic for a given span / level / variant / focus / style / seed):

1. **Timeline** — one slot per chord event, keeping its bar count from the chart.
2. **Strategy family** — the material and contour of the idea (chord-tone cell, scalar
   fragment, pentatonic cell, guide-tone line, arpeggio + scale, enclosure line, bebop
   run, intervallic cell, lyrical arch, common-tone anchor, rhythmic motif, sequence,
   call-and-response), weighted by Level × Practice Focus × song style × harmony and
   drawn from the seed, so New Idea can change the whole architecture.
3. **Targets** — one landing note per chord, chosen by a voice-leading cost over all
   chord tones in register (common tones, half/whole steps, 7→3 and leading-tone
   resolutions rewarded; leaps penalized).
4. **Segments** — each chord realizes the family's contour from its target in the
   family's pitch space, then connectors lead into the next target: a diatonic step
   (Beginner), chromatic approach / enclosure (Intermediate), enclosures, double
   chromatics and harmony-selected dominant colour that resolves by step (Advanced).
5. **Musicality** — several candidates are built and scored (leaps, repeated notes,
   mechanical alternation, zig-zag, range, arc, step share, root abuse, resolution); the
   most coherent melodic sentence wins.
6. **Rhythm** — ``melodic_rhythm_engine.rhythm_candidates_by_bar`` with a fixed note
   count per bar (every pitch stays inside its chord, each target on the new chord's
   downbeat), ordered by Level / style / Practice Focus preferences.

The chord and key data are authoritative; the MC1 relationship label only steers style
of development, never which notes are legal.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Callable, Sequence

LENGTHS = ("seed", "standard", "extended")
REGISTER = (55, 81)  # G3–A5: comfortable written range for staff and guitar
CENTER = 67
_LEVELS = ("Beginner", "Intermediate", "Advanced")
_MAX_LEAP: dict[str, int] = {"Beginner": 7, "Intermediate": 9, "Advanced": 9}

# --------------------------------------------------------------------------- style / focus

STYLE_PROFILES: dict[str, dict[str, float]] = {
    # chromatic: appetite for approaches/enclosures; rhythm prefs drive candidate order.
    "jazz": {"density": 0, "chromatic": 1.0, "syncopation": 1.0, "triplets": 1.0, "sixteenths": 0.4, "long": 0.0},
    "jazz_ballad": {"density": -1, "chromatic": 0.7, "syncopation": 0.4, "triplets": 0.6, "sixteenths": 0.0, "long": 1.0},
    "bossa": {"density": 0, "chromatic": 0.7, "syncopation": 0.9, "triplets": 0.1, "sixteenths": 0.2, "long": 0.3},
    "blues": {"density": 0, "chromatic": 0.6, "syncopation": 0.7, "triplets": 0.8, "sixteenths": 0.1, "long": 0.2},
    "ballad": {"density": -1, "chromatic": 0.15, "syncopation": 0.2, "triplets": 0.0, "sixteenths": 0.0, "long": 1.0},
    "pop": {"density": 0, "chromatic": 0.25, "syncopation": 0.4, "triplets": 0.0, "sixteenths": 0.1, "long": 0.3},
    "rock": {"density": 0, "chromatic": 0.25, "syncopation": 0.5, "triplets": 0.0, "sixteenths": 0.1, "long": 0.2},
    "funk": {"density": 1, "chromatic": 0.35, "syncopation": 1.0, "triplets": 0.0, "sixteenths": 1.0, "long": 0.0},
    "folk": {"density": 0, "chromatic": 0.15, "syncopation": 0.2, "triplets": 0.0, "sixteenths": 0.0, "long": 0.5},
    "default": {"density": 0, "chromatic": 0.5, "syncopation": 0.5, "triplets": 0.3, "sixteenths": 0.2, "long": 0.3},
}
JAZZ_STYLES = {"jazz", "jazz_ballad", "bossa", "blues"}
LYRICAL_STYLES = {"ballad", "jazz_ballad", "folk"}
POP_STYLES = {"pop", "rock", "folk", "ballad", "funk"}


def song_style(
    genre: str = "",
    *,
    groove: str = "",
    bpm: Any = None,
    tags: Sequence[str] = (),
    jazz_ballad: bool = False,
) -> str:
    """Style bucket from the song's own metadata (genre, default groove, tags) — never its title."""
    g = str(genre or "").strip().lower()
    groove_l = str(groove or "").strip().lower()
    tags_l = " ".join(str(t).lower() for t in tags or ())
    try:
        tempo = float(bpm) if bpm not in (None, "") else None
    except (TypeError, ValueError):
        tempo = None
    balladish = "ballad" in groove_l or "ballad" in tags_l
    if g == "jazz" or "jazz" in groove_l or "bossa" in groove_l or "bossa" in tags_l:
        if jazz_ballad or balladish:
            return "jazz_ballad"
        return "bossa" if ("bossa" in groove_l or "bossa" in tags_l) else "jazz"
    if g == "blues":
        return "blues"
    if g == "funk" or "funk" in groove_l:
        return "funk"
    if balladish or (tempo is not None and tempo < 80 and g in ("pop", "rock", "soul", "country")):
        return "ballad"
    if g in ("rock",):
        return "rock"
    if g in ("pop", "soul", "country"):
        return "pop"
    if g in ("jewish", "classical", "folk"):
        return "folk"
    return "default"


def focus_preference(focus: str) -> str:
    """Map the existing Practice Focus label onto a melodic-generation preference."""
    low = " ".join(str(focus or "").strip().lower().split())
    if not low:
        return "neutral"
    keyword_map = (
        (("guide tone", "voice leading", "voicing", "comping", "inversion"), "guide_tones"),
        (("pentatonic",), "pentatonic"),
        (("bebop", "jazz phrasing"), "bebop"),
        (("scale",), "scales"),
        (("syncop", "rhythm", "groove", "pocket", "timing", "strum", "walking"), "rhythm"),
        (("improvis", "soloing", "lead", "motif"), "motif"),
        (("melody", "phrasing", "emotional", "double stop"), "lyrical"),
        (("harmony", "triad", "chord", "root motion", "reharmon"), "chord_tones"),
    )
    for words, pref in keyword_map:
        if any(w in low for w in words):
            return pref
    try:
        from practice_focus_policy import (
            CATEGORY_HARMONY,
            CATEGORY_IMPROVISATION,
            CATEGORY_MELODY,
            CATEGORY_PHRASING,
            CATEGORY_RHYTHM_GROOVE,
            CATEGORY_TIMING,
            category_for_focus,
        )

        cat = category_for_focus(focus)
        return {
            CATEGORY_HARMONY: "chord_tones",
            CATEGORY_RHYTHM_GROOVE: "rhythm",
            CATEGORY_TIMING: "rhythm",
            CATEGORY_MELODY: "lyrical",
            CATEGORY_PHRASING: "lyrical",
            CATEGORY_IMPROVISATION: "motif",
        }.get(cat, "neutral")
    except ImportError:
        return "neutral"


# --------------------------------------------------------------------------- families

FAMILIES: dict[str, dict[str, Any]] = {
    # space: chord | scale | pentatonic | bebop ; shape: cell | run | arch | arp_run | anchor | rhythmic | bebop
    "chord_tone_cell": {"levels": _LEVELS, "space": "chord", "shape": "cell"},
    "pentatonic_cell": {"levels": _LEVELS, "space": "pentatonic", "shape": "cell"},
    "scalar_fragment": {"levels": _LEVELS, "space": "scale", "shape": "run"},
    "lyrical_arch": {"levels": _LEVELS, "space": "scale", "shape": "arch", "density": -1},
    "common_tone_anchor": {"levels": ("Beginner", "Intermediate"), "space": "scale", "shape": "anchor"},
    "rhythmic_motif": {"levels": _LEVELS, "space": "chord", "shape": "rhythmic"},
    "guide_tone_line": {"levels": ("Intermediate", "Advanced"), "space": "scale", "shape": "cell", "roles": "guide"},
    "arpeggio_scale": {"levels": ("Intermediate", "Advanced"), "space": "scale", "shape": "arp_run"},
    "sequence": {"levels": ("Intermediate", "Advanced"), "space": "scale", "shape": "cell", "roles": "fixed"},
    "call_response": {"levels": ("Intermediate", "Advanced"), "space": "scale", "shape": "cell", "answer": True},
    "enclosure_line": {"levels": ("Intermediate", "Advanced"), "space": "scale", "shape": "run", "connector": "enclosure"},
    "bebop_run": {"levels": ("Advanced",), "space": "bebop", "shape": "bebop", "connector": "enclosure"},
    "intervallic_cell": {"levels": ("Advanced",), "space": "scale", "shape": "cell", "cells": "wide"},
}
_BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "Beginner": {
        "chord_tone_cell": 1.0, "scalar_fragment": 1.0, "pentatonic_cell": 0.8,
        "common_tone_anchor": 0.7, "lyrical_arch": 0.7, "rhythmic_motif": 0.5,
    },
    "Intermediate": {
        "guide_tone_line": 1.0, "scalar_fragment": 0.9, "arpeggio_scale": 0.9, "sequence": 0.8,
        "call_response": 0.7, "enclosure_line": 0.6, "pentatonic_cell": 0.5, "chord_tone_cell": 0.4,
        "lyrical_arch": 0.5, "rhythmic_motif": 0.5, "common_tone_anchor": 0.3,
    },
    "Advanced": {
        "bebop_run": 1.0, "enclosure_line": 0.9, "guide_tone_line": 0.8, "intervallic_cell": 0.8,
        "arpeggio_scale": 0.8, "sequence": 0.6, "call_response": 0.6, "scalar_fragment": 0.6,
        "pentatonic_cell": 0.3, "lyrical_arch": 0.3, "rhythmic_motif": 0.4,
    },
}
_STYLE_FACTORS: dict[str, dict[str, float]] = {
    "jazz": {"bebop_run": 1.4, "enclosure_line": 1.3, "guide_tone_line": 1.3, "pentatonic_cell": 0.6, "lyrical_arch": 0.7},
    "bossa": {"guide_tone_line": 1.3, "scalar_fragment": 1.2, "enclosure_line": 1.1, "pentatonic_cell": 0.6},
    "blues": {"pentatonic_cell": 1.6, "rhythmic_motif": 1.3, "enclosure_line": 1.1},
    "jazz_ballad": {"lyrical_arch": 2.0, "guide_tone_line": 1.4, "scalar_fragment": 1.2, "bebop_run": 0.5, "rhythmic_motif": 0.4},
    "ballad": {"lyrical_arch": 2.2, "scalar_fragment": 1.3, "chord_tone_cell": 1.1, "rhythmic_motif": 0.5,
               "bebop_run": 0.2, "enclosure_line": 0.3, "intervallic_cell": 0.4},
    "pop": {"pentatonic_cell": 1.8, "rhythmic_motif": 1.5, "lyrical_arch": 1.3, "chord_tone_cell": 1.2,
            "bebop_run": 0.2, "enclosure_line": 0.4, "intervallic_cell": 0.5, "guide_tone_line": 0.7},
    "rock": {"pentatonic_cell": 2.0, "rhythmic_motif": 1.6, "chord_tone_cell": 1.1, "bebop_run": 0.2, "enclosure_line": 0.4},
    "funk": {"rhythmic_motif": 2.2, "pentatonic_cell": 1.6, "bebop_run": 0.5},
    "folk": {"lyrical_arch": 1.8, "scalar_fragment": 1.4, "chord_tone_cell": 1.2, "bebop_run": 0.2, "enclosure_line": 0.3},
}
_FOCUS_FACTORS: dict[str, dict[str, float]] = {
    "chord_tones": {"chord_tone_cell": 2.5, "arpeggio_scale": 1.6, "common_tone_anchor": 1.3},
    "guide_tones": {"guide_tone_line": 3.0, "common_tone_anchor": 1.8, "chord_tone_cell": 1.4},
    "scales": {"scalar_fragment": 3.0, "lyrical_arch": 1.5, "bebop_run": 1.5, "enclosure_line": 1.2},
    "pentatonic": {"pentatonic_cell": 4.0},
    "rhythm": {"rhythmic_motif": 3.0, "pentatonic_cell": 1.2},
    "motif": {"sequence": 2.5, "call_response": 2.0, "rhythmic_motif": 1.3, "chord_tone_cell": 1.3},
    "bebop": {"bebop_run": 3.0, "enclosure_line": 2.0, "guide_tone_line": 1.4},
    "lyrical": {"lyrical_arch": 3.0, "scalar_fragment": 1.5},
}
_FUNCTIONAL = {
    "ii_V", "V_I", "ii_V_I", "ii_V_chain", "ii_subV", "ii_subV_I", "subV_I",
    "secondary_dominant", "dominant_chain", "dominant_resolution", "cadence",
}
_RELATION_FACTORS: dict[str, dict[str, float]] = {
    "functional": {"guide_tone_line": 1.5, "enclosure_line": 1.3, "arpeggio_scale": 1.2, "bebop_run": 1.2,
                   "chord_tone_cell": 1.2, "scalar_fragment": 1.1},
    "diatonic": {"lyrical_arch": 1.4, "pentatonic_cell": 1.4, "rhythmic_motif": 1.2, "bebop_run": 0.5,
                 "enclosure_line": 0.6},
    "vamp": {"rhythmic_motif": 1.5, "pentatonic_cell": 1.3, "sequence": 1.3},
}
_CELLS: dict[str, tuple[tuple[int, ...], ...]] = {
    "Beginner": ((1, 1), (-1, -1), (1, -1), (-1, 1), (2, -1), (-2, 1)),
    "Intermediate": ((1, 1, -1), (-1, -1, 1), (2, -1, -1), (-2, 1, 1), (1, -2, 1), (1, 1, 1), (-1, -1, -1)),
    "Advanced": ((2, -1, -1, 2), (-1, -1, 3, -1), (1, 2, -1, -1), (-2, -1, 2, 2), (3, -1, -1, -1)),
    "wide": ((3, -1, 3, -2), (-3, 1, -2, 3), (2, 2, -3, 1), (-2, -2, 3, -1)),
    # Chord-space cells move one chord tone at a time (a skip of two would be a 5th/6th).
    "arpeggio": ((1, 1), (-1, -1), (1, 1, -1), (-1, -1, 1), (1, 1, 1, -1), (-1, -1, -1, 1)),
}
# Build (developed exercise): notes per bar of every chord; Seed: notes on each non-final chord.
_NOTES_PER_BAR: dict[str, dict[str, int]] = {
    "Beginner": {"easier": 3, "normal": 4, "harder": 4},
    "Intermediate": {"easier": 4, "normal": 5, "harder": 6},
    "Advanced": {"easier": 5, "normal": 6, "harder": 7},
}
_SEED_NOTES: dict[str, int] = {"Beginner": 3, "Intermediate": 4, "Advanced": 5}
_STABLE_ROLES = ("R", "3", "5")
# Families whose line can carry an outside side-slip (the contour is a run, not a figure).
_LINEAR_FAMILIES = {"bebop_run", "enclosure_line", "scalar_fragment", "sequence", "intervallic_cell", "arpeggio_scale"}


@dataclass(frozen=True)
class ChordSlot:
    """One harmony in the span: when it starts/ends (quarter notes) and which bars it owns."""

    index: int
    chord: str
    bars: int
    first_bar: int
    start: Fraction
    end: Fraction

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start"], d["end"] = str(self.start), str(self.end)
        return d


def _level(level: str) -> str:
    low = str(level or "").strip().lower()
    if low.startswith("beg"):
        return "Beginner"
    if low.startswith("adv"):
        return "Advanced"
    return "Intermediate"


def _tier(variant: str) -> str:
    v = str(variant or "normal").strip().lower()
    return v if v in ("easier", "harder") else "normal"


def chord_timeline(span: Any, *, meter: str = "4/4", passes: int = 1) -> list[ChordSlot]:
    """Explicit harmony timeline, repeated ``passes`` times (bar counts from the chart)."""
    from melodic_rhythm_engine import parse_meter

    bar_len = parse_meter(meter).bar
    slots: list[ChordSlot] = []
    bar = 0
    for _ in range(max(1, int(passes))):
        for ev in span.raw_events:
            bars = max(1, int(ev.bars))
            slots.append(ChordSlot(len(slots), ev.chord, bars, bar, bar * bar_len, (bar + bars) * bar_len))
            bar += bars
    return slots


def _ctx(key: str, chord: str):
    from melodic_pattern_engine import build_context

    return build_context(key, chord)


def _in_register(pc: int) -> list[int]:
    lo, hi = REGISTER
    return [m for m in range(lo, hi + 1) if m % 12 == pc % 12]


def _step(midi: int, steps: int, pcs: Sequence[int]) -> int:
    from melodic_pattern_engine import _step as walk

    return walk(midi, steps, tuple(pcs))


def _bounded_walk(midi: int, delta: int, pcs: Sequence[int]) -> int:
    """Walk ``delta`` collection steps, turning back instead of leaving the register."""
    nxt = _step(midi, delta, pcs)
    if REGISTER[0] <= nxt <= REGISTER[1]:
        return nxt
    return _step(midi, -delta, pcs)


def _role(ctx: Any, pc: int) -> str:
    return ctx.role_of(pc % 12) if pc % 12 in ctx.chord_pcs else ""


# --------------------------------------------------------------------------- pitch spaces


def _pentatonic(ctx: Any) -> tuple[int, ...]:
    """The chord's pentatonic, kept inside its chord-scale (no outside notes)."""
    root = ctx.chord_pcs[0]
    if ctx.quality in ("minor", "m7"):
        steps = (0, 3, 5, 7, 10)
    elif ctx.quality == "half-dim":
        steps = (0, 3, 5, 6, 10)
    else:
        steps = (0, 2, 4, 7, 9)
    pcs = tuple(p for p in ((root + s) % 12 for s in steps) if p in ctx.scale_pcs)
    return pcs if len(pcs) >= 4 else tuple(ctx.scale_pcs)


def _bebop(ctx: Any) -> tuple[int, ...]:
    """Bebop scale: chord-scale plus the chromatic passing tone that keeps chord tones on beats."""
    root = ctx.chord_pcs[0]
    extra = {"dom": (root + 11) % 12, "maj7": (root + 8) % 12, "major": (root + 8) % 12, "m7": (root + 4) % 12}.get(ctx.quality)
    pcs = list(ctx.scale_pcs)
    if extra is not None and extra not in pcs:
        pcs.append(extra)
    return tuple(sorted(set(pcs)))


def _space(ctx: Any, name: str) -> tuple[int, ...]:
    if name == "chord":
        return tuple(ctx.chord_pcs)
    if name == "pentatonic":
        return _pentatonic(ctx)
    if name == "bebop":
        return _bebop(ctx)
    return tuple(ctx.scale_pcs)


_MELODIC_MINOR = (0, 2, 3, 5, 7, 9, 11)


def dominant_color(
    ctx: Any, next_ctx: Any | None, *, rng: random.Random, tier: str, chord_symbol: str = ""
) -> tuple[str, tuple[int, ...]] | None:
    """Advanced dominant colour chosen from the harmony, never at random.

    V7 → I (down a fifth): altered, half-whole diminished, or whole-tone (whole-tone only
    for an augmented / #5 / 9th sonority, or the harder tier). subV7 → I (down a half
    step): lydian dominant. A dominant that does not resolve gets no outside colour.
    """
    if ctx.quality not in ("dom", "aug") or next_ctx is None:
        return None
    root = ctx.chord_pcs[0]
    motion = (next_ctx.chord_pcs[0] - root) % 12
    if motion == 11:
        return "lydian_dominant", tuple(((root + 7) % 12 + s) % 12 for s in _MELODIC_MINOR)
    if motion != 5:
        return None
    sym = str(chord_symbol or ctx.chord)
    options = [("altered", 0.45), ("diminished", 0.35)]
    if ctx.quality == "aug" or any(t in sym for t in ("+", "#5", "aug", "9")) or tier == "harder":
        options.append(("whole_tone", 0.25))
    pick = rng.choices([o[0] for o in options], weights=[o[1] for o in options])[0]
    if pick == "altered":
        return "altered", tuple(((root + 1) % 12 + s) % 12 for s in _MELODIC_MINOR)
    if pick == "diminished":
        return "diminished", tuple((root + s) % 12 for s in (0, 1, 3, 4, 6, 7, 9, 10))
    return "whole_tone", tuple((root + s) % 12 for s in (0, 2, 4, 6, 8, 10))


# --------------------------------------------------------------------------- targets


def _target_role_cost(role: str, level: str, roles_pref: str) -> float:
    if roles_pref == "guide":
        return {"3": 0.0, "7": 0.05, "R": 1.2, "5": 1.4}.get(role, 1.6)
    if roles_pref == "chord":
        return {"R": 0.2, "3": 0.0, "5": 0.3, "7": 0.7}.get(role, 1.4)
    if level == "Beginner":
        return {"R": 0.4, "3": 0.0, "5": 0.6, "7": 0.9}.get(role, 1.2)
    return {"3": 0.0, "7": 0.1, "R": 0.9, "5": 1.1}.get(role, 1.4)


def _motion_cost(a: int, b: int) -> float:
    d = abs(a - b)
    if d == 0:
        return 0.3  # a held common tone: smooth, but the change is less audible
    if d <= 2:
        return 0.0
    if d <= 4:
        return 0.8
    if d <= 7:
        return 2.0
    return 4.0 + (d - 7)


def voice_leading_cost(prev: int, prev_role: str, cur: int, cur_role: str, cur_ctx: Any) -> float:
    """Cost of moving the line from ``prev`` (over the previous chord) to ``cur``."""
    cost = _motion_cost(prev, cur)
    d = abs(prev - cur)
    if prev_role == "7" and cur_role == "3" and 1 <= d <= 2:
        cost -= 1.2  # guide-tone resolution: 7th falls to the next 3rd
    elif prev_role == "3" and cur_role == "7" and d <= 2:
        cost -= 0.8  # 3rd held / stepped into the next 7th
    if cur_role == "R" and (cur - prev) == 1:
        cost -= 0.6  # leading tone up to the new root
    return cost


def choose_targets(
    contexts: Sequence[Any],
    *,
    level: str,
    strategy: str = "",
    rng: random.Random,
    start_near: int = CENTER,
    start_weight: float = 0.06,
    roles_pref: str = "",
    fixed_role: str = "",
    resolve_to_stable: bool = True,
) -> list[tuple[int, str]]:
    """Minimum-cost landing note per chord (dynamic programming over chord tones).

    ``roles_pref``: "guide" (3rds/7ths), "chord" (plain chord tones) or level default.
    ``fixed_role``: every chord starts on the same degree (a sequence of the idea).
    """
    layers: list[list[tuple[int, str, float]]] = []
    for li, ctx in enumerate(contexts):
        cands = []
        arrival = li == len(contexts) - 1 and resolve_to_stable
        for pc in ctx.chord_pcs:
            role = _role(ctx, pc)
            jitter = rng.uniform(0.0, 0.9 if level == "Beginner" else 0.5)
            settle = 0.9 if arrival and role not in ("R", "3") else 0.0
            fixed = 0.0 if not fixed_role or role == fixed_role or arrival else 2.5
            for m in _in_register(pc):
                cands.append(
                    (m, role, _target_role_cost(role, level, roles_pref) + settle + fixed + jitter + 0.03 * abs(m - CENTER))
                )
        layers.append(cands)
    best: list[dict[int, tuple[float, int | None]]] = []
    best.append({i: (c[2] + start_weight * abs(c[0] - start_near), None) for i, c in enumerate(layers[0])})
    for li in range(1, len(layers)):
        cur: dict[int, tuple[float, int | None]] = {}
        for i, (m, role, base) in enumerate(layers[li]):
            choice = None
            for j, (pm, prole, _b) in enumerate(layers[li - 1]):
                total = best[li - 1][j][0] + voice_leading_cost(pm, prole, m, role, contexts[li]) + base
                if choice is None or total < choice[0]:
                    choice = (total, j)
            cur[i] = choice
        best.append(cur)
    idx = min(best[-1], key=lambda i: (best[-1][i][0], i))
    path = []
    for li in range(len(layers) - 1, -1, -1):
        m, role, _b = layers[li][idx]
        path.append((m, role))
        idx = best[li][idx][1] if best[li][idx][1] is not None else idx
    return list(reversed(path))


# --------------------------------------------------------------------------- notes


def _spell(ctx: Any, pc: int, *, below_target: bool | None = None) -> str:
    from music_theory import spell_pitch_class

    name = ctx.name_for_pc(pc)
    if name:
        return name
    if below_target is True:
        return spell_pitch_class(pc, mode="sharp")
    return spell_pitch_class(pc, mode="flat")


@dataclass
class _Note:
    midi: int
    name: str
    role: str  # rhythm-engine role: target / guide_tone / chord_tone / scale / approach / neighbor / passing
    chord_index: int
    kind: str  # target / cell / connector / tension / ending
    locked: bool = False  # a restated vamp note: a copy, never edited on its own


def _note(ctx: Any, midi: int, chord_index: int, kind: str, *, below_target: bool | None = None) -> _Note:
    pc = midi % 12
    if kind in ("target", "ending"):
        role = "target"
    elif pc in ctx.guide_pcs:
        role = "guide_tone"
    elif pc in ctx.chord_pcs:
        role = "chord_tone"
    elif pc in ctx.scale_pcs:
        role = "scale"
    elif kind == "tension":
        role = "passing"
    else:
        role = "approach"
    return _Note(midi, _spell(ctx, pc, below_target=below_target), role, chord_index, kind)


def _realize_body(
    shape: str,
    cell: tuple[int, ...],
    *,
    start: int,
    toward: int | None,
    count: int,
    ctx: Any,
    space: Sequence[int],
    level: str,
    color: tuple[str, tuple[int, ...]] | None,
) -> list[tuple[int, str]]:
    """The body of one chord's segment (after its target): (midi, kind) per note."""
    out: list[tuple[int, str]] = []
    cur = start
    limit = _MAX_LEAP[level]
    pcs = tuple(color[1]) if color else tuple(space)

    def push(m: int, kind: str = "cell") -> None:
        nonlocal cur
        if out and m == out[-1][0] or (not out and m == start):
            m = _bounded_walk(m, 1, pcs)
        if abs(m - cur) > limit:
            m = _bounded_walk(cur, -1 if m > cur else 1, pcs)
        kind = "tension" if color and m % 12 not in ctx.chord_pcs and m % 12 not in ctx.scale_pcs else kind
        out.append((m, kind))
        cur = m

    direction = 1 if toward is None or toward >= start else -1
    if shape == "run":
        for _ in range(count):
            if toward is not None and abs(cur - toward) <= 2 and len(out) < count - 1:
                direction = -direction  # do not land early: turn and re-approach
            push(_bounded_walk(cur, direction, pcs))
    elif shape == "arch":
        up = max(1, (count + 1) // 2)
        for i in range(count):
            push(_bounded_walk(cur, 1 if i < up else -1, pcs))
    elif shape == "arp_run":
        arp = max(1, count // 2)
        for i in range(count):
            if i < arp:
                push(_bounded_walk(cur, 1, ctx.chord_pcs if not color else pcs))
            else:
                d = 1 if toward is not None and toward > cur else -1
                push(_bounded_walk(cur, d, pcs))
    elif shape == "anchor":
        # The target is an anchor ringed by its upper and lower neighbours (A-up-A-down),
        # then the line drifts toward the chord tone nearest the next target.
        up, down = _bounded_walk(start, 1, pcs), _bounded_walk(start, -1, pcs)
        ring = [up, start, down, start]
        for i in range(count):
            push(ring[i % len(ring)] if i < count - 1 or toward is None else _bounded_walk(cur, 1 if toward > cur else -1, pcs))
    elif shape == "rhythmic":
        # A repeated two-note figure that climbs (or falls) toward the next chord: the next
        # chord tone, then the scale step back from it (1-3-2-4-3-5) — the rhythm carries
        # the motif while the pitch drifts.
        anchor = start
        for i in range(count):
            if i % 2 == 0:
                anchor = _bounded_walk(anchor, direction, ctx.chord_pcs)
                push(anchor)
            else:
                push(_bounded_walk(anchor, -direction, pcs))
    elif shape == "bebop":
        rise = min(2, max(1, count // 3))
        for i in range(count):
            if i < rise:
                push(_bounded_walk(cur, 1, ctx.chord_pcs))
            else:
                push(_bounded_walk(cur, -1 if (toward is None or toward <= cur) else 1, pcs))
    else:  # "cell"
        k = 0
        while len(out) < count:
            push(_bounded_walk(cur, cell[k % len(cell)], pcs))
            k += 1
    return out[:count]


def _connectors(
    prev: int,
    target: int,
    ctx: Any,
    *,
    level: str,
    tier: str,
    room: int,
    rng: random.Random,
    color: tuple[str, tuple[int, ...]] | None,
    style: dict[str, float],
    family: str,
) -> list[tuple[int, str, bool | None]]:
    """Notes (midi, kind, spelled-below) leading from the current chord into ``target``."""
    if room <= 0:
        return []
    scale = ctx.scale_pcs
    if level == "Beginner":
        # A diatonic neighbour of the target (chord tone or scale step), nearest the line.
        near = {m for pc in ctx.chord_pcs for m in _in_register(pc) if 1 <= abs(m - target) <= 2}
        near |= {m for m in (_step(target, 1, scale), _step(target, -1, scale)) if m != target}
        options = [m for m in near if m != prev] or sorted(near)
        return [(min(options, key=lambda m: (abs(m - prev), m % 12 not in ctx.chord_pcs, m)), "connector", None)]
    from_above = prev > target
    if level == "Advanced" and color is not None:
        res = [m for pc in color[1] for m in _in_register(pc) if 1 <= abs(m - target) <= 2 and m % 12 not in ctx.chord_pcs]
        if res:
            pick = min(res, key=lambda m: (abs(m - target), abs(m - prev), m))
            # Outside colour resolves by step; only a half step below reads sharp.
            return [(pick, "tension", True if target - pick == 1 else None)]
    chromatic = style.get("chromatic", 0.5)
    wants_enclosure = FAMILIES.get(family, {}).get("connector") == "enclosure"
    if room >= 2 and (wants_enclosure or (level == "Advanced" and rng.random() < 0.15 + 0.6 * chromatic)):
        if level == "Advanced" and rng.random() < 0.4:
            sign = 1 if from_above else -1
            return [(target + 2 * sign, "connector", sign < 0), (target + sign, "connector", sign < 0)]
        upper, lower = _step(target, 1, scale), target - 1
        pair = [(upper, "connector", None), (lower, "connector", True)]  # enclosure
        if not from_above:
            pair.reverse()  # the line arrives from below: lower neighbour first
        if abs(pair[0][0] - prev) <= _MAX_LEAP[level]:
            return pair
    p_chromatic = (0.85 if level == "Advanced" else 0.6) * chromatic + (0.3 if family in ("guide_tone_line", "enclosure_line") else 0.0)
    if tier == "easier" or rng.random() >= p_chromatic:
        step = _step(target, 1 if from_above else -1, scale)
        if step == prev:
            step = _step(target, -1 if from_above else 1, scale)
        return [(step, "connector", None)]
    sign = 1 if from_above else -1
    return [(target + sign, "connector", sign < 0)]  # chromatic approach


def _repair_leaps(notes: list[_Note], contexts: Sequence[Any], limit: int) -> None:
    """Move a cell/ending note by an octave when it leaps further than ``limit``."""
    for _ in range(3):
        changed = False
        for i, n in enumerate(notes):
            if n.kind not in ("cell", "ending") or n.locked:
                continue
            prev = notes[i - 1].midi if i > 0 else None
            nxt = notes[i + 1].midi if i + 1 < len(notes) else None

            def worst(m: int) -> int:
                gaps = [abs(m - x) for x in (prev, nxt) if x is not None]
                return max(gaps) if gaps else 0

            if worst(n.midi) <= limit:
                continue
            options = [m for m in (n.midi - 12, n.midi + 12) if REGISTER[0] <= m <= REGISTER[1]]
            best = min(options, key=lambda m: (worst(m), m), default=None)
            if best is not None and worst(best) < worst(n.midi) and best != prev and best != nxt:
                notes[i] = _note(contexts[n.chord_index], best, n.chord_index, n.kind)
                changed = True
        if not changed:
            return


def _break_alternation(
    notes: list[_Note], contexts: Sequence[Any], spaces: Sequence[Sequence[int]], limit: int, *, diatonic: bool = False
) -> None:
    """Undo mechanical A-B-A-B: move the free (cell) note of the pattern to another neighbour."""
    for i in range(3, len(notes)):
        a, b, c, d = (notes[j].midi for j in range(i - 3, i + 1))
        if not (a == c and b == d and a != b):
            continue
        for j in (i - 2, i - 1, i - 3, i):
            n = notes[j]
            if n.locked:
                continue
            prev = notes[j - 1].midi if j > 0 else None
            nxt = notes[j + 1].midi if j + 1 < len(notes) else None
            ctx = contexts[n.chord_index]
            if n.kind == "cell":
                space = spaces[n.chord_index]
                ref0 = prev if prev is not None else n.midi
                moves = {_bounded_walk(ref0, dlt, space) for dlt in (-2, -1, 1, 2)}
            elif n.kind == "connector" and nxt is not None and notes[j + 1].kind == "target":
                # Approach the target from its other side (diatonically at Beginner).
                moves = {2 * nxt - n.midi, _step(nxt, -1 if n.midi > nxt else 1, ctx.scale_pcs)}
                if diatonic:
                    moves = {m for m in moves if m % 12 in ctx.scale_pcs}
            else:
                continue
            # A connector may meet a free cell before it: the repeat pass then moves that cell.
            prev_free = n.kind == "connector" and j > 0 and notes[j - 1].kind == "cell" and not notes[j - 1].locked
            options = [
                m for m in moves
                if m not in (nxt, n.midi) and (m != prev or prev_free) and REGISTER[0] <= m <= REGISTER[1]
                and all(abs(m - x) <= limit for x in (prev, nxt) if x is not None)
            ]
            options = [m for m in options if not _alternates_at([x.midi for x in notes], j, m)]
            if options:
                ref = prev if prev is not None else n.midi
                pick = min(options, key=lambda m: (abs(m - ref), m))
                below = True if n.kind == "connector" and nxt is not None and nxt - pick == 1 else None
                notes[j] = _note(ctx, pick, n.chord_index, n.kind, below_target=below)
                break


def _fix_adjacent_repeats(notes: list[_Note], contexts: Sequence[Any], spaces: Sequence[Sequence[int]], limit: int) -> None:
    """No pitch is struck twice in a row: move the free (cell) note of a repeated pair."""
    for i in range(len(notes) - 1):
        if notes[i].midi != notes[i + 1].midi:
            continue
        for j in (i, i + 1):
            n = notes[j]
            prev = notes[j - 1].midi if j > 0 else None
            nxt = notes[j + 1].midi if j + 1 < len(notes) else None
            if n.locked:
                continue
            if n.kind == "cell":
                moves = [_bounded_walk(n.midi, d, spaces[n.chord_index]) for d in (-1, 1, -2, 2)]
            elif n.kind == "connector" and nxt is not None and notes[j + 1].kind == "target":
                moves = [2 * nxt - n.midi]  # approach the target from its other side
            else:
                continue
            options = [
                m for m in moves
                if m not in (prev, nxt) and REGISTER[0] <= m <= REGISTER[1]
                and all(abs(m - x) <= limit for x in (prev, nxt) if x is not None)
                and not _alternates_at([x.midi for x in notes], j, m)
            ]
            if options:
                ctx = contexts[n.chord_index]
                below = True if n.kind == "connector" and nxt - options[0] == 1 else None
                notes[j] = _note(ctx, options[0], n.chord_index, n.kind, below_target=below)
                break


def _alternates_at(midis: list[int], j: int, value: int) -> bool:
    """Would ``midis[j] = value`` sit inside an A-B-A-B window?"""
    seq = list(midis)
    seq[j] = value
    for start in range(max(0, j - 3), min(j, len(seq) - 4) + 1):
        a, b, c, d = seq[start:start + 4]
        if a == c and b == d and a != b:
            return True
    return False


def _avoid_repeats(seg: list[_Note], before: int | None, ctx: Any, space: Sequence[int], chord_index: int) -> None:
    """A cell note never restates its neighbour; targets and connectors are fixed."""
    for i, n in enumerate(seg):
        if n.kind not in ("cell", "tension"):
            continue
        prev = seg[i - 1].midi if i > 0 else before
        nxt = seg[i + 1].midi if i + 1 < len(seg) else None
        if n.midi != prev and n.midi != nxt:
            continue
        options = [m for m in (_bounded_walk(n.midi, d, space) for d in (-1, 1)) if m not in (prev, nxt)]
        if options:
            ref = prev if prev is not None else n.midi
            seg[i] = _note(ctx, min(options, key=lambda m: (abs(m - ref), m)), chord_index, n.kind)


# --------------------------------------------------------------------------- musicality


def musicality(midis: Sequence[int], chord_index: Sequence[int], contexts: Sequence[Any], *, level: str) -> dict[str, float]:
    """Score how coherent a melodic sentence is (higher is better) with a breakdown."""
    n = len(midis)
    gaps = [b - a for a, b in zip(midis, midis[1:])]
    sizes = [abs(g) for g in gaps]
    leaps = -sum(max(0, d - 5) * 0.6 for d in sizes) - 3.0 * sum(1 for d in sizes if d > _MAX_LEAP[level])
    repeats = -1.2 * sum(1 for d in sizes if d == 0)
    alternation = -1.0 * sum(
        1 for i in range(2, n - 1) if midis[i] == midis[i - 2] and midis[i + 1] == midis[i - 1] and midis[i] != midis[i - 1]
    )
    dirs = [1 if g > 0 else -1 for g in gaps if g]
    flips = sum(1 for a, b in zip(dirs, dirs[1:]) if a != b)
    ratio = flips / max(1, len(dirs) - 1)
    zigzag = -3.0 * (ratio - 0.75) * n / 4 if (ratio > 0.75 and n > 5) else 0.0
    span = (max(midis) - min(midis)) if midis else 0
    range_score = -0.5 * (span - 16) if span > 16 else (-2.0 if span < 4 and n >= 6 else 0.0)
    peak = max(range(n), key=lambda i: midis[i]) if midis else 0
    arc = 1.0 if 0 < peak < n - 1 else 0.0
    roots = sum(1 for m, c in zip(midis, chord_index) if m % 12 == contexts[c].chord_pcs[0])
    root_abuse = -2.0 * (roots / n - 0.4) * n if n and roots / n > 0.4 else 0.0
    steps = 2.0 * (sum(1 for d in sizes if 1 <= d <= 2) / max(1, len(sizes)))
    parts = {
        "leaps": round(leaps, 3), "repeats": round(repeats, 3), "alternation": round(alternation, 3),
        "zigzag": round(zigzag, 3), "range": round(range_score, 3), "arc": arc,
        "root_abuse": round(root_abuse, 3), "steps": round(steps, 3),
    }
    parts["total"] = round(sum(parts.values()), 3)
    return parts


# --------------------------------------------------------------------------- strategy choice


def _relation_kind(span: Any) -> str:
    if span.repeated_vamp:
        return "vamp"
    if span.relationship in _FUNCTIONAL:
        return "functional"
    if span.relationship == "diatonic":
        return "diatonic"
    return ""


def family_weights(span: Any, *, level: str, focus: str, style: str) -> dict[str, float]:
    """Weighted strategy families available for this span / Level / Practice Focus / style."""
    lvl = _level(level)
    pref = focus_preference(focus)
    weights = dict(_BASE_WEIGHTS[lvl])
    for fam in list(weights):
        if lvl not in FAMILIES[fam]["levels"]:
            weights.pop(fam)
    for factors in (_STYLE_FACTORS.get(style, {}), _FOCUS_FACTORS.get(pref, {}), _RELATION_FACTORS.get(_relation_kind(span), {})):
        for fam, f in factors.items():
            if fam in weights:
                weights[fam] *= f
    return weights


def _choose_family(span: Any, *, level: str, focus: str, style: str, rng: random.Random) -> str:
    weights = family_weights(span, level=level, focus=focus, style=style)
    names = sorted(weights)
    return rng.choices(names, weights=[weights[n] for n in names])[0]


def _development(family: str, span: Any) -> str:
    if span.repeated_vamp:
        return "vamp_restatement"
    if family == "sequence":
        return "sequence"
    if family == "call_response":
        return "call_response"
    return "cell_carry"


def _bar_counts(
    slots: Sequence[ChordSlot], *, level: str, tier: str, length: str, final_index: int, density: int
) -> list[list[int]]:
    """Notes per bar for each slot. Seed: one cell per chord; Build: full density."""
    from melodic_rhythm_engine import max_notes_per_bar

    cap = max_notes_per_bar("4/4", level)
    per_bar = max(2, _NOTES_PER_BAR[level][tier] + density)
    seed_notes = max(2, _SEED_NOTES[level] + min(0, density))
    out = []
    for s in slots:
        last = s.index == final_index
        if length == "seed":
            counts = [2 if last else seed_notes] + [1] * (s.bars - 1)
        else:
            counts = [per_bar] * s.bars
            if last:
                counts[-1] = 3 if level == "Advanced" and density >= 0 else 2
                if s.bars > 1:
                    counts[-1] = 1  # settle on a long final note
        out.append([max(1, min(c, cap)) for c in counts])
    return out


def _stable_seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


# --------------------------------------------------------------------------- generation


def generate_span_motif(
    span: Any,
    *,
    level: str,
    variant: str = "normal",
    instrument: str = "",
    meter: str = "4/4",
    vocabulary: str = "auto",
    seed: int | None = None,
    length: str = "seed",
    plan: dict[str, Any] | None = None,
    focus: str = "",
    style: str = "default",
    candidates: int = 5,
) -> dict[str, Any]:
    """One connected motif across ``span``.

    ``length``: ``seed`` (a short connected idea), ``standard`` (the developed exercise)
    or ``extended`` (the span played twice, the second pass answering the first).
    ``plan``: a previous result's ``span_seed`` — Build develops *that* idea.
    ``focus``: the Practice Focus label; ``style``: :func:`song_style` bucket.
    ``vocabulary``: ``auto`` or a forced family (``chord_tones`` / ``guide_tones`` / a family id).
    """
    if length not in LENGTHS:
        raise ValueError(f"unknown span length: {length}")
    lvl = _level(level)
    tier = _tier(variant)
    style = style if style in STYLE_PROFILES else "default"
    if plan:
        seed_value = int(plan["seed"])
        family = str(plan.get("family") or "chord_tone_cell")
        focus = str(plan.get("focus", focus))
        style = str(plan.get("style", style)) if plan.get("style") in STYLE_PROFILES else style
    else:
        seed_value = int(seed) if seed is not None else _stable_seed(span.span_id, lvl, tier, focus, style)
        forced = {"chord_tones": "chord_tone_cell", "guide_tones": "guide_tone_line"}.get(str(vocabulary), str(vocabulary))
        if forced in FAMILIES and lvl in FAMILIES[forced]["levels"]:
            family = forced
        else:
            family = _choose_family(span, level=lvl, focus=focus, style=style, rng=random.Random(seed_value))
    # Pitch candidates are cheap; musicality picks the most coherent line before the
    # (expensive) rhythm search runs once for the winner.
    # The seed picks among the near-best so New Idea keeps varying instead of converging;
    # Build regenerates exactly the seed's winning candidate (same cell, register, targets).
    attempts = [int(plan["attempt"])] if plan and "attempt" in plan else range(max(1, int(candidates)))
    drafts = [
        _generate_once(
            span, level=lvl, tier=tier, meter=meter, seed=seed_value, attempt=k, length=length,
            family=family, focus=focus, style=style, instrument=instrument,
        )
        for k in attempts
    ]
    top = max(d["meta"]["musicality"]["total"] for d in drafts)
    near = [d for d in drafts if d["meta"]["musicality"]["total"] >= top - 1.0]
    best = near[random.Random(seed_value ^ 0x5F3759DF).randrange(len(near))]
    motif = _assemble_motif(
        span, best["notes"], best["slots"], best["bar_counts"], best["downbeats"], [n.role for n in best["notes"]],
        meter=meter, level=lvl, seed=best["rhythm_seed"], style=style, focus=focus,
    )
    motif.update(best["meta"])
    return motif


def _generate_once(
    span: Any,
    *,
    level: str,
    tier: str,
    meter: str,
    seed: int,
    attempt: int,
    length: str,
    family: str,
    focus: str,
    style: str,
    instrument: str,
) -> dict[str, Any]:
    lvl = level
    profile = FAMILIES[family]
    sty = STYLE_PROFILES[style]
    rng0 = random.Random(seed * 31 + attempt)
    rng = random.Random(seed + 7919 + attempt * 104729)
    if profile.get("cells") == "wide":
        cell_pool = _CELLS["wide"]
    elif profile["space"] == "chord":
        cell_pool = _CELLS["arpeggio"]
    else:
        cell_pool = _CELLS[lvl]
    cell = cell_pool[rng0.randrange(len(cell_pool))]
    development = _development(family, span)
    passes = 2 if length == "extended" else 1
    slots = chord_timeline(span, meter=meter, passes=passes)
    contexts = [_ctx(span.key_center, s.chord) for s in slots]
    one_pass = len(span.raw_events)
    pref = focus_preference(focus)
    roles_pref = "guide" if (profile.get("roles") == "guide" or pref == "guide_tones") else ("chord" if pref == "chord_tones" else "")
    fixed_role = ""
    if profile.get("roles") == "fixed":
        fixed_role = ("3", "R", "5")[rng0.randrange(3)]
    leads_forward = contexts[one_pass - 1].quality == "dom" and span.relationship in ("ii_V", "ii_subV", "dominant_chain", "ii_V_chain")
    # The seed owns the starting register; candidates only explore its neighbours, so
    # different New Ideas search different spaces rather than converging on one line.
    start_near = (60, 64, CENTER, 71, 74)[(seed + (0, 0, 1, 4, 0)[attempt % 5]) % 5]
    targets = choose_targets(
        contexts[:one_pass], level=lvl, rng=rng, start_near=start_near, roles_pref=roles_pref,
        fixed_role=fixed_role, resolve_to_stable=not leads_forward,
    )
    if passes == 2 and development == "vamp_restatement":
        targets = targets + targets

    def _answer_targets(near: int) -> None:
        if len(targets) < len(slots):
            targets.extend(
                choose_targets(
                    contexts[one_pass:], level=lvl, rng=random.Random(seed + 104729 + attempt), start_near=near,
                    start_weight=0.2, roles_pref=roles_pref, fixed_role=fixed_role, resolve_to_stable=not leads_forward,
                )
            )

    density = int(sty["density"]) + int(profile.get("density", 0))
    counts = _bar_counts(slots, level=lvl, tier=tier, length=length, final_index=len(slots) - 1, density=density)

    notes: list[_Note] = []
    vocab: set[str] = {"chord_tone"}
    colors: list[dict[str, Any]] = []
    slot_notes: list[list[_Note]] = []
    slot_start: list[int] = []
    restated_from: list[tuple[int, int]] = []  # (copy index, source index) in ``notes``
    orientations: list[str] = []
    for si, slot in enumerate(slots):
        ctx = contexts[si]
        total = sum(counts[si])
        slot_start.append(len(notes))
        if development == "vamp_restatement" and si >= one_pass and si != len(slots) - 1:
            restated = [_Note(n.midi, n.name, n.role, si, n.kind, locked=True) for n in slot_notes[si - one_pass]]
            src = slot_start[si - one_pass]
            restated_from.extend((len(notes) + k, src + k) for k in range(len(restated)))
            slot_notes.append(restated)
            orientations.append(orientations[si - one_pass])
            notes.extend(restated)
            continue
        target_midi = targets[si][0]
        seg: list[_Note] = [_note(ctx, target_midi, si, "target")]
        is_last = si == len(slots) - 1
        nxt_target = None if is_last or si + 1 >= len(targets) else targets[si + 1][0]
        nxt_ctx = None if is_last else contexts[si + 1]
        color = None
        # Jazz dominants always take a colour; elsewhere it scales with the style's appetite.
        if lvl == "Advanced" and tier != "easier" and not is_last and (
            style in JAZZ_STYLES or rng.random() < 0.3 + sty["chromatic"]
        ):
            color = dominant_color(ctx, nxt_ctx, rng=rng, tier=tier, chord_symbol=slot.chord)
            if (
                color is None and ctx.quality in ("m7", "half-dim") and style in JAZZ_STYLES and total >= 5
                and family in _LINEAR_FAMILIES and rng.random() < 0.35
            ):
                # Side-slip: the ii idea played a half step up, then back inside by step.
                color = ("side_slip", tuple((p + 1) % 12 for p in ctx.scale_pcs))
        if color:
            colors.append({"chord_index": si, "chord": slot.chord, "color": color[0]})
            vocab.add(color[0])
        space = _space(ctx, profile["space"])
        base_cell = cell
        if (passes == 2 and si >= one_pass and development != "vamp_restatement") or (
            profile.get("answer") and si % 2 == 1
        ):
            base_cell = tuple(-d for d in cell)  # the answer turns the idea over
        if is_last:
            body_len = total - 1
        else:
            # Room for the connector: two notes only where an enclosure is likely.
            two = lvl != "Beginner" and total >= 4 and (
                profile.get("connector") == "enclosure" or (lvl == "Advanced" and total >= 5)
            )
            body_len = max(0, total - 1 - (2 if two else 1 if total >= 2 else 0))

        def realize(shape_cell: tuple[int, ...]) -> list[tuple[int, str]]:
            return _realize_body(
                profile["shape"], shape_cell, start=target_midi, toward=nxt_target, count=body_len,
                ctx=ctx, space=space, level=lvl, color=color,
            )

        body = realize(base_cell)
        pass_cell = base_cell
        orientation = "cell"
        if nxt_target is not None and body and profile["shape"] in ("cell", "rhythmic"):
            mirrored = tuple(-d for d in base_cell)
            alt = realize(mirrored)
            if abs(alt[-1][0] - nxt_target) < abs(body[-1][0] - nxt_target):
                body, pass_cell, orientation = alt, mirrored, "mirror"
        orientations.append(orientation)
        for midi, kind in body:
            seg.append(_note(ctx, midi, si, kind))
        if is_last:
            if len(seg) > 1:
                prev = seg[-2].midi
                # ii→V (unresolved dominant) ends leaning forward on 3/7/5, never the root.
                want = ("3", "7", "5") if leads_forward else _STABLE_ROLES
                stable = [
                    m for pc in ctx.chord_pcs if _role(ctx, pc) in want for m in _in_register(pc)
                    if abs(m - prev) <= _MAX_LEAP[lvl]
                ] or [prev]

                def _settle(m: int) -> tuple:
                    d = abs(m - prev)
                    closeness = 4 if d == 0 else 0 if d <= 2 else 1 if d <= 4 else 3
                    preferred = ("3", "7") if leads_forward else ("R",)
                    return (closeness, _role(ctx, m) not in preferred, d, m)

                seg[-1] = _note(ctx, min(stable, key=_settle), si, "ending")
        else:
            if nxt_target is None:
                _answer_targets(seg[-1].midi)
                nxt_target = targets[si + 1][0]
            room = total - len(seg)
            conn = _connectors(
                seg[-1].midi, nxt_target, ctx, level=lvl, tier=tier, room=room, rng=rng, color=color, style=sty, family=family,
            )
            body_end = seg[-1].midi
            fill: list[_Note] = []
            while len(seg) + len(fill) + len(conn) < total:
                body_end = _bounded_walk(body_end, pass_cell[len(fill) % len(pass_cell)], space)
                fill.append(_note(ctx, body_end, si, "cell"))
            seg.extend(fill)
            for m, kind, below in conn:
                if m == seg[-1].midi and len(conn) == 1 and abs(m - nxt_target) == 1:
                    m = 2 * nxt_target - m
                    below = m < nxt_target
                seg.append(_note(ctx, m, si, kind, below_target=below))
                if kind == "connector" and m % 12 not in ctx.scale_pcs:
                    vocab.add("chromatic_approach")
            if len(conn) == 2:
                vocab.add("enclosure")
        seg = seg[:total]
        _avoid_repeats(seg, notes[-1].midi if notes else None, ctx, space, si)
        if any(n.midi % 12 not in ctx.chord_pcs for n in seg):
            vocab.add("scale" if profile["space"] != "pentatonic" else "pentatonic")
        slot_notes.append(seg)
        notes.extend(seg)

    _repair_leaps(notes, contexts, _MAX_LEAP[lvl])
    spaces = [_space(c, profile["space"]) for c in contexts]
    _break_alternation(notes, contexts, spaces, _MAX_LEAP[lvl], diatonic=lvl == "Beginner")
    _fix_adjacent_repeats(notes, contexts, spaces, _MAX_LEAP[lvl])
    if restated_from:
        for dst, src in restated_from:  # the vamp's second pass restates the (cleaned) first exactly
            n = notes[src]
            notes[dst] = _Note(n.midi, n.name, n.role, notes[dst].chord_index, n.kind, locked=True)
        _break_alternation(notes, contexts, spaces, _MAX_LEAP[lvl], diatonic=lvl == "Beginner")  # seams only: copies are locked
        _fix_adjacent_repeats(notes, contexts, spaces, _MAX_LEAP[lvl])
    flat_counts = [c for slot_counts in counts for c in slot_counts]
    downbeats = [s.first_bar for s in slots]
    meta = {
        "strategy_family": family,
        "development_strategy": development,
        "vocabulary_used": sorted(vocab),
        "advanced_colors": colors,
        "span_length": length,
        "level": lvl,
        "variant": tier,
        "style": style,
        "focus": focus,
        "focus_preference": pref,
        "span_seed": {"seed": seed, "attempt": attempt, "family": family, "cell": list(cell), "strategy": development,
                      "level": lvl, "focus": focus, "style": style},
        "instrument": instrument,
        "cell_orientations": orientations,
        "musicality": musicality([n.midi for n in notes], [n.chord_index for n in notes], contexts, level=lvl),
        "transition_targets": [
            {"chord_index": n.chord_index, "note_index": i, "midi": n.midi, "name": n.name,
             "role": _role(contexts[n.chord_index], n.midi % 12)}
            for i, n in enumerate(notes)
            if n.kind == "target"
        ],
        "note_kinds": [n.kind for n in notes],
    }
    return {"notes": notes, "slots": slots, "bar_counts": flat_counts, "downbeats": downbeats,
            "rhythm_seed": seed + attempt, "meta": meta}


# --------------------------------------------------------------------------- rhythm


def rhythm_profile(realization_or_events: Any, meter: str = "4/4") -> dict[str, float]:
    """Fractions of notes that are off the beat, syncopated, triplets, sixteenths, or long.

    *Syncopated* = an off-beat onset that sustains across the next beat (an anticipation or
    tie), so a plain eighth-note pair is off-beat but not syncopated.
    """
    from melodic_rhythm_engine import events_from_json, parse_meter

    events = getattr(realization_or_events, "events", None)
    if events is None:
        events = events_from_json(realization_or_events)
    beat = parse_meter(meter).beat
    notes = [e for e in events if not e.rest]
    n = max(1, len(notes))

    def crosses_beat(e: Any) -> bool:
        onset = Fraction(e.onset)
        if onset % beat == 0:
            return False
        next_beat = onset - onset % beat + beat
        return onset + Fraction(e.duration) > next_beat

    return {
        "offbeat": round(sum(1 for e in notes if Fraction(e.onset) % beat != 0) / n, 3),
        "syncopation": round(sum(1 for e in notes if crosses_beat(e)) / n, 3),
        "triplets": round(sum(1 for e in notes if e.tuplet) / n, 3),
        "sixteenths": round(sum(1 for e in notes if e.duration < Fraction(1, 2) and not e.tuplet) / n, 3),
        "long": round(sum(1 for e in notes if e.duration >= 2) / n, 3),
    }


def _rhythm_preference(prof: dict[str, float], *, level: str, style: str, focus: str) -> float:
    sty = STYLE_PROFILES.get(style, STYLE_PROFILES["default"])
    pref = focus_preference(focus)
    if level == "Beginner":
        # Quarters and eighths: anticipations, triplets and sixteenths are for later.
        return -3.0 * (prof["syncopation"] + prof["triplets"] + prof["sixteenths"]) + sty["long"] * prof["long"]
    gain = 1.5 if level == "Intermediate" else 2.2
    sync = sty["syncopation"] + (0.6 if pref == "rhythm" else 0.0)
    if style not in JAZZ_STYLES and style != "funk":
        # Pop / ballad / folk: a regular, singable pulse.
        sync -= 0.4 * (1 if level == "Intermediate" else 0.5)
    trip = sty["triplets"] * (0.6 if level == "Intermediate" else 1.0) + (0.3 if pref == "bebop" else 0.0)
    six = sty["sixteenths"] * (0.3 if level == "Intermediate" else 1.0)
    straightness = 0.0 if style in JAZZ_STYLES else 0.5 * (1 - prof["triplets"])
    if sty["long"] >= 1.0:
        six -= 1.0  # ballads breathe: no sixteenth-note flurries
    return gain * (sync * prof["syncopation"] + trip * prof["triplets"] + six * prof["sixteenths"]) + sty["long"] * prof["long"] * 1.5 + straightness


def _ranked_rhythms(bar_counts: Sequence[int], roles: Sequence[str], downbeats: Sequence[int], *, meter: str, level: str, seed: int, style: str, focus: str) -> list[Any]:
    from melodic_rhythm_engine import rhythm_candidates_by_bar

    cands = rhythm_candidates_by_bar(
        bar_counts, meter=meter, level=level, roles=list(roles), downbeat_bars=downbeats, seed=seed, limit=24,
    )
    return sorted(
        cands,
        key=lambda c: (-(c.score + _rhythm_preference(rhythm_profile(c, meter), level=level, style=style, focus=focus)), c.id),
    )


def _assemble_motif(
    span: Any,
    notes: Sequence[_Note],
    slots: Sequence[ChordSlot],
    bar_counts: Sequence[int],
    downbeats: Sequence[int],
    roles: Sequence[str],
    *,
    meter: str,
    level: str,
    seed: int,
    style: str = "default",
    focus: str = "",
) -> dict[str, Any]:
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi

    cands = _ranked_rhythms(bar_counts, roles, downbeats, meter=meter, level=level, seed=seed, style=style, focus=focus)
    if not cands:
        raise ValueError(f"no rhythm fits bar counts {list(bar_counts)} at {level}")
    meta = {
        "meter": meter, "level": level, "group": 0, "seed": int(seed), "roles": list(roles),
        "bar_counts": list(bar_counts), "downbeat_bars": list(downbeats), "style": style, "focus": focus,
    }
    total_bars = sum(s.bars for s in slots)
    bar_symbols: list[str | None] = [None] * total_bars
    for s in slots:
        bar_symbols[s.first_bar] = s.chord
    first_note = []
    idx = 0
    bar_i = 0
    for slot in slots:
        first_note.append(idx)
        for _b in range(slot.bars):
            idx += bar_counts[bar_i]
            bar_i += 1
    timeline = []
    for i, s in enumerate(slots):
        last = (first_note[i + 1] if i + 1 < len(slots) else len(notes)) - 1
        d = s.to_dict()
        d.update({"first_note": first_note[i], "last_note": last})
        timeline.append(d)
    motif: dict[str, Any] = {
        "notes": [n.name for n in notes],
        "midi": [n.midi for n in notes],
        "display": " – ".join(n.name for n in notes),
        "chord": " → ".join(span.chords),
        "span_motif": True,
        "span_id": span.span_id,
        "span_scope": span.scope,
        "span_chords": list(span.chords),
        "span_relationship": span.relationship,
        "key_center": span.key_center,
        "chord_timeline": timeline,
        "note_chord_index": [n.chord_index for n in notes],
        "change_indices": first_note[1:],
        "bar_chord_symbols": bar_symbols,
        "pattern_note_roles": list(roles),
        "is_pattern": False,
        "last_transform": "span_generate",
    }
    motif.update(_engine_rhythm_fields(cands[0], index=0, count=len(cands), meta=meta))
    motif["rhythm_profile"] = rhythm_profile(cands[0], meter)
    return sync_motif_midi(motif)


def note_chord_assignment(motif: dict[str, Any]) -> list[int]:
    """Chord index for each note, derived from rhythm onsets and the timeline (not stored lists)."""
    from melodic_rhythm_engine import events_from_json

    timeline = motif.get("chord_timeline") or []
    out = []
    for e in events_from_json(motif.get("rhythm_events") or []):
        if e.rest:
            continue
        onset = Fraction(e.onset)
        out.append(next(i for i, t in enumerate(timeline) if Fraction(t["start"]) <= onset < Fraction(t["end"])))
    return out


def cycle_span_rhythm(motif: dict[str, Any]) -> dict[str, Any]:
    """Change Rhythm: the next per-bar candidate (same style ordering) — pitches and chords untouched."""
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi

    meta = dict(motif.get("rhythm_meta") or {})
    meter = str(meta.get("meter") or "4/4")
    cands = _ranked_rhythms(
        list(meta.get("bar_counts") or []), list(meta.get("roles") or []), list(meta.get("downbeat_bars") or []),
        meter=meter, level=str(meta.get("level") or "Intermediate"), seed=int(meta.get("seed") or 0),
        style=str(meta.get("style") or "default"), focus=str(meta.get("focus") or ""),
    )
    if not cands:
        return motif
    ids = [c.id for c in cands]
    current = str(meta.get("id") or "")
    index = (ids.index(current) + 1) % len(cands) if current in ids else 0
    out = dict(motif)
    out.update(_engine_rhythm_fields(cands[index], index=index, count=len(cands), meta=meta))
    out["rhythm_profile"] = rhythm_profile(cands[index], meter)
    out["last_transform"] = "change_rhythm"
    return sync_motif_midi(out)


def project_span_motif(
    motif: dict[str, Any],
    *,
    semitones: int,
    chart_key: str,
    project_chord: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Concert span motif → written/shape chart (MIDI shifted, notes respelled, symbols projected)."""
    if not semitones and project_chord is None:
        return motif
    from improvisation_motif import _note_from_midi, sync_motif_midi

    out = dict(motif)
    if semitones:
        midis = [int(m) + int(semitones) for m in motif.get("midi") or []]
        out["midi"] = midis
        out["notes"] = [_note_from_midi(m, chart_key) for m in midis]
        out["display"] = " – ".join(out["notes"])
    if project_chord is not None:
        out["bar_chord_symbols"] = [project_chord(s) if s else None for s in motif.get("bar_chord_symbols") or []]
        out["chord"] = " → ".join(project_chord(c) for c in motif.get("span_chords") or [])
    out["projected_chart_key"] = chart_key
    return sync_motif_midi(out)


def build_span_exercise(span: Any, seed_motif: dict[str, Any], *, length: str = "standard", **kw: Any) -> dict[str, Any]:
    """Build Motif Pattern for a span: develop the seed's idea through the whole span."""
    if length not in ("standard", "extended"):
        raise ValueError(f"build length must be standard or extended, not {length}")
    plan = dict(seed_motif.get("span_seed") or {})
    return generate_span_motif(
        span, level=plan.get("level") or seed_motif.get("level") or "Intermediate",
        variant=seed_motif.get("variant") or "normal", length=length, plan=plan, **kw,
    )


__all__ = [
    "ChordSlot",
    "FAMILIES",
    "LENGTHS",
    "STYLE_PROFILES",
    "build_span_exercise",
    "choose_targets",
    "chord_timeline",
    "cycle_span_rhythm",
    "dominant_color",
    "family_weights",
    "focus_preference",
    "generate_span_motif",
    "musicality",
    "note_chord_assignment",
    "project_span_motif",
    "rhythm_profile",
    "song_style",
    "voice_leading_cost",
]

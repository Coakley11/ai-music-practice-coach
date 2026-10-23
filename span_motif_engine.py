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
6. **Rhythm** (MC2.2) — planned *before* the pitches by :mod:`span_rhythm_grammar`: one
   rhythmic cell, stated, repeated or varied, then a cadence made from its opening. The
   plan fixes the notes per bar; each target lands on its chord's downbeat; a held note
   before a change is never a chromatic approach.
7. **Build** (MC2.2) — develops the *actual* seed: every seed note is kept in order and
   new notes (passing / neighbour / chord tone / enclosure / chromatic passing) fill
   values split from the seed's own rhythm, the same split in every bar carrying the
   same cell. :func:`motif_identity` measures how audibly the seed survives.

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


@dataclass(frozen=True)
class SpanConstraints:
    """Optional knobs a caller (e.g. a Mission) imposes on one span line.

    Defaults reproduce unconstrained MC2.2 generation exactly.

    - ``target_roles``: landing roles allowed on each chord ("R", "3", "5", "7").
    - ``pitch_space``: "chord" | "pentatonic" | "scale" | "common" (with ``common_pcs``).
    - ``connector``: "step" (diatonic) | "chord" | "chromatic" | "enclosure" | "double".
    - ``color``: "require" | "forbid" an Advanced dominant colour (still harmony-chosen).
    - ``smooth_targets``: weight voice leading harder (common tones, nearest motion).
    - ``tail_short``: rhythm cells end with two short notes, so an approach fits before a change.
    - ``rhythm_focus``: Practice-Focus label for the rhythm plan (a rhythmic Mission's intent).
    - ``no_chromatic``: no outside notes at all (chord-tone / common-scale / pentatonic goals).
    - ``require_syncopation``: the rhythm cell carries a (style-restrained) syncopation.
    - ``plain_rhythm``: straight / dotted cells only, repeated exactly (an "Easier" example).
    - ``simple_pitches``: a 2–4 note pitch cell per chord, repeated notes welcome — the rhythm
      carries the line (the "rhythm over note choice" Mission).
    - ``free_ending``: the phrase may end on a stable extension (9 / 6 / 11 / maj7) in jazz at
      Intermediate / Advanced; False where the Mission requires a structural resolution.
    - ``inner_enclosure``: a role ("R", "3", "5", "7") of the FIRST chord that the line encloses inside that chord - two
      neighbour notes around it, one of them a half step away - before the connector carries it into the next chord.
    """

    target_roles: tuple[str, ...] = ()
    pitch_space: str = ""
    common_pcs: tuple[int, ...] = ()
    connector: str = ""
    color: str = ""
    smooth_targets: bool = False
    tail_short: bool = False
    rhythm_focus: str = ""
    no_chromatic: bool = False
    require_syncopation: bool = False
    plain_rhythm: bool = False
    simple_pitches: bool = False
    free_ending: bool = True
    inner_enclosure: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["target_roles"] = list(self.target_roles)
        d["common_pcs"] = list(self.common_pcs)
        return d

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "SpanConstraints | None":
        if not isinstance(data, dict) or not data:
            return None
        return SpanConstraints(
            target_roles=tuple(data.get("target_roles") or ()),
            pitch_space=str(data.get("pitch_space") or ""),
            common_pcs=tuple(int(x) for x in data.get("common_pcs") or ()),
            connector=str(data.get("connector") or ""),
            color=str(data.get("color") or ""),
            smooth_targets=bool(data.get("smooth_targets")),
            tail_short=bool(data.get("tail_short")),
            rhythm_focus=str(data.get("rhythm_focus") or ""),
            no_chromatic=bool(data.get("no_chromatic")),
            require_syncopation=bool(data.get("require_syncopation")),
            plain_rhythm=bool(data.get("plain_rhythm")),
            simple_pitches=bool(data.get("simple_pitches")),
            free_ending=bool(data.get("free_ending", True)),
            inner_enclosure=str(data.get("inner_enclosure") or ""),
        )


def _constraint_space(ctx: Any, c: "SpanConstraints | None") -> tuple[int, ...] | None:
    if c is None or not c.pitch_space:
        return None
    if c.pitch_space == "chord":
        return tuple(ctx.chord_pcs)
    if c.pitch_space == "pentatonic":
        return _pentatonic(ctx)
    if c.pitch_space == "scale":
        return tuple(ctx.scale_pcs)
    if c.pitch_space == "common" and c.common_pcs:
        return tuple(sorted(set(c.common_pcs)))
    return None


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
    allowed_roles: Sequence[str] = (),
    vl_weight: float = 1.0,
    allowed_pcs: Sequence[set[int] | None] = (),
) -> list[tuple[int, str]]:
    """Minimum-cost landing note per chord (dynamic programming over chord tones).

    ``roles_pref``: "guide" (3rds/7ths), "chord" (plain chord tones) or level default.
    ``fixed_role``: every chord starts on the same degree (a sequence of the idea).
    """
    layers: list[list[tuple[int, str, float]]] = []
    for li, ctx in enumerate(contexts):
        cands = []
        arrival = li == len(contexts) - 1 and resolve_to_stable
        allowed_here = allowed_pcs[li] if li < len(allowed_pcs) else None
        for pc in ctx.chord_pcs:
            if allowed_here and pc not in allowed_here:
                continue
            role = _role(ctx, pc)
            jitter = rng.uniform(0.0, 0.9 if level == "Beginner" else 0.5)
            settle = 0.9 if arrival and role not in ("R", "3") else 0.0
            fixed = 0.0 if not fixed_role or role == fixed_role or arrival else 2.5
            barred = 6.0 if allowed_roles and role not in allowed_roles else 0.0
            for m in _in_register(pc):
                cands.append(
                    (m, role, _target_role_cost(role, level, roles_pref) + settle + fixed + barred + jitter
                     + 0.03 * abs(m - CENTER))
                )
        layers.append(cands)
    best: list[dict[int, tuple[float, int | None]]] = []
    best.append({i: (c[2] + start_weight * abs(c[0] - start_near), None) for i, c in enumerate(layers[0])})
    for li in range(1, len(layers)):
        cur: dict[int, tuple[float, int | None]] = {}
        for i, (m, role, base) in enumerate(layers[li]):
            choice = None
            for j, (pm, prole, _b) in enumerate(layers[li - 1]):
                total = best[li - 1][j][0] + vl_weight * voice_leading_cost(pm, prole, m, role, contexts[li]) + base
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


_LYDIAN = (0, 2, 4, 6, 7, 9, 11)


def _inner_enclosure_notes(ctx: Any, role: str, *, before: int, rng: random.Random) -> list[tuple[int, str]] | None:
    """The three notes [neighbour, neighbour, tone] that enclose the first chord's ``role`` tone, or None when the chord has no
    such tone. One neighbour is a half step from the tone, the other a half or whole step on the opposite side."""
    tones = [m for pc in ctx.chord_pcs if _role(ctx, pc) == role for m in _in_register(pc)]
    if not tones:
        return None
    tone = min(tones, key=lambda m: (abs(m - before), m))
    upper = [tone + d for d in (1, 2) if (tone + d) % 12 in ctx.scale_pcs or d == 1]
    lower = [tone - d for d in (1, 2) if (tone - d) % 12 in ctx.scale_pcs or d == 1]
    pairs = [(u, l) for u in upper for l in lower if 1 in (u - tone, tone - l)]
    pairs = [(u, l) for u, l in pairs if (u % 12 in ctx.chord_pcs) + (l % 12 in ctx.chord_pcs) == 0] or pairs
    u, l = rng.choice(pairs)
    first, second = (u, l) if rng.random() < 0.5 else (l, u)
    return [(first, "connector"), (second, "connector"), (tone, "cell")]


def _jazz_colour_rate(ctx: Any, next_ctx: Any | None, tier: str) -> float:
    """How often an Advanced jazz dominant takes an outside colour (sometimes, not always).

    A tritone substitute (resolving down a half step) *is* a Lydian-dominant sound, so it is
    coloured more often than a V7 → I.
    """
    if next_ctx is not None and ctx.quality == "dom" and (next_ctx.chord_pcs[0] - ctx.chord_pcs[0]) % 12 == 11:
        return 0.85
    return 0.8 if tier == "harder" else 0.55


def lydian_color(ctx: Any, *, rng: random.Random, level: str, total: int) -> tuple[str, tuple[int, ...]] | None:
    """Lydian / ♯11 on a major-7th chord — only where ♯11 is a real colour.

    Needs a maj7 sonority (never a plain triad or dominant), room for the colour to resolve
    (three or more notes on the chord), and a ♯11 that is *outside* the song's scale (on IV it
    is already diatonic, so calling it Lydian colour would be empty). Occasional, not automatic.
    """
    if ctx.quality != "maj7" or total < 3:
        return None
    root = ctx.chord_pcs[0]
    if (root + 6) % 12 in ctx.scale_pcs:
        return None
    if rng.random() >= (0.3 if level == "Intermediate" else 0.4):
        return None
    return "lydian", tuple((root + s) % 12 for s in _LYDIAN)


# Stable extensions a jazz phrase can end on, by chord quality (semitones above the root).
_ENDING_EXTENSIONS = {
    "maj7": (2, 9, 11),  # 9th, 6th / 13th, major 7th
    "major": (2, 9),  # 9th, 6th
    "m7": (2, 5),  # 9th, 11th
    "minor": (2, 5),
    "dom": (2, 9),  # 9th, 13th
    "half-dim": (5,),  # 11th
}


def extension_ending(
    ctx: Any, prev: int, *, level: str, style: str, tier: str, constraints: "SpanConstraints | None",
    rng: random.Random,
) -> int | None:
    """A jazz phrase sometimes ends on a stable extension instead of R / 3 / 5.

    Intermediate / Advanced, jazz styles only, never when the Mission requires a structural
    resolution (``free_ending=False``). The extension is in the chord-scale and a step or a
    small skip from the previous note, so it sounds like a lyrical landing, not a leap.
    """
    if style not in JAZZ_STYLES or level == "Beginner" or tier == "easier":
        return None
    if constraints is not None and (not constraints.free_ending or constraints.pitch_space in ("chord", "common")):
        return None
    ivs = _ENDING_EXTENSIONS.get(ctx.quality)
    if not ivs or rng.random() >= (0.3 if level == "Intermediate" else 0.45):
        return None
    root = ctx.chord_pcs[0]
    pcs = [(root + iv) % 12 for iv in ivs if (root + iv) % 12 in ctx.scale_pcs]
    options = [m for pc in pcs for m in _in_register(pc) if 1 <= abs(m - prev) <= 4]
    if not options:
        return None
    return min(options, key=lambda m: (abs(m - prev), m))


def _spell_color_notes(seg: list[_Note], ctx: Any, color: str, chord_symbol: str) -> None:
    """Outside notes take the colour scale's own spelling (C♯ in E half-whole, F♯ in C Lydian)."""
    try:
        from music_theory import pitch_class_from_spelled_note as note_to_pc, split_chord
        from span_motif_explain import _COLOR_SPELLING, spell_from_root
    except ImportError:
        return
    pattern = _COLOR_SPELLING.get(color)
    if not pattern:
        return
    root = str(split_chord(str(chord_symbol).split("/", 1)[0])[0] or "")
    if not root:
        return
    names = {}
    for name in spell_from_root(root, pattern):
        try:
            names[note_to_pc(name) % 12] = name
        except Exception:
            continue
    for n in seg:
        pc = n.midi % 12
        if pc not in ctx.scale_pcs and pc in names:
            n.name = names[pc]


# Per-bar pitch cells (0 = anchor, 1 = partner, 2 = third note): mostly the anchor, repeated.
_LINE_CELLS = {
    "Beginner": ((0, 0, 0, 1), (0, 0, 1, 1), (0, 0, 0, 0, 1)),
    "Intermediate": ((0, 0, 0, 1), (0, 0, 1, 1), (0, 0, 1, 1, 0)),
    "Advanced": ((0, 0, 1, 1, 0), (0, 0, 0, 1, 2), (0, 0, 1, 1, 2)),
}


def _nearest_chord_tone(ctx: Any, ref: int, *, exclude: Sequence[int] = (), lo: int = 0, hi: int = 7) -> int | None:
    opts = [m for pc in ctx.chord_pcs for m in _in_register(pc) if lo <= abs(m - ref) <= hi and m not in exclude]
    return min(opts, key=lambda m: (abs(m - ref), m)) if opts else None


def _simplify_line(
    notes: list[_Note], contexts: Sequence[Any], realization: Any, meter: str, *, level: str, rng: random.Random,
) -> list[_Note]:
    """Rhythm-Mission pitches: one anchor note (and a small partner) carried across the changes.

    The anchor stays put while it is still a chord tone of the next chord and otherwise
    moves to the nearest chord tone; the partner does the same. A per-bar pitch cell repeats
    with the rhythm, so each bar is mostly the same note — the rhythm is the exercise. Every
    change lands on the anchor (a chord tone), and the line ends on a stable chord tone.
    """
    from melodic_rhythm_engine import parse_meter

    if not notes:
        return notes
    bar_len = parse_meter(meter).bar
    events = list(realization.note_events)
    cell = _LINE_CELLS[level][rng.randrange(len(_LINE_CELLS[level]))]
    first = {}
    for i, n in enumerate(notes):
        first.setdefault(n.chord_index, i)
    anchor = partner = None
    vocab_by_slot: dict[int, list[int]] = {}
    for ci in sorted(first):
        ctx = contexts[ci]
        if anchor is None:
            a = notes[first[ci]].midi
        elif anchor % 12 in ctx.chord_pcs:
            a = anchor  # common tone: nothing needs to change
        else:
            a = _nearest_chord_tone(ctx, anchor, lo=1) or notes[first[ci]].midi
        if partner is not None and partner % 12 in ctx.chord_pcs and 1 <= abs(partner - a) <= 5:
            b = partner
        else:
            b = _nearest_chord_tone(ctx, a, exclude=(a,), lo=1, hi=5) or _step(a, 1, ctx.scale_pcs)
        vocab = [a, b]
        if level == "Advanced":
            c = _step(a, -1 if b > a else 1, ctx.scale_pcs)
            vocab.append(c if c not in vocab else _step(a, 2, ctx.scale_pcs))
        vocab_by_slot[ci] = vocab
        anchor, partner = a, b
    out: list[_Note] = []
    pos_in_bar: dict[int, int] = {}
    for i, n in enumerate(notes):
        ci = n.chord_index
        vocab = vocab_by_slot[ci]
        bar = int(events[i].onset // bar_len) if i < len(events) else 0
        pos = pos_in_bar.get(bar, 0)
        pos_in_bar[bar] = pos + 1
        if i == first[ci]:
            m, kind = vocab[0], "target"
        elif i == len(notes) - 1:
            ctx = contexts[ci]
            stable = [v for v in vocab if _role(ctx, v % 12) in _STABLE_ROLES]
            m = stable[0] if stable else (_nearest_chord_tone(ctx, vocab[0]) or vocab[0])
            kind = "ending"
        else:
            m, kind = vocab[min(cell[pos % len(cell)], len(vocab) - 1)], "cell"
        note = _note(contexts[ci], m, ci, kind)
        note.locked = True
        out.append(note)
    return out


def _resolve_line_tensions(notes: list[_Note], contexts: Sequence[Any], colors: dict[int, str], limit: int) -> None:
    """Final guarantee after every repair pass: an outside colour note steps (≤ 2) to its next
    note. Inside a side-slip the borrowed fragment may continue outside, but its last outside
    note must step back in. Anything else returns to the nearest chord tone."""
    for k, n in enumerate(notes):
        if n.kind != "tension" or n.locked:
            continue
        ctx = contexts[n.chord_index]
        nxt = notes[k + 1] if k + 1 < len(notes) else None
        if nxt is not None and 1 <= abs(nxt.midi - n.midi) <= 2:
            continue
        if (
            nxt is not None and colors.get(n.chord_index) == "side_slip" and nxt.chord_index == n.chord_index
            and nxt.midi % 12 not in ctx.scale_pcs and abs(nxt.midi - n.midi) <= 4
        ):
            continue  # still inside the slipped idea
        prev = notes[k - 1].midi if k > 0 else None
        nm = nxt.midi if nxt is not None else None
        options = [
            m for pc in ctx.chord_pcs for m in _in_register(pc)
            if m not in (prev, nm) and all(abs(m - x) <= limit for x in (prev, nm) if x is not None)
        ]
        if options:
            notes[k] = _note(ctx, min(options, key=lambda m: (abs(m - n.midi), m)), n.chord_index, "cell")


def _resolve_tensions(seg: list[_Note], ctx: Any, chord_index: int, *, next_target: int | None) -> None:
    """An outside colour note must move by step (≤ 2 semitones) to its next note; else it goes."""
    for k, n in enumerate(seg):
        if n.kind != "tension" or n.locked:
            continue
        nxt = seg[k + 1].midi if k + 1 < len(seg) else next_target
        if nxt is not None and 1 <= abs(nxt - n.midi) <= 2:
            continue
        prev = seg[k - 1].midi if k > 0 else n.midi
        options = [m for pc in ctx.chord_pcs for m in _in_register(pc) if m != prev and abs(m - n.midi) <= 4]
        if options:
            seg[k] = _note(ctx, min(options, key=lambda m: (abs(m - n.midi), m)), chord_index, "cell")


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
    tail: Sequence[Fraction] = (),
    mode: str = "",
    step_pcs: Sequence[int] | None = None,
) -> list[tuple[int, str, bool | None]]:
    """Notes (midi, kind, spelled-below) leading from the current chord into ``target``.

    ``tail``: durations of the slot's last notes. A held last note is a breath before the
    change, so it stays diatonic; an enclosure needs two short notes.
    ``mode``: a caller-required approach (see :class:`SpanConstraints`); ``step_pcs`` the
    collection a diatonic step walks in (defaults to the chord-scale).
    """
    if room <= 0:
        return []
    if mode:
        return _mode_connectors(prev, target, ctx, mode=mode, level=level, room=room, step_pcs=step_pcs)
    scale = ctx.scale_pcs
    held = bool(tail) and tail[-1] >= Fraction(3, 2)
    if len(tail) >= 2 and tail[-2] >= Fraction(3, 2):
        room = 1
    if level == "Beginner" or (held and color is None):
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


def _mode_connectors(
    prev: int, target: int, ctx: Any, *, mode: str, level: str, room: int, step_pcs: Sequence[int] | None
) -> list[tuple[int, str, bool | None]]:
    """A required approach into ``target``: step / chord / chromatic / enclosure / double.

    Beginner never receives chromatic notes: chromatic modes fall back to diatonic ones.
    """
    pcs = tuple(step_pcs) if step_pcs else tuple(ctx.scale_pcs)
    from_above = prev > target
    sign = 1 if from_above else -1
    up, down = _step(target, 1, pcs), _step(target, -1, pcs)
    if mode == "chord":
        near = [m for pc in ctx.chord_pcs for m in _in_register(pc) if 1 <= abs(m - target) <= 5 and m != prev]
        if near:
            return [(min(near, key=lambda m: (abs(m - target), abs(m - prev), m)), "connector", None)]
        mode = "step"
    if mode in ("enclosure", "double") and room >= 2:
        if mode == "double" and level == "Advanced":
            return [(target + 2 * sign, "connector", sign < 0), (target + sign, "connector", sign < 0)]
        lower = down if level == "Beginner" else target - 1
        pair = [(up, "connector", None), (lower, "connector", True if target - lower == 1 else None)]
        if not from_above:
            pair.reverse()  # arriving from below: lower neighbour first
        return pair
    if mode in ("chromatic", "enclosure", "double") and level != "Beginner":
        outside = [s_ for s_ in (sign, -sign) if (target + s_) % 12 not in ctx.scale_pcs and target + s_ != prev]
        s_ = outside[0] if outside else sign
        return [(target + s_, "connector", s_ < 0)]
    step = up if from_above else down
    if step == prev:
        step = down if from_above else up
    return [(step, "connector", None)]


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
    notes: list[_Note], contexts: Sequence[Any], spaces: Sequence[Sequence[int]], limit: int, *, diatonic: bool = False,
    strict: bool = False,
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
                if strict:
                    moves = {m for m in moves if m % 12 in spaces[n.chord_index]}
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


def _fix_adjacent_repeats(
    notes: list[_Note], contexts: Sequence[Any], spaces: Sequence[Sequence[int]], limit: int, *, strict: bool = False
) -> None:
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
                if strict:
                    moves = [m for m in moves if m % 12 in spaces[n.chord_index]]
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


# The family a Practice Focus asks for, per level (first one available wins).
_FOCUS_PRIMARY: dict[str, tuple[str, ...]] = {
    "scales": ("scalar_fragment",),
    "pentatonic": ("pentatonic_cell",),
    "guide_tones": ("guide_tone_line", "common_tone_anchor"),
    "chord_tones": ("chord_tone_cell",),
    "rhythm": ("rhythmic_motif",),
    "motif": ("sequence", "call_response", "chord_tone_cell"),
    "bebop": ("bebop_run", "enclosure_line", "scalar_fragment"),
    "lyrical": ("lyrical_arch",),
}
_FOCUS_PRIMARY_SHARE = 0.65


def _choose_family(span: Any, *, level: str, focus: str, style: str, rng: random.Random) -> str:
    """Practice Focus picks its own family about two times in three (when the level has it);
    otherwise the Level × style × harmony weights decide — focus biases, never dictates."""
    weights = family_weights(span, level=level, focus=focus, style=style)
    names = sorted(weights)
    primary = next((f for f in _FOCUS_PRIMARY.get(focus_preference(focus), ()) if f in weights), None)
    if primary is not None and rng.random() < _FOCUS_PRIMARY_SHARE:
        return primary
    return rng.choices(names, weights=[weights[n] for n in names])[0]


def _development(family: str, span: Any) -> str:
    if span.repeated_vamp:
        return "vamp_restatement"
    if family == "sequence":
        return "sequence"
    if family == "call_response":
        return "call_response"
    return "cell_carry"


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
    constraints: SpanConstraints | None = None,
) -> dict[str, Any]:
    """One connected motif across ``span``.

    ``length``: ``seed`` (a short connected idea), ``standard`` (the developed exercise)
    or ``extended`` (the span played twice: the opening returns, the ending answers).
    Standard / Extended are always a development of the seed (see :func:`develop_span_motif`).
    ``plan``: a previous result's ``span_seed`` — regenerates *that* seed.
    ``focus``: the Practice Focus label; ``style``: :func:`song_style` bucket.
    ``vocabulary``: ``auto`` or a forced family (``chord_tones`` / ``guide_tones`` / a family id).
    ``constraints``: optional :class:`SpanConstraints` (a Mission's requirements).
    """
    if length not in LENGTHS:
        raise ValueError(f"unknown span length: {length}")
    if length != "seed":
        seed_motif = generate_span_motif(
            span, level=level, variant=variant, instrument=instrument, meter=meter, vocabulary=vocabulary,
            seed=seed, plan=plan, focus=focus, style=style, candidates=candidates, constraints=constraints,
        )
        return develop_span_motif(span, seed_motif, length=length)
    from span_rhythm_grammar import plan_seed_rhythm, rhythm_coherence

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
    slots = chord_timeline(span, meter=meter)
    density = int(STYLE_PROFILES[style]["density"]) + int(FAMILIES[family].get("density", 0))
    # The rhythm is planned first: its cell decides how many notes each bar holds.
    rhythm_focus = constraints.rhythm_focus if constraints is not None and constraints.rhythm_focus else focus
    rplan = plan_seed_rhythm(
        [s.bars for s in slots], level=lvl, style=style, focus_pref=focus_preference(rhythm_focus), tier=tier,
        family_density=density, development=_development(family, span), meter=meter, seed=seed_value,
        tail_short=bool(constraints is not None and constraints.tail_short),
        require_syncopation=bool(constraints is not None and constraints.require_syncopation),
        plain_rhythm=bool(constraints is not None and constraints.plain_rhythm),
        rhythmic=bool(constraints is not None and constraints.simple_pitches),
    )
    realization = rplan.realization(lvl)
    # Pitch candidates are cheap; musicality picks the most coherent line for the planned
    # rhythm. The seed picks among the near-best so New Idea keeps varying instead of
    # converging; ``plan`` regenerates exactly the seed's winning candidate.
    attempts = [int(plan["attempt"])] if plan and "attempt" in plan else range(max(1, int(candidates)))
    drafts = [
        _generate_once(
            span, level=lvl, tier=tier, seed=seed_value, attempt=k, family=family, focus=focus, style=style,
            instrument=instrument, slots=slots, rplan=rplan, realization=realization, constraints=constraints,
        )
        for k in attempts
    ]
    def _clean(d: dict[str, Any]) -> bool:
        mids = [n.midi for n in d["notes"]]
        return d["meta"]["musicality"]["alternation"] == 0 and all(
            a != b and abs(a - b) <= _MAX_LEAP[lvl] for a, b in zip(mids, mids[1:])
        )

    simple = bool(constraints is not None and constraints.simple_pitches)
    clean = [d for d in drafts if _clean(d)]
    if not clean and not (plan and "attempt" in plan) and not simple:
        # Every candidate broke a guardrail (rare with dense cells): search a little further.
        more = [
            _generate_once(
                span, level=lvl, tier=tier, seed=seed_value, attempt=k, family=family, focus=focus, style=style,
                instrument=instrument, slots=slots, rplan=rplan, realization=realization, constraints=constraints,
            )
            for k in range(len(drafts), len(drafts) + 10)
        ]
        clean = [d for d in more if _clean(d)]
    drafts = clean or drafts
    top = max(d["meta"]["musicality"]["total"] for d in drafts)
    near = [d for d in drafts if d["meta"]["musicality"]["total"] >= top - 1.0]
    best = near[random.Random(seed_value ^ 0x5F3759DF).randrange(len(near))]
    motif = _assemble_motif(
        span, best["notes"], slots, realization, meter=meter, level=lvl, seed=best["rhythm_seed"], style=style, focus=focus,
    )
    motif.update(best["meta"])
    motif["rhythm_plan"] = {
        "cell": list(rplan.cell.figures),
        "cell_kind": rplan.cell.kind,
        "bar_roles": [b.role for b in rplan.bars],
        "bar_cells": [list(b.cell.figures) for b in rplan.bars],
    }
    motif["rhythm_coherence"] = rhythm_coherence(realization.events, meter, style=style)
    motif["note_details"] = [n.kind for n in best["notes"]]
    if constraints is not None:
        motif["mission_constraints"] = constraints.to_dict()
    return motif


def _generate_once(
    span: Any,
    *,
    level: str,
    tier: str,
    seed: int,
    attempt: int,
    family: str,
    focus: str,
    style: str,
    instrument: str,
    slots: Sequence[ChordSlot],
    rplan: Any,
    realization: Any,
    constraints: SpanConstraints | None = None,
) -> dict[str, Any]:
    lvl = level
    c = constraints
    profile = FAMILIES[family]
    sty = STYLE_PROFILES[style]
    rng0 = random.Random(seed * 31 + attempt)
    rng = random.Random(seed + 7919 + attempt * 104729)
    rng_x = random.Random((seed * 131 + attempt * 17) ^ 0xC0105)
    jazz = style in JAZZ_STYLES
    simple = c is not None and c.simple_pitches
    if profile.get("cells") == "wide":
        cell_pool = _CELLS["wide"]
    elif profile["space"] == "chord":
        cell_pool = _CELLS["arpeggio"]
    else:
        cell_pool = _CELLS[lvl]
    cell = cell_pool[rng0.randrange(len(cell_pool))]
    development = _development(family, span)
    contexts = [_ctx(span.key_center, s.chord) for s in slots]
    pref = focus_preference(focus)
    roles_pref = "guide" if (profile.get("roles") == "guide" or pref == "guide_tones") else ("chord" if pref == "chord_tones" else "")
    fixed_role = ""
    if profile.get("roles") == "fixed":
        fixed_role = ("3", "R", "5")[rng0.randrange(3)]
    leads_forward = contexts[-1].quality == "dom" and span.relationship in ("ii_V", "ii_subV", "dominant_chain", "ii_V_chain")
    # The seed owns the starting register; candidates only explore its neighbours, so
    # different New Ideas search different spaces rather than converging on one line.
    start_near = (60, 64, CENTER, 71, 74)[(seed + (0, 0, 1, 4, 0)[attempt % 5]) % 5]
    targets = choose_targets(
        contexts, level=lvl, rng=rng, start_near=start_near, roles_pref=roles_pref,
        fixed_role=fixed_role, resolve_to_stable=not leads_forward,
        allowed_roles=c.target_roles if c is not None else (),
        vl_weight=2.5 if c is not None and c.smooth_targets else 1.0,
        allowed_pcs=[
            (set(_constraint_space(cx, c) or ()) & set(cx.chord_pcs)) or None
            if c is not None and c.pitch_space in ("pentatonic", "common") else None
            for cx in contexts
        ],
    )
    counts = rplan.counts_by_slot(len(slots))
    note_events = realization.note_events
    slot_durs: list[list[Fraction]] = []
    k = 0
    for si in range(len(slots)):
        n = sum(counts[si])
        slot_durs.append([e.duration for e in note_events[k:k + n]])
        k += n

    notes: list[_Note] = []
    vocab: set[str] = {"chord_tone"}
    colors: list[dict[str, Any]] = []
    orientations: list[str] = []
    for si, slot in enumerate(slots):
        ctx = contexts[si]
        total = sum(counts[si])
        tail = slot_durs[si][-2:]
        target_midi = targets[si][0]
        seg: list[_Note] = [_note(ctx, target_midi, si, "target")]
        is_last = si == len(slots) - 1
        nxt_target = None if is_last else targets[si + 1][0]
        nxt_ctx = None if is_last else contexts[si + 1]
        color = None
        forbid = c is not None and (c.color == "forbid" or c.no_chromatic)
        if c is not None and c.color == "require" and lvl == "Advanced" and not is_last and not forbid:
            color = dominant_color(ctx, nxt_ctx, rng=rng, tier=tier, chord_symbol=slot.chord)
        # Jazz dominants take a colour often but not always; elsewhere it scales with the
        # style's appetite. The colour itself is always chosen from the harmony.
        elif not forbid and not simple and lvl == "Advanced" and tier != "easier" and not is_last and (
            rng_x.random() < _jazz_colour_rate(ctx, nxt_ctx, tier) if jazz else rng.random() < 0.3 + sty["chromatic"]
        ):
            color = dominant_color(ctx, nxt_ctx, rng=rng, tier=tier, chord_symbol=slot.chord)
            if (
                color is None and ctx.quality in ("m7", "half-dim") and style in JAZZ_STYLES and total >= 5
                and family in _LINEAR_FAMILIES and rng.random() < 0.35
            ):
                # Side-slip: the ii idea played a half step up, then back inside by step.
                color = ("side_slip", tuple((p + 1) % 12 for p in ctx.scale_pcs))
        if color is None and not forbid and not simple and jazz and lvl != "Beginner" and tier != "easier":
            color = lydian_color(ctx, rng=rng_x, level=lvl, total=total)
        if color:
            colors.append({"chord_index": si, "chord": slot.chord, "color": color[0]})
            vocab.add(color[0])
        space = _constraint_space(ctx, c) or _space(ctx, profile["space"])
        base_cell = cell
        if profile.get("answer") and si % 2 == 1:
            base_cell = tuple(-d for d in cell)  # the answer turns the idea over
        if is_last:
            body_len = total - 1
        else:
            # Room for the connector: two notes only where an enclosure is likely and the
            # rhythm gives two short notes before the change.
            short_tail = len(tail) >= 2 and max(tail) < Fraction(3, 2)
            two = lvl != "Beginner" and total >= 4 and short_tail and (
                profile.get("connector") == "enclosure" or (lvl == "Advanced" and total >= 5)
            )
            if c is not None and c.connector:
                two = c.connector in ("enclosure", "double") and total >= 3 and short_tail
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
        inner = c.inner_enclosure if (c is not None and si == 0 and not is_last) else ""
        if inner and len(body) >= 3:
            ring = _inner_enclosure_notes(ctx, inner, before=body[-4][0] if len(body) > 3 else target_midi, rng=rng_x)
            if ring is not None:
                body = body[:-3] + ring
                vocab.add("first_chord_enclosure")
        orientations.append(orientation)
        for midi, kind in body:
            seg.append(_note(ctx, midi, si, kind))
        if inner and "first_chord_enclosure" in vocab:
            ring_len = 3
            for n_ in seg[-ring_len:]:
                n_.locked = True
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
                    # A cadence prefers the root (then the 3rd) unless reaching it means a leap.
                    d = abs(m - prev)
                    closeness = 9.0 if d == 0 else 0.0 if d <= 2 else 0.8 if d <= 4 else 2.0
                    if leads_forward:
                        weight = {"3": 0.0, "7": 0.0, "5": 1.0}.get(_role(ctx, m), 2.0)
                    else:
                        weight = {"R": 0.0, "3": 0.5, "5": 1.5}.get(_role(ctx, m), 2.0)
                    return (closeness + weight, d, m)

                end_m = min(stable, key=_settle)
                ext = None if leads_forward or simple else extension_ending(
                    ctx, prev, level=lvl, style=style, tier=tier, constraints=c, rng=rng_x,
                )
                seg[-1] = _note(ctx, ext if ext is not None else end_m, si, "ending")
                if ext is not None:
                    seg[-1].locked = True  # a chosen extension: repairs never move it
                    vocab.add("extension_ending")
        else:
            room = total - len(seg)
            mode = ""
            if c is not None:
                mode = c.connector or ("chord" if c.pitch_space == "chord" else "step" if c.no_chromatic else "")
            conn = _connectors(
                seg[-1].midi, nxt_target, ctx, level=lvl, tier=tier, room=room, rng=rng, color=color, style=sty,
                family=family, tail=tail, mode=mode, step_pcs=_constraint_space(ctx, c) if mode == "step" else None,
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
        if not simple:
            _avoid_repeats(seg, notes[-1].midi if notes else None, ctx, space, si)
        _resolve_tensions(seg, ctx, si, next_target=nxt_target)
        if color:
            _spell_color_notes(seg, ctx, color[0], slot.chord)
        if color and not any(n.kind == "tension" for n in seg) and not any(
            n.midi % 12 in color[1] and n.midi % 12 not in ctx.scale_pcs for n in seg
        ):
            colors[:] = [x for x in colors if x["chord_index"] != si]
        if any(n.midi % 12 not in ctx.chord_pcs for n in seg):
            vocab.add("scale" if profile["space"] != "pentatonic" else "pentatonic")
        notes.extend(seg)

    if simple:
        notes = _simplify_line(notes, contexts, realization, rplan.meter, level=lvl, rng=rng_x)
    _repair_leaps(notes, contexts, _MAX_LEAP[lvl])
    spaces = [_constraint_space(cx, c) or _space(cx, profile["space"]) for cx in contexts]
    strict = c is not None and c.no_chromatic
    _break_alternation(notes, contexts, spaces, _MAX_LEAP[lvl], diatonic=lvl == "Beginner", strict=strict)
    _fix_adjacent_repeats(notes, contexts, spaces, _MAX_LEAP[lvl], strict=strict)
    if colors:
        _resolve_line_tensions(notes, contexts, {x["chord_index"]: x["color"] for x in colors}, _MAX_LEAP[lvl])
        colors[:] = [
            x for x in colors
            if any(n.chord_index == x["chord_index"] and n.midi % 12 not in contexts[n.chord_index].scale_pcs for n in notes)
        ]
    meta = {
        "strategy_family": family,
        "development_strategy": development,
        "vocabulary_used": sorted(vocab),
        "advanced_colors": colors,
        "span_length": "seed",
        "level": lvl,
        "variant": tier,
        "style": style,
        "focus": focus,
        "focus_preference": pref,
        "span_seed": {"seed": seed, "attempt": attempt, "family": family, "cell": list(cell), "strategy": development,
                      "level": lvl, "focus": focus, "style": style, "rhythm_cell": list(rplan.cell.figures)},
        "instrument": instrument,
        "cell_orientations": orientations,
        "musicality": musicality([n.midi for n in notes], [n.chord_index for n in notes], contexts, level=lvl),
        "transition_targets": _transition_targets(notes, contexts),
        "note_kinds": [n.kind for n in notes],
    }
    return {"notes": notes, "rhythm_seed": seed + attempt, "meta": meta}


def _transition_targets(notes: Sequence[_Note], contexts: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {"chord_index": n.chord_index, "note_index": i, "midi": n.midi, "name": n.name,
         "role": _role(contexts[n.chord_index], n.midi % 12)}
        for i, n in enumerate(notes)
        if n.kind == "target"
    ]


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


def _bar_note_counts(realization: Any, meter: str) -> list[int]:
    from melodic_rhythm_engine import parse_meter

    bar = parse_meter(meter).bar
    counts = [0] * int(realization.bars)
    for e in realization.note_events:
        counts[int(e.onset // bar)] += 1
    return counts


def _assemble_motif(
    span: Any,
    notes: Sequence[_Note],
    slots: Sequence[ChordSlot],
    realization: Any,
    *,
    meter: str,
    level: str,
    seed: int,
    style: str = "default",
    focus: str = "",
) -> dict[str, Any]:
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi

    if len(realization.note_events) != len(notes):
        raise ValueError(f"rhythm holds {len(realization.note_events)} notes for {len(notes)} pitches")
    bar_counts = _bar_note_counts(realization, meter)
    meta = {
        "meter": meter, "level": level, "group": 0, "seed": int(seed), "roles": [n.role for n in notes],
        "bar_counts": bar_counts, "downbeat_bars": [s.first_bar for s in slots], "style": style, "focus": focus,
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
        "pattern_note_roles": [n.role for n in notes],
        "is_pattern": False,
        "last_transform": "span_generate",
    }
    motif.update(_engine_rhythm_fields(realization, index=0, count=1, meta=meta))
    motif["rhythm_profile"] = rhythm_profile(realization, meter)
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
    """Change Rhythm: the next *motivic* rhythm for the same notes per bar — pitches and chords untouched.

    Bars holding the same number of notes keep sharing one cell, so the alternative is
    still a repeated rhythmic idea, not a fresh bar-by-bar shuffle.
    """
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi
    from melodic_rhythm_engine import events_from_json
    from span_rhythm_grammar import motivic_candidates, rhythm_coherence

    meta = dict(motif.get("rhythm_meta") or {})
    meter = str(meta.get("meter") or "4/4")
    style = str(meta.get("style") or "default")
    cands = motivic_candidates(
        list(meta.get("bar_counts") or []), meter=meter, level=str(meta.get("level") or "Intermediate"),
        style=style, focus_pref=focus_preference(str(meta.get("focus") or "")),
        downbeat_bars=list(meta.get("downbeat_bars") or []), seed=int(meta.get("seed") or 0),
    )
    current = tuple((e.duration, e.rest, e.tuplet) for e in events_from_json(motif.get("rhythm_events") or []))
    cands = [c for c in cands if c.signature != current]
    if not cands:
        return motif
    previous = list(meta.get("history") or [])
    index = next((i for i, c in enumerate(cands) if c.id not in previous), 0)
    out = dict(motif)
    meta["history"] = (previous + [str(meta.get("id") or "")])[-12:]
    out.update(_engine_rhythm_fields(cands[index], index=index, count=len(cands), meta=meta))
    out["rhythm_profile"] = rhythm_profile(cands[index], meter)
    out["rhythm_coherence"] = rhythm_coherence(cands[index].events, meter, style=style)
    out["last_transform"] = "change_rhythm"
    return sync_motif_midi(out)


def _projected_symbol(source: str, project_chord: Callable[[str], str] | None) -> str:
    text = str(source or "").strip()
    if not text or project_chord is None:
        return text
    return str(project_chord(text) or text)


def _timeline_chord(motif: dict[str, Any], chord_index: int | None) -> str:
    if chord_index is None:
        return ""
    timeline = motif.get("chord_timeline") or []
    if 0 <= chord_index < len(timeline):
        slot = timeline[chord_index]
        if isinstance(slot, dict):
            return str(slot.get("chord") or "")
    span = motif.get("span_chords") or []
    if 0 <= chord_index < len(span):
        return str(span[chord_index] or "")
    return ""


def _chord_index_at(motif: dict[str, Any], index: int) -> int | None:
    raw = motif.get("note_chord_index") or []
    if index >= len(raw):
        return None
    try:
        return int(raw[index])
    except (TypeError, ValueError):
        return None


def _approaches_from_below(
    index: int,
    midis: Sequence[int],
    kinds: Sequence[str],
    details: Sequence[str],
    timeline: Sequence[dict[str, Any]],
) -> bool:
    """Half-step-below spelling, matching generator connectors, enclosures, and ornaments."""
    midi = int(midis[index])
    kind = kinds[index] if index < len(kinds) else ""
    detail = details[index] if index < len(details) else ""
    if kind not in ("connector", "tension", "ornament") and detail not in (
        "chromatic_passing",
        "enclosure",
        "chromatic approach",
    ):
        return False
    if index + 1 < len(midis) and int(midis[index + 1]) - midi == 1:
        return True
    arrivals = set()
    for slot in timeline:
        if isinstance(slot, dict) and "first_note" in slot:
            try:
                arrivals.add(int(slot["first_note"]))
            except (TypeError, ValueError):
                continue
    for j in range(index + 1, min(len(midis), index + 3)):
        is_target = j in arrivals or (j < len(kinds) and kinds[j] == "target")
        if is_target and int(midis[j]) - midi == 1:
            return True
    return False


def _name_keeps_midi(name: str, midi: int) -> bool:
    from improvisation_motif import _midi_from_note

    try:
        return _midi_from_note(name, 4) % 12 == int(midi) % 12
    except Exception:
        return False


def _respell_projected_notes(
    motif: dict[str, Any],
    midis: Sequence[int],
    chart_key: str,
    project_chord: Callable[[str], str] | None,
) -> list[str]:
    """Spell shifted pitches from each note's destination chord, not the chart key alone."""
    from improvisation_motif import _note_from_midi

    kinds = [str(k) for k in (motif.get("note_kinds") or [])]
    details = [str(d) for d in (motif.get("note_details") or kinds)]
    timeline = list(motif.get("chord_timeline") or [])
    contexts: dict[str, Any] = {}
    names: list[str] = []
    chord_at: list[str] = []
    for i, midi in enumerate(midis):
        dest = _projected_symbol(_timeline_chord(motif, _chord_index_at(motif, i)), project_chord)
        chord_at.append(dest)
        if not dest:
            names.append(_note_from_midi(int(midi), chart_key))
            continue
        ctx = contexts.get(dest)
        if ctx is None:
            ctx = _ctx(chart_key, dest)
            contexts[dest] = ctx
        below = True if _approaches_from_below(i, midis, kinds, details, timeline) else None
        spelled = _spell(ctx, int(midi) % 12, below_target=below)
        names.append(spelled if _name_keeps_midi(spelled, int(midi)) else _note_from_midi(int(midi), chart_key))
    colors: dict[int, dict[str, Any]] = {}
    for entry in motif.get("advanced_colors") or []:
        if not isinstance(entry, dict):
            continue
        try:
            colors[int(entry["chord_index"])] = entry
        except (KeyError, TypeError, ValueError):
            continue
    if not colors:
        return names
    grouped: dict[int, list[int]] = {}
    for i in range(len(midis)):
        ci = _chord_index_at(motif, i)
        if ci in colors:
            grouped.setdefault(ci, []).append(i)
    for ci, idxs in grouped.items():
        entry = colors[ci]
        dest = _projected_symbol(str(entry.get("chord") or ""), project_chord) or (
            chord_at[idxs[0]] if idxs else ""
        )
        if not dest:
            continue
        ctx = contexts.get(dest)
        if ctx is None:
            ctx = _ctx(chart_key, dest)
            contexts[dest] = ctx

        class _Named:
            def __init__(self, midi: int, name: str) -> None:
                self.midi = midi
                self.name = name

        seg = [_Named(int(midis[i]), names[i]) for i in idxs]
        _spell_color_notes(seg, ctx, str(entry.get("color") or ""), dest)
        for note, i in zip(seg, idxs):
            if _name_keeps_midi(note.name, int(midis[i])):
                names[i] = note.name
    return names


def project_span_motif(
    motif: dict[str, Any],
    *,
    semitones: int,
    chart_key: str,
    project_chord: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Concert span motif → written/shape chart (MIDI shifted, chord-aware respell, symbols projected)."""
    if not semitones and project_chord is None:
        return motif
    from improvisation_motif import sync_motif_midi

    out = dict(motif)
    if semitones:
        midis = [int(m) + int(semitones) for m in motif.get("midi") or []]
        out["midi"] = midis
        out["notes"] = _respell_projected_notes(motif, midis, chart_key, project_chord)
        out["display"] = " – ".join(out["notes"])
    if project_chord is not None:
        out["bar_chord_symbols"] = [project_chord(s) if s else None for s in motif.get("bar_chord_symbols") or []]
        out["chord"] = " → ".join(project_chord(c) for c in motif.get("span_chords") or [])
    out["projected_chart_key"] = chart_key
    return sync_motif_midi(out)


# --------------------------------------------------------------------------- build: develop the seed


@dataclass
class _Item:
    note: _Note
    event: Any  # melodic_rhythm_engine.RhythmEvent
    origin: int | None  # index of the seed note this is (None: a note the development added)
    detail: str  # seed kind, or passing / neighbour / chord_tone / chromatic_passing / enclosure


_SPLITS_PER_BAR = {"Beginner": 1, "Intermediate": 1, "Advanced": 2}


def _seed_items(seed_motif: dict[str, Any]) -> list[_Item]:
    from melodic_rhythm_engine import events_from_json

    note_evs = [e for e in events_from_json(seed_motif.get("rhythm_events") or []) if not e.rest]
    kinds = list(seed_motif.get("note_kinds") or [])
    details = list(seed_motif.get("note_details") or kinds)
    roles = list(seed_motif.get("pattern_note_roles") or [])
    items = []
    for i, (m, name, ci, e) in enumerate(
        zip(seed_motif["midi"], seed_motif["notes"], seed_motif["note_chord_index"], note_evs)
    ):
        kind = kinds[i] if i < len(kinds) else "cell"
        items.append(_Item(
            _Note(int(m), str(name), roles[i] if i < len(roles) else "chord_tone", int(ci), kind),
            e, i, details[i] if i < len(details) else kind,
        ))
    return items


def _ornament_space(
    ctx: Any, *, family: str, focus_pref: str, color_pcs: Sequence[int] | None, constraints: SpanConstraints | None = None
) -> tuple[set[int], set[int]]:
    """(preferred, allowed) pitch classes for an added note on this chord."""
    fixed = _constraint_space(ctx, constraints)
    if fixed:
        return set(fixed), set(fixed)
    allowed = set(ctx.scale_pcs)
    if color_pcs:
        allowed = set(color_pcs) | set(ctx.chord_pcs)
        return allowed, allowed
    if focus_pref == "pentatonic" or FAMILIES[family]["space"] == "pentatonic":
        return set(_pentatonic(ctx)), allowed
    if FAMILIES[family]["space"] == "bebop" or focus_pref == "bebop":
        return set(_bebop(ctx)), allowed | set(_bebop(ctx))
    return allowed, allowed


def _ornament_options(
    a: int,
    b: int,
    *,
    ctx: Any,
    level: str,
    style: str,
    family: str,
    focus_pref: str,
    color_pcs: Sequence[int] | None,
    enclosure_target: int | None,
    constraints: SpanConstraints | None = None,
) -> list[tuple[float, int, str]]:
    """Candidate added notes between ``a`` and ``b`` (score, midi, detail), best first."""
    prefer, allowed = _ornament_space(
        ctx, family=family, focus_pref=focus_pref, color_pcs=color_pcs, constraints=constraints
    )
    out: list[tuple[float, int, str]] = []
    lo, hi = sorted((a, b))
    mid = (a + b) / 2
    scalar = 0.0 if focus_pref in ("scales", "lyrical") else 0.2
    for m in range(lo + 1, hi):
        pc = m % 12
        if pc in prefer:
            out.append((scalar + 0.2 * abs(m - mid), m, "passing"))
        elif pc in allowed:
            out.append((0.6 + 0.2 * abs(m - mid), m, "passing"))
    if focus_pref in ("chord_tones", "guide_tones") or FAMILIES[family]["space"] == "chord":
        for pc in ctx.chord_pcs:
            for m in _in_register(pc):
                if m not in (a, b) and abs(m - a) <= 5 and abs(m - b) <= 5:
                    guide = focus_pref == "guide_tones" and pc in ctx.guide_pcs
                    out.append(((0.0 if guide else 0.3) + 0.1 * abs(m - mid), m, "chord_tone"))
    walk = sorted(prefer) or sorted(allowed)
    for base in (b, a):
        for d in (1, -1):
            m = _step(base, d, walk)
            if m not in (a, b):
                out.append((1.0 + 0.15 * max(abs(m - a), abs(m - b)), m, "neighbour"))
    # Chromatic decoration is jazz language: pop / rock / folk / ballad lines stay diatonic.
    jazzy = (style in JAZZ_STYLES or style == "default") and not (constraints is not None and constraints.no_chromatic)
    chromatic_ok = jazzy and (level == "Advanced" or (level == "Intermediate" and (focus_pref == "bebop" or style in JAZZ_STYLES)))
    if chromatic_ok and hi - lo == 2 and (lo + 1) % 12 not in ctx.scale_pcs:
        out.append((0.4 if focus_pref == "bebop" or family == "bebop_run" else 0.9, lo + 1, "chromatic_passing"))
    if enclosure_target is not None and level != "Beginner" and 1 <= abs(b - enclosure_target) <= 2:
        m = 2 * enclosure_target - b  # the other side of the target from the approach note
        if m % 12 in ctx.scale_pcs or (jazzy and (level == "Advanced" or abs(m - enclosure_target) == 1)):
            keen = FAMILIES[family].get("connector") == "enclosure" or focus_pref in ("bebop", "guide_tones")
            out.append((0.15 if keen else 0.7, m, "enclosure"))
    best: dict[int, tuple[float, int, str]] = {}
    for opt in out:
        if opt[1] not in best or opt[0] < best[opt[1]][0]:
            best[opt[1]] = opt
    return sorted(best.values(), key=lambda t: (t[0], t[1]))


def _change_starts(items: Sequence[_Item]) -> set[int]:
    return {i for i in range(1, len(items)) if items[i].note.chord_index != items[i - 1].note.chord_index}


def _try_ornament(
    items: list[_Item],
    i: int,
    *,
    contexts: Sequence[Any],
    colors: dict[int, tuple[int, ...]],
    level: str,
    style: str,
    family: str,
    focus_pref: str,
    constraints: SpanConstraints | None = None,
) -> list[_Item] | None:
    from span_rhythm_grammar import split_event

    it = items[i]
    nxt = items[i + 1] if i + 1 < len(items) else None
    prv = items[i - 1] if i > 0 else None
    ci = it.note.chord_index
    ctx = contexts[ci]
    if constraints is not None and constraints.simple_pitches:
        # Rhythm-first line: the split repeats the same pitch — denser rhythm, same tiny cell.
        first, second = split_event(it.event)
        repeat = _note(ctx, it.note.midi, ci, "ornament")
        repeat.locked = True
        out = list(items)
        out[i] = _Item(it.note, first, it.origin, it.detail)
        out.insert(i + 1, _Item(repeat, second, None, "repeated note"))
        return out
    before_change = nxt is not None and nxt.note.chord_index != ci
    if it.note.kind == "target":
        modes = ["after"]
    elif before_change:
        modes = ["before"]  # the approach stays next to the target it approaches
    else:
        modes = ["after", "before"]
    limit = min(_MAX_LEAP[level], 7)
    midis = [x.note.midi for x in items]
    best: tuple[float, str, int, str] | None = None
    for mode in modes:
        if mode == "after":
            if nxt is None:
                continue
            a, b, pos = it.note.midi, nxt.note.midi, i + 1
            enclosure_target = None
        else:
            if prv is None:
                continue
            a, b, pos = prv.note.midi, it.note.midi, i
            enclosure_target = nxt.note.midi if before_change else None
        new_next_is_change = mode == "after" and before_change
        for score, m, detail in _ornament_options(
            a, b, ctx=ctx, level=level, style=style, family=family, focus_pref=focus_pref,
            color_pcs=colors.get(ci), enclosure_target=enclosure_target, constraints=constraints,
        ):
            if m in (a, b) or abs(m - a) > limit or abs(m - b) > limit or not REGISTER[0] <= m <= REGISTER[1]:
                continue
            pc = m % 12
            inside = pc in ctx.scale_pcs or pc in (colors.get(ci) or ())
            fixed = _constraint_space(ctx, constraints)
            if fixed and pc not in fixed and constraints is not None and constraints.no_chromatic:
                continue
            if level == "Beginner" and pc not in ctx.scale_pcs:
                continue
            # Chromatic notes only lead into a chord change (approach / enclosure / passing).
            near_change = before_change and (mode == "before" or new_next_is_change)
            if not inside and not near_change:
                continue
            if new_next_is_change and abs(m - b) > 2:
                continue
            trial = midis[:pos] + [m] + midis[pos:]
            if _alternates_at(trial, pos, m):
                continue
            if best is None or score < best[0]:
                best = (score, mode, m, detail)
            break
    if best is None:
        return None
    _score, mode, m, detail = best
    first, second = split_event(it.event)
    below = None
    out = list(items)
    if mode == "after":
        target_pitch = nxt.note.midi if nxt is not None else None
        if target_pitch is not None and before_change and target_pitch - m == 1:
            below = True
        added = _Item(_note(ctx, m, ci, "ornament", below_target=below), second, None, detail)
        out[i] = _Item(it.note, first, it.origin, it.detail)
        out.insert(i + 1, added)
    else:
        if b - m == 1 or (detail == "enclosure" and nxt is not None and nxt.note.midi - m == 1):
            below = True
        added = _Item(_note(ctx, m, ci, "ornament", below_target=below), first, None, detail)
        out[i] = _Item(it.note, second, it.origin, "enclosure" if detail == "enclosure" else it.detail)
        out.insert(i, added)
    return out


def _diminish(
    items: list[_Item],
    *,
    contexts: Sequence[Any],
    colors: dict[int, tuple[int, ...]],
    level: str,
    tier: str,
    style: str,
    family: str,
    focus_pref: str,
    bar_len: Fraction,
    final_slot: int,
    variant: int = 0,
    constraints: SpanConstraints | None = None,
) -> list[_Item]:
    """Split values of the seed's rhythm and fill them with related notes.

    The seed notes stay in order (most at their own onsets); bars that carried the same
    cell are split at the same place, so the rhythmic repetition survives the development.
    """
    from span_rhythm_grammar import LYRICAL_STYLES, SYNCOPATING_STYLES, split_allowed

    out = list(items)
    if not out:
        return out
    n_bars = int((out[-1].event.onset + out[-1].event.duration) // bar_len)
    # Ballads keep their space; pop / rock keep a hook-like pulse rather than running eighths.
    per_bar = 1 if style in LYRICAL_STYLES or style in ("pop", "rock") else _SPLITS_PER_BAR[level]
    if tier == "harder":
        per_bar += 1
    signatures: dict[int, tuple] = {}
    for b in range(n_bars):
        lo = bar_len * b
        signatures[b] = tuple((x.event.onset - lo, x.event.duration) for x in out if lo <= x.event.onset < lo + bar_len)
    chosen: dict[tuple, Fraction] = {}
    for b in range(n_bars):
        lo, hi = bar_len * b, bar_len * (b + 1)
        sig = signatures[b]
        bar_items = [x for x in out if lo <= x.event.onset < hi]
        if len(bar_items) == 1 and bar_items[0].note.chord_index == final_slot and bar_items[0].event.duration == bar_len:
            continue  # a held resolution stays held
        for k in range(per_bar):
            idx = [j for j, x in enumerate(out) if lo <= x.event.onset < hi and j != len(out) - 1]
            ranked = []
            for j in idx:
                e = out[j].event
                if not split_allowed(e, level=level, style=style):
                    continue
                d = e.duration
                if style in LYRICAL_STYLES:
                    pri = {Fraction(1): 0.0, Fraction(3, 2): 1.0, Fraction(3): 2.0, Fraction(4): 2.0, Fraction(2): 3.0}.get(d, 5.0)
                else:
                    pri = {Fraction(4): 0.0, Fraction(3): 0.0, Fraction(2): 0.2, Fraction(3, 2): 1.0, Fraction(1): 2.0}.get(d, 5.0)
                if out[j].note.kind == "target":
                    pri += 0.5
                beat_off = e.onset % 1 != 0 and e.onset + e.duration > e.onset - e.onset % 1 + 1
                if beat_off and style in SYNCOPATING_STYLES:
                    pri += 3.0  # keep the syncopation that makes the cell
                ranked.append((pri, e.onset, j))
            ranked.sort()
            order = [j for _p, _o, j in ranked]
            if variant and len(order) > 1:
                r = variant % len(order)
                order = order[r:] + order[:r]
            want = chosen.get((sig, k))
            if want is not None:
                order.sort(key=lambda j: out[j].event.onset - lo != want)
            for j in order:
                res = _try_ornament(out, j, contexts=contexts, colors=colors, level=level, style=style,
                                    family=family, focus_pref=focus_pref, constraints=constraints)
                if res is not None:
                    chosen.setdefault((sig, k), out[j].event.onset - lo)
                    out = res
                    break
    if len(out) == len(items) and split_allowed(out[-1].event, level=level, style=style):
        # Nothing else could be split (e.g. an all-eighths seed): approach the held final note.
        res = _try_ornament(out, len(out) - 1, contexts=contexts, colors=colors, level=level, style=style,
                            family=family, focus_pref=focus_pref, constraints=constraints)
        if res is not None:
            out = res
    return out


def _color_collection(name: str, ctx: Any) -> tuple[int, ...] | None:
    root = ctx.chord_pcs[0]
    if name == "lydian_dominant":
        return tuple(((root + 7) % 12 + s) % 12 for s in _MELODIC_MINOR)
    if name == "altered":
        return tuple(((root + 1) % 12 + s) % 12 for s in _MELODIC_MINOR)
    if name == "diminished":
        return tuple((root + s) % 12 for s in (0, 1, 3, 4, 6, 7, 9, 10))
    if name == "whole_tone":
        return tuple((root + s) % 12 for s in (0, 2, 4, 6, 8, 10))
    if name == "side_slip":
        return tuple((p + 1) % 12 for p in ctx.scale_pcs)
    if name == "lydian":
        return tuple((root + s) % 12 for s in _LYDIAN)
    return None


def _turnaround(
    final_items: Sequence[_Item],
    template: Sequence[Any],
    *,
    prev_midi: int | None,
    t0: int,
    before: Sequence[int] = (),
    after: Sequence[int] = (),
    ctx: Any,
    chord_index: int,
    family: str,
    cell: tuple[int, ...],
    level: str,
    tier: str,
    style: str,
    slot_start: Fraction,
    slot_bars: int,
    bar_len: Fraction,
) -> list[_Item] | None:
    """Pass 1's last chord, kept moving: its target, then a line back into the opening (t0)."""
    from melodic_rhythm_engine import RhythmEvent

    events = [
        RhythmEvent(slot_start + bar_len * k + e.onset, e.duration, e.written, e.rest, e.tuplet, e.tuplet_start, None)
        for k in range(slot_bars) for e in template if not e.rest
    ]
    n = len(events)
    if n < 2 or not final_items:
        return None
    tf = final_items[0].note.midi
    scale = tuple(sorted(set(ctx.scale_pcs)))
    limit = min(_MAX_LEAP[level], 7)
    # Beam search for the smoothest scalar line tf → (a neighbour of t0): steps and few
    # turns, no repeated pitch, no A-B-A-B against the bars on either side of the seam.
    beam: list[tuple[float, tuple[int, ...]]] = [(0.0, (tf,))]
    for depth in range(1, n):
        left = n - 1 - depth
        grown = []
        for cost, seq in beam:
            for d in (-2, -1, 1, 2):
                m = _step(seq[-1], d, scale)
                if not REGISTER[0] <= m <= REGISTER[1] or abs(m - seq[-1]) > limit:
                    continue
                if abs(m - t0) > 2 + 4 * left:
                    continue  # could no longer get home in the notes left
                line = list(before) + list(seq) + [m]
                if _alternates_at(line, len(line) - 1, m):
                    continue
                step = m - seq[-1]
                turn = 2.0 if len(seq) > 1 and (seq[-1] - seq[-2]) * step < 0 else 0.0
                grown.append((cost + abs(step) + turn, seq + (m,)))
        grown.sort(key=lambda t: (t[0] + 0.5 * max(0, abs(t[1][-1] - t0) - 2), t[1]))
        beam = grown[:96]
    finals = []
    for cost, seq in beam:
        last = seq[-1]
        if last == t0 or abs(last - t0) > 2:
            continue
        line = list(before) + list(seq) + [t0] + list(after)
        if any(_alternates_at(line, j, line[j]) for j in range(len(line))):
            continue
        turn = 2.0 if len(seq) > 1 and (last - seq[-2]) * (t0 - last) < 0 else 0.0
        finals.append((cost + abs(t0 - last) + turn, seq))
    if not finals:
        return None
    seq = list(min(finals, key=lambda t: (t[0], t[1]))[1])
    # Jazz above Beginner: a whole-step approach becomes the chromatic half step from that side.
    if level != "Beginner" and (style in JAZZ_STYLES or style == "default") and abs(seq[-1] - t0) == 2:
        chrom = t0 + (1 if seq[-1] > t0 else -1)
        trial = list(before) + seq[:-1] + [chrom, t0] + list(after)
        if chrom != seq[-2] and abs(chrom - seq[-2]) <= limit and not any(
            _alternates_at(trial, j, trial[j]) for j in range(len(trial))
        ):
            seq[-1] = chrom
    notes = [_note(ctx, tf, chord_index, "target")]
    notes += [_note(ctx, m, chord_index, "cell") for m in seq[1:-1]]
    notes.append(_note(ctx, seq[-1], chord_index, "connector", below_target=True if t0 - seq[-1] == 1 else None))
    return [_Item(x, e, None, x.kind) for x, e in zip(notes, events)]


def develop_span_motif(span: Any, seed_motif: dict[str, Any], *, length: str = "standard") -> dict[str, Any]:
    """Build: develop the seed (its notes, its rhythm) through the span — never a new phrase.

    Standard: the seed with values split and filled (passing / neighbour / chord-tone /
    enclosure / chromatic-passing notes, by Level, style and Practice Focus).
    Extended: pass 1 = that development, its last chord leading back to the opening;
    pass 2 = the same opening, then an answering variation and the cadence.
    """
    from melodic_rhythm_engine import parse_meter
    if length not in ("standard", "extended"):
        raise ValueError(f"build length must be standard or extended, not {length}")
    meter = str((seed_motif.get("rhythm_meta") or {}).get("meter") or "4/4")
    bar_len = parse_meter(meter).bar
    lvl = _level(seed_motif.get("level") or "Intermediate")
    tier = _tier(seed_motif.get("variant") or "normal")
    style = str(seed_motif.get("style") or "default")
    style = style if style in STYLE_PROFILES else "default"
    focus = str(seed_motif.get("focus") or "")
    pref = focus_preference(focus)
    family = str(seed_motif.get("strategy_family") or "chord_tone_cell")
    slots1 = chord_timeline(span, meter=meter)
    contexts1 = [_ctx(span.key_center, s.chord) for s in slots1]
    n_slots = len(slots1)
    final_slot = n_slots - 1
    colors = {
        int(c["chord_index"]): col
        for c in seed_motif.get("advanced_colors") or []
        if (col := _color_collection(str(c.get("color")), contexts1[int(c["chord_index"])])) is not None
    }
    seed_items = _seed_items(seed_motif)
    constraints = SpanConstraints.from_dict(seed_motif.get("mission_constraints"))
    kw = dict(contexts=contexts1, colors=colors, level=lvl, tier=tier, style=style, family=family,
              focus_pref=pref, bar_len=bar_len, final_slot=final_slot, constraints=constraints)
    dev1 = _diminish(seed_items, variant=0, **kw)
    if length == "standard":
        # Candidate developments (different split choices) compete on how audibly they keep
        # the seed, then on melodic and rhythmic musicality; unrelated ones are rejected.
        scored = []
        for v in (0, 1, 2):
            cand = dev1 if v == 0 else _diminish(seed_items, variant=v, **kw)
            if v and [x.note.midi for x in cand] == [x.note.midi for x in dev1]:
                continue
            trial = _assemble_dev(span, cand, slots1, meter=meter, level=lvl, style=style, focus=focus, seed_motif=seed_motif)
            ident = motif_identity(seed_motif, trial)["total"]
            mus = musicality([x.note.midi for x in cand], [x.note.chord_index for x in cand], contexts1, level=lvl)["total"]
            coh = trial["rhythm_coherence"]["total"]
            # Ballads keep their held values: space is part of the style, not a gap to fill.
            space = 3.0 * trial["rhythm_profile"]["long"] if style in ("ballad", "jazz_ballad", "folk") else 0.0
            scored.append((ident >= 0.75, 2.0 * ident + 0.3 * mus + 0.5 * coh + space, -v, cand))
        dev1 = max(scored, key=lambda t: t[:3])[3]
        items, slots, contexts = dev1, slots1, contexts1
    else:
        dev2 = _diminish(seed_items, variant=1, **kw)
        pass_len = bar_len * sum(s.bars for s in slots1)
        head1 = [x for x in dev1 if x.note.chord_index < final_slot]
        template = [x.event for x in dev1 if x.event.onset < bar_len]
        cell = tuple((seed_motif.get("span_seed") or {}).get("cell") or (1, -1))
        turn = _turnaround(
            [x for x in dev1 if x.note.chord_index == final_slot], template,
            prev_midi=head1[-1].note.midi if head1 else None, t0=dev1[0].note.midi,
            before=[x.note.midi for x in head1[-3:]], after=[x.note.midi for x in dev1[1:4]], ctx=contexts1[final_slot],
            chord_index=final_slot, family=family, cell=cell, level=lvl, tier=tier, style=style,
            slot_start=slots1[final_slot].start, slot_bars=slots1[final_slot].bars, bar_len=bar_len,
        )
        pass1 = head1 + (turn if turn is not None else [x for x in dev1 if x.note.chord_index == final_slot])
        if seed_motif.get("development_strategy") == "vamp_restatement":
            answer = [x for x in dev1 if x.note.chord_index < final_slot] + [x for x in dev2 if x.note.chord_index == final_slot]
        else:
            answer = [x for x in dev1 if x.note.chord_index == 0] + [x for x in dev2 if x.note.chord_index > 0]
        pass2 = _shift_items(answer, pass_len, n_slots)
        def _clean(seq: Sequence[_Item]) -> bool:
            line = [x.note.midi for x in seq]
            return not any(_alternates_at(line, j, line[j]) for j in range(len(line))) and all(
                a != b for a, b in zip(line, line[1:])
            )

        if not _clean(pass1 + pass2):
            pass2 = _shift_items(dev1, pass_len, n_slots)
        items = pass1 + pass2
        slots = chord_timeline(span, meter=meter, passes=2)
        contexts = contexts1 * 2
    notes = [x.note for x in items]
    motif = _assemble_dev(span, items, slots, meter=meter, level=lvl, style=style, focus=focus, seed_motif=seed_motif)
    vocab = set(seed_motif.get("vocabulary_used") or ["chord_tone"])
    for x in items:
        ctx = contexts[x.note.chord_index]
        pc = x.note.midi % 12
        if x.origin is not None:
            continue
        if x.detail == "enclosure" and lvl != "Beginner":
            vocab.add("enclosure")
        if pc not in ctx.scale_pcs and pc not in (colors.get(x.note.chord_index % n_slots) or ()):
            vocab.add("chromatic_approach")
        elif pc not in ctx.chord_pcs:
            vocab.add("pentatonic" if FAMILIES[family]["space"] == "pentatonic" else "scale")
    colors_meta = [dict(c) for c in seed_motif.get("advanced_colors") or []]
    if length == "extended":
        colors_meta += [{**c, "chord_index": int(c["chord_index"]) + n_slots} for c in seed_motif.get("advanced_colors") or []]
    for key in ("strategy_family", "development_strategy", "span_seed", "variant", "style", "focus",
                "focus_preference", "instrument", "cell_orientations", "rhythm_plan", "mission_constraints"):
        if key in seed_motif:
            motif[key] = seed_motif[key]
    motif.update({
        "level": lvl,
        "span_length": length,
        "vocabulary_used": sorted(vocab),
        "advanced_colors": colors_meta,
        "musicality": musicality([n.midi for n in notes], [n.chord_index for n in notes], contexts, level=lvl),
        "transition_targets": _transition_targets(notes, contexts),
        "note_kinds": [n.kind for n in notes],
        "note_details": [x.detail for x in items],
        "seed_note_indices": [i for i, x in enumerate(items) if x.origin is not None],
        "seed_note_origin": [x.origin for x in items],
    })
    motif["motif_identity"] = motif_identity(seed_motif, motif)
    return motif


def _assemble_dev(
    span: Any, items: Sequence[_Item], slots: Sequence[ChordSlot], *, meter: str, level: str, style: str, focus: str,
    seed_motif: dict[str, Any],
) -> dict[str, Any]:
    """A developed line as a motif dict (rhythm realization built from its own events)."""
    from melodic_rhythm_engine import parse_meter
    from span_rhythm_grammar import realization_from_events, renumber, rhythm_coherence

    events = renumber([x.event for x in items])
    rid = f"dev:{parse_meter(meter).token}:" + ",".join(f"{e.onset}/{e.duration}" for e in events)
    realization = realization_from_events(events, meter, rid=f"dev:{zlib.crc32(rid.encode()) & 0xFFFFFFFF:08x}")
    motif = _assemble_motif(
        span, [x.note for x in items], slots, realization, meter=meter, level=level,
        seed=int((seed_motif.get("rhythm_meta") or {}).get("seed") or 0), style=style, focus=focus,
    )
    motif["rhythm_coherence"] = rhythm_coherence(realization.events, meter, style=style)
    return motif


def _shift_items(items: Sequence[_Item], offset: Fraction, slot_offset: int) -> list[_Item]:
    from melodic_rhythm_engine import RhythmEvent

    out = []
    for x in items:
        e = x.event
        moved = RhythmEvent(e.onset + offset, e.duration, e.written, e.rest, e.tuplet, e.tuplet_start, e.note)
        n = x.note
        out.append(_Item(_Note(n.midi, n.name, n.role, n.chord_index + slot_offset, n.kind, n.locked), moved, x.origin, x.detail))
    return out


# --------------------------------------------------------------------------- seed → Build identity


def _lcs(a: Sequence[Any], b: Sequence[Any]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def _sounding_curve(midis: Sequence[int], events: Sequence[Any], length: Fraction, step: Fraction) -> list[float]:
    notes = [e for e in events if not e.rest]
    out: list[float] = []
    t = Fraction(0)
    j = 0
    last = float(midis[0]) if midis else 0.0
    while t < length:
        while j + 1 < len(notes) and notes[j + 1].onset <= t:
            j += 1
        if j < len(notes) and notes[j].onset <= t and j < len(midis):
            last = float(midis[j])
        out.append(last)
        t += step
    return out


def motif_identity(seed_motif: dict[str, Any], built: dict[str, Any]) -> dict[str, Any]:
    """How recognizably ``built`` develops ``seed_motif`` (0–1 per part; higher = more related).

    - ``skeleton``: seed notes (pitch + chord) found in order in the build's first pass.
    - ``rhythm_cell``: share of each seed bar's onsets that the build keeps in that bar.
    - ``opening``: the seed's first three notes heard in the build's first four.
    - ``contour``: correlation of the sounding pitch over time (eighth-note grid).
    """
    from melodic_rhythm_engine import events_from_json, parse_meter
    from span_rhythm_grammar import bar_signatures

    meter = str((seed_motif.get("rhythm_meta") or {}).get("meter") or "4/4")
    bar_len = parse_meter(meter).bar
    n_slots = len(seed_motif.get("chord_timeline") or []) or 1
    s_mid, s_ci = list(seed_motif["midi"]), list(seed_motif["note_chord_index"])
    b_mid, b_ci = list(built["midi"]), list(built["note_chord_index"])
    s_ev = [e for e in events_from_json(seed_motif.get("rhythm_events") or []) if not e.rest]
    b_ev = [e for e in events_from_json(built.get("rhythm_events") or []) if not e.rest]
    s_sigs, b_sigs = bar_signatures(s_ev, meter), bar_signatures(b_ev, meter)
    n_bars = len(s_sigs)
    length = bar_len * n_bars
    sc = _sounding_curve(s_mid, s_ev, length, Fraction(1, 2))
    passes = max(1, len(built.get("chord_timeline") or []) // n_slots)
    per_pass = []
    for p in range(passes):
        idx = [i for i, c in enumerate(b_ci) if p * n_slots <= c < (p + 1) * n_slots]
        if not idx:
            continue
        pm = [b_mid[i] for i in idx]
        skeleton = _lcs(list(zip(s_mid, s_ci)), [(b_mid[i], b_ci[i] - p * n_slots) for i in idx]) / max(1, len(s_mid))
        kept = []
        for i, sig in enumerate(s_sigs):
            onsets = {x[0] for x in sig}
            j = p * n_bars + i
            if onsets and j < len(b_sigs):
                kept.append(len(onsets & {x[0] for x in b_sigs[j]}) / len(onsets))
        rhythm = sum(kept) / len(kept) if kept else 0.0
        shifted = [
            type(b_ev[i])(b_ev[i].onset - length * p, b_ev[i].duration, b_ev[i].written, False, b_ev[i].tuplet,
                          b_ev[i].tuplet_start, b_ev[i].note)
            for i in idx
        ]
        bc = _sounding_curve(pm, shifted, length, Fraction(1, 2))
        contour = 0.0
        if len(sc) > 2 and len(sc) == len(bc):
            ms, mb = sum(sc) / len(sc), sum(bc) / len(bc)
            cov = sum((x - ms) * (y - mb) for x, y in zip(sc, bc))
            vs = sum((x - ms) ** 2 for x in sc) ** 0.5
            vb = sum((y - mb) ** 2 for y in bc) ** 0.5
            contour = max(0.0, cov / (vs * vb)) if vs and vb else (1.0 if sc == bc else 0.0)
        head = min(3, len(s_mid))
        opening = _lcs(s_mid[:head], pm[:head + 1]) / max(1, head)
        total = 0.35 * skeleton + 0.25 * rhythm + 0.15 * opening + 0.25 * contour
        per_pass.append({
            "skeleton": round(skeleton, 3), "rhythm_cell": round(rhythm, 3), "opening": round(opening, 3),
            "contour": round(contour, 3), "total": round(total, 3),
        })
    if not per_pass:
        return {"skeleton": 0.0, "rhythm_cell": 0.0, "opening": 0.0, "contour": 0.0, "total": 0.0, "passes": []}
    best = dict(max(per_pass, key=lambda d: d["total"]))
    best["passes"] = per_pass
    return best


def build_span_exercise(span: Any, seed_motif: dict[str, Any], *, length: str = "standard", **_kw: Any) -> dict[str, Any]:
    """Build Span Exercise: develop *this* seed (as shown, including a changed rhythm) through the span."""
    return develop_span_motif(span, seed_motif, length=length)


__all__ = [
    "ChordSlot",
    "SpanConstraints",
    "develop_span_motif",
    "motif_identity",
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

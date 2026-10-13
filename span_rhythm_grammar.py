"""MC2.2 — rhythmic motif grammar for span motifs.

A span motif's rhythm is not a sequence of independently legal bars. It is one small
**rhythmic cell** that the phrase states, repeats or varies, and then closes with a
cadence built from the cell's own opening:

    statement (A) → repeat (A) / variation (A′) → cadence (A's head + a long note)

The plan is made *before* pitches, so it fixes how many notes each bar holds; the pitch
generator then fills exactly those notes. Build develops a seed by **diminution** —
splitting values of the seed's own rhythm (the same split in every bar that carries the
same cell) — so the seed's rhythm stays audible inside the exercise.

Style decides which cells are idiomatic (pop: straight / dotted, little syncopation;
jazz: syncopation, triplets; ballad: long values, space). Level gates the figures
(Beginner: quarters, halves and eighths on the beat). Practice Focus biases the choice.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence

from melodic_rhythm_engine import (
    FIGURES_BY_ID,
    BarRhythm,
    RhythmEvent,
    RhythmRealization,
    _bar_events,
    _opens_on_downbeat,
    _placement_ok,
    _top_bars,
    display_rhythm,
    parse_meter,
)

F = Fraction
LEVELS = ("Beginner", "Intermediate", "Advanced")
RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

# Curated 4/4 cells: every one opens with a note on beat 1 (a chord change can land there).
# Level and kind (straight / dotted / syncopated / triplet / sixteenth) are derived from the
# figures, so the list cannot mislabel a cell.
CELLS_44: tuple[tuple[str, ...], ...] = (
    ("h", "h"), ("dh", "q"), ("q", "dh"),
    ("q", "q", "h"), ("h", "q", "q"),
    ("q", "q", "q", "q"), ("ee", "q", "h"), ("q", "ee", "h"), ("h", "ee", "q"), ("h", "q", "ee"),
    ("ee", "ee", "h"), ("q", "q", "ee", "q"), ("ee", "q", "q", "q"), ("q", "ee", "q", "q"),
    ("ee", "q", "ee", "q"), ("ee", "ee", "q", "q"), ("q", "ee", "ee", "q"), ("ee", "ee", "ee", "q"),
    ("qd_e", "h"), ("qd_e", "q", "q"), ("q", "q", "qd_e"), ("qd_e", "qd_e"), ("qd_e", "ee", "q"), ("qd_e", "q", "ee"),
    ("e_q_e", "h"), ("q", "q", "e_qd"), ("e_q_e", "q", "q"), ("q", "q", "e_q_e"), ("e_q_e", "qd_e"),
    ("ee", "q", "e_qd"), ("e_q_e", "e_q_e"), ("e_q_e", "ee", "q"), ("q", "e_q_e", "q"),
    ("trip_e", "q", "h"), ("q", "trip_e", "h"), ("trip_e", "q", "q", "q"), ("q", "q", "trip_e", "q"),
    ("ee", "trip_e", "h"), ("trip_e", "trip_e", "h"), ("trip_q", "h"), ("e_q_e", "trip_e", "q"),
    ("e_ss", "q", "h"), ("q", "e_ss", "h"), ("ssss", "q", "h"),
)

# Appetite for each kind of cell, per song style (multiplies the cell's weight).
KIND_WEIGHTS: dict[str, dict[str, float]] = {
    "jazz": {"straight": 1.0, "dotted": 0.6, "syncopated": 1.8, "triplet": 1.3, "sixteenth": 0.4},
    "bossa": {"straight": 1.0, "dotted": 0.9, "syncopated": 1.8, "triplet": 0.15, "sixteenth": 0.3},
    "blues": {"straight": 1.0, "dotted": 0.8, "syncopated": 1.2, "triplet": 1.5, "sixteenth": 0.2},
    "jazz_ballad": {"straight": 1.0, "dotted": 0.9, "syncopated": 0.3, "triplet": 0.4, "sixteenth": 0.0},
    "ballad": {"straight": 1.0, "dotted": 0.6, "syncopated": 0.04, "triplet": 0.0, "sixteenth": 0.0},
    "pop": {"straight": 1.5, "dotted": 1.0, "syncopated": 0.12, "triplet": 0.0, "sixteenth": 0.05},
    "rock": {"straight": 1.5, "dotted": 0.8, "syncopated": 0.2, "triplet": 0.0, "sixteenth": 0.1},
    "funk": {"straight": 0.7, "dotted": 0.6, "syncopated": 1.8, "triplet": 0.0, "sixteenth": 1.4},
    "folk": {"straight": 1.5, "dotted": 1.0, "syncopated": 0.04, "triplet": 0.0, "sixteenth": 0.0},
    "default": {"straight": 1.2, "dotted": 0.8, "syncopated": 0.6, "triplet": 0.4, "sixteenth": 0.2},
}
# Preference for cells holding a half note or longer (space, lyricism).
LONG_PREF: dict[str, float] = {
    "jazz": 0.0, "bossa": 0.2, "blues": 0.2, "jazz_ballad": 1.2, "ballad": 1.5,
    "pop": 0.4, "rock": 0.3, "funk": 0.0, "folk": 0.9, "default": 0.3,
}
LYRICAL_STYLES = {"ballad", "jazz_ballad", "folk"}
SYNCOPATING_STYLES = {"jazz", "bossa", "blues", "funk"}
# Practice Focus multiplies kinds — a bias, never an override (pop syncopation stays modest).
FOCUS_KIND_FACTORS: dict[str, dict[str, float]] = {
    "rhythm": {"syncopated": 2.5, "dotted": 1.6},
    "bebop": {"triplet": 1.5, "straight": 1.2},
    "lyrical": {"long": 2.0},
    "scales": {"straight": 1.2},
}
_SEED_COUNT = {"Beginner": 3, "Intermediate": 4, "Advanced": 5}


# --------------------------------------------------------------------------- cells


@dataclass(frozen=True)
class CellInfo:
    figures: tuple[str, ...]
    level: str
    kind: str
    notes: int
    has_long: bool
    displaced: bool


def bar_rhythm(figures: Sequence[str], meter: str = "4/4") -> BarRhythm | None:
    """A validated bar from figure ids (placement, bar length), or None."""
    m = parse_meter(meter)
    pos = F(0)
    rank = 0
    fams: set[str] = set()
    displaced = False
    for fid in figures:
        fig = FIGURES_BY_ID.get(fid)
        if fig is None or fig.compound != m.compound:
            return None
        ok, disp = _placement_ok(fig, pos, m)
        if not ok:
            return None
        displaced = displaced or disp
        rank = max(rank, RANK[fig.level])
        fams.add(fig.family)
        pos += fig.span
    if pos != m.bar:
        return None
    if displaced:
        rank = 2
        fams.add("syncopated")
    return BarRhythm(tuple(figures), LEVELS[rank], tuple(sorted(fams)), displaced)


def cell_info(figures: Sequence[str], meter: str = "4/4") -> CellInfo | None:
    bar = bar_rhythm(figures, meter)
    if bar is None:
        return None
    evs, _ = _bar_events(bar, F(0), 0)
    notes = [e for e in evs if not e.rest]
    if any(e.tuplet for e in notes):
        kind = "triplet"
    elif any(e.duration < F(1, 2) for e in notes):
        kind = "sixteenth"
    elif bar.displaced or any(_crosses_beat(e.onset, e.duration, parse_meter(meter).beat) for e in notes):
        kind = "syncopated"
    elif "dotted" in bar.families:
        kind = "dotted"
    else:
        kind = "straight"
    return CellInfo(tuple(figures), bar.level, kind, len(notes), any(e.duration >= 2 for e in notes), bar.displaced)


def _crosses_beat(onset: Fraction, duration: Fraction, beat: Fraction) -> bool:
    if onset % beat == 0:
        return False
    return onset + duration > onset - onset % beat + beat


def cell_pool(meter: str, level: str) -> list[CellInfo]:
    """Cells playable at ``level`` that open on the downbeat (curated for 4/4, engine-derived otherwise)."""
    rank = RANK[level]
    if parse_meter(meter).token == "4/4":
        infos = [cell_info(c, meter) for c in CELLS_44]
    else:
        cap = 6
        infos = []
        for n in range(1, cap + 1):
            for bar in _top_bars(parse_meter(meter).token, n, level, None, 0, False, 6):
                if _opens_on_downbeat(bar):
                    infos.append(cell_info(bar.figures, meter))
    # Sixteenth cells are an Advanced idea here, whatever the figure table allows.
    return [c for c in infos if c is not None and RANK[c.level] <= rank and (c.kind != "sixteenth" or rank == 2)]


def _kind_weight(info: CellInfo, *, style: str, focus_pref: str) -> float:
    kinds = KIND_WEIGHTS.get(style, KIND_WEIGHTS["default"])
    w = kinds.get(info.kind, 0.5)
    factors = FOCUS_KIND_FACTORS.get(focus_pref, {})
    w *= factors.get(info.kind, 1.0)
    long_pref = LONG_PREF.get(style, 0.3) * factors.get("long", 1.0)
    if info.has_long:
        w *= 1.0 + long_pref
    elif style in LYRICAL_STYLES:
        w *= 0.5
    return w


def desired_count(level: str, *, style: str, family_density: int = 0, tier: str = "normal") -> int:
    """Notes in the seed's cell. ``family_density``: style + strategy-family density (ballads < 0)."""
    base = _SEED_COUNT[level] + int(family_density)
    if style in LYRICAL_STYLES and family_density >= 0:
        base -= 1
    if tier == "easier":
        base -= 1
    elif tier == "harder":
        base += 1
    return max(3, base)


def _short_tail(info: CellInfo, meter: str = "4/4") -> bool:
    """The cell's last two notes are short (room for an approach / enclosure before a change)."""
    bar = bar_rhythm(info.figures, meter)
    if bar is None:
        return False
    evs, _ = _bar_events(bar, F(0), 0)
    notes = [e for e in evs if not e.rest]
    return len(notes) >= 2 and all(e.duration < F(3, 2) for e in notes[-2:])


def _syncopated_entries(info: CellInfo, meter: str = "4/4") -> int:
    bar = bar_rhythm(info.figures, meter)
    if bar is None:
        return 0
    evs, _ = _bar_events(bar, F(0), 0)
    beat = parse_meter(meter).beat
    return sum(1 for e in evs if not e.rest and _crosses_beat(e.onset, e.duration, beat))


def choose_cell(
    meter: str, level: str, *, style: str, focus_pref: str, want: int, rng: random.Random, minimum: int = 3,
    tail_short: bool = False, require_syncopation: bool = False, plain: bool = False,
) -> CellInfo:
    pool = [c for c in cell_pool(meter, level) if c.notes >= minimum]
    if plain:
        # "Easier": plain values and never more notes than the level's target density.
        pool = [c for c in pool if c.kind in ("straight", "dotted") and c.notes <= want] or pool
    if tail_short:
        pool = [c for c in pool if _short_tail(c, meter)] or pool
    if require_syncopation:
        # Restrained where the style is: the fewest syncopated entries that still say "syncopation".
        synced = [c for c in pool if c.kind == "syncopated"]
        if synced and style in LYRICAL_STYLES | {"pop", "rock", "folk"}:
            synced = [c for c in synced if _syncopated_entries(c, meter) <= 1] or synced
        pool = synced or pool
    weights = []
    for c in pool:
        closeness = {0: 1.0, 1: 0.3}.get(abs(c.notes - want), 0.0)
        at_level = 1.3 if RANK[c.level] == RANK[level] and level != "Beginner" else 1.0
        weights.append(closeness * at_level * _kind_weight(c, style=style, focus_pref=focus_pref))
    if not any(w > 0 for w in weights):
        weights = [1.0 if c.notes == want else 0.1 for c in pool]
    return rng.choices(pool, weights=weights)[0]


# --------------------------------------------------------------------------- variation / cadence


def _ops(level: str, style: str, focus_pref: str) -> list[tuple[str, float]]:
    """Variation operators allowed here, with weights (A → A′)."""
    lyrical = style in LYRICAL_STYLES
    sync = KIND_WEIGHTS.get(style, KIND_WEIGHTS["default"])["syncopated"]
    ops = [("split", 1.0), ("tail", 0.8 if not lyrical else 0.3)]
    if lyrical:
        ops.append(("merge", 1.0))
    if level != "Beginner":
        ops.append(("dot", 0.7 if not lyrical else 0.5))
        if sync >= 0.5 or (focus_pref == "rhythm" and not lyrical):
            ops.append(("syncopate", 1.2 * sync + (0.6 if focus_pref == "rhythm" else 0.0)))
        if KIND_WEIGHTS.get(style, KIND_WEIGHTS["default"])["triplet"] >= 0.8:
            ops.append(("triplet", 0.8))
    return ops


def _apply_op(op: str, figs: tuple[str, ...], rng: random.Random) -> tuple[str, ...] | None:
    idx = list(range(len(figs)))
    rng.shuffle(idx)
    if op == "split":  # one quarter → two eighths (the classic pickup variation)
        for i in sorted(idx, key=lambda i: (figs[i] != "q", -i)):
            if figs[i] == "q":
                return figs[:i] + ("ee",) + figs[i + 1:]
    elif op == "tail":  # the closing half note answers as two quarters
        for i in range(len(figs) - 1, -1, -1):
            if figs[i] == "h":
                return figs[:i] + ("q", "q") + figs[i + 1:]
    elif op == "merge":  # ballad space: two quarters breathe as one half note
        for i in range(len(figs) - 1):
            if figs[i] == "q" and figs[i + 1] == "q":
                return figs[:i] + ("h",) + figs[i + 2:]
    elif op == "dot":
        for i in range(len(figs) - 1):
            if figs[i] == "q" and figs[i + 1] == "q":
                return figs[:i] + ("qd_e",) + figs[i + 2:]
    elif op == "syncopate":
        for i in range(len(figs) - 1):
            if figs[i] == "q" and figs[i + 1] == "q":
                return figs[:i] + ("e_q_e",) + figs[i + 2:]
    elif op == "triplet":
        for i in sorted(idx, key=lambda i: -i):
            if figs[i] == "q":
                return figs[:i] + ("trip_e",) + figs[i + 1:]
    return None


def vary_cell(
    cell: CellInfo, meter: str, level: str, *, style: str, focus_pref: str, rng: random.Random, minimum: int = 3
) -> CellInfo:
    """A′: one small, recognizable change to A (same opening idea), or A itself."""
    ops = _ops(level, style, focus_pref)
    order = []
    pool = list(ops)
    while pool:
        pick = rng.choices(pool, weights=[w for _, w in pool])[0]
        order.append(pick[0])
        pool.remove(pick)
    for op in order:
        figs = _apply_op(op, cell.figures, rng)
        if not figs or figs == cell.figures:
            continue
        info = cell_info(figs, meter)
        if info is None or RANK[info.level] > RANK[level] or info.notes < minimum:
            continue
        if style in LYRICAL_STYLES and info.kind in ("syncopated", "triplet", "sixteenth"):
            continue
        return info
    return cell


def cadence_cell(cell: CellInfo, meter: str, level: str) -> CellInfo:
    """The phrase ending: A's first half bar, then a held note (or A itself if it already closes long)."""
    m = parse_meter(meter)
    if m.token != "4/4":
        for bar in _top_bars(m.token, 2, level, None, 0, True, 6):
            info = cell_info(bar.figures, meter)
            if info is not None and _opens_on_downbeat(bar):
                return info
        return cell
    pos = F(0)
    head: list[str] = []
    for fid in cell.figures:
        if pos >= 2:
            break
        head.append(fid)
        pos += FIGURES_BY_ID[fid].span
    if pos == 2:
        info = cell_info(tuple(head) + ("h",), meter)
        if info is not None:
            return info
    return cell_info(("h", "h"), meter)  # type: ignore[return-value]


HOLD_44 = ("dh", "q")  # a held note, then a pickup into the next chord
HELD_44 = ("w",)  # a held resolution


# --------------------------------------------------------------------------- planning


@dataclass(frozen=True)
class BarPlan:
    bar: int
    slot: int
    role: str  # statement / repeat / variation / hold / cadence / held
    cell: CellInfo


@dataclass
class RhythmPlan:
    meter: str
    cell: CellInfo
    bars: list[BarPlan] = field(default_factory=list)

    def counts(self) -> list[int]:
        return [b.cell.notes for b in self.bars]

    def counts_by_slot(self, n_slots: int) -> list[list[int]]:
        out: list[list[int]] = [[] for _ in range(n_slots)]
        for b in self.bars:
            out[b.slot].append(b.cell.notes)
        return out

    def realization(self, level: str, *, prefix: str = "motif") -> RhythmRealization:
        m = parse_meter(self.meter)
        bars = [bar_rhythm(b.cell.figures, self.meter) for b in self.bars]
        events: list[RhythmEvent] = []
        note = 0
        for i, bar in enumerate(bars):
            evs, note = _bar_events(bar, m.bar * i, note)  # type: ignore[arg-type]
            events.extend(evs)
        rid = f"{prefix}:{m.token}:" + "/".join(b.id for b in bars)  # type: ignore[union-attr]
        return realization_from_events(events, self.meter, rid=rid)


def plan_seed_rhythm(
    slot_bars: Sequence[int],
    *,
    level: str,
    style: str,
    focus_pref: str,
    tier: str = "normal",
    family_density: int = 0,
    development: str = "cell_carry",
    meter: str = "4/4",
    seed: int = 0,
    tail_short: bool = False,
    require_syncopation: bool = False,
    plain_rhythm: bool = False,
) -> RhythmPlan:
    """The seed's rhythm: one cell stated, repeated / varied through the span, then a cadence.

    ``tail_short``: every bar before a chord change ends with two short notes (a Mission
    that approaches or encloses the next chord needs that room).
    """
    rng = random.Random(zlib.crc32(f"rhythm|{seed}|{level}|{style}|{focus_pref}|{tier}".encode()) & 0x7FFFFFFF)
    want = desired_count(level, style=style, family_density=family_density, tier=tier)
    a = choose_cell(meter, level, style=style, focus_pref=focus_pref, want=want, rng=rng, tail_short=tail_short,
                    require_syncopation=require_syncopation, plain=plain_rhythm)
    a2 = a if plain_rhythm else vary_cell(a, meter, level, style=style, focus_pref=focus_pref, rng=rng)
    if require_syncopation and a.kind == "syncopated":
        a2 = a  # keep the syncopated cell exact: it is the Mission
    if tail_short and not _short_tail(a2, meter):
        a2 = a
    plan = RhythmPlan(meter=meter, cell=a)
    hold = cell_info(HOLD_44, meter) if parse_meter(meter).token == "4/4" else a
    held = cell_info(HELD_44, meter) if parse_meter(meter).token == "4/4" else cadence_cell(a, meter, level)
    # Motif focus and Beginner keep the cell exact; above that the middle alternates A′ / A.
    alternate = level != "Beginner" and focus_pref != "motif" and development != "vamp_restatement"
    if level == "Beginner" and tier == "harder":
        alternate = True
    last = len(slot_bars) - 1
    bar = 0
    middle = 0
    for si, nbars in enumerate(slot_bars):
        for k in range(max(1, int(nbars))):
            if si == last:
                if nbars == 1:
                    role, cell = "cadence", cadence_cell(a, meter, level)
                elif k == nbars - 1:
                    role, cell = "held", held
                else:
                    role, cell = "repeat", a
            elif k == 0:
                if bar == 0:
                    role, cell = "statement", a
                else:
                    middle += 1
                    if alternate and middle % 2 == 1:
                        role, cell = "variation", a2
                    else:
                        role, cell = "repeat", a
            else:
                role, cell = ("repeat", a) if tail_short and k == nbars - 1 else ("hold", hold)
            plan.bars.append(BarPlan(bar, si, role, cell))  # type: ignore[arg-type]
            bar += 1
    return plan


# --------------------------------------------------------------------------- realization helpers


def realization_from_events(events: Sequence[RhythmEvent], meter: str, *, rid: str) -> RhythmRealization:
    m = parse_meter(meter)
    notes = [e for e in events if not e.rest]
    rank = 0
    fams: set[str] = set()
    for e in notes:
        if e.tuplet:
            fams.add("triplet")
            rank = max(rank, 2 if e.written >= 1 else 1)
        elif e.duration < F(1, 2):
            fams.add("straight")
            rank = max(rank, 1)
        elif _crosses_beat(e.onset, e.duration, m.beat):
            fams.add("syncopated")
            rank = max(rank, 1)
        elif e.duration in (F(3, 2), F(3, 4)):
            fams.add("dotted")
            rank = max(rank, 1)
        else:
            fams.add("straight")
    if any(e.rest for e in events):
        fams.add("rest")
    total = sum((e.duration for e in events), F(0))
    bars = int(total / m.bar) if total else 0
    return RhythmRealization(
        id=rid, meter=m.token, level=LEVELS[rank], families=tuple(sorted(fams)), bars=bars, unit_bars=bars,
        events=tuple(events), score=0.0, signature=tuple((e.duration, e.rest, e.tuplet) for e in events),
    )


def bar_signatures(events: Sequence[RhythmEvent], meter: str) -> list[tuple]:
    """Per bar: ((onset-in-bar, duration, rest, tuplet), …)."""
    m = parse_meter(meter)
    total = sum((e.duration for e in events), F(0))
    nbars = int(total / m.bar) if total else 0
    out: list[list[tuple]] = [[] for _ in range(nbars)]
    for e in events:
        b = int(e.onset // m.bar)
        if 0 <= b < nbars:
            out[b].append((e.onset - m.bar * b, e.duration, e.rest, e.tuplet))
    return [tuple(x) for x in out]


def onset_similarity(a: Sequence[tuple], b: Sequence[tuple]) -> float:
    """Jaccard similarity of two bars' note onsets (1.0 = same rhythm positions)."""
    sa = {x[0] for x in a if not x[2]}
    sb = {x[0] for x in b if not x[2]}
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


# --------------------------------------------------------------------------- coherence


def rhythm_coherence(events: Sequence[RhythmEvent], meter: str, *, style: str = "default") -> dict[str, Any]:
    """How motivic a phrase rhythm is (higher is better), with the evidence.

    Rewards a repeated cell, related bars (onset overlap), a long closing note; penalizes
    many unrelated bar rhythms, long notes in arbitrary mid-phrase places, and isolated
    syncopation outside syncopating styles. ``singable``: one hearing is enough to
    recognize and repeat the basic rhythmic idea.
    """
    m = parse_meter(meter)
    sigs = bar_signatures(events, meter)
    notes = [e for e in events if not e.rest]
    if not sigs or not notes:
        return {"total": 0.0, "singable": False}
    active = [i for i, s in enumerate(sigs[:-1]) if sum(1 for x in s if not x[2]) >= 2] or [0]
    cell = sigs[active[0]]
    same = sum(1 for i in active if sigs[i] == cell)
    related = sum(1 for i in active if sigs[i] != cell and onset_similarity(sigs[i], cell) >= 0.5)
    identity = (same + 0.7 * related) / len(active)
    distinct = len({sigs[i] for i in active})
    consecutive = [onset_similarity(sigs[a], sigs[b]) for a, b in zip(active, active[1:])]
    flow = sum(consecutive) / len(consecutive) if consecutive else 1.0
    # A long value needs a reason: phrase end, arrival on a barline, breath before a change.
    unmotivated = 0
    for i, e in enumerate(notes):
        if e.duration < 2 or i == len(notes) - 1:
            continue
        in_bar = e.onset % m.bar
        ends_bar = (e.onset + e.duration) % m.bar == 0
        if in_bar == 0 or ends_bar:
            continue
        unmotivated += 1
    sync_bars = [i for i, s in enumerate(sigs) if any(not x[2] and _crosses_beat(x[0], x[1], m.beat) for x in s)]
    isolated = 0
    if style not in SYNCOPATING_STYLES:
        isolated = sum(1 for i in sync_bars if sum(1 for j in sync_bars if sigs[j] == sigs[i]) == 1 and len(sigs) > 2)
    last = notes[-1].duration
    cadence = 1.5 if last >= 2 else (1.0 if last >= 1 else 0.0)
    parts = {
        "cell_identity": round(identity, 3),
        "flow": round(flow, 3),
        "distinct_bars": distinct,
        "variety_penalty": round(-0.6 * max(0, distinct - 2), 3),
        "unmotivated_long": unmotivated,
        "isolated_syncopation": isolated,
        "cadence": cadence,
    }
    total = 3.0 * identity + 1.5 * flow + parts["variety_penalty"] - 1.0 * unmotivated - 0.8 * isolated + cadence
    parts["total"] = round(total, 3)
    parts["singable"] = bool(identity >= 0.6 and distinct <= 2 and unmotivated == 0 and isolated == 0)
    return parts


# --------------------------------------------------------------------------- Change Rhythm


def motivic_candidates(
    bar_counts: Sequence[int],
    *,
    meter: str = "4/4",
    level: str = "Intermediate",
    style: str = "default",
    focus_pref: str = "neutral",
    downbeat_bars: Sequence[int] = (),
    seed: int = 0,
    limit: int = 16,
) -> list[RhythmRealization]:
    """Alternative rhythms for fixed per-bar note counts that stay motivic.

    Bars holding the same number of notes share one cell (repetition survives Change
    Rhythm); the last bar prefers a held closing value. Ranked by coherence, then style.
    """
    m = parse_meter(meter)
    counts = [int(c) for c in bar_counts]
    if not counts:
        return []
    pool = cell_pool(meter, level)
    need = {int(b) for b in downbeat_bars}
    per_count: dict[int, list[CellInfo]] = {}
    for c in sorted(set(counts)):
        opts = [x for x in pool if x.notes == c]
        if style in LYRICAL_STYLES:
            opts = [x for x in opts if x.kind not in ("syncopated", "sixteenth")] or opts
        if not opts:
            for bar in _top_bars(m.token, c, level, None, 0, False, 8):
                info = cell_info(bar.figures, meter)
                if info is not None and _opens_on_downbeat(bar):
                    opts.append(info)
        if not opts:
            return []
        opts.sort(key=lambda x: (-_kind_weight(x, style=style, focus_pref=focus_pref), x.figures))
        per_count[c] = opts
    last = len(counts) - 1
    out: list[RhythmRealization] = []
    seen: set = set()
    width = max(len(v) for v in per_count.values())
    for r in range(width * 2):
        choice = {c: per_count[c][(r + k) % len(per_count[c])] for k, c in enumerate(sorted(per_count))}
        bars: list[CellInfo] = [choice[c] for c in counts]
        final_opts = [x for x in per_count[counts[last]] if _ends_long(x)]
        if final_opts and not _ends_long(bars[last]):
            bars[last] = final_opts[r % len(final_opts)]
        brs = [bar_rhythm(b.figures, meter) for b in bars]
        if any(b is None for b in brs) or any(i in need and not _opens_on_downbeat(brs[i]) for i in range(len(brs))):  # type: ignore[arg-type]
            continue
        events: list[RhythmEvent] = []
        note = 0
        for i, br in enumerate(brs):
            evs, note = _bar_events(br, m.bar * i, note)  # type: ignore[arg-type]
            events.extend(evs)
        rid = f"motif:{m.token}:" + "/".join(b.id for b in brs)  # type: ignore[union-attr]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(realization_from_events(events, meter, rid=rid))
    scored = []
    for real in out:
        coh = rhythm_coherence(real.events, meter, style=style)["total"]
        tie = zlib.crc32(f"{real.id}|{seed}".encode())
        scored.append((-coh, tie, real))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in scored[:limit]]


def _ends_long(info: CellInfo) -> bool:
    bar = bar_rhythm(info.figures)
    if bar is None:
        return False
    evs, _ = _bar_events(bar, F(0), 0)
    notes = [e for e in evs if not e.rest]
    return bool(notes) and notes[-1].duration >= 1


# --------------------------------------------------------------------------- diminution

SPLITS: dict[Fraction, tuple[Fraction, Fraction]] = {
    F(4): (F(2), F(2)),
    F(3): (F(2), F(1)),
    F(2): (F(1), F(1)),
    F(3, 2): (F(1), F(1, 2)),
    F(1): (F(1, 2), F(1, 2)),
    F(1, 2): (F(1, 4), F(1, 4)),
}


def split_allowed(event: RhythmEvent, *, level: str, style: str) -> bool:
    if event.rest or event.tuplet or event.duration not in SPLITS:
        return False
    if event.duration == F(1, 2):
        return level == "Advanced" and style not in LYRICAL_STYLES and style not in ("pop", "rock", "folk")
    return True


def split_event(event: RhythmEvent) -> tuple[RhythmEvent, RhythmEvent]:
    d1, d2 = SPLITS[event.duration]
    first = RhythmEvent(onset=event.onset, duration=d1, written=d1, note=event.note)
    second = RhythmEvent(onset=event.onset + d1, duration=d2, written=d2, note=event.note)
    return first, second


def renumber(events: Sequence[RhythmEvent]) -> list[RhythmEvent]:
    out = []
    n = 0
    for e in events:
        if e.rest:
            out.append(RhythmEvent(e.onset, e.duration, e.written, True, e.tuplet, e.tuplet_start, None))
        else:
            out.append(RhythmEvent(e.onset, e.duration, e.written, False, e.tuplet, e.tuplet_start, n))
            n += 1
    return out


def shift_events(events: Sequence[RhythmEvent], offset: Fraction) -> list[RhythmEvent]:
    return [RhythmEvent(e.onset + offset, e.duration, e.written, e.rest, e.tuplet, e.tuplet_start, e.note) for e in events]


def cell_display(figures: Sequence[str], meter: str = "4/4") -> str:
    bar = bar_rhythm(figures, meter)
    if bar is None:
        return ""
    evs, _ = _bar_events(bar, F(0), 0)
    return display_rhythm(evs, meter)


__all__ = [
    "CELLS_44",
    "BarPlan",
    "CellInfo",
    "RhythmPlan",
    "bar_rhythm",
    "bar_signatures",
    "cadence_cell",
    "cell_display",
    "cell_info",
    "cell_pool",
    "choose_cell",
    "motivic_candidates",
    "onset_similarity",
    "plan_seed_rhythm",
    "realization_from_events",
    "rhythm_coherence",
    "split_allowed",
    "split_event",
    "vary_cell",
]

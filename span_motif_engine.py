"""MC2 — one connected motif across a harmonic span (2–3 contiguous chords).

Consumes an MC1 :class:`~harmonic_span_analyzer.HarmonicSpan` and returns a motif dict
the existing renderers already understand (``notes`` / ``midi`` / engine rhythm), plus
the harmony metadata that makes it a *span* motif: an explicit chord timeline, a chord
assignment for every note, the target note at each change, and the development
strategy that keeps one idea alive across the changes.

Pipeline (pure and deterministic for a given span / level / variant / seed):

1. **Timeline** — one slot per chord event, keeping its bar count from the chart.
2. **Targets** — one landing note per chord, chosen by a voice-leading cost over all
   chord tones in register (common tones, half/whole steps, 7→3 and leading-tone
   resolutions rewarded; leaps penalized), so the line moves smoothly between chords.
3. **Seed cell** — one short contour, realized on every chord from its target: in
   chord-tone space (Beginner arpeggio fragments) or chord-scale space (Intermediate /
   Advanced). The same cell on every chord is what keeps the idea recognizable.
4. **Connectors** — the last note(s) before each change lead into the next target: a
   diatonic step (Beginner), a chromatic approach or simple enclosure (Intermediate),
   enclosures / double chromatic / altered dominant tension that resolves by step
   (Advanced).
5. **Rhythm** — ``melodic_rhythm_engine.rhythm_candidates_by_bar`` with a fixed note
   count per bar, so every pitch stays inside its chord and each target lands on the
   new chord's downbeat.

Every chord tone, chord-scale tone and approach is judged against the chord it sounds
over — the chord/key data are authoritative; the MC1 relationship label only steers the
development strategy.
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

_LEVEL_CELLS: dict[str, tuple[tuple[int, ...], ...]] = {
    # Deltas in chord-tone space: arpeggio fragments the student can see.
    "Beginner": ((1, 1), (-1, -1), (1, -1), (-1, 1), (2, -1), (-2, 1)),
    # Deltas in chord-scale space.
    "Intermediate": ((1, 1, -1), (-1, -1, 1), (2, -1, -1), (-2, 1, 1), (1, -2, 1)),
    "Advanced": ((2, -1, -1, 2), (-1, -1, 3, -1), (1, 2, -1, -1), (-2, -1, 2, 2), (3, -1, -1, -1)),
}
# Build (developed exercise): notes per bar of every chord.
_NOTES_PER_BAR: dict[str, dict[str, int]] = {
    "Beginner": {"easier": 3, "normal": 4, "harder": 4},
    "Intermediate": {"easier": 4, "normal": 5, "harder": 6},
    "Advanced": {"easier": 5, "normal": 6, "harder": 7},
}
# Seed (the short idea): notes on each non-final chord — target, cell, connector.
_SEED_NOTES: dict[str, int] = {"Beginner": 3, "Intermediate": 3, "Advanced": 4}
_MAX_LEAP: dict[str, int] = {"Beginner": 7, "Intermediate": 9, "Advanced": 9}
_FUNCTIONAL = {
    "ii_V", "V_I", "ii_V_I", "ii_V_chain", "ii_subV", "ii_subV_I", "subV_I",
    "secondary_dominant", "dominant_chain", "dominant_resolution", "cadence",
}
_STABLE_ROLES = ("R", "3", "5")


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
            slots.append(
                ChordSlot(len(slots), ev.chord, bars, bar, bar * bar_len, (bar + bars) * bar_len)
            )
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


def _target_role_cost(role: str, level: str, strategy: str) -> float:
    if level == "Beginner" or strategy == "chord_tone_sequence":
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
    strategy: str,
    rng: random.Random,
    start_near: int = CENTER,
    start_weight: float = 0.06,
) -> list[tuple[int, str]]:
    """Minimum-cost landing note per chord (dynamic programming over chord tones)."""
    layers: list[list[tuple[int, str, float]]] = []
    for li, ctx in enumerate(contexts):
        cands = []
        arrival = li == len(contexts) - 1  # the last chord is where the line resolves
        for pc in ctx.chord_pcs:
            role = _role(ctx, pc)
            jitter = rng.uniform(0.0, 0.9 if level == "Beginner" else 0.5)
            settle = 0.9 if arrival and role not in ("R", "3") else 0.0
            for m in _in_register(pc):
                cands.append(
                    (m, role, _target_role_cost(role, level, strategy) + settle + jitter + 0.03 * abs(m - CENTER))
                )
        layers.append(cands)
    best: list[dict[int, tuple[float, int | None]]] = []
    first = {i: (c[2] + start_weight * abs(c[0] - start_near), None) for i, c in enumerate(layers[0])}
    best.append(first)
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


def _spell(ctx: Any, pc: int, *, below_target: bool | None = None) -> str:
    from music_theory import spell_pitch_class

    name = ctx.name_for_pc(pc)
    if name:
        return name
    if below_target is True:
        return spell_pitch_class(pc, mode="sharp")
    return spell_pitch_class(pc, mode="flat")


def _tension_collection(ctx: Any, next_ctx: Any | None) -> tuple[str, tuple[int, ...]] | None:
    """Advanced colour for a dominant that resolves: altered / diminished / lydian-dominant."""
    if ctx.quality != "dom" or next_ctx is None:
        return None
    root = ctx.chord_pcs[0]
    nxt = next_ctx.chord_pcs[0]
    if (nxt - root) % 12 == 5:  # V7 → I: altered scale (melodic minor a half step up)
        mm = ((root + 1) % 12,)
        steps = (0, 2, 3, 5, 7, 9, 11)
        return "altered", tuple((mm[0] + s) % 12 for s in steps)
    if (nxt - root) % 12 == 11:  # subV7 → I: lydian dominant (melodic minor a fifth up)
        steps = (0, 2, 3, 5, 7, 9, 11)
        return "lydian_dominant", tuple(((root + 7) % 12 + s) % 12 for s in steps)
    return None


def _diminished_collection(ctx: Any) -> tuple[int, ...]:
    root = ctx.chord_pcs[0]
    return tuple((root + s) % 12 for s in (0, 1, 3, 4, 6, 7, 9, 10))  # half-whole


@dataclass
class _Note:
    midi: int
    name: str
    role: str  # rhythm-engine role: target / guide_tone / chord_tone / scale / approach / neighbor / passing
    chord_index: int
    kind: str  # target / cell / connector / tension / ending


def _note(ctx: Any, midi: int, chord_index: int, kind: str, *, below_target: bool | None = None) -> _Note:
    pc = midi % 12
    if kind == "target":
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


def _repair_leaps(notes: list[_Note], contexts: Sequence[Any], limit: int) -> None:
    """Last line of defence against avoidable leaps: move a cell/ending note by an octave.

    Same pitch class, so the harmony and spelling are unchanged; targets (on the chord
    changes) and connectors (a step from the next target) are never moved.
    """
    for _ in range(3):
        changed = False
        for i, n in enumerate(notes):
            if n.kind not in ("cell", "ending"):
                continue
            prev = notes[i - 1].midi if i > 0 else None
            nxt = notes[i + 1].midi if i + 1 < len(notes) else None

            def worst(m: int) -> int:
                return max(abs(m - x) for x in (prev, nxt) if x is not None) if (prev, nxt) != (None, None) else 0

            if worst(n.midi) <= limit:
                continue
            options = [m for m in (n.midi - 12, n.midi + 12) if REGISTER[0] <= m <= REGISTER[1]]
            best = min(options, key=lambda m: (worst(m), m), default=None)
            if best is not None and worst(best) < worst(n.midi) and best != prev and best != nxt:
                notes[i] = _note(contexts[n.chord_index], best, n.chord_index, n.kind)
                changed = True
        if not changed:
            return


def _avoid_repeated_cell_notes(
    seg: list[_Note], before: int | None, ctx: Any, space: Sequence[int], chord_index: int
) -> None:
    """A cell note never restates its neighbour; targets and connectors are fixed."""
    for i, n in enumerate(seg):
        if n.kind not in ("cell", "tension"):
            continue
        prev = seg[i - 1].midi if i > 0 else before
        nxt = seg[i + 1].midi if i + 1 < len(seg) else None
        if n.midi != prev and n.midi != nxt:
            continue
        options = [_bounded_walk(n.midi, d, space) for d in (-1, 1)]
        options = [m for m in options if m not in (prev, nxt)]
        if options:
            ref = prev if prev is not None else n.midi
            seg[i] = _note(ctx, min(options, key=lambda m: (abs(m - ref), m)), chord_index, "cell")


def _connectors(
    prev: int,
    target: int,
    ctx: Any,
    *,
    level: str,
    tier: str,
    room: int,
    rng: random.Random,
    tension: tuple[str, tuple[int, ...]] | None,
) -> list[tuple[int, str, bool | None]]:
    """Notes (midi, kind, spelled-below) leading from the current chord into ``target``."""
    if room <= 0:
        return []
    scale = ctx.scale_pcs
    if level == "Beginner":
        # A current chord tone within a step of the next target, else a diatonic step.
        near = [m for pc in ctx.chord_pcs for m in _in_register(pc) if 1 <= abs(m - target) <= 2 and m != prev]
        if near:
            return [(min(near, key=lambda m: (abs(m - prev), m)), "connector", None)]
        step = [m for m in (_step(target, 1, scale), _step(target, -1, scale)) if m != target]
        return [(min(step, key=lambda m: (m == prev, abs(m - prev), m)), "connector", None)]
    from_above = prev > target
    if level == "Advanced" and tension is not None and room >= 1:
        # Altered colour that resolves by half/whole step into the target.
        pcs = tension[1]
        res = [m for pc in pcs for m in _in_register(pc) if 1 <= abs(m - target) <= 2 and m % 12 not in ctx.chord_pcs]
        if res:
            pick = min(res, key=lambda m: (abs(m - target), abs(m - prev), m))
            # Altered tones keep their altered (flat) spelling; only a half step below reads sharp.
            return [(pick, "tension", True if target - pick == 1 else None)]
    if room >= 2 and (level == "Advanced" or (level == "Intermediate" and tier == "harder")):
        if level == "Advanced" and rng.random() < 0.4:
            sign = 1 if from_above else -1
            return [(target + 2 * sign, "connector", sign < 0), (target + sign, "connector", sign < 0)]
        upper = _step(target, 1, scale)
        return [(upper, "connector", None), (target - 1, "connector", True)]  # enclosure
    if level == "Intermediate" and tier == "easier":
        step = _step(target, 1 if from_above else -1, scale)
        return [(step, "connector", None)]
    sign = 1 if from_above else -1
    return [(target + sign, "connector", sign < 0)]  # chromatic approach


def _choose_strategy(span: Any, level: str, vocabulary: str) -> str:
    voc = str(vocabulary or "auto").lower()
    if voc == "chord_tones" or level == "Beginner":
        return "vamp_restatement" if span.repeated_vamp else "chord_tone_sequence"
    if span.repeated_vamp:
        return "vamp_restatement"
    if voc == "guide_tones" or span.relationship in _FUNCTIONAL:
        return "guide_tone_arc"
    return "cell_sequence"


def _bar_counts(slots: Sequence[ChordSlot], *, level: str, tier: str, length: str, final_index: int) -> list[list[int]]:
    """Notes per bar for each slot. Seed: one cell per chord; Build: full density."""
    from melodic_rhythm_engine import max_notes_per_bar

    cap = max_notes_per_bar("4/4", level)
    per_bar = _NOTES_PER_BAR[level][tier]
    out = []
    for s in slots:
        last = s.index == final_index
        if length == "seed":
            first = 2 if last else _SEED_NOTES[level]
            counts = [first] + [1] * (s.bars - 1)
        else:
            counts = [per_bar] * s.bars
            if last:
                counts[-1] = 3 if level == "Advanced" else 2
                if s.bars > 1:
                    counts[-1] = 1  # settle on a long final note
        out.append([max(1, min(c, cap)) for c in counts])
    return out


def _stable_seed(*parts: Any) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


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
) -> dict[str, Any]:
    """One connected motif across ``span``.

    ``length``: ``seed`` (a short connected idea: one cell per chord), ``standard``
    (the developed exercise through the span) or ``extended`` (the span played twice,
    the second pass answering the first). ``plan``: a previous result's ``span_seed`` —
    Build develops *that* idea (same cell, same strategy) instead of a new one.
    """
    if length not in LENGTHS:
        raise ValueError(f"unknown span length: {length}")
    lvl = _level(level)
    tier = _tier(variant)
    if plan:
        seed_value = int(plan["seed"])
        cell = tuple(int(d) for d in plan["cell"])
        strategy = str(plan["strategy"])
    else:
        seed_value = int(seed) if seed is not None else _stable_seed(span.span_id, lvl, tier)
        rng0 = random.Random(seed_value)
        strategy = _choose_strategy(span, lvl, vocabulary)
        cells = _LEVEL_CELLS[lvl]
        cell = cells[rng0.randrange(len(cells))]
    rng = random.Random(seed_value + 7919)
    passes = 2 if length == "extended" else 1
    slots = chord_timeline(span, meter=meter, passes=passes)
    key = span.key_center
    contexts = [_ctx(key, s.chord) for s in slots]

    one_pass = len(span.raw_events)
    # Where the idea starts (low / middle / high) is part of the seed: New idea varies it.
    start_near = (60, 64, CENTER, 71, 74)[seed_value % 5]
    targets = choose_targets(contexts[:one_pass], level=lvl, strategy=strategy, rng=rng, start_near=start_near)
    if passes == 2 and strategy == "vamp_restatement":
        targets = targets + targets  # restated on purpose

    def _answer_targets(near: int) -> None:
        """Second-pass targets, voice-led from where the first pass actually ended up."""
        if len(targets) < len(slots):
            targets.extend(
                choose_targets(
                    contexts[one_pass:], level=lvl, strategy=strategy,
                    rng=random.Random(seed_value + 104729), start_near=near, start_weight=0.2,
                )
            )

    counts = _bar_counts(slots, level=lvl, tier=tier, length=length, final_index=len(slots) - 1)

    notes: list[_Note] = []
    vocab: set[str] = {"chord_tone"}
    slot_notes: list[list[_Note]] = []
    orientations: list[str] = []
    for si, slot in enumerate(slots):
        ctx = contexts[si]
        total = sum(counts[si])
        if strategy == "vamp_restatement" and si >= one_pass and si != len(slots) - 1:
            # The vamp's second pass restates the first one note for note.
            restated = [_Note(n.midi, n.name, n.role, si, n.kind) for n in slot_notes[si - one_pass]]
            slot_notes.append(restated)
            orientations.append(orientations[si - one_pass])
            notes.extend(restated)
            continue
        target_midi, _role_name = targets[si]
        seg: list[_Note] = [_note(ctx, target_midi, si, "target")]
        is_last = si == len(slots) - 1
        nxt_target = None if is_last or si + 1 >= len(targets) else targets[si + 1][0]
        nxt_ctx = None if is_last else contexts[si + 1]
        tension = _tension_collection(ctx, nxt_ctx) if lvl == "Advanced" and tier != "easier" else None
        base_cell = cell
        if passes == 2 and si >= one_pass and strategy != "vamp_restatement":
            base_cell = tuple(-d for d in cell)  # the answer turns the cell over
        space = ctx.chord_pcs if (lvl == "Beginner" or strategy == "chord_tone_sequence") else ctx.scale_pcs
        if is_last:
            body_len = total - 1
        else:
            body_len = max(0, total - 1 - (2 if total >= 4 and lvl != "Beginner" else 1 if total >= 2 else 0))

        def _realize(shape: tuple[int, ...]) -> tuple[list[tuple[int, str]], int]:
            """The cell walked from the target: (midi, kind) per body note, steps used."""
            out: list[tuple[int, str]] = []
            cur = target_midi
            k = 0
            while len(out) < body_len:
                delta = shape[k % len(shape)]
                k += 1
                prev_m = cur
                if tension is not None:
                    cur = _bounded_walk(cur, delta, tension[1])
                    kind = "tension" if cur % 12 not in ctx.chord_pcs and cur % 12 not in ctx.scale_pcs else "cell"
                else:
                    cur = _bounded_walk(cur, delta, space)
                    if abs(cur - prev_m) > _MAX_LEAP[lvl]:
                        cur = _bounded_walk(prev_m, -delta, space)  # turn the cell instead of leaping
                    kind = "cell"
                if cur == prev_m:
                    cur = _bounded_walk(cur, 1 if delta < 0 else -1, space)
                out.append((cur, kind))
            return out, k

        body, k = _realize(base_cell)
        pass_cell = base_cell
        orientation = "cell"
        if nxt_target is not None and body:
            mirrored = tuple(-d for d in base_cell)
            alt, alt_k = _realize(mirrored)
            # Head toward the next chord: the same cell turned over, never a leap at the change.
            if abs(alt[-1][0] - nxt_target) < abs(body[-1][0] - nxt_target):
                body, k, pass_cell, orientation = alt, alt_k, mirrored, "mirror"
        orientations.append(orientation)
        for midi, kind in body:
            if kind == "tension" and tension is not None:
                vocab.add(tension[0])
            seg.append(_note(ctx, midi, si, kind))
        if is_last:
            # Settle: the final note is a stable tone of the final chord, reached by step.
            if len(seg) > 1:
                prev = seg[-2].midi
                stable = [m for pc in ctx.chord_pcs if _role(ctx, pc) in _STABLE_ROLES for m in _in_register(pc)]

                def _settle(m: int) -> tuple:
                    d = abs(m - prev)
                    closeness = 2 if d == 0 else 0 if d <= 2 else 1 if d <= 4 else 3
                    return (closeness, _role(ctx, m) != "R", d, m)

                seg[-1] = _note(ctx, min(stable, key=_settle), si, "ending")
        else:
            if nxt_target is None:  # entering the answer pass: lead from the line's real position
                _answer_targets(seg[-1].midi)
                nxt_target = targets[si + 1][0]
            room = total - len(seg)
            conn = _connectors(seg[-1].midi, nxt_target, ctx, level=lvl, tier=tier, room=room, rng=rng, tension=tension)
            body_end = seg[-1].midi
            # Room the connectors leave free is filled by continuing the cell before them.
            fill: list[_Note] = []
            while len(seg) + len(fill) + len(conn) < total:
                body_end = _bounded_walk(body_end, pass_cell[(k + len(fill)) % len(pass_cell)], space)
                fill.append(_note(ctx, body_end, si, "cell"))
            seg.extend(fill)
            for ci, (m, kind, below) in enumerate(conn):
                if m == seg[-1].midi and len(conn) == 1 and abs(m - nxt_target) == 1:
                    # Never restate the previous pitch: half-step approach from the other side.
                    m = 2 * nxt_target - m
                    below = m < nxt_target
                if kind == "tension":
                    vocab.add(tension[0] if tension else "tension")
                seg.append(_note(ctx, m, si, kind, below_target=below))
                if kind == "connector" and m % 12 not in ctx.scale_pcs:
                    vocab.add("chromatic_approach")
            if len(conn) == 2:
                vocab.add("enclosure")
        seg = seg[:total]
        _avoid_repeated_cell_notes(seg, notes[-1].midi if notes else None, ctx, space, si)
        if lvl != "Beginner" and any(n.midi % 12 not in ctx.chord_pcs for n in seg):
            vocab.add("scale")
        slot_notes.append(seg)
        notes.extend(seg)

    _repair_leaps(notes, contexts, _MAX_LEAP[lvl])
    flat_counts = [c for slot_counts in counts for c in slot_counts]
    downbeats = [s.first_bar for s in slots]
    roles = [n.role for n in notes]
    motif = _assemble_motif(
        span, notes, slots, flat_counts, downbeats, roles, meter=meter, level=lvl, seed=seed_value,
    )
    motif.update(
        {
            "development_strategy": strategy,
            "vocabulary_used": sorted(vocab),
            "span_length": length,
            "level": lvl,
            "variant": tier,
            "span_seed": {"seed": seed_value, "cell": list(cell), "strategy": strategy, "level": lvl},
            "cell_orientations": orientations,
            "instrument": instrument,
            "transition_targets": [
                {
                    "chord_index": n.chord_index,
                    "note_index": i,
                    "midi": n.midi,
                    "name": n.name,
                    "role": _role(contexts[n.chord_index], n.midi % 12),
                }
                for i, n in enumerate(notes)
                if n.kind == "target"
            ],
            "note_kinds": [n.kind for n in notes],
        }
    )
    return motif


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
) -> dict[str, Any]:
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi
    from melodic_rhythm_engine import rhythm_candidates_by_bar

    cands = rhythm_candidates_by_bar(
        bar_counts, meter=meter, level=level, roles=list(roles), downbeat_bars=downbeats, seed=seed,
    )
    if not cands:
        raise ValueError(f"no rhythm fits bar counts {list(bar_counts)} at {level}")
    meta = {
        "meter": meter, "level": level, "group": 0, "seed": int(seed), "roles": list(roles),
        "bar_counts": list(bar_counts), "downbeat_bars": list(downbeats),
    }
    total_bars = sum(s.bars for s in slots)
    bar_symbols: list[str | None] = [None] * total_bars
    for s in slots:
        bar_symbols[s.first_bar] = s.chord
    first_note = []
    idx = 0
    starts = {s.first_bar: s for s in slots}
    bar_i = 0
    for slot in slots:
        first_note.append(idx)
        for _b in range(slot.bars):
            idx += bar_counts[bar_i]
            bar_i += 1
    del starts
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
        out.append(
            next(i for i, t in enumerate(timeline) if Fraction(t["start"]) <= onset < Fraction(t["end"]))
        )
    return out


def cycle_span_rhythm(motif: dict[str, Any]) -> dict[str, Any]:
    """Change Rhythm: the next per-bar candidate — pitches and chord assignment untouched."""
    from improvisation_motif import _engine_rhythm_fields, sync_motif_midi
    from melodic_rhythm_engine import next_rhythm_by_bar, rhythm_candidates_by_bar

    meta = dict(motif.get("rhythm_meta") or {})
    kw = dict(
        meter=str(meta.get("meter") or "4/4"),
        level=str(meta.get("level") or "Intermediate"),
        roles=list(meta.get("roles") or []) or None,
        downbeat_bars=list(meta.get("downbeat_bars") or []),
        seed=int(meta.get("seed") or 0),
    )
    counts = list(meta.get("bar_counts") or [])
    step = next_rhythm_by_bar(str(meta.get("id") or ""), counts, **kw)
    if step is None:
        return motif
    index, realization = step
    total = len(rhythm_candidates_by_bar(counts, **kw))
    out = dict(motif)
    out.update(_engine_rhythm_fields(realization, index=index, count=total, meta=meta))
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
    "LENGTHS",
    "build_span_exercise",
    "choose_targets",
    "chord_timeline",
    "cycle_span_rhythm",
    "generate_span_motif",
    "note_chord_assignment",
    "project_span_motif",
    "voice_leading_cost",
]

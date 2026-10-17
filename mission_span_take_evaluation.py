"""MC4 — Mission-specific evaluation of a recorded / uploaded take across a chord span.

performance transcription → span-assigned notes (mission_span_recording_alignment)
→ per-chord windows + per-change facts → Mission evaluator → evidence → feedback.

Rules that hold throughout:

* Harmony is evaluated in concert pitch (the microphone hears sounding pitch); note names in
  feedback use the player's chart (written key for transposing instruments).
* The generated example is *one* way to satisfy the Mission — a take is never graded as a
  transcription of it.
* Chord-by-chord statements are made only when the alignment is trusted (live take, user
  confirmed / adjusted, or a high-confidence detection). Otherwise the result is whole-span
  feedback plus an invitation to confirm the start.
* Timing is musical: a target may anticipate the change slightly or arrive a little late.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Callable, Sequence

from mission_span_recording_alignment import (
    Alignment,
    AssignedEvent,
    SpanGrid,
    assign_events,
    build_grid,
    coverage,
    events_in_loop,
)

UNALIGNED_MESSAGE = (
    "I can hear the notes and rhythm, but the first bar is not aligned confidently enough to grade each "
    "chord change. Confirm or adjust the detected start for chord-by-chord Mission feedback."
)

# How far (in beats) a target may sit from its chord change and still count.
_TOLERANCE = {
    "Beginner": {"early": 0.5, "late": 1.0},
    "Intermediate": {"early": 0.5, "late": 0.5},
    "Advanced": {"early": 0.5, "late": 0.4},
}
_LETTERS = "CDEFGAB"
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# Letter distance from the chord root for each degree_label role.
_ROLE_LETTER_STEPS = {
    "root": 0, "♭9": 1, "9th": 1, "♯9": 1, "3rd": 2, "major 3rd": 2, "4th": 3, "11th": 3, "♯11": 3,
    "♭5": 4, "5th": 4, "♯5": 4, "♭13": 5, "♭6": 5, "13th": 5, "6th": 5, "7th": 6, "♭7": 6, "major 7th": 6,
}
_STABLE_ON_ARRIVAL = {"root", "3rd", "5th", "6th", "9th", "7th", "major 7th", "13th"}


def _level(level: str) -> str:
    low = str(level or "").strip().lower()
    return "Beginner" if low.startswith("beg") else "Advanced" if low.startswith("adv") else "Intermediate"


# --------------------------------------------------------------------------- harmony / naming


@dataclass
class Harmony:
    """Concert chord frames for evaluation and chart frames for naming notes."""

    concert: list[Any]
    chart: list[Any]
    chart_chords: list[str]
    shift: int  # concert → chart semitones

    def role(self, pc: int, ci: int) -> str:
        from span_motif_explain import degree_label

        return degree_label(self.concert[ci], pc % 12)

    def name(self, pc: int, ci: int) -> str:
        from music_theory import spell_note_in_key
        from span_motif_explain import pretty

        wpc = (pc + self.shift) % 12
        by_degree = self._degree_spelling(wpc, self.role(pc, ci), ci)
        if by_degree:
            return by_degree
        ctx = self.chart[ci]
        n = ctx.name_for_pc(wpc) if ctx is not None else None
        return pretty(n or spell_note_in_key(wpc, getattr(ctx, "key", "C") or "C"))

    def _degree_spelling(self, wpc: int, role: str, ci: int) -> str:
        """Spell a note on the letter its chord degree implies (B♯ = 3rd of G♯7, not C)."""
        from span_motif_explain import _root_name

        steps = _ROLE_LETTER_STEPS.get(role)
        root = _root_name(self.chart_chords[ci]) if steps is not None else ""
        if not root or root[0].upper() not in _LETTERS:
            return ""
        letter = _LETTERS[(_LETTERS.index(root[0].upper()) + steps) % 7]
        acc = ((wpc - _NATURAL_PC[letter] + 6) % 12) - 6
        if abs(acc) > 1:
            return ""  # would need a double accidental — fall back to the key spelling
        return letter + ("♯" if acc == 1 else "♭" if acc == -1 else "")

    def neighbour_name(self, pc: int, target_pc: int, ci: int) -> str:
        """A step-away note spelled on the letter next to its target (D♯ → E, not E♭ → E)."""
        t_name = self.name(target_pc, ci)
        d = ((pc - target_pc + 6) % 12) - 6
        if not t_name or d == 0 or abs(d) > 2:
            return self.name(pc, ci)
        letters = "CDEFGAB"
        natural = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        letter = letters[(letters.index(t_name[0]) + (1 if d > 0 else -1)) % 7]
        acc = (((pc + self.shift) % 12 - natural[letter] + 6) % 12) - 6
        if abs(acc) > 1:
            return self.name(pc, ci)
        return letter + ("♯" if acc == 1 else "♭" if acc == -1 else "")

    def chord(self, ci: int) -> str:
        from span_motif_explain import pretty

        return pretty(self.chart_chords[ci])

    def third(self, ci: int) -> int | None:
        c = self.concert[ci]
        root = c.chord_pcs[0]
        for iv in (4, 3):
            if (root + iv) % 12 in c.chord_pcs:
                return (root + iv) % 12
        return None

    def seventh(self, ci: int) -> int | None:
        c = self.concert[ci]
        root = c.chord_pcs[0]
        for iv in (10, 11) + ((9,) if c.quality == "dim" else ()):
            if (root + iv) % 12 in c.chord_pcs:
                return (root + iv) % 12
        return None

    def guide(self, ci: int) -> set[int]:
        return {p for p in (self.third(ci), self.seventh(ci)) if p is not None}

    def is_chord_tone(self, pc: int, ci: int) -> bool:
        return pc % 12 in self.concert[ci].chord_pcs

    def in_scale(self, pc: int, ci: int) -> bool:
        return pc % 12 in self.concert[ci].scale_pcs


def build_harmony(block: dict[str, Any]) -> Harmony:
    from melodic_pattern_engine import build_context
    from music_theory import semitone_distance

    key = str(block.get("practice_key") or block.get("span_key_center") or "C")
    chart_key = str(block.get("chart_key") or key)
    timeline = list(block.get("timeline") or [])
    concert = [build_context(key, str(t.get("chord") or "")) for t in timeline]
    chart_chords = [str(t.get("chart_chord") or t.get("chord") or "") for t in timeline]
    try:
        chart = [build_context(chart_key, c) for c in chart_chords]
    except Exception:
        chart = list(concert)
    shift = int(semitone_distance(key, chart_key) or 0) % 12 if chart_key != key else 0
    return Harmony(concert, chart, chart_chords, shift)


# --------------------------------------------------------------------------- loop facts


@dataclass
class ChordWindow:
    index: int
    chord: str
    start_beat: float
    end_beat: float
    events: list[AssignedEvent] = field(default_factory=list)

    @property
    def beats(self) -> float:
        return self.end_beat - self.start_beat


@dataclass
class Change:
    index: int  # the arriving chord
    beat: float
    target: AssignedEvent | None = None
    target_offset: float | None = None  # beats from the change (negative = anticipation)
    before: list[AssignedEvent] = field(default_factory=list)  # notes leading into the target
    tail: list[AssignedEvent] = field(default_factory=list)  # last notes of the previous chord
    head: list[AssignedEvent] = field(default_factory=list)  # first notes of the arriving chord


@dataclass
class LoopFacts:
    loop: int
    windows: list[ChordWindow]
    changes: list[Change]
    events: list[AssignedEvent]
    covered: list[int]


def _loop_facts(
    events: Sequence[AssignedEvent], grid: SpanGrid, *, loop: int, level: str, covered: Sequence[int],
) -> LoopFacts:
    tol = _TOLERANCE[level]
    evs = sorted(events_in_loop(events, loop, pickup_beats=tol["early"]), key=lambda e: e.time)
    windows = [ChordWindow(s.index, s.chord, s.start_beat, s.end_beat) for s in grid.slots]
    for e in evs:
        if e.loop_index == loop:
            windows[e.chord_index].events.append(e)
    rel = lambda e: e.beat - loop * grid.loop_beats  # beat within this loop (pickups negative)  # noqa: E731
    changes: list[Change] = []
    for s in grid.slots:
        if s.index == 0:
            ch = Change(0, 0.0)
        else:
            ch = Change(s.index, s.start_beat)
        cands = [e for e in evs if -tol["early"] <= rel(e) - ch.beat <= tol["late"]]
        if cands:
            ch.target = min(cands, key=lambda e: abs(rel(e) - ch.beat))
            ch.target_offset = rel(ch.target) - ch.beat
            idx = evs.index(ch.target)
            ch.before = [e for e in evs[max(0, idx - 2):idx] if rel(ch.target) - rel(e) <= 2.0]
        if s.index > 0:
            prev = windows[s.index - 1]
            ch.tail = [e for e in prev.events if prev.end_beat - (rel(e)) <= 2.0][-3:]
            ch.head = [e for e in windows[s.index].events if rel(e) - s.start_beat <= 2.0][:3]
            if ch.target is not None and ch.target not in ch.head and ch.target.chord_index == s.index - 1:
                ch.head = [ch.target] + ch.head  # an anticipation belongs to the arriving chord
        changes.append(ch)
    return LoopFacts(loop, windows, changes, evs, list(covered))


# --------------------------------------------------------------------------- checks


@dataclass
class Check:
    where: str
    passed: bool
    text: str
    tip: str = ""
    weight: float = 1.0
    chord_specific: bool = True


def _timing_words(offset_beats: float | None, grid: SpanGrid) -> str:
    if offset_beats is None:
        return ""
    if abs(offset_beats) < 0.2:
        return "right on the change"
    unit = "an eighth note" if abs(offset_beats) <= 0.6 else f"about {abs(offset_beats):.1f} beats"
    return f"{unit} {'early (an anticipation)' if offset_beats < 0 else 'late'}"


def _preferred_roles(level: str) -> set[str]:
    if level == "Beginner":
        return {"root", "3rd", "5th"}
    if level == "Intermediate":
        return {"3rd", "7th", "major 7th"}
    return {"3rd", "7th", "major 7th", "9th", "♭9", "♯9", "♯11", "13th", "♭13", "6th", "5th"}


def _target_checks(f: LoopFacts, h: Harmony, grid: SpanGrid, level: str, *, require_role: set[str] | None = None) -> list[Check]:
    out = []
    roles = require_role or _preferred_roles(level)
    tol = _TOLERANCE[level]
    for ch in f.changes[1:]:
        if ch.index not in f.covered:
            continue
        where = f"{h.chord(ch.index - 1)} → {h.chord(ch.index)}"
        if ch.target is None:
            late = [e for e in f.windows[ch.index].events]
            if late:
                e = late[0]
                off = e.beats_since_change
                out.append(Check(where, False, f"No note landed on the change to {h.chord(ch.index)} — the first one arrived {_timing_words(off, grid)}.",
                                 tip=f"Land a {('/'.join(sorted(roles)))} of {h.chord(ch.index)} right on the change."))
            else:
                out.append(Check(where, False, f"Nothing was played on {h.chord(ch.index)}.", tip=f"Give {h.chord(ch.index)} at least one target note."))
            continue
        pc = ch.target.pc
        role = h.role(pc, ch.index)
        name = h.name(pc, ch.index)
        timing = _timing_words(ch.target_offset, grid)
        preferred = "3rd" if roles == {"3rd"} else ("root, 3rd or 5th" if level == "Beginner" else "3rd or 7th")
        if role in roles:
            out.append(Check(where, True, f"{name} (the {role} of {h.chord(ch.index)}) landed {timing}."))
        elif h.is_chord_tone(pc, ch.index):
            # A valid chord tone, just not the one this level is reaching for: partial credit.
            out.append(Check(where, True, f"{name} (the {role} of {h.chord(ch.index)}) landed {timing} — a chord tone.",
                             tip=f"Next time aim for the {preferred} of {h.chord(ch.index)} at the change.",
                             weight=0.5))
        else:
            out.append(Check(where, False, f"{name} on {h.chord(ch.index)} ({role}) isn't a stable target there.",
                             tip=f"Resolve onto the {preferred} of {h.chord(ch.index)} as it arrives."))
        if ch.target_offset is not None and ch.target_offset > tol["late"] * 0.6 and out[-1].passed:
            out[-1].tip = f"Your {h.chord(ch.index)} target arrived {timing}. Try landing directly on the change."
    return out


def _approach_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out = []
    for ch in f.changes[1:]:
        if ch.index not in f.covered:
            continue
        where = f"into {h.chord(ch.index)}"
        if ch.target is None or not ch.before:
            out.append(Check(where, False, f"No approach note led into {h.chord(ch.index)}.",
                             tip=f"Play one note a half or whole step away just before {h.chord(ch.index)}, then resolve."))
            continue
        t = ch.target
        if not h.is_chord_tone(t.pc, ch.index):
            out.append(Check(where, False, f"The approach resolved to {h.name(t.pc, ch.index)}, not a chord tone of {h.chord(ch.index)}.",
                             tip=f"Let the approach resolve to a chord tone of {h.chord(ch.index)}."))
            continue
        b = ch.before[-1]
        d = t.midi - b.midi
        double = len(ch.before) == 2 and level == "Advanced"
        if double:
            a = ch.before[0]
            da = t.midi - a.midi
            same_side = (da > 0) == (d > 0) and abs(d) == 1 and 1 <= abs(da) <= 2
            straddle = da * d < 0 and abs(da) <= 2 and abs(d) <= 2
            if same_side or straddle:
                kind = "double chromatic approach" if same_side else "two-note approach from both sides"
                out.append(Check(where, True, f"{h.neighbour_name(a.pc, t.pc, ch.index)}–{h.neighbour_name(b.pc, t.pc, ch.index)} → {h.name(t.pc, ch.index)} ({h.role(t.pc, ch.index)} of {h.chord(ch.index)}): {kind}."))
                continue
        if 1 <= abs(d) <= 2:
            kind = "chromatic" if abs(d) == 1 and not h.in_scale(b.pc, max(0, ch.index - 1)) else ("half-step" if abs(d) == 1 else "diatonic step")
            ok = abs(d) == 1 if level == "Intermediate" else True
            out.append(Check(where, ok, f"{h.neighbour_name(b.pc, t.pc, ch.index)} → {h.name(t.pc, ch.index)} ({h.role(t.pc, ch.index)} of {h.chord(ch.index)}): {kind} approach from {'below' if d > 0 else 'above'}.",
                             tip="" if ok else f"At your level, approach {h.chord(ch.index)}'s target by a half step."))
        else:
            out.append(Check(where, False, f"The note before {h.chord(ch.index)} was {abs(d)} semitones from the target — a leap, not an approach.",
                             tip=f"Approach {h.name(t.pc, ch.index)} from a half or whole step away."))
    return out


def _enclosure_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out = []
    for ch in f.changes[1:]:
        if ch.index not in f.covered:
            continue
        where = f"into {h.chord(ch.index)}"
        if ch.target is None or len(ch.before) < 2:
            out.append(Check(where, False, f"No enclosure led into {h.chord(ch.index)}.",
                             tip=f"Play a note above and a note below {h.chord(ch.index)}'s target, then land on it."))
            continue
        t = ch.target
        a, b = ch.before[-2], ch.before[-1]
        da, db = a.midi - t.midi, b.midi - t.midi
        valid_target = h.is_chord_tone(t.pc, ch.index)
        close = (t.beat - a.beat) <= 2.0 and (b.beat - a.beat) <= 1.2
        shape = da * db < 0 and 1 <= abs(da) <= 2 and 1 <= abs(db) <= 2
        if level != "Beginner":
            shape = shape and 1 in (abs(da), abs(db))
        if shape and valid_target and close:
            out.append(Check(where, True, f"{h.neighbour_name(a.pc, t.pc, ch.index)} and {h.neighbour_name(b.pc, t.pc, ch.index)} enclose {h.name(t.pc, ch.index)} (the {h.role(t.pc, ch.index)} of {h.chord(ch.index)})."))
        elif shape and not valid_target:
            out.append(Check(where, False, f"The enclosure surrounded {h.name(t.pc, ch.index)}, which isn't a chord tone of {h.chord(ch.index)}.",
                             tip=f"Enclose a chord tone of {h.chord(ch.index)} (its 3rd is a strong choice)."))
        else:
            out.append(Check(where, False, f"The two notes before {h.chord(ch.index)} didn't surround the target from above and below.",
                             tip=f"Try {h.neighbour_name((t.pc + 1) % 12, t.pc, ch.index)}–{h.neighbour_name((t.pc - 1) % 12, t.pc, ch.index)} → {h.name(t.pc, ch.index)}."))
    return out


def _guide_tone_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out = []
    for w in f.windows:
        if w.index not in f.covered:
            continue
        g = h.guide(w.index)
        used = sorted({e.pc for e in w.events if e.pc in g})
        if used:
            names = " and ".join(f"{h.name(p, w.index)} ({h.role(p, w.index)})" for p in used)
            out.append(Check(h.chord(w.index), True, f"{h.chord(w.index)}: you used {names}.", weight=0.6))
        elif w.events:
            out.append(Check(h.chord(w.index), False, f"{h.chord(w.index)}: no 3rd or 7th was heard.",
                             tip=f"Put the 3rd or 7th of {h.chord(w.index)} into your line.", weight=0.6))
    for ch in f.changes[1:]:
        if ch.index not in f.covered or not ch.head:
            continue
        # Any guide tone of the previous chord may carry over (later ones preferred), into a
        # guide tone near the start of the arriving chord — credit whichever path was played.
        a_g = [e for e in f.windows[ch.index - 1].events if e.pc in h.guide(ch.index - 1)]
        b_g = [e for e in ch.head if e.pc in h.guide(ch.index)]
        where = f"{h.chord(ch.index - 1)} → {h.chord(ch.index)}"
        if not a_g or not b_g:
            out.append(Check(where, False, f"{where}: the guide tones weren't connected across the change.",
                             tip=f"End {h.chord(ch.index - 1)} on its 3rd or 7th and move to the nearest guide tone of {h.chord(ch.index)}."))
            continue
        a, b = min(
            ((x, y) for x in a_g for y in b_g),
            key=lambda p: (abs(p[1].midi - p[0].midi) > 2, abs(p[1].midi - p[0].midi), -p[0].time),
        )
        ra, rb = h.role(a.pc, ch.index - 1), h.role(b.pc, ch.index)
        if a.pc == b.pc:
            out.append(Check(where, True, f"{where}: {h.name(a.pc, a.chord_index)} stayed common, changing from the {ra} to the {rb}."))
        elif abs(b.midi - a.midi) <= 2:
            direction = "down" if b.midi < a.midi else "up"
            strong = " — a strong 7th-to-3rd resolution" if ra in ("7th", "♭7") and rb == "3rd" else ""
            out.append(Check(where, True, f"{where}: {h.name(a.pc, a.chord_index)} moved {direction} to {h.name(b.pc, ch.index)}, the {rb} of {h.chord(ch.index)}{strong}."))
        else:
            out.append(Check(where, False, f"{where}: {h.name(a.pc, a.chord_index)} jumped {abs(b.midi - a.midi)} semitones to {h.name(b.pc, ch.index)}.",
                             tip=f"Move to the nearest guide tone of {h.chord(ch.index)} instead of leaping."))
    return out


def _common_tone_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out = []
    leap_limit = 9 if level == "Advanced" else 7
    for ch in f.changes[1:]:
        if ch.index not in f.covered or not ch.tail or not ch.head:
            continue
        where = f"{h.chord(ch.index - 1)} → {h.chord(ch.index)}"
        shared = set(h.concert[ch.index - 1].chord_pcs) & set(h.concert[ch.index].chord_pcs)
        kept = [e for e in ch.head if e.pc in shared and e.pc in {x.pc for x in ch.tail}]
        move = abs(ch.head[0].midi - ch.tail[-1].midi)
        if kept:
            p = kept[0].pc
            out.append(Check(where, True, f"{where}: {h.name(p, ch.index)} was kept as a common tone ({h.role(p, ch.index - 1)} → {h.role(p, ch.index)})."))
        elif move <= 2:
            out.append(Check(where, True, f"{where}: the line moved only {move} semitone{'s' if move != 1 else ''} across the change."))
        elif move > leap_limit:
            out.append(Check(where, False, f"{where}: a {move}-semitone leap across the change.",
                             tip=f"Keep a note both chords share{' (' + ', '.join(h.name(p, ch.index) for p in sorted(shared)) + ')' if shared else ''} or move to the nearest tone."))
        else:
            out.append(Check(where, False, f"{where}: no common tone was held ({move} semitones of movement).",
                             tip="Hold a shared note through the change, or move by a step.", weight=0.6))
    return out


def _chord_tone_checks(f: LoopFacts, h: Harmony, *, threshold: float = 0.6) -> list[Check]:
    out = []
    for w in f.windows:
        if w.index not in f.covered or not w.events:
            continue
        pct = sum(1 for e in w.events if h.is_chord_tone(e.pc, w.index)) / len(w.events)
        outside = [h.name(e.pc, w.index) for e in w.events if not h.is_chord_tone(e.pc, w.index)]
        if pct >= threshold:
            out.append(Check(h.chord(w.index), True, f"{h.chord(w.index)}: {round(pct * 100)}% of your notes were chord tones."))
        else:
            out.append(Check(h.chord(w.index), False, f"{h.chord(w.index)}: only {round(pct * 100)}% chord tones ({', '.join(dict.fromkeys(outside))} fell outside).",
                             tip=f"On {h.chord(w.index)} stay on {', '.join(h.name(p, w.index) for p in h.concert[w.index].chord_pcs)}."))
    return out


def _collection_checks(f: LoopFacts, h: Harmony, *, name: str, pcs_for: Callable[[int], set[int]], per_chord: bool) -> list[Check]:
    out = []
    evs = [e for e in f.events if e.loop_index == f.loop and e.chord_index in f.covered]
    if not evs:
        return out
    inside, approaches, outside = 0, [], []
    for i, e in enumerate(evs):
        pcs = pcs_for(e.chord_index)
        if e.pc in pcs:
            inside += 1
            continue
        nxt = evs[i + 1] if i + 1 < len(evs) else None
        if nxt and abs(nxt.midi - e.midi) == 1 and nxt.pc in pcs_for(nxt.chord_index) and nxt.beat - e.beat <= 1.0:
            approaches.append((e, nxt))
        else:
            outside.append(e)
    share = (inside + len(approaches)) / len(evs)
    label = name if not per_chord else "each chord's pentatonic"
    if share >= 0.8:
        out.append(Check("whole span", True, f"Most of your line stayed inside {label} ({round(share * 100)}%)."))
    else:
        out.append(Check("whole span", False, f"Only {round(share * 100)}% of your notes stayed inside {label}.",
                         tip=f"Keep to {label}; use outside notes only as half-step approaches."))
    for a, b in approaches[:2]:
        out.append(Check(h.chord(b.chord_index), True,
                         f"The {h.name(a.pc, a.chord_index)} before {h.name(b.pc, b.chord_index)} was a chromatic approach, so it doesn't count as leaving the exercise.",
                         weight=0.4))
    for e in outside[:2]:
        out.append(Check(h.chord(e.chord_index), False, f"{h.name(e.pc, e.chord_index)} on {h.chord(e.chord_index)} sits outside {label}.",
                         tip=f"Replace it with a neighbouring note from {label}.", weight=0.5))
    return out


def _rhythm_cells(f: LoopFacts, grid: SpanGrid) -> list[tuple[int, ...]]:
    """Onset positions (eighth-note grid) within each bar of the loop."""
    bars = int(round(grid.loop_beats / grid.pulses_per_bar))
    cells: list[set[int]] = [set() for _ in range(bars)]
    for e in f.events:
        if e.loop_index != f.loop:
            continue
        bar = int(e.beat_in_loop // grid.pulses_per_bar)
        if 0 <= bar < bars:
            pos = int(round((e.beat_in_loop - bar * grid.pulses_per_bar) * 2))
            if pos < grid.pulses_per_bar * 2:
                cells[bar].add(pos)
    return [tuple(sorted(c)) for c in cells]


def _rhythm_checks(f: LoopFacts, h: Harmony, grid: SpanGrid, level: str) -> list[Check]:
    out = []
    cells = [c for c in _rhythm_cells(f, grid)]
    played = [c for c in cells if c]
    evs = [e for e in f.events if e.loop_index == f.loop]
    if len(played) >= 2:
        ref = set(played[0])
        sims = [len(ref & set(c)) / len(ref | set(c)) for c in played[1:]]
        consistency = sum(sims) / len(sims)
        if consistency >= 0.6:
            out.append(Check("rhythm", True, f"You kept the same rhythmic cell through the changes ({round(consistency * 100)}% match bar to bar).", chord_specific=False))
        else:
            out.append(Check("rhythm", False, "The rhythm changed from bar to bar rather than repeating one cell.",
                             tip="Pick one short rhythm and repeat it in every bar.", chord_specific=False))
    if evs:
        devs = [abs(e.beat_in_loop * 2 - round(e.beat_in_loop * 2)) / 2 for e in evs]
        steady = sum(1 for d in devs if d <= 0.12) / len(devs)
        if steady >= 0.7:
            out.append(Check("timing", True, f"{round(steady * 100)}% of your onsets sat on the eighth-note grid.", chord_specific=False))
        else:
            out.append(Check("timing", False, f"Only {round(steady * 100)}% of your onsets sat on the eighth-note grid.",
                             tip="Play with the backing and place each note on a beat or half-beat.", chord_specific=False))
        gaps = [b.beat - (a.beat + a.duration / grid.pulse_sec) for a, b in zip(evs, evs[1:])]
        if any(g >= 0.9 for g in gaps) or len(played) < len(cells):
            out.append(Check("space", True, "You left space — rests are part of the rhythm.", weight=0.5, chord_specific=False))
        else:
            out.append(Check("space", False, "There were no rests.", tip="Leave at least one beat of space each bar.", weight=0.5, chord_specific=False))
    vocab = {e.pc for e in evs}
    if vocab and len(vocab) <= 5:
        out.append(Check("pitches", True, f"You kept the pitch choice simple ({len(vocab)} pitches), so the rhythm is the focus.", weight=0.4, chord_specific=False))
    return out


def _syncopation_checks(f: LoopFacts, h: Harmony, grid: SpanGrid) -> list[Check]:
    evs = [e for e in f.events if e.loop_index == f.loop]
    if not evs:
        return []
    off = [e for e in evs if abs(e.beat_in_loop - round(e.beat_in_loop)) >= 0.3]
    share = len(off) / len(evs)
    out = [Check("rhythm", share >= 0.3, f"{round(share * 100)}% of your notes started off the beat.",
                 tip="" if share >= 0.3 else "Start more notes on the 'and' of a beat.", chord_specific=False)]
    antic = [ch for ch in f.changes[1:] if ch.target_offset is not None and ch.target_offset < -0.2]
    if antic:
        out.append(Check(h.chord(antic[0].index), True, f"You anticipated {h.chord(antic[0].index)}, landing its target before the change."))
    return out


def _scalar_checks(f: LoopFacts) -> list[Check]:
    evs = [e for e in f.events if e.loop_index == f.loop]
    steps = [abs(b.midi - a.midi) for a, b in zip(evs, evs[1:])]
    if not steps:
        return []
    share = sum(1 for s in steps if 1 <= s <= 2) / len(steps)
    leaps = [s for s in steps if s > 4]
    return [Check("whole span", share >= 0.7, f"{round(share * 100)}% of your moves were steps.",
                  tip="" if share >= 0.7 else "Connect notes by step; save leaps for the start of a new run.",
                  chord_specific=False)] + (
        [Check("whole span", False, f"{len(leaps)} leap{'s' if len(leaps) != 1 else ''} broke the runs.", tip="Turn leaps into scale runs.", weight=0.5, chord_specific=False)]
        if len(leaps) > 1 else [])


def _bebop_checks(f: LoopFacts, h: Harmony, grid: SpanGrid) -> list[Check]:
    evs = [e for e in f.events if e.loop_index == f.loop]
    if len(evs) < 4:
        return [Check("whole span", False, "Too few notes for a bebop line.", tip="Keep a steady stream of eighth notes.", chord_specific=False)]
    iois = [b.beat - a.beat for a, b in zip(evs, evs[1:])]
    eighths = sum(1 for d in iois if 0.35 <= d <= 0.65) / len(iois)
    strong = [e for e in evs if abs(e.beat_in_loop - round(e.beat_in_loop)) < 0.2 and round(e.beat_in_loop) % 2 == 0]
    ct = sum(1 for e in strong if h.is_chord_tone(e.pc, e.chord_index)) / len(strong) if strong else 0.0
    chrom = sum(1 for a, b in zip(evs, evs[1:]) if abs(b.midi - a.midi) == 1 and not h.in_scale(a.pc, a.chord_index))
    return [
        Check("rhythm", eighths >= 0.6, f"{round(eighths * 100)}% of the line moved in eighth notes.",
              tip="" if eighths >= 0.6 else "Keep the line flowing in eighth notes.", chord_specific=False),
        Check("strong beats", ct >= 0.6, f"{round(ct * 100)}% of the notes on beats 1 and 3 were chord tones.",
              tip="" if ct >= 0.6 else "Put chord tones on the strong beats, passing tones between."),
        Check("colour", chrom > 0, "You used chromatic passing tones." if chrom else "No chromatic passing tones.",
              tip="" if chrom else "Add a chromatic passing note between two scale tones.", weight=0.5, chord_specific=False),
    ]


def _ii_v_i_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out: list[Check] = []
    n = len(f.windows)
    if n < 2:
        return out
    ii, v, i = (0, 1, 2) if n >= 3 else (None, 0, 1)
    if ii is not None and f.windows[ii].events and ii in f.covered:
        w = f.windows[ii]
        pct = sum(1 for e in w.events if h.is_chord_tone(e.pc, ii) or e.pc in h.guide(ii)) / len(w.events)
        out.append(Check(h.chord(ii), pct >= 0.5, f"{h.chord(ii)} set up the progression with {round(pct * 100)}% chord tones.",
                         tip="" if pct >= 0.5 else f"Outline {h.chord(ii)} clearly before the dominant."))
    if v in f.covered and f.windows[v].events:
        w = f.windows[v]
        g = [e for e in w.events if e.pc in h.guide(v)]
        tens = [e for e in w.events if h.role(e.pc, v) in ("♭9", "♯9", "♯11", "♭13")]
        if g or tens:
            pick = (g or tens)[0]
            out.append(Check(h.chord(v), True, f"{h.chord(v)} carried its tension: {h.name(pick.pc, v)} ({h.role(pick.pc, v)})."))
        else:
            out.append(Check(h.chord(v), False, f"{h.chord(v)} had no guide tone or dominant tension.",
                             tip=f"Use the 3rd or 7th of {h.chord(v)} so the resolution is felt."))
    if i in f.covered:
        ch = f.changes[i]
        if ch.target is not None:
            role = h.role(ch.target.pc, i)
            stable = role in _STABLE_ON_ARRIVAL and h.is_chord_tone(ch.target.pc, i) or role in ("9th", "6th", "13th")
            out.append(Check(f"{h.chord(v)} → {h.chord(i)}", stable,
                             f"{h.chord(i)} arrived on {h.name(ch.target.pc, i)}, the {role}." + ("" if stable else " That's not a resting tone."),
                             tip="" if stable else f"Resolve into {h.chord(i)} on its 3rd, 5th, 6th, 9th or root."))
        else:
            out.append(Check(f"{h.chord(v)} → {h.chord(i)}", False, f"No note marked the arrival of {h.chord(i)}.",
                             tip=f"Land on {h.chord(i)} right as it arrives."))
        last = f.windows[i].events[-1] if f.windows[i].events else None
        if last is not None:
            role = h.role(last.pc, i)
            ok = role in _STABLE_ON_ARRIVAL
            out.append(Check(h.chord(i), ok, f"The phrase ended on {h.name(last.pc, i)} ({role} of {h.chord(i)})" + (" — a convincing resolution." if ok else "."),
                             tip="" if ok else f"End the phrase on a stable tone of {h.chord(i)}.", weight=0.7))
    return out


def _dominant_tension_checks(f: LoopFacts, h: Harmony, level: str) -> list[Check]:
    out = []
    tension_roles = ("♭9", "♯9", "♯11", "♭13", "♭5")
    for w in f.windows[:-1]:
        if w.index not in f.covered or h.concert[w.index].quality not in ("dom", "aug"):
            continue
        tens = [e for e in w.events if h.role(e.pc, w.index) in tension_roles]
        where = f"{h.chord(w.index)} → {h.chord(w.index + 1)}"
        if not tens:
            out.append(Check(where, False, f"{h.chord(w.index)} stayed inside — no altered tension was heard.",
                             tip=f"Try the ♭9 ({h.name((h.concert[w.index].chord_pcs[0] + 1) % 12, w.index)}) or ♯9 on {h.chord(w.index)}."))
            continue
        t = tens[-1]
        later = [e for e in f.events if e.time > t.time]
        nxt = later[0] if later else None
        if nxt is None:
            out.append(Check(where, False, f"{h.name(t.pc, w.index)} ({h.role(t.pc, w.index)}) was left hanging.", tip="Resolve the tension by step."))
            continue
        ci = nxt.chord_index
        resolves = abs(nxt.midi - t.midi) <= 2 and h.is_chord_tone(nxt.pc, ci)
        if resolves:
            out.append(Check(where, True, f"{h.name(t.pc, w.index)} (the {h.role(t.pc, w.index)} of {h.chord(w.index)}) resolved to {h.name(nxt.pc, ci)}, the {h.role(nxt.pc, ci)} of {h.chord(ci)}."))
        else:
            out.append(Check(where, False, f"{h.name(t.pc, w.index)} ({h.role(t.pc, w.index)}) didn't resolve by step to a chord tone.",
                             tip=f"Follow the tension with a step into a chord tone of {h.chord(ci)}."))
    return out


def _motif_checks(f: LoopFacts, h: Harmony, grid: SpanGrid) -> list[Check]:
    wins = [w for w in f.windows if w.index in f.covered and len(w.events) >= 2]
    if len(wins) < 2:
        return [Check("motif", False, "There weren't enough notes on each chord to hear a motif carried through.",
                      tip="State a short idea on the first chord, then repeat its shape on the next.", chord_specific=False)]
    out = []

    def feats(w: ChordWindow) -> tuple[list[int], set[int], list[int]]:
        evs = w.events[:6]
        contour = [(1 if b.midi > a.midi else -1 if b.midi < a.midi else 0) for a, b in zip(evs, evs[1:])]
        rhythm = {int(round((e.beat_in_loop - w.start_beat) * 2)) for e in evs if e.beat_in_loop - w.start_beat < grid.pulses_per_bar}
        return contour, rhythm, [e.midi for e in evs]

    ref_c, ref_r, ref_m = feats(wins[0])
    for w in wins[1:]:
        c, r, m = feats(w)
        k = min(len(c), len(ref_c))
        contour_sim = sum(1 for a, b in zip(c[:k], ref_c[:k]) if a == b) / k if k else 0.0
        rhythm_sim = len(r & ref_r) / len(r | ref_r) if (r | ref_r) else 0.0
        same_rhythm, same_shape = rhythm_sim >= 0.6, contour_sim >= 0.65
        where = h.chord(w.index)
        evs = w.events[:6]
        clash = [e for e in evs if not (h.is_chord_tone(e.pc, w.index) or h.in_scale(e.pc, w.index))]
        if (same_rhythm or same_shape) and len(clash) / len(evs) > 0.4:
            outside = ", ".join(dict.fromkeys(h.name(e.pc, w.index) for e in clash))
            out.append(Check(where, False, f"{where} repeated the motif, but it didn't fit the chord ({outside} clashed).",
                             tip=f"Move the motif so its notes come from {where}."))
        elif same_rhythm and same_shape:
            adapted = "adapted to the chord" if m != ref_m[: len(m)] else "and it still fits the chord"
            out.append(Check(where, True, f"{where} kept your motif — same rhythmic cell and melodic shape, {adapted}."))
        elif same_rhythm:
            out.append(Check(where, True, f"{where} kept the same rhythmic cell, but the melodic shape changed substantially.",
                             tip="Keep the up/down shape of the motif too, moving it to fit the new chord.", weight=0.6))
        elif same_shape:
            out.append(Check(where, True, f"{where} kept the motif's shape but changed its rhythm.",
                             tip="Repeat the motif's rhythm as well as its shape.", weight=0.6))
        else:
            out.append(Check(where, False, f"{where} sounded like a new idea rather than the motif.",
                             tip=f"Restate the first chord's idea on {where}, transposed to fit."))
    return out


def _pentatonic_pcs(h: Harmony, ci: int) -> set[int]:
    c = h.concert[ci]
    root = c.chord_pcs[0]
    minorish = c.quality in ("minor", "m7", "half-dim", "dim")
    ivs = (0, 3, 5, 7, 10) if minorish else (0, 2, 4, 7, 9)
    return {(root + i) % 12 for i in ivs}


def _resolve_to_third(f: LoopFacts, h: Harmony, grid: SpanGrid, level: str) -> list[Check]:
    return _target_checks(f, h, grid, level, require_role={"3rd"})


_EVALUATORS: dict[str, Callable[..., list[Check]]] = {
    "guide_tone_voice_leading": lambda f, h, g, lvl, b: _guide_tone_checks(f, h, lvl),
    "target_each_change": lambda f, h, g, lvl, b: _target_checks(f, h, g, lvl),
    "motif_through_changes": lambda f, h, g, lvl, b: _motif_checks(f, h, g),
    "common_tone_voice_leading": lambda f, h, g, lvl, b: _common_tone_checks(f, h, lvl),
    "approach_next_chord": lambda f, h, g, lvl, b: _approach_checks(f, h, lvl),
    "enclose_next_target": lambda f, h, g, lvl, b: _enclosure_checks(f, h, lvl),
    "ii_v_i_resolution": lambda f, h, g, lvl, b: _ii_v_i_checks(f, h, lvl),
    "one_common_scale": lambda f, h, g, lvl, b: _collection_checks(
        f, h, name=str((b.get("common_collection") or {}).get("name") or "the common scale"),
        pcs_for=lambda ci: set((b.get("common_collection") or {}).get("pcs") or h.concert[ci].scale_pcs), per_chord=False),
    "dominant_tension_resolution": lambda f, h, g, lvl, b: _dominant_tension_checks(f, h, lvl),
    "chord_tones_each_chord": lambda f, h, g, lvl, b: _chord_tone_checks(f, h),
    "rhythm_over_notes": lambda f, h, g, lvl, b: _rhythm_checks(f, h, g, lvl),
    "scalar_runs": lambda f, h, g, lvl, b: _scalar_checks(f),
    "resolve_to_third": lambda f, h, g, lvl, b: _resolve_to_third(f, h, g, lvl),
    "bebop_line": lambda f, h, g, lvl, b: _bebop_checks(f, h, g),
    "pentatonic_per_chord": lambda f, h, g, lvl, b: _collection_checks(
        f, h, name="each chord's pentatonic", pcs_for=lambda ci: _pentatonic_pcs(h, ci), per_chord=True),
    "syncopated_phrase": lambda f, h, g, lvl, b: _syncopation_checks(f, h, g),
}


# --------------------------------------------------------------------------- per-chord detail


# Non-chord notes by chord quality, as semitones above the root.
# Stable colour / extension: colours the chord without obscuring it (9th and 13th over a dominant,
# 9th / 11th over minor, 9th / 6th / major 7th over a major triad, 11th over half-diminished …).
_STABLE = {
    "major": {2, 9, 11}, "maj7": {2, 9}, "dom": {2, 9}, "minor": {2, 5, 10}, "m7": {2, 5},
    "half-dim": {5}, "dim": {2, 5, 8, 11}, "sus": {2, 9, 10}, "aug": {2, 6, 10},
}
# Stable only when the chord's scale contains it (lydian ♯11, dorian 6, locrian ♮9, mixolydian ♭7);
# otherwise it is heard as a tension.
_STABLE_IF_IN_SCALE = {"major": {6, 10}, "maj7": {6}, "minor": {9}, "m7": {9}, "half-dim": {2}}
# Contextual tension / suspension: rubs against a chord-defining tone (the natural 11th a half step
# above a major 3rd, ♭6 / ♭13 a half step above the 5th, ♭9 above the root, altered dominant tones),
# so it depends on placement and resolution.
_TENSIONS = {
    "major": {5}, "maj7": {5}, "dom": {1, 3, 5, 6, 8}, "minor": {1, 8, 11}, "m7": {1, 8, 11},
    "half-dim": {1, 8}, "sus": {4},
}
_ALTERED_DOMINANT = {1, 3, 6, 8}  # ♭9 ♯9 ♯11 ♭13
_DETAIL_KINDS = ("chord", "colour", "tension", "passing", "outside")


def altered_language_ok(block: dict[str, Any], mission_id: str = "", level: str = "") -> bool:
    """Altered dominant tensions outside the chord scale count as tensions (not outside notes) when
    the Mission, level or style uses that language."""
    style = str(block.get("style") or "").lower()
    return (mission_id == "dominant_tension" or level == "Advanced"
            or any(s in style for s in ("jazz", "blues", "bossa", "swing", "fusion")))


def note_function(h: "Harmony", pc: int, ci: int, *, altered_ok: bool = False) -> str:
    """Harmonic category of one note against its chord: "chord", "colour" (stable extension),
    "tension" (contextual tension / suspension) or "other" (passing, approach or outside — decided
    by how the note is played, see _note_class)."""
    if h.is_chord_tone(pc, ci):
        return "chord"
    c = h.concert[ci]
    iv = (pc - c.chord_pcs[0]) % 12
    q = c.quality
    in_scale = h.in_scale(pc, ci)
    if iv in _STABLE.get(q, ()):
        return "colour"
    if iv in _STABLE_IF_IN_SCALE.get(q, ()):
        return "colour" if in_scale else "tension"
    if iv in _TENSIONS.get(q, ()) and (in_scale or (q == "dom" and iv in _ALTERED_DOMINANT and altered_ok)):
        return "tension"
    return "other"


def _is_strong(e: Any, grid: SpanGrid | None) -> bool:
    """On a strong beat (beat 1, or beat 3 of a four-beat bar) or right on the chord change."""
    if float(getattr(e, "beats_since_change", 1.0)) < 0.25:
        return True
    if grid is None:
        return False
    beat = float(e.beat_in_loop)
    if abs(beat - round(beat)) > 0.25:
        return False
    ppb = max(1, int(grid.pulses_per_bar))
    strong = {0, ppb // 2} if ppb >= 4 and ppb % 2 == 0 else {0}
    return int(round(beat)) % ppb in strong


def _beats(e: Any, grid: SpanGrid | None) -> float:
    if grid is None or not grid.pulse_sec:
        return 1.0
    return float(e.duration) / float(grid.pulse_sec)


def _note_class(h: "Harmony", e: Any, prev: Any, nxt: Any, grid: SpanGrid | None,
                altered_ok: bool = False) -> tuple[str, bool, bool]:
    """(class, resolved, clash) for one played note, from its harmony *and* how it was played.

    class: chord / colour / tension / passing / outside. A tension that is short, off the strong
    beats and both approached and left by step in one direction is a passing tone. resolved: a
    tension left by step into a chord tone or stable colour (e.g. B → A♯ over F♯7). clash: a
    tension on a strong beat, held a beat or longer, and not resolved by step.
    """
    base = note_function(h, e.pc, e.chord_index, altered_ok=altered_ok)
    if base in ("chord", "colour"):
        return base, False, False
    into = int(e.midi) - int(prev.midi) if prev is not None else 0
    out_of = int(nxt.midi) - int(e.midi) if nxt is not None else 0
    steps_out = 0 < abs(out_of) <= 2
    lands = nxt is not None and note_function(h, nxt.pc, nxt.chord_index, altered_ok=altered_ok) in ("chord", "colour")
    if base == "tension":
        strong = _is_strong(e, grid)
        if not strong and _beats(e, grid) <= 1.01 and 0 < abs(into) <= 2 and steps_out and (into > 0) == (out_of > 0):
            return "passing", False, False
        resolved = steps_out and lands
        clash = not resolved and strong and _beats(e, grid) >= 0.99
        return "tension", resolved, clash
    if h.in_scale(e.pc, e.chord_index) or (steps_out and lands):
        return "passing", False, False
    return "outside", False, False


def _tension_example(h: "Harmony", e: Any, resolved: bool) -> str:
    return f"{h.name(e.pc, e.chord_index)} ({h.role(e.pc, e.chord_index)}, {'resolved' if resolved else 'unresolved'})"


def _passing_or_outside(h: "Harmony", e: Any, nxt: Any) -> str:
    """Kept for callers of the earlier API: the class of a non-chord, non-colour note."""
    kind, _resolved, _clash = _note_class(h, e, None, nxt, None)
    return "passing" if kind == "tension" else kind


def _chord_detail(f: LoopFacts, h: Harmony, grid: SpanGrid | None = None, *, altered_ok: bool = False) -> list[dict[str, Any]]:
    out = []
    order = sorted(f.events, key=lambda e: e.time)
    following = {id(a): b for a, b in zip(order, order[1:])}
    preceding = {id(b): a for a, b in zip(order, order[1:])}
    for w in f.windows:
        evs = w.events
        n = len(evs)
        detail: dict[str, Any] = {"chord": h.chord(w.index), "covered": w.index in f.covered, "notes": n}
        if n:
            detail["chord_tone_pct"] = round(100 * sum(1 for e in evs if h.is_chord_tone(e.pc, w.index)) / n)
            detail["guide_tone_pct"] = round(100 * sum(1 for e in evs if e.pc in h.guide(w.index)) / n)
            detail["scale_fit_pct"] = round(100 * sum(1 for e in evs if h.in_scale(e.pc, w.index)) / n)
            detail["notes_per_beat"] = round(n / max(1.0, w.beats), 2)
            first, last = evs[0], evs[-1]
            detail["first_note"] = f"{h.name(first.pc, w.index)} ({h.role(first.pc, w.index)})"
            detail["last_note"] = f"{h.name(last.pc, w.index)} ({h.role(last.pc, w.index)})"
            detail["roles"] = sorted({h.role(e.pc, w.index) for e in evs})
            classes = [_note_class(h, e, preceding.get(id(e)), following.get(id(e)), grid, altered_ok) for e in evs]
            kinds = [k for k, _r, _c in classes]
            for kind, key in zip(_DETAIL_KINDS[1:], ("colour_tone_pct", "tension_pct", "passing_tone_pct", "outside_tone_pct")):
                detail[key] = round(100 * kinds.count(kind) / n)
            detail["other_tone_pct"] = detail["passing_tone_pct"] + detail["outside_tone_pct"]
            detail["tension_resolved"] = sum(1 for k, r, _c in classes if k == "tension" and r)
            detail["tension_clash_pct"] = round(100 * sum(1 for _k, _r, c in classes if c) / n)
            detail["colour_examples"] = list(dict.fromkeys(
                f"{h.name(e.pc, w.index)} ({h.role(e.pc, w.index)})" for e, k in zip(evs, kinds) if k == "colour"))[:3]
            detail["tension_examples"] = list(dict.fromkeys(
                _tension_example(h, e, r) for e, (k, r, _c) in zip(evs, classes) if k == "tension"))[:3]
            detail["tension_notes"] = [
                {"note": h.name(e.pc, w.index), "role": h.role(e.pc, w.index), "resolved": r, "clash": c,
                 "dominant_11th": h.concert[w.index].quality == "dom" and h.role(e.pc, w.index) == "11th",
                 "third": h.name(h.third(w.index), w.index) if h.third(w.index) is not None else ""}
                for e, (k, r, c) in zip(evs, classes) if k == "tension"
            ][:4]
        out.append(detail)
    return out


def _score(checks: Sequence[Check]) -> int | None:
    total = sum(c.weight for c in checks)
    if not total:
        return None
    return int(round(100 * sum(c.weight for c in checks if c.passed) / total))


# --------------------------------------------------------------------------- whole-span (unaligned)


def _general_feedback(notes: Sequence[dict[str, Any]], block: dict[str, Any], grid: SpanGrid) -> list[str]:
    from melodic_pattern_engine import build_context

    out = []
    if not notes:
        return ["No clear notes were detected — check the recording level or try a cleaner take."]
    key = str(block.get("practice_key") or "C")
    kctx = build_context(key)
    pcs = [int(round(float(n["midi"]))) % 12 for n in notes]
    inside = sum(1 for p in pcs if p in kctx.key_pcs) / len(pcs)
    span_pcs = set()
    for t in block.get("timeline") or []:
        span_pcs |= set(build_context(key, str(t.get("chord") or "")).chord_pcs)
    chordal = sum(1 for p in pcs if p in span_pcs) / len(pcs)
    lo, hi = min(int(n["midi"]) for n in notes), max(int(n["midi"]) for n in notes)
    out.append(f"I heard {len(notes)} notes across about {hi - lo} semitones of range.")
    out.append(f"{round(inside * 100)}% of them belong to the {block.get('practice_key')} key, and "
               f"{round(chordal * 100)}% are tones of one of the span's chords.")
    starts = [float(n["t"]) for n in notes]
    if len(starts) > 3:
        iois = [b - a for a, b in zip(starts, starts[1:])]
        med = median(iois)
        beats = med / grid.pulse_sec if grid.pulse_sec else 0
        out.append(f"Your typical note spacing was about {beats:.1f} beats at {grid.bpm} BPM.")
    return out


# --------------------------------------------------------------------------- entry point


def evaluate_span_take(
    block: dict[str, Any], transcription: dict[str, Any], alignment: Alignment | None, *,
    level: str | None = None, mission_id: str | None = None,
) -> dict[str, Any]:
    """Mission result for one take on a span (see module docstring for the rules)."""
    from mission_span_recording_context import span_chart_label

    lvl = _level(level or block.get("level") or "Intermediate")
    mid = str(mission_id or block.get("mission_id") or "")
    timeline = list(block.get("timeline") or [])
    grid = build_grid(timeline, bpm=int(block.get("bpm") or 100), meter=str(block.get("meter") or "4/4"))
    h = build_harmony(block)
    notes = list(transcription.get("notes") or [])
    headline = f"{block.get('mission_label') or mid} · {span_chart_label(dict(block, relationship_label=''))}"
    base = {
        "kind": "span_mission_take",
        "mission_id": mid,
        "mission_label": str(block.get("mission_label") or mid),
        "span_label": span_chart_label(block),
        "headline": headline,
        "practice_key": str(block.get("practice_key") or ""),
        "bpm": grid.bpm,
        "meter": grid.meter,
        "level": lvl,
        "notes_detected": len(notes),
        "alignment": alignment.to_dict() if alignment else None,
        "aligned": bool(alignment and alignment.trusted),
        "what_worked": [],
        "try_next": [],
        "chord_detail": [],
        "general": [],
        "score": None,
        "coverage": None,
        "loop_analyzed": None,
        "loop_scores": [],
        "message": "",
    }
    if not notes:
        base["message"] = "No clear notes were detected in this take, so the Mission couldn't be scored."
        base["general"] = _general_feedback(notes, block, grid)
        return base
    if alignment is None or not alignment.trusted:
        base["message"] = UNALIGNED_MESSAGE
        base["general"] = _general_feedback(notes, block, grid)
        return base

    events = assign_events(notes, grid, offset_sec=alignment.offset_sec)
    cov = coverage(float(transcription.get("duration") or 0.0), grid, offset_sec=alignment.offset_sec, events=events)
    base["coverage"] = cov.to_dict()
    if cov.status == "empty":
        base["message"] = cov.note
        base["general"] = _general_feedback(notes, block, grid)
        return base

    evaluator = _EVALUATORS.get(mid) or (lambda f, h_, g, l_, b: _chord_tone_checks(f, h_) + _target_checks(f, h_, g, l_))
    loops = list(range(cov.complete_loops)) if cov.complete_loops else [0]
    results = []
    for loop in loops:
        facts = _loop_facts(events, grid, loop=loop, level=lvl, covered=cov.covered_chords)
        if not facts.events:
            continue
        checks = evaluator(facts, h, grid, lvl, block)
        results.append((loop, facts, checks, _score(checks)))
    if not results:
        base["message"] = "No notes fell inside a complete pass of the span."
        base["general"] = _general_feedback(notes, block, grid)
        return base
    best = max(results, key=lambda r: (r[3] if r[3] is not None else -1, -r[0]))
    loop, facts, checks, score = best
    base["score"] = score
    base["loop_analyzed"] = loop + 1
    base["loop_scores"] = [{"loop": r[0] + 1, "score": r[3]} for r in results]
    base["what_worked"] = [c.text for c in checks if c.passed]
    base["try_next"] = [c.tip or c.text for c in checks if not c.passed] + [c.tip for c in checks if c.passed and c.tip]
    base["chord_detail"] = _chord_detail(facts, h, grid, altered_ok=altered_language_ok(block, mid, lvl))
    notes_out = []
    if cov.status == "short":
        total_bars = grid.loop_bars
        covered_bars = cov.covered_beats_last / grid.pulses_per_bar
        missing = ", ".join(h.chord(i) for i in cov.missing_chords)
        amount = (f"about {covered_bars:.0f}" if round(covered_bars) < round(total_bars) else "almost all")
        notes_out.append(
            f"This recording covers {amount} of the {total_bars:.0f} bars, so the "
            f"{missing} {'part wasn' if len(cov.missing_chords) == 1 else 'parts weren'}'t available to score."
            if missing else
            f"This recording covers {amount} of the {total_bars:.0f} bars — it ends during "
            f"{h.chord(max(cov.covered_chords))}, so only the part you played was scored."
        )
    if len(results) > 1:
        scores = " · ".join(str(r[3]) for r in results)
        notes_out.append(f"You played {len(results)} complete passes; pass {loop + 1} was your strongest and is the one analyzed (scores {scores}).")
    elif cov.status == "long":
        notes_out.append("The take runs past one pass of the span; the first complete pass was analyzed.")
    base["message"] = " ".join(notes_out)
    base["chord_timing_trusted"] = True
    return base


def mission_vs_chord_tone_note(result: dict[str, Any]) -> str:
    """Why Mission Compliance and the broader Chord-tone targeting score can differ (or "")."""
    if not isinstance(result, dict) or not result.get("aligned") or result.get("score") is None:
        return ""
    rows = [d for d in result.get("chord_detail") or [] if d.get("notes")]
    if not rows:
        return ""
    score = int(result["score"])
    lead = ("You satisfied the Mission at every required chord change. " if score >= 100
            else f"Mission Compliance is {score}% at the required chord changes. ")
    text = (lead + "Mission Compliance checks the target moments; the broader Chord-tone targeting score "
            "evaluates all notes played across the pass. Across the analyzed pass: "
            + " · ".join(f"{d['chord']} {d.get('chord_tone_pct', 0)}% chord tones" for d in rows) + ".")
    colours = [ex for d in rows for ex in d.get("colour_examples") or []]
    tensions = [_tension_phrase(d["chord"], t) for d in rows for t in d.get("tension_notes") or []]
    tensions = list(dict.fromkeys(tensions))[:2]
    if colours and tensions:
        text += (f" Some notes were stable colour tones ({', '.join(colours[:3])}), while others functioned as "
                 f"tensions that depended on resolution: {'; '.join(tensions)}.")
    elif colours:
        text += (f" Some other notes were stable colour tones ({', '.join(colours[:3])}) — valid in context, "
                 "though not counted as basic chord tones.")
    elif tensions:
        text += f" Some notes functioned as tensions that depended on resolution: {'; '.join(tensions)}."
    outside = any(d.get("outside_tone_pct") for d in rows)
    clash = any(d.get("tension_clash_pct") for d in rows)
    if outside or clash:
        what = " and ".join(x for x, on in (("Notes outside the harmony", outside),
                                            ("unresolved strong-beat clashes", clash)) if on)
        text += f" {what[0].upper()}{what[1:]} lower the broader score further."
    return text


def _tension_phrase(chord: str, t: dict[str, Any]) -> str:
    if t.get("dominant_11th"):
        against = f" ({t['third']})" if t.get("third") else ""
        return (f"{t['note']} over {chord} was an 11th suspension against the 3rd{against} — "
                + ("it resolved by step" if t.get("resolved") else "it works best when it resolves clearly"))
    return f"{t['note']} over {chord} ({t['role']}) " + ("resolved by step" if t.get("resolved") else "was left unresolved")


def span_note_shares(result: dict[str, Any]) -> dict[str, float]:
    """Note-weighted share (%) of chord / colour / passing / outside notes across the pass, plus the
    Mission Compliance score — evidence for proportional chord-tone coaching ({} if unaligned)."""
    if not isinstance(result, dict) or not result.get("aligned"):
        return {}
    rows = [d for d in result.get("chord_detail") or [] if d.get("notes")]
    total = sum(d["notes"] for d in rows)
    if not total:
        return {}
    out = {
        kind: round(sum(float(d.get(f"{key}_pct", 0) or 0) * d["notes"] for d in rows) / total, 1)
        for kind, key in (("chord", "chord_tone"), ("colour", "colour_tone"), ("tension", "tension"),
                          ("passing", "passing_tone"), ("outside", "outside_tone"), ("clash", "tension_clash"))
    }
    out["notes"] = float(total)
    if result.get("score") is not None:
        out["mission_score"] = float(result["score"])
    return out


def span_metric_overrides(result: dict[str, Any]) -> dict[str, float]:
    """Per-chord (not pooled) chord-tone / guide-tone scores for the existing metric cards."""
    if not result.get("aligned") or not result.get("chord_detail"):
        return {}
    rows = [r for r in result["chord_detail"] if r.get("notes")]
    if not rows:
        return {}
    total = sum(r["notes"] for r in rows)
    ct = sum(r.get("chord_tone_pct", 0) * r["notes"] for r in rows) / total
    gt = sum(r.get("guide_tone_pct", 0) * r["notes"] for r in rows) / total
    # Colour tones, passing notes and resolved tensions simply aren't basic chord tones; notes outside
    # the harmony and unresolved strong-beat clashes also cost half their share.
    unsupported = sum((r.get("outside_tone_pct", 0) + r.get("tension_clash_pct", 0)) * r["notes"] for r in rows) / total
    return {"chord_tone_accuracy": round(max(0.0, ct - 0.5 * unsupported), 1), "guide_tone_usage": round(gt, 1)}


__all__ = ["UNALIGNED_MESSAGE", "altered_language_ok", "build_harmony", "evaluate_span_take",
           "mission_vs_chord_tone_note", "note_function", "span_metric_overrides", "span_note_shares"]

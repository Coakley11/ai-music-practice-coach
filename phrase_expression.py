"""Practice Focus *Articulation* / *Dynamics* written into the notation itself (MC3.1).

The planner reads the line exactly as it is engraved — onsets, durations, rests and bars
come from the motif's own ABC, pitches from its MIDI — and returns per-note markings.
:func:`decorate_abc` then inserts ABC decorations (``!staccato!``, ``!accent!``,
``!tenuto!``, slurs, ``!mp!``, ``!crescendo(!`` …) in front of those notes. Pitches,
durations, bars and chord symbols are never touched, so the decorated ABC decodes to the
same MIDI as the plain one.

Articulation (winds offer this focus; the rules still read sensibly for other families):

- Beginner — one simple, repeated pattern: *slur two, tongue two*; held notes get tenuto.
- Intermediate — phrase-level contrast: one phrase slurred, the answer tongued staccato.
- Advanced — style-aware: swing tonguing (slur off-beat into on-beat, accent the
  syncopations, short "dat" before a rest) for jazz; arcs slurred to the high point with
  an accented peak elsewhere.

Dynamics: one musical contour per phrase, never random letters — Beginner a single
contrast (``mp`` … ``mf``), Intermediate an arc to the high point and back, Advanced an
arc per phrase with the overall peak strongest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence

ARTICULATION = "articulation"
DYNAMICS = "dynamics"

_JAZZ = {"jazz", "jazz_ballad", "bossa", "blues"}
_LYRICAL = {"ballad", "jazz_ballad", "folk"}
_DRIVING = {"pop", "rock", "funk"}

# Dynamic ranges per style: (soft, middle, loud).
_RANGES = {"lyrical": ("p", "mp", "mf"), "driving": ("mp", "mf", "f"), "default": ("mp", "mf", "f")}


def expression_kind(focus: str) -> str:
    """``articulation`` / ``dynamics`` when the Practice Focus is written into notation."""
    low = str(focus or "").strip().lower()
    if low == "articulation":
        return ARTICULATION
    if low == "dynamics":
        return DYNAMICS
    return ""


def instrument_family(instrument: str) -> str:
    low = str(instrument or "").lower()
    if any(w in low for w in ("sax", "flute", "clarinet", "trumpet", "trombone", "horn", "oboe", "wind")):
        return "wind"
    if "guitar" in low:
        return "guitar"
    if "piano" in low or "keys" in low:
        return "piano"
    if "bass" in low:
        return "bass"
    if "voice" in low or "vocal" in low:
        return "voice"
    return "other"


# --------------------------------------------------------------------------- ABC scan


@dataclass
class AbcNote:
    index: int  # motif note index (rests are not counted)
    start: int  # char offset in the body where the note token begins (accidental or letter)
    end: int  # char offset just after its length
    onset: Fraction
    duration: Fraction
    bar: int


@dataclass
class AbcScan:
    head: str
    body: str
    notes: list[AbcNote]
    rests: list[tuple[Fraction, Fraction]]
    bar_len: Fraction
    beat: Fraction


_NOTE = re.compile(r"(\^\^|__|\^|_|=)?([A-Ga-g])([,']*)(\d*)(/*)(\d*)")
_REST = re.compile(r"([zZ])(\d*)(/*)(\d*)")
_TUPLET_Q = {2: 3, 3: 2, 4: 3, 6: 2}


def _length(num: str, slashes: str, den: str) -> Fraction:
    n = Fraction(int(num)) if num else Fraction(1)
    if slashes:
        n /= int(den) if den else 2 ** len(slashes)
    return n


def _meter(head: str) -> tuple[Fraction, Fraction]:
    m = re.search(r"^M:\s*(\d+)/(\d+)", head, re.M)
    if not m:
        return Fraction(4), Fraction(1)
    top, bottom = int(m.group(1)), int(m.group(2))
    bar = Fraction(top * 4, bottom)
    beat = Fraction(3, 2) if bottom == 8 and top % 3 == 0 else Fraction(4, bottom)
    return bar, beat


def scan_abc(abc: str) -> AbcScan | None:
    """Notes of a one-voice ``L:1/4`` motif ABC with onsets; None for anything else."""
    lines = str(abc or "").splitlines()
    try:
        k = next(i for i, line in enumerate(lines) if line.startswith("K:"))
    except StopIteration:
        return None
    head = "\n".join(lines[: k + 1])
    if not re.search(r"^L:\s*1/4\s*$", head, re.M):
        return None
    body = "\n".join(lines[k + 1:])
    bar_len, beat = _meter(head)
    notes: list[AbcNote] = []
    rests: list[tuple[Fraction, Fraction]] = []
    onset = Fraction(0)
    tuplet_left, ratio = 0, Fraction(1)
    pos = 0
    while pos < len(body):
        ch = body[pos]
        if ch in " \t\n|:]":
            pos += 1
            continue
        if ch == '"':
            end = body.find('"', pos + 1)
            pos = len(body) if end < 0 else end + 1
            continue
        if ch == "!":
            end = body.find("!", pos + 1)
            pos = len(body) if end < 0 else end + 1
            continue
        if ch == "(":
            m = re.match(r"\((\d)", body[pos:])
            if m:
                p = int(m.group(1))
                tuplet_left, ratio = p, Fraction(_TUPLET_Q.get(p, 2), p)
                pos += 2
            else:
                pos += 1
            continue
        if ch in ")-.~":
            pos += 1
            continue
        m = _REST.match(body, pos)
        if m:
            dur = _length(m.group(2), m.group(3), m.group(4))
            if tuplet_left:
                dur *= ratio
                tuplet_left -= 1
            rests.append((onset, dur))
            onset += dur
            pos = m.end()
            continue
        m = _NOTE.match(body, pos)
        if m:
            dur = _length(m.group(4), m.group(5), m.group(6))
            if tuplet_left:
                dur *= ratio
                tuplet_left -= 1
            notes.append(AbcNote(len(notes), m.start(), m.end(), onset, dur, int(onset // bar_len)))
            onset += dur
            pos = m.end()
            continue
        return None  # an ABC construct this motif renderer never writes
    return AbcScan(head, body, notes, rests, bar_len, beat)


# --------------------------------------------------------------------------- markings


@dataclass
class Marks:
    deco: list[str] = field(default_factory=list)
    slur_open: bool = False
    slur_close: bool = False


@dataclass
class ExpressionPlan:
    kind: str
    marks: dict[int, Marks]
    summary: str
    phrases: list[list[int]]

    def decorations(self) -> dict[int, list[str]]:
        return {i: list(m.deco) for i, m in self.marks.items() if m.deco}

    def slurs(self) -> list[tuple[int, int]]:
        out, start = [], None
        for i in sorted(self.marks):
            m = self.marks[i]
            if m.slur_open:
                start = i
            if m.slur_close and start is not None:
                out.append((start, i))
                start = None
        return out


def _phrases(scan: AbcScan) -> list[list[int]]:
    """Notes grouped into phrases: a rest of a beat or more (or any rest at Beginner pace) splits."""
    groups: list[list[int]] = []
    cur: list[int] = []
    for n in scan.notes:
        if cur:
            prev = scan.notes[cur[-1]]
            gap = [r for r in scan.rests if prev.onset + prev.duration <= r[0] < n.onset]
            if gap and sum((d for _o, d in gap), Fraction(0)) >= Fraction(1, 2):
                groups.append(cur)
                cur = []
        cur.append(n.index)
    if cur:
        groups.append(cur)
    return groups


def _contiguous(scan: AbcScan, a: int, b: int) -> bool:
    """No rest between note a and note b."""
    na, nb = scan.notes[a], scan.notes[b]
    return not any(na.onset + na.duration <= r[0] < nb.onset for r in scan.rests)


def _style_bucket(style: str) -> str:
    s = str(style or "").lower()
    if s in _LYRICAL:
        return "lyrical"
    if s in _DRIVING:
        return "driving"
    return "default"


def _slur(marks: dict[int, Marks], scan: AbcScan, midis: Sequence[int], a: int, b: int) -> bool:
    """Slur a..b when legal: ≥2 notes, no rest inside, not a repeated pitch (would read as a tie), no overlap."""
    if b <= a or b >= len(scan.notes):
        return False
    if any(marks.get(i) and (marks[i].slur_open or marks[i].slur_close) for i in range(a, b + 1)):
        return False
    if any(not _contiguous(scan, i, i + 1) for i in range(a, b)):
        return False
    if b == a + 1 and midis[a] == midis[b]:
        return False
    marks.setdefault(a, Marks()).slur_open = True
    marks.setdefault(b, Marks()).slur_close = True
    return True


def _add(marks: dict[int, Marks], i: int, deco: str) -> None:
    m = marks.setdefault(i, Marks())
    if deco not in m.deco:
        m.deco.append(deco)


def _crosses_beat(n: AbcNote, beat: Fraction) -> bool:
    off = n.onset % beat
    return off != 0 and n.onset - off + beat < n.onset + n.duration


def _offbeat(n: AbcNote, beat: Fraction) -> bool:
    return n.onset % beat != 0


def plan_articulation(scan: AbcScan, midis: Sequence[int], *, level: str, instrument: str, style: str) -> ExpressionPlan:
    marks: dict[int, Marks] = {}
    phrases = _phrases(scan)
    fam = instrument_family(instrument)
    bucket = _style_bucket(style)
    jazz = str(style or "").lower() in _JAZZ
    beat = scan.beat
    notes = scan.notes
    held = "!tenuto!"
    detached = "!staccato!"
    if level == "Beginner":
        # Slur two, tongue two — the same pattern all the way through.
        for ph in phrases:
            i, pair = 0, 0
            while i < len(ph):
                a = ph[i]
                if notes[a].duration >= 2:
                    _add(marks, a, held)
                    i += 1
                    continue
                if pair % 2 == 0 and i + 1 < len(ph) and notes[ph[i + 1]].duration < 2 and _slur(marks, scan, midis, a, ph[i + 1]):
                    i += 2
                else:
                    for b in ph[i:i + 2]:
                        if notes[b].duration < 2:
                            _add(marks, b, held if bucket == "lyrical" else detached)
                    i += 2
                pair += 1
        summary = ("slur two notes, then tongue two — the same pattern throughout"
                   + ("; hold the long notes full value (tenuto)" if any(held in m.deco for m in marks.values()) else ""))
    elif level == "Intermediate":
        # Phrase-level contrast: legato phrase answered by a detached one.
        units = phrases if len(phrases) >= 2 else _halves(phrases[0] if phrases else [])
        for u_i, unit in enumerate(units):
            if not unit:
                continue
            legato = (u_i % 2 == 0) != (bucket == "driving")  # driving styles open detached
            if legato and len(unit) >= 2:
                if not _slur_runs(marks, scan, midis, unit, max_len=6):
                    for b in unit:
                        _add(marks, b, held)
            else:
                for b in unit:
                    if notes[b].duration < 2:
                        _add(marks, b, detached if bucket != "lyrical" else held)
                _add(marks, unit[0], "!accent!")
        last = notes[-1].index if notes else None
        if last is not None and not marks.get(last, Marks()).slur_close:
            _add(marks, last, held if notes[last].duration >= 1 else "!accent!")
        first_legato = (bucket != "driving")
        summary = ("first phrase slurred (legato), the answer tongued and detached" if first_legato
                   else "first phrase tongued and detached, the answer slurred (legato)")
    else:
        if jazz and fam in ("wind", "other", "voice"):
            # Swing tonguing: tongue the off-beat, slur it into the next on-beat note.
            slurred = synco = clipped = 0
            for ph in phrases:
                for x, y in zip(ph, ph[1:]):
                    if _offbeat(notes[x], beat) and not _offbeat(notes[y], beat) and notes[x].duration < beat:
                        slurred += _slur(marks, scan, midis, x, y)
                for b in ph:
                    if _crosses_beat(notes[b], beat):
                        _add(marks, b, "!accent!")
                        synco += 1
                tail = ph[-1]
                if notes[tail].duration < beat and tail != notes[-1].index:
                    _add(marks, tail, detached)  # the short "dat" before the breath
                    clipped += 1
            peak = max(range(len(midis)), key=lambda i: (midis[i], -i)) if midis else None
            if peak is not None:
                _add(marks, peak, "!accent!")
            bits = ["swing tonguing"]
            if slurred:
                bits.append("slur each off-beat into the next beat")
            bits.append("accent the syncopations and the top note" if synco else "accent the top note")
            if clipped:
                bits.append("clip the short note before each rest")
            summary = ": ".join([bits[0], ", ".join(bits[1:])])
        else:
            peak_mark = held if bucket == "lyrical" else "!accent!"
            for ph in phrases:
                if len(ph) < 2:
                    continue
                top = max(ph, key=lambda i: (midis[i], -i))
                if top > ph[0]:
                    _slur(marks, scan, midis, ph[0], top)
                _add(marks, top, peak_mark)
                rest = [b for b in ph if b > top]
                for b in rest:
                    if notes[b].duration < 2:
                        _add(marks, b, detached if bucket != "lyrical" else held)
                    else:
                        _add(marks, b, held)
            summary = ("slur each phrase up to its high point and lean on the peak (tenuto), then let the line fall away held"
                       if bucket == "lyrical" else
                       "slur each phrase up to its high point, accent the peak, then detach the notes that fall away")
    _clean_conflicts(marks)
    return ExpressionPlan(ARTICULATION, marks, summary, phrases)


def _halves(unit: list[int]) -> list[list[int]]:
    if len(unit) < 4:
        return [unit]
    mid = len(unit) // 2
    return [unit[:mid], unit[mid:]]


def _slur_runs(marks: dict[int, Marks], scan: AbcScan, midis: Sequence[int], unit: list[int], *, max_len: int) -> bool:
    """Slur ``unit`` in runs of at most ``max_len`` notes (rests already split phrases)."""
    done = False
    i = 0
    while i < len(unit) - 1:
        j = min(len(unit) - 1, i + max_len - 1)
        while j > i and not _slur_ok(scan, midis, unit[i], unit[j]):
            j -= 1
        if j > i and _slur(marks, scan, midis, unit[i], unit[j]):
            done = True
            i = j + 1
        else:
            i += 1
    return done


def _slur_ok(scan: AbcScan, midis: Sequence[int], a: int, b: int) -> bool:
    return b > a and all(_contiguous(scan, i, i + 1) for i in range(a, b)) and not (b == a + 1 and midis[a] == midis[b])


def _clean_conflicts(marks: dict[int, Marks]) -> None:
    """A note is never both staccato and tenuto; a slurred interior note is not staccato."""
    inside = set()
    start = None
    for i in sorted(marks):
        m = marks[i]
        if m.slur_open:
            start = i
        if m.slur_close and start is not None:
            inside.update(range(start + 1, i))
            start = None
    for i, m in marks.items():
        if "!staccato!" in m.deco and "!tenuto!" in m.deco:
            m.deco.remove("!staccato!")
        if i in inside and "!staccato!" in m.deco:
            m.deco.remove("!staccato!")


def plan_dynamics(scan: AbcScan, midis: Sequence[int], *, level: str, instrument: str, style: str) -> ExpressionPlan:
    marks: dict[int, Marks] = {}
    notes = scan.notes
    phrases = _phrases(scan)
    soft, mid, loud = _RANGES[_style_bucket(style)]
    if not notes:
        return ExpressionPlan(DYNAMICS, marks, "", phrases)
    n = len(notes)
    if level == "Beginner" or n < 4:
        # One clear contrast: start softly, answer louder from the halfway point.
        _add(marks, 0, f"!{soft if level == 'Beginner' else mid}!")
        total = notes[-1].onset + notes[-1].duration
        half = next((x.index for x in notes if x.onset >= total / 2 and x.index > 0), None)
        if half is not None and n >= 4:
            _add(marks, half, f"!{mid if soft != mid else loud}!")
            summary = f"start {soft}, then {mid if soft != mid else loud} from the middle of the phrase"
        else:
            summary = f"play the whole idea {soft if level == 'Beginner' else mid}"
        return ExpressionPlan(DYNAMICS, marks, summary, phrases)

    def arc(ph: list[int], *, start_dyn: str, peak_dyn: str, end_soft: bool) -> str:
        top = max(ph, key=lambda i: (midis[i], i))
        first, last = ph[0], ph[-1]
        _add(marks, first, f"!{start_dyn}!")
        parts = [start_dyn]
        if top - first >= 1:
            _add(marks, first + (1 if top - first >= 3 else 0), "!crescendo(!")
            _add(marks, top, "!crescendo)!")
            parts.append("crescendo")
        if top != first:
            _add(marks, top, f"!{peak_dyn}!")
            parts.append(f"{peak_dyn} at the top")
        if end_soft and last - top >= 2:
            _add(marks, top + 1, "!diminuendo(!")
            _add(marks, last, "!diminuendo)!")
            parts.append("diminuendo")
        return " → ".join(parts)

    if level == "Intermediate" or len(phrases) == 1:
        span_ph = [i for ph in phrases for i in ph]
        summary = arc(span_ph, start_dyn=soft, peak_dyn=mid if level == "Intermediate" else loud, end_soft=True)
    else:
        top_all = max(range(n), key=lambda i: (midis[i], i))
        bits = []
        for p_i, ph in enumerate(phrases):
            if len(ph) < 2:
                _add(marks, ph[0], f"!{soft}!")
                bits.append(soft)
                continue
            peak = loud if top_all in ph else mid
            bits.append(arc(ph, start_dyn=soft if p_i == 0 else mid if peak == loud else soft, peak_dyn=peak,
                            end_soft=True))
        summary = "; ".join(bits)
    _clean_dynamics(marks)
    return ExpressionPlan(DYNAMICS, marks, summary, phrases)


def _clean_dynamics(marks: dict[int, Marks]) -> None:
    """At most one dynamic letter per note (the later marking wins)."""
    letters = {"!p!", "!pp!", "!mp!", "!mf!", "!f!", "!ff!"}
    for m in marks.values():
        found = [d for d in m.deco if d in letters]
        for d in found[:-1]:
            m.deco.remove(d)


def plan_expression(
    abc: str, motif: dict[str, Any] | None, *, focus: str, level: str, instrument: str, style: str = "default",
) -> ExpressionPlan | None:
    kind = expression_kind(focus)
    if not kind:
        return None
    scan = scan_abc(abc)
    if scan is None or not scan.notes:
        return None
    midis = [int(m) for m in list((motif or {}).get("midi") or [])]
    if len(midis) != len(scan.notes):
        return None  # the engraved line is not this motif: never guess
    lvl = level if level in ("Beginner", "Intermediate", "Advanced") else "Intermediate"
    if kind == ARTICULATION:
        return plan_articulation(scan, midis, level=lvl, instrument=instrument, style=style)
    return plan_dynamics(scan, midis, level=lvl, instrument=instrument, style=style)


def decorate_abc(abc: str, plan: ExpressionPlan | None) -> str:
    """Insert the plan's markings in front of (and slur ends after) their notes."""
    if plan is None or not plan.marks:
        return abc
    scan = scan_abc(abc)
    if scan is None:
        return abc
    body = scan.body
    out: list[str] = []
    cursor = 0
    for note in scan.notes:
        m = plan.marks.get(note.index)
        if m is None:
            continue
        out.append(body[cursor:note.start])
        out.append(("(" if m.slur_open else "") + "".join(m.deco))
        out.append(body[note.start:note.end])
        if m.slur_close:
            out.append(")")
        cursor = note.end
    out.append(body[cursor:])
    return f"{scan.head}\n{''.join(out)}"


def apply_focus_expression(
    abc: str, motif: dict[str, Any] | None, *, focus: str, level: str, instrument: str, style: str = "default",
) -> tuple[str, ExpressionPlan | None]:
    """The notation the player sees: ``abc`` with the Practice Focus markings (or unchanged)."""
    plan = plan_expression(abc, motif, focus=focus, level=level, instrument=instrument, style=style)
    if plan is None or not plan.marks:
        return abc, None
    return decorate_abc(abc, plan), plan


def expression_caption(plan: ExpressionPlan | None) -> str:
    if plan is None or not plan.summary:
        return ""
    head = "Articulation" if plan.kind == ARTICULATION else "Dynamics"
    return f"**{head} in the notation:** {plan.summary}."


__all__ = [
    "ARTICULATION",
    "DYNAMICS",
    "ExpressionPlan",
    "apply_focus_expression",
    "decorate_abc",
    "expression_caption",
    "expression_kind",
    "plan_expression",
    "scan_abc",
]

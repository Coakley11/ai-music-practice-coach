"""Song-Aware Coaching (S1) — which bars of the song a coaching session works on.

Pure functions over a :class:`song_coach_context.SongCoachContext`:

- :func:`coach_sections` — the song's sections in chart order, with repeated blocks that
  share identical harmony grouped (``Verse 1``–``Verse 4`` → one *Verse*, 4 occurrences);
  a section whose harmony differs keeps its own entry.
- :func:`build_scope` — a section or a contiguous bar range inside it (1-based,
  section-relative bars, one chart entry = one bar) turned into:

  * the concert bar tokens exactly as charted;
  * a **harmonic timeline** (:class:`HarmonyEvent`): one event per chord change with its
    start and length in beats, so split bars (``C:2|G:2``), anticipations (``…|D:0.5p``)
    and ``N.C.`` bars keep their real timing;
  * a **span chain** (:class:`SpanLink`): the selection partitioned into consecutive
    1–3-chord windows, each carrying the MC1 :class:`~harmonic_span_analyzer.HarmonicSpan`
    analysis (relationship, Roman numerals, common tones) when the window is harmonic.

Nothing here generates notes or reads session state.
"""

from __future__ import annotations

import dataclasses

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from song_coach_context import SongCoachContext, is_no_chord

MAX_SCOPE_BARS = 16
DEFAULT_PHRASE_BARS = 8

ERROR_CONTEXT_UNAVAILABLE = "context_unavailable"
ERROR_UNKNOWN_SECTION = "unknown_section"
ERROR_BAD_RANGE = "bad_range"
ERROR_TOO_LONG = "range_too_long"
ERROR_NO_HARMONY = "no_harmony_in_range"


class ScopeError(ValueError):
    """An impossible selection; ``code`` is one of the ``ERROR_*`` ids."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CoachSection:
    section_id: str
    label: str
    names: tuple[str, ...]
    bars: tuple[str, ...]
    order_index: int

    @property
    def bar_count(self) -> int:
        return len(self.bars)

    @property
    def occurrences(self) -> int:
        return len(self.names)


@dataclass(frozen=True)
class HarmonyEvent:
    """One chord (or ``N.C.``) as it sounds in the selection."""

    chord: str  # theory symbol in concert pitch; "" for no chord
    start_beat: float  # from the first beat of the selection
    beats: float
    start_bar: int  # section-relative bar the event starts in (1-based)
    beat_in_bar: float  # 0 = on the bar line
    push: bool = False  # an anticipation charted before the bar line
    no_chord: bool = False

    @property
    def on_bar_line(self) -> bool:
        return self.beat_in_bar == 0


@dataclass(frozen=True)
class SpanLink:
    """A consecutive window of 1–3 chord events in the selection."""

    index: int
    first_event: int
    last_event: int
    chords: tuple[str, ...]
    start_bar: int
    end_bar: int
    span: Any = None  # HarmonicSpan for 2–3 chords; None for a single chord
    exact_bar_timing: bool = True  # every chord starts on a bar line and lasts whole bars

    @property
    def length(self) -> int:
        return len(self.chords)


@dataclass(frozen=True)
class HarmonicRhythm:
    changes: int
    distinct_chords: int
    beats_per_change: float
    has_split_bars: bool
    has_pushes: bool
    has_no_chord: bool
    cycle: tuple[str, ...]  # the repeating chord cell when the selection loops one, else ()


@dataclass(frozen=True)
class CoachScope:
    context_fingerprint: str
    section_id: str
    section_label: str
    start_bar: int
    end_bar: int
    section_bar_count: int
    bars: tuple[str, ...]
    meter: str
    beats_per_bar: float
    key_center: str
    events: tuple[HarmonyEvent, ...]
    chain: tuple[SpanLink, ...]
    rhythm: HarmonicRhythm
    scope_id: str = ""
    names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bar_count(self) -> int:
        return len(self.bars)

    @property
    def whole_section(self) -> bool:
        return self.start_bar == 1 and self.end_bar == self.section_bar_count

    @property
    def range_label(self) -> str:
        if self.whole_section:
            return f"{self.section_label} · {self.bar_count} bars"
        return f"{self.section_label} · bars {self.start_bar}–{self.end_bar}"

    def section_row(self) -> tuple[str, list[str], list[str]]:
        """``(label, display chords, raw bars)`` for the existing MC1 analyzer / chord map."""
        from improvisation_motif import single_progression_cycle

        raw = list(self.bars)
        return (self.section_label, single_progression_cycle(raw) or raw, raw)


# --------------------------------------------------------------------------- sections

_TRAILING_NUMBER = re.compile(r"\s+\d+$")


def _group_base(name: str) -> str:
    from improvisation_motif import _section_base_key

    return _section_base_key(_TRAILING_NUMBER.sub("", str(name).strip()))


def _group_label(name: str) -> str:
    from improvisation_motif import _display_section_label

    return _display_section_label(_TRAILING_NUMBER.sub("", str(name).strip()))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "section"


def coach_sections(ctx: SongCoachContext) -> list[CoachSection]:
    """Sections in chart order; repeats with identical bars are one entry."""
    if not ctx.available:
        return []
    groups: list[dict[str, Any]] = []
    by_sig: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for name, bars in ctx.sections:
        if not bars:
            continue
        sig = (_group_base(name), tuple(bars))
        group = by_sig.get(sig)
        if group is None:
            group = {"names": [name], "bars": tuple(bars), "base": sig[0]}
            by_sig[sig] = group
            groups.append(group)
        else:
            group["names"].append(name)
    base_counts: dict[str, int] = {}
    for g in groups:
        base_counts[g["base"]] = base_counts.get(g["base"], 0) + 1
    out: list[CoachSection] = []
    for i, g in enumerate(groups):
        first = g["names"][0]
        # A base shared by sections with different harmony keeps each section's own name.
        label = _group_label(first) if base_counts[g["base"]] == 1 else first
        out.append(
            CoachSection(
                section_id=_slug(first),
                label=label,
                names=tuple(g["names"]),
                bars=g["bars"],
                order_index=i,
            )
        )
    return out


def find_section(ctx: SongCoachContext, section_id: str) -> CoachSection | None:
    return next((s for s in coach_sections(ctx) if s.section_id == section_id), None)


def suggested_ranges(section: CoachSection, *, phrase_bars: int = DEFAULT_PHRASE_BARS) -> list[tuple[int, int]]:
    """Whole section when it is short; otherwise phrase-aligned chunks of ``phrase_bars``."""
    n = section.bar_count
    size = max(1, min(int(phrase_bars or DEFAULT_PHRASE_BARS), MAX_SCOPE_BARS))
    if n <= size:
        return [(1, n)] if n else []
    return [(start, min(start + size - 1, n)) for start in range(1, n + 1, size)]


# --------------------------------------------------------------------------- harmony


def _beats_per_bar(meter: str) -> float:
    from chord_events import beats_per_bar_from_signature

    try:
        beats = float(beats_per_bar_from_signature(meter or "4/4"))
    except Exception:
        beats = 4.0
    return beats if beats > 0 else 4.0


def _bar_parts(token: str, beats_per_bar: float) -> list[tuple[str, float, bool]]:
    """``(theory chord or "", beats, push)`` for each chord charted in one bar."""
    from chord_subdivisions import hit_underlying_chord, parse_subdivisions
    from music_theory import normalize_chord_for_theory

    parts = parse_subdivisions(str(token), beats_per_bar=beats_per_bar) or []
    out: list[tuple[str, float, bool]] = []
    for sub in parts:
        raw = hit_underlying_chord(str(sub.chord or "").strip())
        symbol = "" if is_no_chord(raw) else normalize_chord_for_theory(raw)
        if is_no_chord(symbol):
            symbol = ""
        out.append((symbol, float(sub.weight), bool(sub.push)))
    if not out:
        out.append(("", beats_per_bar, False))
    return out


def harmony_events(bars: Sequence[str], *, meter: str = "4/4", first_bar: int = 1) -> list[HarmonyEvent]:
    """Chord changes with exact beat timing; a held chord across bars is one event."""
    bpb = _beats_per_bar(meter)
    events: list[HarmonyEvent] = []
    for i, token in enumerate(bars):
        beat = 0.0
        for symbol, beats, push in _bar_parts(token, bpb):
            start = i * bpb + beat
            prev = events[-1] if events else None
            if prev is not None and prev.chord == symbol and prev.no_chord == (not symbol):
                events[-1] = HarmonyEvent(
                    prev.chord, prev.start_beat, prev.beats + beats, prev.start_bar,
                    prev.beat_in_bar, prev.push, prev.no_chord,
                )
            else:
                events.append(
                    HarmonyEvent(
                        chord=symbol,
                        start_beat=start,
                        beats=beats,
                        start_bar=first_bar + i,
                        beat_in_bar=beat,
                        push=push,
                        no_chord=not symbol,
                    )
                )
            beat += beats
    return events


def _event_end_bar(ev: HarmonyEvent, bpb: float, first_bar: int) -> int:
    end_beat = ev.start_beat + ev.beats
    return first_bar + max(0, int((end_beat - 1e-9) // bpb))


def _whole_bars(ev: HarmonyEvent, bpb: float) -> bool:
    return ev.on_bar_line and abs(ev.beats / bpb - round(ev.beats / bpb)) < 1e-9


# A window must earn its place: its MC1 score minus WINDOW_COST. A lone chord costs
# SINGLE_COST. So a strong 3-chord cadence (ii–V–I, ii–subV–I) stays one window, while
# ordinary diatonic changes pair up instead of forming a weak "mixed" triple.
WINDOW_COST = 50.0
SINGLE_COST = 20.0


def _windows(run: Sequence[int], chords: Sequence[str], lookup: dict[tuple[str, ...], Any]) -> list[list[int]]:
    """Partition consecutive event indices into 1–3-chord windows that follow the harmony."""
    n = len(run)
    if n == 0:
        return []

    def value(i: int, size: int) -> float:
        if size == 1:
            return -SINGLE_COST
        span = lookup.get(tuple(chords[run[k]] for k in range(i, i + size)))
        return float(getattr(span, "score", 0.0) or 0.0) - WINDOW_COST

    # best[i] = (total value, -window count, windows) for run[i:]; deterministic ties.
    best: list[tuple[float, int, list[list[int]]]] = [(0.0, 0, [])] * (n + 1)
    for i in range(n - 1, -1, -1):
        options = []
        for size in (2, 3, 1):
            if i + size <= n:
                total, count, rest = best[i + size]
                options.append((round(value(i, size) + total, 6), count - 1, [list(run[i : i + size])] + rest))
        best[i] = max(options, key=lambda o: (o[0], o[1]))
    return best[0][2]


def _mc1_raw(events: Sequence[HarmonyEvent], bpb: float) -> list[str]:
    raw: list[str] = []
    for ev in events:
        raw.extend([ev.chord or "N.C."] * max(1, int(round(ev.beats / bpb))))
    return raw


def _mc1_events(events: Sequence[HarmonyEvent], bpb: float) -> list[Any]:
    """MC1's view of ``events`` — one ``ChordEvent`` per harmony event (both merge repeats)."""
    from harmonic_span_analyzer import section_events

    return section_events(_mc1_raw(events, bpb))


def _anchored(span: Any, window: Sequence[int], mc1: Sequence[Any]) -> Any:
    """MC1 analyses each chord *sequence* once, at its first occurrence; a repeat of the same
    chords elsewhere (the second C7–F7 of a blues) must keep its own bar lengths, so the span
    is re-anchored on this window's own events."""
    if span is None or not window or window[-1] >= len(mc1):
        return span
    own = tuple(mc1[i] for i in window)
    if tuple(e.chord for e in own) != tuple(span.chords) or (own == tuple(span.raw_events) and span.start_event == window[0]):
        return span
    return dataclasses.replace(
        span,
        span_id=f"{span.progression_key}|s{span.section_index}|e{window[0]}-{window[-1]}",
        start_event=window[0],
        end_event=window[-1],
        raw_start=own[0].raw_index,
        raw_end=own[-1].raw_index + own[-1].bars - 1,
        raw_events=own,
        display_global_indices=tuple(e.raw_index for e in own),
    )


def _span_lookup(
    events: Sequence[HarmonyEvent], *, key_center: str, label: str, bpb: float, source_id: str
) -> dict[tuple[str, ...], Any]:
    """MC1 analysis of every 2- and 3-chord window, keyed by its chord sequence."""
    from harmonic_span_analyzer import analyze_harmonic_spans

    raw = _mc1_raw(events, bpb)
    rows = [(label, raw, raw)]
    found: dict[tuple[str, ...], Any] = {}
    for length in (2, 3):
        for span in analyze_harmonic_spans(
            rows, key_center=key_center, length=length, source_id=source_id, include_weak=True
        ):
            found.setdefault(tuple(span.chords), span)
    return found


def span_chain(
    events: Sequence[HarmonyEvent],
    *,
    key_center: str,
    meter: str = "4/4",
    first_bar: int = 1,
    label: str = "Selection",
    source_id: str = "",
) -> list[SpanLink]:
    """The selection as consecutive chord windows, ``N.C.`` bars breaking the chain."""
    bpb = _beats_per_bar(meter)
    lookup = _span_lookup(events, key_center=key_center, label=label, bpb=bpb, source_id=source_id)
    mc1 = _mc1_events(events, bpb)
    runs: list[list[int]] = [[]]
    for i, ev in enumerate(events):
        if ev.no_chord:
            if runs[-1]:
                runs.append([])
        else:
            runs[-1].append(i)
    links: list[SpanLink] = []
    symbols = [e.chord for e in events]
    for run in runs:
        for window in _windows(run, symbols, lookup):
            evs = [events[i] for i in window]
            chords = tuple(e.chord for e in evs)
            links.append(
                SpanLink(
                    index=len(links),
                    first_event=window[0],
                    last_event=window[-1],
                    chords=chords,
                    start_bar=evs[0].start_bar,
                    end_bar=_event_end_bar(evs[-1], bpb, first_bar),
                    span=_anchored(lookup.get(chords), window, mc1) if len(chords) >= 2 else None,
                    exact_bar_timing=all(_whole_bars(e, bpb) for e in evs),
                )
            )
    return links


def harmonic_rhythm(events: Sequence[HarmonyEvent], bars: Sequence[str]) -> HarmonicRhythm:
    from chord_subdivisions import has_push, is_subdivided_bar
    from improvisation_motif import single_progression_cycle

    chords = [e for e in events if not e.no_chord]
    symbols = [e.chord for e in chords]
    cycle = tuple(single_progression_cycle(symbols)) if symbols else ()
    loops = bool(cycle) and len(cycle) < len(symbols)
    return HarmonicRhythm(
        changes=len(chords),
        distinct_chords=len(set(symbols)),
        beats_per_change=round(sum(e.beats for e in chords) / len(chords), 3) if chords else 0.0,
        has_split_bars=any(is_subdivided_bar(b) for b in bars),
        has_pushes=any(has_push(b) for b in bars),
        has_no_chord=any(e.no_chord for e in events),
        cycle=cycle if loops else (),
    )


# --------------------------------------------------------------------------- scope


def build_scope(
    ctx: SongCoachContext,
    section_id: str,
    start_bar: int | None = None,
    end_bar: int | None = None,
) -> CoachScope:
    """A section (or bars ``start_bar``–``end_bar`` of it) ready for coaching."""
    if not ctx.available:
        raise ScopeError(ERROR_CONTEXT_UNAVAILABLE, ctx.unavailable_message or "No song to coach.")
    section = find_section(ctx, section_id)
    if section is None:
        raise ScopeError(ERROR_UNKNOWN_SECTION, f"No section {section_id!r} in this song.")
    n = section.bar_count
    start = 1 if start_bar is None else int(start_bar)
    end = n if end_bar is None else int(end_bar)
    if start < 1 or end > n or start > end:
        raise ScopeError(ERROR_BAD_RANGE, f"{section.label} has bars 1–{n}; {start}–{end} is not inside it.")
    if end - start + 1 > MAX_SCOPE_BARS:
        raise ScopeError(
            ERROR_TOO_LONG, f"Choose at most {MAX_SCOPE_BARS} bars at a time ({section.label} has {n})."
        )
    bars = section.bars[start - 1 : end]
    events = harmony_events(bars, meter=ctx.meter, first_bar=start)
    if not any(not e.no_chord for e in events):
        raise ScopeError(ERROR_NO_HARMONY, "These bars have no chords to improvise over.")
    chain = span_chain(
        events,
        key_center=ctx.concert_key,
        meter=ctx.meter,
        first_bar=start,
        label=section.label,
        source_id=_slug(ctx.identity),
    )
    return CoachScope(
        context_fingerprint=ctx.fingerprint,
        section_id=section.section_id,
        section_label=section.label,
        start_bar=start,
        end_bar=end,
        section_bar_count=n,
        bars=tuple(bars),
        meter=ctx.meter,
        beats_per_bar=_beats_per_bar(ctx.meter),
        key_center=ctx.concert_key,
        events=tuple(events),
        chain=tuple(chain),
        rhythm=harmonic_rhythm(events, bars),
        scope_id=f"{ctx.fingerprint}:{section.section_id}:{start}-{end}",
        names=section.names,
    )


__all__ = [
    "CoachScope",
    "CoachSection",
    "DEFAULT_PHRASE_BARS",
    "ERROR_BAD_RANGE",
    "ERROR_CONTEXT_UNAVAILABLE",
    "ERROR_NO_HARMONY",
    "ERROR_TOO_LONG",
    "ERROR_UNKNOWN_SECTION",
    "HarmonicRhythm",
    "HarmonyEvent",
    "MAX_SCOPE_BARS",
    "ScopeError",
    "SpanLink",
    "build_scope",
    "coach_sections",
    "find_section",
    "harmonic_rhythm",
    "harmony_events",
    "span_chain",
    "suggested_ranges",
]

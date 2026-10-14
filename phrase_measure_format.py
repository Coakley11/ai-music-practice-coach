"""Measure-aware note sequences: ``C – E – G – A | B♭ – A – G – F | E – D – C`` (MC3.3).

Bar lines come from the phrase's real rhythm — event onsets against the meter, or the
per-note rhythm symbols of older single-chord phrases (the same beat values the staff
uses) — or, failing both, from a chord timeline whose chords each fill whole single bars. Never from note count: a phrase whose measures cannot be known is shown without
bar lines. Tokens are shown exactly as given (written / concert spelling is the caller's),
and repeated notes stay repeated.
"""

from __future__ import annotations

import html
from fractions import Fraction
from typing import Any, Sequence

NOTE_SEP = " – "
BAR_SEP = " | "
EMPTY_MEASURE = "rest"


def _meter_token(motif: dict[str, Any]) -> str:
    meta = motif.get("rhythm_meta") if isinstance(motif.get("rhythm_meta"), dict) else {}
    return str(motif.get("meter") or meta.get("meter") or "4/4")


def _bars_from_events(motif: dict[str, Any], count: int) -> list[int] | None:
    try:
        from improvisation_motif import motif_rhythm_events
        from melodic_rhythm_engine import parse_meter
    except ImportError:  # pragma: no cover
        return None
    events = motif_rhythm_events(motif)
    if not events:
        return None
    bar_len = parse_meter(_meter_token(motif)).bar
    bars: list[int | None] = [None] * count
    for e in events:
        if e.rest or e.note is None or not 0 <= e.note < count:
            continue
        # A note belongs to the measure it starts in (a held note does not open a new bar).
        bars[e.note] = int(Fraction(e.onset) // bar_len)
    if any(b is None for b in bars):
        return None
    return [int(b) for b in bars]  # type: ignore[arg-type]


def _bars_from_symbols(motif: dict[str, Any], count: int) -> list[int] | None:
    """Legacy one-symbol-per-note rhythm (♩ ♪ ♩. …), read with the same beat values the staff uses."""
    symbols = motif.get("rhythm_symbols")
    if not isinstance(symbols, list) or not symbols:
        return None
    try:
        from improvisation_motif import _RHYTHM_BEATS
        from melodic_rhythm_engine import parse_meter
    except ImportError:  # pragma: no cover
        return None
    bar_len = parse_meter(_meter_token(motif)).bar
    bars: list[int] = []
    pos = Fraction(0)
    for sym in symbols:
        beats = _RHYTHM_BEATS.get(str(sym).strip())
        if beats is None:
            return None
        if str(sym).strip() not in ("z", "Z"):
            bars.append(int(pos // bar_len))
        pos += Fraction(beats).limit_denominator(16)
    return bars if len(bars) == count else None


def _bars_from_timeline(motif: dict[str, Any], count: int) -> list[int] | None:
    timeline = motif.get("chord_timeline")
    if not isinstance(timeline, list) or not timeline:
        return None
    bars: list[int | None] = [None] * count
    for slot in timeline:
        try:
            lo, hi = int(slot["first_note"]), int(slot["last_note"])
            first_bar, span = int(slot["first_bar"]), int(slot.get("bars", 1))
        except (KeyError, TypeError, ValueError):
            return None
        if span != 1:
            return None  # a chord held over several bars: its notes' bars are unknown
        for k in range(lo, hi + 1):
            if 0 <= k < count:
                bars[k] = first_bar
    if any(b is None for b in bars):
        return None
    return [int(b) for b in bars]  # type: ignore[arg-type]


def phrase_note_measures(motif: dict[str, Any], count: int | None = None) -> list[int] | None:
    """Measure index of each note (0-based from the phrase's first bar), or None if unknown."""
    if not isinstance(motif, dict):
        return None
    n = len(list(motif.get("notes") or [])) if count is None else int(count)
    if n <= 0:
        return None
    bars = _bars_from_events(motif, n) or _bars_from_symbols(motif, n) or _bars_from_timeline(motif, n)
    if not bars:
        return None
    first = min(bars)
    bars = [b - first for b in bars]
    if any(b2 < b1 for b1, b2 in zip(bars, bars[1:])):
        return None
    return bars


def phrase_measure_groups(motif: dict[str, Any], tokens: Sequence[str] | None = None) -> list[list[str]] | None:
    """Tokens grouped by real measure; an all-rest measure inside the phrase is an empty group."""
    toks = [str(t) for t in (tokens if tokens is not None else (motif or {}).get("notes") or [])]
    bars = phrase_note_measures(motif, len(toks))
    if not bars:
        return None
    groups: list[list[str]] = [[] for _ in range(bars[-1] + 1)]
    for tok, bar in zip(toks, bars):
        groups[bar].append(tok)
    return groups


def display_tokens(motif: dict[str, Any]) -> list[str]:
    """The phrase's notes as displayed (``display`` keeps written-key spelling when it matches)."""
    notes = [str(n) for n in (motif or {}).get("notes") or []]
    shown = [t.strip() for t in str((motif or {}).get("display") or "").split(NOTE_SEP)]
    return shown if notes and len(shown) == len(notes) and all(shown) else notes


def format_phrase_notes_by_measure(motif: dict[str, Any], tokens: Sequence[str] | None = None) -> str:
    """``C – E – G | A – G`` with bars at the real measure boundaries (plain join if unknown)."""
    toks = [str(t) for t in (tokens if tokens is not None else display_tokens(motif))]
    groups = phrase_measure_groups(motif, toks)
    if not groups:
        return NOTE_SEP.join(toks)
    return BAR_SEP.join(NOTE_SEP.join(g) if g else EMPTY_MEASURE for g in groups)


def phrase_notes_html(motif: dict[str, Any], tokens: Sequence[str] | None = None) -> str:
    """Same text as HTML; each measure stays on one line when the sequence wraps on a phone."""
    toks = [str(t) for t in (tokens if tokens is not None else display_tokens(motif))]
    groups = phrase_measure_groups(motif, toks) or [toks]
    cells = [
        f'<span class="mc-measure" style="white-space:nowrap">{html.escape(NOTE_SEP.join(g) if g else EMPTY_MEASURE)}</span>'
        for g in groups
    ]
    return (
        '<code class="mc-phrase-notes" style="white-space:normal;word-break:normal">'
        + html.escape(BAR_SEP).join(cells)
        + "</code>"
    )


__all__ = [
    "display_tokens",
    "format_phrase_notes_by_measure",
    "phrase_measure_groups",
    "phrase_note_measures",
    "phrase_notes_html",
]

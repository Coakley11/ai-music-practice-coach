"""Beat-level chord subdivisions inside a single bar.

A subdivided bar is represented as a single chord token where each beat-level
chord is separated by a pipe ``|``. For example::

    "Fmaj7|Am7|C/D"

means **one bar** containing three quick chords (one chord per beat in 3/4,
or evenly subdivided across whatever meter the song is in). The pipe
separator does not appear in plain chord symbols, so this is safe to add
without changing the existing one-chord-per-bar convention.

This module is the single source of truth for:

* Detecting a subdivided bar token.
* Splitting it back into its sub-chords.
* Mapping a pulse/beat position inside the bar to the active sub-chord.
* Picking a primary/head chord when a single chord is required (Roman-numeral
  analysis, summary labels, etc.).
* Producing a pretty display label such as ``"Fmaj7 -> Am7 -> C/D"``.

All consumer modules (backing audio, lead-sheet rendering, chord-follow
timeline, harmony analysis) call into these helpers instead of duplicating
the parsing logic.
"""

from __future__ import annotations

from typing import Iterable

SUBDIVISION_SEPARATOR = "|"

__all__ = [
    "SUBDIVISION_SEPARATOR",
    "is_subdivided_bar",
    "subdivisions",
    "subdivision_count",
    "primary_chord",
    "display_label",
    "chord_at_pulse",
    "next_chord_at_pulse",
    "expand_chord_list",
    "join_subdivisions",
]


def is_subdivided_bar(token: object) -> bool:
    """Return True if ``token`` represents a subdivided bar (contains ``|``)."""
    s = str(token or "")
    if SUBDIVISION_SEPARATOR not in s:
        return False
    parts = [p.strip() for p in s.split(SUBDIVISION_SEPARATOR) if p.strip()]
    return len(parts) >= 2


def subdivisions(token: object) -> list[str]:
    """Return the list of sub-chords inside a bar.

    For a non-subdivided token, returns a single-element list with the token
    itself (after stripping whitespace).
    """
    s = str(token or "").strip()
    if not s:
        return []
    if SUBDIVISION_SEPARATOR not in s:
        return [s]
    return [p.strip() for p in s.split(SUBDIVISION_SEPARATOR) if p.strip()]


def subdivision_count(token: object) -> int:
    parts = subdivisions(token)
    return max(1, len(parts))


def primary_chord(token: object) -> str:
    """Return the first (head) chord of a subdivided bar, or the token itself."""
    parts = subdivisions(token)
    return parts[0] if parts else ""


def display_label(token: object, sep: str = " \u2192 ") -> str:
    """Pretty inline label for chart cells / status text.

    Default separator is a Unicode rightward arrow so a subdivided bar reads
    as ``"Fmaj7 -> Am7 -> C/D"`` in UI contexts.
    """
    parts = subdivisions(token)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return sep.join(parts)


def chord_at_pulse(token: object, pulse_position: float, pulses_per_bar: float) -> str:
    """Return the active chord at a given pulse position inside a bar.

    Parameters
    ----------
    token
        Chord token (possibly subdivided).
    pulse_position
        Position within the bar in pulses/beats (``0.0`` = first beat,
        ``pulses_per_bar`` = end of bar).
    pulses_per_bar
        Total pulses in the bar.

    For non-subdivided tokens, always returns the token itself. For
    subdivided tokens, the bar is split into ``len(subdivisions)`` equal
    segments and the chord covering the requested position is returned.
    """
    parts = subdivisions(token)
    if len(parts) <= 1:
        return parts[0] if parts else ""
    if pulses_per_bar <= 0:
        return parts[0]
    seg_len = float(pulses_per_bar) / float(len(parts))
    if seg_len <= 0:
        return parts[0]
    seg_idx = int(max(0.0, float(pulse_position)) // seg_len)
    seg_idx = min(seg_idx, len(parts) - 1)
    return parts[seg_idx]


def next_chord_at_pulse(
    token: object,
    pulse_position: float,
    pulses_per_bar: float,
    fallback_next_bar_chord: object | None = None,
) -> str | None:
    """Return the chord that immediately follows ``pulse_position``.

    Inside a subdivided bar this is the next sub-chord. At the last
    subdivision (or for non-subdivided bars), the function falls back to
    the primary chord of the next bar's token.
    """
    parts = subdivisions(token)
    if len(parts) > 1 and pulses_per_bar > 0:
        seg_len = float(pulses_per_bar) / float(len(parts))
        if seg_len > 0:
            seg_idx = int(max(0.0, float(pulse_position)) // seg_len)
            seg_idx = min(seg_idx, len(parts) - 1)
            if seg_idx + 1 < len(parts):
                return parts[seg_idx + 1]
    if fallback_next_bar_chord is None:
        return None
    return primary_chord(fallback_next_bar_chord)


def expand_chord_list(chords: Iterable[object]) -> list[str]:
    """Expand subdivided bars back into a flat per-chord list.

    Useful for harmony analyzers that prefer the literal chord stream over
    the bar-grouped representation. The result has one entry per sub-chord
    so a subdivided bar contributes ``N`` entries instead of one.
    """
    out: list[str] = []
    for token in chords or []:
        for part in subdivisions(token):
            out.append(part)
    return out


def join_subdivisions(parts: Iterable[str]) -> str:
    """Build a subdivided-bar token from a sequence of chord strings.

    >>> join_subdivisions(["Fmaj7", "Am7", "C/D"])
    'Fmaj7|Am7|C/D'
    """
    cleaned = [str(p).strip() for p in parts if str(p).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return SUBDIVISION_SEPARATOR.join(cleaned)

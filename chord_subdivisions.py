"""Beat-level chord subdivisions inside a single bar.

A subdivided bar is represented as a single chord token where each beat-level
chord is separated by a pipe ``|``. For example::

    "Fmaj7|Am7|C/D"

means **one bar** containing three quick chords (one chord per beat in 3/4,
or evenly subdivided across whatever meter the song is in). The pipe
separator does not appear in plain chord symbols, so this is safe to add
without changing the existing one-chord-per-bar convention.

**Weighted subdivisions** (new):

A sub-chord can carry an explicit beat weight using a colon. For example
in 4/4::

    "C:2|G:2"      -- C for 2 beats, then G for 2 beats (half-bar change)
    "C:3|G:1"      -- C for 3 beats, G for 1 beat
    "C:3.5|D:0.5p" -- C for 3.5 beats, then a *pushed* D on the last 8th
    "C:1|G:1|Am:1|F:1"  -- one chord per beat in 4/4

A trailing ``p`` or ``!`` on a sub-chord marks it as a **push** (anticipated
chord that lands before the next bar line). Pushes show as a small "(D
push)" marker in the lead sheet and as an earlier audio attack.

When no weights are given (the original ``"Fmaj7|Am7|C/D"`` form) the
sub-chords are split into **equal** parts, exactly as before. So all
existing songs keep working without changes.

This module is the single source of truth for:

* Detecting a subdivided bar token.
* Splitting it back into its sub-chords (and their beat weights / push flag).
* Mapping a pulse/beat position inside the bar to the active sub-chord.
* Picking a primary/head chord when a single chord is required (Roman-numeral
  analysis, summary labels, etc.).
* Producing a pretty display label such as ``"Fmaj7 -> Am7 -> C/D"``.

All consumer modules (backing audio, lead-sheet rendering, chord-follow
timeline, harmony analysis) call into these helpers instead of duplicating
the parsing logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SUBDIVISION_SEPARATOR = "|"
WEIGHT_SEPARATOR = ":"
PUSH_MARKERS = ("p", "P", "!")

__all__ = [
    "SUBDIVISION_SEPARATOR",
    "WEIGHT_SEPARATOR",
    "PUSH_MARKERS",
    "Subdivision",
    "is_subdivided_bar",
    "subdivisions",
    "subdivision_count",
    "primary_chord",
    "display_label",
    "chord_at_pulse",
    "next_chord_at_pulse",
    "expand_chord_list",
    "join_subdivisions",
    "parse_subdivisions",
    "subdivision_beat_weights",
    "subdivision_beat_offsets",
    "chord_at_beat",
    "next_chord_at_beat",
    "has_push",
    "any_push",
    "join_weighted_subdivisions",
]


@dataclass(frozen=True)
class Subdivision:
    """A single chord event inside a subdivided bar.

    ``weight`` is in beats (e.g. ``2.0`` in a 4/4 half-bar split). When a
    token is provided without explicit weights, all sub-chords share an
    equal share of the bar - see :func:`parse_subdivisions`.
    """

    chord: str
    weight: float
    push: bool = False


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


# ---------------------------------------------------------------------------
# Weighted / pushed subdivisions
# ---------------------------------------------------------------------------


def _strip_push_marker(value: str) -> tuple[str, bool]:
    """If ``value`` ends with a push marker (``p`` / ``P`` / ``!``), strip
    it and return ``(value_without_marker, True)``. Otherwise return
    ``(value, False)``.
    """
    raw = str(value or "").strip()
    if not raw:
        return ("", False)
    if raw[-1] in PUSH_MARKERS:
        return (raw[:-1].strip(), True)
    return (raw, False)


def _parse_weight(value: str) -> tuple[float | None, bool]:
    """Parse ``"2"`` / ``"0.5"`` / ``"0.5p"`` into ``(weight, is_push)``.

    Returns ``(None, False)`` when ``value`` is empty (no explicit weight).
    Invalid numbers also return ``(None, False)`` so the parser falls
    back to the equal-share default for that sub-chord.
    """
    raw, push = _strip_push_marker(value)
    if not raw:
        return (None, push)
    try:
        w = float(raw)
    except ValueError:
        return (None, push)
    if w <= 0:
        return (None, push)
    return (w, push)


def parse_subdivisions(
    token: object,
    *,
    beats_per_bar: float = 4.0,
) -> list[Subdivision]:
    """Parse a (possibly subdivided / weighted) bar token into ``Subdivision`` items.

    Behaviour:

    * Empty / whitespace token -> ``[]``.
    * Single-chord token (no ``|``) -> one ``Subdivision`` covering the
      whole bar with ``weight = beats_per_bar``.
    * Multi-chord token *without* any ``:weight`` annotations -> N equal
      shares of ``beats_per_bar`` (the original behaviour).
    * Multi-chord token *with* explicit ``:weight`` annotations -> beat
      weights honoured exactly. Any sub-chord that omits a weight gets
      whatever's left of ``beats_per_bar`` divided equally among the
      unweighted ones.
    * Trailing push markers (``p`` / ``P`` / ``!``) attach to the
      sub-chord, *not* to its weight. Both ``"D:0.5p"`` and ``"Dp:0.5"``
      / ``"D!:0.5"`` are accepted.
    """
    raw = str(token or "").strip()
    if not raw:
        return []
    if SUBDIVISION_SEPARATOR not in raw:
        chord_clean, push = _strip_push_marker(raw)
        if not chord_clean:
            return []
        return [Subdivision(chord=chord_clean, weight=float(beats_per_bar), push=push)]

    pieces = [p.strip() for p in raw.split(SUBDIVISION_SEPARATOR) if p.strip()]
    if not pieces:
        return []

    parsed: list[tuple[str, float | None, bool]] = []
    for piece in pieces:
        if WEIGHT_SEPARATOR in piece:
            chord_part, weight_part = piece.split(WEIGHT_SEPARATOR, 1)
            chord_clean, push_chord = _strip_push_marker(chord_part)
            weight, push_weight = _parse_weight(weight_part)
            push = push_chord or push_weight
        else:
            chord_clean, push = _strip_push_marker(piece)
            weight = None
        if not chord_clean:
            continue
        parsed.append((chord_clean, weight, push))

    if not parsed:
        return []

    explicit_total = sum(w for _, w, _ in parsed if w is not None)
    unweighted_count = sum(1 for _, w, _ in parsed if w is None)
    bpb = float(beats_per_bar)

    if unweighted_count == 0:
        # Pure-weighted form. If the weights don't sum to ``beats_per_bar``
        # (e.g. ``"C:2|G:2"`` in a 3/4 bar) we trust the weights as-is -
        # the user knows what they're doing. Downstream renderers compute
        # offsets from the actual weights.
        return [Subdivision(chord=c, weight=float(w), push=p) for c, w, p in parsed]

    if explicit_total >= bpb:
        # Weighted entries already fill the bar; unweighted ones get a
        # tiny equal share of what's left (or, if nothing's left, an
        # equal share of one beat - defensive default).
        leftover = max(0.0, bpb - explicit_total)
        share = leftover / unweighted_count if leftover > 0 else 1.0
    else:
        leftover = bpb - explicit_total
        share = leftover / unweighted_count

    out: list[Subdivision] = []
    for chord, weight, push in parsed:
        w = float(weight) if weight is not None else float(share)
        out.append(Subdivision(chord=chord, weight=w, push=push))
    return out


def subdivision_beat_weights(
    token: object,
    *,
    beats_per_bar: float = 4.0,
) -> list[float]:
    """Return the beat-weights for each sub-chord inside ``token``.

    Equivalent to ``[s.weight for s in parse_subdivisions(token, ...)]``.
    """
    return [s.weight for s in parse_subdivisions(token, beats_per_bar=beats_per_bar)]


def subdivision_beat_offsets(
    token: object,
    *,
    beats_per_bar: float = 4.0,
) -> list[float]:
    """Return the beat-offset (start position, in beats) for each sub-chord.

    For ``"C:2|G:2"`` in 4/4 -> ``[0.0, 2.0]``.
    For ``"Fmaj7|Am7|C/D"`` in 3/4 -> ``[0.0, 1.0, 2.0]``.
    """
    subs = parse_subdivisions(token, beats_per_bar=beats_per_bar)
    out: list[float] = []
    cursor = 0.0
    for s in subs:
        out.append(cursor)
        cursor += s.weight
    return out


def chord_at_beat(
    token: object,
    beat_offset: float,
    *,
    beats_per_bar: float = 4.0,
) -> str:
    """Return the active sub-chord at ``beat_offset`` beats into the bar.

    Honours weighted subdivisions: in ``"C:3|G:1"``, beat 0..3 returns
    ``"C"`` and beat 3..4 returns ``"G"``.
    """
    subs = parse_subdivisions(token, beats_per_bar=beats_per_bar)
    if not subs:
        return ""
    if len(subs) == 1:
        return subs[0].chord
    cursor = 0.0
    pos = max(0.0, float(beat_offset))
    for s in subs:
        end = cursor + s.weight
        # Closed-open interval [cursor, end): a sub-chord owns its start
        # beat but the next sub-chord owns the beat where it begins.
        if pos < end:
            return s.chord
        cursor = end
    return subs[-1].chord


def next_chord_at_beat(
    token: object,
    beat_offset: float,
    *,
    beats_per_bar: float = 4.0,
    fallback_next_bar_chord: object | None = None,
) -> str | None:
    """Return the chord that follows ``beat_offset`` inside the bar.

    Falls back to the head chord of ``fallback_next_bar_chord`` when the
    requested position is in the final sub-chord of the bar.
    """
    subs = parse_subdivisions(token, beats_per_bar=beats_per_bar)
    if len(subs) > 1:
        cursor = 0.0
        pos = max(0.0, float(beat_offset))
        for idx, s in enumerate(subs):
            end = cursor + s.weight
            if pos < end:
                if idx + 1 < len(subs):
                    return subs[idx + 1].chord
                break
            cursor = end
    if fallback_next_bar_chord is None:
        return None
    return primary_chord(fallback_next_bar_chord)


def has_push(token: object) -> bool:
    """``True`` when *any* sub-chord in ``token`` is marked as a push."""
    return any(s.push for s in parse_subdivisions(token))


def any_push(tokens: Iterable[object]) -> bool:
    """``True`` when any token in the iterable contains a push marker."""
    return any(has_push(t) for t in tokens or ())


def join_weighted_subdivisions(
    subs: Iterable[Subdivision | tuple[str, float, bool] | tuple[str, float]],
) -> str:
    """Build a weighted subdivided-bar token from a sequence of ``Subdivision``s.

    >>> join_weighted_subdivisions([
    ...     Subdivision("C", 3.5, False),
    ...     Subdivision("D", 0.5, True),
    ... ])
    'C:3.5|D:0.5p'
    """
    pieces: list[str] = []
    for s in subs or ():
        if isinstance(s, Subdivision):
            chord, weight, push = s.chord, s.weight, s.push
        elif isinstance(s, tuple) and len(s) >= 2:
            chord = str(s[0])
            weight = float(s[1])
            push = bool(s[2]) if len(s) >= 3 else False
        else:
            continue
        chord_str = str(chord).strip()
        if not chord_str:
            continue
        # Render the weight cleanly: integer when it really is integer,
        # otherwise short float so "3" stays "3" (not "3.0").
        if abs(weight - round(weight)) < 1e-6:
            weight_str = str(int(round(weight)))
        else:
            weight_str = f"{weight:g}"
        suffix = f"{WEIGHT_SEPARATOR}{weight_str}"
        if push:
            suffix += PUSH_MARKERS[0]
        pieces.append(f"{chord_str}{suffix}")
    if not pieces:
        return ""
    if len(pieces) == 1:
        # Single-chord; don't render weight - keep simple bar token.
        return pieces[0].split(WEIGHT_SEPARATOR, 1)[0]
    return SUBDIVISION_SEPARATOR.join(pieces)

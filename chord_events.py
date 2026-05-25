"""Bidirectional converter between the user-facing chord-event format
and the internal weighted-subdivision bar token list.

The user-facing format is a list of dicts, e.g.::

    [
        {"section": "Verse 1", "bar": 4, "beat": 1, "duration_beats": 2, "chord": "C"},
        {"section": "Verse 1", "bar": 4, "beat": 3, "duration_beats": 2, "chord": "G"},
        {"section": "Harmonica Intro", "bar": 14, "beat": 1, "duration_beats": 1, "chord": "Fmaj7"},
        {"section": "Harmonica Intro", "bar": 14, "beat": 2, "duration_beats": 1, "chord": "Am7"},
        {"section": "Harmonica Intro", "bar": 14, "beat": 3, "duration_beats": 1, "chord": "C/D"},
        {"section": "Chorus", "bar": 8, "beat": 4.5, "duration_beats": 0.5, "chord": "D", "push": True},
    ]

The internal format is the bar-grouped list already used by the
synthesizer / lead sheet / chord-follow timeline. Each bar is a single
token, with subdivided bars expressed as a weighted ``"C:2|G:2"`` token
(see :mod:`chord_subdivisions`).

This module is intentionally tiny - no song-catalog logic, just pure
data transforms - so it can be imported from anywhere without circular
dependencies.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

import chord_subdivisions as cs

__all__ = (
    "events_to_bar_tokens",
    "events_to_sections",
    "section_chord_list_to_events",
    "sections_dict_to_events",
    "beats_per_bar_from_signature",
    "expanded_subdivisions_for_bar",
    "validate_chord_events",
)


# ---------------------------------------------------------------------------
# Meter helpers
# ---------------------------------------------------------------------------


def beats_per_bar_from_signature(time_signature: str | None) -> float:
    """Beats per bar for chord-event timing purposes.

    ``4/4`` -> 4, ``3/4`` -> 3, ``2/4`` -> 2. Compound meters (``6/8``,
    ``12/8``) return *pulses* per bar - the chord event API talks in
    eighth-note pulses for compound meters, matching the engine.
    """
    raw = str(time_signature or "4/4").strip()
    if "/" not in raw:
        try:
            return float(int(raw))
        except (TypeError, ValueError):
            return 4.0
    top_str, bot_str = raw.split("/", 1)
    try:
        top = int(top_str)
    except (TypeError, ValueError):
        top = 4
    try:
        bot = int(bot_str)
    except (TypeError, ValueError):
        bot = 4
    return float(max(1, top))


# ---------------------------------------------------------------------------
# Event-list -> bar-token list
# ---------------------------------------------------------------------------


def _normalize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce a raw event dict into the keys the converter cares about."""
    if not isinstance(event, Mapping):
        return {}
    chord = str(event.get("chord", "")).strip()
    if not chord:
        return {}
    section = str(event.get("section", "")).strip()
    try:
        bar = int(event.get("bar", 1))
    except (TypeError, ValueError):
        bar = 1
    try:
        beat = float(event.get("beat", 1))
    except (TypeError, ValueError):
        beat = 1.0
    try:
        duration_beats = float(event.get("duration_beats", 0))
    except (TypeError, ValueError):
        duration_beats = 0.0
    push = bool(event.get("push", False))
    return {
        "section": section,
        "bar": max(1, bar),
        "beat": max(1.0, beat),
        "duration_beats": max(0.0, duration_beats),
        "chord": chord,
        "push": push,
    }


def _events_grouped_by_section_and_bar(
    events: Iterable[Mapping[str, Any]],
) -> tuple[list[str], dict[str, dict[int, list[dict[str, Any]]]]]:
    """Group events by section, then by bar; preserve section first-seen order.

    Returns ``(ordered_section_names, {section: {bar: [events...]}})``.
    Events inside a bar are sorted by ``beat``.
    """
    order: list[str] = []
    grouped: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for raw in events or ():
        ev = _normalize_event(raw)
        if not ev:
            continue
        if ev["section"] not in grouped:
            order.append(ev["section"])
        grouped[ev["section"]][ev["bar"]].append(ev)
    for section_buckets in grouped.values():
        for bar_events in section_buckets.values():
            bar_events.sort(key=lambda e: e["beat"])
    return order, grouped


def _bar_events_to_token(
    bar_events: list[dict[str, Any]],
    *,
    beats_per_bar: float,
) -> str:
    """Compose one bar's chord token from its sorted event list."""
    if not bar_events:
        return ""
    if len(bar_events) == 1:
        ev = bar_events[0]
        chord = ev["chord"]
        # Pushed single-bar chord: keep the chord plain (push only really
        # matters for multi-chord bars; a one-bar push is rare and the
        # marker would clutter the chart) - but record it so the synth
        # can still treat it as an early attack.
        if ev["push"]:
            return cs.join_weighted_subdivisions(
                [cs.Subdivision(chord=chord, weight=float(beats_per_bar), push=True)]
            )
        return chord
    parts: list[cs.Subdivision] = []
    for ev in bar_events:
        dur = float(ev["duration_beats"]) if ev["duration_beats"] > 0 else None
        if dur is None or dur <= 0:
            # No explicit duration: equal share of remaining time.
            dur = float(beats_per_bar) / float(len(bar_events))
        parts.append(
            cs.Subdivision(chord=ev["chord"], weight=dur, push=ev["push"])
        )
    return cs.join_weighted_subdivisions(parts)


def events_to_bar_tokens(
    events: Iterable[Mapping[str, Any]],
    *,
    time_signature: str = "4/4",
    section_name: str | None = None,
) -> list[str]:
    """Convert a chord-event list to a flat list of per-bar tokens.

    ``section_name`` restricts the output to events belonging to that
    section. When omitted, *all* sections are merged into a single
    contiguous bar list in event-section order.
    """
    bpb = beats_per_bar_from_signature(time_signature)
    order, grouped = _events_grouped_by_section_and_bar(events)
    if section_name is not None:
        if section_name not in grouped:
            return []
        order = [section_name]
    out: list[str] = []
    for section in order:
        buckets = grouped[section]
        if not buckets:
            continue
        for bar_idx in sorted(buckets.keys()):
            out.append(_bar_events_to_token(buckets[bar_idx], beats_per_bar=bpb))
    return out


def events_to_sections(
    events: Iterable[Mapping[str, Any]],
    *,
    time_signature: str = "4/4",
) -> dict[str, list[str]]:
    """Convert a chord-event list to a ``{section: [bar_token, ...]}`` dict.

    Section iteration order matches the first-seen order in ``events``.
    Within a section the bar order matches the catalog ``bar`` numbers
    (1-indexed, sorted).
    """
    bpb = beats_per_bar_from_signature(time_signature)
    order, grouped = _events_grouped_by_section_and_bar(events)
    out: dict[str, list[str]] = {}
    for section in order:
        buckets = grouped[section]
        bars: list[str] = []
        if buckets:
            max_bar = max(buckets.keys())
            for bar_idx in range(1, max_bar + 1):
                if bar_idx in buckets:
                    bars.append(_bar_events_to_token(buckets[bar_idx], beats_per_bar=bpb))
                else:
                    bars.append("")  # caller can decide how to fill gaps
        out[section] = bars
    return out


# ---------------------------------------------------------------------------
# Bar-token list -> event list
# ---------------------------------------------------------------------------


def section_chord_list_to_events(
    section_name: str,
    chord_tokens: Iterable[str],
    *,
    time_signature: str = "4/4",
    start_bar: int = 1,
) -> list[dict[str, Any]]:
    """Convert a section's bar-token list into chord events.

    A plain bar token (``"C"``) becomes a single event covering all
    ``beats_per_bar`` beats of that bar. A subdivided bar
    (``"Fmaj7|Am7|C/D"`` or ``"C:2|G:2"``) becomes one event per
    sub-chord at the correct beat offset and duration.
    """
    bpb = beats_per_bar_from_signature(time_signature)
    out: list[dict[str, Any]] = []
    bar_idx = int(start_bar)
    for raw in chord_tokens or ():
        token = str(raw or "").strip()
        if not token:
            bar_idx += 1
            continue
        subs = cs.parse_subdivisions(token, beats_per_bar=bpb)
        if not subs:
            bar_idx += 1
            continue
        beat_cursor = 1.0  # 1-indexed beat positions (musician-facing)
        for s in subs:
            event: dict[str, Any] = {
                "section": section_name,
                "bar": bar_idx,
                "beat": round(beat_cursor, 6),
                "duration_beats": round(float(s.weight), 6),
                "chord": s.chord,
            }
            if s.push:
                event["push"] = True
            out.append(event)
            beat_cursor += float(s.weight)
        bar_idx += 1
    return out


def sections_dict_to_events(
    sections: Mapping[str, Iterable[str]] | None,
    *,
    time_signature: str = "4/4",
    section_order: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert a full sections dict to a chord-event list.

    Bar numbering restarts at 1 for each section (matches the way the
    rest of the app talks about bars - "Verse 1 bar 4", not "absolute
    bar 23").
    """
    if not sections:
        return []
    if section_order:
        order = [s for s in section_order if s in sections]
        for name in sections:
            if name not in order:
                order.append(name)
    else:
        order = list(sections.keys())
    out: list[dict[str, Any]] = []
    for section_name in order:
        out.extend(
            section_chord_list_to_events(
                section_name,
                sections.get(section_name) or [],
                time_signature=time_signature,
                start_bar=1,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Convenience: per-bar subdivision expansion
# ---------------------------------------------------------------------------


def expanded_subdivisions_for_bar(
    chord_token: str,
    *,
    time_signature: str = "4/4",
) -> list[cs.Subdivision]:
    """Return the ``Subdivision`` items for a single bar token.

    Thin wrapper around :func:`chord_subdivisions.parse_subdivisions`
    that resolves ``beats_per_bar`` from a meter string for convenience.
    """
    bpb = beats_per_bar_from_signature(time_signature)
    return cs.parse_subdivisions(chord_token, beats_per_bar=bpb)


def validate_chord_events(
    events: Iterable[Mapping[str, Any]],
    *,
    time_signature: str = "4/4",
) -> list[str]:
    """Return a list of human-readable issues with an event list.

    Empty list means the events look well-formed. Checks:

    * Every event has a non-empty ``chord``.
    * ``beat`` >= 1 and ``beat + duration_beats - 1 <= beats_per_bar``
      (chords must end at or before the bar line; pushes are exempt).
    * Inside the same section + bar, sub-chords don't overlap.
    """
    bpb = beats_per_bar_from_signature(time_signature)
    issues: list[str] = []
    _, grouped = _events_grouped_by_section_and_bar(events)
    for section, buckets in grouped.items():
        for bar_idx, bar_events in buckets.items():
            cursor = 0.0
            for ev in bar_events:
                if not ev["chord"]:
                    issues.append(f"{section} bar {bar_idx}: empty chord at beat {ev['beat']}")
                    continue
                start = ev["beat"] - 1.0
                end = start + ev["duration_beats"]
                if start < cursor - 1e-6:
                    issues.append(
                        f"{section} bar {bar_idx}: chord '{ev['chord']}' at beat "
                        f"{ev['beat']} overlaps previous chord"
                    )
                if not ev.get("push") and end - bpb > 1e-6:
                    issues.append(
                        f"{section} bar {bar_idx}: chord '{ev['chord']}' extends past "
                        f"the bar line ({end:g} beats, meter has {bpb:g})"
                    )
                cursor = max(cursor, end)
    return issues

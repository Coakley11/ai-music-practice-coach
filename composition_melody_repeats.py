"""Melody phrase repeat expansion for Composition Studio."""

from __future__ import annotations

import copy
from typing import Any, Callable

EDIT_SCOPE_ALL = "all_repeats"
EDIT_SCOPE_FIRST = "first_occurrence"


def phrase_length_beats(events: list[dict[str, Any]] | None) -> float:
    total = 0.0
    for ev in list(events or []):
        if not isinstance(ev, dict):
            continue
        end = float(ev.get("beat") or 0.0) + float(ev.get("duration_beats") or 0.0)
        if end > total:
            total = end
    return total


def expand_melody_events_by_repeats(
    events: list[dict[str, Any]] | None,
    repeats: int,
    *,
    phrase_beats: float | None = None,
) -> list[dict[str, Any]]:
    """
    Tile a melodic phrase ``repeats`` times.

    Each repeat shifts event beats by the phrase length so alignment with
    measures/chords stays consistent.
    """
    base = [copy.deepcopy(e) for e in list(events or []) if isinstance(e, dict)]
    n = max(1, int(repeats))
    if n == 1 or not base:
        for ev in base:
            ev.setdefault("repeat_index", 0)
        return base
    span = float(phrase_beats) if phrase_beats is not None else phrase_length_beats(base)
    if span <= 0:
        span = sum(float(e.get("duration_beats") or 1.0) for e in base) or 4.0
    out: list[dict[str, Any]] = []
    for r in range(n):
        offset = r * span
        for ev in base:
            row = copy.deepcopy(ev)
            row["beat"] = float(row.get("beat") or 0.0) + offset
            row["repeat_index"] = r
            out.append(row)
    return out


def detect_repeat_count(events: list[dict[str, Any]] | None) -> int:
    """Infer how many tiled phrase occurrences are present."""
    idxs = {
        int(ev.get("repeat_index"))
        for ev in list(events or [])
        if isinstance(ev, dict) and ev.get("repeat_index") is not None
    }
    if idxs:
        return max(idxs) + 1
    return 1


def apply_transform_with_repeat_scope(
    events: list[dict[str, Any]] | None,
    transform: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    *,
    scope: str = EDIT_SCOPE_ALL,
) -> list[dict[str, Any]]:
    """
    Apply a melodic transform either to every repeat occurrence or only the first.

    Explicit rule:
    - ``all_repeats`` (default): transform whole accepted melody (all tiles).
    - ``first_occurrence``: transform only events with ``repeat_index == 0`` (or the
      first phrase-length slice when indices are missing); later repeats stay as-is.
    """
    evs = [copy.deepcopy(e) for e in list(events or []) if isinstance(e, dict)]
    if not evs:
        return []
    mode = str(scope or EDIT_SCOPE_ALL).strip() or EDIT_SCOPE_ALL
    if mode != EDIT_SCOPE_FIRST:
        return transform(evs)

    has_idx = any(e.get("repeat_index") is not None for e in evs)
    if has_idx:
        first = [e for e in evs if int(e.get("repeat_index") or 0) == 0]
        rest = [e for e in evs if int(e.get("repeat_index") or 0) != 0]
        updated_first = transform(first)
        # Keep later occurrences' absolute beats; only first-tile content changes.
        return list(updated_first) + list(rest)

    # No markers: treat first phrase-length half (or all if single) as first occurrence.
    span = phrase_length_beats(evs)
    if detect_repeat_count(evs) <= 1 and span <= 0:
        return transform(evs)
    # Heuristic when unmarked: edit all (safer than silently splitting wrong).
    return transform(evs)
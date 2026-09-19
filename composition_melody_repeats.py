"""Section melody pattern repeats for Composition Studio.

Authoritative melody for a section is always ``section["melody"]["events"]`` — the
full expanded event list (including every repeated pass and any occurrence-level edit).

When the melody is still a clean tile of a base pattern, ``melody`` also tracks:
- ``melody_pattern`` — base suggestion / one-pass events
- ``melody_repeats`` — how many times that pattern is tiled into ``events``
- ``melody_tiled`` — True while slider re-expansion is safe

Once the user accepts a refinement or manual edit that is not a pure re-tile,
``melody_tiled`` becomes False and the full ``events`` list is the only truth.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from composition_document import apply_melody_events, section_by_id

MELODY_REPEAT_MIN = 1
MELODY_REPEAT_MAX = 4

EDIT_SCOPE_ALL = "all_repeats"
EDIT_SCOPE_FIRST = "first_occurrence"


def clamp_melody_repeats(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 1
    return max(MELODY_REPEAT_MIN, min(MELODY_REPEAT_MAX, n))


def _clone_events(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [copy.deepcopy(e) for e in list(events or []) if isinstance(e, dict)]


def _event_pitch_signature(events: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for ev in list(events or []):
        if not isinstance(ev, dict):
            continue
        pitch = str(ev.get("pitch") or "").strip()
        if pitch:
            out.append(pitch)
    return out


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
    measures/chords stays consistent. Sets both ``repeat_index`` and ``pass_index``.
    """
    base = _clone_events(events)
    n = clamp_melody_repeats(repeats)
    if n == 1 or not base:
        for ev in base:
            ev.setdefault("repeat_index", 0)
            ev.setdefault("pass_index", 0)
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
            row["pass_index"] = r
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
    pass_idxs = {
        int(ev.get("pass_index"))
        for ev in list(events or [])
        if isinstance(ev, dict) and ev.get("pass_index") is not None
    }
    if pass_idxs:
        return max(pass_idxs) + 1
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
    evs = _clone_events(events)
    if not evs:
        return []
    mode = str(scope or EDIT_SCOPE_ALL).strip() or EDIT_SCOPE_ALL
    if mode != EDIT_SCOPE_FIRST:
        return transform(evs)

    has_idx = any(
        e.get("repeat_index") is not None or e.get("pass_index") is not None for e in evs
    )
    if has_idx:

        def _idx(e: dict[str, Any]) -> int:
            if e.get("repeat_index") is not None:
                return int(e.get("repeat_index") or 0)
            return int(e.get("pass_index") or 0)

        first = [e for e in evs if _idx(e) == 0]
        rest = [e for e in evs if _idx(e) != 0]
        updated_first = transform(first)
        # Keep later occurrences' absolute beats; only first-tile content changes.
        return list(updated_first) + list(rest)

    # No markers: treat first phrase-length half (or all if single) as first occurrence.
    span = phrase_length_beats(evs)
    if detect_repeat_count(evs) <= 1 and span <= 0:
        return transform(evs)
    # Heuristic when unmarked: edit all (safer than silently splitting wrong).
    return transform(evs)


def ensure_melody_repeat_meta(section: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure section melody carries pattern / repeat metadata."""
    if not isinstance(section, dict):
        return {}
    melody = section.get("melody")
    if not isinstance(melody, dict):
        melody = {}
        section["melody"] = melody
    events = _clone_events(melody.get("events") if isinstance(melody.get("events"), list) else [])
    if "melody_pattern" not in melody:
        melody["melody_pattern"] = _clone_events(events) if events else []
    if "melody_repeats" not in melody:
        melody["melody_repeats"] = 1
    if "melody_tiled" not in melody:
        pattern = list(melody.get("melody_pattern") or [])
        if pattern and events:
            p_sig = _event_pitch_signature(pattern)
            e_sig = _event_pitch_signature(events)
            if p_sig and e_sig and len(e_sig) % len(p_sig) == 0:
                n = len(e_sig) // len(p_sig)
                melody["melody_tiled"] = e_sig == (p_sig * n)
                if melody["melody_tiled"]:
                    melody["melody_repeats"] = clamp_melody_repeats(n)
            else:
                melody["melody_tiled"] = False
        else:
            melody["melody_tiled"] = bool(events)
    melody["melody_repeats"] = clamp_melody_repeats(melody.get("melody_repeats"))
    return melody


def get_melody_pattern(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    melody = ensure_melody_repeat_meta(section)
    pattern = melody.get("melody_pattern")
    if isinstance(pattern, list) and pattern:
        return _clone_events(pattern)
    return _clone_events((melody.get("events") if isinstance(melody, dict) else None) or [])


def get_melody_repeats(section: dict[str, Any] | None) -> int:
    melody = ensure_melody_repeat_meta(section)
    return clamp_melody_repeats(melody.get("melody_repeats"))


def melody_is_tiled(section: dict[str, Any] | None) -> bool:
    melody = ensure_melody_repeat_meta(section)
    return bool(melody.get("melody_tiled"))


def accept_melody_pattern(
    doc: dict[str, Any],
    section_id: str,
    pattern_events: list[dict[str, Any]],
    *,
    source_id: str = "",
    repeats: int | None = None,
) -> bool:
    """Accept a base melodic idea as the active tiled melody."""
    sec = section_by_id(doc, section_id)
    if not sec:
        return False
    melody = ensure_melody_repeat_meta(sec)
    pattern = _clone_events(pattern_events)
    if not pattern:
        return False
    n = clamp_melody_repeats(repeats if repeats is not None else melody.get("melody_repeats") or 1)
    melody["melody_pattern"] = pattern
    melody["melody_repeats"] = n
    melody["melody_tiled"] = True
    melody["melody_customized"] = False
    if source_id:
        melody["active_source_id"] = str(source_id)
    expanded = expand_melody_events_by_repeats(pattern, n)
    applied = apply_melody_events(doc, section_id, expanded, replace=True)
    return bool(applied)


def heal_melody_tiling_if_safe(section: dict[str, Any] | None) -> bool:
    """Ensure a clean accepted melody can use the repeats slider.

    Heals missing/false ``melody_tiled`` when events are still a clean pattern
    (or an exact N× expansion of the stored pattern). Never unlocks after
    true pass-specific customization (``melody_customized``).
    """
    if not isinstance(section, dict):
        return False
    melody = ensure_melody_repeat_meta(section)
    if bool(melody.get("melody_customized")):
        melody["melody_tiled"] = False
        return False
    if bool(melody.get("melody_tiled")):
        return True
    events = _clone_events(melody.get("events") if isinstance(melody.get("events"), list) else [])
    if not events:
        return False
    pattern = _clone_events(melody.get("melody_pattern") if isinstance(melody.get("melody_pattern"), list) else [])
    e_sig = _event_pitch_signature(events)
    if not pattern:
        # Accepted melody with no pattern yet — treat events as the base phrase.
        melody["melody_pattern"] = _clone_events(events)
        melody["melody_repeats"] = 1
        melody["melody_tiled"] = True
        melody["melody_customized"] = False
        return True
    p_sig = _event_pitch_signature(pattern)
    if not p_sig or not e_sig:
        return False
    if e_sig == p_sig:
        melody["melody_tiled"] = True
        melody["melody_repeats"] = 1
        melody["melody_customized"] = False
        return True
    if len(e_sig) % len(p_sig) == 0:
        n = len(e_sig) // len(p_sig)
        if e_sig == (p_sig * n) and 1 <= n <= MELODY_REPEAT_MAX:
            melody["melody_tiled"] = True
            melody["melody_repeats"] = clamp_melody_repeats(n)
            melody["melody_customized"] = False
            return True
    return False


def melody_repeats_are_editable(section: dict[str, Any] | None) -> bool:
    """True when the Melody repeats slider can safely change the timeline."""
    return heal_melody_tiling_if_safe(section)


def set_section_melody_repeats(doc: dict[str, Any], section_id: str, repeats: int) -> bool:
    """Re-tile the stored base pattern when still in tiled mode."""
    sec = section_by_id(doc, section_id)
    if not sec:
        return False
    if not heal_melody_tiling_if_safe(sec):
        return False
    melody = ensure_melody_repeat_meta(sec)
    pattern = get_melody_pattern(sec)
    if not pattern:
        return False
    n = clamp_melody_repeats(repeats)
    melody["melody_repeats"] = n
    melody["melody_tiled"] = True
    expanded = expand_melody_events_by_repeats(pattern, n)
    applied = apply_melody_events(doc, section_id, expanded, replace=True)
    # apply_melody_events without concept must not drop tiling metadata
    melody = ensure_melody_repeat_meta(sec)
    melody["melody_pattern"] = _clone_events(pattern)
    melody["melody_repeats"] = n
    melody["melody_tiled"] = True
    melody["melody_customized"] = False
    return bool(applied)


def accept_full_melody(
    doc: dict[str, Any],
    section_id: str,
    events: list[dict[str, Any]],
    *,
    source_id: str = "",
    tiled: bool = False,
    pattern_events: list[dict[str, Any]] | None = None,
    repeats: int | None = None,
) -> bool:
    """Install a full melody as authoritative section events."""
    sec = section_by_id(doc, section_id)
    if not sec:
        return False
    full = _clone_events(events)
    if not full:
        return False
    melody = ensure_melody_repeat_meta(sec)
    if tiled and pattern_events:
        pattern = _clone_events(pattern_events)
        n = clamp_melody_repeats(repeats if repeats is not None else 1)
        melody["melody_pattern"] = pattern
        melody["melody_repeats"] = n
        melody["melody_tiled"] = True
        melody["melody_customized"] = False
        if source_id:
            melody["active_source_id"] = str(source_id)
        full = expand_melody_events_by_repeats(pattern, n)
    else:
        melody["melody_pattern"] = _clone_events(full)
        melody["melody_repeats"] = 1
        melody["melody_tiled"] = False
        melody["melody_customized"] = True
        if source_id:
            melody["active_source_id"] = str(source_id)
    applied = apply_melody_events(doc, section_id, full, replace=True)
    return bool(applied)


def mark_melody_customized(section: dict[str, Any] | None) -> None:
    """After occurrence-level edits, freeze tiling so repeats cannot wipe changes."""
    if not isinstance(section, dict):
        return
    melody = ensure_melody_repeat_meta(section)
    events = _clone_events(melody.get("events") if isinstance(melody.get("events"), list) else [])
    melody["melody_tiled"] = False
    melody["melody_customized"] = True
    melody["melody_pattern"] = events
    melody["melody_repeats"] = 1

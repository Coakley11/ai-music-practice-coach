"""Measure-level playback synchronization data for Practice Melody (Slice F2).

Builds a mapping from each displayed Practice Melody measure to real
playback-time windows, by joining against Backing's own existing
``follow_timeline`` (built by ``build_chord_event_timeline`` in
streamlit_music_practice_app.py and already used to drive Backing's own
chord-chart follow-along highlighting). This module never invents its own
clock or timing data -- it only re-keys timing Backing already computed, so
"the synchronization source is the same playback truth that drives
Backing" is true by construction, not by convention.

Two-step join, both pure and unit-testable without Streamlit or a browser:

1. ``build_melody_measure_sync_data`` walks the Practice Melody sections
   actually being displayed (full song or Section-Focus-scoped, in the
   same order ``practice_melody_notation.practice_melody_sections_abc``
   renders them) and assigns each measure a ``(section, bar_in_section)``
   key plus the range of *note* indices (rests excluded, matching abcjs's
   own ``.abcjs-note`` element numbering) that measure occupies in the
   flattened event stream fed to ``build_abc_from_melody_events``.
2. ``resolve_melody_measure_timing`` joins that against Backing's
   ``follow_timeline`` rows by ``(section, bar_in_section)``, grouping by
   ``absolute_bar`` (unique per sounding occurrence, including every Key
   Cycle loop pass) so a repeated section's measures get one timing window
   per loop pass while always pointing at the same melody note range --
   multiple loops stay synchronized without any special-case loop logic.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from practice_melody_model import MelodySection


def build_melody_measure_sync_data(sections: Sequence[MelodySection]) -> list[dict[str, Any]]:
    """One entry per measure across ``sections``, in the exact order
    ``practice_melody_notation``'s ABC builders will flatten them into
    events -- so the Nth note here is the Nth ``.abcjs-note`` abcjs renders.
    """
    out: list[dict[str, Any]] = []
    note_cursor = 0
    for section in sections:
        events_by_measure: dict[int, list] = {}
        for event in section.events:
            events_by_measure.setdefault(event.measure, []).append(event)
        for measure_index in range(section.measures):
            measure_events = events_by_measure.get(measure_index, [])
            note_count = sum(1 for e in measure_events if not e.is_rest)
            out.append(
                {
                    "section": section.section_id,
                    # Backing's follow_timeline bar_in_section is 1-based.
                    "bar_in_section": measure_index + 1,
                    "note_start_index": note_cursor,
                    "note_end_index": note_cursor + note_count,
                }
            )
            note_cursor += note_count
    return out


def resolve_melody_measure_timing(
    measure_entries: Sequence[Mapping[str, Any]],
    follow_timeline: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join melody measures against Backing's own follow_timeline rows.

    Returns a JS-ready, time-sorted list of
    ``{start, end, note_start, note_end, key}`` windows, one per actual
    sounding occurrence of each measure (so a measure played twice by a
    loop, or revisited across Key Cycle passes, gets two separate windows
    pointing at the same note range). Rows whose ``(section,
    bar_in_section)`` isn't part of the displayed melody (e.g. Backing is
    playing a section the melody doesn't cover) are silently skipped.
    """
    index: dict[tuple[str, int], Mapping[str, Any]] = {}
    for entry in measure_entries:
        key = (str(entry.get("section") or ""), int(entry.get("bar_in_section") or 0))
        index[key] = entry

    groups: dict[Any, dict[str, Any]] = {}
    for row in follow_timeline:
        key = (str(row.get("section") or ""), int(row.get("bar_in_section") or 0))
        melody_entry = index.get(key)
        if melody_entry is None:
            continue
        abs_bar = row.get("absolute_bar")
        start = float(row.get("start_time") or 0.0)
        end = float(row.get("end_time") or start)
        group = groups.setdefault(abs_bar, {"start": start, "end": end, "key": key})
        group["start"] = min(group["start"], start)
        group["end"] = max(group["end"], end)

    out: list[dict[str, Any]] = []
    for window in groups.values():
        melody_entry = index[window["key"]]
        out.append(
            {
                "start": window["start"],
                "end": window["end"],
                "note_start": int(melody_entry["note_start_index"]),
                "note_end": int(melody_entry["note_end_index"]),
                "key": f"{window['key'][0]}:{window['key'][1]}",
            }
        )
    out.sort(key=lambda e: e["start"])
    return out

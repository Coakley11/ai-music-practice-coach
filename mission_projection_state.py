"""Single Missions projection resolver: concert vs chart vs selected chord vs example."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

II_SELECTED_CHORD = "ii_selected_chord"
II_SELECTED_SECTION = "ii_selected_section"
II_SELECTED_CHORD_INDEX = "ii_selected_chord_index"


@dataclass(frozen=True)
class MissionProjectionState:
    """Authoritative Missions key/chord snapshot for one render or Generate click."""

    concert_key: str
    chart_key: str
    concert_chord: str
    display_chord: str
    section_label: str
    chord_index: int


def concert_and_chart_keys(session: dict[str, Any], *, fallback: str = "C") -> tuple[str, str]:
    concert = str(fallback or "C").strip() or "C"
    try:
        from improvisation_intelligence_ui import _authoritative_practice_chart_key

        concert = _authoritative_practice_chart_key(session, concert)
    except ImportError:
        concert = str(session.get("display_key") or session.get("concert_key") or concert).strip() or concert
    try:
        from effective_practice_context import musician_facing_chart_key

        chart = musician_facing_chart_key(session, concert)
    except ImportError:
        chart = concert
    return concert, str(chart or concert).strip() or concert


def display_chord_from_concert(concert_chord: str, *, concert_key: str, chart_key: str) -> str:
    src = str(concert_chord or "").strip()
    if not src:
        return ""
    concert = str(concert_key or "").strip()
    chart = str(chart_key or "").strip()
    if not concert or not chart or concert == chart:
        return src
    try:
        from effective_practice_context import musician_facing_chord

        return musician_facing_chord(src, concert_key=concert, chart_key=chart)
    except ImportError:
        return src


def concert_chord_at_index(
    section_map: list[tuple[str, list[str]]],
    chord_index: int,
) -> tuple[str, str]:
    """Return (section, concert_chord) for a sticky global index."""
    try:
        from improvisation_motif import flatten_section_map, section_and_chord_at_global_index

        flat = flatten_section_map(section_map)
        if not flat:
            return "", ""
        idx = max(0, min(int(chord_index), len(flat) - 1))
        sec, ch = section_and_chord_at_global_index(section_map, idx)
        return str(sec or "").strip(), str(ch or "").strip()
    except Exception:
        return "", ""


def resolve_mission_projection_state(
    session: dict[str, Any],
    *,
    section_map: list[tuple[str, list[str]]] | None,
    fallback_key: str = "C",
) -> MissionProjectionState:
    """Index-sticky concert chord, then one Shape/Written projection for display."""
    concert_key, chart_key = concert_and_chart_keys(session, fallback=fallback_key)
    try:
        idx = int(session.get(II_SELECTED_CHORD_INDEX, 0) or 0)
    except (TypeError, ValueError):
        idx = 0
    section_label = str(session.get(II_SELECTED_SECTION) or "").strip()
    concert_chord = str(session.get(II_SELECTED_CHORD) or "").strip()
    if section_map:
        try:
            from creative_chord_selection_authority import resolve_authoritative_chord_selection

            concert_chord, section_label, idx = resolve_authoritative_chord_selection(session, section_map)
        except ImportError:
            pass
        at_sec, at_ch = concert_chord_at_index(section_map, idx)
        if at_ch:
            concert_chord = at_ch
            section_label = at_sec or section_label
            try:
                from creative_chord_selection_authority import write_authoritative_chord_selection

                write_authoritative_chord_selection(
                    session,
                    section_map,
                    chord_symbol=concert_chord,
                    section_label=section_label,
                    chord_index=idx,
                )
            except ImportError:
                session[II_SELECTED_CHORD] = concert_chord
                session[II_SELECTED_SECTION] = section_label
                session[II_SELECTED_CHORD_INDEX] = int(idx)
    display_chord = display_chord_from_concert(
        concert_chord,
        concert_key=concert_key,
        chart_key=chart_key,
    )
    return MissionProjectionState(
        concert_key=concert_key,
        chart_key=chart_key,
        concert_chord=concert_chord,
        display_chord=display_chord,
        section_label=section_label or "Progression",
        chord_index=int(idx),
    )


def example_needs_chart_reproject(
    example: Any,
    state: MissionProjectionState,
) -> bool:
    """True when stored example heading/notes/insight still belong to a prior key/chord."""
    if example is None:
        return False
    motif = example.motif if isinstance(getattr(example, "motif", None), dict) else {}
    projected = str(motif.get("_projected_display_key") or "").strip()
    motif_chord = str(motif.get("chord") or "").strip()
    concert_stored = str(motif.get("_concert_chord") or getattr(example, "chord", "") or "").strip()
    insight = getattr(example, "insight", None)
    insight_chord = str(getattr(insight, "chord", "") or "").strip()
    abc = str(getattr(example, "abc", "") or "")
    display = str(state.display_chord or "").strip()
    chart = str(state.chart_key or "").strip()
    concert = str(state.concert_key or "").strip()
    if projected != chart:
        return True
    if str(getattr(example, "concert_key", "") or "").strip() != concert:
        return True
    if display and motif_chord and motif_chord != display:
        return True
    if concert_stored and state.concert_chord and concert_stored != state.concert_chord:
        return True
    if display and insight_chord and insight_chord != display:
        return True
    if display and abc and f"— {display}" not in abc and display not in abc.split("K:", 1)[0]:
        return True
    tones = list(getattr(insight, "chord_tones", None) or [])
    if display and tones:
        from music_theory import chord_root_for_theory, normalize_root

        root = normalize_root(chord_root_for_theory(display) or display)
        tone0 = normalize_root(str(tones[0] or ""))
        if root and tone0 and root != tone0:
            return True
    return False


__all__ = [
    "MissionProjectionState",
    "concert_and_chart_keys",
    "concert_chord_at_index",
    "display_chord_from_concert",
    "example_needs_chart_reproject",
    "resolve_mission_projection_state",
]

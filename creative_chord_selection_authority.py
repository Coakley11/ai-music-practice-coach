"""Section + symbol authoritative chord selection (deduped section map)."""

from __future__ import annotations

from typing import Any

II_SELECTED_CHORD = "ii_selected_chord"
II_SELECTED_SECTION = "ii_selected_section"
II_SELECTED_CHORD_INDEX = "ii_selected_chord_index"
II_SELECTED_CHORD_LABEL = "ii_selected_chord_label"


def global_chord_index_for_section_chord(
    section_map: list[tuple[str, list[str]]],
    section_label: str,
    chord_symbol: str,
) -> int | None:
    """Global flat index for an exact (section, symbol) pair in the UI section map."""
    sec = str(section_label or "").strip()
    sym = str(chord_symbol or "").strip()
    if not sec or not sym or not section_map:
        return None
    try:
        from improvisation_motif import global_chord_index
    except ImportError:
        return None
    for si, (label, chords) in enumerate(section_map):
        if str(label or "").strip() != sec:
            continue
        for ci, ch in enumerate(chords):
            if str(ch or "").strip() == sym:
                return int(global_chord_index(section_map, si, ci))
    return None


def section_chord_at_global_index(
    section_map: list[tuple[str, list[str]]],
    global_idx: int,
) -> tuple[str, str]:
    try:
        from improvisation_motif import section_and_chord_at_global_index

        sec, ch = section_and_chord_at_global_index(section_map, int(global_idx))
        return str(sec or "").strip(), str(ch or "").strip()
    except ImportError:
        return "", ""


def authoritative_pair_matches_index(
    section_map: list[tuple[str, list[str]]] | None,
    *,
    section_label: str,
    chord_symbol: str,
    chord_index: int,
) -> bool:
    if not section_map:
        return False
    sec = str(section_label or "").strip()
    sym = str(chord_symbol or "").strip()
    if not sec or not sym:
        return False
    at_sec, at_ch = section_chord_at_global_index(section_map, int(chord_index))
    return at_sec == sec and at_ch == sym


def resolve_authoritative_chord_selection(
    session: dict[str, Any],
    section_map: list[tuple[str, list[str]]],
) -> tuple[str, str, int]:
    """
    Return (chord_symbol, section_label, global_index) from session authority fields.
    Recomputes index from (section, symbol) only when index does not match that pair on the map.
    """
    sym = str(session.get(II_SELECTED_CHORD) or "").strip()
    sec = str(session.get(II_SELECTED_SECTION) or "").strip()
    try:
        idx = int(session.get(II_SELECTED_CHORD_INDEX, -1))
    except (TypeError, ValueError):
        idx = -1

    if sym and sec and authoritative_pair_matches_index(
        section_map, section_label=sec, chord_symbol=sym, chord_index=idx
    ):
        return sym, sec, idx

    try:
        from improvisation_motif import flatten_section_map

        flat_early = flatten_section_map(section_map)
    except ImportError:
        flat_early = [ch for _l, chs in section_map for ch in chs]
    if flat_early and 0 <= idx < len(flat_early):
        at_sec, at_ch = section_chord_at_global_index(section_map, idx)
        if at_ch and (not sym or at_ch != sym):
            # Stale original-key symbol after Practice Key / Shape change.
            return at_ch, at_sec or sec, idx

    if sym and sec:
        matches: list[int] = []
        try:
            from improvisation_motif import global_chord_index
        except ImportError:
            global_chord_index = None  # type: ignore[assignment,misc]
        for si, (label, chords) in enumerate(section_map):
            if str(label or "").strip() != sec:
                continue
            for ci, ch in enumerate(chords):
                if str(ch or "").strip() == sym and global_chord_index is not None:
                    matches.append(int(global_chord_index(section_map, si, ci)))
        if len(matches) == 1:
            return sym, sec, matches[0]
        if len(matches) > 1 and idx in matches:
            return sym, sec, idx
        if len(matches) > 1:
            return sym, sec, matches[0]

    if sym and sec:
        mapped = global_chord_index_for_section_chord(section_map, sec, sym)
        if mapped is not None:
            return sym, sec, mapped

    flat: list[str] = []
    try:
        from improvisation_motif import flatten_section_map

        flat = flatten_section_map(section_map)
    except ImportError:
        flat = [ch for _l, chs in section_map for ch in chs]

    if flat:
        # Index is sticky across Practice Key / Shape projection. A leftover
        # original-key symbol (e.g. F#m while the concert map is now Dm) must
        # not steal selection away from the highlighted tile.
        if 0 <= idx < len(flat):
            at_sec, at_ch = section_chord_at_global_index(section_map, idx)
            if at_ch:
                if not sec:
                    sec = at_sec
                if not sec or at_sec == sec or (at_sec and not sym):
                    return at_ch, at_sec or sec, idx
                if at_ch == sym:
                    return at_ch, at_sec or sec, idx
                return at_ch, at_sec or sec, idx
        if 0 <= idx < len(flat) and sym and flat[idx] == sym:
            at_sec, at_ch = section_chord_at_global_index(section_map, idx)
            if at_sec and not sec:
                sec = at_sec
            if at_ch and (not sec or at_sec == sec):
                return at_ch, at_sec or sec, idx
        if sym:
            for si, (label, chords) in enumerate(section_map):
                for ci, ch in enumerate(chords):
                    if ch == sym and (not sec or label == sec):
                        try:
                            from improvisation_motif import global_chord_index

                            return sym, str(label), int(global_chord_index(section_map, si, ci))
                        except ImportError:
                            return sym, str(label), 0
        idx = max(0, min(idx if idx >= 0 else 0, len(flat) - 1))
        at_sec, at_ch = section_chord_at_global_index(section_map, idx)
        return at_ch or flat[idx], at_sec, idx

    return sym or "", sec or "", max(0, idx)


def write_authoritative_chord_selection(
    session: dict[str, Any],
    section_map: list[tuple[str, list[str]]],
    *,
    chord_symbol: str,
    section_label: str,
    chord_index: int | None = None,
) -> tuple[str, str, int]:
    """Normalize session keys to (section, symbol) with index derived from section_map when possible."""
    sym = str(chord_symbol or "").strip()
    sec = str(section_label or "").strip()
    gidx: int | None = None
    if chord_index is not None:
        try:
            cand = int(chord_index)
            if sym and sec and authoritative_pair_matches_index(
                section_map, section_label=sec, chord_symbol=sym, chord_index=cand
            ):
                gidx = cand
        except (TypeError, ValueError):
            gidx = None
    if gidx is None and sym and sec:
        mapped = global_chord_index_for_section_chord(section_map, sec, sym)
        if mapped is not None:
            gidx = mapped
    if gidx is None:
        gidx = 0
    if sym and sec and not authoritative_pair_matches_index(
        section_map, section_label=sec, chord_symbol=sym, chord_index=gidx
    ):
        rsym, rsec, ridx = resolve_authoritative_chord_selection(
            {
                II_SELECTED_CHORD: sym,
                II_SELECTED_SECTION: sec,
                II_SELECTED_CHORD_INDEX: gidx,
            },
            section_map,
        )
        sym, sec, gidx = rsym, rsec, ridx
    label = f"{sec} · {sym}" if sec else sym
    session[II_SELECTED_CHORD] = sym
    session[II_SELECTED_SECTION] = sec
    session[II_SELECTED_CHORD_INDEX] = int(gidx)
    session[II_SELECTED_CHORD_LABEL] = label
    session["harmony_map_chord"] = sym
    session["harmony_map_section"] = sec
    return sym, sec, int(gidx)


def read_mission_section_map_from_session(session: dict[str, Any]) -> list[tuple[str, list[str]]]:
    try:
        from creative_mission_config_persistence import IMPROV_MISSION_SECTION_MAP_SESSION_KEY

        raw = session.get(IMPROV_MISSION_SECTION_MAP_SESSION_KEY)
    except ImportError:
        raw = session.get("_improv_mission_section_map")
    if isinstance(raw, list) and raw:
        out: list[tuple[str, list[str]]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out.append((str(item[0]), list(item[1])))
        if out:
            return out
    return []


def read_authoritative_mission_chord_selection(
    session: dict[str, Any],
    section_map: list[tuple[str, list[str]]] | None = None,
) -> tuple[str, str, int]:
    sm = section_map or read_mission_section_map_from_session(session)
    if not sm:
        sym = str(session.get(II_SELECTED_CHORD) or "").strip()
        sec = str(session.get(II_SELECTED_SECTION) or "").strip()
        try:
            idx = int(session.get(II_SELECTED_CHORD_INDEX, 0))
        except (TypeError, ValueError):
            idx = 0
        return sym, sec, idx
    return resolve_authoritative_chord_selection(session, sm)


def deduped_section_map_for_focus(session: dict[str, Any], ctx: Any) -> list[tuple[str, list[str]]]:
    """Same deduped progression shape used by Harmony / Missions chord maps."""
    try:
        from improvisation_motif import (
            concert_song_sections_from_session,
            dedupe_sections_for_display,
            resolve_improv_sections,
        )
        from mission_workflow_context import resolve_missions_section_map
    except ImportError:
        return _section_map_fallback_raw(session, ctx)

    tab = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "")
    if tab == "Missions":
        try:
            mapped, _owner = resolve_missions_section_map(session, ctx)
            if mapped:
                return mapped
        except ImportError:
            pass
    concert = concert_song_sections_from_session(session)
    if concert:
        order = list(getattr(ctx, "section_order", None) or concert.keys())
        mapped = dedupe_sections_for_display(concert, section_names=order or None)
        if mapped:
            return mapped
    mapped = resolve_improv_sections(session, ctx)
    if mapped:
        return mapped
    return _section_map_fallback_raw(session, ctx)


def _section_map_fallback_raw(session: dict[str, Any], ctx: Any) -> list[tuple[str, list[str]]]:
    raw = session.get("improv_song_concert_sections") or session.get("home_sections") or {}
    if isinstance(raw, dict) and raw:
        order = list(getattr(ctx, "section_order", None) or raw.keys())
        try:
            from improvisation_motif import dedupe_sections_for_display

            return dedupe_sections_for_display(
                {str(k): list(v) for k, v in raw.items() if isinstance(v, list)},
                section_names=order or None,
            )
        except ImportError:
            return [(str(k), list(v)) for k, v in raw.items() if isinstance(v, list)]
    return []


__all__ = [
    "authoritative_pair_matches_index",
    "deduped_section_map_for_focus",
    "global_chord_index_for_section_chord",
    "read_authoritative_mission_chord_selection",
    "read_mission_section_map_from_session",
    "resolve_authoritative_chord_selection",
    "section_chord_at_global_index",
    "write_authoritative_chord_selection",
]

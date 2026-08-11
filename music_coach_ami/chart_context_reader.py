"""Read-only active chart harmony for Music Coach — consumer only, no chart writes."""

from __future__ import annotations

from typing import Any


def _clean(text: object) -> str:
    return str(text or "").strip()


def _sections_dict(raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, chords in raw.items():
        if not isinstance(chords, list):
            continue
        cleaned = [_clean(c) for c in chords if _clean(c)]
        if cleaned:
            out[_clean(name)] = cleaned
    return out


def _pick_active_section(section_names: list[str], requested: str) -> str:
    req = _clean(requested)
    if req and req in section_names:
        return req
    if req:
        req_low = req.lower()
        for name in section_names:
            if name.lower() == req_low:
                return name
    return section_names[0] if section_names else ""


def resolve_coach_chart_snapshot(
    session_state: dict[str, Any],
    *,
    ami_ctx: dict[str, Any] | None = None,
    active_section: str = "",
    pick_key: str = "",
    song_original_key: str = "",
    practice_key: str = "",
) -> dict[str, Any]:
    """Layered read-only chart resolution for coach solvers."""
    ctx = dict(ami_ctx or {})
    session = session_state if isinstance(session_state, dict) else {}
    sections: dict[str, list[str]] = {}
    source = ""
    original_key = _clean(song_original_key)
    meter = _clean(ctx.get("chart_meter") or ctx.get("time_signature") or "")
    bpm = ctx.get("bpm")

    if isinstance(ctx.get("chart_sections"), dict):
        sections = _sections_dict(ctx["chart_sections"])
        source = "ami_ctx.chart_sections"
    if not sections and isinstance(ctx.get("active_song"), dict):
        active = ctx["active_song"]
        sections = _sections_dict(active.get("chart_sections") or active.get("sections"))
        if sections:
            source = "ami_ctx.active_song.sections"
        if not original_key:
            original_key = _clean(active.get("key") or active.get("default_key"))
    if not sections:
        try:
            from music_workflow_song_practice import song_practice_blob

            blob = song_practice_blob(session)
            if blob is not None and isinstance(blob.section_map, dict) and blob.section_map:
                sections = _sections_dict(blob.section_map)
                source = "song_practice_blob.section_map"
                if blob.keys.original_tonic and not original_key:
                    ot = _clean(blob.keys.original_tonic)
                    om = _clean(blob.keys.original_mode).lower()
                    original_key = f"{ot}m" if om == "minor" and not ot.lower().endswith("m") else ot
        except ImportError:
            pass
    if not sections:
        for key in ("improv_song_concert_sections", "home_sections"):
            stored = session.get(key)
            candidate = _sections_dict(stored)
            if candidate and sum(len(v) for v in candidate.values()) > 1:
                sections = candidate
                source = f"session.{key}"
                break
    if not sections and pick_key:
        try:
            from songs.music_source import resolve_catalog_song_for_pick

            selected, catalog_original = resolve_catalog_song_for_pick(session, pick_key)
            if isinstance(selected, dict):
                sections = _sections_dict(selected.get("sections"))
                if sections:
                    source = "catalog.resolve_catalog_song_for_pick"
                    if not original_key:
                        original_key = _clean(catalog_original or selected.get("key") or selected.get("default_key"))
        except ImportError:
            pass

    resolved_practice_key = _clean(practice_key or ctx.get("display_key") or session.get("display_key"))
    if not resolved_practice_key:
        try:
            from musical_context_authority import resolve_authoritative_practice_key

            auth = resolve_authoritative_practice_key(session)
            resolved_practice_key = auth.practice_key_token
            if not original_key:
                original_key = auth.original_key_token
        except ImportError:
            resolved_practice_key = resolved_practice_key or original_key or "C"

    if sections and original_key and resolved_practice_key and original_key != resolved_practice_key:
        try:
            from music_theory import transpose_sections_dict

            sections = transpose_sections_dict(sections, original_key, resolved_practice_key)
            source = f"{source}+transpose" if source else "transpose"
        except ImportError:
            pass

    if not meter and sections:
        try:
            from songs.meter import default_time_signature_for_record

            meter = _clean(default_time_signature_for_record({"sections": sections}, sections=sections)) or "4/4"
        except ImportError:
            meter = meter or "4/4"
    if not meter:
        meter = "4/4"

    section_names = list(sections.keys())
    chosen_section = _pick_active_section(section_names, active_section)
    active_chords = list(sections.get(chosen_section) or [])
    if not active_chords and section_names:
        chosen_section = section_names[0]
        active_chords = list(sections.get(chosen_section) or [])

    return {
        "chart_sections": sections,
        "active_section": chosen_section,
        "active_section_chords": active_chords[:8],
        "chart_meter": meter,
        "practice_key": resolved_practice_key or "C",
        "original_key": original_key or resolved_practice_key or "C",
        "chart_source": source or "none",
        "chart_available": bool(active_chords),
        "bpm": int(bpm) if bpm else None,
    }

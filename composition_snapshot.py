"""Single musical snapshot of a composition — shared context for UI and future AI."""

from __future__ import annotations

from typing import Any

from composition_document import chords_for_playback, ordered_sections, playback_globals
from custom_progression_lab import expand_entries_to_chords


def build_composition_snapshot(
    doc: dict[str, Any] | None,
    *,
    active_section_id: str | None = None,
    focus_lane: str = "chords",
) -> dict[str, Any]:
    if not doc:
        return {"empty": True, "focus_lane": focus_lane}

    pg = playback_globals(doc)
    sections = ordered_sections(doc)
    active = None
    for sec in sections:
        if sec.get("id") == active_section_id:
            active = sec
            break
    if active is None and sections:
        active = sections[0]
        active_section_id = str(active.get("id") or "")

    active_chords = expand_entries_to_chords((active or {}).get("chords") or [])
    active_lyrics = list(((active or {}).get("lyrics") or {}).get("lines") or [])
    melody_phrases = list(((active or {}).get("melody") or {}).get("phrases") or [])

    has_melody = bool(melody_phrases)
    has_chords = bool(chords_for_playback(doc, scope="song"))
    has_lyrics = any(
        bool((s.get("lyrics") or {}).get("lines") or (s.get("lyrics") or {}).get("raw_text"))
        for s in sections
    )

    return {
        "empty": False,
        "title": str(doc.get("title") or ""),
        "status": str(doc.get("status") or "draft"),
        "origin_seed": str((doc.get("origin") or {}).get("seed_type") or ""),
        "focus_lane": focus_lane,
        "active_section_id": active_section_id,
        "active_section_label": str((active or {}).get("label_variant") or (active or {}).get("label") or ""),
        "global": pg,
        "form": {
            "section_count": len(sections),
            "section_labels": [
                str(s.get("label_variant") or s.get("label") or "Section") for s in sections
            ],
        },
        "active_section": {
            "chord_symbols": active_chords,
            "chord_count": len(active_chords),
            "lyric_lines": active_lyrics[:8],
            "melody_phrase_count": len(melody_phrases),
        },
        "commitment": {
            "has_melody": has_melody,
            "has_chords": has_chords,
            "has_lyrics": has_lyrics,
        },
        "experiments_available": {
            "reharm": has_melody and has_chords,
            "style_shift": has_chords or bool(pg.get("style")),
            "modulate": has_chords,
            "meter_change": True,
            "intensity": has_chords,
        },
    }


def snapshot_invalidate_token(doc: dict[str, Any] | None) -> str:
    """Cheap hash for cache invalidation when doc changes."""
    if not doc:
        return "empty"
    parts = [
        str(doc.get("updated_at") or ""),
        str(doc.get("id") or ""),
        str(len(chords_for_playback(doc, scope="song"))),
    ]
    return "|".join(parts)

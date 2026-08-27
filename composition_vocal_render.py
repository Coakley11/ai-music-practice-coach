"""Provider-independent vocal / sung-lyric render for Composition Studio.

Builds a lyric-note plan from the canonical melody + syllable alignment.
Does not use ordinary speech TTS as a singing substitute.
"""

from __future__ import annotations

from typing import Any

from composition_document import (
    ordered_sections,
    playback_globals,
    section_by_id,
    section_lyric_alignment,
    section_melody_events,
)

VOCAL_RENDER_STATUS_UNAVAILABLE = "unavailable"
VOCAL_RENDER_STATUS_READY = "ready"
VOCAL_RENDER_PROVIDER = None  # Isolated integration point. No provider is configured.


def vocal_render_available() -> bool:
    return bool(VOCAL_RENDER_PROVIDER)


def vocal_render_unavailable_reason() -> str:
    return (
        "Sung-lyric playback needs a singing-synthesis provider. "
        "Ordinary speech TTS is not used, because it would not follow the melody."
    )


def _pitched_events(events: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    out: list[tuple[int, dict[str, Any]]] = []
    for i, ev in enumerate(events or []):
        if not isinstance(ev, dict):
            continue
        if ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest":
            continue
        out.append((i, ev))
    return out


def _alignment_for_event(alignment: list[dict[str, Any]], event_index: int) -> dict[str, Any] | None:
    for row in alignment:
        if not isinstance(row, dict):
            continue
        indexes = row.get("event_indexes")
        if isinstance(indexes, list) and event_index in indexes:
            return row
        if row.get("event_index") == event_index:
            return row
    return None


def build_vocal_render_plan(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
) -> dict[str, Any]:
    """Canonical lyric-note plan. Safe to persist; contains no audio."""
    pg = playback_globals(doc)
    notes: list[dict[str, Any]] = []
    if str(scope or "section").strip().lower() == "song":
        offset_index = 0
        for sec in ordered_sections(doc):
            sec_events = section_melody_events(sec)
            pitched = _pitched_events(sec_events)
            local_align = section_lyric_alignment(sec)
            for local_i, ev in pitched:
                global_i = offset_index + local_i
                row = _alignment_for_event(local_align, local_i)
                notes.append(
                    {
                        "pitch": ev.get("pitch"),
                        "midi": ev.get("midi"),
                        "beat": ev.get("beat"),
                        "duration_beats": ev.get("duration_beats"),
                        "syllable": (row or {}).get("syllable") or "",
                        "word": (row or {}).get("word") or "",
                        "melisma": bool((row or {}).get("melisma")),
                        "section_id": str(sec.get("id") or ""),
                        "event_index": global_i,
                    }
                )
            offset_index += len(sec_events)
    else:
        sec = section_by_id(doc, str(section_id or "")) if section_id else None
        events = section_melody_events(sec)
        alignment = section_lyric_alignment(sec)
        for i, ev in _pitched_events(events):
            row = _alignment_for_event(alignment, i)
            notes.append(
                {
                    "pitch": ev.get("pitch"),
                    "midi": ev.get("midi"),
                    "beat": ev.get("beat"),
                    "duration_beats": ev.get("duration_beats"),
                    "syllable": (row or {}).get("syllable") or "",
                    "word": (row or {}).get("word") or "",
                    "melisma": bool((row or {}).get("melisma")),
                    "section_id": str(section_id or ""),
                    "event_index": i,
                }
            )
    return {
        "provider": VOCAL_RENDER_PROVIDER,
        "available": vocal_render_available(),
        "reason": "" if vocal_render_available() else vocal_render_unavailable_reason(),
        "scope": "song" if str(scope or "").strip().lower() == "song" else "section",
        "section_id": str(section_id or ""),
        "bpm": int(pg.get("bpm") or 96),
        "meter": str(pg.get("time_signature") or "4/4"),
        "key": str(pg.get("key_center") or "C"),
        "notes": notes,
        "note_count": len(notes),
        "aligned_count": sum(1 for n in notes if str(n.get("syllable") or "").strip()),
    }


def render_vocal_audio(plan: dict[str, Any] | None) -> dict[str, Any]:
    """Attempt sung-lyric render. Never returns speech-TTS audio as a success."""
    payload = plan if isinstance(plan, dict) else {}
    # Provider hook is isolated here. Until a singing synthesizer is wired,
    # report unavailable rather than substituting speech TTS.
    return {
        "status": VOCAL_RENDER_STATUS_UNAVAILABLE,
        "audio": None,
        "message": str(payload.get("reason") or vocal_render_unavailable_reason()),
        "plan": payload,
    }

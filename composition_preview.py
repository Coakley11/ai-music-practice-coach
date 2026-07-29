"""Audition backing audio for Composition Studio."""

from __future__ import annotations

from typing import Any

from composition_document import chords_for_playback, playback_globals


def preview_signature(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
) -> tuple:
    pg = playback_globals(doc)
    chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    return (
        str(doc.get("id") or ""),
        scope,
        section_id or "",
        tuple(chords),
        pg["bpm"],
        pg["time_signature"],
        pg["style"],
        pg["groove"],
        int(loops),
    )


def generate_preview_wav(
    doc: dict[str, Any],
    *,
    scope: str = "section",
    section_id: str | None = None,
    loops: int = 2,
    level: str = "Intermediate",
) -> bytes | None:
    chords = chords_for_playback(doc, scope=scope, section_id=section_id)
    if not chords:
        return None
    pg = playback_globals(doc)
    from backing_audio import generate_backing_track

    return generate_backing_track(
        chords,
        bpm=pg["bpm"],
        loops=max(1, int(loops)),
        style=pg["groove"],
        level=level,
        song_title=str(doc.get("title") or "Composition"),
        song_artist="",
        time_signature=pg["time_signature"],
        mood=pg.get("mood") or "",
    )


def invalidate_composer_preview(session_state: dict) -> None:
    session_state.pop("composer_preview_wav", None)
    session_state.pop("composer_preview_signature", None)

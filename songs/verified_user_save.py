"""Atomic save + activity log for user-verified charts and lyrics."""

from __future__ import annotations

from typing import Any

from song_catalog.user_overrides import USER_VERIFIED, save_user_override
from song_catalog.user_song_content import CONTENT_USER_VERIFIED, save_user_song_content
from songs.state import SELECTED_SONG_STATE_KEY


def canonical_song_identity(
    session_state: dict[str, Any],
    song_data: dict[str, Any],
) -> tuple[str, str, str]:
    """Title/artist/genre from master selection (stable override storage keys)."""
    sel = session_state.get(SELECTED_SONG_STATE_KEY) or {}
    title = str(sel.get("title") or song_data.get("title") or "").strip()
    artist = str(sel.get("artist") or song_data.get("artist") or "").strip()
    genre = str(sel.get("genre") or song_data.get("genre") or "").strip()
    return title, artist, genre


def record_verified_user_activity(
    st: Any,
    *,
    title: str,
    artist: str,
    edited_fields: list[str],
    pick_key: str = "",
) -> None:
    if not edited_fields:
        return
    fields = sorted(set(edited_fields))
    try:
        from suite_activity_client import record_activity

        from songs.state import build_music_local_state

        local_state = build_music_local_state(st)
        summary_parts = []
        if "chords" in fields:
            summary_parts.append(f"Saved verified chords for {title}")
        if "lyrics" in fields:
            summary_parts.append(f"Updated lyrics for {title}")
        summary = " · ".join(summary_parts) if summary_parts else f"Verified save for {title}"
        record_activity(
            "music",
            "verified_chart_saved",
            page=str(st.session_state.get("studio_page") or "Song Picker"),
            metrics={
                "song": title,
                "artist": artist,
                "edited_fields": fields,
                "pick_key": pick_key,
            },
            summary=summary,
            resume_key=f"song:{pick_key or title}",
            resume_title=f"Continue: {title}",
            resume_subtitle=artist,
            local_state=local_state,
        )
    except Exception:
        pass


def save_verified_chart(
    *,
    title: str,
    artist: str,
    genre: str,
    key: str,
    sections: dict[str, list[str]],
    chart_versions: dict[str, dict[str, list[str]]],
    section_order: list[str],
    edited_level: str,
    catalog_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return save_user_override(
        title=title,
        artist=artist,
        genre=genre,
        key=key,
        sections=sections,
        chart_versions=chart_versions,
        section_order=section_order,
        override_status=USER_VERIFIED,
        edited_level=edited_level,
        catalog_snapshot=catalog_snapshot,
    )


def save_verified_lyrics(
    *,
    title: str,
    artist: str,
    genre: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not (
        payload.get("section_lyrics")
        or payload.get("lyric_cues")
        or payload.get("performance_notes")
    ):
        return None
    return save_user_song_content(
        title=title,
        artist=artist,
        genre=genre,
        content_status=CONTENT_USER_VERIFIED,
        **payload,
    )

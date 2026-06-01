"""Session + disk resolution for user lyrics, cues, and performance notes."""

from __future__ import annotations

import re
from typing import Any

from song_catalog.user_overrides import USER_VERIFIED
from song_catalog.user_song_content import (
    CONTENT_MY_VERSION,
    CONTENT_SESSION,
    CONTENT_USER_VERIFIED,
    get_user_song_content,
    save_user_song_content,
)

PERFORMANCE_CUE_PRESETS: tuple[str, ...] = (
    "Soft entrance",
    "Breathe here",
    "Pause",
    "Crescendo",
    "Emphasize word",
    "Strong finish",
    "Vocal harmony",
    "Instrument break",
)

_LYRICS_HYDRATED_AT = "_lyrics_hydrated_at"
_LYRICS_SAVE_TIER = "_lyrics_save_tier"
_LYRICS_DIRTY = "_lyrics_dirty"
_LYRICS_SAVE_NOTICE = "_lyrics_save_notice"


def song_lyrics_slug(title: str, artist: str) -> str:
    base = f"{title}_{artist}".lower()
    return re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_") or "song"


def lyrics_session_keys(title: str, artist: str) -> dict[str, str]:
    slug = song_lyrics_slug(title, artist)
    return {
        "slug": slug,
        "song_lyrics": f"song_lyrics::{slug}",
        "section_lyrics": f"section_lyrics::{slug}",
        "lyric_cues": f"lyric_cues::{slug}",
        "section_layout": f"lyrics_section_layout::{slug}",
        "performance_notes": f"performance_notes::{slug}",
        "karaoke_markers": f"karaoke_markers::{slug}",
        "save_tier": f"{_LYRICS_SAVE_TIER}::{slug}",
        "dirty": f"{_LYRICS_DIRTY}::{slug}",
        "hydrated_at": f"{_LYRICS_HYDRATED_AT}::{slug}",
    }


def mark_lyrics_dirty(session_state: dict, slug: str) -> None:
    session_state[f"{_LYRICS_DIRTY}::{slug}"] = True


def lyrics_save_status(session_state: dict, *, slug: str, title: str, artist: str) -> str:
    """Return: unsaved | session | my_version | user_verified."""
    if session_state.get(f"{_LYRICS_DIRTY}::{slug}"):
        return "unsaved"
    tier = session_state.get(f"{_LYRICS_SAVE_TIER}::{slug}")
    if tier == CONTENT_SESSION:
        return "session"
    entry = get_user_song_content(title, artist)
    if entry:
        status = entry.get("content_status", CONTENT_MY_VERSION)
        if status in {CONTENT_USER_VERIFIED, USER_VERIFIED}:
            return "user_verified"
        return "my_version"
    if tier == CONTENT_MY_VERSION:
        return "my_version"
    return "catalog"


def lyrics_status_label(status: str) -> str:
    return {
        "unsaved": "Unsaved changes",
        "session": "Saved for this session only",
        "my_version": "Using User Lyrics",
        "user_verified": "Using User Verified Lyrics",
        "catalog": "No saved lyrics yet",
    }.get(status, status)


def lyrics_active_source_label(
    session_state: dict,
    *,
    title: str,
    artist: str,
) -> tuple[str, str]:
    """Return (banner text, kind) where kind is ``user`` or ``empty``."""
    status = lyrics_save_status(
        session_state,
        slug=song_lyrics_slug(title, artist),
        title=title,
        artist=artist,
    )
    if status in {"my_version", "user_verified", "session"}:
        if status == "user_verified":
            return ("Using User Verified Lyrics", "user")
        return ("Using User Lyrics", "user")
    return ("No saved lyrics yet", "empty")


def hydrate_user_lyrics_session(
    session_state: dict,
    *,
    title: str,
    artist: str,
    force: bool = False,
) -> None:
    """Load disk-backed lyrics into session when the active song changes."""
    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]
    entry = get_user_song_content(title, artist)
    saved_at = (entry or {}).get("saved_at")
    if not force and session_state.get(keys["hydrated_at"]) == saved_at and saved_at:
        return

    if entry:
        session_state[keys["section_lyrics"]] = dict(entry.get("section_lyrics") or {})
        session_state[keys["lyric_cues"]] = {
            k: list(v) for k, v in (entry.get("lyric_cues") or {}).items()
        }
        if entry.get("section_layout"):
            session_state[keys["section_layout"]] = list(entry["section_layout"])
        session_state[keys["performance_notes"]] = str(entry.get("performance_notes") or "")
        session_state[keys["karaoke_markers"]] = dict(entry.get("karaoke_markers") or {})
        session_state[keys["save_tier"]] = entry.get("content_status", CONTENT_MY_VERSION)
        session_state.pop(f"{_LYRICS_DIRTY}::{slug}", None)
    else:
        session_state.setdefault(keys["section_lyrics"], {})
        session_state.setdefault(keys["lyric_cues"], {})
        session_state.setdefault(keys["performance_notes"], "")
        session_state.setdefault(keys["karaoke_markers"], {})

    session_state[keys["hydrated_at"]] = saved_at
    session_state.pop(f"{_LYRICS_SAVE_NOTICE}::{slug}", None)


def collect_lyrics_payload(
    session_state: dict,
    *,
    title: str,
    artist: str,
    section_names: list[str],
) -> dict[str, Any]:
    keys = lyrics_session_keys(title, artist)
    section_lyrics: dict[str, str] = {}
    for section_name in section_names:
        from songs.lyrics_editor import section_lyrics_widget_key

        wkey = section_lyrics_widget_key(keys["slug"], section_name)
        raw = session_state.get(wkey, "")
        if not raw:
            raw = (session_state.get(keys["section_lyrics"]) or {}).get(section_name, "")
        text = str(raw or "").strip()
        if text:
            section_lyrics[section_name] = text

    store = session_state.get(keys["section_lyrics"]) or {}
    for section_name, text in store.items():
        if section_name not in section_lyrics and str(text or "").strip():
            section_lyrics[section_name] = str(text).strip()

    lyric_cues: dict[str, list[str]] = {}
    cues_store = session_state.get(keys["lyric_cues"]) or {}
    for section_name in section_names:
        cue_key = f"lyric_cues_edit::{keys['slug']}::{section_name}"
        raw_cues = session_state.get(cue_key)
        if raw_cues is None:
            raw_cues = cues_store.get(section_name, [])
        if isinstance(raw_cues, str):
            lines = [ln.strip() for ln in raw_cues.splitlines() if ln.strip()]
        elif isinstance(raw_cues, list):
            lines = [str(c).strip() for c in raw_cues if str(c).strip()]
        else:
            lines = []
        if lines:
            lyric_cues[section_name] = lines

    layout = session_state.get(keys["section_layout"])
    if not isinstance(layout, list):
        layout = list(section_names)

    return {
        "section_lyrics": section_lyrics,
        "lyric_cues": lyric_cues,
        "section_layout": layout,
        "performance_notes": str(session_state.get(keys["performance_notes"]) or "").strip(),
        "karaoke_markers": dict(session_state.get(keys["karaoke_markers"]) or {}),
    }


def save_lyrics_for_session(session_state: dict, *, title: str, artist: str) -> None:
    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]
    session_state[keys["save_tier"]] = CONTENT_SESSION
    session_state.pop(f"{_LYRICS_DIRTY}::{slug}", None)
    session_state[f"{_LYRICS_SAVE_NOTICE}::{slug}"] = (
        "Saved for this session — available until you refresh or restart the app."
    )


def save_lyrics_my_version(
    session_state: dict,
    *,
    title: str,
    artist: str,
    genre: str,
    section_names: list[str],
) -> dict[str, Any]:
    payload = collect_lyrics_payload(
        session_state, title=title, artist=artist, section_names=section_names
    )
    entry = save_user_song_content(
        title=title,
        artist=artist,
        genre=genre,
        content_status=CONTENT_MY_VERSION,
        **payload,
    )
    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]
    session_state[keys["save_tier"]] = CONTENT_MY_VERSION
    session_state[keys["hydrated_at"]] = entry.get("saved_at")
    session_state.pop(f"{_LYRICS_DIRTY}::{slug}", None)
    session_state[f"{_LYRICS_SAVE_NOTICE}::{slug}"] = (
        "✅ Lyrics & cues saved successfully — loads when you open this song again."
    )
    return entry


def save_lyrics_user_verified(
    session_state: dict,
    *,
    title: str,
    artist: str,
    genre: str,
    section_names: list[str],
    song_data: dict[str, Any],
    catalog_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist lyrics/cues and align chart override status to user verified."""
    payload = collect_lyrics_payload(
        session_state, title=title, artist=artist, section_names=section_names
    )
    entry = save_user_song_content(
        title=title,
        artist=artist,
        genre=genre,
        content_status=CONTENT_USER_VERIFIED,
        **payload,
    )

    from songs.verified_user_save import mark_chart_verified_from_disk

    mark_chart_verified_from_disk(
        title=title,
        artist=artist,
        genre=genre,
        song_data=song_data,
        catalog_snapshot=catalog_snapshot,
    )

    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]
    session_state[keys["save_tier"]] = CONTENT_USER_VERIFIED
    session_state[keys["hydrated_at"]] = entry.get("saved_at")
    session_state.pop(f"{_LYRICS_DIRTY}::{slug}", None)
    session_state[f"{_LYRICS_SAVE_NOTICE}::{slug}"] = (
        "✅ Saved as user verified — your preferred lyrics, cues, and chart."
    )
    return entry


def revert_user_lyrics(
    session_state: dict,
    *,
    title: str,
    artist: str,
) -> bool:
    """Remove saved user lyrics/cues from disk and clear the editor session."""
    from song_catalog.user_song_content import delete_user_song_content

    deleted = delete_user_song_content(title, artist)
    keys = lyrics_session_keys(title, artist)
    slug = keys["slug"]
    for key in (
        keys["section_lyrics"],
        keys["lyric_cues"],
        keys["song_lyrics"],
        keys["performance_notes"],
        keys["karaoke_markers"],
        keys["section_layout"],
        keys["save_tier"],
        keys["hydrated_at"],
    ):
        session_state.pop(key, None)
    session_state.pop(f"{_LYRICS_DIRTY}::{slug}", None)
    session_state[f"{_LYRICS_SAVE_NOTICE}::{slug}"] = (
        "Reverted — your saved lyrics and cues were removed for this song."
    )
    return deleted


def pop_lyrics_save_notice(session_state: dict, *, title: str, artist: str) -> str | None:
    slug = song_lyrics_slug(title, artist)
    return session_state.pop(f"{_LYRICS_SAVE_NOTICE}::{slug}", None)


def resolve_user_lyrics_and_cues(
    session_state: dict,
    *,
    title: str,
    artist: str,
    song_data: dict[str, Any] | None = None,
    include_catalog_cues: bool = False,
) -> tuple[dict[str, str], dict[str, list[str]], str]:
    """User/session lyrics first; catalog cues only when explicitly allowed."""
    keys = lyrics_session_keys(title, artist)
    section_lyrics = dict(session_state.get(keys["section_lyrics"]) or {})
    lyric_cues = {
        k: list(v) for k, v in (session_state.get(keys["lyric_cues"]) or {}).items()
    }
    performance_notes = str(session_state.get(keys["performance_notes"]) or "").strip()

    if not section_lyrics and not lyric_cues:
        entry = get_user_song_content(title, artist)
        if entry:
            section_lyrics = dict(entry.get("section_lyrics") or {})
            lyric_cues = {
                k: list(v) for k, v in (entry.get("lyric_cues") or {}).items()
            }
            performance_notes = performance_notes or str(entry.get("performance_notes") or "")

    if include_catalog_cues and song_data and not lyric_cues:
        from songs.sheet_format import merge_lyric_cues_for_song

        lyric_cues = merge_lyric_cues_for_song(song_data, {})

    return section_lyrics, lyric_cues, performance_notes

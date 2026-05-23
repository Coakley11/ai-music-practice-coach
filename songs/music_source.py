"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
_LAST_SOURCE_KEY = "_last_active_music_source"


def ensure_active_music_source(session_state: dict[str, Any]) -> None:
    session_state.setdefault(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)


def is_custom_progression(session_state: dict[str, Any]) -> bool:
    return session_state.get(ACTIVE_MUSIC_SOURCE_KEY) == SOURCE_CUSTOM


def set_catalog_source(session_state: dict[str, Any]) -> None:
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG


def set_custom_source(session_state: dict[str, Any]) -> None:
    session_state[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM


def note_active_source_change(st: Any, *, invalidate_backing) -> bool:
    """Invalidate backing cache when the user switches catalog ↔ custom."""
    from .playback_defaults import reset_playback_song_tracking

    session_state = st.session_state
    current = session_state.get(ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG)
    previous = session_state.get(_LAST_SOURCE_KEY)
    session_state[_LAST_SOURCE_KEY] = current
    if previous is not None and previous != current:
        reset_playback_song_tracking(st)
        invalidate_backing(st)
        return True
    return False


def active_source_labels(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` for the sidebar active-source banner."""
    if is_custom_progression(session_state):
        return "Custom Progression", str(custom_name or "Custom Progression")
    title = str(catalog_title or "").strip()
    artist = str(catalog_artist or "").strip()
    detail = f"{title} — {artist}".strip(" —") if title or artist else ""
    return "Song", detail


def _parse_legacy_active_source_markdown(text: str) -> tuple[str, str]:
    """Older builds returned one markdown string (``Song Picker — title — artist``)."""
    raw = str(text or "").replace("**", "").strip()
    if raw.lower().startswith("active source:"):
        raw = raw.split(":", 1)[1].strip()
    parts = [p.strip() for p in raw.split("—") if p.strip()]
    if not parts:
        return "Song", ""
    kind = parts[0].replace("Song Picker", "Song").strip() or "Song"
    detail = " — ".join(parts[1:]) if len(parts) > 1 else ""
    return kind, detail


def unpack_active_source_banner(result: Any) -> tuple[str, str]:
    """Normalize banner return value to exactly ``(kind, detail)``."""
    if isinstance(result, tuple):
        if len(result) >= 2:
            return str(result[0]), str(result[1])
        if len(result) == 1:
            return str(result[0]), ""
        return "Song", ""
    if isinstance(result, str):
        return _parse_legacy_active_source_markdown(result)
    if result is None:
        return "Song", ""
    return "Song", str(result)


def active_source_banner(
    session_state: dict[str, Any],
    *,
    catalog_title: str,
    catalog_artist: str,
    custom_name: str,
) -> tuple[str, str]:
    """Return ``(source_kind, source_detail)`` — always a 2-tuple (never markdown)."""
    kind, detail = active_source_labels(
        session_state,
        catalog_title=catalog_title,
        catalog_artist=catalog_artist,
        custom_name=custom_name,
    )
    return (str(kind), str(detail))


def display_key_context(
    session_state: dict[str, Any],
    *,
    catalog_song_data: dict[str, Any],
    cpl_active_key: str,
) -> tuple[str, tuple]:
    """Original/home key and identity tuple for the global display-key widget."""
    if is_custom_progression(session_state):
        from custom_progression_lab import (
            default_active_progression,
            ensure_original_structure,
            written_home_key,
        )

        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        home = written_home_key(active)
        title = active.get("name", "Custom Progression")
        return home, (title, "Custom progression", home)

    original = catalog_song_data.get("key", "C")
    return original, (
        catalog_song_data.get("title"),
        catalog_song_data.get("artist"),
        original,
    )


def build_active_chart_bundle(
    session_state: dict[str, Any],
    *,
    catalog_genre: str,
    catalog_song: str,
    catalog_song_data: dict[str, Any],
    level: str,
    display_key: str,
    cpl_active_key: str,
    sections_for_level: Callable[[dict, str], dict],
    transpose_sections: Callable[[dict, str], dict],
) -> dict[str, Any]:
    """Resolve genre, song, song_data, and chord sections for the active source."""
    if is_custom_progression(session_state):
        from custom_progression_lab import (
            default_active_progression,
            ensure_all_cpl_sections,
            ensure_original_structure,
            sections_to_chord_lists,
            written_home_key,
        )

        active = ensure_original_structure(
            session_state.get(cpl_active_key) or default_active_progression()
        )
        active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
        session_state[cpl_active_key] = active
        home_key = written_home_key(active)
        home_sections = active.get("original_sections") or {}
        level_source_sections = sections_to_chord_lists(home_sections)
        level_song_data = {
            "key": home_key,
            "sections": level_source_sections,
        }
        sections = transpose_sections(level_song_data, display_key)
        title = active.get("name", "Custom Progression")
        return {
            "source": SOURCE_CUSTOM,
            "genre": "Custom",
            "song": title,
            "song_data": {
                "title": title,
                "artist": "Your progression",
                "genre": "Custom",
                "key": home_key,
                "sections": level_source_sections,
                "chart_status": "custom",
                "trusted_core": False,
            },
            "original_key": home_key,
            "level_source_sections": level_source_sections,
            "sections": sections,
            "cpl_active": active,
            "default_bpm": int(active.get("bpm", 100) or 100),
            "default_loops": int(active.get("loops", 2) or 2),
            "default_groove": active.get("groove_style", "Auto") or "Auto",
            "time_signature": active.get("time_signature", "4/4") or "4/4",
        }

    level_source_sections = sections_for_level(catalog_song_data, level)
    level_song_data = {
        **catalog_song_data,
        "sections": level_source_sections,
    }
    sections = transpose_sections(level_song_data, display_key)
    return {
        "source": SOURCE_CATALOG,
        "genre": catalog_genre,
        "song": catalog_song,
        "song_data": catalog_song_data,
        "original_key": catalog_song_data.get("key", "C"),
        "level_source_sections": level_source_sections,
        "sections": sections,
        "cpl_active": None,
        "default_bpm": 100,
        "default_loops": 2,
        "default_groove": "Auto",
        "time_signature": "4/4",
    }

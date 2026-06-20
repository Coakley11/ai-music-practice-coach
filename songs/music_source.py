"""Active music source: catalog song vs custom progression (shared session contract)."""

from __future__ import annotations

from typing import Any, Callable

ACTIVE_MUSIC_SOURCE_KEY = "active_music_source"
SOURCE_CATALOG = "catalog_song"
SOURCE_CUSTOM = "custom_progression"
_LAST_SOURCE_KEY = "_last_active_music_source"
PENDING_CUSTOM_ACTIVE_SONG_KEY = "_pending_custom_active_song_activation"


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


def custom_pick_key_for(active: dict[str, Any]) -> str:
    """Stable session pick_key for a custom progression (not a catalog pk:: id)."""
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    rev = str(active.get("id") or "").strip()
    if rev:
        return f"custom::{rev}"
    safe = title.replace(":", "_").replace("/", "_")[:80]
    return f"custom::{safe}"


def custom_selected_song_record(active: dict[str, Any]) -> dict[str, Any]:
    """Sidebar/global ``selected_song`` shape for an active custom progression."""
    from custom_progression_lab import ensure_original_structure, written_home_key

    active = ensure_original_structure(active)
    home_key = written_home_key(active)
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    artist = str(active.get("artist") or "Your progression").strip() or "Your progression"
    pick_key = custom_pick_key_for(active)
    return {
        "pick_key": pick_key,
        "title": title,
        "artist": artist,
        "key": home_key,
        "source": SOURCE_CUSTOM,
        "is_custom": True,
    }


def queue_custom_active_song_activation(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    toast_title: str | None = None,
) -> None:
    """Queue CPL activation for the next run (before sidebar/global widgets render)."""
    from custom_progression_lab import ensure_all_cpl_sections, ensure_original_structure

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active
    payload: dict[str, Any] = {"cpl_active_key": cpl_active_key}
    if toast_title:
        payload["toast_title"] = str(toast_title).strip()
    session[PENDING_CUSTOM_ACTIVE_SONG_KEY] = payload


def apply_pending_custom_active_song_activation_before_widgets(
    st: Any,
    *,
    invalidate_backing,
) -> bool:
    """Apply queued CPL activation before any widget-bound session keys are touched."""
    session = st.session_state
    pending = session.pop(PENDING_CUSTOM_ACTIVE_SONG_KEY, None)
    if not isinstance(pending, dict):
        return False
    cpl_active_key = str(pending.get("cpl_active_key") or "cpl_active_progression").strip()
    active = session.get(cpl_active_key)
    if not isinstance(active, dict):
        return False
    commit_custom_active_song(
        st,
        active,
        cpl_active_key=cpl_active_key,
        invalidate_backing=invalidate_backing,
    )
    toast_title = str(pending.get("toast_title") or "").strip()
    if toast_title:
        session["_cpl_activation_toast"] = toast_title
    return True


def commit_custom_active_song(
    st: Any,
    active: dict[str, Any],
    *,
    cpl_active_key: str = "cpl_active_progression",
    invalidate_backing,
) -> dict[str, Any]:
    """Promote CPL draft to the global active song (source, title, key, playback, cloud).

    Must run before sidebar/global widgets render. Use ``queue_custom_active_song_activation``
    from page callbacks, then ``apply_pending_custom_active_song_activation_before_widgets``
    at app startup.
    """
    from custom_progression_lab import (
        ensure_all_cpl_sections,
        ensure_original_structure,
        prepare_cpl_backing_handoff,
        written_home_key,
    )
    from songs.key_state import (
        apply_display_key_for_active_song,
        song_display_identity,
    )
    from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

    session = st.session_state
    active = ensure_original_structure(active)
    active["original_sections"] = ensure_all_cpl_sections(active.get("original_sections"))
    active["user_locked_home_key"] = True
    session[cpl_active_key] = active

    home_key = written_home_key(active)
    selected = custom_selected_song_record(active)
    pick_key = str(selected.get("pick_key") or "").strip()

    set_custom_source(session)
    note_active_source_change(st, invalidate_backing=invalidate_backing)

    session[SELECTED_SONG_STATE_KEY] = selected
    if pick_key:
        session[ACTIVE_CATALOG_PICK_KEY] = pick_key

    identity = song_display_identity(
        selected.get("title", ""),
        selected.get("artist", ""),
        home_key,
    )
    apply_display_key_for_active_song(st, home_key, identity, pending_key=home_key)

    prepare_cpl_backing_handoff(session, active)

    try:
        from active_song_state import write_canonical_active_song_state
        from global_active_song_state import sync_active_song_to_canonical

        ctx = {
            "pick_key": pick_key,
            "display_key": home_key,
            "instrument": str(session.get("instrument") or "").strip(),
            "level": str(session.get("level") or "").strip(),
            "focus": str(session.get("focus") or "").strip(),
            "selected_song": selected,
            "music_source": SOURCE_CUSTOM,
            "custom_progression_name": selected.get("title", ""),
            "custom_home_key": home_key,
        }
        write_canonical_active_song_state(
            session,
            ctx,
            reason="custom_active_song",
            local_edit=True,
        )
        sync_active_song_to_canonical(session)
    except ImportError:
        pass

    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
    except ImportError:
        pass

    return active


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

    from backing_audio import infer_groove_style
    from .playback_defaults import default_bpm_for_song_data, default_groove_for_song

    level_source_sections = sections_for_level(catalog_song_data, level)
    level_song_data = {
        **catalog_song_data,
        "sections": level_source_sections,
    }
    sections = transpose_sections(level_song_data, display_key)
    ext = catalog_song_data.get("extensions") or {}
    return {
        "source": SOURCE_CATALOG,
        "genre": catalog_genre,
        "song": catalog_song,
        "song_data": catalog_song_data,
        "original_key": catalog_song_data.get("key", "C"),
        "level_source_sections": level_source_sections,
        "sections": sections,
        "cpl_active": None,
        "default_bpm": default_bpm_for_song_data(catalog_song_data),
        "default_loops": int(ext.get("default_loops", 2) or 2),
        "default_groove": default_groove_for_song(
            catalog_song_data,
            infer_fn=infer_groove_style,
        ),
        "time_signature": ext.get("time_signature", "4/4") or "4/4",
    }

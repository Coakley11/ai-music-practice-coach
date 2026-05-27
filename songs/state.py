"""Single master selected song for the whole Streamlit app."""

from __future__ import annotations

from typing import Any

from song_catalog import format_pick_key, parse_pick_key, resolve_pick_key

from .key_state import (
    BACKING_NEEDS_REGEN,
    IDENTITY_KEY,
    LAST_DISPLAY_KEY,
    PENDING_DISPLAY_KEY,
    invalidate_backing_cache,
)
from .playback_defaults import (
    active_song_sync_id,
    canonical_active_song_bpm,
    playback_song_id,
    prime_active_song_bpm,
    reset_playback_song_tracking,
)

SELECTED_SONG_STATE_KEY = "selected_song"
ACTIVE_CATALOG_PICK_KEY = "active_catalog_pick_key"
PENDING_MATCHING_SONG_DROPDOWN = "_pending_matching_song_dropdown"
_LAST_PICK_KEY = "_master_song_pick_key"


def sync_matching_song_dropdown_before_widget(
    st: Any,
    pick_options: list[str],
    fallback_pk: str,
) -> str:
    """Align the dropdown widget with ``ACTIVE_CATALOG_PICK_KEY`` before it is drawn.

    Never assign ``matching_song_dropdown`` after the selectbox exists — use pending
    values applied on the next run only.
    """
    if not pick_options:
        return fallback_pk

    fallback = fallback_pk if fallback_pk in pick_options else pick_options[0]
    active = st.session_state.get(ACTIVE_CATALOG_PICK_KEY) or fallback
    if active not in pick_options:
        active = fallback
        st.session_state[ACTIVE_CATALOG_PICK_KEY] = active

    pending = st.session_state.pop(PENDING_MATCHING_SONG_DROPDOWN, None)
    if pending in pick_options:
        st.session_state["matching_song_dropdown"] = pending
    elif st.session_state.get("matching_song_dropdown") not in pick_options:
        st.session_state["matching_song_dropdown"] = active

    return active


def _label_for_library_entry(genre: str, title: str, song_library: dict) -> str:
    artist = song_library[genre][title]["artist"]
    return f"{title} — {artist}"


def ensure_master_song_initialized(
    st: Any,
    *,
    all_records: list[dict[str, Any]],
    song_library: dict[str, dict[str, dict]],
    song_picker_catalog: dict[str, dict[str, dict]],
) -> None:
    """Pick a default song once; migrate legacy sidebar session keys if present."""
    if (
        SELECTED_SONG_STATE_KEY in st.session_state
        and st.session_state[SELECTED_SONG_STATE_KEY]
        and st.session_state[SELECTED_SONG_STATE_KEY].get("pick_key")
    ):
        return

    # Migrate from pre-refactor keys
    legacy_g = st.session_state.get("active_genre")
    legacy_t = st.session_state.get("active_song_title")
    if (
        legacy_g
        and legacy_t
        and legacy_g in song_library
        and legacy_t in song_library[legacy_g]
    ):
        label = _label_for_library_entry(legacy_g, legacy_t, song_library)
        if legacy_g in song_picker_catalog and label in song_picker_catalog[legacy_g]:
            apply_pick_key(st, format_pick_key(legacy_g, label), song_picker_catalog)
            return

    r0 = all_records[0]
    label0 = f"{r0['title']} — {r0['artist']}"
    pk = format_pick_key(r0["genre"], label0)
    apply_pick_key(st, pk, song_picker_catalog)


def apply_pick_key(
    st: Any,
    pick_key: str,
    song_picker_catalog: dict[str, dict[str, dict]],
    *,
    song_library: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any]:
    resolved = resolve_pick_key(pick_key, song_picker_catalog=song_picker_catalog)
    if not resolved:
        existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
        if isinstance(existing, dict) and existing.get("title"):
            return existing
        for genre, labels in song_picker_catalog.items():
            if labels:
                first_label = next(iter(labels))
                resolved = format_pick_key(genre, first_label)
                break
        if not resolved:
            return {}
    pick_key = resolved
    genre, label = parse_pick_key(pick_key)
    if genre not in song_picker_catalog or label not in song_picker_catalog[genre]:
        existing = st.session_state.get(SELECTED_SONG_STATE_KEY)
        return existing if isinstance(existing, dict) else {}
    data = song_picker_catalog[genre][label]
    st.session_state[SELECTED_SONG_STATE_KEY] = {
        "pick_key": pick_key,
        "title": data["title"],
        "artist": data["artist"],
        "genre": genre,
        "label": label,
    }
    prev = st.session_state.get(_LAST_PICK_KEY)
    st.session_state[_LAST_PICK_KEY] = pick_key
    st.session_state["active_genre"] = genre
    st.session_state["active_song_title"] = data["title"]
    if prev is not None and prev != pick_key:
        st.session_state[PENDING_DISPLAY_KEY] = data["key"]
        st.session_state[IDENTITY_KEY] = (data["title"], data["artist"], data["key"])
        st.session_state[LAST_DISPLAY_KEY] = data["key"]
        reset_playback_song_tracking(st)
        invalidate_backing_cache(st)
        st.session_state[BACKING_NEEDS_REGEN] = False
        st.session_state.pop("multitrack_backing_wav", None)
        st.session_state.pop("multitrack_backing_music_wav", None)
        st.session_state.pop("mixed_track_wav", None)
        lib_record = data
        if song_library is not None:
            lib_record = song_library.get(genre, {}).get(data["title"], data)
        _pid = playback_song_id(
            is_custom=False,
            song_title=data["title"],
            song_artist=data.get("artist", ""),
        )
        _sync_id = active_song_sync_id(pick_key=pick_key, playback_song_id=_pid, is_custom=False)
        prime_active_song_bpm(
            st,
            sync_id=_sync_id,
            active_song_bpm=canonical_active_song_bpm(lib_record),
        )
    elif "display_key" not in st.session_state:
        st.session_state[PENDING_DISPLAY_KEY] = data["key"]
    st.session_state[ACTIVE_CATALOG_PICK_KEY] = pick_key
    st.session_state[PENDING_MATCHING_SONG_DROPDOWN] = pick_key
    return data


def get_song_context(
    st: Any,
    *,
    song_library: dict[str, dict[str, dict]],
    song_picker_catalog: dict[str, dict[str, dict]],
) -> tuple[str, str, dict]:
    """Return (genre, title, song_data) for the master selection."""
    sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
    pk = sel.get("pick_key")
    if not pk:
        raise RuntimeError("Master song not initialized — call ensure_master_song_initialized first.")
    resolved = resolve_pick_key(pk, song_picker_catalog=song_picker_catalog) or pk
    genre, label = parse_pick_key(resolved)
    if genre not in song_picker_catalog or label not in song_picker_catalog[genre]:
        raise RuntimeError(f"Master song pick key could not be resolved: {pk!r}")
    title = song_picker_catalog[genre][label]["title"]
    song_data = song_library[genre][title]
    return genre, title, song_data

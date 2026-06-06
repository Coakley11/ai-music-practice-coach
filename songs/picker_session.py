"""Song picker session-state helpers (no Streamlit import — safe for unit tests)."""

from __future__ import annotations

from typing import MutableMapping

WORKSPACE_GENRE_FILTERS_KEY = "workspace_genre_filters"
SONG_SEARCH_RESET_REQUESTED_KEY = "song_search_reset_requested"
SONG_SEARCH_TEXT_KEY = "song_search_text"
CATALOG_FAVORITES_KEY = "catalog_favorite_pick_keys"
SONG_PICKER_FAVORITES_ONLY_KEY = "song_picker_favorites_only"


def apply_picker_session_resets(session_state: MutableMapping[str, object]) -> None:
    """Apply pending resets before song-search widgets are drawn."""
    if session_state.pop(SONG_SEARCH_RESET_REQUESTED_KEY, False):
        session_state[SONG_SEARCH_TEXT_KEY] = ""


def request_clear_browse_filters(session_state: MutableMapping[str, object]) -> None:
    """Clear genre and favorites-only filters; defer search-box reset until pre-widget apply."""
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = []
    session_state[SONG_PICKER_FAVORITES_ONLY_KEY] = False
    session_state[SONG_SEARCH_RESET_REQUESTED_KEY] = True


def prune_catalog_pick_keys(pick_keys: list[str], valid: set[str]) -> list[str]:
    """Drop catalog pick keys that no longer exist (e.g. after catalog rebuild)."""
    return [k for k in pick_keys if k in valid]


def toggle_catalog_favorite(session_state: MutableMapping[str, object], pick_key: str) -> None:
    """Add or remove one catalog pick key from the persisted favorites list."""
    if not pick_key:
        return
    favs = set(session_state.get(CATALOG_FAVORITES_KEY) or [])
    if pick_key in favs:
        favs.discard(pick_key)
    else:
        favs.add(pick_key)
    session_state[CATALOG_FAVORITES_KEY] = sorted(favs)


def toggle_favorites_filter(session_state: MutableMapping[str, object]) -> None:
    """Toggle browse view to show only favorited catalog songs."""
    session_state[SONG_PICKER_FAVORITES_ONLY_KEY] = not bool(
        session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY)
    )


def toggle_genre_filter(session_state: MutableMapping[str, object], genre: str) -> None:
    """Toggle one genre in the multi-select pill filter list."""
    filters = list(session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    if genre in filters:
        filters = [g for g in filters if g != genre]
    else:
        filters.append(genre)
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = filters

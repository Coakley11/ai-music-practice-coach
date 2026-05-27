"""Song picker session-state helpers (no Streamlit import — safe for unit tests)."""

from __future__ import annotations

from typing import MutableMapping

WORKSPACE_GENRE_FILTERS_KEY = "workspace_genre_filters"
SONG_SEARCH_RESET_REQUESTED_KEY = "song_search_reset_requested"
SONG_SEARCH_TEXT_KEY = "song_search_text"


def apply_picker_session_resets(session_state: MutableMapping[str, object]) -> None:
    """Apply pending resets before song-search widgets are drawn."""
    if session_state.pop(SONG_SEARCH_RESET_REQUESTED_KEY, False):
        session_state[SONG_SEARCH_TEXT_KEY] = ""


def request_clear_browse_filters(session_state: MutableMapping[str, object]) -> None:
    """Clear genre filters; defer search-box reset until pre-widget apply."""
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = []
    session_state[SONG_SEARCH_RESET_REQUESTED_KEY] = True


def toggle_genre_filter(session_state: MutableMapping[str, object], genre: str) -> None:
    """Toggle one genre in the multi-select pill filter list."""
    filters = list(session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    if genre in filters:
        filters = [g for g in filters if g != genre]
    else:
        filters.append(genre)
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = filters

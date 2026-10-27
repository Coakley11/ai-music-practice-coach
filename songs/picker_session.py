"""Song picker session-state helpers (no Streamlit import — safe for unit tests)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, MutableMapping

WORKSPACE_GENRE_FILTERS_KEY = "workspace_genre_filters"
SONG_SEARCH_RESET_REQUESTED_KEY = "song_search_reset_requested"
SONG_SEARCH_TEXT_KEY = "song_search_text"
CATALOG_FAVORITES_KEY = "catalog_favorite_pick_keys"
SONG_PICKER_FAVORITES_ONLY_KEY = "song_picker_favorites_only"
SONG_SEARCH_USER_TOUCHED_KEY = "_song_search_user_touched"
FAVORITES_ONLY_USER_TOUCHED_KEY = "_favorites_only_user_touched"
LEGACY_ALL_GENRES_VALUE = "All genres"


def _save_picker_page_snapshot(session_state: MutableMapping[str, object]) -> None:
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session_state, "picker")
    except ImportError:
        pass


def apply_picker_session_resets(session_state: MutableMapping[str, object]) -> None:
    """Apply pending resets before song-search widgets are drawn."""
    if session_state.pop(SONG_SEARCH_RESET_REQUESTED_KEY, False):
        session_state[SONG_SEARCH_TEXT_KEY] = ""
        # The cleared search text only lands in session_state here (it is applied
        # one rerun after Clear Filters, before the Search widget is drawn), so the
        # page snapshot must be re-saved here too, or a reload before the next
        # autosave tick would resurrect the pre-clear search text.
        _save_picker_page_snapshot(session_state)


def request_clear_browse_filters(session_state: MutableMapping[str, object]) -> None:
    """Clear every Browse contribution source and legacy compatibility value."""
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = []
    session_state[SONG_PICKER_FAVORITES_ONLY_KEY] = False
    session_state["workspace_genre_filter"] = LEGACY_ALL_GENRES_VALUE
    session_state[SONG_SEARCH_USER_TOUCHED_KEY] = True
    session_state["_genre_filters_user_touched"] = True
    session_state[FAVORITES_ONLY_USER_TOUCHED_KEY] = True
    session_state[SONG_SEARCH_RESET_REQUESTED_KEY] = True
    _save_picker_page_snapshot(session_state)


def commit_browse_search_text(session_state: MutableMapping[str, object]) -> None:
    """Mark the live Search widget value authoritative, including empty text."""
    session_state[SONG_SEARCH_TEXT_KEY] = str(
        session_state.get(SONG_SEARCH_TEXT_KEY) or ""
    )
    session_state[SONG_SEARCH_USER_TOUCHED_KEY] = True
    _save_picker_page_snapshot(session_state)


def text_search_active(query: object) -> bool:
    """True when the Songs search box holds any non-whitespace text."""
    return bool(str(query or "").strip())


def effective_browse_filters(
    session_state: MutableMapping[str, object], query: object
) -> tuple[list[str], bool]:
    """Return independent active Genre and Favorites contribution sources.

    Search is intentionally not used for precedence here: all three sources are
    composed additively by :func:`compose_browse_results`.

    """
    genres = [str(g) for g in (session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or []) if g]
    return genres, bool(session_state.get(SONG_PICKER_FAVORITES_ONLY_KEY))


def compose_browse_results(
    records: Iterable[Mapping[str, Any]],
    *,
    query: object = "",
    genres: Iterable[str] = (),
    favorite_pick_keys: Iterable[str] = (),
    favorites_enabled: bool = False,
    pick_key_for_record: Callable[[Mapping[str, Any]], str] | None = None,
) -> list[dict[str, Any]]:
    """Compose Search union Genres union Favorites with canonical pick-key deduplication."""
    from song_catalog.catalog import format_pick_key, search_records

    rows = [dict(record) for record in records]
    selected_genres = {str(genre) for genre in genres if str(genre)}
    favorites = {str(key) for key in favorite_pick_keys if str(key)}
    search_active = text_search_active(query)
    any_source = search_active or bool(selected_genres) or bool(favorites_enabled)
    if pick_key_for_record is None:
        def pick_key_for_record(record: Mapping[str, Any]) -> str:
            return format_pick_key(
                str(record.get("genre") or ""),
                f"{record.get('title', '')} {chr(0x2014)} {record.get('artist', '')}",
            )

    contributors: list[dict[str, Any]] = []
    if not any_source:
        contributors.extend(rows)
    else:
        if search_active:
            contributors.extend(search_records(rows, str(query), limit=max(500, len(rows))))
        if selected_genres:
            contributors.extend(
                row for row in rows if str(row.get("genre") or "") in selected_genres
            )
        if favorites_enabled:
            contributors.extend(row for row in rows if pick_key_for_record(row) in favorites)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in contributors:
        identity = str(pick_key_for_record(row) or "")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def prune_catalog_pick_keys(pick_keys: list[str], valid: set[str]) -> list[str]:
    """Drop catalog pick keys that no longer exist (e.g. after catalog rebuild)."""
    return [k for k in pick_keys if k in valid]


CATALOG_FAVORITE_SAVE_REASON = "catalog_favorite_edit"


def is_catalog_favorite(session_state: MutableMapping[str, object], pick_key: str) -> bool:
    """Favorite belongs to the Catalog song (pick), never to a Practice Key."""
    return bool(pick_key) and str(pick_key) in set(session_state.get(CATALOG_FAVORITES_KEY) or [])


def persist_catalog_favorites(st: object) -> bool:
    """Durably save a Favorite / unfavorite as a deliberate user change."""
    try:
        from music_persistent_state import force_save_music_state

        return bool(force_save_music_state(st, reason=CATALOG_FAVORITE_SAVE_REASON))
    except Exception:
        return False


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
    session_state[FAVORITES_ONLY_USER_TOUCHED_KEY] = True
    _save_picker_page_snapshot(session_state)


def toggle_genre_filter(session_state: MutableMapping[str, object], genre: str) -> None:
    """Toggle one genre in the multi-select pill filter list."""
    filters = list(session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or [])
    if genre in filters:
        filters = [g for g in filters if g != genre]
    else:
        filters.append(genre)
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = filters
    session_state["_genre_filters_user_touched"] = True
    _save_picker_page_snapshot(session_state)


def mark_improv_tab_user_touched(session_state: MutableMapping[str, object]) -> None:
    """Record Improvisation Intelligence sub-tab — canonical blob + discrete cloud save."""
    try:
        from creative_tab_tool_persistence import handle_user_creative_selector_change

        handle_user_creative_selector_change(session_state, "improv_intelligence_tab")
        return
    except ImportError:
        pass
    tab = str(session_state.get("improv_intelligence_tab") or "").strip()
    if tab:
        session_state["creative_improv_intelligence_tab"] = tab
    session_state["_improv_tab_user_touched"] = True
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session_state)
    except ImportError:
        pass
    try:
        from studio_page_persistence import save_page_snapshot

        save_page_snapshot(session_state, "creative")
    except ImportError:
        pass


def genre_filter_widget_key(genre: str) -> str:
    """Stable Streamlit widget key suffix for a genre label."""
    import re

    return re.sub(r"[^a-zA-Z0-9_]", "_", str(genre or "genre"))[:48] or "genre"

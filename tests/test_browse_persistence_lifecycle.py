"""Regression tests: Browse filters (Search, Genres, Favorites, Clear Filters)
must all participate in the same page-scoped snapshot/restore lifecycle, so a
reload/reconnect can never silently resurrect stale Browse state or lose a
just-applied Clear Filters / Favorites-toggle change.
"""

from __future__ import annotations

from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    FAVORITES_ONLY_USER_TOUCHED_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_TEXT_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    request_clear_browse_filters,
    toggle_catalog_favorite,
    toggle_favorites_filter,
    toggle_genre_filter,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY
from studio_page_persistence import (
    _PAGE_LOCAL_KEYS,
    _PAGE_SNAPSHOT_USER_TOUCH_GUARDS,
    _PAGE_SNAPSHOTS_KEY,
    restore_page_snapshot,
    save_page_snapshot,
)


def _picker_snapshot(state: dict) -> dict:
    return (state.get(_PAGE_SNAPSHOTS_KEY) or {}).get("picker") or {}


def test_favorites_only_is_page_local_and_guarded():
    assert SONG_PICKER_FAVORITES_ONLY_KEY in _PAGE_LOCAL_KEYS["picker"]
    assert (
        _PAGE_SNAPSHOT_USER_TOUCH_GUARDS.get(SONG_PICKER_FAVORITES_ONLY_KEY)
        == FAVORITES_ONLY_USER_TOUCHED_KEY
    )


def test_toggle_favorites_filter_writes_picker_page_snapshot():
    state: dict = {}
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    assert _picker_snapshot(state).get(SONG_PICKER_FAVORITES_ONLY_KEY) is True

    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False
    assert _picker_snapshot(state).get(SONG_PICKER_FAVORITES_ONLY_KEY) is False


def test_request_clear_browse_filters_writes_picker_page_snapshot():
    state: dict = {
        SONG_SEARCH_TEXT_KEY: "Sheeran",
        WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
    }
    request_clear_browse_filters(state)
    snap = _picker_snapshot(state)
    assert snap.get(WORKSPACE_GENRE_FILTERS_KEY) == []
    assert snap.get(SONG_PICKER_FAVORITES_ONLY_KEY) is False
    # Search text is only actually blanked one rerun later (apply_picker_session_resets,
    # mirroring the widget-apply ordering in the real app) — closing that gap is what
    # apply_picker_session_resets' own save_page_snapshot call is for.
    apply_picker_session_resets(state)
    snap = _picker_snapshot(state)
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert snap.get(SONG_SEARCH_TEXT_KEY) == ""


def test_stale_favorites_only_cannot_resurrect_after_turned_off():
    """A reload/reconnect must not bring back a stale Favorites-ON value once the
    user has explicitly turned it off this session (same touch-guard pattern as
    Search and Genre filters)."""
    state: dict = {SONG_PICKER_FAVORITES_ONLY_KEY: True}
    # Simulate a stale on-disk snapshot saved before the merge (Favorites stuck ON).
    save_page_snapshot(state, "picker")

    toggle_favorites_filter(state)  # user turns it OFF
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False

    # Simulate any later page-snapshot restore attempt (e.g. a subsequent hydration).
    restore_page_snapshot(state, "picker")
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_stale_favorites_only_true_round_trips_without_contradictory_state():
    """STALE-1: a persisted snapshot that already has Favorites ON hydrates cleanly
    (no leftover contradictory global/page-local split)."""
    state: dict = {}
    save_page_snapshot({SONG_PICKER_FAVORITES_ONLY_KEY: True, **state}, "picker")
    seeded_snapshot = {SONG_PICKER_FAVORITES_ONLY_KEY: True}
    state[_PAGE_SNAPSHOTS_KEY] = {"picker": seeded_snapshot}

    restore_page_snapshot(state, "picker")
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    # Page-local, not a bare untouched global: a later explicit OFF still wins.
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_clear_filters_then_reset_leaves_no_stale_state_after_restore():
    """STALE-4 core assertion: after Clear Filters + the next rerun's reset-apply,
    the stored snapshot itself (what a reload would read back) is already fully
    cleared — no race window where an old snapshot could still resurrect it."""
    state: dict = {
        SONG_SEARCH_TEXT_KEY: "Sheeran",
        WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
    }
    request_clear_browse_filters(state)
    apply_picker_session_resets(state)

    snap = _picker_snapshot(state)
    assert snap.get(SONG_SEARCH_TEXT_KEY) == ""
    assert snap.get(WORKSPACE_GENRE_FILTERS_KEY) == []
    assert snap.get(SONG_PICKER_FAVORITES_ONLY_KEY) is False

    # A subsequent restore (simulating a reload reading this now-current snapshot)
    # must not reintroduce the pre-clear values.
    restore_page_snapshot(state, "picker")
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == []
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_clear_filters_preserves_canonical_favorite_records():
    """Clear Filters resets the Favorites *Browse filter*, never the canonical
    Favorite song data."""
    state: dict = {CATALOG_FAVORITES_KEY: []}
    toggle_catalog_favorite(state, "Pop|Shallow — Lady Gaga")
    toggle_favorites_filter(state)
    assert state[CATALOG_FAVORITES_KEY] == ["Pop|Shallow — Lady Gaga"]
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True

    request_clear_browse_filters(state)

    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False
    assert state[CATALOG_FAVORITES_KEY] == ["Pop|Shallow — Lady Gaga"]

    # Turning the Browse filter back on still surfaces the still-starred song.
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    assert "Pop|Shallow — Lady Gaga" in state[CATALOG_FAVORITES_KEY]


def test_browse_filter_changes_never_touch_active_song():
    """Active Song selection stays global/unrestricted — Browse filter writers
    must never write ACTIVE_CATALOG_PICK_KEY."""
    state: dict = {ACTIVE_CATALOG_PICK_KEY: "Pop|Say — John Mayer"}
    toggle_favorites_filter(state)
    toggle_genre_filter(state, "Jazz")
    request_clear_browse_filters(state)
    apply_picker_session_resets(state)
    assert state[ACTIVE_CATALOG_PICK_KEY] == "Pop|Say — John Mayer"

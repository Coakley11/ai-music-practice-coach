"""Regression tests for song-picker session reset / filter helpers."""

from __future__ import annotations

from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_RESET_REQUESTED_KEY,
    SONG_SEARCH_TEXT_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    prune_catalog_pick_keys,
    request_clear_browse_filters,
    toggle_catalog_favorite,
    toggle_favorites_filter,
    toggle_genre_filter,
)


def test_request_clear_does_not_mutate_search_until_apply():
    state = {
        SONG_SEARCH_TEXT_KEY: "shalom",
        WORKSPACE_GENRE_FILTERS_KEY: ["Jewish"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
    }
    request_clear_browse_filters(state)
    assert state[SONG_SEARCH_TEXT_KEY] == "shalom"
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == []
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False
    assert state[SONG_SEARCH_RESET_REQUESTED_KEY] is True


def test_apply_picker_session_resets_clears_search_once():
    state = {SONG_SEARCH_TEXT_KEY: "shalom", SONG_SEARCH_RESET_REQUESTED_KEY: True}
    apply_picker_session_resets(state)
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert SONG_SEARCH_RESET_REQUESTED_KEY not in state
    apply_picker_session_resets(state)
    assert state[SONG_SEARCH_TEXT_KEY] == ""


def test_toggle_genre_filter_add_and_remove():
    state: dict = {WORKSPACE_GENRE_FILTERS_KEY: []}
    toggle_genre_filter(state, "Pop")
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == ["Pop"]
    toggle_genre_filter(state, "Rock")
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == ["Pop", "Rock"]
    toggle_genre_filter(state, "Pop")
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == ["Rock"]


def test_toggle_catalog_favorite_add_and_remove():
    state: dict = {CATALOG_FAVORITES_KEY: []}
    toggle_catalog_favorite(state, "Jazz|Autumn Leaves — Joseph Kosma")
    assert state[CATALOG_FAVORITES_KEY] == ["Jazz|Autumn Leaves — Joseph Kosma"]
    toggle_catalog_favorite(state, "Jazz|Autumn Leaves — Joseph Kosma")
    assert state[CATALOG_FAVORITES_KEY] == []


def test_toggle_favorites_filter_flips_flag():
    state: dict = {}
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is True
    toggle_favorites_filter(state)
    assert state[SONG_PICKER_FAVORITES_ONLY_KEY] is False


def test_prune_catalog_pick_keys_drops_stale_entries():
    valid = {"Jazz|Song A — Artist", "Pop|Song B — Artist"}
    raw = ["Jazz|Song A — Artist", "Rock|Removed — Nobody", "Pop|Song B — Artist"]
    assert prune_catalog_pick_keys(raw, valid) == [
        "Jazz|Song A — Artist",
        "Pop|Song B — Artist",
    ]


def test_widget_key_guard_pattern_simulates_pre_widget_apply():
    """Simulate: clear requested on prior run, apply before text_input on next run."""
    state = {
        SONG_SEARCH_TEXT_KEY: "shallow",
        WORKSPACE_GENRE_FILTERS_KEY: ["Pop"],
    }
    request_clear_browse_filters(state)
    apply_picker_session_resets(state)
    assert state[SONG_SEARCH_TEXT_KEY] == ""
    assert state[WORKSPACE_GENRE_FILTERS_KEY] == []

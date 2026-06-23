"""Scalable song database and search helpers."""

from .catalog import (
    load_song_catalog,
    reload_song_catalog,
    clear_catalog_cache,
    search_records,
    format_pick_key,
    parse_pick_key,
    resolve_pick_key,
    first_valid_pick_key,
    resolve_picker_catalog_selection,
    build_search_blob,
    record_for_pick_key,
    PICK_KEY_SEP,
)

__all__ = [
    "load_song_catalog",
    "reload_song_catalog",
    "clear_catalog_cache",
    "search_records",
    "format_pick_key",
    "parse_pick_key",
    "resolve_pick_key",
    "first_valid_pick_key",
    "resolve_picker_catalog_selection",
    "build_search_blob",
    "record_for_pick_key",
    "PICK_KEY_SEP",
]

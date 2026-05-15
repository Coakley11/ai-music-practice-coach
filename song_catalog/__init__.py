"""Scalable song database and search helpers."""

from .catalog import (
    load_song_catalog,
    search_records,
    format_pick_key,
    parse_pick_key,
    build_search_blob,
)

__all__ = [
    "load_song_catalog",
    "search_records",
    "format_pick_key",
    "parse_pick_key",
    "build_search_blob",
]

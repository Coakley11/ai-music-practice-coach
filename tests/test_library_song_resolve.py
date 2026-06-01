"""SONG_LIBRARY title collisions must not return the wrong artist's chart."""

from __future__ import annotations

from song_catalog import format_pick_key
from songs.state import _build_library_from_picker, get_song_context


def _duplicate_title_catalog():
    picker = {
        "Jazz": {
            "Autumn Leaves — Eric Clapton": {
                "title": "Autumn Leaves",
                "artist": "Eric Clapton",
                "genre": "Jazz",
                "key": "Bm",
                "sections": {"A": ["USER"]},
            },
            "Autumn Leaves — Jazz Standard": {
                "title": "Autumn Leaves",
                "artist": "Jazz Standard",
                "genre": "Jazz",
                "key": "Bm",
                "sections": {"A": ["CATALOG"]},
            },
        }
    }
    library = {
        "Jazz": {
            "Autumn Leaves": {
                "title": "Autumn Leaves",
                "artist": "Jazz Standard",
                "genre": "Jazz",
                "key": "Bm",
                "sections": {"A": ["CATALOG"]},
            }
        }
    }
    return picker, library


def test_build_library_from_picker_uses_matching_artist():
    picker, library = _duplicate_title_catalog()
    title, data = _build_library_from_picker(
        "Jazz",
        "Autumn Leaves — Eric Clapton",
        picker,
        library,
    )
    assert title == "Autumn Leaves"
    assert data["artist"] == "Eric Clapton"
    assert data["sections"]["A"] == ["USER"]


def test_get_song_context_keeps_eric_clapton_override():
    from songs.state import SELECTED_SONG_STATE_KEY

    picker, library = _duplicate_title_catalog()
    pk = format_pick_key("Jazz", "Autumn Leaves — Eric Clapton")

    class _FakeSt:
        session_state = {
            SELECTED_SONG_STATE_KEY: {
                "pick_key": pk,
                "title": "Autumn Leaves",
                "artist": "Eric Clapton",
                "genre": "Jazz",
            }
        }

    _genre, title, data = get_song_context(
        _FakeSt(),
        song_library=library,
        song_picker_catalog=picker,
    )
    assert title == "Autumn Leaves"
    assert data["artist"] == "Eric Clapton"
    assert data["sections"]["A"] == ["USER"]

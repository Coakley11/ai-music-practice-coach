"""Regression tests for catalog pick-key parsing and resolution."""

from __future__ import annotations

from song_catalog.catalog import (
    PICK_KEY_SEP,
    format_pick_key,
    parse_pick_key,
    record_for_pick_key,
    resolve_pick_key,
    search_records,
)

_SAMPLE_CATALOG = {
    "Jewish Traditional": {
        "Shalom Aleichem — Traditional Jewish Sabbath Song": {
            "title": "Shalom Aleichem",
            "artist": "Traditional Jewish Sabbath Song",
            "key": "Dm",
        },
    },
    "Pop": {
        "Shallow — Lady Gaga / Bradley Cooper": {
            "title": "Shallow",
            "artist": "Lady Gaga / Bradley Cooper",
            "key": "G",
        },
    },
}

_SAMPLE_RECORDS = [
    {
        "genre": "Jewish Traditional",
        "title": "Shalom Aleichem",
        "artist": "Traditional Jewish Sabbath Song",
        "composer": "Traditional",
        "chart_versions": {"Beginner": {}},
        "extensions": {"default_groove": "Jewish ballad"},
    },
    {
        "genre": "Pop",
        "title": "Shallow",
        "artist": "Lady Gaga / Bradley Cooper",
        "composer": "",
        "chart_versions": {"Intermediate": {}},
        "extensions": {"default_groove": "Pop groove"},
    },
]


def test_parse_pick_key_canonical_roundtrip():
    pk = format_pick_key("Pop", "Shallow — Lady Gaga / Bradley Cooper")
    assert PICK_KEY_SEP in pk
    genre, label = parse_pick_key(pk)
    assert genre == "Pop"
    assert label == "Shallow — Lady Gaga / Bradley Cooper"


def test_parse_pick_key_plain_label_without_separator():
    genre, label = parse_pick_key("Shallow — Lady Gaga / Bradley Cooper")
    assert genre == ""
    assert label == "Shallow — Lady Gaga / Bradley Cooper"


def test_resolve_pick_key_plain_label():
    resolved = resolve_pick_key(
        "Shallow — Lady Gaga / Bradley Cooper",
        song_picker_catalog=_SAMPLE_CATALOG,
        records=_SAMPLE_RECORDS,
    )
    assert resolved == format_pick_key("Pop", "Shallow — Lady Gaga / Bradley Cooper")


def test_resolve_pick_key_title_only():
    resolved = resolve_pick_key(
        "Shalom Aleichem",
        song_picker_catalog=_SAMPLE_CATALOG,
        records=_SAMPLE_RECORDS,
    )
    assert resolved == format_pick_key(
        "Jewish Traditional", "Shalom Aleichem — Traditional Jewish Sabbath Song"
    )


def test_resolve_pick_key_custom_title_returns_none():
    assert (
        resolve_pick_key(
            "Daniel Practice Tune",
            song_picker_catalog=_SAMPLE_CATALOG,
            records=_SAMPLE_RECORDS,
        )
        is None
    )


def test_resolve_pick_key_filtered_genre_search_dropdown_options():
    filtered = search_records(_SAMPLE_RECORDS, "shalom", genres=["Jewish Traditional"])
    assert len(filtered) == 1
    pick_options = [
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered
    ]
    assert len(pick_options) == 1
    assert PICK_KEY_SEP in pick_options[0]
    resolved = resolve_pick_key(
        pick_options[0],
        song_picker_catalog=_SAMPLE_CATALOG,
        records=filtered,
    )
    assert resolved == pick_options[0]
    # Stale session may store display label only
    plain = parse_pick_key(pick_options[0])[1]
    assert resolve_pick_key(plain, song_picker_catalog=_SAMPLE_CATALOG, records=filtered) == pick_options[0]


def test_resolve_pick_key_search_filtered_plain_title():
    filtered = search_records(_SAMPLE_RECORDS, "Shallow")
    pick_options = [
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}") for r in filtered
    ]
    assert pick_options
    resolved = resolve_pick_key("Shallow", song_picker_catalog=_SAMPLE_CATALOG, records=filtered)
    assert resolved == pick_options[0]


def test_record_for_pick_key_accepts_plain_label():
    rec = record_for_pick_key(_SAMPLE_RECORDS, "Shalom Aleichem")
    assert rec is not None
    assert rec["title"] == "Shalom Aleichem"


def test_apply_pick_key_does_not_crash_on_plain_label():
    from songs.state import apply_pick_key

    class _FakeSt:
        session_state: dict = {}

    st = _FakeSt()
    data = apply_pick_key(
        st,
        "Shallow — Lady Gaga / Bradley Cooper",
        _SAMPLE_CATALOG,
    )
    assert data["title"] == "Shallow"
    assert st.session_state["selected_song"]["pick_key"] == format_pick_key(
        "Pop", "Shallow — Lady Gaga / Bradley Cooper"
    )


def test_parse_pick_key_empty_and_none():
    assert parse_pick_key("") == ("", "")
    assert parse_pick_key(None) == ("", "")  # type: ignore[arg-type]


def test_resolve_pick_key_stale_genre_same_label():
    stale = format_pick_key("DeletedGenre", "Shallow — Lady Gaga / Bradley Cooper")
    resolved = resolve_pick_key(stale, song_picker_catalog=_SAMPLE_CATALOG)
    assert resolved == format_pick_key("Pop", "Shallow — Lady Gaga / Bradley Cooper")


def _sample_library() -> dict:
    library: dict = {}
    for g, labels in _SAMPLE_CATALOG.items():
        library[g] = {}
        for _lab, data in labels.items():
            library[g][data["title"]] = {
                **data,
                "sections": {"A": ["C"]},
                "chart_status": "verified",
            }
    return library


def test_get_song_context_recovers_deleted_song():
    from songs.state import SELECTED_SONG_STATE_KEY, get_song_context

    stale = format_pick_key("Pop", "Removed Song — Nobody")

    class _FakeSt:
        session_state = {
            SELECTED_SONG_STATE_KEY: {
                "pick_key": stale,
                "title": "Removed Song",
                "artist": "Nobody",
            }
        }

    genre, title, data = get_song_context(
        _FakeSt(),
        song_library=_sample_library(),
        song_picker_catalog=_SAMPLE_CATALOG,
    )
    assert title in {"Shallow", "Shalom Aleichem"}
    assert _FakeSt.session_state.get("_pick_key_recovery_notice")


def test_get_song_context_empty_pick_key_uses_default():
    from songs.state import SELECTED_SONG_STATE_KEY, get_song_context

    class _FakeSt:
        session_state = {SELECTED_SONG_STATE_KEY: {"pick_key": ""}}

    genre, title, data = get_song_context(
        _FakeSt(),
        song_library=_sample_library(),
        song_picker_catalog=_SAMPLE_CATALOG,
    )
    assert genre and title and data


def test_get_song_context_recovers_by_title_after_rename():
    from songs.state import SELECTED_SONG_STATE_KEY, get_song_context

    stale = format_pick_key("Jewish", "Shalom Aleichem — Traditional")

    class _FakeSt:
        session_state = {
            SELECTED_SONG_STATE_KEY: {
                "pick_key": stale,
                "title": "Shalom Aleichem",
                "artist": "Traditional",
            }
        }

    genre, title, _data = get_song_context(
        _FakeSt(),
        song_library=_sample_library(),
        song_picker_catalog=_SAMPLE_CATALOG,
    )
    assert title == "Shalom Aleichem"
    assert genre == "Jewish Traditional"

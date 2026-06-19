"""Reboot/reload: verified chart + lyrics survive catalog cache clear."""

from __future__ import annotations

from song_catalog import catalog as cat
from song_catalog import user_overrides as uo
from song_catalog import user_song_content as usc
from songs.state import resolve_library_song_data
from songs.user_lyrics_runtime import hydrate_user_lyrics_session


def test_verified_chart_and_lyrics_survive_catalog_reload(tmp_path, monkeypatch):
    overrides_file = tmp_path / "user_chart_overrides.json"
    content_file = tmp_path / "user_song_content.json"
    monkeypatch.setattr(uo, "overrides_path", lambda workspace_id=None: overrides_file)
    monkeypatch.setattr(usc, "USER_CONTENT_PATH", content_file)

    sections = {"Verse": ["Gmaj7", "D", "Em", "C"]}
    uo.save_user_override(
        title="Reboot Song",
        artist="Test Artist",
        genre="Pop",
        key="C",
        sections=sections,
        chart_versions={"Intermediate": sections},
        section_order=["Verse"],
        override_status=uo.USER_VERIFIED,
        edited_level="Intermediate",
        catalog_snapshot={
            "key": "C",
            "chart_status": "practice_simplified",
            "sections": {"Verse": ["G", "D", "Em", "C"]},
            "chart_versions": {},
        },
    )
    usc.save_user_song_content(
        title="Reboot Song",
        artist="Test Artist",
        genre="Pop",
        section_lyrics={"Verse": "Custom lyric line"},
        content_status=usc.CONTENT_USER_VERIFIED,
    )

    catalog_row = {
        "title": "Reboot Song",
        "artist": "Test Artist",
        "genre": "Pop",
        "key": "C",
        "sections": {"Verse": ["G", "D", "Em", "C"]},
        "chart_versions": {},
        "chart_status": "practice_simplified",
    }
    merged1 = uo.apply_user_override_to_record(catalog_row)
    assert merged1["sections"]["Verse"][0] == "Gmaj7"
    assert merged1["user_override"]["status"] == uo.USER_VERIFIED

    # Simulate process reboot: drop in-memory cache only (disk unchanged).
    cat.clear_catalog_cache()
    on_disk = uo.get_user_override("Reboot Song", "Test Artist")
    assert on_disk is not None
    assert on_disk["sections"]["Verse"][0] == "Gmaj7"
    merged2 = uo.apply_user_override_to_record(catalog_row)
    assert merged2["sections"]["Verse"][0] == "Gmaj7"

    keys = __import__(
        "songs.user_lyrics_runtime", fromlist=["lyrics_session_keys"]
    ).lyrics_session_keys("Reboot Song", "Test Artist")
    session: dict = {}
    hydrate_user_lyrics_session(session, title="Reboot Song", artist="Test Artist", force=True)
    assert session[keys["section_lyrics"]]["Verse"] == "Custom lyric line"


def test_library_resolve_prefers_picker_when_title_collides():
    """Duplicate titles in one genre must not load another artist's chart."""
    picker_row = {
        "title": "Autumn Leaves",
        "artist": "Eric Clapton",
        "genre": "Jazz",
        "key": "Bm",
        "sections": {"Verse": ["USER", "D", "G", "C"]},
        "chart_versions": {},
        "chart_status": uo.USER_VERIFIED,
        "user_override": {"status": uo.USER_VERIFIED},
    }
    library = {
        "Jazz": {
            "Autumn Leaves": {
                "title": "Autumn Leaves",
                "artist": "Jazz Standard",
                "genre": "Jazz",
                "key": "Bm",
                "sections": {"Verse": ["CATALOG", "D", "G", "C"]},
                "chart_versions": {},
                "chart_status": "practice_simplified",
            }
        }
    }
    resolved = resolve_library_song_data(
        library,
        genre="Jazz",
        title="Autumn Leaves",
        artist="Eric Clapton",
        fallback=picker_row,
    )
    assert resolved["sections"]["Verse"][0] == "USER"
    assert resolved["artist"] == "Eric Clapton"


def test_chart_editor_save_reload_end_to_end(tmp_path, monkeypatch):
    """Simulate edit → save verified → reboot → reopen (disk + merge)."""
    overrides_file = tmp_path / "user_chart_overrides.json"
    monkeypatch.setattr(uo, "overrides_path", lambda workspace_id=None: overrides_file)

    from songs.verified_user_save import save_verified_chart

    edited = {"Verse": ["Dm7", "G7", "Cmaj7", "Fmaj7"]}
    save_verified_chart(
        title="End To End",
        artist="QA",
        genre="Jazz",
        key="C",
        sections=edited,
        chart_versions={
            "Beginner": edited,
            "Intermediate": edited,
            "Advanced": edited,
        },
        section_order=["Verse"],
        edited_level="Intermediate",
        catalog_snapshot={
            "key": "C",
            "sections": {"Verse": ["C", "G", "Am", "F"]},
            "chart_versions": {},
            "chart_status": "practice_simplified",
        },
    )

    assert overrides_file.is_file()
    cat.clear_catalog_cache()

    row = {
        "title": "End To End",
        "artist": "QA",
        "genre": "Jazz",
        "key": "C",
        "sections": {"Verse": ["C", "G", "Am", "F"]},
        "chart_versions": {},
        "chart_status": "practice_simplified",
    }
    merged = uo.apply_user_override_to_record(row)
    assert merged["sections"]["Verse"][0] == "Dm7"
    assert merged["user_override"]["status"] == uo.USER_VERIFIED

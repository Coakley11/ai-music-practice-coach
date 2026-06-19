"""User lyrics/cues persistence (separate from core catalog)."""

from __future__ import annotations

from pathlib import Path

from song_catalog import user_song_content as usc
from song_catalog.user_overrides import USER_VERIFIED
from songs.user_lyrics_runtime import (
    collect_lyrics_payload,
    hydrate_user_lyrics_session,
    lyrics_save_status,
    save_lyrics_my_version,
    save_lyrics_user_verified,
    song_lyrics_slug,
)


class _State(dict):
    pass


def test_save_and_reload_lyrics_my_version(tmp_path, monkeypatch):
    path = tmp_path / "user_song_content.json"
    monkeypatch.setattr(usc, "USER_CONTENT_PATH", path)

    state = _State()
    slug = song_lyrics_slug("My Song", "My Band")
    state[f"section_lyrics::{slug}"] = {"Verse": "Line one\nLine two", "Chorus": "Sing loud"}
    state[f"lyric_cues::{slug}"] = {"Verse": ["Breathe here"], "Chorus": ["Strong finish"]}
    state[f"performance_notes::{slug}"] = "Keep it gentle in the intro."

    save_lyrics_my_version(
        state,
        title="My Song",
        artist="My Band",
        genre="Pop",
        section_names=["Verse", "Chorus"],
    )

    loaded = usc.get_user_song_content("My Song", "My Band")
    assert loaded is not None
    assert loaded["section_lyrics"]["Verse"] == "Line one\nLine two"
    assert loaded["lyric_cues"]["Verse"] == ["Breathe here"]
    assert "gentle" in loaded["performance_notes"]

    fresh = _State()
    hydrate_user_lyrics_session(fresh, title="My Song", artist="My Band", force=True)
    assert fresh[f"section_lyrics::{slug}"]["Chorus"] == "Sing loud"
    assert fresh[f"lyric_cues::{slug}"]["Verse"] == ["Breathe here"]


def test_session_save_status(tmp_path, monkeypatch):
    path = tmp_path / "user_song_content.json"
    monkeypatch.setattr(usc, "USER_CONTENT_PATH", path)
    state = _State()
    slug = song_lyrics_slug("S", "A")
    state[f"section_lyrics::{slug}"] = {"Verse": "Hi"}
    from songs.user_lyrics_runtime import save_lyrics_for_session

    save_lyrics_for_session(state, title="S", artist="A")
    assert lyrics_save_status(state, slug=slug, title="S", artist="A") == "session"
    assert not path.exists() or usc.get_user_song_content("S", "A") is None


def test_user_verified_marks_chart_override(tmp_path, monkeypatch):
    content_path = tmp_path / "user_song_content.json"
    chart_path = tmp_path / "user_chart_overrides.json"
    monkeypatch.setattr(usc, "USER_CONTENT_PATH", content_path)
    monkeypatch.setattr("song_catalog.user_overrides.overrides_path", lambda workspace_id=None: chart_path)

    state = _State()
    slug = song_lyrics_slug("Verify Me", "Artist")
    state[f"section_lyrics::{slug}"] = {"Chorus": "La la la"}
    song_data = {
        "title": "Verify Me",
        "artist": "Artist",
        "genre": "Rock",
        "key": "G",
        "sections": {"Chorus": ["G", "D", "Em", "C"]},
        "chart_versions": {},
    }
    save_lyrics_user_verified(
        state,
        title="Verify Me",
        artist="Artist",
        genre="Rock",
        section_names=["Chorus"],
        song_data=song_data,
        catalog_snapshot={"sections": song_data["sections"], "key": "G"},
    )

    content = usc.get_user_song_content("Verify Me", "Artist")
    assert content["content_status"] == usc.CONTENT_USER_VERIFIED

    from song_catalog.user_overrides import get_user_override

    chart = get_user_override("Verify Me", "Artist")
    assert chart is not None
    assert chart["override_status"] == USER_VERIFIED


def test_apply_user_song_content_metadata_only():
    record = {
        "title": "T",
        "artist": "A",
        "lyric_cues": {"Verse": ["catalog cue"]},
        "sections": {"Verse": ["C"]},
    }
    out = usc.apply_user_song_content_to_record(record)
    assert "user_song_content" not in record
    assert out["lyric_cues"] == {"Verse": ["catalog cue"]}

"""Tests for backing-track BPM sync when the active song changes."""

from __future__ import annotations

from songs.playback_defaults import (
    ACTIVE_PLAYBACK_SONG_ID_KEY,
    ACTIVE_SONG_BPM_KEY,
    BPM_WIDGET_KEY,
    LAST_BACKING_DEFAULTS_SONG_ID,
    apply_backing_defaults_for_song,
    reset_playback_song_tracking,
)


class _FakeSession:
    def __init__(self, data: dict | None = None) -> None:
        self.session_state: dict = dict(data or {})


def test_song_change_resets_bpm_and_metadata():
    st = _FakeSession({BPM_WIDGET_KEY: 140, "bpm": 140})
    bpm, _ = apply_backing_defaults_for_song(
        st,
        song_id="cat::Viva la Vida::Coldplay",
        default_bpm=100,
        default_groove="Pop groove",
    )
    assert bpm == 100
    assert st.session_state[BPM_WIDGET_KEY] == 100
    assert st.session_state["bpm"] == 100
    assert st.session_state[ACTIVE_SONG_BPM_KEY] == 100
    assert st.session_state[ACTIVE_PLAYBACK_SONG_ID_KEY] == "cat::Viva la Vida::Coldplay"
    assert st.session_state[LAST_BACKING_DEFAULTS_SONG_ID] == "cat::Viva la Vida::Coldplay"


def test_manual_bpm_preserved_for_same_song():
    st = _FakeSession()
    apply_backing_defaults_for_song(
        st,
        song_id="cat::Song A::Artist",
        default_bpm=100,
        default_groove="Pop groove",
    )
    st.session_state[BPM_WIDGET_KEY] = 128
    bpm, _ = apply_backing_defaults_for_song(
        st,
        song_id="cat::Song A::Artist",
        default_bpm=100,
        default_groove="Pop groove",
    )
    assert bpm == 128


def test_reset_tracking_forces_new_song_defaults():
    st = _FakeSession()
    apply_backing_defaults_for_song(
        st,
        song_id="cat::Song A::Artist",
        default_bpm=100,
        default_groove="Pop groove",
    )
    st.session_state[BPM_WIDGET_KEY] = 140
    st.session_state["_studio_page_snapshots"] = {
        "backing": {BPM_WIDGET_KEY: 140, "backing_groove_style": "Rock groove"},
    }
    reset_playback_song_tracking(st)
    bpm, _ = apply_backing_defaults_for_song(
        st,
        song_id="cat::Song B::Artist",
        default_bpm=96,
        default_groove="Pop groove",
    )
    assert bpm == 96
    assert "backing" not in st.session_state.get("_studio_page_snapshots", {})

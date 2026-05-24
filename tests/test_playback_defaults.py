"""Tests for backing-track BPM sync when the active song changes."""

from __future__ import annotations

from songs.playback_defaults import (
    ACTIVE_PLAYBACK_SONG_ID_KEY,
    ACTIVE_SONG_BPM_KEY,
    BPM_WIDGET_KEY,
    LAST_BACKING_DEFAULTS_SONG_ID,
    active_song_sync_id,
    apply_backing_defaults_for_song,
    backing_bpm_slider_widget_key,
    canonical_active_song_bpm,
    prime_active_song_bpm,
    reset_playback_song_tracking,
)


class _FakeSession:
    def __init__(self, data: dict | None = None) -> None:
        self.session_state: dict = dict(data or {})


def test_song_change_resets_bpm_and_metadata():
    st = _FakeSession({BPM_WIDGET_KEY: 140, "bpm": 140})
    sync_id = active_song_sync_id(
        pick_key="Rock::Perfect — Ed Sheeran",
        playback_song_id="cat::Perfect::Ed Sheeran",
    )
    bpm, _ = apply_backing_defaults_for_song(
        st,
        song_id=sync_id,
        default_bpm=95,
        default_groove="Pop groove",
    )
    assert bpm == 95
    assert st.session_state[BPM_WIDGET_KEY] == 95
    assert st.session_state["bpm"] == 95
    assert st.session_state[ACTIVE_SONG_BPM_KEY] == 95
    assert st.session_state[ACTIVE_PLAYBACK_SONG_ID_KEY] == sync_id
    assert st.session_state[LAST_BACKING_DEFAULTS_SONG_ID] == sync_id


def test_manual_bpm_preserved_for_same_song():
    st = _FakeSession()
    sync_id = "pk::Pop::Song A — Artist"
    apply_backing_defaults_for_song(
        st,
        song_id=sync_id,
        default_bpm=100,
        default_groove="Pop groove",
    )
    st.session_state[BPM_WIDGET_KEY] = 128
    bpm, _ = apply_backing_defaults_for_song(
        st,
        song_id=sync_id,
        default_bpm=100,
        default_groove="Pop groove",
    )
    assert bpm == 128


def test_reset_tracking_forces_new_song_defaults():
    st = _FakeSession()
    apply_backing_defaults_for_song(
        st,
        song_id="pk::Rock::Song A — Queen",
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
        song_id="pk::Rock::Song B — Queen",
        default_bpm=107,
        default_groove="Pop groove",
    )
    assert bpm == 107
    assert "backing" not in st.session_state.get("_studio_page_snapshots", {})


def test_prime_active_song_bpm_sets_widget_keys():
    st = _FakeSession({BPM_WIDGET_KEY: 95, "bpm": 95})
    sync_id = "pk::Rock::We Are the Champions — Queen"
    prime_active_song_bpm(st, sync_id=sync_id, active_song_bpm=107)
    assert st.session_state[BPM_WIDGET_KEY] == 107
    assert st.session_state[backing_bpm_slider_widget_key(sync_id)] == 107
    assert st.session_state[LAST_BACKING_DEFAULTS_SONG_ID] == sync_id


def test_canonical_bpm_reads_extensions():
    song = {
        "title": "We Are the Champions",
        "artist": "Queen",
        "genre": "Rock",
        "extensions": {"default_bpm": 107},
    }
    assert canonical_active_song_bpm(song) == 107

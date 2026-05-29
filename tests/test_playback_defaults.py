"""Tests for backing-track BPM sync when the active song changes."""

from __future__ import annotations

from songs.playback_defaults import (
    ACTIVE_PLAYBACK_SONG_ID_KEY,
    ACTIVE_SONG_BPM_KEY,
    BACKING_GROOVE_KEY,
    BPM_WIDGET_KEY,
    LAST_BACKING_DEFAULTS_SONG_ID,
    active_song_sync_id,
    apply_backing_defaults_for_song,
    backing_bpm_slider_widget_key,
    canonical_active_song_bpm,
    canonicalize_backing_defaults_for_song,
    prime_active_song_bpm,
    reset_playback_song_tracking,
    resolve_backing_bpm_for_slider,
    sync_backing_bpm_from_slider,
)
from songs.meter_state import BACKING_METER_KEY, BACKING_METER_OVERRIDE_KEY


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


def test_canonicalize_force_resets_on_song_change():
    """Switching songs must reset BPM, groove, meter, and override flags."""
    st = _FakeSession({
        BPM_WIDGET_KEY: 100,
        BACKING_GROOVE_KEY: "Rock groove",
        BACKING_METER_KEY: "3/4",
        BACKING_METER_OVERRIDE_KEY: True,
        "_last_backing_wav": b"stale_audio",
        "_last_backing_signature": ("stale",),
    })
    result = canonicalize_backing_defaults_for_song(
        st,
        sync_id="pk::Pop::Shallow",
        active_song_bpm=96,
        active_song_groove="Ballad",
        active_song_meter="4/4",
    )
    assert result["did_reset"] is True
    assert result["applied_bpm"] == 96
    assert result["applied_groove"] == "Ballad"
    assert result["applied_meter"] == "4/4"
    assert st.session_state[BPM_WIDGET_KEY] == 96
    assert st.session_state[BACKING_GROOVE_KEY] == "Ballad"
    assert st.session_state[BACKING_METER_KEY] == "4/4"
    assert st.session_state[BACKING_METER_OVERRIDE_KEY] is False
    # Cached audio must be wiped so the Play button returns to Generate.
    assert "_last_backing_wav" not in st.session_state
    assert "_last_backing_signature" not in st.session_state


def test_canonicalize_preserves_user_tweaks_for_same_song():
    """Once a song is active, user BPM/groove tweaks must survive reruns."""
    st = _FakeSession()
    canonicalize_backing_defaults_for_song(
        st,
        sync_id="pk::Pop::Shallow",
        active_song_bpm=96,
        active_song_groove="Ballad",
        active_song_meter="4/4",
    )
    # User adjusts BPM and groove manually.
    st.session_state[BPM_WIDGET_KEY] = 110
    st.session_state[BACKING_GROOVE_KEY] = "Pop groove"
    result = canonicalize_backing_defaults_for_song(
        st,
        sync_id="pk::Pop::Shallow",
        active_song_bpm=96,
        active_song_groove="Ballad",
        active_song_meter="4/4",
    )
    assert result["did_reset"] is False
    assert result["applied_bpm"] == 110  # user override preserved
    assert result["applied_groove"] == "Pop groove"  # user override preserved


def test_slider_bpm_not_clobbered_on_rerun():
    """Slider widget value must win over stale canonical BPM before render."""
    st = _FakeSession({BPM_WIDGET_KEY: 100, "bpm": 100})
    sync_id = "pk::Pop::Song — Artist"
    slider_key = backing_bpm_slider_widget_key(sync_id)
    st.session_state[slider_key] = 132
    resolved = resolve_backing_bpm_for_slider(
        st,
        sync_id=sync_id,
        default_bpm=100,
        song_just_reset=False,
    )
    assert resolved == 132
    assert st.session_state[BPM_WIDGET_KEY] == 132
    assert st.session_state["bpm"] == 132


def test_sync_backing_bpm_from_slider_updates_canonical_keys():
    st = _FakeSession({BPM_WIDGET_KEY: 100})
    sync_id = "pk::Pop::Song — Artist"
    slider_key = backing_bpm_slider_widget_key(sync_id)
    st.session_state[slider_key] = 100
    bpm = sync_backing_bpm_from_slider(st, slider_bpm=118)
    assert bpm == 118
    assert st.session_state[BPM_WIDGET_KEY] == 118
    assert st.session_state["bpm"] == 118
    assert st.session_state[slider_key] == 100


def test_canonicalize_song_card_matches_playback_for_known_songs():
    """End-to-end: the BPM the song card shows must equal what the engine uses."""
    test_cases = [
        ("pk::Pop::Shallow — Lady Gaga / Bradley Cooper", 96, "Ballad", "4/4"),
        ("pk::Pop::Perfect — Ed Sheeran", 95, "Pop groove", "6/8"),
        ("pk::Jazz::Blue Bossa — Kenny Dorham", 100, "Bossa nova", "4/4"),
        ("pk::Rock::We Are the Champions — Queen", 65, "Rock groove", "4/4"),
    ]
    for sync_id, bpm, groove, meter in test_cases:
        st = _FakeSession({
            # Stale state from a "previous song":
            BPM_WIDGET_KEY: 175,
            BACKING_GROOVE_KEY: "Funk groove",
            BACKING_METER_KEY: "12/8",
        })
        result = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=bpm,
            active_song_groove=groove,
            active_song_meter=meter,
        )
        assert result["applied_bpm"] == bpm, (
            f"{sync_id}: card BPM ({bpm}) != applied BPM ({result['applied_bpm']})"
        )
        assert result["applied_meter"] == meter, (
            f"{sync_id}: card meter ({meter}) != applied meter ({result['applied_meter']})"
        )
        # Groove gets normalized to GROOVE_STYLE_CHOICES, but the card style
        # label and the playback engine consume the SAME normalized value.
        assert result["applied_groove"] == result["active_song_groove"], (
            f"{sync_id}: groove drift between card and playback "
            f"({result['active_song_groove']} vs {result['applied_groove']})"
        )

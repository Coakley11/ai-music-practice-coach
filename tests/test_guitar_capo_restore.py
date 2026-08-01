"""Guitar capo restore must not reset user-selected shape on chart build."""

from __future__ import annotations

from guitar_capo import (
    CAPO_ENABLED_KEY,
    CAPO_SHAPE_KEY,
    CAPO_SOUNDING_KEY,
    init_capo_session_state,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


def test_init_capo_preserves_enabled_eb_shape():
    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "Eb",
        CAPO_SOUNDING_KEY: "G",
    }
    init_capo_session_state(ss, concert_key="C")
    assert ss[CAPO_ENABLED_KEY] is True
    assert ss[CAPO_SHAPE_KEY] == "Eb"


def test_init_capo_preserves_from_active_song_meta():
    from active_song_state import ACTIVE_SONG_STATE_KEY

    ss = {
        ACTIVE_SONG_STATE_KEY: {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "Eb",
            CAPO_SOUNDING_KEY: "Ab",
        },
        CAPO_ENABLED_KEY: False,
        CAPO_SHAPE_KEY: "",
    }
    init_capo_session_state(ss, concert_key="G")
    assert ss[CAPO_ENABLED_KEY] is True
    assert ss[CAPO_SHAPE_KEY] == "Eb"
    assert ss[CAPO_SOUNDING_KEY] == "Ab"


def test_capo_fields_round_trip_build_apply():
    catalog: dict = {}
    ss = {
        "studio_page": "practice",
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "Eb",
        CAPO_SOUNDING_KEY: "Ab",
        "guitar_capo_last_concert_key": "Ab",
    }
    st = _FakeSt(ss)
    blob = build_music_disk_state(st)
    fresh = _FakeSt({})
    apply_music_disk_state(
        fresh,
        blob,
        song_picker_catalog=catalog,
        song_library=catalog,
        authoritative_restore=True,
    )
    assert fresh.session_state.get(CAPO_ENABLED_KEY) is True
    assert fresh.session_state.get(CAPO_SHAPE_KEY) == "Eb"

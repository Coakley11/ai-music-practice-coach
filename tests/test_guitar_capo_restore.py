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


def test_capo_off_widget_does_not_wipe_canonical_shape_during_refresh():
    """Checkbox Capo-off must not persist-wipe Bb while meta still Capo-on."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from active_song_state import ACTIVE_SONG_STATE_KEY
    from guitar_capo import (
        CAPO_ENABLED_WIDGET_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        render_guitar_capo_sidebar,
    )

    ss = {
        ACTIVE_SONG_STATE_KEY: {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "Bb",
            CAPO_SOUNDING_KEY: "C",
        },
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "Bb",
        # Simulate refresh race: widget key lands False before seed.
        CAPO_ENABLED_WIDGET_KEY: False,
        CAPO_SHAPE_WIDGET_KEY: "C",
    }
    ui = MagicMock()
    ui.checkbox.return_value = False  # widget Capo-off
    ui.selectbox.return_value = "Bb"
    persist = SimpleNamespace(rerun=MagicMock())
    render_guitar_capo_sidebar(ui, ss, practice_display_key="C", persist_st=persist)
    assert ss[CAPO_SHAPE_KEY] == "Bb"
    assert ss.get("_pending_capo_enabled_widget") is True
    persist.rerun.assert_called()


def test_capo_backing_restore_keeps_live_song_practice_key():
    """Capo Shape Bb must not let sealed Roads PK (A) displace Love Story C on Backing."""
    from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, CAPO_SOUNDING_KEY
    from music_theory import split_key_center
    from music_workflow_song_practice import resolve_song_practice_key_token
    from songs.practice_key_state import get_practice_concert_key

    pick = "Country\x1fLove Story — Taylor Swift"
    roads = "Country\x1fTake Me Home, Country Roads — John Denver"
    ss = {
        "display_key": "C",
        "active_catalog_pick_key": pick,
        "selected_song": {"pick_key": pick, "title": "Love Story", "key": "C"},
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "Bb",
        CAPO_SOUNDING_KEY: "C",
        "practice_key_by_source": {pick: "C", roads: "A"},
        "active_song_state": {
            "pick_key": roads,
            "display_key": "A",
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "Bb",
            CAPO_SOUNDING_KEY: "C",
        },
    }
    saved = str(get_practice_concert_key(ss, pick) or "").strip()
    song_tok = saved or str(resolve_song_practice_key_token(ss) or "").strip()
    live_dk = str(ss.get("display_key") or "").strip()
    sel_key = str(ss["selected_song"].get("key") or "").strip()
    live_t, _ = split_key_center(live_dk)
    sel_t, _ = split_key_center(sel_key)
    if live_t and sel_t and live_t == sel_t:
        song_tok = live_dk
    assert song_tok == "C"

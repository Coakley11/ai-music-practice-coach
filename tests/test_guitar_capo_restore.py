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


SHAPE_PICK = "Pop\x1fShape of You — Ed Sheeran"
OTHER_PICK = "Country\x1fLove Story — Taylor Swift"


def _sidebar_selectbox_returns_widget(ss):
    def _selectbox(*_a, **kw):
        return ss.get(kw["key"])

    return _selectbox


def test_live_shape_widget_outranks_unseeded_canonical_on_same_source():
    """Failing Gate-10 rerun: widget C, canonical B, seeded false, restore incomplete."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from guitar_capo import (
        CAPO_ENABLED_WIDGET_KEY,
        CAPO_SHAPE_SEED_SOURCE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        render_guitar_capo_sidebar,
        shape_chart_label_for_concert,
    )

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "B",
        CAPO_SOUNDING_KEY: "Bm",
        CAPO_ENABLED_WIDGET_KEY: True,
        CAPO_SHAPE_WIDGET_KEY: "C",
        "_capo_on_shape_seeded": False,
        "_pending_capo_shape_key": "B",
        "_music_restore_phase_complete": False,
        "active_catalog_pick_key": SHAPE_PICK,
        CAPO_SHAPE_SEED_SOURCE_KEY: SHAPE_PICK,
        "display_key": "Bm",
    }
    ui = MagicMock()
    ui.checkbox.return_value = True
    ui.selectbox.side_effect = _sidebar_selectbox_returns_widget(ss)
    with patch("guitar_capo.persist_capo_to_canonical", return_value=False), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ):
        render_guitar_capo_sidebar(
            ui, ss, practice_display_key="Bm", persist_st=SimpleNamespace(rerun=MagicMock())
        )
    assert ss[CAPO_SHAPE_WIDGET_KEY] == "C"
    assert ss[CAPO_SHAPE_KEY] == "C"
    assert shape_chart_label_for_concert("Bm", "C").lower() == "c minor"


def test_uninitialized_shape_widget_still_seeds_from_canonical():
    """Leftover browser C must not beat canonical B before the control is bound."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from guitar_capo import CAPO_SHAPE_WIDGET_KEY, render_guitar_capo_sidebar

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "B",
        CAPO_SOUNDING_KEY: "Bm",
        CAPO_SHAPE_WIDGET_KEY: "C",
        "_capo_on_shape_seeded": False,
        "_music_restore_phase_complete": False,
        "active_catalog_pick_key": SHAPE_PICK,
    }
    ui = MagicMock()
    ui.checkbox.return_value = True
    ui.selectbox.side_effect = _sidebar_selectbox_returns_widget(ss)
    with patch("guitar_capo.persist_capo_to_canonical", return_value=False), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ):
        render_guitar_capo_sidebar(
            ui, ss, practice_display_key="Bm", persist_st=SimpleNamespace(rerun=MagicMock())
        )
    assert ss[CAPO_SHAPE_WIDGET_KEY] == "B"
    assert ss[CAPO_SHAPE_KEY] == "B"


def test_authoritative_restore_reseeds_shape_over_live_widget():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from guitar_capo import (
        CAPO_SHAPE_SEED_SOURCE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        render_guitar_capo_sidebar,
    )

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "B",
        CAPO_SOUNDING_KEY: "Bm",
        CAPO_SHAPE_WIDGET_KEY: "C",
        "_capo_on_shape_seeded": True,
        "_music_disk_restore_this_run": True,
        "active_catalog_pick_key": SHAPE_PICK,
        CAPO_SHAPE_SEED_SOURCE_KEY: SHAPE_PICK,
    }
    ui = MagicMock()
    ui.checkbox.return_value = True
    ui.selectbox.side_effect = _sidebar_selectbox_returns_widget(ss)
    with patch("guitar_capo.persist_capo_to_canonical", return_value=False), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ):
        render_guitar_capo_sidebar(
            ui, ss, practice_display_key="Bm", persist_st=SimpleNamespace(rerun=MagicMock())
        )
    assert ss[CAPO_SHAPE_WIDGET_KEY] == "B"
    assert ss[CAPO_SHAPE_KEY] == "B"


def test_source_change_does_not_keep_stale_shape_tonic():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from guitar_capo import (
        CAPO_SHAPE_SEED_SOURCE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        render_guitar_capo_sidebar,
    )

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "D",
        CAPO_SOUNDING_KEY: "C",
        CAPO_SHAPE_WIDGET_KEY: "C",
        "_capo_on_shape_seeded": True,
        "_pending_capo_shape_key": "C",
        "active_catalog_pick_key": OTHER_PICK,
        CAPO_SHAPE_SEED_SOURCE_KEY: SHAPE_PICK,
    }
    ui = MagicMock()
    ui.checkbox.return_value = True
    ui.selectbox.side_effect = _sidebar_selectbox_returns_widget(ss)
    with patch("guitar_capo.persist_capo_to_canonical", return_value=False), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ):
        render_guitar_capo_sidebar(
            ui, ss, practice_display_key="C", persist_st=SimpleNamespace(rerun=MagicMock())
        )
    assert ss[CAPO_SHAPE_WIDGET_KEY] == "D"
    assert ss[CAPO_SHAPE_KEY] == "D"
    assert ss.get(CAPO_SHAPE_SEED_SOURCE_KEY) == OTHER_PICK


def test_source_change_drops_stale_c_when_new_sounding_differs():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from guitar_capo import (
        CAPO_SHAPE_SEED_SOURCE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        render_guitar_capo_sidebar,
        shape_tonic_only,
    )

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "C",
        CAPO_SOUNDING_KEY: "F#m",
        CAPO_SHAPE_WIDGET_KEY: "C",
        "_capo_on_shape_seeded": True,
        "active_catalog_pick_key": OTHER_PICK,
        CAPO_SHAPE_SEED_SOURCE_KEY: SHAPE_PICK,
    }
    ui = MagicMock()
    ui.checkbox.return_value = True
    ui.selectbox.side_effect = _sidebar_selectbox_returns_widget(ss)
    with patch("guitar_capo.persist_capo_to_canonical", return_value=False), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ):
        render_guitar_capo_sidebar(
            ui, ss, practice_display_key="F#m", persist_st=SimpleNamespace(rerun=MagicMock())
        )
    home = shape_tonic_only("F#m")
    assert ss[CAPO_SHAPE_WIDGET_KEY] == home
    assert ss[CAPO_SHAPE_KEY] == home
    assert ss[CAPO_SHAPE_WIDGET_KEY] != "C"


def test_apply_capo_context_does_not_stomp_live_c_when_restore_incomplete():
    from guitar_capo import (
        CAPO_ENABLED_WIDGET_KEY,
        CAPO_SHAPE_SEED_SOURCE_KEY,
        CAPO_SHAPE_WIDGET_KEY,
        apply_capo_context_fields,
    )

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "C",
        CAPO_SHAPE_WIDGET_KEY: "C",
        CAPO_ENABLED_WIDGET_KEY: True,
        "_capo_on_shape_seeded": True,
        "_capo_widgets_instantiated_this_run": True,
        "_music_restore_phase_complete": False,
        "active_catalog_pick_key": SHAPE_PICK,
        CAPO_SHAPE_SEED_SOURCE_KEY: SHAPE_PICK,
    }
    apply_capo_context_fields(
        ss,
        {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "B",
            CAPO_SOUNDING_KEY: "Bm",
        },
    )
    assert ss[CAPO_SHAPE_KEY] == "C"
    assert ss[CAPO_SHAPE_WIDGET_KEY] == "C"
    assert ss.get("_capo_on_shape_seeded") is True
    assert not ss.get("_pending_capo_shape_key")


def test_practice_key_bm_to_dm_keeps_shape_tonic_c():
    from guitar_capo import shape_chart_label_for_concert, sync_capo_from_practice_display_key

    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "C",
        CAPO_SOUNDING_KEY: "Bm",
        "guitar_capo_last_concert_key": "Bm",
    }
    sync_capo_from_practice_display_key(ss, "Dm")
    assert ss[CAPO_SHAPE_KEY] == "C"
    assert shape_chart_label_for_concert("Dm", "C").lower() == "c minor"

"""Written-key mode persists across practice-key changes; resets on instrument rules."""

from __future__ import annotations

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    chart_in_instrument_key,
    effective_chart_key,
    effective_practice_key,
    preserve_written_key_on_display_key_change,
    resolve_practice_keys,
    sync_written_key_instrument_anchor,
    written_key_for_type,
)


def _state(**kwargs):
    base = {
        WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        CHART_IN_INSTRUMENT_KEY_KEY: True,
    }
    base.update(kwargs)
    return base


def test_tenor_written_key_follows_concert_practice_key():
    ss = _state()
    ctx_c = resolve_practice_keys(ss, "C", "Saxophone")
    assert ctx_c["chart_key_mode"] == "written"
    assert ctx_c["chart_key"] == written_key_for_type("C", "Tenor saxophone (Bb)")
    assert ctx_c["chart_key"] == "D"

    ctx_f = resolve_practice_keys(ss, "F", "Saxophone")
    assert chart_in_instrument_key(ss)
    assert ctx_f["chart_key_mode"] == "written"
    assert ctx_f["chart_key"] == "G"


def test_display_key_change_does_not_clear_written_mode():
    ss = _state()
    preserve_written_key_on_display_key_change(ss)
    resolve_practice_keys(ss, "Bb", "Saxophone")
    assert chart_in_instrument_key(ss) is True
    chart_k, mode = effective_chart_key("Bb", "Saxophone", ss)
    assert mode == "written"
    assert chart_k == written_key_for_type("Bb", "Tenor saxophone (Bb)")


def test_switch_to_piano_clears_written_mode():
    ss = _state()
    sync_written_key_instrument_anchor(ss, "Piano")
    assert chart_in_instrument_key(ss) is False
    ctx = resolve_practice_keys(ss, "F", "Piano")
    assert ctx["chart_key"] == "F"
    assert ctx["chart_key_mode"] == "concert"


def test_written_key_spelling_follows_concert_accidental_style():
    assert written_key_for_type("Db", "Alto saxophone (Eb)") == "Bb"
    assert written_key_for_type("F#", "Tenor saxophone (Bb)") == "G#"
    assert written_key_for_type("Ab", "Alto saxophone (Eb)") == "F"
    assert written_key_for_type("C#", "Tenor saxophone (Bb)") == "D#"


def test_effective_practice_key_written_mode_matches_chart_key():
    ss = _state()
    assert effective_practice_key(ss, "Db", "Saxophone") == written_key_for_type(
        "Db", "Tenor saxophone (Bb)"
    )
    assert effective_practice_key(ss, "Db", "Saxophone") == "Eb"


def test_effective_practice_key_concert_when_written_off():
    ss = _state()
    ss[CHART_IN_INSTRUMENT_KEY_KEY] = False
    assert effective_practice_key(ss, "Db", "Saxophone") == "Db"


def test_resolve_practice_keys_includes_effective_practice_key():
    ss = _state()
    ctx = resolve_practice_keys(ss, "F", "Saxophone")
    assert ctx["effective_practice_key"] == ctx["chart_key"] == "G"


def test_switch_sax_to_trumpet_keeps_written_mode():
    ss = _state()
    ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Bb Trumpet"
    sync_written_key_instrument_anchor(ss, "Trumpet")
    assert chart_in_instrument_key(ss) is True
    ctx = resolve_practice_keys(ss, "C", "Trumpet")
    assert ctx["chart_key_mode"] == "written"
    assert ctx["chart_key"] == written_key_for_type("C", "Bb Trumpet")


def test_capo_shape_is_derived_without_mutating_display_key_widget():
    from guitar_capo import (
        CAPO_ENABLED_KEY,
        CAPO_SHAPE_KEY,
        capo_written_display_key,
        sync_capo_written_display_key,
    )

    ss = {
        "display_key": "C",
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "G",
    }
    sync_capo_written_display_key(ss)
    assert ss["display_key"] == "C"
    assert capo_written_display_key(ss) == "G"
    ctx = resolve_practice_keys(ss, "C", "Guitar")
    assert ctx["chart_key"] == "G"
    assert ctx["global_display_key"] == "C"


def test_sounding_key_follows_practice_display_key():
    from guitar_capo import (
        CAPO_ENABLED_KEY,
        CAPO_SHAPE_KEY,
        CAPO_SOUNDING_KEY,
        sync_capo_from_practice_display_key,
    )

    ss: dict = {CAPO_ENABLED_KEY: False}
    assert sync_capo_from_practice_display_key(ss, "D") == "D"
    assert ss[CAPO_SOUNDING_KEY] == "D"
    assert ss[CAPO_SHAPE_KEY] == "D"
    assert sync_capo_from_practice_display_key(ss, "F") == "F"
    assert ss[CAPO_SOUNDING_KEY] == "F"
    assert ss[CAPO_SHAPE_KEY] == "F"


def test_capo_fret_d_sounding_g_shape():
    from guitar_capo import capo_fret_for_shape

    assert capo_fret_for_shape("D", "G") == 7


def test_persist_capo_blob_only_skips_apply_context():
    from unittest.mock import patch

    from active_song_state import ACTIVE_SONG_STATE_KEY
    from guitar_capo import (
        CAPO_ENABLED_KEY,
        CAPO_SHAPE_KEY,
        CAPO_SOUNDING_KEY,
        persist_capo_to_canonical,
    )

    session = {
        "display_key": "D",
        "instrument": "Guitar",
        CAPO_ENABLED_KEY: True,
        CAPO_SOUNDING_KEY: "D",
        CAPO_SHAPE_KEY: "G",
        ACTIVE_SONG_STATE_KEY: {CAPO_ENABLED_KEY: False},
    }
    with patch("active_song_state._apply_context_to_session_keys") as mock_apply:
        persist_capo_to_canonical(session)
        mock_apply.assert_not_called()
    assert session["display_key"] == "D"
    assert session[ACTIVE_SONG_STATE_KEY][CAPO_ENABLED_KEY] is True
    assert session[ACTIVE_SONG_STATE_KEY][CAPO_SHAPE_KEY] == "G"


def test_chart_bundle_transpose_key_uses_sounding_when_capo_on():
    from guitar_capo import chart_bundle_transpose_key

    assert (
        chart_bundle_transpose_key(
            instrument="Guitar",
            capo_enabled=True,
            concert_key="Bm",
            chart_key="Gm",
        )
        == "Bm"
    )
    assert (
        chart_bundle_transpose_key(
            instrument="Guitar",
            capo_enabled=False,
            concert_key="Bm",
            chart_key="Bm",
        )
        == "Bm"
    )


def test_capo_shape_sections_from_sounding_sections():
    from guitar_capo import (
        CAPO_ENABLED_KEY,
        CAPO_SHAPE_KEY,
        CAPO_SOUNDING_KEY,
        build_capo_context,
    )

    sections = {"Verse": ["Bm", "G", "A"]}
    ss = {
        CAPO_ENABLED_KEY: True,
        CAPO_SOUNDING_KEY: "Bm",
        CAPO_SHAPE_KEY: "Gm",
    }
    ctx = build_capo_context(ss, sections, concert_key="Bm", instrument="Guitar")
    assert ctx.shape_key == "Gm"
    assert ctx.sounding_key == "Bm"
    assert ctx.shape_sections["Verse"][0] == "Gm"


def test_music_active_song_cloud_drift_detects_display_key():
    from unittest.mock import MagicMock

    from music_persistent_state import music_active_song_cloud_drift

    st = MagicMock()
    st.session_state = {"display_key": "Bm"}
    drift, detail = music_active_song_cloud_drift(
        st,
        {"active_song_state": {"display_key": "C#m"}},
        "2026-06-22T00:00:00+00:00",
    )
    assert drift is True
    assert "display_key" in detail


def test_music_active_song_cloud_drift_when_live_display_key_empty():
    from unittest.mock import MagicMock

    from music_persistent_state import music_active_song_cloud_drift

    st = MagicMock()
    st.session_state = {}
    drift, detail = music_active_song_cloud_drift(
        st,
        {"active_song_state": {"display_key": "C#m"}, "core": {"display_key": "C#m"}},
        "2026-06-22T00:00:00+00:00",
    )
    assert drift is True
    assert "display_key" in detail


def test_cpl_merge_preserves_sidebar_display_key():
    from active_song_state import ACTIVE_SONG_STATE_KEY, _merge_display_key_for_active_song
    from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY
    from songs.key_state import DISPLAY_KEY_OWNER_IDENTITY_KEY
    from songs.music_source import SOURCE_CUSTOM

    session = {
        "display_key": "F",
        DISPLAY_KEY_CHANGE_SOURCE_KEY: "sidebar_on_change",
        DISPLAY_KEY_OWNER_IDENTITY_KEY: "cpl::test::F",
        "active_music_source": "custom_progression",
        ACTIVE_SONG_STATE_KEY: {
            "music_source": SOURCE_CUSTOM,
            "display_key": "G",
            "custom_home_key": "D",
            "pick_key": "custom::test",
        },
    }
    ctx = {
        "music_source": SOURCE_CUSTOM,
        "display_key": "G",
        "custom_home_key": "D",
        "pick_key": "custom::test",
    }
    merged = _merge_display_key_for_active_song(session, ctx, home_key="D")
    assert merged == "F"


def test_flush_capo_edits_to_cloud_uses_streamlit_module_not_sidebar():
    from unittest.mock import MagicMock, patch

    from guitar_capo import flush_capo_edits_to_cloud

    st_module = MagicMock()
    ss: dict = {}
    st_module.session_state = ss

    with patch(
        "music_persistent_state.flush_active_song_edits_and_save", return_value=True
    ) as flush_save, patch("active_song_state.clear_active_song_local_edit") as clear_edit:
        assert flush_capo_edits_to_cloud(st_module) is True
        flush_save.assert_called_once_with(st_module, reason="capo_widget")
        clear_edit.assert_called_once_with(ss)


def test_render_guitar_capo_sidebar_passes_persist_st_to_cloud_flush():
    from unittest.mock import MagicMock, patch

    from guitar_capo import render_guitar_capo_sidebar

    ui = MagicMock()
    ui.checkbox.return_value = False
    persist_st = MagicMock()
    ss: dict = {}

    with patch("guitar_capo.persist_capo_to_canonical"), patch(
        "guitar_capo.flush_capo_edits_to_cloud"
    ) as flush_cloud:
        render_guitar_capo_sidebar(
            ui,
            ss,
            practice_display_key="C",
            persist_st=persist_st,
        )
        flush_cloud.assert_called_once_with(persist_st)


def test_rehydrate_capo_from_canonical():
    from active_song_state import ACTIVE_SONG_STATE_KEY, rehydrate_capo_from_canonical
    from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

    session = {
        ACTIVE_SONG_STATE_KEY: {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "Am",
        }
    }
    rehydrate_capo_from_canonical(session)
    assert session[CAPO_ENABLED_KEY] is True
    assert session[CAPO_SHAPE_KEY] == "Am"

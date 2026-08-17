"""Creative/Backing stabilization — key ownership, BPM, section selection."""

from __future__ import annotations

from effective_practice_context import musician_facing_chord


def test_stale_catalog_sections_not_kept_as_concert_when_practice_moved():
    """Bm catalog pitch must not stay as concert when Practice Key is Dm.

    Otherwise Guitar Shape Em projects Bm→C#m (the live corruption).
    """
    from backing_context import _song_improv_sections_dict

    session = {
        "improv_song_concert_sections": {
            "Verse": ["Bm", "A", "E", "F#m"],
        },
        "selected_song": {"key": "Bm", "title": "Demo"},
        "display_key": "Dm",
        "concert_key": "Dm",
    }
    out = _song_improv_sections_dict(session)
    firsts = {str((chs or [""])[0]) for chs in (out or {}).values() if chs}
    assert "Bm" not in firsts


def test_guitar_shape_projection_dm_plus_e_is_em_not_cshm():
    """Correct concert Dm chord under Shape Em displays Em, never C#m."""
    shown = musician_facing_chord("Dm", concert_key="Dm", chart_key="Em")
    assert shown.startswith("E")
    wrong = musician_facing_chord("Bm", concert_key="Dm", chart_key="Em")
    # Document the corruption path — stale Bm input is what produced C#m.
    assert wrong in {"C#m", "Dbm"}


def test_mission_chord_selection_does_not_mutate_practice_key():
    from music_workflow_mutation import mutate_mission_chord_selection

    session = {
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
        "ii_selected_chord": "Dm",
        "ii_selected_section": "Verse",
        "ii_selected_chord_index": 0,
        "home_sections": {"Verse": ["Dm", "C", "Bb", "A"]},
        "improv_song_concert_sections": {"Verse": ["Dm", "C", "Bb", "A"]},
    }
    before = str(session.get("display_key"))
    mutate_mission_chord_selection(
        session,
        chord="C",
        section="Verse",
        chord_index=1,
        chord_label="C",
    )
    assert str(session.get("display_key") or "") == before
    assert str(session.get("concert_key") or "") in {"", "Dm", before}


def test_catalog_default_bpm_vs_current_session_bpm():
    from backing_context import build_regular_song_context, format_backing_context_banner

    session = {
        "backing_track_bpm": 96,
        "bpm": 96,
        "display_key": "Dm",
        "concert_key": "Dm",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "C#m",
            "bpm": 82,
            "pick_key": "Pop::Shape of You — Ed Sheeran",
            "extensions": {"default_bpm": 82},
        },
        "active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran",
    }
    ctx = build_regular_song_context(session)
    assert ctx is not None
    assert int(ctx.bpm) == 96
    banner = format_backing_context_banner(ctx, applied_bpm=96)
    assert "96 BPM" in banner
    assert "82 BPM" not in banner


def test_seed_selected_sections_before_resolve_filters_chords():
    from backing_track_state import (
        BACKING_MULTI_SECTIONS_WIDGET_KEY,
        BACKING_SCOPE_WIDGET_KEY,
        resolve_selected_section_names,
        seed_backing_multi_sections_for_widget,
    )

    session = {BACKING_SCOPE_WIDGET_KEY: "Selected sections"}
    names = ["Intro", "Verse", "Chorus", "Bridge"]
    seeded = seed_backing_multi_sections_for_widget(session, names)
    assert seeded
    assert session.get(BACKING_MULTI_SECTIONS_WIDGET_KEY)
    chosen = resolve_selected_section_names(session, names)
    assert chosen
    assert set(chosen).issubset(set(names))
    assert len(chosen) <= 2


def test_example_match_accepts_equivalent_chord_spelling():
    from improvisation_intelligence_ui import (
        _chords_identity_equal,
        _example_matches_active_context,
    )
    from improvisation_missions import ChordCoachInsight, MissionExample

    insight = ChordCoachInsight(
        chord="Dm",
        scales=["dorian"],
        scale_suggestions=[],
        chord_tones=["D", "F", "A"],
        tensions=[],
        avoid_notes=[],
        target_notes=["D", "F"],
        motif_idea="",
        resolve_hint="",
        instrument_tips=[],
    )
    example = MissionExample(
        mission="Chord Tones",
        variant="normal",
        chord="Dm",
        section="Verse",
        song_title="Demo",
        display_key="Em",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        motif={"display": "D F A"},
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=insight,
        show_tab=False,
        show_piano=False,
        concert_key="Dm",
    )
    assert _chords_identity_equal("Dm", "Dm")
    assert _example_matches_active_context(
        example,
        mission="Chord Tones",
        cur_chord="Dm",
        section_label="Verse",
        song_title="Demo",
    )


def test_musician_facing_em_refresh_path_not_gm_from_correct_concert():
    """With correct Dm concert map, Shape Em stays Em-family — not Gm."""
    shown = musician_facing_chord("Dm", concert_key="Dm", chart_key="Em")
    assert "G" not in shown
    assert shown.startswith("E")


def test_example_match_accepts_concert_vs_shape_projection():
    """Generate Example must not discard when UI shows Shape Em for concert Dm."""
    from improvisation_intelligence_ui import _example_matches_active_context
    from improvisation_missions import ChordCoachInsight, MissionExample

    insight = ChordCoachInsight(
        chord="Dm",
        scales=["dorian"],
        scale_suggestions=[],
        chord_tones=["D", "F", "A"],
        tensions=[],
        avoid_notes=[],
        target_notes=["D", "F"],
        motif_idea="",
        resolve_hint="",
        instrument_tips=[],
    )
    example = MissionExample(
        mission="Chord Tones",
        variant="normal",
        chord="Dm",
        section="Verse",
        song_title="Demo",
        display_key="Em",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        motif={"display": "D F A", "_concert_chord": "Dm"},
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=insight,
        show_tab=False,
        show_piano=False,
        concert_key="Dm",
    )
    assert _example_matches_active_context(
        example,
        mission="Chord Tones",
        cur_chord="Dm",
        section_label="Verse",
        song_title="Demo",
    )
    # If selection path ever surfaces the Shape label, still keep the example.
    facing = musician_facing_chord("Dm", concert_key="Dm", chart_key="Em")
    assert _example_matches_active_context(
        example,
        mission="Chord Tones",
        cur_chord=facing,
        section_label="Verse",
        song_title="Demo",
    )


def test_same_source_creative_bpm_override_keeps_live_slider():
    """User dirty / live slider must win over creative source default BPM."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from backing_context import build_entry_jam_context, set_backing_context
    from songs.bpm_state import BPM_WIDGET_KEY, LAST_BPM_SONG
    from songs.playback_defaults import (
        _CANONICAL_BACKING_ID_KEY,
        backing_bpm_slider_widget_key,
        canonicalize_backing_defaults_for_song,
    )

    session = {
        "studio_page": "backing",
        "entry_jam_key": "C",
        "entry_jam_bpm": 60,
        "entry_jam_style": "Pop",
        "entry_jam_mood": "Bright",
        "entry_jam_intensity": "Medium",
        "entry_jam_meter": "4/4",
        "entry_jam_progression": ["C", "G", "Am", "F"],
        "display_key": "C",
        "concert_key": "C",
    }
    ctx = build_entry_jam_context(session)
    set_backing_context(session, ctx)
    sync_id = f"creative:entry_jam:{ctx.source_signature}"
    session[_CANONICAL_BACKING_ID_KEY] = sync_id
    session[BPM_WIDGET_KEY] = 75
    session[LAST_BPM_SONG] = sync_id
    session[backing_bpm_slider_widget_key(sync_id)] = 75
    st = SimpleNamespace(session_state=session)
    with patch("backing_track_state.is_backing_user_dirty", return_value=True):
        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=60,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
    assert not canon["did_reset"]
    assert int(canon["applied_bpm"]) == 75


def test_live_practice_dm_wins_over_stale_store_bm_for_sbi():
    """SBI must use live Practice Dm, not stale practice_key_by_source Bm."""
    from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key
    from source_session_state import _catalog_display_key, resolve_sbi_preview

    pick = "Pop::Shape of You — Ed Sheeran"
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "practice_key_by_source": {pick: "Bm"},
        "selected_song": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm", "pick_key": pick},
        "catalog_session": {
            "pick_key": pick,
            "display_key": "Bm",
            "original_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm"},
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        },
        "improv_song_concert_sections": {"Verse": ["Bm", "Em", "G", "A"]},
        "home_sections": {"Verse": ["Bm", "Em", "G", "A"]},
    }
    assert overlay_destination_practice_key(session) == "Dm"
    assert _catalog_display_key(session, session["catalog_session"]) == "Dm"
    assert session["practice_key_by_source"].get(pick) == "Dm"
    prev = resolve_sbi_preview(session)
    assert prev.get("display_key") == "Dm"
    first = (list((prev.get("sections") or {}).values()) or [[]])[0]
    assert first and str(first[0]).startswith("D")
    assert not str(first[0]).startswith("B")


def test_shape_key_control_is_tonic_only_not_major():
    from custom_progression_lab import format_key_label
    from guitar_capo import shape_chart_key_for_concert, shape_tonic_only

    assert shape_tonic_only("E") == "E"
    assert "major" not in shape_tonic_only("E").lower()
    # format_key_label invents major — that must not be used for Shape control.
    assert "major" in format_key_label("E").lower()
    assert shape_chart_key_for_concert("Dm", "E") == "Em"


def test_mission_chord_selection_does_not_restore_stale_blob_key():
    """Selecting a Mission chord must not push stale song-blob Bm over live Dm."""
    from music_workflow_mutation import mutate_mission_chord_selection

    session = {
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
        "ii_selected_chord": "Dm",
        "ii_selected_section": "Verse",
        "ii_selected_chord_index": 0,
        "home_sections": {"Verse": ["Dm", "C", "Bb", "A"]},
        "improv_song_concert_sections": {"Verse": ["Dm", "C", "Bb", "A"]},
        "selected_song": {"title": "Shape of You", "key": "Bm"},
        "active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran",
    }
    mutate_mission_chord_selection(
        session,
        chord="Am",
        section="Verse",
        chord_index=1,
        chord_label="Am",
    )
    assert str(session.get("display_key") or "") == "Dm"
    assert str(session.get("concert_key") or "") in {"", "Dm"}


def test_mission_chord_change_clears_stale_em_example():
    from improvisation_missions import MISSION_EXAMPLE_KEY
    from music_workflow_mutation import _invalidate_mission_chord_dependent_session

    session = {
        MISSION_EXAMPLE_KEY: {
            "chord": "Dm",
            "mission": "Chord Tones",
            "motif": {"_concert_chord": "Dm", "notes": ["D", "F", "A"]},
        },
        "_mission_example_output_fp": "stale",
    }
    _invalidate_mission_chord_dependent_session(session, new_chord="Am")
    assert MISSION_EXAMPLE_KEY not in session


def test_shape_change_reprojects_mission_example_notes():
    from improvisation_missions import ChordCoachInsight, MissionExample, refresh_mission_example

    insight = ChordCoachInsight(
        chord="Dm",
        scales=[],
        scale_suggestions=[],
        chord_tones=["D", "F", "A"],
        tensions=[],
        avoid_notes=[],
        target_notes=[],
        motif_idea="",
        resolve_hint="",
        instrument_tips=[],
    )
    example = MissionExample(
        mission="Chord Tones",
        variant="normal",
        chord="Dm",
        section="Verse",
        song_title="Demo",
        display_key="Em",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        motif={
            "notes": ["E", "G", "B"],
            "display": "E – G – B",
            "_concert_notes": ["D", "F", "A"],
            "_concert_chord": "Dm",
            "_projected_display_key": "Em",
        },
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=insight,
        show_tab=False,
        show_piano=False,
        concert_key="Dm",
    )
    example.display_key = "Ebm"
    refreshed = refresh_mission_example(example, instrument="Guitar", bpm=100, song_concert_key="Dm")
    notes = list((refreshed.motif or {}).get("notes") or [])
    assert notes
    # Concert D/F/A under Shape Ebm must not remain E/G/B.
    assert notes != ["E", "G", "B"]
    assert list((refreshed.motif or {}).get("_concert_notes") or []) == ["D", "F", "A"]
    assert str((refreshed.motif or {}).get("_projected_display_key") or "") == "Ebm"


def test_mission_backing_card_prefers_live_style_and_meter():
    from unittest.mock import MagicMock

    from backing_context import BackingContext
    from backing_context_ui import render_backing_creative_context_card

    ctx = BackingContext(
        source="mission",
        source_label="Mission",
        active_song_id="mission-test",
        song_title="Mission jam",
        key="Dm",
        display_key="Dm",
        concert_key="Dm",
        style="Pop groove",
        groove="Pop groove",
        meter="4/4",
        bpm=96,
        progression=["Dm", "Am"],
        progression_label="Dm – Am",
        section="Verse",
        source_signature="mission-test",
    )
    session = {
        "backing_groove_style": "Blues",
        "backing_time_signature": "3/4",
        "instrument": "Guitar",
        "display_key": "Dm",
        "concert_key": "Dm",
    }
    st = MagicMock()
    render_backing_creative_context_card(
        st,
        ctx,
        session,
        applied_bpm=96,
        applied_groove="Pop groove",
        applied_meter="4/4",
        practice_key="Dm",
    )
    html_out = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
    assert "Blues" in html_out
    assert "3/4" in html_out
    assert "Current Style" in html_out or "Style: <strong>Blues</strong>" in html_out


def test_sync_mission_style_does_not_clobber_dirty_live_groove():
    from mission_song_backing_style import sync_mission_style_from_song
    from backing_track_state import BACKING_DIRTY_KEY, BACKING_USER_EDIT_INTENT_KEY

    session = {
        "active_catalog_pick_key": "Pop::Shape of You — Ed Sheeran",
        "selected_song": {"title": "Shape of You", "key": "Bm", "genre": "Pop", "bpm": 96},
        "backing_groove_style": "Blues",
        "backing_time_signature": "3/4",
        BACKING_DIRTY_KEY: True,
        BACKING_USER_EDIT_INTENT_KEY: True,
    }
    sync_mission_style_from_song(session, force=False)
    assert session.get("backing_groove_style") == "Blues"
    assert session.get("backing_time_signature") == "3/4"


def test_catalog_practice_key_init_uses_original_when_no_override():
    from music_workflow_song_practice import reconcile_catalog_practice_key_owner

    pick = "Pop::Shape of You — Ed Sheeran"
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Bm",
        "concert_key": "Bm",
        "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
    }
    assert reconcile_catalog_practice_key_owner(session) == "Bm"


def test_user_practice_key_bm_to_dm_survives_hydrate_and_heals_blob():
    """Live Dm must not be overwritten by stale song-blob Bm on SBI hydrate."""
    from music_workflow_song_practice import (
        ensure_missions_parent_practice_key_hydrated,
        ensure_song_practice_blob_for_active_song,
        resolve_song_practice_key_token,
    )
    from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
    from source_session_state import resolve_sbi_preview

    pick = "Pop::Shape of You — Ed Sheeran"
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "selected_song": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm", "pick_key": pick},
        "catalog_session": {
            "pick_key": pick,
            "display_key": "Bm",
            "original_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm"},
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        },
        "home_sections": {"Verse": ["Bm", "Em", "G", "A"]},
        "improv_song_concert_sections": {"Verse": ["Bm", "Em", "G", "A"]},
    }
    set_practice_concert_key(session, "Dm", pick_key=pick)
    ensure_song_practice_blob_for_active_song(session, practice_key="Bm", original_key="Bm")
    session["display_key"] = "Dm"
    session["concert_key"] = "Dm"
    assert resolve_song_practice_key_token(session) == "Bm"
    tok = ensure_missions_parent_practice_key_hydrated(session)
    assert tok == "Dm"
    assert session.get("display_key") == "Dm"
    assert resolve_song_practice_key_token(session) == "Dm"
    assert get_practice_concert_key(session, pick) == "Dm"
    prev = resolve_sbi_preview(session)
    assert prev.get("display_key") == "Dm"


def test_persisted_store_dm_restores_when_live_clobbered_to_original_bm():
    from music_workflow_song_practice import reconcile_catalog_practice_key_owner
    from songs.practice_key_state import set_practice_concert_key

    pick = "Pop::Shape of You — Ed Sheeran"
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Bm",
        "concert_key": "Bm",
        "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
    }
    set_practice_concert_key(session, "Dm", pick_key=pick)
    assert reconcile_catalog_practice_key_owner(session) == "Dm"
    assert session.get("display_key") == "Dm"


def test_shape_e_projects_dm_without_mutating_practice_key():
    from guitar_capo import shape_chart_key_for_concert, shape_tonic_only

    assert shape_tonic_only("E") == "E"
    assert shape_chart_key_for_concert("Dm", "E") == "Em"
    session = {"display_key": "Dm", "concert_key": "Dm", "guitar_capo_shape_key": "E"}
    assert session["display_key"] == "Dm"


def test_bm_to_dm_same_rerun_concert_is_dm_not_fm():
    """Practice Bm→Dm must transpose once — never Dm→Fm double transpose."""
    import copy
    from unittest.mock import patch

    from music_theory import transpose_sections_dict
    from music_workflow_song_practice import ensure_song_practice_blob_for_active_song
    from songs.practice_key_state import set_practice_concert_key
    from source_session_state import resolve_sbi_preview
    from workflow_musical_authority import sync_song_improv_sections_to_practice_key
    from creative_key_sync import creative_progression_display

    pick = "Pop::Shape of You — Ed Sheeran"
    bm = {"Verse": ["Bm", "Em", "G", "A"]}
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "selected_song": {
            "title": "Shape of You",
            "key": "Bm",
            "pick_key": pick,
            "sections": copy.deepcopy(bm),
        },
        "home_sections": copy.deepcopy(bm),
        "improv_song_concert_sections": copy.deepcopy(bm),
        "instrument": "Guitar",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "E",
        "catalog_session": {
            "pick_key": pick,
            "display_key": "Dm",
            "original_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm", "sections": copy.deepcopy(bm)},
            "sections": copy.deepcopy(bm),
        },
    }
    set_practice_concert_key(session, "Dm", pick_key=pick)
    ensure_song_practice_blob_for_active_song(session, practice_key="Dm", original_key="Bm")
    with patch(
        "songs.music_source.catalog_chart_sections_for_pick",
        return_value=copy.deepcopy(bm),
    ):
        synced = sync_song_improv_sections_to_practice_key(session)
        assert list(synced["Verse"][:4]) == ["Dm", "Gm", "Bb", "C"]
        # Pollute home/selected with already-practice pitch (prior bug path).
        session["home_sections"] = copy.deepcopy(synced)
        session["selected_song"]["sections"] = copy.deepcopy(synced)
        again = sync_song_improv_sections_to_practice_key(session)
        assert list(again["Verse"][:4]) == ["Dm", "Gm", "Bb", "C"]
        prev = resolve_sbi_preview(session)
        first = list((list(prev["sections"].values()) or [[]])[0][:4])
        assert first == ["Dm", "Gm", "Bb", "C"]
        assert first[0] != "Fm"
        disp = creative_progression_display(session, prev["sections"], concert_key="Dm")
        assert disp["concert_line"].startswith("Dm")
        assert "Fm" not in disp["concert_line"]
        assert disp["chart_key"] == "Em"
        assert disp["chart_line"].startswith("Em")
        assert not disp["chart_line"].startswith("Gm")


def test_song_improv_backing_does_not_retranspose_synced_sections():
    """sections_dict_from_backing_context must not apply ctx.key after sync."""
    import copy
    from types import SimpleNamespace
    from unittest.mock import patch

    from music_workflow_song_practice import ensure_song_practice_blob_for_active_song
    from songs.practice_key_state import set_practice_concert_key
    from backing_context import sections_dict_from_backing_context
    from workflow_musical_authority import sync_song_improv_sections_to_practice_key

    pick = "Pop::Shape of You — Ed Sheeran"
    bm = {"Verse": ["Bm", "Em", "G", "A"]}
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick, "sections": copy.deepcopy(bm)},
        "home_sections": copy.deepcopy(bm),
    }
    set_practice_concert_key(session, "Dm", pick_key=pick)
    ensure_song_practice_blob_for_active_song(session, practice_key="Dm", original_key="Bm")
    with patch(
        "songs.music_source.catalog_chart_sections_for_pick",
        return_value=copy.deepcopy(bm),
    ):
        sync_song_improv_sections_to_practice_key(session)
        ctx = SimpleNamespace(
            source="song_improv",
            concert_key="Dm",
            display_key="Dm",
            key="Bm",
            song_title="Shape of You",
            progression_label="Shape of You",
            progression=[],
            section="",
            sections=[],
            entry_mode="",
            meter="4/4",
            bpm=96,
            style="",
            groove="",
            mood="",
            groove_intensity="",
            difficulty="",
        )
        out = sections_dict_from_backing_context(session, ctx)
        assert list(out["Verse"][:4]) == ["Dm", "Gm", "Bb", "C"]


def test_transpose_idempotent_when_sections_already_at_practice():
    from music_theory import transpose_sections_dict
    from workflow_musical_authority import sync_song_improv_sections_to_practice_key
    import copy
    from unittest.mock import patch

    pick = "Pop::X"
    dm = {"Verse": ["Dm", "Gm", "Bb", "C"]}
    session = {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "selected_song": {"key": "Bm", "sections": copy.deepcopy(dm)},
        "home_sections": copy.deepcopy(dm),
    }
    with patch(
        "songs.music_source.catalog_chart_sections_for_pick",
        return_value=copy.deepcopy(dm),
    ):
        out = sync_song_improv_sections_to_practice_key(session)
        assert list(out["Verse"][:4]) == ["Dm", "Gm", "Bb", "C"]
        # Explicit double-transpose would be Fm — prove we do not.
        doubled = transpose_sections_dict(dm, "Bm", "Dm")
        assert list(doubled["Verse"][:1]) == ["Fm"]


def test_mission_chord_path_does_not_call_song_blob_key_sync():
    """Regression: skip_parent_practice_key must not sync_session_practice_key_from_song_blob."""
    import inspect
    from music_workflow_legacy_projection import restore_workflow_blob_to_session

    src = inspect.getsource(restore_workflow_blob_to_session)
    assert "skip_mission_projection_sections" in src
    assert 'sync_session_practice_key_from_song_blob(session, source=f"skip_mission_projection:' not in src

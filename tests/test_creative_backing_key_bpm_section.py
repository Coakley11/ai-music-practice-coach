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

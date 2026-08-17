"""Pass 5: shared Backing BPM lifecycle, subordinate Practice Key, Mission Shape reprojection."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from backing_context import (
    apply_backing_context_to_session,
    get_backing_context,
    open_backing_from_creative,
)
from backing_play_session import (
    backing_play_session_has_override,
    capture_backing_play_session_overrides,
    expire_backing_play_session_on_page_exit,
    sync_backing_play_session_on_backing_page,
)
from creative_key_sync import prepare_backing_context_sidebar_display_key, user_sidebar_display_key_authoritative
from effective_practice_context import musician_facing_chord
from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    generate_mission_example,
    refresh_mission_example,
)
from music_workflow_generated_session import commit_jam_session_generation, commit_style_jam_generation
from songs.bpm_state import BPM_WIDGET_KEY
from songs.playback_defaults import (
    backing_bpm_slider_widget_key,
    resolve_backing_bpm_for_slider,
    seed_backing_bpm_slider_before_widget,
    sync_backing_bpm_from_slider,
)
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
STYLE_SECTIONS = {"A (Bossa Nova)": ["Cmaj7", "Dm7", "G7", "C6"]}
JAM_SECTIONS = {"Head": ["Am7", "D7", "Gmaj7"]}


class _FakeSt:
    def __init__(self, session: dict):
        self.session_state = session


def _style_jam_session(*, bpm: int = 130) -> dict:
    session = {
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Bossa Nova",
        "improv_mood": "Mellow",
        "improv_groove": "Medium",
        "improv_style_bpm": bpm,
        "improv_difficulty": "Intermediate",
        "improv_style_key": "C",
        "improv_generated_sections": copy.deepcopy(STYLE_SECTIONS),
        "active_catalog_pick_key": SHAPE_PICK,
        "song": "Shape of You",
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
        "backing_track_bpm": 96,
        BPM_WIDGET_KEY: 96,
        "bpm": 96,
    }
    commit_style_jam_generation(
        session,
        key_center="C",
        style="Bossa Nova",
        section_map=copy.deepcopy(STYLE_SECTIONS),
        mood="Mellow",
        groove="Medium",
        tempo_bpm=bpm,
        new_session=True,
    )
    return session


def _jam_generator_session(*, bpm: int = 142) -> dict:
    session = {
        "studio_page": "creative",
        "improv_entry_mode": "Jam Session Generator",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_jam_key": "A minor",
        "improv_jam_bpm": bpm,
        "improv_generated_sections": copy.deepcopy(JAM_SECTIONS),
        "active_catalog_pick_key": SHAPE_PICK,
        "song": "Shape of You",
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
        "backing_track_bpm": 96,
        BPM_WIDGET_KEY: 96,
        "bpm": 96,
    }
    jam = {
        "id": "test-jam-gen",
        "bpm": bpm,
        "sections": copy.deepcopy(JAM_SECTIONS),
        "mood": "Mellow",
        "style": "Jazz Swing",
    }
    commit_jam_session_generation(
        session,
        jam,
        key_center="A minor",
        style="Jazz Swing",
        new_session=True,
    )
    return session


class TestBackingBpmWidgetLifecycle(unittest.TestCase):
    def test_sync_from_slider_does_not_mutate_widget_key(self) -> None:
        sync_id = "entry_jam::style::130"
        slider_key = backing_bpm_slider_widget_key(sync_id)
        st = _FakeSt(
            {
                "_active_bpm_sync_id": sync_id,
                slider_key: 96,
                BPM_WIDGET_KEY: 96,
                "backing_track_bpm": 96,
                "bpm": 96,
            }
        )
        bpm = sync_backing_bpm_from_slider(st, slider_bpm=112)
        self.assertEqual(bpm, 112)
        self.assertEqual(st.session_state[BPM_WIDGET_KEY], 112)
        self.assertEqual(st.session_state["backing_track_bpm"], 112)
        self.assertEqual(st.session_state["bpm"], 112)
        # Widget key remains whatever Streamlit owns; helper must not rewrite it.
        self.assertEqual(st.session_state[slider_key], 96)

    def test_style_jam_open_backing_initializes_current_bpm_from_generated(self) -> None:
        session = _style_jam_session(bpm=130)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        ctx = get_backing_context(session)
        assert ctx is not None
        self.assertEqual(int(ctx.bpm), 130)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 130)
        self.assertEqual(int(session.get(BPM_WIDGET_KEY) or 0), 130)
        sync_id = str(session.get("_active_bpm_sync_id") or session.get("_backing_trace_sync_id") or "")
        if sync_id:
            self.assertEqual(int(session.get(backing_bpm_slider_widget_key(sync_id)) or 0), 130)

    def test_style_jam_slider_change_aligns_domain_current(self) -> None:
        session = _style_jam_session(bpm=130)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        sync_backing_bpm_from_slider(st, slider_bpm=112)
        self.assertEqual(int(session["backing_track_bpm"]), 112)
        self.assertEqual(int(session[BPM_WIDGET_KEY]), 112)
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "bpm"))

    def test_jam_generator_open_backing_uses_generated_bpm(self) -> None:
        session = _jam_generator_session(bpm=142)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 142)
        ctx = get_backing_context(session)
        assert ctx is not None
        self.assertEqual(int(ctx.bpm), 142)

    def test_refresh_same_play_session_preserves_current_bpm(self) -> None:
        session = _style_jam_session(bpm=130)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        sync_backing_bpm_from_slider(st, slider_bpm=112)
        capture_backing_play_session_overrides(session)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 112)
        # Same signature re-open must not reset Current BPM to source 130.
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 112)

    def test_leave_backing_expires_temporary_bpm_override(self) -> None:
        session = _style_jam_session(bpm=130)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        sync_backing_bpm_from_slider(st, slider_bpm=112)
        capture_backing_play_session_overrides(session)
        expire_backing_play_session_on_page_exit(
            session, previous_page="backing", new_page="creative"
        )
        self.assertFalse(backing_play_session_has_override(session, "bpm"))

    def test_resolve_prefers_domain_over_stale_slider_before_widget(self) -> None:
        # Pre-widget seeding (open_backing / seed helper) must align slider to Current BPM.
        sync_id = "entry_jam::style::130"
        slider_key = backing_bpm_slider_widget_key(sync_id)
        st = _FakeSt(
            {
                "_active_bpm_sync_id": sync_id,
                slider_key: 96,
                BPM_WIDGET_KEY: 96,
                "backing_track_bpm": 96,
                "bpm": 96,
            }
        )
        seed_backing_bpm_slider_before_widget(st.session_state, sync_id=sync_id, bpm=130)
        resolved = resolve_backing_bpm_for_slider(
            st, sync_id=sync_id, default_bpm=130, song_just_reset=False
        )
        self.assertEqual(resolved, 130)
        self.assertEqual(int(st.session_state[slider_key]), 130)


class TestSubordinateBackingPracticeKey(unittest.TestCase):
    def test_apply_backing_context_does_not_overwrite_practice_key_for_sbi(self) -> None:
        from backing_context import BackingContext

        session = {
            "display_key": "Fm",
            "concert_key": "Fm",
            "display_key_change_source": "sidebar",
            "studio_page": "backing",
        }
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id="sbi",
            song_title="Shape of You",
            key="Dm",
            display_key="Dm",
            concert_key="Dm",
            style="Pop",
            groove="Pop",
            meter="4/4",
            bpm=96,
            progression=["Dm", "F"],
            progression_label="Dm – F",
            section="Verse",
            source_signature="sbi-sig",
        )
        apply_backing_context_to_session(session, ctx, widget_safe=True, apply_transport_bpm=False)
        self.assertEqual(session.get("display_key"), "Fm")

    def test_apply_backing_context_does_not_overwrite_practice_key_for_mission(self) -> None:
        from backing_context import BackingContext

        session = {
            "display_key": "Gm",
            "concert_key": "Gm",
            "display_key_change_source": "sidebar",
            "studio_page": "backing",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="mission",
            song_title="Shape of You",
            key="Dm",
            display_key="Dm",
            concert_key="Dm",
            style="Pop",
            groove="Pop",
            meter="4/4",
            bpm=96,
            progression=["Dm", "Am"],
            progression_label="Dm – Am",
            section="Verse",
            source_signature="mission-sig",
        )
        apply_backing_context_to_session(session, ctx, widget_safe=True, apply_transport_bpm=False)
        self.assertEqual(session.get("display_key"), "Gm")

    def test_prepare_sidebar_preserves_user_key_on_sbi_backing(self) -> None:
        from backing_context import BackingContext, set_backing_context

        session = {
            "display_key": "Fm",
            "concert_key": "Fm",
            "display_key_change_source": "sidebar",
            "studio_page": "backing",
            "instrument": "Guitar",
        }
        set_backing_context(
            session,
            BackingContext(
                source="song_improv",
                source_label="Song-Based Improvisation",
                active_song_id="sbi",
                song_title="Shape of You",
                key="Dm",
                display_key="Dm",
                concert_key="Dm",
                style="Pop",
                groove="Pop",
                meter="4/4",
                bpm=96,
                progression=["Dm"],
                progression_label="Dm",
                section="Verse",
                source_signature="sbi-sig",
            ),
        )
        self.assertTrue(user_sidebar_display_key_authoritative(session))
        st = _FakeSt(session)
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertIn("Fm", options)
        self.assertEqual(session.get("display_key"), "Fm")
        self.assertEqual(session.get("concert_key"), "Fm")

    def test_prepare_sidebar_preserves_user_key_on_mission_backing(self) -> None:
        from backing_context import BackingContext, set_backing_context

        session = {
            "display_key": "Gm",
            "concert_key": "Gm",
            "display_key_change_source": "sidebar",
            "studio_page": "backing",
            "instrument": "Guitar",
            "improv_intelligence_tab": "Missions",
        }
        set_backing_context(
            session,
            BackingContext(
                source="mission",
                source_label="Mission",
                active_song_id="mission",
                song_title="Shape of You",
                key="Dm",
                display_key="Dm",
                concert_key="Dm",
                style="Pop",
                groove="Pop",
                meter="4/4",
                bpm=96,
                progression=["Dm"],
                progression_label="Dm",
                section="Verse",
                source_signature="mission-sig",
            ),
        )
        st = _FakeSt(session)
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertIn("Gm", options)
        self.assertEqual(session.get("display_key"), "Gm")


class TestMissionShapeReprojectionAndGenerate(unittest.TestCase):
    def _ctx(self, *, concert: str, chart: str) -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center=concert,
            display_key=chart,
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Bb", "F"]},
            bpm=100,
        )

    def test_shape_change_keeps_canonical_and_updates_all_projected_fields(self) -> None:
        ctx = self._ctx(concert="Dm", chart="D# minor")
        example = generate_mission_example(
            "Focus on rhythm over note choice",
            improv_ctx=ctx,
            chord="Bb",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            bpm=100,
        )
        concert_chord = str((example.motif or {}).get("_concert_chord") or example.chord)
        concert_notes = list((example.motif or {}).get("_concert_notes") or [])
        self.assertEqual(concert_chord, "Bb")
        display_b = musician_facing_chord("Bb", concert_key="Dm", chart_key="D# minor")
        self.assertEqual(str((example.motif or {}).get("chord") or ""), display_b)
        self.assertIn(display_b, example.abc)

        example.display_key = "C# minor"
        refreshed = refresh_mission_example(
            example, instrument="Guitar", bpm=100, song_concert_key="Dm"
        )
        self.assertEqual(str((refreshed.motif or {}).get("_concert_chord") or ""), "Bb")
        self.assertEqual(list((refreshed.motif or {}).get("_concert_notes") or []), concert_notes)
        display_a = musician_facing_chord("Bb", concert_key="Dm", chart_key="C# minor")
        self.assertEqual(str((refreshed.motif or {}).get("chord") or ""), display_a)
        self.assertIn(f"— {display_a}", refreshed.abc)
        self.assertNotIn(f"— {display_b}", refreshed.abc)
        self.assertEqual(str(refreshed.insight.chord or ""), display_a)
        self.assertNotEqual(display_a, display_b)

    def test_stale_projected_concert_chord_is_recovered_on_refresh(self) -> None:
        # Simulate buggy storage: display chord B saved as "_concert_chord".
        from improvisation_missions import ChordCoachInsight, MissionExample

        display_b = musician_facing_chord("Bb", concert_key="Dm", chart_key="D# minor")
        example = MissionExample(
            mission="Focus on rhythm over note choice",
            variant="normal",
            chord=display_b,
            section="Verse",
            song_title="Shape of You",
            display_key="D# minor",
            concert_key="Dm",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            motif={
                "notes": ["B", "D", "F#"],
                "display": "B – D – F#",
                "chord": display_b,
                "_concert_chord": display_b,
                "_projected_display_key": "D# minor",
            },
            abc=f"T:Mission: Focus on rhythm over note choice — {display_b}",
            tab="",
            piano_html="",
            why="",
            practice_steps=[],
            insight=ChordCoachInsight(
                chord=display_b,
                scales=["B major"],
                scale_suggestions=[],
                chord_tones=["B"],
                tensions=[],
                avoid_notes=[],
                target_notes=[],
                motif_idea="",
                resolve_hint="",
                instrument_tips=[],
            ),
            show_tab=False,
            show_piano=False,
        )
        example.display_key = "C# minor"
        refreshed = refresh_mission_example(
            example, instrument="Guitar", bpm=100, song_concert_key="Dm"
        )
        display_a = musician_facing_chord("Bb", concert_key="Dm", chart_key="C# minor")
        self.assertEqual(str((refreshed.motif or {}).get("chord") or ""), display_a)
        self.assertNotEqual(str((refreshed.motif or {}).get("_concert_chord") or ""), display_b)

    def test_generate_uses_concert_map_chord_not_stale_projected_snap(self) -> None:
        from improvisation_intelligence_ui import (
            MISSIONS_GENERATE_CONTEXT_KEY,
            _run_mission_example_generate,
            _stash_missions_generate_context,
        )

        ctx = self._ctx(concert="Dm", chart="C# minor")
        session = {
            "song": "Shape of You",
            "display_key": "Dm",
            "concert_key": "Dm",
            "instrument": "Guitar",
            "level": "Intermediate",
            "focus": "Improvisation",
            "improv_mission_pick": "Focus on rhythm over note choice",
            "improv_active_mission": "Focus on rhythm over note choice",
            "ii_selected_chord": "A",  # stale Shape projection
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
            "home_sections": {"Verse": ["Bb", "F"]},
            "improv_song_concert_sections": {"Verse": ["Bb", "F"]},
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "C#",
        }
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Verse", ["Bb", "F"])],
            mission="Focus on rhythm over note choice",
            cur_chord="B",  # stale projected chord in snap
            section_label="Verse",
            chord_idx=0,
            live_inst="Guitar",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        session[MISSIONS_GENERATE_CONTEXT_KEY]["chart_key"] = "D# minor"
        session[MISSIONS_GENERATE_CONTEXT_KEY]["key_center"] = "Dm"
        with mock.patch("streamlit.session_state", session, create=True):
            _run_mission_example_generate(session, "normal")
        raw = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(raw, dict)
        motif = raw.get("motif") or {}
        self.assertEqual(str(motif.get("_concert_chord") or raw.get("chord") or ""), "Bb")
        display_a = musician_facing_chord("Bb", concert_key="Dm", chart_key="C# minor")
        self.assertEqual(str(motif.get("chord") or ""), display_a)

    def test_generate_first_click_stores_example(self) -> None:
        from improvisation_intelligence_ui import (
            _run_mission_example_generate,
            _stash_missions_generate_context,
        )

        ctx = self._ctx(concert="Dm", chart="Dm")
        session = {
            "song": "Shape of You",
            "display_key": "Dm",
            "concert_key": "Dm",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "Improvisation",
            "improv_mission_pick": "Focus on rhythm over note choice",
            "improv_active_mission": "Focus on rhythm over note choice",
            "ii_selected_chord": "Bb",
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
            "home_sections": {"Verse": ["Bb", "F"]},
            "improv_song_concert_sections": {"Verse": ["Bb", "F"]},
        }
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Verse", ["Bb", "F"])],
            mission="Focus on rhythm over note choice",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=0,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        with mock.patch("streamlit.session_state", session, create=True):
            _run_mission_example_generate(session, "normal")
        self.assertIsInstance(session.get(MISSION_EXAMPLE_KEY), dict)
        from improvisation_missions import MISSION_EXAMPLE_GEN_DIAG_KEY

        self.assertFalse((session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}).get("abort"))


if __name__ == "__main__":
    unittest.main()

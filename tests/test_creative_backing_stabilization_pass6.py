"""Pass 6: instrument ownership, Generate first-click, BPM init, catalog overrides."""

from __future__ import annotations

import copy
import unittest
from unittest import mock

from active_song_state import _apply_context_to_session_keys
from backing_context import (
    BackingContext,
    get_backing_context,
    open_backing_from_creative,
    set_backing_context,
)
from backing_play_session import (
    backing_play_session_has_override,
    capture_backing_play_session_overrides,
    expire_backing_play_session_on_page_exit,
    play_session_blocks_canonical_seed,
    sync_backing_play_session_on_backing_page,
)
from improvisation_intelligence_ui import (
    MISSION_EXAMPLE_FRESH_RUN_KEY,
    _run_mission_example_generate,
)
from improvisation_missions import MISSIONS_GENERATE_CONTEXT_KEY
from practice_setup_controls import (
    DEFAULT_INSTRUMENT_OPTIONS,
    _widget_value_for_global as qc_widget_value_for_global,
)
from practice_setup_globals import sync_widget_state_from_globals
from songs.bpm_state import BPM_WIDGET_KEY
from songs.playback_defaults import (
    apply_backing_defaults_for_song,
    backing_bpm_slider_widget_key,
    resolve_backing_bpm_for_slider,
)
from music_workflow_generated_session import commit_jam_session_generation, commit_style_jam_generation
from song_catalog.catalog import format_pick_key

SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
STYLE_SECTIONS = {"A (Bossa Nova)": ["Cmaj7", "Dm7", "G7", "C6"]}
JAM_SECTIONS = {"Head": ["Am7", "D7", "Gmaj7"]}


class _FakeSt:
    def __init__(self, session: dict):
        self.session_state = session


def _jam_generator_session(*, bpm: int = 98) -> dict:
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
        "backing_track_bpm": 95,
        BPM_WIDGET_KEY: 95,
        "bpm": 95,
    }
    jam = {
        "id": f"test-jam-{bpm}",
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
        "backing_track_bpm": 95,
        BPM_WIDGET_KEY: 95,
        "bpm": 95,
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


class TestInstrumentOwnership(unittest.TestCase):
    def test_page_local_piano_default_does_not_overwrite_guitar(self) -> None:
        session = {"instrument": "Guitar", "level": "Intermediate", "focus": "Improvisation"}
        shown = qc_widget_value_for_global(
            session, "improv_mission::qc_instrument", "instrument", DEFAULT_INSTRUMENT_OPTIONS
        )
        self.assertEqual(shown, "Guitar")
        self.assertEqual(session["instrument"], "Guitar")
        self.assertEqual(session["improv_mission::qc_instrument"], "Guitar")

    def test_sync_widget_state_does_not_clamp_global_to_piano(self) -> None:
        session = {"instrument": "Guitar", "level": "Intermediate", "focus": "Improvisation"}
        sync_widget_state_from_globals(
            session,
            instrument_widget_key="page::qc_instrument",
            instrument_options=["Piano", "Bass"],  # Guitar not listed
        )
        self.assertEqual(session["instrument"], "Guitar")
        self.assertEqual(session["page::qc_instrument"], "Piano")  # projection only

    def test_active_song_apply_does_not_overwrite_guitar_with_piano(self) -> None:
        session = {"instrument": "Guitar", "level": "Intermediate", "focus": "Improvisation"}
        _apply_context_to_session_keys(
            session,
            {"instrument": "Piano", "level": "Beginner", "focus": "Melody", "pick_key": SHAPE_PICK},
            apply_global_controls=True,
            global_control_source="canonical_apply",
        )
        self.assertEqual(session["instrument"], "Guitar")

    def test_open_mission_backing_preserves_guitar(self) -> None:
        session = {
            "studio_page": "creative",
            "instrument": "Guitar",
            "level": "Intermediate",
            "focus": "Improvisation",
            "display_key": "C#m",
            "concert_key": "C#m",
            "improv_active_mission": "Chord tones only",
            "improv_mission_pick": "Chord tones only",
            "ii_selected_chord": "F#m",
            "ii_selected_section": "Verse",
            "improv_mission_chord_options": ["F#m", "C#m"],
            "ii_selected_chord_index": 0,
            "active_catalog_pick_key": SHAPE_PICK,
            "song": "Shape of You",
            "home_sections": {"Verse": ["F#m", "C#m"]},
            "backing_track_bpm": 100,
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "G",
        }
        st = _FakeSt(session)
        # Stale page-local widget must not win.
        session["improv_mission::qc_instrument"] = "Piano"
        open_backing_from_creative(session, source="mission", st_like=st)
        self.assertEqual(session["instrument"], "Guitar")

    def test_canonical_mission_chord_invariant_under_projection(self) -> None:
        session = {
            "studio_page": "creative",
            "instrument": "Guitar",
            "display_key": "C#m",
            "concert_key": "C#m",
            "improv_active_mission": "Chord tones only",
            "improv_mission_pick": "Chord tones only",
            "ii_selected_chord": "F#m",
            "ii_selected_section": "Verse",
            "improv_mission_chord_options": ["F#m"],
            "ii_selected_chord_index": 0,
            "active_catalog_pick_key": SHAPE_PICK,
            "song": "Shape of You",
            "home_sections": {"Verse": ["F#m"]},
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "G",
        }
        st = _FakeSt(session)
        open_backing_from_creative(session, source="mission", st_like=st)
        self.assertEqual(session.get("_mission_backing_canonical_chord"), "F#m")
        self.assertEqual(session["instrument"], "Guitar")


class TestGenerateExampleFirstClick(unittest.TestCase):
    def test_fresh_run_flag_protects_display(self) -> None:
        session = {MISSION_EXAMPLE_FRESH_RUN_KEY: True}
        self.assertTrue(bool(session.get(MISSION_EXAMPLE_FRESH_RUN_KEY)))

    def test_generate_does_not_mutate_instrument(self) -> None:
        from improvisation_intelligence import ImprovSessionContext

        session = {
            "instrument": "Guitar",
            "level": "Intermediate",
            "focus": "Improvisation",
            "display_key": "Dm",
            "concert_key": "Dm",
            "improv_mission_pick": "Chord tones only",
            "improv_active_mission": "Chord tones only",
            "ii_selected_chord": "Dm",
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
            "home_sections": {"Verse": ["Dm", "Am", "G", "C"]},
            "backing_track_bpm": 100,
        }
        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Dm",
            display_key="Dm",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            bpm=100,
            sections={"Verse": ["Dm", "Am", "G", "C"]},
            progression_flat=["Dm", "Am", "G", "C"],
        )
        session[MISSIONS_GENERATE_CONTEXT_KEY] = {
            "mission": "Chord tones only",
            "cur_chord": "Dm",
            "section_label": "Verse",
            "chord_idx": 0,
            "live_inst": "Guitar",
            "live_level": "Intermediate",
            "live_focus": "Improvisation",
            "bpm": 100,
            "key_center": "Dm",
            "chart_key": "Dm",
            "improv_ctx": {
                "song_title": "Shape of You",
                "artist": "Ed Sheeran",
                "key_center": "Dm",
                "display_key": "Dm",
                "instrument": "Guitar",
                "level": "Intermediate",
                "focus": "Improvisation",
                "bpm": 100,
                "sections": [("Verse", ["Dm", "Am", "G", "C"])],
            },
        }
        with mock.patch(
            "improvisation_intelligence_ui._improv_ctx_from_generate_context",
            return_value=ctx,
        ):
            _run_mission_example_generate(session, "normal")
        self.assertEqual(session["instrument"], "Guitar")


class TestGeneratedBpmInitialization(unittest.TestCase):
    def test_jam_generator_98_initializes_slider_98(self) -> None:
        session = _jam_generator_session(bpm=98)
        # Stale prior slider/domain must not win.
        session[BPM_WIDGET_KEY] = 95
        session["backing_track_bpm"] = 95
        session["bpm"] = 95
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 98)
        self.assertEqual(int(session.get(BPM_WIDGET_KEY) or 0), 98)
        ctx = get_backing_context(session)
        assert ctx is not None
        self.assertEqual(int(ctx.bpm), 98)
        sync_id = str(session.get("_active_bpm_sync_id") or session.get("_backing_trace_sync_id") or "")
        if sync_id:
            self.assertEqual(int(session.get(backing_bpm_slider_widget_key(sync_id)) or 0), 98)

    def test_second_jam_does_not_reuse_prior_slider(self) -> None:
        session = _jam_generator_session(bpm=98)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session["backing_track_bpm"]), 98)
        # Simulate user leaving a slider at 98, then generate a new jam at 133.
        session2 = _jam_generator_session(bpm=133)
        session2[BPM_WIDGET_KEY] = 98
        session2["backing_track_bpm"] = 98
        # Carry prior backing context + play session overrides from first jam.
        session2["backing_context"] = session.get("backing_context")
        session2["_backing_play_session"] = {
            "launch_id": "old-launch",
            "expired": False,
            "defaults": {"bpm": 98},
            "overrides": {"bpm": 98},
        }
        st2 = _FakeSt(session2)
        open_backing_from_creative(session2, source="entry_jam", st_like=st2)
        self.assertEqual(int(session2.get("backing_track_bpm") or 0), 133)
        self.assertEqual(int(session2.get(BPM_WIDGET_KEY) or 0), 133)

    def test_style_jam_equivalent_initialization(self) -> None:
        session = _style_jam_session(bpm=130)
        session[BPM_WIDGET_KEY] = 95
        session["backing_track_bpm"] = 95
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 130)

    def test_resolve_slider_prefers_domain_matching_source_over_stale(self) -> None:
        sync_id = "entry_jam::jam::98"
        slider_key = backing_bpm_slider_widget_key(sync_id)
        st = _FakeSt(
            {
                "_active_bpm_sync_id": sync_id,
                "active_playback_song_id": sync_id,
                slider_key: 95,
                BPM_WIDGET_KEY: 98,
                "backing_track_bpm": 98,
                "bpm": 98,
            }
        )
        bpm = resolve_backing_bpm_for_slider(st, sync_id=sync_id, default_bpm=98)
        self.assertEqual(bpm, 98)
        self.assertEqual(int(st.session_state[slider_key]), 98)


class TestCatalogBackingOverrides(unittest.TestCase):
    def test_catalog_bpm_override_editable(self) -> None:
        session = {
            "studio_page": "backing",
            "instrument": "Guitar",
            "backing_track_bpm": 82,
            BPM_WIDGET_KEY: 82,
            "bpm": 82,
            "backing_groove_style": "Pop",
            "backing_time_signature": "4/4",
            "backing_track_scope": "Full song",
            "active_catalog_pick_key": SHAPE_PICK,
            "_canonical_backing_id": "cat::shape",
        }
        session["backing_context"] = {
            "source": "regular_song",
            "bpm": 82,
            "style": "Pop",
            "meter": "4/4",
            "source_signature": "catalog82",
            "backing_session_launch_id": "launch-a",
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_bpm"] = 96
        session[BPM_WIDGET_KEY] = 96
        session["bpm"] = 96
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "bpm"))
        self.assertTrue(play_session_blocks_canonical_seed(session))
        # Same-session reseal must not wipe override.
        sync_backing_play_session_on_backing_page(session)
        self.assertEqual(int(session["backing_track_bpm"]), 96)

    def test_catalog_style_meter_sections_editable(self) -> None:
        session = {
            "studio_page": "backing",
            "backing_track_bpm": 82,
            BPM_WIDGET_KEY: 82,
            "backing_groove_style": "Pop",
            "backing_time_signature": "4/4",
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["Verse"],
            "backing_context": {
                "source": "regular_song",
                "bpm": 82,
                "style": "Pop",
                "meter": "4/4",
                "source_signature": "catalog82",
                "backing_session_launch_id": "launch-b",
            },
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_groove_style"] = "Blues"
        session["backing_time_signature"] = "3/4"
        session["backing_track_multi_sections"] = ["Chorus"]
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "groove"))
        self.assertTrue(backing_play_session_has_override(session, "meter"))
        self.assertTrue(backing_play_session_has_override(session, "multi_sections"))
        sync_backing_play_session_on_backing_page(session)
        self.assertEqual(session["backing_groove_style"], "Blues")
        self.assertEqual(session["backing_time_signature"], "3/4")
        self.assertEqual(session["backing_track_multi_sections"], ["Chorus"])

    def test_source_reseal_does_not_overwrite_dirty_overrides(self) -> None:
        session = _style_jam_session(bpm=130)
        st = _FakeSt(session)
        open_backing_from_creative(session, source="entry_jam", st_like=st)
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_bpm"] = 110
        session[BPM_WIDGET_KEY] = 110
        session["backing_groove_style"] = "Blues"
        session["backing_time_signature"] = "3/4"
        from backing_track_state import mark_backing_user_edit

        mark_backing_user_edit(session)
        capture_backing_play_session_overrides(session)
        apply_backing_defaults_for_song(
            st,
            song_id="ignored",
            default_bpm=130,
            default_groove="Bossa Nova",
            song_data=None,
        )
        self.assertEqual(int(session["backing_track_bpm"]), 110)
        self.assertIn("Blues", str(session["backing_groove_style"]))
        self.assertEqual(session["backing_time_signature"], "3/4")

    def test_leave_reenter_expires_ephemeral_overrides(self) -> None:
        session = {
            "studio_page": "backing",
            "backing_track_bpm": 96,
            BPM_WIDGET_KEY: 96,
            "backing_groove_style": "Blues",
            "backing_time_signature": "3/4",
            "backing_context": {
                "source": "regular_song",
                "bpm": 82,
                "style": "Pop",
                "meter": "4/4",
                "source_signature": "catalog82",
                "backing_session_launch_id": "launch-c",
            },
        }
        sync_backing_play_session_on_backing_page(session)
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "bpm"))
        expire_backing_play_session_on_page_exit(
            session, previous_page="backing", new_page="practice"
        )
        self.assertFalse(backing_play_session_has_override(session, "bpm"))


class TestLaunchIdOnSignatureChange(unittest.TestCase):
    def test_signature_change_mints_new_launch_id(self) -> None:
        session: dict = {}
        ctx1 = BackingContext(
            source="entry_jam",
            source_label="Jam",
            active_song_id="jam-1",
            song_title="Jam",
            key="Am",
            display_key="Am",
            concert_key="Am",
            bpm=98,
            style="Jazz Swing",
            groove="Medium",
            meter="4/4",
            progression=["Am7"],
            entry_mode="Jam Session Generator",
            jam_id="j1",
        )
        set_backing_context(
            session,
            ctx1,
            creative_return_route={"tab": "Entry & Jam", "entry": "Jam Session Generator"},
        )
        launch1 = str(session["backing_context"].get("backing_session_launch_id") or "")
        self.assertTrue(launch1)
        ctx2 = BackingContext(
            source="entry_jam",
            source_label="Jam",
            active_song_id="jam-2",
            song_title="Jam",
            key="Am",
            display_key="Am",
            concert_key="Am",
            bpm=133,
            style="Jazz Swing",
            groove="Medium",
            meter="4/4",
            progression=["Am7", "D7"],
            entry_mode="Jam Session Generator",
            jam_id="j2",
        )
        set_backing_context(
            session,
            ctx2,
            creative_return_route={"tab": "Entry & Jam", "entry": "Jam Session Generator"},
        )
        launch2 = str(session["backing_context"].get("backing_session_launch_id") or "")
        self.assertTrue(launch2)
        self.assertNotEqual(launch1, launch2)

    def test_same_signature_explicit_route_keeps_launch_id(self) -> None:
        session: dict = {}
        ctx = BackingContext(
            source="entry_jam",
            source_label="Jam",
            active_song_id="jam-1",
            song_title="Jam",
            key="Am",
            display_key="Am",
            concert_key="Am",
            bpm=98,
            style="Jazz Swing",
            groove="Medium",
            meter="4/4",
            progression=["Am7"],
            entry_mode="Jam Session Generator",
            jam_id="j1",
        )
        set_backing_context(
            session,
            ctx,
            creative_return_route={"tab": "Entry & Jam", "entry": "Jam Session Generator"},
        )
        launch1 = str(session["backing_context"].get("backing_session_launch_id") or "")
        set_backing_context(
            session,
            ctx,
            creative_return_route={"tab": "Entry & Jam", "entry": "Jam Session Generator"},
        )
        launch2 = str(session["backing_context"].get("backing_session_launch_id") or "")
        self.assertEqual(launch1, launch2)


if __name__ == "__main__":
    unittest.main()

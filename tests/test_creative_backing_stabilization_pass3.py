"""Pass 3: live generated-source controls, ephemeral Backing play session, Mission projection."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY
from backing_play_session import (
    backing_play_session_has_override,
    capture_backing_play_session_overrides,
    effective_backing_play_overrides,
    expire_backing_play_session_on_page_exit,
    sync_backing_play_session_on_backing_page,
)
from effective_practice_context import musician_facing_chart_key, musician_facing_chord
from guitar_capo import shape_chart_key_for_concert
from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import generate_mission_example, refresh_mission_example
from music_workflow_generated_session import commit_jam_session_generation, commit_style_jam_control_settings, commit_style_jam_generation
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_active_workflow_pointer,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from songs.playback_defaults import sync_backing_bpm_from_slider
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
STYLE_SECTIONS = {"A (Bossa Nova)": ["Cmaj7", "Dm7", "G7", "C6"]}


def _style_jam_session(*, jam_key: str = "C", bpm: int = 96) -> dict:
    session = {
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Bossa Nova",
        "improv_mood": "Mellow",
        "improv_groove": "Medium",
        "improv_style_bpm": bpm,
        "improv_difficulty": "Intermediate",
        "improv_style_key": jam_key,
        "improv_generated_sections": copy.deepcopy(STYLE_SECTIONS),
        "active_catalog_pick_key": SHAPE_PICK,
        "song": "Shape of You",
        "display_key": "Dm",
        "concert_key": "Dm",
        "instrument": "Guitar",
    }
    commit_style_jam_generation(
        session,
        key_center=jam_key,
        style="Bossa Nova",
        section_map=copy.deepcopy(STYLE_SECTIONS),
        mood="Mellow",
        groove="Medium",
        tempo_bpm=bpm,
        new_session=True,
    )
    return session


class TestStyleJamLiveControlCommit(unittest.TestCase):
    def test_style_mood_groove_bpm_commit_while_widgets_locked(self) -> None:
        session = _style_jam_session()
        session["_streamlit_widgets_locked_this_run"] = True
        session["improv_style"] = "Jazz Swing"
        session["improv_mood"] = "Dark"
        session["improv_groove"] = "Heavy"
        session["improv_style_bpm"] = 128
        self.assertTrue(commit_style_jam_control_settings(session))
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(str(blob.style), "Jazz Swing")
        self.assertEqual(str(blob.mood), "Dark")
        self.assertEqual(str(blob.groove), "Heavy")
        self.assertEqual(int(blob.tempo_bpm), 128)
        self.assertEqual(session.get("improv_style"), "Jazz Swing")
        self.assertEqual(int(session.get("improv_style_bpm") or 0), 128)

    def test_style_change_does_not_retarget_session_id(self) -> None:
        session = _style_jam_session()
        ptr_before = get_active_workflow_pointer(session)
        assert ptr_before is not None
        sid_before = str(ptr_before.workflow_session_id)
        session["_streamlit_widgets_locked_this_run"] = True
        session["improv_style"] = "Jazz Swing"
        self.assertTrue(commit_style_jam_control_settings(session))
        ptr_after = get_active_workflow_pointer(session)
        assert ptr_after is not None
        self.assertEqual(str(ptr_after.workflow_session_id), sid_before)
        blob = get_workflow_blob(session, "style_jam", sid_before)
        assert blob is not None
        self.assertEqual(str(blob.style), "Jazz Swing")


class TestJamGeneratorLiveControls(unittest.TestCase):
    def test_atmosphere_and_exact_bpm_commit_while_locked(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Jazz Swing",
            "improv_jam_mood": "Mellow",
            "improv_jam_bpm": 110,
            "improv_jam_key": "C",
            "improv_groove": "Medium",
        }
        commit_jam_session_generation(
            session,
            {
                "id": "jam-test-1",
                "style": "Jazz Swing",
                "bpm": 110,
                "mood": "Mellow",
                "atmosphere": "Mellow",
                "key": "C",
                "sections": {"Head": ["Cmaj7", "Am7", "Dm7", "G7"]},
            },
            key_center="C",
            style="Jazz Swing",
        )
        session["_streamlit_widgets_locked_this_run"] = True
        session["improv_jam_mood"] = "Bright"
        session["improv_jam_bpm"] = 90
        self.assertTrue(commit_style_jam_control_settings(session))
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(str(blob.mood), "Bright")
        self.assertEqual(int(blob.tempo_bpm), 90)
        self.assertEqual(int(session.get("improv_jam_bpm") or 0), 90)

    def test_generate_uses_widget_bpm_not_stale_jam_payload(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Jazz Swing",
            "improv_jam_mood": "Bright",
            "improv_jam_bpm": 90,
            "improv_jam_key": "C",
        }
        self.assertTrue(
            commit_jam_session_generation(
                session,
                {
                    "id": "jam-test-90",
                    "style": "Jazz Swing",
                    "bpm": 110,
                    "mood": "Mellow",
                    "atmosphere": "Mellow",
                    "key": "C",
                    "sections": {"Head": ["Cmaj7", "Am7", "Dm7", "G7"]},
                },
                key_center="C",
                style="Jazz Swing",
            )
        )
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(int(blob.tempo_bpm), 90)


class TestBackingPlaySessionLifecycle(unittest.TestCase):
    def test_bpm_override_survives_same_session_and_resets_after_exit(self) -> None:
        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "bpm": 100,
                "style": "Pop groove",
                "meter": "4/4",
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "launch-1",
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Pop groove",
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_bpm"] = 84
        session["backing_groove_style"] = "Disco"
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "bpm"))
        self.assertEqual(int(effective_backing_play_overrides(session)["bpm"]), 84)
        self.assertEqual(str(effective_backing_play_overrides(session)["groove"]), "Disco")

        sync_backing_play_session_on_backing_page(session)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 84)
        self.assertEqual(session.get("backing_groove_style"), "Disco")

        expire_backing_play_session_on_page_exit(
            session, previous_page="backing", new_page="upload"
        )
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 100)
        self.assertNotEqual(str(session.get("backing_groove_style") or "").lower(), "disco")

        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        self.assertFalse(backing_play_session_has_override(session, "bpm"))
        self.assertEqual(int(effective_backing_play_overrides(session)["bpm"]), 100)

    def test_play_session_override_blocks_canonical_seed_on_refresh(self) -> None:
        from backing_track_state import BACKING_RESTORED_KEY, prepare_backing_bpm_for_widget, write_canonical_backing_state

        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "bpm": 100,
                "style": "Pop groove",
                "meter": "4/4",
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "launch-refresh",
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Pop groove",
            BACKING_RESTORED_KEY: True,
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_bpm"] = 84
        capture_backing_play_session_overrides(session)
        write_canonical_backing_state(
            session,
            {"backing_track_bpm": 100, "backing_groove_style": "Pop groove"},
            reason="stale_canonical",
        )
        session[BACKING_RESTORED_KEY] = True
        sync_backing_play_session_on_backing_page(session)
        bpm = prepare_backing_bpm_for_widget(session, default_bpm=100)
        self.assertEqual(int(bpm), 84)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 84)

    def test_slider_does_not_rewrite_backing_context_source_bpm(self) -> None:
        session = _style_jam_session(bpm=90)
        session["studio_page"] = "backing"
        session["improv_style_bpm"] = 90
        st = SimpleNamespace(session_state=session)
        sync_backing_bpm_from_slider(st, slider_bpm=118)
        self.assertEqual(int(session.get("improv_style_bpm") or 0), 90)
        self.assertEqual(int(session.get("backing_track_bpm") or 0), 118)
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(int(blob.tempo_bpm), 90)

    def test_regular_song_live_bpm_is_not_forced_back_to_ctx(self) -> None:
        from songs.bpm_state import sync_backing_bpm_before_widget
        from backing_track_state import mark_backing_user_edit

        session = {
            "song": "Perfect",
            "backing_track_bpm": 84,
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "bpm": 100,
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "launch-reg",
            },
        }
        mark_backing_user_edit(session)
        capture_backing_play_session_overrides(session)
        st = SimpleNamespace(session_state=session)
        bpm = sync_backing_bpm_before_widget(st, "Perfect", 100)
        self.assertEqual(int(bpm), 84)


class TestBackingScopeLiveMutation(unittest.TestCase):
    def test_selected_scope_survives_same_play_session(self) -> None:
        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "song_improv",
                "bpm": 96,
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "launch-sbi",
            },
            "backing_track_scope": "Full song",
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_scope"] = "Selected sections"
        session["backing_track_multi_sections"] = ["Chorus"]
        capture_backing_play_session_overrides(session)
        sync_backing_play_session_on_backing_page(session)
        self.assertEqual(session.get("backing_track_scope"), "Selected sections")
        self.assertEqual(session.get("backing_track_multi_sections"), ["Chorus"])
        expire_backing_play_session_on_page_exit(
            session, previous_page="backing", new_page="practice"
        )
        self.assertEqual(session.get("backing_track_scope"), "Full song")


class TestMissionCanonicalThenProject(unittest.TestCase):
    def test_shape_cm_selected_ab_example_stays_ab_after_refresh(self) -> None:
        concert = "F#m"
        shape = "C"
        chart = shape_chart_key_for_concert(concert, shape)
        self.assertEqual(chart, "Cm")
        concert_chord = "D"
        shown = musician_facing_chord(concert_chord, concert_key=concert, chart_key=chart)
        self.assertEqual(shown, "Ab")
        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center=concert,
            display_key=chart,
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": [concert_chord, "F#m", "C#m"]},
            bpm=96,
            style_label="Pop",
        )
        example = generate_mission_example(
            "Chord tones only",
            improv_ctx=ctx,
            chord=concert_chord,
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            variant="normal",
            bpm=96,
        )
        self.assertEqual(example.chord, concert_chord)
        tones = " ".join(example.insight.chord_tones or [])
        self.assertIn("Ab", tones)
        self.assertNotIn("D ", tones + " ")
        display = str((example.motif or {}).get("display") or "")
        self.assertTrue(display)
        again = refresh_mission_example(
            example,
            instrument="Guitar",
            bpm=96,
            song_concert_key=concert,
        )
        again = refresh_mission_example(
            again,
            instrument="Guitar",
            bpm=96,
            song_concert_key=concert,
        )
        tones2 = " ".join(again.insight.chord_tones or [])
        display2 = str((again.motif or {}).get("display") or "")
        self.assertIn("Ab", tones2)
        self.assertEqual(display, display2)

    def test_load_mission_example_insight_uses_displayed_chord(self) -> None:
        from improvisation_missions import store_mission_example, load_mission_example

        concert = "F#m"
        chart = "Cm"
        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center=concert,
            display_key=chart,
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["D", "F#m", "C#m"]},
            bpm=96,
            style_label="Pop",
        )
        example = generate_mission_example(
            "Chord tones only",
            improv_ctx=ctx,
            chord="D",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            variant="normal",
            bpm=96,
        )
        session: dict = {}
        store_mission_example(session, example)
        loaded = load_mission_example(session, ctx)
        assert loaded is not None
        tones = " ".join(loaded.insight.chord_tones or [])
        self.assertIn("Ab", tones)
        self.assertEqual(loaded.chord, "D")

    def test_perfect_g_to_a_alto_written_f_sharp(self) -> None:
        session = {
            "instrument": "Saxophone",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True,
            "display_key": "A",
            "concert_key": "A",
        }
        self.assertEqual(musician_facing_chart_key(session, "G"), "E")
        self.assertEqual(musician_facing_chart_key(session, "A"), "F#")
        chord_g = musician_facing_chord("C", concert_key="G", chart_key="E")
        chord_a = musician_facing_chord("D", concert_key="A", chart_key="F#")
        self.assertEqual(chord_g, "A")
        self.assertEqual(chord_a, "B")


class TestMissionPracticeKeyImmediateProjection(unittest.TestCase):
    def test_authoritative_practice_key_overlays_pending_a(self) -> None:
        from improvisation_intelligence_ui import _authoritative_practice_chart_key, _coherent_improv_key_pair
        from music_workflow_pending_song_practice_key_edit import queue_pending_song_practice_key_edit
        from music_workflow_song_practice import ensure_song_practice_blob_for_active_song
        from songs.practice_key_state import set_practice_concert_key

        session = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "active_catalog_pick_key": SHAPE_PICK,
            "song": "Perfect",
            "display_key": "A",
            "concert_key": "G",
            "instrument": "Saxophone",
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "show_chart_in_instrument_key": True,
        }
        set_practice_concert_key(session, "G", pick_key=SHAPE_PICK)
        ensure_song_practice_blob_for_active_song(session, practice_key="G", original_key="G")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id=SHAPE_PICK),
            source="test",
        )
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id=SHAPE_PICK,
            keys=KeyAuthority(
                original_tonic="G",
                original_mode="major",
                practice_tonic="G",
                practice_mode="major",
            ),
            section_map={"Verse": ["G", "Em", "C", "D"]},
        )
        save_workflow_blob(session, blob, source="test")
        pending = queue_pending_song_practice_key_edit(
            session,
            selected_key_token="A",
            workflow_owner="mission_jam",
            workflow_session_id=SHAPE_PICK,
        )
        self.assertIsNotNone(pending)
        token = _authoritative_practice_chart_key(session, "G")
        self.assertEqual(token, "A")
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="",
            key_center="G",
            display_key="E",
            instrument="Saxophone",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["G", "Em", "C", "D"]},
            bpm=90,
            style_label="Pop",
        )
        concert, chart = _coherent_improv_key_pair(session, ctx)
        self.assertEqual(concert, "A")
        self.assertEqual(chart, "F#")


if __name__ == "__main__":
    unittest.main()

"""Pass 4: same-rerun key/sections, ephemeral Advanced Settings, Regular restore, Mission labels."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    BACKING_SESSION_LAUNCH_ID_BLOB_KEY,
    BackingContext,
    apply_backing_context_to_session,
    format_backing_context_banner,
    restore_regular_song_backing,
)
from backing_play_session import (
    backing_play_session_has_override,
    capture_backing_play_session_overrides,
    effective_backing_play_overrides,
    expire_backing_play_session_on_page_exit,
    sync_backing_play_session_on_backing_page,
)
from backing_musical_state import resolve_current_backing_musical_state
from effective_practice_context import musician_facing_chord
from improvisation_intelligence import ImprovSessionContext
from improvisation_missions import MISSION_EXAMPLE_KEY, generate_mission_example, load_mission_example
from music_theory import transpose_sections_dict
from music_workflow_generated_session import commit_jam_session_generation
from music_workflow_pending_song_practice_key_edit import (
    overlay_destination_practice_key,
    overlay_sections_with_pending_practice_key,
)
from music_workflow_song_practice import ensure_song_practice_blob_for_active_song
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from song_catalog.catalog import format_pick_key
from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key
from source_session_state import resolve_sbi_preview


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
PERFECT_G = {
    "Verse": ["G", "D/F#", "Em7", "D", "Cadd9", "D", "G"],
}


def _perfect_session(*, practice: str = "G") -> dict:
    session = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "active_catalog_pick_key": PERFECT_PICK,
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "display_key": practice,
        "concert_key": practice,
        "instrument": "Alto Saxophone",
        "improv_song_concert_sections": copy.deepcopy(PERFECT_G)
        if practice == "G"
        else transpose_sections_dict(copy.deepcopy(PERFECT_G), "G", practice),
        "home_sections": copy.deepcopy(PERFECT_G),
        "catalog_session": {
            "pick_key": PERFECT_PICK,
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
            "original_key": "G",
            "display_key": practice,
            "sections": copy.deepcopy(PERFECT_G)
            if practice == "G"
            else transpose_sections_dict(copy.deepcopy(PERFECT_G), "G", practice),
        },
    }
    set_practice_concert_key(session, practice, pick_key=PERFECT_PICK)
    set_active_workflow_pointer(
        session,
        ActiveWorkflowPointer(workflow_owner="song_based_improvisation", workflow_session_id=PERFECT_PICK),
        source="test",
    )
    ensure_song_practice_blob_for_active_song(session, practice_key=practice, original_key="G")
    blob = WorkflowStateBlob(
        workflow_owner="song_based_improvisation",
        workflow_session_id=PERFECT_PICK,
        keys=KeyAuthority(
            original_tonic="G",
            original_mode="major",
            practice_tonic="A" if practice == "A" else "G",
            practice_mode="major",
        ),
        section_map=copy.deepcopy(session["improv_song_concert_sections"]),
    )
    save_workflow_blob(session, blob, source="test")
    return session


def _jam_session(*, jam_key: str = "D#", bpm: int = 96) -> dict:
    session = {
        "studio_page": "backing",
        "improv_entry_mode": "Jam Session Generator",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_jam_key": jam_key,
        "improv_jam_bpm": bpm,
        "improv_generated_sections": {"A": ["D#", "A#", "Cm", "G#"]},
        "active_catalog_pick_key": PERFECT_PICK,
        "song": "Perfect",
        "selected_song": {"title": "Perfect", "artist": "Ed Sheeran", "key": "G", "pick_key": PERFECT_PICK},
        "display_key": "A",
        "concert_key": jam_key,
        "instrument": "Alto Saxophone",
    }
    set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
    commit_jam_session_generation(
        session,
        {
            "id": "jam-dsharp-test",
            "style": "Pop groove",
            "bpm": bpm,
            "mood": "Mellow",
            "key": jam_key,
            "sections": {"A": ["D#", "A#", "Cm", "G#"]},
        },
        key_center=jam_key,
        style="Pop groove",
        new_session=True,
    )
    session["studio_page"] = "backing"
    session[BACKING_CONTEXT_KEY] = {
        "source": "entry_jam",
        "entry_mode": "Jam Session Generator",
        "key": jam_key,
        "concert_key": jam_key,
        "display_key": jam_key,
        "bpm": bpm,
        "style": "Pop groove",
        "meter": "4/4",
        BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "jam-launch-1",
    }
    return session


class TestSbiSameRerunPracticeKeyTranspose(unittest.TestCase):
    def test_perfect_g_to_a_transposes_sbi_sections_same_call(self) -> None:
        session = _perfect_session(practice="G")
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
        session["display_key"] = "A"
        session["concert_key"] = "A"
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["display_key"], "A")
        verse = [str(c) for c in (preview.get("sections") or {}).get("Verse") or []]
        self.assertTrue(verse, "SBI preview must have transposed sections")
        self.assertTrue(verse[0].startswith("A"), verse)
        self.assertFalse(verse[0].startswith("G"), verse)
        expected = transpose_sections_dict(PERFECT_G, "G", "A")["Verse"]
        self.assertEqual(verse[0], expected[0])

    def test_alto_projects_from_transposed_a_progression(self) -> None:
        session = _perfect_session(practice="G")
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
        session["display_key"] = "A"
        preview = resolve_sbi_preview(session)
        verse = list((preview.get("sections") or {}).get("Verse") or [""])
        concert_first = str(verse[0])
        shown = musician_facing_chord(concert_first, concert_key="A", chart_key="F#")
        self.assertTrue(shown.startswith("F#") or shown.startswith("Gb"), shown)

    def test_saved_practice_key_invalidates_stale_blob_sections(self) -> None:
        session = _perfect_session(practice="G")
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
        session["display_key"] = "A"
        dest = overlay_destination_practice_key(session)
        self.assertEqual(dest, "A")
        overlaid = overlay_sections_with_pending_practice_key(
            session, copy.deepcopy(PERFECT_G), spelled_in_key="G"
        )
        self.assertTrue(str(overlaid["Verse"][0]).startswith("A"))

    def test_blob_already_dest_still_transposes_original_pitch_map(self) -> None:
        """Identity can already be A while the section map is still Perfect in G."""
        session = _perfect_session(practice="G")
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
        session["display_key"] = "A"
        session["concert_key"] = "A"
        ensure_song_practice_blob_for_active_song(session, practice_key="A", original_key="G")
        overlaid = overlay_sections_with_pending_practice_key(
            session, copy.deepcopy(PERFECT_G), spelled_in_key="A"
        )
        self.assertTrue(str(overlaid["Verse"][0]).startswith("A"), overlaid)
        self.assertFalse(str(overlaid["Verse"][0]).startswith("G"), overlaid)

    def test_expanded_original_pitch_map_still_transposes(self) -> None:
        session = _perfect_session(practice="G")
        set_practice_concert_key(session, "A", pick_key=PERFECT_PICK)
        session["display_key"] = "A"
        ensure_song_practice_blob_for_active_song(session, practice_key="A", original_key="G")
        expanded = {
            "Verse": list(PERFECT_G["Verse"]) + list(PERFECT_G["Verse"]),
        }
        overlaid = overlay_sections_with_pending_practice_key(
            session, expanded, spelled_in_key="A"
        )
        self.assertTrue(str(overlaid["Verse"][0]).startswith("A"), overlaid)
        self.assertFalse(str(overlaid["Verse"][0]).startswith("G"), overlaid)

    def test_sbi_discards_jam_generator_sections(self) -> None:
        session = _perfect_session(practice="A")
        session["improv_song_concert_sections"] = {"A": ["D#", "A#", "Cm", "G#"]}
        preview = resolve_sbi_preview(session)
        sections = preview.get("sections") or {}
        first = ""
        for chs in sections.values():
            if chs:
                first = str(chs[0] or "").strip()
                if first:
                    break
        self.assertFalse(first.startswith("D#"), sections)
        self.assertTrue(first.startswith("A") or first.startswith("G"), sections)

    def test_prior_practice_key_map_transposes_when_blob_already_dest(self) -> None:
        """A-major Perfect map must move to E even if identity/fallback is already E."""
        session = _perfect_session(practice="A")
        set_practice_concert_key(session, "E", pick_key=PERFECT_PICK)
        session["display_key"] = "E"
        session["concert_key"] = "E"
        ensure_song_practice_blob_for_active_song(session, practice_key="E", original_key="G")
        a_map = transpose_sections_dict(copy.deepcopy(PERFECT_G), "G", "A")
        overlaid = overlay_sections_with_pending_practice_key(
            session, a_map, spelled_in_key="E"
        )
        self.assertTrue(str(overlaid["Verse"][0]).startswith("E"), overlaid)
        self.assertFalse(str(overlaid["Verse"][0]).startswith("A"), overlaid)
        self.assertFalse(str(overlaid["Verse"][0]).startswith("F#"), overlaid)


class TestBackingBannerEffectiveBpm(unittest.TestCase):
    def test_banner_uses_ephemeral_bpm_not_source(self) -> None:
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="jam-1",
            song_title="Gritty Bossa Nova",
            key="Eb",
            display_key="Eb",
            concert_key="Eb",
            bpm=96,
            style="Bossa nova",
            groove="Medium",
            mood="Gritty",
            meter="4/4",
        )
        banner = format_backing_context_banner(ctx, practice_concert_key="Eb", applied_bpm=129)
        self.assertIn("129 BPM", banner)
        self.assertNotIn("96 BPM", banner)

    def test_local_bpm_does_not_rewrite_generated_source(self) -> None:
        session = _jam_session(jam_key="D#", bpm=96)
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        before = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert before is not None
        self.assertEqual(int(before.tempo_bpm), 96)
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        session["backing_track_bpm"] = 129
        capture_backing_play_session_overrides(session)
        after = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert after is not None
        self.assertEqual(int(after.tempo_bpm), 96)
        self.assertEqual(int(effective_backing_play_overrides(session)["bpm"]), 129)


class TestAdvancedSettingsLiveMutation(unittest.TestCase):
    def test_groove_meter_scope_commit_and_survive_refresh(self) -> None:
        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "entry_mode": "Style Jam Mode",
                "bpm": 96,
                "style": "Bossa nova",
                "meter": "4/4",
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "adv-1",
            },
            "backing_track_bpm": 96,
            "backing_groove_style": "Bossa nova",
            "backing_time_signature": "4/4",
            "backing_track_scope": "Full song",
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_groove_style"] = "Disco"
        session["backing_time_signature"] = "3/4"
        session["backing_track_scope"] = "Selected sections"
        session["backing_track_multi_sections"] = ["Verse"]
        capture_backing_play_session_overrides(session)
        ov = effective_backing_play_overrides(session)
        self.assertEqual(ov["groove"], "Disco")
        self.assertEqual(ov["meter"], "3/4")
        self.assertEqual(ov["scope"], "Selected sections")

        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="jam-adv",
            song_title="Jam",
            key="Eb",
            display_key="Eb",
            concert_key="Eb",
            bpm=96,
            style="Bossa nova",
            groove="Medium",
            meter="4/4",
            scope="Full song",
            loops=2,
            entry_mode="Style Jam Mode",
            source_signature="sig-adv",
        )
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
        self.assertEqual(session.get("backing_groove_style"), "Disco")
        self.assertEqual(session.get("backing_time_signature"), "3/4")

        sync_backing_play_session_on_backing_page(session)
        self.assertEqual(session.get("backing_groove_style"), "Disco")
        self.assertEqual(int(effective_backing_play_overrides(session)["bpm"] or 96), 96)

    def test_ephemeral_override_resets_after_page_exit(self) -> None:
        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "regular_song",
                "bpm": 100,
                "style": "Pop groove",
                "meter": "4/4",
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "reg-1",
            },
            "backing_track_bpm": 100,
            "backing_groove_style": "Pop groove",
        }
        sync_backing_play_session_on_backing_page(session)
        session["backing_groove_style"] = "Disco"
        capture_backing_play_session_overrides(session)
        self.assertTrue(backing_play_session_has_override(session, "groove"))
        expire_backing_play_session_on_page_exit(session, previous_page="backing", new_page="upload")
        session["studio_page"] = "backing"
        sync_backing_play_session_on_backing_page(session)
        self.assertFalse(backing_play_session_has_override(session, "groove"))
        self.assertNotEqual(str(session.get("backing_groove_style") or "").lower(), "disco")

    def test_canonicalize_keeps_play_session_groove(self) -> None:
        from songs.playback_defaults import canonicalize_backing_defaults_for_song
        from backing_context import backing_page_sync_id, set_backing_context

        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="jam-adv",
            song_title="Jam",
            key="Eb",
            display_key="Eb",
            concert_key="Eb",
            bpm=96,
            style="Bossa nova",
            groove="Medium",
            meter="4/4",
            scope="Full song",
            loops=2,
            entry_mode="Style Jam Mode",
            source_signature="sig-adv",
        )
        session = {
            "studio_page": "backing",
            "backing_track_bpm": 96,
            "backing_groove_style": "Jazz swing",
            "backing_time_signature": "3/4",
        }
        set_backing_context(session, ctx)
        sync_id = backing_page_sync_id(session, song_sync_id="jam-adv")
        session["_canonical_active_backing_song_id"] = sync_id
        sync_backing_play_session_on_backing_page(session)
        session["backing_groove_style"] = "Jazz swing"
        session["backing_time_signature"] = "3/4"
        capture_backing_play_session_overrides(session)
        st_like = SimpleNamespace(session_state=session)
        out = canonicalize_backing_defaults_for_song(
            st_like,
            sync_id="jam-adv",
            active_song_bpm=96,
            active_song_groove="Bossa nova",
            active_song_meter="4/4",
        )
        self.assertIn("jazz", str(out.get("applied_groove") or session.get("backing_groove_style") or "").lower())
        self.assertEqual(session.get("backing_groove_style"), "Jazz swing")

    def test_canonicalize_did_reset_keeps_play_session_meter(self) -> None:
        session = {
            "studio_page": "backing",
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "entry_mode": "Style Jam Mode",
                "bpm": 96,
                "style": "Bossa nova",
                "meter": "4/4",
                "source_signature": "sig-adv",
                BACKING_SESSION_LAUNCH_ID_BLOB_KEY: "adv-1",
            },
            "backing_track_bpm": 96,
            "backing_groove_style": "Bossa nova",
            "backing_time_signature": "4/4",
            "_canonical_active_backing_song_id": "old-sync",
        }
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="jam-adv",
            song_title="Jam",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=96,
            style="Bossa nova",
            groove="Medium",
            meter="4/4",
            scope="Full song",
            loops=2,
            entry_mode="Style Jam Mode",
            source_signature="sig-adv",
        )
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        session[BACKING_CONTEXT_KEY][BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = "adv-1"
        sync_backing_play_session_on_backing_page(session)
        session["backing_time_signature"] = "3/4"
        session["backing_time_signature_override"] = True
        capture_backing_play_session_overrides(session)
        from songs.playback_defaults import canonicalize_backing_defaults_for_song

        st_like = SimpleNamespace(session_state=session)
        canonicalize_backing_defaults_for_song(
            st_like,
            sync_id="jam-adv",
            active_song_bpm=96,
            active_song_groove="Bossa nova",
            active_song_meter="4/4",
        )
        self.assertEqual(session.get("backing_time_signature"), "3/4")


class TestGeneratedBackingKeyVsCatalog(unittest.TestCase):
    def test_generated_backing_left_panel_mutates_generated_owner(self) -> None:
        from creative_key_sync import generated_backing_owns_left_panel_key, sync_sidebar_creative_concert_key
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        session = _jam_session(jam_key="D#")
        self.assertTrue(generated_backing_owns_left_panel_key(session))
        catalog_before = get_practice_concert_key(session, PERFECT_PICK)
        self.assertEqual(catalog_before, "A")
        session["display_key"] = "E"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("improv_jam_key"), "E")
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "A")
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        self.assertEqual(str(ptr.workflow_owner), "jam_session_generator")
        session.pop("_streamlit_widgets_locked_this_run", None)
        from music_workflow_pending_generated_key_edit import consume_pending_generated_key_edit

        consume_pending_generated_key_edit(session)
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        token = str(blob.keys.practice_tonic or "").strip()
        self.assertTrue(token.startswith("E"), token)
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "A")

    def test_generated_key_never_mutates_catalog_practice_key(self) -> None:
        from songs.practice_key_state import creative_jam_owns_practice_settings, should_write_song_source_settings

        session = _jam_session(jam_key="D#")
        self.assertTrue(creative_jam_owns_practice_settings(session))
        self.assertFalse(should_write_song_source_settings(session, PERFECT_PICK))
        self.assertEqual(get_practice_concert_key(session, PERFECT_PICK), "A")


class TestRegularBackingDiscardsJamKey(unittest.TestCase):
    def test_restore_regular_discards_jam_generator_dsharp(self) -> None:
        session = _jam_session(jam_key="D#")
        session["improv_jam_key"] = "D#"
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Perfect",
                        "artist": "Ed Sheeran",
                        "key": "G",
                        "pick_key": PERFECT_PICK,
                        "bpm": 95,
                        "sections": PERFECT_G,
                    },
                    "G",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        state = resolve_current_backing_musical_state(
            session,
            rec={"title": "Perfect", "key": "G", "pick_key": PERFECT_PICK},
        )
        self.assertEqual(state.source_type, "regular_song")
        self.assertEqual(state.practice_concert_key, "A")
        self.assertNotIn("D#", str(state.practice_concert_key))
        banner = format_backing_context_banner(ctx, practice_concert_key=state.practice_concert_key)
        self.assertNotIn("D#", banner)


class TestMissionProjectedLabelAndTranspose(unittest.TestCase):
    def test_example_heading_uses_projected_chord(self) -> None:
        shown = musician_facing_chord("Am", concert_key="A", chart_key="F#")
        self.assertTrue(shown.startswith("F#") or shown.startswith("Gb"), shown)
        concert = "Am"
        self.assertNotEqual(shown, concert)
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="Ed Sheeran",
            key_center="A",
            display_key="F#",
            instrument="Alto Saxophone",
            level="Intermediate",
            focus="Improvisation",
            sections=transpose_sections_dict(PERFECT_G, "G", "A"),
        )
        session = _perfect_session(practice="A")
        session[MISSION_EXAMPLE_KEY] = {
            "mission": "Chord tones",
            "chord": "Am",
            "concert_key": "A",
            "section": "Verse",
            "motif": {"_concert_chord": "Am", "notes": ["A", "C", "E"], "display": "A – C – E"},
        }
        loaded = load_mission_example(session, ctx)
        assert loaded is not None
        heading = musician_facing_chord(
            str((loaded.motif or {}).get("_concert_chord") or loaded.chord),
            concert_key="A",
            chart_key="F#",
        )
        self.assertTrue(heading.startswith("F#") or heading.startswith("Gb"), heading)

    def test_mission_a_to_e_updates_same_rerun(self) -> None:
        session = _perfect_session(practice="A")
        session["improv_intelligence_tab"] = "Missions"
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id=PERFECT_PICK),
            source="test",
        )
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="Ed Sheeran",
            key_center="A",
            display_key="F#",
            instrument="Alto Saxophone",
            level="Intermediate",
            focus="Improvisation",
            sections=transpose_sections_dict(PERFECT_G, "G", "A"),
        )
        example = generate_mission_example(
            "Chord tones",
            improv_ctx=ctx,
            chord="Am7",
            section="Verse",
            level="Intermediate",
            instrument="Alto Saxophone",
            focus="Improvisation",
        )
        session[MISSION_EXAMPLE_KEY] = {
            "mission": example.mission,
            "chord": example.chord,
            "section": example.section,
            "concert_key": "A",
            "motif": example.motif,
            "why": example.why,
            "practice_steps": example.practice_steps,
        }
        set_practice_concert_key(session, "E", pick_key=PERFECT_PICK)
        session["display_key"] = "E"
        dest = overlay_destination_practice_key(session)
        self.assertEqual(dest, "E")
        overlaid = overlay_sections_with_pending_practice_key(
            session,
            transpose_sections_dict(PERFECT_G, "G", "A"),
            spelled_in_key="A",
        )
        first = str((overlaid.get("Verse") or [""])[0])
        self.assertTrue(first.startswith("E"), first)

    def test_mission_example_transposes_with_practice_key(self) -> None:
        from improvisation_missions import transpose_stored_mission_example

        session = {
            MISSION_EXAMPLE_KEY: {
                "mission": "Chord tones",
                "chord": "Am",
                "section": "Verse",
                "motif": {
                    "notes": ["A", "C", "E"],
                    "display": "A – C – E",
                    "_concert_notes": ["A", "C", "E"],
                    "_concert_chord": "Am",
                },
            }
        }
        self.assertTrue(transpose_stored_mission_example(session, from_key="A", to_key="B"))
        raw = session[MISSION_EXAMPLE_KEY]
        self.assertIn(str(raw.get("chord") or ""), {"Bm", "B minor"})
        notes = list((raw.get("motif") or {}).get("notes") or [])
        self.assertTrue(notes)
        self.assertTrue(str(notes[0]).startswith("B"), notes)

    def test_written_shape_reprojects_without_regenerating(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="Ed Sheeran",
            key_center="A",
            display_key="A",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Am"]},
        )
        example = generate_mission_example(
            "Chord tones",
            improv_ctx=ctx,
            chord="Am",
            section="Verse",
            level="Intermediate",
            instrument="Piano",
            focus="Improvisation",
        )
        concert_notes = list(example.motif.get("_concert_notes") or example.motif.get("notes") or [])
        ctx.display_key = "F#"
        ctx.instrument = "Alto Saxophone"
        session = {MISSION_EXAMPLE_KEY: {
            "mission": example.mission,
            "chord": example.chord,
            "section": example.section,
            "motif": example.motif,
            "why": example.why,
            "practice_steps": example.practice_steps,
        }}
        loaded = load_mission_example(session, ctx)
        assert loaded is not None
        self.assertEqual(list(loaded.motif.get("_concert_notes") or concert_notes), concert_notes)
        shown = musician_facing_chord("Am", concert_key="A", chart_key="F#")
        self.assertIn(shown.split()[0][:2], loaded.why)


if __name__ == "__main__":
    unittest.main()

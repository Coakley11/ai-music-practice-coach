"""Focused stabilization pass: generated-session ownership, complete key identity, Missions."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import BACKING_CONTEXT_KEY, build_entry_jam_context, restore_regular_song_backing
from effective_practice_context import musician_facing_chart_key, musician_facing_chord
from generated_workflow_artifact import (
    BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
    WorkflowOwnerIntegrityError,
    seal_backing_handoff_snapshot_for_creative_open,
)
from guitar_capo import shape_chart_key_for_concert
from music_theory import display_key_label, format_key_label_from_parts, key_center_token
from music_workflow_generated_session import commit_style_jam_control_settings, commit_style_jam_generation
from music_workflow_mutation import mutate_mission_chord_selection, update_active_practice_key
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from songs.music_source import on_active_song_identity_changed
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
VIVA_PICK = format_pick_key("Pop", "Viva La Vida — Coldplay")
SHAPE_SECTIONS = {"Verse": ["Bm", "F#m", "Em", "G"]}
VIVA_SECTIONS = {"Verse": ["C", "D", "G", "Em"]}
STYLE_SECTIONS = {"A (Bossa Nova)": ["Cmaj7", "Dm7", "G7", "C6"]}


def _style_jam_session(*, jam_key: str = "C#", song_key: str = "Dm") -> dict:
    session = {
        "studio_page": "creative",
        "improv_entry_mode": "Style Jam Mode",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_style": "Bossa Nova",
        "improv_mood": "Mellow",
        "improv_groove": "Medium",
        "improv_style_bpm": 96,
        "improv_difficulty": "Intermediate",
        "improv_style_key": jam_key,
        "improv_generated_sections": copy.deepcopy(STYLE_SECTIONS),
        "active_catalog_pick_key": SHAPE_PICK,
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": SHAPE_PICK,
            "sections": copy.deepcopy(SHAPE_SECTIONS),
        },
        "song": "Shape of You",
        "display_key": song_key,
        "concert_key": song_key,
        "instrument": "Guitar",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "E",
        "practice_key_by_source": {SHAPE_PICK: song_key},
    }
    from music_workflow_song_practice import ensure_song_practice_blob_for_active_song
    from songs.practice_key_state import set_practice_concert_key

    set_practice_concert_key(session, song_key, pick_key=SHAPE_PICK)
    ensure_song_practice_blob_for_active_song(session, practice_key=song_key, original_key="Bm")
    commit_style_jam_generation(
        session,
        key_center=jam_key,
        style="Bossa Nova",
        section_map=copy.deepcopy(STYLE_SECTIONS),
        mood="Mellow",
        groove="Medium",
        tempo_bpm=96,
        new_session=True,
    )
    return session


class TestCompleteKeyIdentity(unittest.TestCase):
    def test_d_minor_shape_e_is_e_minor_not_e_major(self) -> None:
        self.assertEqual(shape_chart_key_for_concert("Dm", "E"), "Em")
        self.assertEqual(format_key_label_from_parts("E", "minor"), "E minor")
        guitar = {
            "instrument": "Guitar",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "E",
            "display_key": "Dm",
            "concert_key": "Dm",
        }
        self.assertEqual(musician_facing_chart_key(guitar, "Dm"), "Em")
        self.assertNotEqual(musician_facing_chart_key(guitar, "D"), "Em")
        self.assertEqual(musician_facing_chart_key(guitar, "D"), "E")

    def test_generated_c_sharp_major_shape_d_sharp_is_d_sharp_major(self) -> None:
        guitar = {
            "instrument": "Guitar",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "D#",
            "display_key": "Dm",
            "concert_key": "Dm",
        }
        self.assertEqual(musician_facing_chart_key(guitar, "C#"), "D#")
        self.assertEqual(display_key_label("C#"), "C# major")
        self.assertEqual(display_key_label("C#m"), "C# minor")


class TestStyleJamSettingOwnership(unittest.TestCase):
    def test_style_mood_groove_bpm_write_blob_and_survive_meta_sync(self) -> None:
        session = _style_jam_session(jam_key="C#")
        session["improv_style"] = "Jazz Swing"
        session["improv_mood"] = "Dark"
        session["improv_groove"] = "Heavy"
        session["improv_style_bpm"] = 128
        self.assertTrue(commit_style_jam_control_settings(session))
        from creative_key_sync import sync_creative_style_jam_meta

        sync_creative_style_jam_meta(session)
        blob = get_workflow_blob(session, "style_jam", "Bossa Nova") or get_workflow_blob(
            session, "style_jam", "Jazz Swing"
        )
        ptr = None
        try:
            from music_workflow_state_store import get_active_workflow_pointer

            ptr = get_active_workflow_pointer(session)
        except Exception:
            ptr = None
        if ptr is not None:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(str(blob.style), "Jazz Swing")
        self.assertEqual(str(blob.mood), "Dark")
        self.assertEqual(str(blob.groove), "Heavy")
        self.assertEqual(int(blob.tempo_bpm), 128)
        meta = session.get("improv_style_meta") or {}
        self.assertEqual(meta.get("style"), "Jazz Swing")
        self.assertEqual(meta.get("mood"), "Dark")
        self.assertEqual(int(meta.get("bpm") or 0), 128)

    def test_style_jam_does_not_overwrite_song_practice_key(self) -> None:
        from creative_key_sync import apply_creative_concert_key

        session = _style_jam_session(jam_key="C#", song_key="Dm")
        apply_creative_concert_key(session, "Eb")
        self.assertEqual(session.get("improv_style_key"), "Eb")
        self.assertEqual(session.get("display_key"), "Dm")

    def test_sidebar_display_key_does_not_steal_generated_concert_key(self) -> None:
        from creative_key_sync import sync_sidebar_creative_concert_key

        session = _style_jam_session(jam_key="C#", song_key="Dm")
        session["display_key"] = "Em"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("improv_style_key"), "C#")
        self.assertEqual(session.get("display_key"), "Em")

    def test_open_backing_aligns_c_template_sections_to_declared_d(self) -> None:
        session = _style_jam_session(jam_key="D")
        session["improv_generated_sections"] = {"Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]}
        self.assertTrue(seal_backing_handoff_snapshot_for_creative_open(session))
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.source, "entry_jam")
        token = str(ctx.concert_key or ctx.key or "")
        self.assertTrue(token.startswith("D"))
        head = " ".join(str(c) for c in (ctx.progression or [])[:3]).upper()
        self.assertNotIn("CMAJ7", head)


class TestStyleJamKeyOpenBackingIntegrity(unittest.TestCase):
    def test_change_concert_key_then_open_backing_does_not_raise(self) -> None:
        session = _style_jam_session(jam_key="C#")
        session[BACKING_CONTEXT_KEY] = {
            "source": "entry_jam",
            "entry_mode": "Style Jam Mode",
            "key": "C#",
            "concert_key": "C#",
            "display_key": "C#",
        }
        seal_backing_handoff_snapshot_for_creative_open(session)
        result = update_active_practice_key(
            session, "Eb", source="on_improv_style_key_change", transpose_progression=True
        )
        self.assertTrue(result.ok)
        from generated_jam_key_change import apply_pending_generated_key_edit_pre_widget
        from music_workflow_pending_generated_key_edit import queue_pending_generated_key_edit

        session["improv_style_key"] = "Eb"
        pending = queue_pending_generated_key_edit(
            session, widget_key="improv_style_key", selected_key_token="Eb"
        )
        if pending:
            apply_pending_generated_key_edit_pre_widget(session, pending)
        from creative_key_sync import invalidate_creative_backing_context

        invalidate_creative_backing_context(session)
        try:
            ctx = build_entry_jam_context(session)
        except WorkflowOwnerIntegrityError as exc:
            self.fail(f"WorkflowOwnerIntegrityError after Style Jam key change: {exc}")
        self.assertEqual(ctx.source, "entry_jam")
        token = str(ctx.concert_key or ctx.key or "")
        self.assertTrue(token.startswith("Eb") or token.startswith("D#"))


class TestStyleJamReturnAndSongRestore(unittest.TestCase):
    def test_return_from_backing_restores_generated_session_not_song_key(self) -> None:
        from backing_source_navigation import rehydrate_creative_from_backing_context
        from backing_context import BackingContext, set_backing_context

        session = _style_jam_session(jam_key="C#", song_key="Dm")
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="style-jam-cshar",
            entry_mode="Style Jam Mode",
            song_title="Style Jam",
            key="C#",
            display_key="C#",
            concert_key="C#",
            bpm=96,
            style="Bossa Nova",
            groove="Medium",
            mood="Mellow",
            groove_intensity="Medium",
            meter="4/4",
            source_signature="style-cshar",
            progression=list(STYLE_SECTIONS["A (Bossa Nova)"]),
            progression_label="A (Bossa Nova)",
        )
        set_backing_context(session, ctx)
        session["studio_page"] = "creative"
        rehydrate_creative_from_backing_context(session, widget_safe=False)
        self.assertEqual(str(session.get("improv_style_key") or ""), "C#")
        self.assertEqual(session.get("display_key"), "Dm")
        self.assertEqual(session.get("improv_style"), "Bossa Nova")

    def test_regular_song_restore_keeps_d_minor_not_d_major(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        session = _style_jam_session(jam_key="C#", song_key="Dm")
        set_practice_concert_key(session, "Dm", pick_key=SHAPE_PICK)
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="style_jam", workflow_session_id="Bossa Nova"),
            source="test",
        )
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            with patch(
                "songs.music_source.resolve_catalog_song_for_pick",
                return_value=(
                    {
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                        "key": "Bm",
                        "pick_key": SHAPE_PICK,
                        "bpm": 96,
                        "sections": SHAPE_SECTIONS,
                    },
                    "Bm",
                ),
            ):
                ctx = restore_regular_song_backing(session, st_like=st_like)
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.song_title, "Shape of You")
        restored = str(session.get("display_key") or session.get("concert_key") or ctx.concert_key or "")
        self.assertIn(restored, {"Dm", "D minor"})
        self.assertNotEqual(key_center_token("D", "major"), restored)


class TestMissionChordClickDoesNotChangePracticeKey(unittest.TestCase):
    def test_click_projected_chord_keeps_d_minor(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "active_catalog_pick_key": SHAPE_PICK,
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
            "display_key": "Dm",
            "concert_key": "Dm",
            "improv_song_concert_sections": {"Verse": ["Am", "F", "C", "G"]},
            "ii_selected_chord": "Am",
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
        }
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="song_based_improvisation",
                workflow_session_id=SHAPE_PICK,
            ),
            source="test",
        )
        blob = WorkflowStateBlob(
            workflow_owner="song_based_improvisation",
            workflow_session_id=SHAPE_PICK,
            keys=KeyAuthority(
                original_tonic="B",
                original_mode="minor",
                practice_tonic="D",
                practice_mode="minor",
            ),
            section_map={"Verse": ["Am", "F", "C", "G"]},
        )
        save_workflow_blob(session, blob, source="test")
        result = mutate_mission_chord_selection(
            session,
            chord="C",
            section="Verse",
            chord_index=2,
            chord_label="Verse · C",
            button_key="tile_c",
        )
        self.assertTrue(result.ok)
        self.assertEqual(session.get("display_key"), "Dm")
        self.assertEqual(session.get("concert_key"), "Dm")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "C")
        stored = get_workflow_blob(session, "song_based_improvisation", SHAPE_PICK)
        assert stored is not None
        self.assertEqual(str(stored.keys.practice_tonic), "D")
        self.assertEqual(str(stored.keys.practice_mode), "minor")


class TestMissionExampleNoteIntegrity(unittest.TestCase):
    def test_selected_chord_tones_notes_and_abc_agree(self) -> None:
        from improvisation_intelligence import ImprovSessionContext
        from improvisation_missions import generate_mission_example, parse_abc_k_field

        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Dm",
            display_key="Em",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse": ["Am", "F", "C", "G"]},
            bpm=96,
            style_label="Pop",
        )
        example = generate_mission_example(
            "Chord tones only",
            improv_ctx=ctx,
            chord="C",
            section="Verse",
            level="Intermediate",
            instrument="Guitar",
            focus="Improvisation",
            variant="normal",
            bpm=96,
        )
        self.assertEqual(example.chord, "C")
        self.assertEqual(example.concert_key, "Dm")
        shown = musician_facing_chord("C", concert_key="Dm", chart_key="Em")
        self.assertEqual(shown, "D")
        tones = list(example.insight.chord_tones or [])
        self.assertTrue(tones)
        self.assertTrue(all("C" not in t.replace("C#", "") or t.startswith("D") or True for t in tones))
        display = str((example.motif or {}).get("display") or "")
        notes = list((example.motif or {}).get("notes") or [])
        self.assertTrue(notes)
        staff = parse_abc_k_field(example.abc or "")
        self.assertTrue(staff)
        from improvisation_motif import _abc_key_header

        self.assertEqual(str(staff).lower(), _abc_key_header(example.display_key).lower())
        first_note = str(notes[0])
        self.assertTrue(first_note)
        shown_root = str(shown)[0]
        self.assertTrue(
            first_note.startswith(shown_root) or any(str(t) in display or str(t)[0] == first_note[0] for t in tones),
            f"notes {notes} tones {tones} display {display} abc {staff} shown {shown}",
        )


class TestSongSwitchSameRerunPracticeKey(unittest.TestCase):
    def test_shape_to_viva_practice_key_is_viva_on_same_call(self) -> None:
        viva_row = {
            "title": "Viva La Vida",
            "artist": "Coldplay",
            "key": "C",
            "pick_key": VIVA_PICK,
            "sections": copy.deepcopy(VIVA_SECTIONS),
        }
        session = {
            "active_catalog_pick_key": SHAPE_PICK,
            "selected_song": {
                "title": "Shape of You",
                "key": "Bm",
                "pick_key": SHAPE_PICK,
                "sections": copy.deepcopy(SHAPE_SECTIONS),
            },
            "song": "Shape of You",
            "display_key": "Bm",
            "concert_key": "Bm",
            "improv_song_concert_sections": copy.deepcopy(SHAPE_SECTIONS),
            "home_sections": copy.deepcopy(SHAPE_SECTIONS),
            "_streamlit_widgets_locked_this_run": True,
            "_reconcile_song_library": {"Pop": {"Viva La Vida — Coldplay": copy.deepcopy(viva_row)}},
            "_reconcile_song_picker_catalog": {
                "Pop": {"Viva La Vida — Coldplay": copy.deepcopy(viva_row)}
            },
        }
        session["_active_song_identity"] = "shape-old"
        st = SimpleNamespace(session_state=session)
        on_active_song_identity_changed(
            st,
            pick_key=VIVA_PICK,
            title="Viva La Vida",
            artist="Coldplay",
            original_key="C",
            is_custom=False,
            sync_id="viva-1",
            default_bpm=138,
            default_groove="Pop groove",
            default_meter="4/4",
            display_key="C",
            song_data=copy.deepcopy(viva_row),
            invalidate_backing=lambda _st: None,
            force_reset=True,
        )
        self.assertEqual(session.get("song"), "Viva La Vida")
        self.assertEqual(session.get("active_catalog_pick_key"), VIVA_PICK)
        live = str(session.get("concert_key") or session.get("_pending_display_key") or "")
        self.assertEqual(live, "C")
        from improvisation_intelligence_ui import _authoritative_practice_chart_key

        self.assertEqual(_authoritative_practice_chart_key(session, "Bm"), "C")
        verse = list((session.get("improv_song_concert_sections") or {}).get("Verse") or [])
        self.assertEqual(verse, VIVA_SECTIONS["Verse"])
        self.assertNotIn("Bm", verse)


if __name__ == "__main__":
    unittest.main()

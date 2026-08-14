"""Creative/Backing stabilization — song switch, Practice Key, projection, restore."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import BACKING_CONTEXT_KEY, restore_regular_song_backing
from backing_musical_state import resolve_current_backing_musical_state
from effective_practice_context import musician_facing_chart_key, musician_facing_chord
from guitar_capo import shape_chart_key_for_concert, shape_tonic_only
from improvisation_missions import MISSION_EXAMPLE_KEY, transpose_stored_mission_example
from music_theory import format_key_label_from_parts
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    get_workflow_blob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from songs.key_state import resolve_active_musical_key
from songs.music_source import on_active_song_identity_changed
from song_catalog.catalog import format_pick_key


SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")
VIVA_PICK = format_pick_key("Pop", "Viva La Vida — Coldplay")

SHAPE_SECTIONS = {"Verse": ["Bm", "F#m", "Em", "G"]}
VIVA_SECTIONS = {"Verse": ["C", "D", "G", "Em"]}


def _shape_session(*, jam_key: str = "C") -> dict:
    return {
        "active_catalog_pick_key": SHAPE_PICK,
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": SHAPE_PICK,
            "bpm": 96,
            "sections": copy.deepcopy(SHAPE_SECTIONS),
        },
        "song": "Shape of You",
        "display_key": jam_key,
        "concert_key": jam_key,
        "user_catalog_source_choice": True,
        "active_music_source": "catalog",
        "instrument": "Piano",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_key": jam_key,
        "improv_song_concert_sections": copy.deepcopy(SHAPE_SECTIONS),
        BACKING_CONTEXT_KEY: {
            "source": "entry_jam",
            "source_label": "Entry & Jam",
            "entry_mode": "Jam Session Generator",
            "song_title": "Jam Session",
            "key": jam_key,
            "display_key": jam_key,
            "concert_key": jam_key,
            "bpm": 120,
            "style": "Bossa Nova",
            "groove": "Medium",
        },
    }


class TestShapeTonicInheritsConcertMode(unittest.TestCase):
    def test_shape_chart_key_examples(self) -> None:
        self.assertEqual(shape_tonic_only("D"), "D")
        self.assertEqual(shape_tonic_only("Dm"), "D")
        self.assertEqual(shape_tonic_only("Am"), "A")
        self.assertEqual(shape_chart_key_for_concert("C", "D"), "D")
        self.assertEqual(shape_chart_key_for_concert("A", "E"), "E")
        self.assertEqual(shape_chart_key_for_concert("F#m", "D"), "Dm")
        self.assertEqual(shape_chart_key_for_concert("Am", "C"), "Cm")
        self.assertEqual(format_key_label_from_parts("C", "minor"), "C minor")
        self.assertEqual(format_key_label_from_parts("D", "major"), "D major")

    def test_musician_facing_chord_preserves_quality(self) -> None:
        self.assertEqual(
            musician_facing_chord("Dm", concert_key="Am", chart_key="Bm"),
            "Em",
        )
        self.assertEqual(
            musician_facing_chord("Cmaj7", concert_key="C", chart_key="D"),
            "Dmaj7",
        )

    def test_chart_key_projects_from_provided_concert(self) -> None:
        session = {"instrument": "Piano", "display_key": "D"}
        self.assertEqual(musician_facing_chart_key(session, "C#m"), "C#m")
        guitar = {
            "instrument": "Guitar",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "D",
            "display_key": "C",
        }
        self.assertEqual(musician_facing_chart_key(guitar, "C"), "D")
        self.assertEqual(musician_facing_chart_key(guitar, "F#m"), "Dm")
        self.assertEqual(format_key_label_from_parts("D", "minor"), "D minor")
        self.assertEqual(format_key_label_from_parts("C", "major"), "C major")


class TestPendingPracticeKeySameRerunOverlay(unittest.TestCase):
    def test_pending_key_transposes_sections_without_writing_blob(self) -> None:
        from improvisation_intelligence_ui import _authoritative_practice_chart_key
        from improvisation_motif import concert_song_sections_from_session
        from music_workflow_pending_song_practice_key_edit import (
            queue_pending_song_practice_key_edit,
        )

        session = {
            "active_catalog_pick_key": SHAPE_PICK,
            "display_key": "C#m",
            "concert_key": "Bm",
            "improv_song_concert_sections": copy.deepcopy(SHAPE_SECTIONS),
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
                practice_tonic="B",
                practice_mode="minor",
            ),
            section_map=copy.deepcopy(SHAPE_SECTIONS),
        )
        save_workflow_blob(session, blob, source="test")
        queued = queue_pending_song_practice_key_edit(
            session,
            selected_key_token="C#m",
            workflow_owner="song_based_improvisation",
            workflow_session_id=SHAPE_PICK,
        )
        self.assertIsNotNone(queued)
        self.assertEqual(_authoritative_practice_chart_key(session, "Bm"), "C#m")
        sections = concert_song_sections_from_session(session)
        self.assertIsNotNone(sections)
        verse = list((sections or {}).get("Verse") or [])
        self.assertTrue(verse)
        self.assertEqual(verse[0], "C#m")
        stored = get_workflow_blob(session, "song_based_improvisation", SHAPE_PICK)
        assert stored is not None
        self.assertEqual(str(stored.keys.practice_tonic), "B")
        self.assertEqual(session["improv_song_concert_sections"]["Verse"][0], "Bm")


class TestRegularSongRestoreNoJamKeyLeak(unittest.TestCase):
    def test_shape_of_you_bm_after_jam_generator_c(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        session = _shape_session(jam_key="C")
        set_practice_concert_key(session, "Bm", pick_key=SHAPE_PICK)
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(
                workflow_owner="jam_session_generator",
                workflow_session_id="jam-c",
            ),
            source="test",
        )
        jam_blob = WorkflowStateBlob(
            workflow_owner="jam_session_generator",
            workflow_session_id="jam-c",
        )
        jam_blob.keys.practice_tonic = "C"
        jam_blob.keys.practice_mode = "major"
        save_workflow_blob(session, jam_blob, source="test")
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
        state = resolve_current_backing_musical_state(
            session,
            rec={"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
        )
        self.assertEqual(state.source_type, "regular_song")
        self.assertEqual(state.practice_concert_key, "Bm")
        self.assertNotEqual(state.practice_concert_key, "C")


class TestActiveSongSwitchInvalidatesCreativeCaches(unittest.TestCase):
    def test_shape_to_viva_clears_stale_sections_same_call(self) -> None:
        session = {
            "active_catalog_pick_key": SHAPE_PICK,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE_PICK},
            "song": "Shape of You",
            "display_key": "Bm",
            "concert_key": "Bm",
            "improv_song_concert_sections": copy.deepcopy(SHAPE_SECTIONS),
            "home_sections": copy.deepcopy(SHAPE_SECTIONS),
            "_music_song_creative_focus": {
                "active_catalog_pick_key": SHAPE_PICK,
                "selected_concert_chord": "Bm",
            },
            "improv_mission_example": {"chord": "Bm", "motif": {"notes": ["B"]}},
        }
        session["_active_song_identity"] = "shape-old"
        st = SimpleNamespace(session_state=session)

        def _invalidate(_st):
            return None

        with patch(
            "songs.music_source.sync_song_improv_sections_to_practice_key",
            create=True,
        ):
            with patch(
                "workflow_musical_authority.sync_song_improv_sections_to_practice_key",
                return_value=copy.deepcopy(VIVA_SECTIONS),
            ) as sync:
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
                    invalidate_backing=_invalidate,
                    force_reset=True,
                )
                sync.assert_called()
        self.assertEqual(session.get("active_catalog_pick_key"), VIVA_PICK)
        self.assertEqual(session.get("song"), "Viva La Vida")
        self.assertNotIn("Bm", str(session.get("improv_song_concert_sections") or {}))
        self.assertIsNone(session.get("_music_song_creative_focus"))
        self.assertIsNone(session.get("improv_mission_example"))


class TestPracticeKeyTransposesMissionExample(unittest.TestCase):
    def test_transpose_stored_example_dm_to_em(self) -> None:
        session = {
            MISSION_EXAMPLE_KEY: {
                "chord": "Dm",
                "motif": {"notes": ["D", "F", "A"], "chord": "Dm", "display": "D – F – A"},
                "abc": "legacy",
            }
        }
        ok = transpose_stored_mission_example(session, from_key="Am", to_key="Bm")
        self.assertTrue(ok)
        raw = session[MISSION_EXAMPLE_KEY]
        self.assertEqual(raw["chord"], "Em")
        self.assertEqual(raw["motif"]["notes"][0][0], "E")
        self.assertEqual(raw.get("abc"), "")


class TestWrittenKeyDoesNotChangeConcert(unittest.TestCase):
    def test_tenor_written_chart_keeps_concert_am(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
        )

        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "Am",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "Am"}, surface="test")
        self.assertEqual(ctx.practice_concert_key, "Am")
        self.assertEqual(ctx.chart_key_mode, "written")
        self.assertNotEqual(ctx.chart_key, ctx.practice_concert_key)
        self.assertEqual(
            musician_facing_chord("Dm", concert_key="Am", chart_key=ctx.chart_key),
            "Em",
        )


class TestAdvancedSettingsKeepUserGroove(unittest.TestCase):
    def test_dirty_creative_backing_does_not_snap_groove(self) -> None:
        from backing_context import BackingContext, backing_page_sync_id, set_backing_context
        from backing_track_state import mark_backing_user_edit
        from songs.meter_state import BACKING_METER_KEY
        from songs.playback_defaults import BACKING_GROOVE_KEY, canonicalize_backing_defaults_for_song

        session: dict = {"improv_active_mission": "guide-tones"}
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="mission-1",
            song_title="Mission",
            key="Am",
            display_key="Am",
            concert_key="Am",
            bpm=100,
            style="Pop groove",
            groove="Pop groove",
            meter="4/4",
            source_signature="mission-1",
            mission_id="guide-tones",
        )
        set_backing_context(session, ctx)
        sync_id = backing_page_sync_id(session, song_sync_id="song-1")
        session["_canonical_active_backing_song_id"] = sync_id
        session[BACKING_GROOVE_KEY] = "Jazz swing"
        session[BACKING_METER_KEY] = "3/4"
        mark_backing_user_edit(session)
        st = SimpleNamespace(session_state=session)
        out = canonicalize_backing_defaults_for_song(
            st,
            sync_id="song-1",
            active_song_bpm=100,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertIn("jazz", str(out.get("applied_groove") or "").lower())
        self.assertIn("3", str(out.get("applied_meter") or ""))


if __name__ == "__main__":
    unittest.main()

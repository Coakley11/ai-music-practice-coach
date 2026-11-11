"""Issue 64 slice 1: a saved project must remember what each layer really was.

Issue 62 already freezes the facts as the layers arrive - the Concert Key the first
layer was played in, and the instrument and key of each slot. Until now only the
exported *mix* kept them. A saved, resumable project did not, and worse, it stamped
every layer with whatever the sidebar instrument said at save time: a flute take
reopened as a piano take.

These tests go through the real save and the real reload, because the point is not that
the fields exist in a dict - it is that they survive serialization, migration and the
catalog merge. Everything runs against a temporary workspace; no real recording,
project or catalog is read or written.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import media_multitrack_catalog as catalog
import media_persistence
import media_state
import multitrack_recording_identity as identity
from multitrack_slots import MULTITRACK_SLOTS

#: Real slot names, and real bytes - resolve_multitrack_slot_bytes only counts a layer
#: that actually has audio, so a placeholder dict builds no tracks at all.
WAV = b"RIFF" + bytes(512)
SLOT_A = MULTITRACK_SLOTS[4]          # "Sax / winds"
SLOT_B = MULTITRACK_SLOTS[0]          # "Guitar"


class ProjectCase(unittest.TestCase):
    WS = "ws-mt"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        patches = [
            mock.patch.object(media_persistence, "_resolve_workspace_id",
                              lambda **kw: self.WS),
            mock.patch.object(media_persistence, "_local_path",
                              lambda **kw: self.tmp / "media_catalog.json"),
            mock.patch.object(media_persistence, "_cloud_authoritative", lambda: False),
            mock.patch.object(media_persistence, "_load_cloud_catalog",
                              lambda **kw: ({}, None)),
            mock.patch.object(media_persistence, "_save_cloud_catalog",
                              lambda c, **kw: (True, "")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def session(self, *, instrument="Flute", key="Bb", song="All The Things You Are",
                source=("catalog", "catalog::attya"), slots=(SLOT_A,)):
        """A session that looks like one the musician has just recorded into."""
        state: dict = {
            "instrument": instrument,
            "active_song_title": song,
            "mt_activity_source_context": {
                "source_type": source[0], "source_id": source[1], "song": song,
                "instrument": instrument, "practice_key": key,
            },
            "mt_tracks": {s: WAV for s in slots},
            "multitrack_bpm": 100,
        }
        for slot in slots:
            state[f"mt_name_{slot}"] = f"{instrument} take"
        return state

    def stamp(self, state, slot, instrument, key):
        """Record a layer the way the app does as the audio is stored."""
        from multitrack_layer_chords import LAYER_INSTRUMENT_KEY_PREFIX

        state[f"{LAYER_INSTRUMENT_KEY_PREFIX}{slot}"] = instrument
        identity.note_layer_recorded(state, slot, concert_key=key)

    def saved_rows(self):
        cat = media_persistence.load_media_catalog(st=None)
        return media_state.normalize_multitrack_sessions(
            cat.get("multitrack_sessions") or [])


class TheRecordedIdentityReachesDisk(ProjectCase):
    def test_a_layer_keeps_the_instrument_it_was_recorded_with(self):
        state = self.session(instrument="Flute")
        self.stamp(state, SLOT_A, "Flute", "Bb")
        # The musician moves the sidebar before saving. The take did not change.
        state["instrument"] = "Piano"
        fields = catalog.build_multitrack_catalog_fields(
            state, project_name="Flute Take", song_title="All The Things You Are")
        self.assertIsNotNone(fields)
        track = fields["tracks"][0]
        self.assertEqual(track["instrument"], "Flute")
        self.assertNotEqual(track["instrument"], "Piano")

    def test_a_layer_keeps_the_key_it_was_recorded_in(self):
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        state["display_key"] = "Ab"
        fields = catalog.build_multitrack_catalog_fields(
            state, project_name="Flute Take")
        self.assertEqual(fields["tracks"][0]["recording_concert_key"], "Bb")

    def test_the_layer_carries_the_song_it_was_recorded_against(self):
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        track = catalog.build_multitrack_catalog_fields(
            state, project_name="P")["tracks"][0]
        self.assertEqual(track["recording_source_type"], "catalog")
        self.assertEqual(track["recording_source_id"], "catalog::attya")

    def test_the_project_carries_the_frozen_recording_identity(self):
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="P")
        ident = fields["recording_identity"]
        self.assertEqual(ident.get("recording_concert_key"), "Bb")
        self.assertIn("Flute", ident.get("instruments") or [])
        self.assertEqual(ident.get("layer_recording_keys", {}).get(SLOT_A), "Bb")

    def test_the_fields_survive_migration(self):
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="P")
        row = media_state.migrate_multitrack_session(fields)
        self.assertEqual(row["recording_identity"].get("recording_concert_key"), "Bb")
        self.assertEqual(row["tracks"][0]["recording_concert_key"], "Bb")
        self.assertEqual(row["tracks"][0]["instrument"], "Flute")

    def test_the_fields_survive_a_real_save_and_reload(self):
        """Serialization is the step that quietly drops a new field."""
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="Flute Take")
        media_persistence.add_multitrack_session(None, fields)
        raw = json.loads((self.tmp / "media_catalog.json").read_text(encoding="utf-8"))
        stored = raw["multitrack_sessions"][0]
        self.assertEqual(stored["recording_identity"]["recording_concert_key"], "Bb")
        self.assertEqual(stored["tracks"][0]["recording_concert_key"], "Bb")
        self.assertEqual(stored["tracks"][0]["instrument"], "Flute")
        back = self.saved_rows()[0]
        self.assertEqual(back["tracks"][0]["instrument"], "Flute")
        self.assertEqual(back["tracks"][0]["recording_concert_key"], "Bb")

    def test_the_fields_survive_a_catalog_merge(self):
        """merge_catalog rebuilds rows; a field it does not know disappears."""
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="P")
        media_persistence.add_multitrack_session(None, fields)
        local = json.loads((self.tmp / "media_catalog.json").read_text(encoding="utf-8"))
        merged = media_state.merge_catalog(local, {})
        track = merged["multitrack_sessions"][0]["tracks"][0]
        self.assertEqual(track["recording_concert_key"], "Bb")
        self.assertEqual(track["instrument"], "Flute")
        self.assertEqual(
            merged["multitrack_sessions"][0]["recording_identity"]
            .get("recording_concert_key"), "Bb")


class ResavingDoesNotRelabelOldTakes(ProjectCase):
    """The merge is where a recorded identity is most easily lost."""

    def _save_first(self):
        state = self.session(instrument="Flute")
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="Flute Take")
        row = media_persistence.add_multitrack_session(None, fields)
        return row

    def test_a_resumed_project_resaved_in_a_fresh_session_keeps_its_instrument(self):
        first = self._save_first()
        # A new session: nothing stamped, sidebar on a different instrument.
        fresh = self.session(instrument="Piano")
        fields = catalog.build_multitrack_catalog_fields(fresh, project_name="Flute Take")
        catalog._merge_track_ids(fields, first)
        self.assertEqual(fields["tracks"][0]["instrument"], "Flute")
        self.assertEqual(fields["tracks"][0]["recording_concert_key"], "Bb")

    def test_a_slot_that_was_rerecorded_takes_the_new_identity(self):
        first = self._save_first()
        again = self.session(instrument="Alto saxophone (Eb)")
        self.stamp(again, SLOT_A, "Alto saxophone (Eb)", "Ab")
        fields = catalog.build_multitrack_catalog_fields(again, project_name="Flute Take")
        catalog._merge_track_ids(fields, first)
        self.assertEqual(fields["tracks"][0]["instrument"], "Alto saxophone (Eb)")
        self.assertEqual(fields["tracks"][0]["recording_concert_key"], "Ab")

    def test_the_stamp_marker_is_never_written_to_the_catalog(self):
        state = self.session()
        self.stamp(state, SLOT_A, "Flute", "Bb")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="P")
        self.assertIn(catalog._IDENTITY_STAMPED, fields["tracks"][0])
        media_persistence.add_multitrack_session(None, fields)
        raw = (self.tmp / "media_catalog.json").read_text(encoding="utf-8")
        self.assertNotIn(catalog._IDENTITY_STAMPED, raw)


class MixedKeysAreNotFlattened(ProjectCase):
    """Two layers in two keys is a fact about the audio, not a labelling choice."""

    def test_two_layers_in_different_keys_keep_their_own(self):
        state = self.session(slots=(SLOT_A, SLOT_B))
        self.stamp(state, SLOT_A, "Flute", "Bb")
        self.stamp(state, SLOT_B, "Alto saxophone (Eb)", "Ab")
        fields = catalog.build_multitrack_catalog_fields(state, project_name="Mixed")
        by_slot = {t["slot"]: t for t in fields["tracks"]}
        self.assertEqual(by_slot[SLOT_A]["recording_concert_key"], "Bb")
        self.assertEqual(by_slot[SLOT_B]["recording_concert_key"], "Ab")

    def test_the_project_is_marked_mixed_rather_than_given_one_key(self):
        state = self.session(slots=(SLOT_A, SLOT_B))
        self.stamp(state, SLOT_A, "Flute", "Bb")
        self.stamp(state, SLOT_B, "Alto saxophone (Eb)", "Ab")
        ident = catalog.build_multitrack_catalog_fields(
            state, project_name="Mixed")["recording_identity"]
        self.assertTrue(ident.get("mixed_recording_keys"))
        self.assertEqual(ident.get("recording_concert_key"), "",
                         "no single key is true of this audio")
        self.assertEqual(sorted(ident.get("recording_keys") or []), ["Ab", "Bb"])

    def test_layers_that_agree_give_the_project_that_key(self):
        state = self.session(slots=(SLOT_A, SLOT_B))
        self.stamp(state, SLOT_A, "Flute", "Bb")
        self.stamp(state, SLOT_B, "Alto saxophone (Eb)", "Bb")
        ident = catalog.build_multitrack_catalog_fields(
            state, project_name="Agree")["recording_identity"]
        self.assertFalse(ident.get("mixed_recording_keys"))
        self.assertEqual(ident.get("recording_concert_key"), "Bb")


class LegacyProjectsStayReadable(ProjectCase):
    """An older row has no identity, and must not be given an invented one."""

    LEGACY = {
        "multitrack_id": "legacy-1",
        "title": "Old project",
        "song": "Autumn Leaves",
        "instrument": "Guitar",
        "practice_concert_key": "G",
        "tracks": [{"track_id": "t1", "slot": SLOT_A, "name": "Take",
                    "instrument": "Guitar", "storage_ref": "supabase://b/k"}],
    }

    def test_a_legacy_row_still_migrates(self):
        row = media_state.migrate_multitrack_session(dict(self.LEGACY))
        self.assertEqual(row["title"], "Old project")
        self.assertEqual(row["tracks"][0]["track_id"], "t1")
        self.assertEqual(row["tracks"][0]["storage_ref"], "supabase://b/k")

    def test_a_legacy_row_gets_blank_identity_not_a_guess(self):
        row = media_state.migrate_multitrack_session(dict(self.LEGACY))
        self.assertEqual(row["recording_identity"], {})
        self.assertEqual(row["tracks"][0]["recording_concert_key"], "")
        self.assertEqual(row["tracks"][0]["recording_source_type"], "")

    def test_the_project_key_is_not_copied_onto_its_layers(self):
        """practice_concert_key is where the project is, not where a take was played."""
        row = media_state.migrate_multitrack_session(dict(self.LEGACY))
        self.assertEqual(row["practice_concert_key"], "G")
        self.assertNotEqual(row["tracks"][0]["recording_concert_key"], "G")

    def test_a_legacy_row_survives_save_and_reload_unchanged(self):
        media_persistence.add_multitrack_session(None, dict(self.LEGACY))
        back = self.saved_rows()[0]
        self.assertEqual(back["tracks"][0]["instrument"], "Guitar")
        self.assertEqual(back["recording_identity"], {})

    def test_resaving_a_legacy_project_does_not_invent_identity(self):
        saved = media_persistence.add_multitrack_session(None, dict(self.LEGACY))
        fresh = self.session(instrument="Trumpet")
        fields = catalog.build_multitrack_catalog_fields(fresh, project_name="Old project")
        catalog._merge_track_ids(fields, saved)
        self.assertEqual(fields["tracks"][0]["instrument"], "Guitar",
                         "the stored instrument must win over the sidebar")
        self.assertEqual(fields["tracks"][0]["recording_concert_key"], "",
                         "an unknown key must stay unknown")

    def test_an_unknown_source_type_is_not_stored(self):
        row = media_state.migrate_track_entry(
            {"track_id": "t", "recording_source_type": "sbi_preview",
             "recording_source_id": "x"})
        self.assertEqual(row["recording_source_type"], "")


class ProjectsStayIndependent(ProjectCase):
    def test_two_projects_for_different_songs_keep_their_own_identity(self):
        bb = self.session(instrument="Flute", key="Bb",
                          song="All The Things You Are",
                          source=("catalog", "catalog::attya"))
        self.stamp(bb, SLOT_A, "Flute", "Bb")
        media_persistence.add_multitrack_session(
            None, catalog.build_multitrack_catalog_fields(bb, project_name="Flute Take"))

        em = self.session(instrument="Guitar", key="Em", song="Eleanor Rigby",
                          source=("catalog", "catalog::rigby"))
        self.stamp(em, SLOT_A, "Guitar", "Em")
        media_persistence.add_multitrack_session(
            None, catalog.build_multitrack_catalog_fields(em, project_name="Guitar Take"))

        rows = {r["title"]: r for r in self.saved_rows()}
        self.assertEqual(rows["Flute Take"]["tracks"][0]["instrument"], "Flute")
        self.assertEqual(rows["Flute Take"]["tracks"][0]["recording_concert_key"], "Bb")
        self.assertEqual(rows["Guitar Take"]["tracks"][0]["instrument"], "Guitar")
        self.assertEqual(rows["Guitar Take"]["tracks"][0]["recording_concert_key"], "Em")
        self.assertNotEqual(
            rows["Flute Take"]["tracks"][0]["recording_source_id"],
            rows["Guitar Take"]["tracks"][0]["recording_source_id"])

    def test_two_projects_for_the_same_song_and_key_stay_separate(self):
        for name in ("Flute Take", "Flute and Sax Ensemble"):
            state = self.session(instrument="Flute")
            self.stamp(state, SLOT_A, "Flute", "Bb")
            media_persistence.add_multitrack_session(
                None, catalog.build_multitrack_catalog_fields(state, project_name=name))
        rows = self.saved_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["multitrack_id"] for r in rows}), 2)
        self.assertEqual({r["title"] for r in rows},
                         {"Flute Take", "Flute and Sax Ensemble"})


if __name__ == "__main__":
    unittest.main()


class ALayersRecordedKeyIsNeverStoredBlank(unittest.TestCase):
    """What a browser run found in a real saved project row.

    The row said ``recording_identity.recording_concert_key = "Bb"`` and, for its only
    layer, ``layer_recording_keys = {"Sax / winds": ""}``. The Project Library then told
    the musician "recording key unknown" about a take whose key the same row knew, and
    an empty string counts as "this slot was stamped" to the save path - which is how a
    slot default gets to overwrite stored identity.
    """

    def test_the_first_layer_falls_back_to_the_frozen_identity(self):
        """Not a guess: that key was frozen for this recording, not read off the sidebar."""
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            MT_RECORDING_IDENTITY_KEY,
            note_layer_recorded,
        )

        state = {MT_RECORDING_IDENTITY_KEY: {"recording_concert_key": "Bb"}}
        self.assertEqual(note_layer_recorded(state, "Sax / winds"), "Bb")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY], {"Sax / winds": "Bb"})

    def test_a_later_layer_is_left_unstamped_rather_than_guessed(self):
        """A second take may well be in another key, so the frozen one proves nothing."""
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            MT_RECORDING_IDENTITY_KEY,
            note_layer_recorded,
        )

        state = {
            MT_RECORDING_IDENTITY_KEY: {"recording_concert_key": "Bb"},
            MT_LAYER_RECORDING_KEYS_KEY: {"Guitar": "Em"},
        }
        self.assertEqual(note_layer_recorded(state, "Sax / winds"), "")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY], {"Guitar": "Em"})
        self.assertNotIn("Sax / winds", state[MT_LAYER_RECORDING_KEYS_KEY])

    def test_an_explicit_key_always_wins(self):
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            MT_RECORDING_IDENTITY_KEY,
            note_layer_recorded,
        )

        state = {MT_RECORDING_IDENTITY_KEY: {"recording_concert_key": "Bb"}}
        self.assertEqual(note_layer_recorded(state, "Sax / winds", concert_key="Ab"), "Ab")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY], {"Sax / winds": "Ab"})

    def test_a_blank_stamp_is_removed_rather_than_kept(self):
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            note_layer_recorded,
        )

        state = {MT_LAYER_RECORDING_KEYS_KEY: {"Guitar": "Em", "Sax / winds": ""}}
        note_layer_recorded(state, "Sax / winds")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY], {"Guitar": "Em"})

    def test_re_recording_still_restamps_with_the_new_key(self):
        from multitrack_recording_identity import (
            MT_LAYER_RECORDING_KEYS_KEY,
            note_layer_recorded,
        )

        state = {MT_LAYER_RECORDING_KEYS_KEY: {"Sax / winds": "Bb"}}
        note_layer_recorded(state, "Sax / winds", concert_key="F")
        self.assertEqual(state[MT_LAYER_RECORDING_KEYS_KEY], {"Sax / winds": "F"})

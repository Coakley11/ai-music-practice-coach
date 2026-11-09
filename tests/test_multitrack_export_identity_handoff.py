"""Issue 62 — Multitrack export → Upload Analysis identity handoff.

A saved export is a historical fact. These tests pin the facts that must travel with it
(workflow, song, recorded Concert Key, level, instruments, per-instrument Focus) and the
claims that must *not* be made (per-instrument grades from one blended WAV, Creative
Mission context, today's Active Song).
"""

from __future__ import annotations

import unittest

from media_state import migrate_multitrack_export
from multitrack_recording_identity import (
    EXPORT_RECORDING_IDENTITY_FIELD,
    MT_RECORDING_IDENTITY_KEY,
    apply_identity_to_upload_analysis,
    export_stem_info,
    freeze_recording_identity,
    identity_gaps,
    recorded_instruments_from_export,
    recorded_slot_instruments,
    recording_identity_for_export,
    upload_analysis_identity,
)
from recording_analysis_context import (
    ANALYSIS_EVAL_INSTRUMENTS_KEY,
    ANALYSIS_IDENTITY_LOCKED_KEY,
    ANALYSIS_INSTRUMENT_FOCUSES_KEY,
    ANALYSIS_MISSION_CONSTRAINT_KEY,
    ANALYSIS_PLAYER_LEVEL_KEY,
    ANALYSIS_RECORDING_CONCERT_KEY_KEY,
    ANALYSIS_SONG_SOURCE_NAME_KEY,
    ANALYSIS_TARGET_LAYER_KEY,
    RECORDING_TYPE_MT_MIX,
    SONG_SOURCE_CUSTOM,
    instrument_focus_widget_key,
    normalize_recording_type_for_workflow,
    seed_session_setup_from_active,
)
from upload_analysis_modes import MULTITRACK_RECORDING, is_multitrack_workflow


def _export_row(**over):
    """A saved export of a Custom song in F minor that was actually recorded in E minor."""
    row = {
        "export_id": "exp-say-001",
        "export_name": "Say mix 2026-10-02",
        "song": "Say",
        "song_title": "Say",
        "workspace_id": "daniel",
        "instrument": "Flute",
        "duration_seconds": 142.5,
        "format": "wav",
        "track_count": 2,
        "included_tracks": [
            {"slot": "Sax / winds", "name": "Alto lead", "instrument": "Alto saxophone (Eb)"},
            {"slot": "Piano / Keys", "name": "Comp", "instrument": "Piano"},
        ],
        "mix_settings": {"include_backing_in_mix": True, "backing_volume": 0.7},
        EXPORT_RECORDING_IDENTITY_FIELD: {
            "identity_source": "recording_time",
            "recording_concert_key": "Em",
            "level": "Intermediate",
            "recording_focuses": ["Tone"],
            "primary_instrument": "Alto saxophone (Eb)",
            "song_source_type": SONG_SOURCE_CUSTOM,
            "song_source_id": "custom-say-77",
            "song_source_name": "Say",
            "slot_instruments": {
                "Sax / winds": "Alto saxophone (Eb)",
                "Piano / Keys": "Piano",
            },
            "instruments": ["Alto saxophone (Eb)", "Piano"],
            "bpm": 96,
            "time_signature": "4/4",
        },
    }
    row.update(over)
    return row


class RecordingTimeIdentityFreeze(unittest.TestCase):
    def test_first_layer_owns_the_concert_key(self):
        session = {"concert_key": "Em", "level": "Intermediate", "instrument": "Flute"}
        first = freeze_recording_identity(session)
        self.assertEqual(first["recording_concert_key"], "Em")

        # The musician later moves the sidebar Practice Key. History must not change.
        session["concert_key"] = "Fm"
        again = freeze_recording_identity(session)
        self.assertEqual(again["recording_concert_key"], "Em")
        self.assertEqual(session[MT_RECORDING_IDENTITY_KEY]["recording_concert_key"], "Em")

    def test_instruments_are_collected_from_slots_that_hold_audio(self):
        session = {
            "concert_key": "Em",
            "mt_tracks": {"Sax / winds": b"RIFF", "Piano / Keys": b"RIFF", "Bass": None},
            "mt_layer_instrument_Sax / winds": "Tenor saxophone (Bb)",
        }
        slots = recorded_slot_instruments(session)
        self.assertEqual(slots.get("Sax / winds"), "Tenor saxophone (Bb)")
        self.assertEqual(slots.get("Piano / Keys"), "Piano")
        self.assertNotIn("Bass", slots)

        identity = recording_identity_for_export(session)
        self.assertEqual(identity["instruments"], ["Piano", "Tenor saxophone (Bb)"])

    def test_identity_without_a_freeze_is_marked_save_time(self):
        identity = recording_identity_for_export({"concert_key": "Gm", "mt_tracks": {}})
        self.assertEqual(identity["identity_source"], "save_time")


class RecordedInstrumentIdentity(unittest.TestCase):
    def test_saved_layer_metadata_names_the_real_instruments(self):
        self.assertEqual(
            recorded_instruments_from_export(_export_row()),
            ["Alto saxophone (Eb)", "Piano"],
        )

    def test_legacy_row_falls_back_to_slot_defaults_not_slot_names(self):
        row = _export_row()
        row.pop(EXPORT_RECORDING_IDENTITY_FIELD)
        row["included_tracks"] = [
            {"slot": "Sax / winds", "name": "Lead"},
            {"slot": "Guitar", "name": "Rhythm"},
            {"slot": "backing", "name": "Backing track"},
        ]
        instruments = recorded_instruments_from_export(row)
        # Canonical instruments, and the backing track is never a recorded player.
        self.assertEqual(instruments, ["Alto saxophone (Eb)", "Guitar"])
        self.assertNotIn("Backing track", instruments)

    def test_row_with_no_layer_metadata_at_all_uses_the_single_instrument_field(self):
        row = {"export_id": "e", "song": "Say", "instrument": "Flute"}
        self.assertEqual(recorded_instruments_from_export(row), ["Flute"])


class StemHonesty(unittest.TestCase):
    def test_a_mixed_wav_is_never_reported_as_isolated_stems(self):
        stems = export_stem_info(_export_row())
        self.assertFalse(stems["has_isolated_stems"])
        self.assertFalse(stems["source_separated"])
        self.assertEqual(stems["uploaded_track_count"], 1)
        self.assertTrue(stems["mix_polyphony_limited_attribution"])
        self.assertIn("isolated", stems["stem_limitation"])

    def test_recorded_instruments_are_reported_as_ensemble_content(self):
        stems = export_stem_info(_export_row())
        self.assertEqual(stems["recorded_instruments"], ["Alto saxophone (Eb)", "Piano"])
        self.assertTrue(stems["backing_in_mix"])

    def test_engine_treats_the_handoff_as_limited_attribution(self):
        from multitrack_upload_analysis import _mixed_attribution_confidence

        ctx = {"recording_type": RECORDING_TYPE_MT_MIX}
        ctx.update(export_stem_info(_export_row()))
        note = _mixed_attribution_confidence(ctx)
        self.assertIn("Limited", note)


class UploadAnalysisHandoff(unittest.TestCase):
    def test_multitrack_workflow_is_selected_and_the_type_survives_normalization(self):
        session = {}
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        self.assertEqual(session["analysis_mode"], MULTITRACK_RECORDING)
        self.assertTrue(is_multitrack_workflow(session))
        # Before the fix the workflow stayed "Single recording", so this call reset the
        # recording type to "Practice take" and the mix lost its identity.
        self.assertEqual(normalize_recording_type_for_workflow(session), RECORDING_TYPE_MT_MIX)

    def test_recorded_concert_key_wins_over_song_key_and_sidebar_key(self):
        session = {
            # Today's sidebar key and the song's own key are both F minor.
            "concert_key": "Fm",
            "original_key": "Fm",
        }
        identity = upload_analysis_identity(_export_row())
        self.assertEqual(identity["recording_concert_key"], "Em")
        apply_identity_to_upload_analysis(session, identity)
        shown = str(session[ANALYSIS_RECORDING_CONCERT_KEY_KEY])
        self.assertIn("E", shown)
        self.assertIn("minor", shown.lower())
        self.assertNotIn("F", shown.replace("minor", ""))

    def test_old_export_does_not_inherit_the_currently_selected_song(self):
        session = {
            "active_song_title": "Blues in F minor",
            "song": "Blues in F minor",
            "active_catalog_pick_key": "catalog::blues-f-minor",
        }
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        self.assertEqual(session[ANALYSIS_SONG_SOURCE_NAME_KEY], "Say")
        self.assertTrue(session[ANALYSIS_IDENTITY_LOCKED_KEY])

        # Active-song seeding runs on every Upload render; the lock must hold.
        seed_session_setup_from_active(session)
        self.assertEqual(session[ANALYSIS_SONG_SOURCE_NAME_KEY], "Say")

    def test_recording_time_level_transfers(self):
        session = {"level": "Advanced"}
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        self.assertEqual(session[ANALYSIS_PLAYER_LEVEL_KEY], "Intermediate")

    def test_recorded_instruments_become_the_evaluated_instruments(self):
        session = {}
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        self.assertEqual(
            session[ANALYSIS_EVAL_INSTRUMENTS_KEY], ["Alto saxophone (Eb)", "Piano"]
        )
        self.assertEqual(session[ANALYSIS_TARGET_LAYER_KEY], "Alto saxophone (Eb)")

    def test_each_instrument_gets_its_own_editable_practice_focus(self):
        session = {}
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        focuses = session[ANALYSIS_INSTRUMENT_FOCUSES_KEY]
        self.assertEqual(set(focuses), {"Alto saxophone (Eb)", "Piano"})
        for inst, value in focuses.items():
            # Each instrument has its own widget state, so each control edits alone.
            self.assertEqual(session[instrument_focus_widget_key(inst)], value)

        # Editing one instrument's focus must not disturb the other's.
        session[instrument_focus_widget_key("Piano")] = ["Harmony"]
        self.assertNotEqual(
            session[instrument_focus_widget_key("Piano")],
            session[instrument_focus_widget_key("Alto saxophone (Eb)")],
        )

    def test_creative_mission_context_is_removed(self):
        session = {
            ANALYSIS_MISSION_CONSTRAINT_KEY: "Blues phrasing mission",
            "analysis_sync_creative_mission": True,
            "improv_active_mission": "Blues phrasing mission",
        }
        apply_identity_to_upload_analysis(session, upload_analysis_identity(_export_row()))
        self.assertEqual(session[ANALYSIS_MISSION_CONSTRAINT_KEY], "")
        self.assertFalse(session["analysis_sync_creative_mission"])
        self.assertNotEqual(session["analysis_recording_type"], "Mission Recording")

    def test_recording_workspace_ownership_is_preserved(self):
        identity = upload_analysis_identity(_export_row(workspace_id="studio-b"))
        self.assertEqual(identity["workspace_id"], "studio-b")
        self.assertEqual(identity["export_id"], "exp-say-001")


class LegacyMetadataSafety(unittest.TestCase):
    def test_legacy_row_keeps_its_own_song_and_reports_what_is_missing(self):
        row = _export_row()
        row.pop(EXPORT_RECORDING_IDENTITY_FIELD)
        identity = upload_analysis_identity(row)
        self.assertTrue(identity["legacy_metadata"])
        self.assertEqual(identity["song_source_name"], "Say")
        self.assertFalse(identity["recording_key_known"])
        self.assertFalse(identity["song_source_type_known"])

        gaps = identity_gaps(identity)
        self.assertIn("the Concert Key it was recorded in", gaps)
        self.assertIn("which song library it came from", gaps)

    def test_legacy_row_does_not_invent_a_concert_key(self):
        row = _export_row()
        row.pop(EXPORT_RECORDING_IDENTITY_FIELD)
        session = {"concert_key": "Fm"}
        apply_identity_to_upload_analysis(session, upload_analysis_identity(row))
        # No key claim at all is better than claiming today's sidebar key.
        self.assertNotIn(ANALYSIS_RECORDING_CONCERT_KEY_KEY, session)

    def test_empty_and_malformed_rows_do_not_raise(self):
        for row in ({}, None, {"included_tracks": "not-a-list"}, {"recording_identity": 7}):
            self.assertIsInstance(upload_analysis_identity(row), dict)
            self.assertIsInstance(export_stem_info(row), dict)
            self.assertIsInstance(recorded_instruments_from_export(row), list)


class HandoffEntryPoint(unittest.TestCase):
    """The real entry point used by Send to Upload Analysis and by audio reload."""

    def _send(self, row, session=None):
        from media_multitrack_export_catalog import (
            _compact_export_handoff_meta,
            replace_upload_analysis_with_multitrack_export,
        )

        session = session if session is not None else {}
        meta = _compact_export_handoff_meta({**row, "song_title": row.get("song")})
        ok, err = replace_upload_analysis_with_multitrack_export(
            session, meta, audio=b"RIFF0000WAVEfmt ", keep_pending=False
        )
        self.assertTrue(ok, err)
        return session, meta

    def test_compact_meta_carries_the_recording_identity(self):
        _session, meta = self._send(_export_row())
        self.assertEqual(meta["recording_identity"]["recording_concert_key"], "Em")
        self.assertEqual(meta["workspace_id"], "daniel")

    def test_send_seeds_workflow_song_key_level_and_instruments(self):
        session, _meta = self._send(
            _export_row(), session={"active_song_title": "Blues in F minor", "level": "Advanced"}
        )
        self.assertEqual(session["analysis_mode"], MULTITRACK_RECORDING)
        self.assertEqual(session["analysis_recording_type"], RECORDING_TYPE_MT_MIX)
        self.assertEqual(session[ANALYSIS_SONG_SOURCE_NAME_KEY], "Say")
        self.assertEqual(session[ANALYSIS_PLAYER_LEVEL_KEY], "Intermediate")
        self.assertEqual(
            session[ANALYSIS_EVAL_INSTRUMENTS_KEY], ["Alto saxophone (Eb)", "Piano"]
        )
        self.assertIn("E", str(session[ANALYSIS_RECORDING_CONCERT_KEY_KEY]))

    def test_send_records_the_stem_limitation_for_the_coach(self):
        session, _meta = self._send(_export_row())
        stems = session["analysis_multitrack_stems"]
        self.assertFalse(stems["has_isolated_stems"])
        self.assertEqual(stems["uploaded_track_count"], 1)

    def test_audio_is_handed_over_byte_for_byte(self):
        session, _meta = self._send(_export_row())
        self.assertEqual(bytes(session["last_analysis_audio"]), b"RIFF0000WAVEfmt ")
        self.assertEqual(
            bytes(session["_analysis_prepared_upload"].getvalue()), b"RIFF0000WAVEfmt "
        )


class UnknownsAreNotInvented(unittest.TestCase):
    def test_a_session_with_no_song_records_no_concert_key(self):
        # The key resolver answers "C" for a songless session. That default must not be
        # saved as the key the musician played in.
        identity = freeze_recording_identity({"instrument": "Flute"})
        self.assertEqual(identity["recording_concert_key"], "")

    def test_an_explicit_session_key_is_still_used(self):
        identity = freeze_recording_identity({"instrument": "Flute", "practice_key": "Em"})
        self.assertEqual(identity["recording_concert_key"], "Em")


class ExportRowPersistence(unittest.TestCase):
    def test_migration_preserves_the_recording_identity(self):
        migrated = migrate_multitrack_export(_export_row())
        identity = migrated.get(EXPORT_RECORDING_IDENTITY_FIELD)
        self.assertIsInstance(identity, dict)
        self.assertEqual(identity.get("recording_concert_key"), "Em")
        self.assertEqual(identity.get("level"), "Intermediate")

    def test_migration_preserves_per_layer_instruments(self):
        migrated = migrate_multitrack_export(_export_row())
        slots = {t.get("slot"): t.get("instrument") for t in migrated["included_tracks"]}
        self.assertEqual(slots.get("Sax / winds"), "Alto saxophone (Eb)")

    def test_migration_of_a_legacy_row_yields_an_empty_identity_not_a_crash(self):
        row = _export_row()
        row.pop(EXPORT_RECORDING_IDENTITY_FIELD)
        migrated = migrate_multitrack_export(row)
        self.assertEqual(migrated.get(EXPORT_RECORDING_IDENTITY_FIELD), {})


if __name__ == "__main__":
    unittest.main()

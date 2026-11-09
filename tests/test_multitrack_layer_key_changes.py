"""Issue 62 §3 — the musician changes Practice Key between layers.

The reported case: alto saxophone recorded in E minor, Practice Key moved to G minor,
guitar recorded afterwards. A recorded layer is audio — it does not transpose with the
sidebar — so that project genuinely contains two keys. The rule these tests pin is that
such a mix is never labelled with either key.
"""

from __future__ import annotations

import unittest

from multitrack_recording_identity import (
    EXPORT_RECORDING_IDENTITY_FIELD,
    MT_LAYER_RECORDING_KEYS_KEY,
    apply_identity_to_upload_analysis,
    identity_gaps,
    key_conflict_warning,
    layer_recording_keys,
    note_layer_recorded,
    recording_identity_for_export,
    upload_analysis_identity,
)
from recording_analysis_context import (
    ANALYSIS_RECORDING_CONCERT_KEY_KEY,
    RECORDING_CONCERT_KEY_UNSPECIFIED,
    RECORDING_TYPE_MT_MIX,
)

ALTO = "Sax / winds"
GUITAR = "Guitar"


def _record(session, slot, key, audio=b"RIFF"):
    session.setdefault("mt_tracks", {})[slot] = audio
    note_layer_recorded(session, slot, concert_key=key)
    return session


def _mixed_key_session():
    """Alto in E minor, then the Practice Key moves to G minor, then guitar."""
    session = {
        "practice_key": "Em",
        "instrument": "Alto saxophone (Eb)",
        "level": "Intermediate",
        "mt_tracks": {},
        "mt_layer_instrument_Sax / winds": "Alto saxophone (Eb)",
    }
    _record(session, ALTO, "Em")
    session["practice_key"] = "Gm"  # the musician moves the sidebar
    _record(session, GUITAR, "Gm")
    return session


def _export_row(identity):
    return {
        "export_id": "exp-mixed-key",
        "export_name": "Two key mix",
        "song": "Say",
        "workspace_id": "daniel",
        "included_tracks": [{"slot": ALTO, "name": "Alto"}, {"slot": GUITAR, "name": "Gtr"}],
        EXPORT_RECORDING_IDENTITY_FIELD: identity,
    }


class PerLayerKeyIsStored(unittest.TestCase):
    def test_each_layer_keeps_the_key_it_was_played_in(self):
        session = _mixed_key_session()
        self.assertEqual(
            session[MT_LAYER_RECORDING_KEYS_KEY], {ALTO: "Em", GUITAR: "Gm"}
        )

    def test_a_later_sidebar_change_does_not_rewrite_a_recorded_layer(self):
        session = _mixed_key_session()
        session["practice_key"] = "Bbm"  # moved again, nothing recorded after
        self.assertEqual(layer_recording_keys(session)[ALTO], "Em")
        self.assertEqual(layer_recording_keys(session)[GUITAR], "Gm")

    def test_re_recording_a_slot_restamps_it(self):
        session = _mixed_key_session()
        _record(session, GUITAR, "Em", audio=b"RIFF-take2")
        self.assertEqual(layer_recording_keys(session)[GUITAR], "Em")
        identity = recording_identity_for_export(session)
        # Both layers now agree, so the project has one key again.
        self.assertFalse(identity["mixed_recording_keys"])
        self.assertEqual(identity["recording_concert_key"], "Em")

    def test_a_slot_with_no_audio_contributes_no_key(self):
        session = {"practice_key": "Em", "mt_tracks": {}}
        _record(session, GUITAR, "Em")
        self.assertNotIn(ALTO, layer_recording_keys(session))


class MixedKeyIsNeverMislabelled(unittest.TestCase):
    def test_the_export_claims_no_single_recording_key(self):
        identity = recording_identity_for_export(_mixed_key_session())
        self.assertTrue(identity["mixed_recording_keys"])
        self.assertEqual(identity["recording_concert_key"], "")
        self.assertEqual(sorted(identity["recording_keys"]), ["Em", "Gm"])

    def test_it_is_not_silently_labelled_e_minor(self):
        """The exact thing to avoid: first-layer key standing in for the whole mix."""
        identity = recording_identity_for_export(_mixed_key_session())
        self.assertNotEqual(identity["recording_concert_key"], "Em")
        upload = upload_analysis_identity(_export_row(identity))
        self.assertFalse(upload["recording_key_known"])
        self.assertEqual(upload["recording_concert_key"], "")
        self.assertEqual(upload["recording_concert_key_label"], "")

    def test_both_keys_are_named_in_the_explanation(self):
        upload = upload_analysis_identity(_export_row(recording_identity_for_export(_mixed_key_session())))
        note = upload["key_conflict_note"]
        self.assertIn("E minor", note)
        self.assertIn("G minor", note)
        self.assertIn(ALTO, note)
        self.assertIn(GUITAR, note)

    def test_upload_analysis_shows_unspecified_rather_than_a_guess(self):
        session = {"practice_key": "Bbm"}  # today's sidebar must not leak in either
        upload = upload_analysis_identity(_export_row(recording_identity_for_export(_mixed_key_session())))
        apply_identity_to_upload_analysis(session, upload)
        self.assertEqual(
            session[ANALYSIS_RECORDING_CONCERT_KEY_KEY], RECORDING_CONCERT_KEY_UNSPECIFIED
        )
        self.assertIn("different Concert Keys", session["analysis_multitrack_key_conflict"])

    def test_the_conflict_is_reported_as_a_gap_to_resolve(self):
        upload = upload_analysis_identity(_export_row(recording_identity_for_export(_mixed_key_session())))
        self.assertIn(
            "which Concert Key applies, because its layers were recorded in two",
            identity_gaps(upload),
        )

    def test_a_single_key_project_still_names_its_key(self):
        session = {"practice_key": "Em", "mt_tracks": {}}
        _record(session, ALTO, "Em")
        _record(session, GUITAR, "Em")
        upload = upload_analysis_identity(_export_row(recording_identity_for_export(session)))
        self.assertTrue(upload["recording_key_known"])
        self.assertEqual(upload["recording_concert_key"], "Em")
        self.assertEqual(upload["key_conflict_note"], "")
        sess = {}
        apply_identity_to_upload_analysis(sess, upload)
        self.assertIn("E", str(sess[ANALYSIS_RECORDING_CONCERT_KEY_KEY]))
        self.assertNotIn("analysis_multitrack_key_conflict", sess)


class WarnedBeforeTheConflictIsCreated(unittest.TestCase):
    def test_warning_names_the_existing_layer_and_both_keys(self):
        session = {"practice_key": "Em", "mt_tracks": {}}
        _record(session, ALTO, "Em")
        warning = key_conflict_warning(session, "Gm")
        self.assertIn("G minor", warning)
        self.assertIn("E minor", warning)
        self.assertIn(ALTO, warning)
        self.assertIn("do not transpose", warning)

    def test_no_warning_when_the_key_still_matches(self):
        session = {"practice_key": "Em", "mt_tracks": {}}
        _record(session, ALTO, "Em")
        self.assertEqual(key_conflict_warning(session, "Em"), "")

    def test_no_warning_before_the_first_layer(self):
        self.assertEqual(key_conflict_warning({"practice_key": "Em", "mt_tracks": {}}, "Gm"), "")

    def test_recording_is_warned_about_not_blocked(self):
        """The musician keeps control: the layer still records after the warning."""
        session = {"practice_key": "Em", "mt_tracks": {}}
        _record(session, ALTO, "Em")
        self.assertTrue(key_conflict_warning(session, "Gm"))
        _record(session, GUITAR, "Gm")
        self.assertIn(GUITAR, session["mt_tracks"])
        self.assertEqual(len(session["mt_tracks"]), 2)


class LegacyLayersWithoutStamps(unittest.TestCase):
    def test_an_unstamped_layer_is_unknown_not_assumed_to_match(self):
        session = {"practice_key": "Em", "mt_tracks": {ALTO: b"old"}}
        _record(session, GUITAR, "Em")
        keys = layer_recording_keys(session)
        self.assertEqual(keys[ALTO], "")
        self.assertEqual(keys[GUITAR], "Em")

    def test_one_known_key_plus_one_unknown_is_not_a_conflict_claim(self):
        session = {"practice_key": "Em", "mt_tracks": {ALTO: b"old"}}
        _record(session, GUITAR, "Em")
        identity = recording_identity_for_export(session)
        # Only one key is known, so nothing contradicts it; the unknown layer is reported
        # rather than being counted as a second key.
        self.assertFalse(identity["mixed_recording_keys"])
        self.assertEqual(identity["recording_concert_key"], "Em")
        self.assertEqual(identity["layer_recording_keys"][ALTO], "")

    def test_a_wholly_legacy_project_claims_nothing_from_layer_keys(self):
        session = {"practice_key": "Em", "mt_tracks": {ALTO: b"old", GUITAR: b"old"}}
        identity = recording_identity_for_export(session)
        self.assertFalse(identity["mixed_recording_keys"])
        self.assertEqual(identity["recording_keys"], [])


if __name__ == "__main__":
    unittest.main()


class AnalysisSnapshotKeepsTheMetadata(unittest.TestCase):
    """Step 12 of the journey: the saved analysis context must carry the real identity.

    build_analysis_context_snapshot + attach_selected_song_harmony_to_snapshot is the pair
    the Run Analysis path uses, and the snapshot is what a saved analysis reloads from.
    """

    def _snapshot(self, identity, *, sidebar_key="Fm"):
        from media_multitrack_export_catalog import (
            _compact_export_handoff_meta,
            replace_upload_analysis_with_multitrack_export,
        )
        from recording_analysis_context import (
            attach_selected_song_harmony_to_snapshot,
            build_analysis_context_snapshot,
        )

        row = _export_row(identity)
        session = {"practice_key": sidebar_key}
        ok, err = replace_upload_analysis_with_multitrack_export(
            session,
            _compact_export_handoff_meta({**row, "song_title": row.get("song")}),
            audio=b"RIFF0000WAVEfmt ",
        )
        self.assertTrue(ok, err)
        snap = build_analysis_context_snapshot(session)
        return attach_selected_song_harmony_to_snapshot(session, snap), session

    def _single_key_identity(self):
        session = {"practice_key": "Em", "mt_tracks": {}, "level": "Intermediate",
                   "instrument": "Alto saxophone (Eb)",
                   "mt_layer_instrument_Sax / winds": "Alto saxophone (Eb)"}
        _record(session, ALTO, "Em")
        return recording_identity_for_export(session)

    def test_the_snapshot_keeps_the_recorded_key_not_the_sidebar_key(self):
        snap, _ = self._snapshot(self._single_key_identity(), sidebar_key="Fm")
        self.assertEqual(snap["recording_concert_key"], "Em")
        self.assertEqual(snap["recording_concert_key_label"], "E minor")

    def test_the_snapshot_keeps_the_multitrack_workflow_and_type(self):
        snap, _ = self._snapshot(self._single_key_identity())
        self.assertEqual(snap["workflow"], "Multitrack recording")
        self.assertEqual(snap["recording_type"], RECORDING_TYPE_MT_MIX)

    def test_the_snapshot_keeps_level_song_and_per_instrument_focus(self):
        snap, _ = self._snapshot(self._single_key_identity())
        self.assertEqual(snap["level"], "Intermediate")
        self.assertEqual(snap["song_source_name"], "Say")
        self.assertTrue(snap["identity_locked"])
        self.assertIn("Alto saxophone (Eb)", snap["instrument_focuses"])

    def test_the_snapshot_carries_no_mission_context(self):
        snap, _ = self._snapshot(self._single_key_identity())
        self.assertEqual(snap["mission_type"], "")
        self.assertEqual(snap["mission_constraint"], "")

    def test_a_mixed_key_take_is_saved_as_unspecified_not_as_one_key(self):
        snap, session = self._snapshot(recording_identity_for_export(_mixed_key_session()))
        self.assertEqual(snap["recording_concert_key"], "")
        self.assertEqual(snap["recording_concert_key_label"], RECORDING_CONCERT_KEY_UNSPECIFIED)
        # And the explanation is available to show beside it.
        self.assertIn("different Concert Keys", session["analysis_multitrack_key_conflict"])

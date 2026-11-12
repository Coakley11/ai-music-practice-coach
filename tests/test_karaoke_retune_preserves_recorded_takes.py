"""Issue 69 Part E: a re-key leaves recorded takes in the keys they were recorded in.

This file exists because of a fair correction. My Part D report argued recording safety
from the fact that a karaoke queue entry carries no recording-identity fields - which
shows the entry cannot *itself* relabel a take, and says nothing about whether a re-key
leaves real saved takes alone. Absence of a field is not preservation of data.

So these tests put actual takes in front of a re-key: multitrack project rows carrying
``recording_concert_key`` per layer, a frozen session recording identity, per-layer
stamps, layer audio, and the media-catalog cache - then re-key and read them back
through the code that owns them.
"""

from __future__ import annotations

import copy
import unittest

import karaoke_mode as km
from multitrack_recording_identity import (
    MT_LAYER_RECORDING_KEYS_KEY,
    MT_RECORDING_IDENTITY_KEY,
    layer_recording_keys,
)
from multitrack_slots import MULTITRACK_SLOTS

SAX = MULTITRACK_SLOTS[4]
GUITAR = MULTITRACK_SLOTS[0]
WAV = b"RIFF" + bytes(4096)

#: Two saved projects for one song, recorded in different keys - the Issue 64 shape.
SAVED_ROWS = [
    {
        "multitrack_id": "mt-bb",
        "title": "Say — 1 layer(s)",
        "practice_concert_key": "Bb",
        "activity_source_context": {"source_type": "catalog",
                                    "source_id": "Pop\u001fSay — John Mayer"},
        "recording_identity": {"recording_concert_key": "Bb",
                               "slot_instruments": {SAX: "Alto saxophone (Eb)"}},
        "tracks": [{"slot": SAX, "instrument": "Alto saxophone (Eb)",
                    "recording_concert_key": "Bb", "recording_source_type": "catalog"}],
    },
    {
        "multitrack_id": "mt-em",
        "title": "Say — 2 layer(s)",
        "practice_concert_key": "Em",
        "activity_source_context": {"source_type": "catalog",
                                    "source_id": "Pop\u001fSay — John Mayer"},
        "recording_identity": {"recording_concert_key": "Em"},
        "tracks": [
            {"slot": GUITAR, "instrument": "Guitar", "recording_concert_key": "Em"},
            {"slot": SAX, "instrument": "Alto saxophone (Eb)",
             "recording_concert_key": "Bb"},
        ],
    },
]


def performing_session(entry_key="C"):
    """A live karaoke performance with real recorded work in the session."""
    state: dict = {}
    state[km.KARAOKE_QUEUE_KEY] = [{
        "entry_id": "e1",
        "pick_key": "Pop\u001fSay — John Mayer",
        "title": "Say",
        "artist": "John Mayer",
        "practice_key": entry_key,
        "play_count": 1,
    }]
    state[km.KARAOKE_SESSION_ACTIVE_KEY] = True
    state[km.KARAOKE_SESSION_INDEX_KEY] = 0
    state["instrument"] = "Voice"

    # Work that exists independently of the performance.
    state["mt_tracks"] = {SAX: WAV, GUITAR: WAV}
    state["mt_track_filenames"] = {SAX: "sax.wav", GUITAR: "guitar.wav"}
    state[MT_LAYER_RECORDING_KEYS_KEY] = {SAX: "Bb", GUITAR: "Em"}
    state[MT_RECORDING_IDENTITY_KEY] = {"recording_concert_key": "Bb",
                                        "level": "Intermediate"}
    state["multitrack_catalog_active_id"] = "mt-bb"
    state["_media_catalog_cache"] = {"multitrack_sessions": copy.deepcopy(SAVED_ROWS)}
    state["mixed_track_wav"] = b"RIFF" + bytes(2048)
    return state


class SavedProjectRowsKeepTheirRecordedKeys(unittest.TestCase):
    def setUp(self):
        self.state = performing_session("C")
        self.before = copy.deepcopy(self.state["_media_catalog_cache"])
        self.result = km.retune_now_singing_entry(self.state, "D")
        self.assertTrue(self.result["changed"], "the retune must have happened")

    def test_the_catalog_rows_are_byte_identical_afterwards(self):
        self.assertEqual(self.state["_media_catalog_cache"], self.before)

    def test_each_layer_keeps_the_key_it_was_recorded_in(self):
        rows = {r["multitrack_id"]: r for r in
                self.state["_media_catalog_cache"]["multitrack_sessions"]}
        bb = rows["mt-bb"]["tracks"][0]
        self.assertEqual(bb["recording_concert_key"], "Bb")
        mixed = {t["slot"]: t["recording_concert_key"]
                 for t in rows["mt-em"]["tracks"]}
        self.assertEqual(mixed, {GUITAR: "Em", SAX: "Bb"})

    def test_a_mixed_key_project_is_still_read_as_mixed(self):
        """Read back through the code that owns it, not by inspecting the dict."""
        from multitrack_project_discovery import KEY_STATUS_MIXED, project_key_status

        rows = {r["multitrack_id"]: r for r in
                self.state["_media_catalog_cache"]["multitrack_sessions"]}
        status, keys = project_key_status(rows["mt-em"])
        self.assertEqual(status, KEY_STATUS_MIXED)
        self.assertEqual(keys, ["Bb", "Em"])

    def test_the_single_key_project_still_reads_as_b_flat(self):
        from multitrack_project_discovery import project_key_label

        rows = {r["multitrack_id"]: r for r in
                self.state["_media_catalog_cache"]["multitrack_sessions"]}
        self.assertEqual(project_key_label(rows["mt-bb"]), "Bb")

    def test_the_saved_projects_own_practice_key_is_untouched(self):
        rows = {r["multitrack_id"]: r for r in
                self.state["_media_catalog_cache"]["multitrack_sessions"]}
        self.assertEqual(rows["mt-bb"]["practice_concert_key"], "Bb")
        self.assertEqual(rows["mt-em"]["practice_concert_key"], "Em")


class LiveRecordedWorkIsNotTouched(unittest.TestCase):
    def setUp(self):
        self.state = performing_session("C")
        km.retune_now_singing_entry(self.state, "D")

    def test_the_per_layer_recorded_keys_survive(self):
        """Read through layer_recording_keys, the accessor the save path uses."""
        self.assertEqual(layer_recording_keys(self.state),
                         {SAX: "Bb", GUITAR: "Em"})

    def test_the_frozen_recording_identity_survives(self):
        self.assertEqual(self.state[MT_RECORDING_IDENTITY_KEY]["recording_concert_key"],
                         "Bb")

    def test_the_layer_audio_survives(self):
        self.assertEqual(self.state["mt_tracks"], {SAX: WAV, GUITAR: WAV})
        self.assertEqual(self.state["mixed_track_wav"], b"RIFF" + bytes(2048))

    def test_the_open_project_is_still_the_open_project(self):
        self.assertEqual(self.state["multitrack_catalog_active_id"], "mt-bb")

    def test_the_filenames_survive(self):
        self.assertEqual(self.state["mt_track_filenames"],
                         {SAX: "sax.wav", GUITAR: "guitar.wav"})

    def test_a_retune_does_not_make_the_project_look_unsaved(self):
        """Otherwise reopening Multitrack would warn about losing work it still has."""
        from multitrack_work_state import mark_project_saved, work_is_at_risk

        state = performing_session("C")
        mark_project_saved(state)
        self.assertFalse(work_is_at_risk(state))
        km.retune_now_singing_entry(state, "D")
        self.assertFalse(work_is_at_risk(state),
                         "a key change must not register as an unsaved edit")


class RepeatedAndRolledBackRetunesAreAlsoSafe(unittest.TestCase):
    def test_several_key_changes_in_a_row_leave_takes_alone(self):
        state = performing_session("C")
        before = copy.deepcopy(state["_media_catalog_cache"])
        for key in ("D", "E", "F", "Bb", "C", "D"):
            km.retune_now_singing_entry(state, key)
        self.assertEqual(km.current_session_practice_key(state), "D")
        self.assertEqual(state["_media_catalog_cache"], before)
        self.assertEqual(layer_recording_keys(state), {SAX: "Bb", GUITAR: "Em"})

    def test_a_rollback_leaves_takes_alone_too(self):
        state = performing_session("C")
        before = copy.deepcopy(state["_media_catalog_cache"])
        km.retune_now_singing_entry(state, "D")
        km.rollback_now_singing_retune(state)
        self.assertEqual(km.current_session_practice_key(state), "C")
        self.assertEqual(state["_media_catalog_cache"], before)
        self.assertEqual(layer_recording_keys(state), {SAX: "Bb", GUITAR: "Em"})


class TheCatalogOriginalKeyIsNotTheseKeys(unittest.TestCase):
    """Issue 74 is a separate report; this only shows a retune is not its cause."""

    def test_a_retune_writes_nothing_to_the_curated_catalog(self):
        from song_catalog import curated_songs

        import pathlib

        path = pathlib.Path(curated_songs.__file__)
        before = path.read_bytes()
        state = performing_session("C")
        km.retune_now_singing_entry(state, "D")
        self.assertEqual(path.read_bytes(), before,
                         "the curated catalog file must never be written by a retune")

    def test_a_retune_touches_no_original_key_field(self):
        state = performing_session("C")
        state["original_key"] = "Bb"
        state["selected_song"] = {"key": "Bb", "title": "Say"}
        km.retune_now_singing_entry(state, "D")
        self.assertEqual(state["original_key"], "Bb")
        self.assertEqual(state["selected_song"]["key"], "Bb")


if __name__ == "__main__":
    unittest.main()

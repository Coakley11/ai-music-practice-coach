"""A renamed Multitrack layer keeps its name when the session is rehydrated elsewhere.

A layer recorded and renamed on one device arrived on the next one with its audio intact but its
generic slot label back ("Extra layer"): the audio travels in the persisted blob while the name lives
in the multitrack page snapshot, and only the audio was being applied on restore.

These tests use the real save/restore functions and model a second device as a FRESH session hydrated
from the payload the first one produced. They prove the data survives a round trip - they do not prove
that cloud delivery between two physical devices works.
"""
import copy
import unittest

from multitrack_mixer_state import (
    commit_all_multitrack_mixer_widgets,
    prepare_multitrack_mixer_widgets,
    resolve_slot_control,
)
from multitrack_session_persistence import (
    encode_mt_tracks_for_persist,
    restore_multitrack_layer_names_from_snapshot,
    restore_multitrack_layers_from_workspace,
)
from multitrack_slots import MULTITRACK_SLOTS
from studio_page_persistence import save_page_snapshot

SLOT = "Extra layer"
AUDIO = b"RIFF....flute-take"


def _device_a(name="Flute", slot=SLOT):
    """A session that recorded into ``slot`` and renamed the layer."""
    s = {
        "studio_page": "multitrack",
        "mt_tracks": {x: (AUDIO if x == slot else None) for x in MULTITRACK_SLOTS},
        "mt_track_filenames": {x: f"{x}.wav" for x in MULTITRACK_SLOTS},
        f"mt_name_{slot}": name,
        f"mt_vol_{slot}": 0.8,
        f"mt_delay_{slot}": 0.25,
    }
    commit_all_multitrack_mixer_widgets(s)
    save_page_snapshot(s, "multitrack")
    return s


def _sync_payload(a):
    """What travels: the page snapshot plus the encoded audio blob."""
    enc, _diag = encode_mt_tracks_for_persist(a["mt_tracks"])
    return copy.deepcopy(a["_studio_page_snapshots"]), copy.deepcopy(enc)


def _device_b(snapshots, blob, **extra):
    s = {"studio_page": "multitrack", "_studio_page_snapshots": snapshots, "_mt_tracks_persist_blob": blob}
    s.update(extra)
    restore_multitrack_layers_from_workspace(s)
    prepare_multitrack_mixer_widgets(s)
    return s


class TestTheNameIsSavedLayerData(unittest.TestCase):
    def test_renaming_writes_the_name_into_the_canonical_layer_control(self):
        a = _device_a()
        self.assertEqual(resolve_slot_control(a, SLOT)["layer_name"], "Flute")

    def test_the_name_travels_in_the_sync_payload(self):
        a = _device_a()
        snapshots, _blob = _sync_payload(a)
        snap = snapshots["multitrack"]
        self.assertEqual(snap.get(f"mt_name_{SLOT}"), "Flute")
        self.assertEqual(snap["mt_track_controls"][SLOT]["layer_name"], "Flute")

    def test_a_layer_with_audio_but_no_live_widget_still_shows_its_saved_name(self):
        a = _device_a()
        s = {
            "mt_tracks": dict(a["mt_tracks"]),
            "mt_track_controls": copy.deepcopy(a["mt_track_controls"]),
        }
        prepare_multitrack_mixer_widgets(s)
        self.assertEqual(s.get(f"mt_name_{SLOT}"), "Flute")


class TestSecondDeviceHydration(unittest.TestCase):
    def test_the_recording_and_the_name_both_arrive(self):
        snapshots, blob = _sync_payload(_device_a())
        b = _device_b(snapshots, blob)
        self.assertEqual(b["mt_tracks"][SLOT], AUDIO)          # the recording is there ...
        self.assertEqual(b.get(f"mt_name_{SLOT}"), "Flute")    # ... and so is the name

    def test_the_mixer_settings_come_with_it(self):
        snapshots, blob = _sync_payload(_device_a())
        b = _device_b(snapshots, blob)
        ctrl = resolve_slot_control(b, SLOT)
        self.assertEqual(ctrl["layer_name"], "Flute")
        self.assertAlmostEqual(float(ctrl["volume"]), 0.8, places=3)
        self.assertAlmostEqual(float(ctrl["delay"]), 0.25, places=3)

    def test_a_rename_in_progress_on_this_device_is_not_clobbered(self):
        snapshots, blob = _sync_payload(_device_a())
        b = _device_b(snapshots, blob, **{f"mt_name_{SLOT}": "Piccolo"})
        self.assertEqual(b.get(f"mt_name_{SLOT}"), "Piccolo")
        self.assertEqual(b["mt_tracks"][SLOT], AUDIO)

    def test_untouched_slots_keep_their_plain_labels(self):
        snapshots, blob = _sync_payload(_device_a())
        b = _device_b(snapshots, blob)
        for slot in MULTITRACK_SLOTS:
            if slot != SLOT:
                self.assertIsNone(b.get(f"mt_name_{slot}"), slot)

    def test_every_slot_round_trips_its_own_name(self):
        for slot in MULTITRACK_SLOTS:
            with self.subTest(slot=slot):
                snapshots, blob = _sync_payload(_device_a(name=f"My {slot}", slot=slot))
                b = _device_b(snapshots, blob)
                self.assertEqual(b.get(f"mt_name_{slot}"), f"My {slot}")
                self.assertEqual(b["mt_tracks"][slot], AUDIO)


class TestRenameDoesNotDisturbTheRecording(unittest.TestCase):
    def test_renaming_again_keeps_the_audio_and_the_slot_identity(self):
        a = _device_a()
        a[f"mt_name_{SLOT}"] = "Alto flute"
        commit_all_multitrack_mixer_widgets(a)
        save_page_snapshot(a, "multitrack")
        self.assertEqual(a["mt_tracks"][SLOT], AUDIO)
        snapshots, blob = _sync_payload(a)
        b = _device_b(snapshots, blob)
        self.assertEqual(b.get(f"mt_name_{SLOT}"), "Alto flute")
        self.assertEqual(b["mt_tracks"][SLOT], AUDIO)
        self.assertIsNone(b["mt_tracks"]["Guitar"])            # identity unchanged: still the same slot


class TestRestoreHelperIsSafe(unittest.TestCase):
    def test_no_snapshot_is_a_no_op(self):
        s = {}
        self.assertEqual(restore_multitrack_layer_names_from_snapshot(s), 0)
        self.assertEqual(s, {})

    def test_a_name_equal_to_the_slot_label_is_not_written_back(self):
        snap = {"multitrack": {f"mt_name_{SLOT}": SLOT}}
        s = {"_studio_page_snapshots": snap}
        self.assertEqual(restore_multitrack_layer_names_from_snapshot(s), 0)
        self.assertNotIn(f"mt_name_{SLOT}", s)


if __name__ == "__main__":
    unittest.main()

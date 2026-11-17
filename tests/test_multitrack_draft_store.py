"""Unsaved and saved Multitrack takes kept as their own files, so a long take survives a session ending.

Measured before this existed: the workspace save drops any layer over 2 MiB - about 12 s of the
recorder's stereo 44.1 kHz audio - so a 30 s take was found nowhere after a refresh, and a 30 s take
that had been SAVED was found nowhere too. These tests pin what the file store has to guarantee:

  * full-length audio round-trips exactly, with its timing, controls and name;
  * a draft is only ever returned to the workspace, song and project it was recorded in;
  * a discarded take never comes back, even from a file that survived the delete;
  * a saved layer keeps its file (deleting it on save would destroy the only copy) and is restored
    as SAVED, while a draft is restored as UNSAVED - never silently promoted;
  * a take still in the live session always wins over a file;
  * an altered file is refused rather than restored as though it were the take;
  * no title or slot text can become a path outside the workspace.
"""

from __future__ import annotations

import atexit
import io
import math
import os
import shutil
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The data dir is resolved when the storage modules load, so it is pointed at a throwaway directory
# BEFORE any app import - otherwise this writes into a real workspace.
_DATA = tempfile.mkdtemp(prefix="mt-draft-store-tests-")
os.environ["MUSIC_APP_DATA_DIR"] = _DATA
atexit.register(lambda: shutil.rmtree(_DATA, ignore_errors=True))

import multitrack_draft_store as store  # noqa: E402
from multitrack_takes import adopt_restored_layers_as_saved, is_take_saved  # noqa: E402


def wav(seconds: float, sr: int = 44100, channels: int = 2, hz: float = 220.0) -> bytes:
    """Shaped like the recorder's takes: 16-bit stereo 44.1 kHz."""
    buf = io.BytesIO()
    frames = bytearray()
    for i in range(int(seconds * sr)):
        v = int(5000 * math.sin(2 * math.pi * hz * i / sr))
        frames += struct.pack("<h", v) * channels
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return buf.getvalue()


SHORT = wav(1.0)


def session(song: str = "Say", project: str = "proj-1", workspace: str = "daniel") -> dict:
    return {
        "_suite_active_workspace_id": workspace,
        "active_catalog_pick_key": f"Pop\x1f{song}",
        "active_song_title": song,
        "multitrack_catalog_active_id": project,
        "mt_tracks": {"Guitar": None, "Sax / winds": None},
        "mt_track_filenames": {"Guitar": "guitar.wav", "Sax / winds": "sax.wav"},
    }


class AFullLengthTakeSurvives(unittest.TestCase):
    def test_a_song_length_take_round_trips_exactly(self) -> None:
        """86 s - the backing length in the reported session - about 15 MB, seven times the cap."""
        take = wav(86.0)
        self.assertGreater(len(take), 7 * 2_097_152)
        live = session()
        self.assertTrue(store.write_draft(live, "Guitar", take)["ok"])
        fresh = session()                       # what a refresh leaves: a new, empty session
        self.assertEqual(store.restore_drafts(fresh, ["Guitar"]), ["Guitar"])
        self.assertEqual(fresh["mt_tracks"]["Guitar"], take, "the exact bytes come back")

    def test_timing_controls_and_name_come_back_with_it(self) -> None:
        live = session()
        live["mt_take_timing"] = {"Guitar": {"zero_frame": 1234, "measured": True}}
        live["mt_delay_Guitar"] = 0.125
        live["mt_vol_Guitar"] = 0.8
        live["mt_name_Guitar"] = "Rhythm guitar"
        store.write_draft(live, "Guitar", SHORT)
        fresh = session()
        store.restore_drafts(fresh, ["Guitar"])
        self.assertEqual(fresh["mt_take_timing"]["Guitar"], {"zero_frame": 1234, "measured": True})
        self.assertEqual(fresh["mt_delay_Guitar"], 0.125, "alignment must survive")
        self.assertEqual(fresh["mt_vol_Guitar"], 0.8)
        self.assertEqual(fresh["mt_name_Guitar"], "Rhythm guitar")


class ADraftBelongsToOneSongProjectAndUser(unittest.TestCase):
    def setUp(self) -> None:
        store.write_draft(session(), "Guitar", SHORT)

    def test_another_song_does_not_receive_it(self) -> None:
        other = session(song="Perfect")
        self.assertEqual(store.restore_drafts(other, ["Guitar"]), [])
        self.assertIsNone(other["mt_tracks"]["Guitar"])

    def test_another_project_for_the_same_song_does_not_receive_it(self) -> None:
        other = session(project="proj-2")
        self.assertEqual(store.restore_drafts(other, ["Guitar"]), [])

    def test_another_workspace_does_not_receive_it(self) -> None:
        other = session(workspace="ariel")
        self.assertEqual(store.restore_drafts(other, ["Guitar"]), [])

    def test_the_owner_still_does(self) -> None:
        self.assertEqual(store.restore_drafts(session(), ["Guitar"]), ["Guitar"])


class DiscardStaysDiscarded(unittest.TestCase):
    def test_a_discarded_take_is_not_restored(self) -> None:
        live = session(project="discard-1")
        store.write_draft(live, "Guitar", SHORT)
        self.assertTrue(store.discard_draft(live, "Guitar"))
        self.assertEqual(store.restore_drafts(session(project="discard-1"), ["Guitar"]), [])

    def test_not_even_from_a_file_that_survived_the_delete(self) -> None:
        """Simulate a delete that failed: put the very same bytes back. The tombstone refuses them."""
        live = session(project="discard-2")
        store.write_draft(live, "Guitar", SHORT)
        meta_before = store.read_draft(live, "Guitar")[1]
        store.discard_draft(live, "Guitar")
        wav_path, meta_path, _tomb = store._paths(live, "Guitar")
        wav_path.write_bytes(SHORT)
        import json
        meta_path.write_text(json.dumps(meta_before), encoding="utf-8")
        raw, _meta, why = store.read_draft(live, "Guitar")
        self.assertIsNone(raw)
        self.assertIn("discarded", why)

    def test_a_new_take_in_that_slot_is_kept(self) -> None:
        """A different recording supersedes the tombstone - it is not the take that was thrown away."""
        live = session(project="discard-3")
        store.write_draft(live, "Guitar", SHORT)
        store.discard_draft(live, "Guitar")
        new = wav(1.5, hz=330.0)
        store.write_draft(live, "Guitar", new)
        fresh = session(project="discard-3")
        self.assertEqual(store.restore_drafts(fresh, ["Guitar"]), ["Guitar"])
        self.assertEqual(fresh["mt_tracks"]["Guitar"], new)

    def test_remove_take_discards_the_file(self) -> None:
        """The app's one removal entry point reaches the file too."""
        from multitrack_take_removal import remove_take

        live = session(project="discard-4")
        live["mt_tracks"]["Guitar"] = SHORT
        store.write_draft(live, "Guitar", SHORT)
        report = remove_take(live, "Guitar", slots=["Guitar", "Sax / winds"])
        self.assertTrue(report.get("removed"))
        self.assertTrue(report.get("draft_discarded"))
        self.assertEqual(store.restore_drafts(session(project="discard-4"), ["Guitar"]), [])


class SavedAndUnsavedStayDistinct(unittest.TestCase):
    def test_a_draft_comes_back_unsaved_and_is_not_adopted_as_saved(self) -> None:
        """adopt_restored_layers_as_saved promotes any audio with no recorded state - after a refresh,
        all of it. restore_drafts must record the state first."""
        store.write_draft(session(project="state-1"), "Guitar", SHORT)
        fresh = session(project="state-1")
        store.restore_drafts(fresh, ["Guitar"])
        adopt_restored_layers_as_saved(fresh, ["Guitar"])
        self.assertFalse(is_take_saved(fresh, "Guitar"), "a draft must never become a saved layer")
        self.assertTrue(store.was_restored(fresh, "Guitar"))

    def test_save_keeps_the_file_and_it_comes_back_saved(self) -> None:
        """Deleting the file on save would destroy the only copy of a long layer."""
        live = session(project="state-2")
        store.write_draft(live, "Guitar", SHORT)
        self.assertTrue(store.mark_draft_saved(live, "Guitar"))
        wav_path = store._paths(live, "Guitar")[0]
        self.assertTrue(wav_path.exists(), "the file must survive Save layer")
        fresh = session(project="state-2")
        store.restore_drafts(fresh, ["Guitar"])
        self.assertTrue(is_take_saved(fresh, "Guitar"))


class FoundOnlyInTheBrowser(unittest.TestCase):
    """Two defects every test above missed, found by the real-browser matrix.

    1. A 30 s and an 86 s take were each WRITTEN to disk and found nowhere after a refresh. The
       draft is keyed to the unsaved project's working token, which was minted per session - so a
       refresh minted a new one, the identity no longer matched, and the file was refused as "a
       different project". Every unit test reused one session dict, so the token never changed.
    2. A short take comes back through the persist blob on its own, before restore_drafts sees it -
       with no record of whether it was saved, so adopt_restored_layers_as_saved promoted it.
    """

    def test_the_working_project_token_survives_a_new_session(self) -> None:
        from music_persistent_state import _PERSIST_KEYS, _device_view_keys

        self.assertIn("_mt_working_project_token", _PERSIST_KEYS,
                      "a refresh must keep the identity a draft is filed under")
        self.assertIn("_mt_working_project_token", _device_view_keys(),
                      "another device's save must not re-key this device's drafts mid-session")

    def test_an_unsaved_project_finds_its_draft_after_a_refresh(self) -> None:
        """The measured case: no library id, only the working token - carried over by the save."""
        live = session(project="")
        live.pop("multitrack_catalog_active_id", None)
        store.write_draft(live, "Guitar", SHORT)
        token = live["_mt_working_project_token"]
        fresh = session(project="")
        fresh.pop("multitrack_catalog_active_id", None)
        fresh["_mt_working_project_token"] = token          # what the persisted state restores
        self.assertEqual(store.restore_drafts(fresh, ["Guitar"]), ["Guitar"])

    def test_without_the_token_the_draft_is_correctly_refused(self) -> None:
        """The isolation check is right; it was handed the wrong identity."""
        live = session(project="")
        live.pop("multitrack_catalog_active_id", None)
        store.write_draft(live, "Guitar", SHORT)
        fresh = session(project="")
        fresh.pop("multitrack_catalog_active_id", None)      # a new session mints a new token
        self.assertEqual(store.restore_drafts(fresh, ["Guitar"]), [])

    def test_a_take_the_blob_restored_keeps_its_unsaved_state(self) -> None:
        store.write_draft(session(project="blob-1"), "Guitar", SHORT)
        fresh = session(project="blob-1")
        fresh["mt_tracks"]["Guitar"] = SHORT                  # the persist blob got there first
        store.restore_drafts(fresh, ["Guitar"])
        adopt_restored_layers_as_saved(fresh, ["Guitar"])
        self.assertFalse(is_take_saved(fresh, "Guitar"),
                         "an unsaved take must not be promoted because the blob restored it")

    def test_a_saved_layer_the_blob_restored_stays_saved(self) -> None:
        live = session(project="blob-2")
        store.write_draft(live, "Guitar", SHORT)
        store.mark_draft_saved(live, "Guitar")
        fresh = session(project="blob-2")
        fresh["mt_tracks"]["Guitar"] = SHORT
        store.restore_drafts(fresh, ["Guitar"])
        self.assertTrue(is_take_saved(fresh, "Guitar"))

    def test_a_state_already_set_this_session_is_not_overridden(self) -> None:
        live = session(project="blob-3")
        store.write_draft(live, "Guitar", SHORT)
        store.mark_draft_saved(live, "Guitar")
        fresh = session(project="blob-3")
        fresh["mt_tracks"]["Guitar"] = SHORT
        fresh["mt_take_saved_Guitar"] = False                 # the musician's state this session
        store.restore_drafts(fresh, ["Guitar"])
        self.assertFalse(is_take_saved(fresh, "Guitar"))

    def test_different_bytes_in_the_slot_are_not_given_the_drafts_state(self) -> None:
        store.write_draft(session(project="blob-4"), "Guitar", SHORT)
        fresh = session(project="blob-4")
        fresh["mt_tracks"]["Guitar"] = wav(0.7, hz=500.0)      # not this draft
        store.restore_drafts(fresh, ["Guitar"])
        self.assertNotIn("mt_take_saved_Guitar", fresh)


class TheLiveSessionWins(unittest.TestCase):
    def test_a_take_still_in_the_session_is_not_replaced(self) -> None:
        store.write_draft(session(project="live-1"), "Guitar", SHORT)
        live = session(project="live-1")
        newer = wav(0.8, hz=440.0)
        live["mt_tracks"]["Guitar"] = newer
        self.assertEqual(store.restore_drafts(live, ["Guitar"]), [])
        self.assertEqual(live["mt_tracks"]["Guitar"], newer)


class IntegrityAndContainment(unittest.TestCase):
    def test_an_altered_file_is_refused(self) -> None:
        live = session(project="integrity-1")
        store.write_draft(live, "Guitar", SHORT)
        wav_path = store._paths(live, "Guitar")[0]
        data = bytearray(wav_path.read_bytes())
        data[-10] ^= 0xFF
        wav_path.write_bytes(bytes(data))
        raw, _meta, why = store.read_draft(live, "Guitar")
        self.assertIsNone(raw)
        self.assertIn("no longer matches", why)

    def test_hostile_slot_and_title_text_stay_inside_the_workspace(self) -> None:
        live = session(song="../../../etc", project="..\\..\\x")
        paths = store._paths(live, "../../escape")
        self.assertIsNotNone(paths, "a safe path must still be produced")
        # The workspace root the APP resolves, not this file's temp dir: in a full-suite run another
        # module can load the storage code first, and a hardcoded root then compares the wrong thing.
        from media_storage import recording_local_abs_path

        root = recording_local_abs_path(store._workspace_id(), "").resolve()
        for p in paths:
            self.assertTrue(str(p.resolve()).startswith(str(root)), f"{p} escaped {root}")
            self.assertNotIn("..", p.name)


if __name__ == "__main__":
    unittest.main()

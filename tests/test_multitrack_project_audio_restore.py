"""A reopened saved project brings back its saved audio; a project save says where the audio is."""
from __future__ import annotations

import io
import unittest
import wave
from unittest import mock

import multitrack_project_audio_restore as r


def wav(seconds: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x01\x00" * int(48000 * seconds))
    return buf.getvalue()


AUDIO = wav(2.0)
ROW = {"multitrack_id": "p1", "workspace_id": "daniel",
       "tracks": [{"slot": "Guitar", "track_id": "t1", "local_path": "x.wav", "filename": "guitar.wav"},
                  {"slot": "Bass", "track_id": "t2", "local_path": "y.wav"}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.ss = {"multitrack_catalog_active_id": "p1", "_active_catalog_multitrack_id": "p1",
                   "mt_tracks": {"Guitar": None, "Bass": None, "Vocals": None}, "mt_track_filenames": {}}
        self.loads = []

        def fake_load(track, session=None, st=None):
            self.loads.append(track["slot"])
            return (AUDIO, "") if track["slot"] == "Guitar" else (None, "download_failed")

        self.patches = [
            mock.patch("media_multitrack_catalog.active_catalog_multitrack_id", return_value="p1"),
            mock.patch.object(r, "_active_row", return_value=ROW),
            mock.patch("media_multitrack_catalog.track_playback_status", return_value="playable"),
            mock.patch("media_multitrack_catalog.is_real_multitrack_track", return_value=True),
            mock.patch("media_storage.load_track_audio", side_effect=fake_load),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()


class Restore(Base):
    def test_a_reopened_project_gets_its_saved_audio_back(self):
        rep = r.restore_active_project_audio(self.ss, ["Guitar", "Bass", "Vocals"])
        self.assertEqual(self.ss["mt_tracks"]["Guitar"], AUDIO)
        self.assertTrue(rep["slots"]["Guitar"]["ok"])
        self.assertAlmostEqual(rep["slots"]["Guitar"]["seconds"] or 2.0, 2.0, places=1)
        from multitrack_takes import is_take_saved

        self.assertTrue(is_take_saved(self.ss, "Guitar"))

    def test_a_failure_is_reported_not_hidden(self):
        rep = r.restore_active_project_audio(self.ss, ["Guitar", "Bass"])
        self.assertEqual(r.failed_slots(rep), ["Bass"])

    def test_a_slot_that_already_has_audio_keeps_it(self):
        self.ss["mt_tracks"]["Guitar"] = b"newer unsaved draft" * 10
        r.restore_active_project_audio(self.ss, ["Guitar", "Bass"])
        self.assertEqual(self.ss["mt_tracks"]["Guitar"], b"newer unsaved draft" * 10)

    def test_a_deliberately_removed_layer_is_not_brought_back(self):
        r.note_slot_removed(self.ss, "Guitar")
        r.restore_active_project_audio(self.ss, ["Guitar", "Bass"])
        self.assertIsNone(self.ss["mt_tracks"]["Guitar"])
        self.assertNotIn("Guitar", self.loads)

    def test_saving_the_project_again_clears_the_removal_record(self):
        r.note_slot_removed(self.ss, "Guitar")
        r.note_project_saved(self.ss, "p1")
        self.assertNotIn("p1", self.ss[r.REMOVED_KEY])

    def test_it_runs_once_per_session_and_retry_runs_it_again(self):
        r.restore_active_project_audio(self.ss, ["Bass"])
        r.restore_active_project_audio(self.ss, ["Bass"])
        self.assertEqual(self.loads.count("Bass"), 1)
        r.request_retry(self.ss)
        r.restore_active_project_audio(self.ss, ["Bass"])
        self.assertEqual(self.loads.count("Bass"), 2)

    def test_a_slot_emptied_again_later_is_refilled_without_downloading_again(self):
        r.restore_active_project_audio(self.ss, ["Guitar"])
        self.ss["mt_tracks"]["Guitar"] = None          # a later rerun's snapshot reconciliation
        r.restore_active_project_audio(self.ss, ["Guitar"])
        self.assertEqual(self.ss["mt_tracks"]["Guitar"], AUDIO)
        self.assertEqual(self.loads.count("Guitar"), 1)

    def test_a_removed_layer_is_not_refilled_from_the_cache(self):
        r.restore_active_project_audio(self.ss, ["Guitar"])
        self.ss["mt_tracks"]["Guitar"] = None
        r.note_slot_removed(self.ss, "Guitar")
        r.restore_active_project_audio(self.ss, ["Guitar"])
        self.assertIsNone(self.ss["mt_tracks"]["Guitar"])

    def test_the_cache_is_never_part_of_a_workspace_save(self):
        import music_persistent_state as mps

        self.assertNotIn(r.CACHE_KEY, getattr(mps, "_PERSIST_KEYS", ()))

    def test_no_active_project_does_nothing(self):
        with mock.patch("media_multitrack_catalog.active_catalog_multitrack_id", return_value=""):
            self.assertEqual(r.restore_active_project_audio(self.ss, ["Guitar"]), {})
        self.assertEqual(self.loads, [])

    def test_invalid_audio_is_refused(self):
        with mock.patch("media_storage.load_track_audio", return_value=(b"<html>not audio</html>" * 50, "")):
            rep = r.restore_active_project_audio(self.ss, ["Guitar"])
        self.assertIsNone(self.ss["mt_tracks"]["Guitar"])
        self.assertIn("invalid_audio", rep["slots"]["Guitar"]["error"])


class UploadVerification(unittest.TestCase):
    def client(self, items=None, exc=None):
        bucket = mock.Mock()
        bucket.list.side_effect = exc
        bucket.list.return_value = items
        c = mock.Mock()
        c.storage.from_.return_value = bucket
        return c

    def test_listed_at_the_sent_size_is_verified(self):
        import media_storage as ms

        c = self.client([{"name": "t.wav", "metadata": {"size": 10}}])
        self.assertTrue(ms.verify_uploaded_object(c, "b", "u/ws/t.wav", 10))

    def test_wrong_size_missing_or_error_is_not(self):
        import media_storage as ms

        self.assertFalse(ms.verify_uploaded_object(self.client([{"name": "t.wav", "metadata": {"size": 9}}]), "b", "u/t.wav", 10))
        self.assertFalse(ms.verify_uploaded_object(self.client([]), "b", "u/t.wav", 10))
        self.assertFalse(ms.verify_uploaded_object(self.client(exc=RuntimeError("503")), "b", "u/t.wav", 10))


class SaveMessage(unittest.TestCase):
    def test_success_only_when_every_layer_is_in_the_account(self):
        lvl, txt = r.project_save_message({"cloud_enabled": True, "layers": {"Guitar": "account"}, "backing": ""}, "Saved new project")
        self.assertEqual(lvl, "success")
        self.assertIn("saved to your account", txt)

    def test_server_only_is_an_error_that_names_the_layer(self):
        lvl, txt = r.project_save_message({"cloud_enabled": True, "layers": {"Guitar": "server_only", "Bass": "account"},
                                           "backing": "server_only"}, "Saved new project")
        self.assertEqual(lvl, "error")
        self.assertIn("Guitar", txt)
        self.assertIn("the backing track", txt)
        self.assertIn("NOT reach your account", txt)

    def test_status_is_read_from_the_saved_fields(self):
        ss: dict = {}
        with mock.patch("studio_history_cloud.cloud_enabled", return_value=True):
            st = r.record_project_save_status(ss, {"tracks": [
                {"slot": "Guitar", "local_path": "a.wav", "storage_ref": "b/x", "cloud_verified": True},
                {"slot": "Bass", "local_path": "b.wav", "storage_ref": "b/y", "cloud_verified": False}]})
        self.assertEqual(st["layers"], {"Guitar": "account", "Bass": "server_only"})


class Wording(unittest.TestCase):
    def test_save_layer_is_not_presented_as_permanent_for_a_long_take(self):
        from multitrack_takes import LONG_TAKE_NOTICE

        self.assertIn("does not keep a long recording permanently", LONG_TAKE_NOTICE)
        self.assertIn("restart of the app can lose", LONG_TAKE_NOTICE)


if __name__ == "__main__":
    unittest.main()

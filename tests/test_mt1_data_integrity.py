"""MT-1 - Multitrack data integrity (2026-11-27).

Three defects measured on Dev db317f3f, each with the behaviour that must hold instead:

1. A take held by the upload widget (or the fallback recorder) landed again on every rerun, so a newer
   microphone take was overwritten by the older upload one rerun after it arrived; Save layer also took
   the widget's file first.
2. Save layer printed "<layer> saved." whatever happened, and never said the take is kept on the app's
   server only (not in the account).
3. Save Export said "Export saved to your Export Library." with no stored audio, hid a failed account
   upload, and never checked the uploaded size.

Synthetic data only: temp directories, fake storage clients, no network, no real recordings.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

os.environ.setdefault("SUITE_AUTH_ENABLED", "0")

SAX = "Sax / winds"
GTR = "Guitar"


def _wav(seconds: float = 0.5, sr: int = 8000, level: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(int(level).to_bytes(2, "little", signed=True) * int(sr * seconds))
    return buf.getvalue()


class _Upload(io.BytesIO):
    """Stands in for Streamlit's UploadedFile: bytes plus the per-upload ``file_id`` Streamlit gives it."""

    def __init__(self, data: bytes, name: str, file_id: str):
        super().__init__(data)
        self.name = name
        self.file_id = file_id
        self.size = len(data)


# --------------------------------------------------------------------------------------- 1. landing
class TakeLandingTests(unittest.TestCase):
    """Which take becomes the layer's audio on a run - decided by input EVENTS, not by what a widget holds."""

    def setUp(self):
        self.ss: dict = {"mt_tracks": {SAX: None, GTR: None}, "mt_track_filenames": {}}
        self.x = _Upload(_wav(level=3), "old-take.wav", "fid-x")

    def _land(self, slot=SAX, **inputs):
        from multitrack_takes import choose_landed_take, consume_landed_take

        choice = choose_landed_take(self.ss, slot, **inputs)
        if choice is not None:
            consume_landed_take(self.ss, slot, choice)
            self.ss["mt_tracks"][slot] = choice["bytes"]
        return choice

    def test_an_upload_lands_once(self):
        c = self._land(uploaded=self.x)
        self.assertEqual(c["source"], "upload")
        self.assertEqual(c["bytes"], self.x.getvalue())
        self.assertIsNone(self._land(uploaded=self.x), "the same upload event must not land again")

    def test_a_newer_microphone_take_is_never_replaced_by_the_held_upload(self):
        self._land(uploaded=self.x)
        live = {"take_id": "t1", "wav": _wav(level=9)}
        c = self._land(uploaded=self.x, live_take=live)
        self.assertEqual(c["source"], "shared-clock")
        # Every later rerun: the recorder hands the take back only once, the uploader keeps its file.
        for _ in range(25):
            self.assertIsNone(self._land(uploaded=self.x))
        self.assertEqual(self.ss["mt_tracks"][SAX], live["wav"])

    def test_a_deliberate_new_upload_after_the_take_still_replaces_it(self):
        self._land(uploaded=self.x)
        self._land(uploaded=self.x, live_take={"take_id": "t1", "wav": _wav(level=9)})
        z = _Upload(_wav(level=5), "new-take.wav", "fid-z")
        c = self._land(uploaded=z)
        self.assertEqual(c["bytes"], z.getvalue())
        self.assertEqual(self.ss["mt_tracks"][SAX], z.getvalue())

    def test_uploading_the_same_file_again_on_purpose_is_a_new_event(self):
        self._land(uploaded=self.x)
        self._land(live_take={"take_id": "t1", "wav": _wav(level=9)}, uploaded=self.x)
        again = _Upload(self.x.getvalue(), self.x.name, "fid-x-again")   # removed and re-added: new file_id
        c = self._land(uploaded=again)
        self.assertIsNotNone(c)
        self.assertEqual(self.ss["mt_tracks"][SAX], self.x.getvalue())

    def test_the_fallback_recorder_follows_the_same_rule(self):
        rec = _Upload(_wav(level=4), "audio.wav", "rec-1")
        self.assertEqual(self._land(recorded=rec)["source"], "basic-recorder")
        live = {"take_id": "t2", "wav": _wav(level=8)}
        self._land(recorded=rec, live_take=live)
        for _ in range(10):
            self.assertIsNone(self._land(recorded=rec))
        self.assertEqual(self.ss["mt_tracks"][SAX], live["wav"])

    def test_a_rejected_input_is_not_swallowed(self):
        from multitrack_takes import choose_landed_take

        first = choose_landed_take(self.ss, SAX, uploaded=self.x)     # caller rejects it: no consume
        again = choose_landed_take(self.ss, SAX, uploaded=self.x)
        self.assertIsNotNone(first)
        self.assertIsNotNone(again, "an input that was never adopted is still the musician's latest action")

    def test_one_layer_cannot_land_on_another(self):
        self._land(slot=SAX, uploaded=self.x)
        self._land(slot=SAX, live_take={"take_id": "t1", "wav": _wav(level=9)}, uploaded=self.x)
        g = _Upload(_wav(level=2), "gtr.wav", "fid-g")
        self._land(slot=GTR, uploaded=g)
        for _ in range(5):
            self.assertIsNone(self._land(slot=SAX, uploaded=self.x))
            self.assertIsNone(self._land(slot=GTR, uploaded=g))
        self.assertEqual(self.ss["mt_tracks"][GTR], g.getvalue())
        self.assertNotEqual(self.ss["mt_tracks"][SAX], g.getvalue())

    def test_an_input_without_a_file_id_is_identified_by_its_content(self):
        from multitrack_takes import input_event_id

        a = io.BytesIO(_wav(level=1)); a.name = "a.wav"
        b = io.BytesIO(_wav(level=2)); b.name = "a.wav"
        self.assertTrue(input_event_id(a))
        self.assertNotEqual(input_event_id(a), input_event_id(b))


# ------------------------------------------------------------------------------------- 2. Save layer
class SaveLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)

        def paths(session, slot, *, st=None):
            stem = hashlib.sha256(str(slot).encode()).hexdigest()[:12]
            return root / f"{stem}.wav", root / f"{stem}.json", root / f"{stem}.tombstone"

        self.patches = [mock.patch("multitrack_draft_store._paths", paths),
                        mock.patch("multitrack_draft_store._sweep_old_drafts", lambda **k: None)]
        for p in self.patches:
            p.start()
        self.ss: dict = {"mt_tracks": {SAX: _wav(level=7), GTR: _wav(level=2)}, "mt_track_filenames": {}}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_save_layer_keeps_the_current_take_and_confirms_it_reads_back(self):
        from multitrack_draft_store import read_draft
        from multitrack_takes import is_take_saved, save_layer_take

        r = save_layer_take(self.ss, SAX)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["where"], "server_only")
        raw, meta, why = read_draft(self.ss, SAX)
        self.assertEqual(raw, self.ss["mt_tracks"][SAX], why)
        self.assertTrue(meta.get("saved"))
        self.assertTrue(is_take_saved(self.ss, SAX))

    def test_save_layer_replaces_an_older_draft_with_the_current_take(self):
        from multitrack_draft_store import read_draft, write_draft
        from multitrack_takes import save_layer_take

        write_draft(self.ss, SAX, _wav(level=1))           # an older take's draft
        self.assertTrue(save_layer_take(self.ss, SAX)["ok"])
        self.assertEqual(read_draft(self.ss, SAX)[0], self.ss["mt_tracks"][SAX])

    def test_a_failed_save_keeps_the_take_and_says_so(self):
        from multitrack_takes import is_take_saved, layer_save_message, save_layer_take

        before = self.ss["mt_tracks"][SAX]
        with mock.patch("multitrack_draft_store._paths", lambda *a, **k: None):
            r = save_layer_take(self.ss, SAX)
        self.assertFalse(r["ok"])
        self.assertEqual(self.ss["mt_tracks"][SAX], before, "a failed save must not touch the take")
        self.assertFalse(is_take_saved(self.ss, SAX))
        level, text = layer_save_message(r, "Alto sax")
        self.assertEqual(level, "error")
        self.assertIn("still", text.lower())
        self.assertNotIn("saved.", text)

    def test_nothing_to_save_is_not_a_success(self):
        from multitrack_takes import layer_save_message, save_layer_take

        self.ss["mt_tracks"][SAX] = None
        r = save_layer_take(self.ss, SAX)
        self.assertFalse(r["ok"])
        self.assertNotEqual(layer_save_message(r, "Alto sax")[0], "success")

    def test_the_message_never_claims_the_account(self):
        from multitrack_takes import layer_save_message, save_layer_take

        level, text = layer_save_message(save_layer_take(self.ss, SAX), "Alto sax")
        self.assertEqual(level, "warning")
        low = text.lower()
        self.assertIn("server", low)
        self.assertIn("restart", low)
        self.assertIn("not in your account", low)

    def test_saving_one_layer_leaves_the_others_alone(self):
        from multitrack_takes import is_take_saved, save_layer_take

        g = self.ss["mt_tracks"][GTR]
        save_layer_take(self.ss, SAX)
        self.assertEqual(self.ss["mt_tracks"][GTR], g)
        self.assertFalse(is_take_saved(self.ss, GTR))

    def test_repeated_save_layer_clicks_stay_one_kept_copy(self):
        from multitrack_draft_store import read_draft
        from multitrack_takes import save_layer_take

        for _ in range(3):
            self.assertTrue(save_layer_take(self.ss, SAX)["ok"])
        self.assertEqual(read_draft(self.ss, SAX)[0], self.ss["mt_tracks"][SAX])
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.wav"))), 1)


# ------------------------------------------------------------------------------------ 3. Save Export
def _fake_catalog_env(tmp: str):
    path = Path(tmp) / "media_catalog.json"
    ws_dir = Path(tmp) / "daniel"
    return path, [
        mock.patch("media_persistence._local_path", lambda *a, **k: path),
        mock.patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"),
        mock.patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)),
        mock.patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")),
        mock.patch("media_storage._resolve_workspace_id", lambda *, st=None: "daniel"),
        mock.patch("media_storage.recording_local_abs_path", lambda ws, rel: ws_dir / rel),
        mock.patch("multitrack_activity.report_export_saved"),
    ]


def _live_rows(path: Path) -> list:
    if not path.exists():
        return []
    return [r for r in json.loads(path.read_text(encoding="utf-8")).get("multitrack_exports") or []
            if not r.get("deleted")]


class SaveExportTests(unittest.TestCase):
    def _save(self, audio: bytes, *, cloud=("", "cloud_disabled"), local_ok=True, session=None):
        import media_multitrack_export_catalog as M

        ss = session if session is not None else {}
        with tempfile.TemporaryDirectory() as tmp:
            path, patches = _fake_catalog_env(tmp)
            patches.append(mock.patch("media_storage.upload_mix_export_cloud", lambda *a, **k: cloud))
            if not local_ok:
                patches.append(mock.patch("media_storage.save_mix_export_local", lambda *a, **k: ("", "disk full")))
            for p in patches:
                p.start()
            try:
                ok, eid, err = M.save_multitrack_export_from_session(ss, audio, export_name="mix")
                rows = _live_rows(path)
            finally:
                for p in patches:
                    p.stop()
        return ok, eid, err, ss.get(M._LAST_EXPORT_SAVE_STATUS_KEY), rows

    def test_no_stored_audio_is_a_failure_with_no_library_entry(self):
        ok, eid, err, status, rows = self._save(_wav(), local_ok=False)
        self.assertFalse(ok, status)
        self.assertEqual(status["where"], "none")
        self.assertEqual(rows, [], "no usable Export Library entry may point at missing audio")

    def test_account_failure_is_reported_as_server_only(self):
        with mock.patch("media_storage._cloud_storage_enabled", return_value=True):
            ok, eid, err, status, rows = self._save(_wav(), cloud=("", "upload refused"))
        self.assertTrue(ok)
        self.assertEqual(status["where"], "server_only")
        self.assertEqual(len(rows), 1)

    def test_account_success_needs_a_verified_upload(self):
        with mock.patch("media_storage._cloud_storage_enabled", return_value=True):
            ok, eid, err, status, rows = self._save(_wav(), cloud=("bucket/k.wav", ""))
        self.assertEqual(status["where"], "account")

    def test_repeated_save_of_the_same_mix_makes_no_duplicate(self):
        ss: dict = {}
        import media_multitrack_export_catalog as M

        audio = _wav(level=6)
        with tempfile.TemporaryDirectory() as tmp:
            path, patches = _fake_catalog_env(tmp)
            patches.append(mock.patch("media_storage.upload_mix_export_cloud", lambda *a, **k: ("", "cloud_disabled")))
            for p in patches:
                p.start()
            try:
                ok1, e1, _ = M.save_multitrack_export_from_session(ss, audio, export_name="mix")
                ok2, e2, _ = M.save_multitrack_export_from_session(ss, audio, export_name="mix")
                rows = _live_rows(path)
            finally:
                for p in patches:
                    p.stop()
        self.assertTrue(ok1 and ok2)
        self.assertEqual(e1, e2)
        self.assertEqual(len(rows), 1)
        self.assertTrue(ss[M._LAST_EXPORT_SAVE_STATUS_KEY].get("reused"))

    def test_messages_match_where_the_audio_is(self):
        from media_multitrack_export_catalog import export_save_message

        self.assertEqual(export_save_message({"ok": True, "where": "account"}, "mix")[0], "success")
        lvl, txt = export_save_message({"ok": True, "where": "server_only", "cloud_enabled": True}, "mix")
        self.assertEqual(lvl, "warning")
        self.assertIn("restart", txt.lower())
        lvl, txt = export_save_message({"ok": True, "where": "server_only", "cloud_enabled": False}, "mix")
        self.assertNotEqual(lvl, "success")
        self.assertIn("restart", txt.lower())
        lvl, txt = export_save_message({"ok": False, "where": "none", "error": "disk full"}, "mix")
        self.assertEqual(lvl, "error")
        self.assertIn("download", txt.lower())
        self.assertNotEqual(export_save_message(None, "mix")[0], "success")


class MixUploadVerificationTests(unittest.TestCase):
    def _client(self, listed_size):
        class _Bucket:
            def upload(self, *a, **k):
                return {"Key": "ok"}

            def list(self, folder, opts):
                return [{"name": opts["search"], "metadata": {"size": listed_size}}]

        class _Client:
            class storage:
                @staticmethod
                def from_(bucket):
                    return _Bucket()

        return _Client()

    def _upload(self, listed_size, data):
        import media_storage as S

        with mock.patch.object(S, "_cloud_storage_enabled", return_value=True), \
             mock.patch.object(S, "_service_storage_client", return_value=self._client(listed_size)), \
             mock.patch.object(S, "_resolve_user_id", return_value="synthetic-user"):
            return S.upload_mix_export_cloud("synthetic", "exp-1", data, filename="mix.wav")

    def test_an_upload_listed_at_the_wrong_size_is_not_confirmed(self):
        data = _wav()
        ref, err = self._upload(len(data) - 10, data)
        self.assertEqual(err, "upload_not_verified")

    def test_an_upload_listed_at_its_size_is_confirmed(self):
        data = _wav()
        ref, err = self._upload(len(data), data)
        self.assertTrue(ref)
        self.assertEqual(err, "")


class UploadHandoffGuard(unittest.TestCase):
    def test_an_export_whose_audio_is_missing_is_not_handed_to_upload(self):
        import media_multitrack_export_catalog as M

        with mock.patch.object(M, "load_export_for_playback", return_value=(None, "missing_file", {"export_id": "e"})):
            ok, err = M.send_export_to_upload_analysis({}, "e")
        self.assertFalse(ok)
        self.assertTrue(err)


# --------------------------------------------------------------------------------- missing status
class ProjectSaveStatusTests(unittest.TestCase):
    def test_no_status_is_not_reported_as_success(self):
        from multitrack_project_audio_restore import project_save_message

        level, text = project_save_message(None, "Project saved")
        self.assertNotEqual(level, "success")
        self.assertIn("could not be confirmed", text)


if __name__ == "__main__":
    unittest.main()

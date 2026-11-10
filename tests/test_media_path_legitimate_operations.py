"""Containment must stop the attack without breaking the ordinary case.

The risk in a path fix is not that it fails to block traversal - that part is easy to
test - but that it quietly redirects a legitimate operation to a different file, or
refuses one that was always fine. So this exercises the real per-kind entry points for
all four media kinds through their normal relative paths, and then the same entry points
with hostile ones, in the same temporary directory.

Everything happens under a temporary root. No real workspace, recording, tone take,
multitrack session, export or uploaded document is read, written or deleted.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import media_storage

AUDIO = b"RIFF" + b"\x00" * 64
HOSTILE = [
    "../stolen.wav",
    "../../stolen.wav",
    "..\\stolen.wav",
    "media/recordings/../../../stolen.wav",
    "/stolen.wav",
    "C:/Windows/win.ini",
]


class MediaOperationsCase(unittest.TestCase):
    WS = "ws-ops"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "workspaces" / self.WS
        self.root.mkdir(parents=True, exist_ok=True)
        self.outside = self.tmp / "stolen.wav"
        self.outside.write_bytes(b"not yours")
        patches = [
            mock.patch.object(media_storage, "workspace_root", lambda ws: self.root),
            # The loaders already refuse a row from another workspace
            # ("workspace_mismatch"), which is a separate and welcome guard - this test
            # is about paths, so the session is the row's own workspace.
            mock.patch.object(media_storage, "_resolve_workspace_id",
                              lambda **kw: self.WS),
            mock.patch.object(media_storage, "_cloud_storage_enabled", lambda: False),
            mock.patch.object(media_storage, "_resolve_user_id", lambda: "user-ops"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def assert_outside_intact(self):
        self.assertTrue(self.outside.is_file(), "a file outside the workspace was touched")
        self.assertEqual(self.outside.read_bytes(), b"not yours")


class LegitimateOperationsStillWork(MediaOperationsCase):
    """The ordinary path, for each kind: save, read back, delete, confirm gone."""

    def test_a_recording_saves_loads_and_deletes(self):
        rel, err = media_storage.save_recording_local(
            self.WS, "rec-1", AUDIO, filename="take.wav")
        self.assertEqual(err, "")
        self.assertTrue(rel.startswith("media/recordings/"))
        path = media_storage.recording_local_abs_path(self.WS, rel)
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), AUDIO)

        data, status = media_storage.load_recording_audio(
            {"recording_id": "rec-1", "workspace_id": self.WS, "local_path": rel})
        self.assertEqual(data, AUDIO, status)

        self.assertEqual(media_storage.delete_recording_local(self.WS, rel), "")
        self.assertFalse(path.is_file())

    def test_a_tone_take_saves_loads_and_deletes(self):
        rel, err = media_storage.save_tone_take_local(
            self.WS, "tone-1", AUDIO, filename="tone.wav")
        self.assertEqual(err, "")
        row = {"tone_take_id": "tone-1", "workspace_id": self.WS, "local_path": rel}
        data, status = media_storage.load_tone_take_audio(row)
        self.assertEqual(data, AUDIO, status)
        path = media_storage.recording_local_abs_path(self.WS, rel)
        self.assertTrue(path.is_file())
        media_storage.delete_tone_take_files(row)
        self.assertFalse(path.is_file())

    def test_a_mix_export_saves_loads_and_deletes(self):
        rel, err = media_storage.save_mix_export_local(
            self.WS, "exp-1", AUDIO, filename="mix.wav")
        self.assertEqual(err, "")
        row = {"export_id": "exp-1", "workspace_id": self.WS, "local_path": rel}
        data, status = media_storage.load_mix_export_audio(row)
        self.assertEqual(data, AUDIO, status)
        path = media_storage.recording_local_abs_path(self.WS, rel)
        self.assertTrue(path.is_file())
        media_storage.delete_mix_export_files(row)
        self.assertFalse(path.is_file())

    def test_a_multitrack_session_deletes_its_own_layers(self):
        rels = []
        for i in range(3):
            rel, err = media_storage.save_recording_local(
                self.WS, f"mt-layer-{i}", AUDIO, filename=f"layer{i}.wav")
            self.assertEqual(err, "")
            rels.append(rel)
        session = {
            "multitrack_id": "mt-1", "workspace_id": self.WS,
            "tracks": [{"track_id": f"t{i}", "local_path": rel} for i, rel in enumerate(rels)],
        }
        for rel in rels:
            self.assertTrue(media_storage.recording_local_abs_path(self.WS, rel).is_file())
        media_storage.delete_multitrack_session_files(session)
        for rel in rels:
            self.assertFalse(
                media_storage.recording_local_abs_path(self.WS, rel).is_file(), rel)

    def test_a_song_document_saves_loads_and_deletes(self):
        rel, err = media_storage.save_song_document_local(
            self.WS, "doc-1", b"%PDF-1.4 %%EOF")
        self.assertEqual(err, "")
        path = media_storage.song_document_local_path(self.WS, rel)
        self.assertIsNotNone(path)
        self.assertEqual(path.read_bytes(), b"%PDF-1.4 %%EOF")
        media_storage.delete_song_document_files(self.WS, local_path=rel)
        self.assertFalse(
            media_storage.recording_local_abs_path(self.WS, rel).is_file())

    def test_deleting_one_recording_leaves_its_neighbours_alone(self):
        """The redirect risk: a contained path must still be the *right* contained path."""
        keep, _ = media_storage.save_recording_local(
            self.WS, "keep", AUDIO, filename="keep.wav")
        drop, _ = media_storage.save_recording_local(
            self.WS, "drop", AUDIO, filename="drop.wav")
        self.assertEqual(media_storage.delete_recording_local(self.WS, drop), "")
        self.assertFalse(media_storage.recording_local_abs_path(self.WS, drop).is_file())
        self.assertTrue(media_storage.recording_local_abs_path(self.WS, keep).is_file())

    def test_a_nested_relative_path_is_preserved_exactly(self):
        deep = "media/recordings/2026/11/take.wav"
        target = media_storage.recording_local_abs_path(self.WS, deep)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(AUDIO)
        self.assertEqual(target, self.root / "media" / "recordings" / "2026" / "11" / "take.wav")
        self.assertEqual(media_storage.delete_recording_local(self.WS, deep), "")
        self.assertFalse(target.is_file())


class HostilePathsAreRefusedByEveryKind(MediaOperationsCase):
    def setUp(self):
        super().setUp()
        self.legit, _ = media_storage.save_recording_local(
            self.WS, "legit", AUDIO, filename="legit.wav")

    def test_recording_delete_refuses_and_keeps_the_real_file(self):
        for rel in HOSTILE:
            with self.subTest(rel=rel):
                self.assertEqual(media_storage.delete_recording_local(self.WS, rel),
                                 "path_outside_workspace")
                self.assert_outside_intact()
        self.assertTrue(
            media_storage.recording_local_abs_path(self.WS, self.legit).is_file())

    def test_recording_load_does_not_return_the_file_outside(self):
        for rel in HOSTILE:
            with self.subTest(rel=rel):
                data, _status = media_storage.load_recording_audio(
                    {"recording_id": "x", "workspace_id": self.WS, "local_path": rel})
                self.assertNotEqual(data, b"not yours")

    def test_tone_take_load_does_not_return_the_file_outside(self):
        for rel in HOSTILE:
            with self.subTest(rel=rel):
                data, _status = media_storage.load_tone_take_audio(
                    {"tone_take_id": "x", "workspace_id": self.WS, "local_path": rel})
                self.assertNotEqual(data, b"not yours")

    def test_mix_export_load_does_not_return_the_file_outside(self):
        for rel in HOSTILE:
            with self.subTest(rel=rel):
                data, _status = media_storage.load_mix_export_audio(
                    {"export_id": "x", "workspace_id": self.WS, "local_path": rel})
                self.assertNotEqual(data, b"not yours")

    def test_a_multitrack_session_cannot_delete_outside_its_workspace(self):
        session = {
            "multitrack_id": "mt-evil", "workspace_id": self.WS,
            "tracks": [{"track_id": "t", "local_path": rel} for rel in HOSTILE],
        }
        media_storage.delete_multitrack_session_files(session)
        self.assert_outside_intact()

    def test_a_song_document_cannot_delete_outside_its_workspace(self):
        for rel in HOSTILE:
            with self.subTest(rel=rel):
                media_storage.delete_song_document_files(self.WS, local_path=rel)
                self.assert_outside_intact()

    def test_the_legitimate_recording_survived_every_attempt(self):
        self.assertTrue(
            media_storage.recording_local_abs_path(self.WS, self.legit).is_file())


if __name__ == "__main__":
    unittest.main()

"""A stored path is data, and data must not be able to name a file outside the workspace.

``recording_local_abs_path`` only stripped a leading slash, so a ``local_path``
containing ``..`` resolved outside the workspace folder entirely. The paths the app
writes are built from generated ids and never contain one - but the values reaching
this function come from media-catalog rows, which are synced from the cloud, stored as
JSON on disk and not necessarily written by this version of the app.

Severity follows the caller, not the helper. ``delete_recording_local`` unlinks what it
is given, so a traversal value there was arbitrary file deletion; the load paths were
arbitrary file reads. Both are reachable from a tampered or corrupted row.

Everything here works inside a temporary directory. No real workspace, recording or
user file is read, written or removed.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import media_storage

ESCAPES = [
    "../escaped.txt",
    "../../escaped.txt",
    "..\\escaped.txt",
    "..\\..\\escaped.txt",
    "media/../../escaped.txt",
    "media/recordings/../../../escaped.txt",
    "/escaped.txt",
    "//escaped.txt",
    "C:/Windows/win.ini",
    "C:\\Windows\\win.ini",
    "./../escaped.txt",
    "media/./../../escaped.txt",
]


class ContainmentCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "workspaces" / "ws"
        (self.root / "media" / "recordings").mkdir(parents=True, exist_ok=True)
        self.outside = self.tmp / "escaped.txt"
        self.outside.write_text("not yours", encoding="utf-8")
        patch = mock.patch.object(media_storage, "workspace_root",
                                  lambda ws: self.root)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)


class NoSpellingOfDotDotEscapes(ContainmentCase):
    def test_the_built_path_always_stays_under_the_workspace(self):
        for rel in ESCAPES:
            with self.subTest(rel=rel):
                path = media_storage.recording_local_abs_path("ws", rel)
                self.assertTrue(
                    self.root.resolve() in path.resolve().parents
                    or path.resolve() == self.root.resolve(),
                    f"{rel!r} produced {path}",
                )
                self.assertNotEqual(path.resolve(), self.outside.resolve())

    def test_the_planted_file_outside_is_never_reached(self):
        for rel in ESCAPES:
            with self.subTest(rel=rel):
                path = media_storage.recording_local_abs_path("ws", rel)
                self.assertFalse(
                    path.is_file() and path.read_text(encoding="utf-8") == "not yours")

    def test_the_strict_check_reports_the_escape_rather_than_correcting_it(self):
        for rel in ESCAPES:
            with self.subTest(rel=rel):
                self.assertIsNone(media_storage.workspace_contained_path("ws", rel))

    def test_an_ordinary_relative_path_still_resolves(self):
        target = self.root / "media" / "recordings" / "a.wav"
        target.write_bytes(b"RIFF")
        path = media_storage.recording_local_abs_path("ws", "media/recordings/a.wav")
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), b"RIFF")
        self.assertEqual(
            media_storage.workspace_contained_path("ws", "media/recordings/a.wav"),
            target.resolve())

    def test_a_backslash_path_still_resolves(self):
        (self.root / "media" / "recordings" / "b.wav").write_bytes(b"RIFF")
        path = media_storage.recording_local_abs_path("ws", "media\\recordings\\b.wav")
        self.assertTrue(path.is_file())

    def test_an_empty_path_is_the_workspace_itself_not_the_parent(self):
        self.assertEqual(
            media_storage.recording_local_abs_path("ws", "").resolve(),
            self.root.resolve())
        self.assertIsNone(media_storage.workspace_contained_path("ws", ""))


class ASymlinkIsNotAWayOut(ContainmentCase):
    """Lexical cleaning cannot see through a link; the canonical check can."""

    def _link(self, name: str, target: Path) -> bool:
        link = self.root / "media" / name
        try:
            os.symlink(target, link, target_is_directory=target.is_dir())
            return True
        except (OSError, NotImplementedError, AttributeError):
            return False

    def test_a_symlinked_file_inside_the_workspace_is_refused(self):
        if not self._link("link.txt", self.outside):
            self.skipTest("symlinks not permitted in this environment")
        self.assertIsNone(
            media_storage.workspace_contained_path("ws", "media/link.txt"))

    def test_a_symlinked_directory_inside_the_workspace_is_refused(self):
        other = self.tmp / "elsewhere"
        other.mkdir(exist_ok=True)
        (other / "secret.wav").write_bytes(b"RIFF")
        if not self._link("linkdir", other):
            self.skipTest("symlinks not permitted in this environment")
        self.assertIsNone(
            media_storage.workspace_contained_path("ws", "media/linkdir/secret.wav"))

    def test_a_real_directory_inside_the_workspace_is_allowed(self):
        inner = self.root / "media" / "real"
        inner.mkdir(parents=True, exist_ok=True)
        (inner / "ok.wav").write_bytes(b"RIFF")
        self.assertIsNotNone(
            media_storage.workspace_contained_path("ws", "media/real/ok.wav"))


class DeletionRefusesWhatItCannotPlace(ContainmentCase):
    """The one operation that cannot be undone must fail loudly, not quietly."""

    def test_a_traversal_path_deletes_nothing_and_says_so(self):
        for rel in ESCAPES:
            with self.subTest(rel=rel):
                result = media_storage.delete_recording_local("ws", rel)
                self.assertEqual(result, "path_outside_workspace")
                self.assertTrue(self.outside.is_file(),
                                "the file outside the workspace was removed")

    def test_a_real_recording_inside_the_workspace_is_still_deleted(self):
        target = self.root / "media" / "recordings" / "gone.wav"
        target.write_bytes(b"RIFF")
        self.assertEqual(media_storage.delete_recording_local(
            "ws", "media/recordings/gone.wav"), "")
        self.assertFalse(target.is_file())

    def test_deleting_something_that_is_not_there_is_not_an_error(self):
        self.assertEqual(media_storage.delete_recording_local(
            "ws", "media/recordings/never.wav"), "")

    def test_a_symlink_out_of_the_workspace_is_not_followed_and_deleted(self):
        link = self.root / "media" / "link.wav"
        try:
            os.symlink(self.outside, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks not permitted in this environment")
        self.assertEqual(media_storage.delete_recording_local("ws", "media/link.wav"),
                         "path_outside_workspace")
        self.assertTrue(self.outside.is_file())


class TheSongDocumentHelperUsesTheSharedCheck(ContainmentCase):
    """One containment implementation, not two."""

    def test_it_delegates_rather_than_repeating_the_logic(self):
        import inspect

        source = inspect.getsource(media_storage.song_document_local_path)
        self.assertIn("workspace_contained_path", source)

    def test_it_still_refuses_an_escape(self):
        for rel in ESCAPES:
            with self.subTest(rel=rel):
                self.assertIsNone(
                    media_storage.song_document_local_path("ws", rel))

    def test_it_still_accepts_a_real_document(self):
        docs = self.root / "media" / "song_documents"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "d.pdf").write_bytes(b"%PDF-1.4 %%EOF")
        self.assertIsNotNone(
            media_storage.song_document_local_path("ws", "media/song_documents/d.pdf"))


if __name__ == "__main__":
    unittest.main()


class TheSymlinkBranchIsTestedEvenWithoutThePrivilege(ContainmentCase):
    """Windows refuses symlink creation here without elevation (WinError 1314).

    Skipping would leave the canonical-resolution branch unexercised, so these simulate
    exactly what a symlink does to ``resolve()`` - return a path outside the root - and
    check the decision this code makes about it. The real-symlink tests above still run
    wherever the privilege exists.
    """

    def _resolve_to(self, mapping: dict):
        real_resolve = Path.resolve

        def fake(self_path, *a, **kw):
            for needle, target in mapping.items():
                if str(self_path).endswith(needle):
                    return target
            return real_resolve(self_path, *a, **kw)

        return mock.patch.object(Path, "resolve", fake)

    def test_a_path_resolving_outside_the_root_is_refused(self):
        with self._resolve_to({"link.wav": self.outside.resolve()}):
            self.assertIsNone(
                media_storage.workspace_contained_path("ws", "media/link.wav"))

    def test_deletion_refuses_a_path_resolving_outside_the_root(self):
        with self._resolve_to({"link.wav": self.outside.resolve()}):
            result = media_storage.delete_recording_local("ws", "media/link.wav")
        self.assertEqual(result, "path_outside_workspace")
        self.assertTrue(self.outside.is_file())

    def test_a_path_resolving_inside_the_root_is_still_allowed(self):
        inside = (self.root / "media" / "recordings" / "ok.wav")
        inside.parent.mkdir(parents=True, exist_ok=True)
        inside.write_bytes(b"RIFF")
        with self._resolve_to({"ok.wav": inside}):
            self.assertIsNotNone(
                media_storage.workspace_contained_path("ws", "media/recordings/ok.wav"))

    def test_a_hardlink_inside_the_workspace_is_not_an_escape(self):
        """Recorded, because it is the one link a canonical check cannot see.

        A hard link is a second name for the same data, and its name really is inside
        the workspace - so containment allows it, and deleting it removes that name
        only, never the original. Creating one needs no privilege, unlike a symlink.
        """
        target = self.root / "media" / "recordings" / "real.wav"
        target.write_bytes(b"RIFF")
        link = self.root / "media" / "recordings" / "second-name.wav"
        try:
            os.link(target, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("hard links not permitted in this environment")
        self.assertIsNotNone(media_storage.workspace_contained_path(
            "ws", "media/recordings/second-name.wav"))
        self.assertEqual(media_storage.delete_recording_local(
            "ws", "media/recordings/second-name.wav"), "")
        self.assertFalse(link.is_file())
        self.assertTrue(target.is_file(), "the original name must survive")

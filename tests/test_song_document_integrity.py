"""My Uploaded Melodies: the storage lifecycle, where the expensive mistakes live.

Deduplication is the dangerous feature here. Storing one blob for three references saves
space and makes a second upload instant - and gets a musician's sheet music deleted if
the bookkeeping is wrong. So the lifecycle is tested at three references rather than two,
because "delete one of two" can pass by accident in a way "delete one of three" cannot.

The other theme is ownership. The server-side storage client can read any object in the
bucket; it is privileged. So a document id or a storage path arriving from a caller is
never treated as proof of anything. Ownership is resolved against the authenticated
workspace and the catalog row, every time, before a byte is read.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import media_persistence
import media_state
import media_storage
import song_document_catalog as sdc

PDF_A = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\ntrailer\n%%EOF\n"
PDF_B = b"%PDF-1.7\n1 0 obj\n<< /Type /Page >>\n2 0 obj\n<< /Type /Page >>\n%%EOF\n"


class LifecycleCase(unittest.TestCase):
    """One disposable workspace per test. No real catalog, recordings or compositions."""

    WORKSPACE = "ws-integrity"
    USER = "user-integrity"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.session: dict = {}
        self.cloud: dict[str, bytes] = {}
        self.cloud_enabled = True
        self.workspace = self.WORKSPACE

        def upload(ws, did, data, user_id=None):
            if not self.cloud_enabled:
                return "", "cloud_disabled"
            key = media_storage.build_song_document_object_key(
                user_id or self.USER, ws, did)
            self.cloud[key] = data
            return media_storage.build_storage_ref("music-media", key), ""

        def download(ref, st=None):
            _bucket, key = media_storage.parse_storage_ref(ref)
            data = self.cloud.get(key)
            return (data, "") if data else (None, "object_missing")

        def delete_cloud(ref):
            _bucket, key = media_storage.parse_storage_ref(ref)
            return "" if self.cloud.pop(key, None) is not None else "object_missing"

        patches = [
            mock.patch.object(media_persistence, "_resolve_workspace_id",
                              lambda **kw: self.workspace),
            mock.patch.object(media_persistence, "_local_path",
                              lambda **kw: self.tmp / self.workspace / "media_catalog.json"),
            mock.patch.object(media_persistence, "_cloud_authoritative", lambda: False),
            mock.patch.object(media_persistence, "_load_cloud_catalog", lambda **kw: ({}, None)),
            mock.patch.object(media_persistence, "_save_cloud_catalog",
                              lambda c, **kw: (True, "")),
            mock.patch.object(media_storage, "recording_local_abs_path",
                              lambda ws, rel: self.tmp / str(ws) / rel),
            mock.patch.object(media_storage, "_resolve_user_id", lambda: self.USER),
            mock.patch.object(media_storage, "upload_song_document_cloud", upload),
            mock.patch.object(media_storage, "download_recording_cloud", download),
            mock.patch.object(media_storage, "delete_recording_cloud", delete_cloud),
            mock.patch.object(sdc, "_workspace_id", lambda **kw: self.workspace),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def owner(self, source_id="catalog::a", source_type="catalog", title="Song"):
        return {"source_type": source_type, "source_id": source_id, "song_title": title}

    def save(self, owner=None, data=PDF_A, **kw):
        with mock.patch.object(sdc, "active_song_owner",
                               lambda session, st=None: owner or self.owner()):
            return sdc.save_song_document(self.session, data, st=self.session, **kw)

    def local_file(self, row):
        return media_storage.recording_local_abs_path(
            self.workspace, str(row.get("local_path") or ""))


class ThreeReferencesOneBlob(LifecycleCase):
    """The lifecycle the feature could silently get wrong."""

    def setUp(self):
        super().setUp()
        self.rows = [
            self.save(owner=self.owner(f"catalog::{i}", title=f"Song {i}"),
                      title=f"ref{i}", data=PDF_A)["row"]
            for i in range(3)
        ]

    def test_all_three_share_one_stored_file(self):
        digests = {r["sha256"] for r in self.rows}
        paths = {r["local_path"] for r in self.rows}
        refs = {r["storage_ref"] for r in self.rows}
        self.assertEqual(len(digests), 1)
        self.assertEqual(len(paths), 1, "a shared blob should be stored once")
        self.assertEqual(len(refs), 1)
        self.assertEqual(len(self.cloud), 1, "one object uploaded, not three")

    def test_deleting_the_first_leaves_the_other_two_readable(self):
        out = sdc.delete_song_document(self.rows[0]["document_id"], st=self.session)
        self.assertTrue(out["ok"])
        self.assertTrue(out["blob_kept_for_other_rows"])
        self.assertTrue(self.local_file(self.rows[1]).is_file())
        for row in self.rows[1:]:
            data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
            self.assertEqual(err, "")
            self.assertEqual(data, PDF_A)

    def test_deleting_two_still_leaves_the_last_one_readable(self):
        for row in self.rows[:2]:
            sdc.delete_song_document(row["document_id"], st=self.session)
        data, err = sdc.load_song_document_bytes(
            self.rows[2]["document_id"], st=self.session)
        self.assertEqual(err, "")
        self.assertEqual(data, PDF_A)
        self.assertTrue(self.local_file(self.rows[2]).is_file())

    def test_deleting_the_last_one_finally_removes_the_blob(self):
        for row in self.rows:
            out = sdc.delete_song_document(row["document_id"], st=self.session)
            self.assertTrue(out["ok"])
        self.assertFalse(out["blob_kept_for_other_rows"])
        self.assertFalse(self.local_file(self.rows[0]).is_file())
        self.assertEqual(self.cloud, {}, "the cloud object should be gone too")

    def test_deleting_the_same_reference_twice_is_not_an_error_for_the_others(self):
        did = self.rows[0]["document_id"]
        self.assertTrue(sdc.delete_song_document(did, st=self.session)["ok"])
        second = sdc.delete_song_document(did, st=self.session)
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "document_not_found")
        data, err = sdc.load_song_document_bytes(
            self.rows[1]["document_id"], st=self.session)
        self.assertEqual((err, data), ("", PDF_A))


class EditingMetadataDoesNotTouchTheBytes(LifecycleCase):
    def setUp(self):
        super().setUp()
        self.row = self.save(title="Original", data=PDF_B)["row"]
        self.path = self.local_file(self.row)
        self.before = (self.path.read_bytes(), self.path.stat().st_mtime_ns,
                       dict(self.cloud))

    def test_renaming_rewrites_no_file(self):
        sdc.rename_song_document(self.row["document_id"], "Renamed", st=self.session)
        self.assertEqual(self.path.read_bytes(), self.before[0])
        self.assertEqual(self.path.stat().st_mtime_ns, self.before[1])
        self.assertEqual(self.cloud, self.before[2])

    def test_retagging_rewrites_no_file(self):
        sdc.retag_song_document(self.row["document_id"], instrument_tag="Flute",
                                key_tag="D", st=self.session)
        self.assertEqual(self.path.stat().st_mtime_ns, self.before[1])
        self.assertEqual(self.cloud, self.before[2])

    def test_renaming_does_not_create_a_second_row_or_blob(self):
        sdc.rename_song_document(self.row["document_id"], "Renamed", st=self.session)
        rows = sdc.documents_for_owner(self.owner(), st=self.session)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["document_id"], self.row["document_id"])
        self.assertEqual(rows[0]["local_path"], self.row["local_path"])
        self.assertEqual(len(self.cloud), 1)

    def test_the_content_hash_survives_an_edit(self):
        out = sdc.rename_song_document(self.row["document_id"], "Renamed", st=self.session)
        self.assertEqual(out["row"]["sha256"], self.row["sha256"])


class DeduplicationStopsAtTheWorkspaceBoundary(LifecycleCase):
    def test_an_identical_file_in_another_workspace_is_stored_separately(self):
        mine = self.save(title="Mine", data=PDF_A)["row"]
        self.workspace = "ws-someone-else"
        theirs = self.save(title="Theirs", data=PDF_A)["row"]
        self.assertEqual(mine["sha256"], theirs["sha256"])
        self.assertNotEqual(mine["storage_ref"], theirs["storage_ref"],
                            "two workspaces must not share one object")
        self.assertEqual(len(self.cloud), 2)

    def test_deleting_in_one_workspace_leaves_the_other_intact(self):
        mine = self.save(title="Mine", data=PDF_A)["row"]
        self.workspace = "ws-someone-else"
        theirs = self.save(title="Theirs", data=PDF_A)["row"]
        sdc.delete_song_document(theirs["document_id"], st=self.session)
        self.workspace = self.WORKSPACE
        data, err = sdc.load_song_document_bytes(mine["document_id"], st=self.session)
        self.assertEqual((err, data), ("", PDF_A))


class OwnershipIsResolvedNotAsserted(LifecycleCase):
    """A privileged storage client makes a supplied id or path worthless as evidence."""

    def test_a_document_id_from_another_workspace_reads_nothing(self):
        row = self.save(title="Private", data=PDF_A)["row"]
        self.workspace = "ws-attacker"
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertIsNone(data)
        self.assertEqual(err, "document_not_found")

    def test_a_row_pointing_at_another_users_object_is_refused(self):
        """Even a catalog row is not authority over a path outside the user's prefix."""
        row = self.save(title="Doc", data=PDF_A)["row"]
        foreign = media_storage.build_storage_ref(
            "music-media", f"other-user/{self.WORKSPACE}/song_documents/x.pdf")
        self.cloud[media_storage.parse_storage_ref(foreign)[1]] = b"%PDF-secret%%EOF"
        media_persistence.update_song_document(
            self.session, row["document_id"],
            {"storage_ref": foreign, "local_path": None})
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertIsNone(data)
        self.assertEqual(err, "storage_ref_not_owned")

    def test_the_local_path_cannot_escape_the_workspace_folder(self):
        """A real file is planted outside, so this proves containment, not absence."""
        secret = self.tmp / "secret.pdf"
        secret.write_bytes(b"%PDF-1.4 not yours %%EOF")
        row = self.save(title="Doc", data=PDF_A)["row"]
        escape = "../" + secret.name
        self.assertTrue(
            media_storage.recording_local_abs_path(self.workspace, escape)
            .resolve() == secret.resolve(),
            "the escape path must really reach the planted file, or this proves nothing",
        )
        media_persistence.update_song_document(
            self.session, row["document_id"],
            {"local_path": escape, "storage_ref": None})
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertIsNone(data)
        self.assertEqual(err, "missing_file")

    def test_a_contained_path_still_resolves(self):
        row = self.save(title="Doc", data=PDF_A)["row"]
        self.assertIsNotNone(
            media_storage.song_document_local_path(self.workspace, row["local_path"]))


class StorageGoesWrongInRealisticWays(LifecycleCase):
    def test_an_interrupted_upload_is_rejected_not_half_saved(self):
        truncated = PDF_A[: len(PDF_A) // 2]
        res = self.save(data=truncated)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "pdf_truncated")
        self.assertEqual(sdc.documents_for_owner(self.owner(), st=self.session), [])
        self.assertEqual(self.cloud, {})

    def test_a_cloud_outage_saves_locally_and_says_so(self):
        self.cloud_enabled = False
        res = self.save(title="Offline")
        self.assertTrue(res["ok"])
        self.assertEqual(res["storage_status"], media_state.DOCUMENT_STORAGE_LOCAL_ONLY)
        data, err = sdc.load_song_document_bytes(
            res["row"]["document_id"], st=self.session)
        self.assertEqual((err, data), ("", PDF_A))

    def test_a_missing_cloud_blob_falls_back_to_the_local_copy(self):
        row = self.save(title="Doc")["row"]
        self.cloud.clear()
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertEqual((err, data), ("", PDF_A))

    def test_a_missing_blob_everywhere_is_an_honest_error(self):
        row = self.save(title="Doc")["row"]
        self.cloud.clear()
        self.local_file(row).unlink()
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertIsNone(data)
        self.assertEqual(err, "object_missing")

    def test_stale_metadata_pointing_nowhere_does_not_crash(self):
        row = self.save(title="Doc")["row"]
        media_persistence.update_song_document(
            self.session, row["document_id"],
            {"local_path": "media/song_documents/gone.pdf", "storage_ref": None})
        data, err = sdc.load_song_document_bytes(row["document_id"], st=self.session)
        self.assertIsNone(data)
        self.assertEqual(err, "missing_file")

    def test_two_saves_in_a_row_both_survive(self):
        """The catalog is read-modify-written, so a second save must not lose the first."""
        first = self.save(title="First", data=PDF_A)["row"]
        second = self.save(title="Second", data=PDF_B)["row"]
        titles = {r["title"] for r in sdc.documents_for_owner(self.owner(), st=self.session)}
        self.assertEqual(titles, {"First", "Second"})
        self.assertNotEqual(first["document_id"], second["document_id"])

    def test_a_save_made_against_a_stale_cached_catalog_does_not_drop_rows(self):
        """A concurrent writer's row is on disk but not in this session's cache."""
        first = self.save(title="First", data=PDF_A)["row"]
        stale = json.loads(
            (self.tmp / self.workspace / "media_catalog.json").read_text(encoding="utf-8"))
        self.session["_media_catalog_cache"] = {
            **stale, "song_documents": []
        }
        self.save(title="Second", data=PDF_B)
        titles = {r["title"] for r in sdc.documents_for_owner(self.owner(), st=self.session)}
        self.assertIn("Second", titles)
        self.assertIn("First", titles,
                      "save_media_catalog merges with what is on disk, so the "
                      "concurrent row must survive")
        self.assertTrue(first["document_id"])


if __name__ == "__main__":
    unittest.main()

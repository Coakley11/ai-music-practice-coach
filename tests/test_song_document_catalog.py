"""My Uploaded Melodies, slice 1: the durable store beneath the Practice-page UI.

The properties worth testing here are the ones a musician would never discover until
they mattered: that two songs with the same title keep separate references, that a
document cannot be read from another workspace, that "saved" means saved, and that a
file claiming to be a PDF is checked rather than believed.
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

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\ntrailer\n%%EOF\n"
SECOND_PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Page >>\n2 0 obj\n<< /Type /Page >>\n%%EOF\n"


class FakeWorkspace:
    """A disposable workspace: its own data dir, its own catalog, no real user state."""

    def __init__(self, tmp: Path, workspace_id: str = "ws-test"):
        self.root = tmp
        self.workspace_id = workspace_id
        self.session: dict = {}

    def dir(self) -> Path:
        path = self.root / self.workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def catalog_path(self) -> Path:
        return self.dir() / "media_catalog.json"


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.ws = FakeWorkspace(self.tmp)
        patches = [
            mock.patch.object(media_persistence, "_resolve_workspace_id",
                              lambda **kw: self.ws.workspace_id),
            mock.patch.object(media_persistence, "_local_path",
                              lambda **kw: self.ws.catalog_path()),
            mock.patch.object(media_persistence, "_cloud_authoritative", lambda: False),
            mock.patch.object(media_persistence, "_load_cloud_catalog",
                              lambda **kw: ({}, None)),
            mock.patch.object(media_persistence, "_save_cloud_catalog",
                              lambda c, **kw: (False, "cloud_disabled")),
            mock.patch.object(media_storage, "recording_local_abs_path",
                              lambda ws, rel: self.tmp / str(ws) / rel),
            mock.patch.object(media_storage, "_cloud_storage_enabled", lambda: False),
            mock.patch.object(media_storage, "_resolve_user_id", lambda: "user-test"),
            mock.patch.object(sdc, "_workspace_id",
                              lambda **kw: self.ws.workspace_id),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def owner(self, source_type="catalog", source_id="catalog::autumn", title="Autumn Leaves"):
        return {"source_type": source_type, "source_id": source_id, "song_title": title}

    def save(self, owner=None, data=MINIMAL_PDF, **kw):
        with mock.patch.object(sdc, "active_song_owner",
                               lambda session, st=None: owner or self.owner()):
            return sdc.save_song_document(self.ws.session, data, st=self.ws.session, **kw)


class SavingIsHonest(StoreCase):
    def test_a_saved_document_is_listed_and_readable(self):
        res = self.save(filename="lick.pdf", title="Bebop lick")
        self.assertTrue(res["ok"], res)
        rows = sdc.documents_for_owner(self.owner(), st=self.ws.session)
        self.assertEqual([r["title"] for r in rows], ["Bebop lick"])
        data, err = sdc.load_song_document_bytes(
            rows[0]["document_id"], st=self.ws.session)
        self.assertEqual(err, "")
        self.assertEqual(data, MINIMAL_PDF)

    def test_local_only_is_reported_as_local_only_not_as_cloud(self):
        """The cloud is off in this test, and the row must say so rather than imply saved."""
        res = self.save()
        self.assertEqual(res["storage_status"], media_state.DOCUMENT_STORAGE_LOCAL_ONLY)
        self.assertTrue(res["ok"])

    def test_a_failed_blob_write_does_not_leave_a_listed_document(self):
        with mock.patch.object(media_storage, "save_song_document_local",
                               lambda *a, **k: ("", "disk_full")):
            res = self.save()
        self.assertFalse(res["ok"])
        self.assertEqual(res["storage_status"], media_state.DOCUMENT_STORAGE_FAILED)
        self.assertEqual(sdc.documents_for_owner(self.owner(), st=self.ws.session), [])

    def test_a_failed_catalog_write_is_reported_as_failure(self):
        with mock.patch.object(media_persistence, "_save_local_catalog",
                               lambda c, **kw: (False, "readonly")):
            res = self.save()
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "readonly")

    def test_an_unknown_song_refuses_the_save(self):
        with mock.patch.object(sdc, "active_song_owner", lambda session, st=None: {}):
            res = sdc.save_song_document(self.ws.session, MINIMAL_PDF, st=self.ws.session)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "unknown_song")


class ContentIsCheckedNotTheFilename(StoreCase):
    def test_a_file_that_is_not_a_pdf_is_rejected_however_it_is_named(self):
        res = self.save(data=b"MZ\x90\x00 this is an executable", filename="exercise.pdf")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "not_a_pdf")

    def test_a_truncated_pdf_is_rejected(self):
        res = self.save(data=b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\n")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "pdf_truncated")

    def test_an_oversized_file_is_rejected_before_anything_is_written(self):
        from upload_media import DOCUMENT_MAX_SIZE_BYTES

        huge = b"%PDF-1.4\n" + b"0" * DOCUMENT_MAX_SIZE_BYTES + b"%%EOF"
        res = self.save(data=huge)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "document_too_large")

    def test_an_empty_upload_is_rejected(self):
        self.assertEqual(self.save(data=b"")["error"], "missing_document")

    def test_the_document_limit_cannot_exceed_streamlits_own(self):
        import upload_media

        self.assertLessEqual(upload_media.DOCUMENT_MAX_SIZE_MB,
                             upload_media.UPLOAD_MAX_SIZE_MB)

    def test_the_stored_path_ignores_the_uploaded_name(self):
        res = self.save(filename="../../escape.pdf.exe")
        self.assertTrue(res["ok"])
        self.assertTrue(str(res["row"]["local_path"]).endswith(".pdf"))
        self.assertNotIn("..", str(res["row"]["local_path"]))


class SongsDoNotShareDocuments(StoreCase):
    def test_two_songs_with_the_same_title_keep_separate_references(self):
        catalog_song = self.owner("catalog", "catalog::autumn", "Autumn Leaves")
        custom_song = self.owner("custom", "custom::autumn", "Autumn Leaves")
        self.save(owner=catalog_song, title="From the Catalog")
        self.save(owner=custom_song, title="My own chart")
        self.assertEqual(
            [r["title"] for r in sdc.documents_for_owner(catalog_song, st=self.ws.session)],
            ["From the Catalog"],
        )
        self.assertEqual(
            [r["title"] for r in sdc.documents_for_owner(custom_song, st=self.ws.session)],
            ["My own chart"],
        )

    def test_all_three_sources_stay_separate(self):
        owners = [
            self.owner("catalog", "catalog::x", "Song"),
            self.owner("custom", "custom::x", "Song"),
            self.owner("composition", "composition::x", "Song"),
        ]
        for i, owner in enumerate(owners):
            self.save(owner=owner, title=f"doc{i}", data=MINIMAL_PDF)
        for i, owner in enumerate(owners):
            rows = sdc.documents_for_owner(owner, st=self.ws.session)
            self.assertEqual([r["title"] for r in rows], [f"doc{i}"])

    def test_a_matching_title_alone_is_not_a_match(self):
        row = {"source_type": "catalog", "source_id": "catalog::a", "song_title": "Song"}
        other = {"source_type": "catalog", "source_id": "catalog::b", "song_title": "Song"}
        self.assertFalse(sdc.document_belongs_to_owner(row, other))

    def test_a_row_with_no_source_id_belongs_to_nobody(self):
        self.assertFalse(sdc.document_belongs_to_owner(
            {"source_type": "catalog", "source_id": ""},
            {"source_type": "catalog", "source_id": ""}))

    def test_many_documents_can_belong_to_one_song(self):
        for i in range(4):
            self.save(title=f"ref{i}", data=MINIMAL_PDF if i % 2 else SECOND_PDF)
        rows = sdc.documents_for_owner(self.owner(), st=self.ws.session)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r["document_id"] for r in rows}), 4)


class DocumentsArePrivate(StoreCase):
    def test_another_workspace_cannot_read_this_one(self):
        res = self.save(title="Private")
        did = res["row"]["document_id"]
        with mock.patch.object(sdc, "_workspace_id", lambda **kw: "someone-else"):
            data, err = sdc.load_song_document_bytes(did, st=self.ws.session)
        self.assertIsNone(data)
        self.assertEqual(err, "document_not_found")

    def test_a_storage_ref_outside_the_users_prefix_is_refused(self):
        self.assertFalse(media_storage.song_document_key_belongs_to(
            "supabase://music-media/other-user/ws/song_documents/abc.pdf",
            "user-test", "ws-test"))
        self.assertTrue(media_storage.song_document_key_belongs_to(
            "supabase://music-media/user-test/ws-test/song_documents/abc.pdf",
            "user-test", "ws-test"))

    def test_a_guessed_object_key_is_not_downloaded(self):
        called = []
        with mock.patch.object(media_storage, "download_recording_cloud",
                               lambda *a, **k: called.append(a) or (b"x", "")):
            data, err = media_storage.download_song_document_cloud(
                "supabase://music-media/victim/ws/song_documents/known-id.pdf",
                workspace_id="ws-test", user_id="user-test")
        self.assertIsNone(data)
        self.assertEqual(err, "storage_ref_not_owned")
        self.assertEqual(called, [], "no fetch should have been attempted")

    def test_the_object_key_is_scoped_by_user_and_workspace(self):
        key = media_storage.build_song_document_object_key("u1", "w1", "d1")
        self.assertEqual(key, "u1/w1/song_documents/d1.pdf")

    def test_nothing_here_builds_a_public_url(self):
        source = Path(media_storage.__file__).read_text(encoding="utf-8")
        for marker in ("get_public_url", "create_signed_url", "public_url"):
            self.assertNotIn(marker, source)


class RenameRetagAndDelete(StoreCase):
    def test_rename_changes_only_the_name(self):
        did = self.save(title="Old")["row"]["document_id"]
        out = sdc.rename_song_document(did, "New name", st=self.ws.session)
        self.assertTrue(out["ok"])
        self.assertEqual(out["row"]["title"], "New name")
        self.assertEqual(out["row"]["document_id"], did)

    def test_an_empty_rename_is_refused(self):
        did = self.save(title="Keep")["row"]["document_id"]
        self.assertFalse(sdc.rename_song_document(did, "   ", st=self.ws.session)["ok"])
        rows = sdc.documents_for_owner(self.owner(), st=self.ws.session)
        self.assertEqual(rows[0]["title"], "Keep")

    def test_tags_can_be_set_and_changed(self):
        did = self.save(title="Lick")["row"]["document_id"]
        out = sdc.retag_song_document(
            did, instrument_tag="Alto Sax", key_tag="Eb", st=self.ws.session)
        self.assertEqual(out["row"]["instrument_tag"], "Alto Sax")
        self.assertEqual(out["row"]["key_tag"], "Eb")

    def test_delete_removes_it_from_the_list_and_from_disk(self):
        res = self.save(title="Gone")
        did = res["row"]["document_id"]
        path = media_storage.recording_local_abs_path(
            self.ws.workspace_id, res["row"]["local_path"])
        self.assertTrue(path.is_file())
        out = sdc.delete_song_document(did, st=self.ws.session)
        self.assertTrue(out["ok"], out)
        self.assertEqual(sdc.documents_for_owner(self.owner(), st=self.ws.session), [])
        self.assertFalse(path.is_file())

    def test_deleting_one_of_two_rows_sharing_a_blob_keeps_the_file(self):
        a = self.save(title="A", data=MINIMAL_PDF)["row"]
        b = self.save(owner=self.owner("custom", "custom::z", "Other"),
                      title="B", data=MINIMAL_PDF)["row"]
        self.assertEqual(a["sha256"], b["sha256"])
        out = sdc.delete_song_document(a["document_id"], st=self.ws.session)
        self.assertTrue(out["blob_kept_for_other_rows"])
        data, err = sdc.load_song_document_bytes(b["document_id"], st=self.ws.session)
        self.assertEqual(err, "")
        self.assertEqual(data, MINIMAL_PDF)

    def test_deleting_an_unknown_document_says_so(self):
        self.assertEqual(
            sdc.delete_song_document("nope", st=self.ws.session)["error"],
            "document_not_found")


class TheSameFileIsStoredOnce(StoreCase):
    def test_a_duplicate_upload_reuses_the_stored_blob(self):
        first = self.save(title="First", data=MINIMAL_PDF)
        second = self.save(owner=self.owner("custom", "custom::z", "Other"),
                           title="Second", data=MINIMAL_PDF)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["row"]["local_path"], second["row"]["local_path"])

    def test_a_different_file_is_stored_separately(self):
        first = self.save(title="First", data=MINIMAL_PDF)
        second = self.save(title="Second", data=SECOND_PDF)
        self.assertFalse(second["reused"])
        self.assertNotEqual(first["row"]["local_path"], second["row"]["local_path"])


class ItSurvivesAFreshSession(StoreCase):
    def test_documents_come_back_with_an_empty_session(self):
        self.save(title="Persisted")
        self.ws.session.clear()          # a new run of the app, same workspace on disk
        rows = sdc.documents_for_owner(self.owner(), st=self.ws.session)
        self.assertEqual([r["title"] for r in rows], ["Persisted"])

    def test_a_document_survives_a_catalog_merge(self):
        """merge_catalog rebuilds the catalog from named keys; an unnamed kind vanishes."""
        self.save(title="Still here")
        before = json.loads(self.ws.catalog_path().read_text(encoding="utf-8"))
        merged = media_state.merge_catalog(before, {})
        self.assertEqual([r["title"] for r in merged["song_documents"]], ["Still here"])

    def test_merging_keeps_the_other_media_kinds_untouched(self):
        self.save(title="Doc")
        catalog = json.loads(self.ws.catalog_path().read_text(encoding="utf-8"))
        for key in ("uploaded_recordings", "multitrack_sessions",
                    "tone_takes", "multitrack_exports"):
            self.assertIn(key, catalog)
            self.assertEqual(catalog[key], [])


class ATagIsNotTheSongsKey(unittest.TestCase):
    """Selecting a reference must never change what the song is played in."""

    def test_the_catalog_never_writes_practice_key_state(self):
        source = Path(sdc.__file__).read_text(encoding="utf-8")
        for forbidden in ("set_practice_concert_key", "practice_key_state",
                          "display_key", "set_display_key"):
            self.assertNotIn(forbidden, source)

    def test_the_key_tag_is_stored_as_written_and_nothing_more(self):
        row = media_state.migrate_song_document(
            {"document_id": "d", "source_type": "catalog", "source_id": "x",
             "key_tag": "Eb concert", "storage_ref": "supabase://b/k"})
        self.assertEqual(row["key_tag"], "Eb concert")
        self.assertNotIn("practice_key", row)
        self.assertNotIn("display_key", row)


class TheRowSchemaBehaves(unittest.TestCase):
    def test_a_tombstone_hides_the_row(self):
        rows = [
            {"document_id": "a", "source_type": "catalog", "source_id": "x",
             "title": "Gone", "updated_at": "2026-01-01T00:00:00+00:00"},
            {"document_id": "a", "deleted": True,
             "updated_at": "2026-01-02T00:00:00+00:00"},
        ]
        self.assertEqual(media_state.normalize_song_documents(rows), [])

    def test_an_unknown_source_type_is_dropped_to_unowned(self):
        row = media_state.migrate_song_document(
            {"document_id": "d", "source_type": "sbi_preview", "source_id": "x"})
        self.assertEqual(row["source_type"], "")
        self.assertEqual(row["source_id"], "")

    def test_a_row_with_no_title_still_has_one(self):
        row = media_state.migrate_song_document(
            {"document_id": "d", "filename": "scan.pdf"})
        self.assertEqual(row["title"], "scan.pdf")

    def test_the_newer_row_wins_a_merge(self):
        old = {"document_id": "a", "title": "Old", "source_type": "catalog",
               "source_id": "x", "updated_at": "2026-01-01T00:00:00+00:00"}
        new = {"document_id": "a", "title": "New", "source_type": "catalog",
               "source_id": "x", "updated_at": "2026-02-01T00:00:00+00:00"}
        merged = media_state.merge_catalog({"song_documents": [old]},
                                           {"song_documents": [new]})
        self.assertEqual([r["title"] for r in merged["song_documents"]], ["New"])

    def test_the_summary_line_names_the_tags_it_has(self):
        self.assertEqual(
            sdc.summarize_document({"title": "Lick", "instrument_tag": "Alto Sax",
                                    "key_tag": "Eb", "page_count": 2}),
            "Lick · Alto Sax / Eb · 2 pages")
        self.assertEqual(sdc.summarize_document({"title": "Plain"}), "Plain")


if __name__ == "__main__":
    unittest.main()

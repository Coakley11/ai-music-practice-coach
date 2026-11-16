"""References can be photographs, and the cloud copy must declare what the file really is.

Measured on a phone: a PDF uploaded, the local copy was kept, and the cloud copy failed with

    415 invalid_mime_type: application/pdf is not supported

``upload_song_document_cloud`` declared ``application/pdf`` for every reference whatever it
held. That is wrong for a photograph, and for the PDF it was refused outright by the private
bucket - which accepts audio to the same bucket, so it is restricting types, not failing.

These tests cover what the app controls: the type it declares, the second attempt when a type
is refused, the message it gives when both are refused, and the fact that a photograph is an
acceptable reference in the first place. Whether the bucket allows those types is storage
configuration and cannot be asserted from here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import media_storage  # noqa: E402
import upload_media  # noqa: E402

PDF = b"%PDF-1.7\n1 0 obj\n"
PNG = b"\x89PNG\r\n\x1a\nIHDR...."
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
HEIF = b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00"


class WhatAReferenceMayBe(unittest.TestCase):
    def test_a_phone_photograph_is_an_acceptable_reference(self) -> None:
        for ext in ("jpg", "jpeg", "png", "heic", "heif"):
            self.assertIn(ext, upload_media.UPLOAD_DOCUMENT_FILE_TYPES,
                          f"{ext} is what a phone produces")
        self.assertIn("pdf", upload_media.UPLOAD_DOCUMENT_FILE_TYPES)

    def test_the_limit_is_still_stated_and_still_fifty_megabytes(self) -> None:
        caption = upload_media.document_limit_caption()
        self.assertIn(str(upload_media.DOCUMENT_MAX_SIZE_MB), caption)
        self.assertEqual(upload_media.DOCUMENT_MAX_SIZE_MB, 50)
        for word in ("PDF", "JPG", "PNG", "HEIC"):
            self.assertIn(word, caption, "the caption must name what it accepts")


class TheTypeIsTakenFromTheFile(unittest.TestCase):
    def test_each_format_is_recognised_by_its_content(self) -> None:
        self.assertEqual(upload_media.document_mime_type(PDF), "application/pdf")
        self.assertEqual(upload_media.document_mime_type(PNG), "image/png")
        self.assertEqual(upload_media.document_mime_type(JPEG), "image/jpeg")
        self.assertEqual(upload_media.document_mime_type(HEIC), "image/heic")
        self.assertEqual(upload_media.document_mime_type(HEIF), "image/heif")

    def test_the_content_beats_a_filename_that_disagrees(self) -> None:
        """An extension is a claim; the store checks the bytes."""
        self.assertEqual(
            upload_media.document_mime_type(JPEG, filename="actually-a.png"), "image/jpeg")
        self.assertEqual(
            upload_media.document_mime_type(PDF, filename="scan.jpg"), "application/pdf")

    def test_the_name_is_used_only_when_the_bytes_say_nothing(self) -> None:
        self.assertEqual(upload_media.document_mime_type(b"", filename="IMG_0042.HEIC"),
                         "image/heic")
        self.assertEqual(upload_media.document_mime_type(b"", filename="sheet.pdf"),
                         "application/pdf")

    def test_an_unknown_file_is_not_guessed_at(self) -> None:
        self.assertEqual(upload_media.document_mime_type(b"not music", filename="notes.txt"), "")

    def test_images_are_distinguishable_from_pdfs(self) -> None:
        self.assertTrue(upload_media.is_document_image_mime("image/jpeg"))
        self.assertFalse(upload_media.is_document_image_mime("application/pdf"))


class WhenTheStoreRefusesTheType(unittest.TestCase):
    def setUp(self) -> None:
        self.attempts: list[str] = []
        self.refuse: set[str] = set()
        self._orig = {
            "enabled": media_storage._cloud_storage_enabled,
            "client": media_storage._service_storage_client,
            "uid": media_storage._resolve_user_id,
        }
        media_storage._cloud_storage_enabled = lambda: True
        media_storage._resolve_user_id = lambda: "user-1"

        outer = self

        class Storage:
            def upload(self, key, data, file_options=None):
                content_type = str((file_options or {}).get("content-type") or "")
                outer.attempts.append(content_type)
                if content_type in outer.refuse:
                    raise RuntimeError(
                        f"415 invalid_mime_type: {content_type} is not supported")
                return {"Key": key}

        class Client:
            storage = type("S", (), {"from_": staticmethod(lambda bucket: Storage())})()

        media_storage._service_storage_client = lambda: Client()

    def tearDown(self) -> None:
        media_storage._cloud_storage_enabled = self._orig["enabled"]
        media_storage._service_storage_client = self._orig["client"]
        media_storage._resolve_user_id = self._orig["uid"]

    def test_a_pdf_is_declared_as_a_pdf(self) -> None:
        ref, err = media_storage.upload_song_document_cloud("ws", "doc1", PDF)
        self.assertTrue(ref)
        self.assertEqual(err, "")
        self.assertEqual(self.attempts, ["application/pdf"])

    def test_a_photograph_is_declared_as_an_image_not_a_pdf(self) -> None:
        """The old code declared application/pdf for everything, photographs included."""
        ref, err = media_storage.upload_song_document_cloud("ws", "doc2", JPEG)
        self.assertTrue(ref)
        self.assertEqual(self.attempts, ["image/jpeg"])

    def test_a_refused_type_is_retried_as_an_opaque_blob(self) -> None:
        self.refuse = {"application/pdf"}
        ref, err = media_storage.upload_song_document_cloud("ws", "doc3", PDF)
        self.assertTrue(ref, "the reference still reached the cloud")
        self.assertEqual(self.attempts,
                         ["application/pdf", media_storage.DOCUMENT_FALLBACK_CONTENT_TYPE])

    def test_when_both_are_refused_the_message_names_the_cause_and_the_fix(self) -> None:
        self.refuse = {"application/pdf", media_storage.DOCUMENT_FALLBACK_CONTENT_TYPE}
        ref, err = media_storage.upload_song_document_cloud("ws", "doc4", PDF)
        self.assertEqual(ref, "")
        self.assertIn("refused the file type application/pdf", err)
        self.assertIn("saved on this device", err)
        for mime in ("application/pdf", "image/jpeg", "image/heic"):
            self.assertIn(mime, err, "the message must say which types to allow")

    def test_a_failure_that_is_not_about_the_type_is_not_retried(self) -> None:
        """Only a TYPE refusal earns a second attempt; a network error is reported as it is."""
        outer = self

        class Storage:
            def upload(self, key, data, file_options=None):
                outer.attempts.append(str((file_options or {}).get("content-type") or ""))
                raise RuntimeError("connection reset by peer")

        class Client:
            storage = type("S", (), {"from_": staticmethod(lambda bucket: Storage())})()

        media_storage._service_storage_client = lambda: Client()
        ref, err = media_storage.upload_song_document_cloud("ws", "doc5", PDF)
        self.assertEqual(ref, "")
        self.assertIn("connection reset", err)
        self.assertEqual(len(self.attempts), 1, "no pointless second attempt")


if __name__ == "__main__":
    unittest.main()

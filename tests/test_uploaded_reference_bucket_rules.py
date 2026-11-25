"""References against the bucket rules set on 2026-11-19 (Daniel AI Suite, music-media):

    file size limit 50 MB · restrict MIME types ON ·
    allowed: audio/*, application/pdf, image/jpeg, image/png, image/heic, image/heif

A stand-in store enforces exactly those rules (the real project is not touched), and each
reference goes through the app's own save -> list -> reopen path: a PDF and every photo type
reach the cloud copy and come back byte-identical; audio still uploads; anything else is refused
honestly.
"""

from __future__ import annotations

import fnmatch
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import media_storage  # noqa: E402

ALLOWED = ("audio/*", "application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif")
LIMIT = 50 * 1024 * 1024

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _image(fmt: str, brand: bytes = b"") -> bytes:
    """A real tiny picture: references that cannot be opened are refused (Slice 1), so placeholder bytes are too."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (24, 32), "white").save(buf, format=fmt)
    data = buf.getvalue()
    return data[:8] + brand + data[12:] if brand else data


PNG, JPEG = _image("PNG"), _image("JPEG")
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC, HEIF = _image("HEIF"), _image("HEIF", brand=b"mif1")
except ImportError:  # without the decoder HEIC is recognised by its header and not opened
    HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00" + b"\x00" * 64
    HEIF = b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00" + b"\x00" * 64


class RuleStore:
    """The bucket as configured: refuses a type or size the way Supabase Storage does."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.refused: list[str] = []

    def from_(self, bucket):
        store = self

        class B:
            def upload(self, key, data, file_options=None):
                ctype = str((file_options or {}).get("content-type") or "")
                if not any(fnmatch.fnmatch(ctype, pat) for pat in ALLOWED):
                    store.refused.append(ctype)
                    raise RuntimeError(f"415 invalid_mime_type: mime type {ctype} is not supported")
                if len(data) > LIMIT:
                    raise RuntimeError("413 Payload too large: The object exceeded the maximum allowed size")
                store.objects[f"{bucket}/{key}"] = (bytes(data), ctype)
                return {"Key": key}

            def download(self, key):
                return store.objects[f"{bucket}/{key}"][0]

        return B()


class Client:
    def __init__(self, store):
        self.storage = store


class BucketRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="um-bucket-")
        self._env = os.environ.get("MUSIC_APP_DATA_DIR")
        os.environ["MUSIC_APP_DATA_DIR"] = self.tmp
        # The data root is fixed at import; every workspace path is built from this global at
        # call time, so pointing it at the temp folder keeps the checkout's data/ untouched.
        import suite_workspace

        self._data_dir = suite_workspace.DATA_DIR
        suite_workspace.DATA_DIR = Path(self.tmp)
        self.store = RuleStore()
        self._orig = (media_storage._cloud_storage_enabled, media_storage._service_storage_client)
        media_storage._cloud_storage_enabled = lambda: True
        media_storage._service_storage_client = lambda: Client(self.store)

    def tearDown(self):
        import suite_workspace

        suite_workspace.DATA_DIR = self._data_dir
        media_storage._cloud_storage_enabled, media_storage._service_storage_client = self._orig
        if self._env is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = self._env

    def test_every_reference_type_is_accepted_with_its_real_type(self):
        for name, data, want in (("pdf", PDF, "application/pdf"), ("png", PNG, "image/png"),
                                 ("jpeg", JPEG, "image/jpeg"), ("heic", HEIC, "image/heic"),
                                 ("heif", HEIF, "image/heif")):
            with self.subTest(name):
                raw, mime, err = media_storage.validate_document_bytes(data)
                self.assertEqual((mime, err), (want, ""))
                out = media_storage.persist_song_document("daniel", f"doc-{name}", raw,
                                                          user_id="test-user", mime_type=mime)
                self.assertEqual(out["storage_status"], "cloud", out)
                ref = out["storage_ref"]
                key = next(k for k in self.store.objects if k.endswith(f"doc-{name}") or f"doc-{name}" in k)
                self.assertEqual(self.store.objects[key], (data, want))
        self.assertEqual(self.store.refused, [])

    def test_a_renamed_text_file_is_refused_before_storage(self):
        raw, mime, err = media_storage.validate_document_bytes(b"just notes, not a picture")
        self.assertIsNone(raw)
        self.assertEqual(err, "unsupported_document_type")
        self.assertEqual(self.store.objects, {})

    def test_audio_still_uploads(self):
        ref, err = media_storage.upload_recording_cloud("daniel", "rec-1", b"RIFF" + b"\x00" * 64,
                                                       filename="take.wav", mime_type="audio/wav",
                                                       user_id="test-user")
        self.assertTrue(ref, err)
        self.assertEqual(err, "")

    def test_a_video_upload_is_now_refused_by_the_bucket(self):
        """Upload Analysis stores videos as video/mp4, which the new list does not allow."""
        ref, err = media_storage.upload_recording_cloud("daniel", "vid-1", b"\x00" * 64,
                                                       filename="clip.mp4", mime_type="video/mp4",
                                                       user_id="test-user")
        self.assertEqual(ref, "")
        self.assertIn("invalid_mime_type", err)


class SaveAndReopen(BucketRules):
    """The app's own path: save_song_document -> list -> load_song_document_bytes."""

    def _owner(self):
        import song_document_catalog as sdc

        orig = sdc.active_song_owner
        sdc.active_song_owner = lambda session, st=None: {
            "owner_source": "catalog", "owner_key": "Attention|Charlie Puth", "song_title": "Attention"}
        return sdc, orig

    def test_a_photo_and_a_pdf_save_and_reopen_byte_identical(self):
        sdc, orig = self._owner()
        try:
            for name, data, want in (("pdf", PDF, "application/pdf"), ("png", PNG, "image/png"),
                                     ("heic", HEIC, "image/heic")):
                with self.subTest(name):
                    res = sdc.save_song_document({}, data, filename=f"ref.{name}")
                    self.assertTrue(res["ok"], res)
                    self.assertEqual(res["storage_status"], "cloud", res)
                    row = res["row"]
                    self.assertEqual(row.get("mime_type"), want)
                    back, err = sdc.load_song_document_bytes(row["document_id"])
                    self.assertEqual((back, err), (data, ""))
                    # A new device / a replaced server has no local copy: it must reopen from the cloud.
                    local = media_storage.song_document_local_path("daniel", row["local_path"])
                    self.assertTrue(local is not None and local.is_file())
                    local.unlink()
                    back, err = sdc.load_song_document_bytes(row["document_id"])
                    self.assertEqual((back, err), (data, ""), "reopened from the cloud copy")
        finally:
            sdc.active_song_owner = orig


if __name__ == "__main__":
    unittest.main()

"""My Uploaded Melodies, Slice 1 (2026-11-22): photographed sheet music - JPEG, PNG and HEIC - beside PDFs.

* a photo is accepted only if it really decodes (a JPEG cut off mid-upload is refused), and only up to 50 MP;
* the reader sees the page upright (the phone's EXIF rotation applied), undistorted, within the render budget;
* HEIC is drawn when ``pillow-heif`` is installed (it is in requirements.txt) and offered as a download otherwise;
* a Reading size control (Fit / Large / Extra large) lets a phone read notation, scrolling sideways.

HEIC tests run only where ``pillow-heif`` is importable.
"""
from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest import mock

import media_storage
import song_document_panel as panel
import upload_media

ROOT = Path(__file__).resolve().parents[1]

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow ships with Streamlit
    Image = None

try:
    import pillow_heif  # noqa: F401

    HAVE_HEIF = True
except Exception:
    HAVE_HEIF = False


def _page(w: int = 600, h: int = 800, fmt: str = "JPEG", **save) -> bytes:
    """A 'photographed page': white with a black band near the top, so orientation can be checked."""
    im = Image.new("RGB", (w, h), (255, 255, 255))
    for y in range(0, max(1, h // 10)):
        for x in range(w):
            im.putpixel((x, y), (0, 0, 0))
    buf = io.BytesIO()
    if fmt == "HEIF":
        import pillow_heif

        pillow_heif.register_heif_opener()
        im.save(buf, format="HEIF", quality=80)
    else:
        im.save(buf, format=fmt, **save)
    return buf.getvalue()


@unittest.skipIf(Image is None, "Pillow not installed")
class APhotoIsKeptOnlyIfItReallyDecodes(unittest.TestCase):
    def test_jpeg_and_png_are_accepted_with_their_real_type(self) -> None:
        for fmt, mime in (("JPEG", "image/jpeg"), ("PNG", "image/png")):
            raw, got, err = media_storage.validate_document_bytes(_page(fmt=fmt))
            self.assertEqual((got, err), (mime, ""), fmt)
            self.assertIsNotNone(raw)

    def test_a_pdf_is_still_a_pdf(self) -> None:
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        raw, mime, err = media_storage.validate_document_bytes(pdf)
        self.assertEqual(mime, "application/pdf", err)

    def test_a_jpeg_cut_off_mid_upload_is_refused(self) -> None:
        data = _page(1200, 1600)
        raw, mime, err = media_storage.validate_document_bytes(data[: len(data) // 2])
        self.assertIsNone(raw)
        self.assertEqual(err, "image_unreadable")

    def test_a_photo_over_50_megapixels_is_refused_from_its_header(self) -> None:
        with mock.patch.object(upload_media, "DOCUMENT_MAX_IMAGE_PIXELS", 100_000):
            raw, mime, err = media_storage.validate_document_bytes(_page(600, 800))
        self.assertEqual((raw, err), (None, "image_too_many_pixels"))

    def test_other_formats_and_junk_are_refused(self) -> None:
        gif = io.BytesIO(); Image.new("RGB", (10, 10)).save(gif, format="GIF")
        for data in (gif.getvalue(), b"not an image at all", b"\x89PNG\r\n\x1a\n" + b"\0" * 40):
            raw, mime, err = media_storage.validate_document_bytes(data)
            self.assertIsNone(raw, err)
            self.assertIn(err, ("unsupported_document_type", "image_unreadable"))

    def test_the_failure_messages_say_what_went_wrong(self) -> None:
        self.assertIn("damaged or incomplete", panel._explain("image_unreadable"))
        self.assertIn("50 megapixels", panel._explain("image_too_many_pixels"))


@unittest.skipIf(Image is None, "Pillow not installed")
class TheReaderSeesThePageUprightAndUndistorted(unittest.TestCase):
    def _decode(self, data: bytes):
        return Image.open(io.BytesIO(data))

    def test_a_phone_photo_is_turned_upright(self) -> None:
        # A portrait page stored landscape with EXIF Orientation 6 ("rotate 90 CW to view").
        stored = Image.new("RGB", (800, 600), (255, 255, 255))
        exif = Image.Exif(); exif[0x0112] = 6
        buf = io.BytesIO(); stored.save(buf, format="JPEG", exif=exif)
        out = self._decode(panel._render_image_jpeg(buf.getvalue(), "image/jpeg", 760))
        self.assertLess(out.size[0], out.size[1], out.size)          # portrait, as photographed

    def test_the_shape_is_kept_and_the_width_respected(self) -> None:
        out = self._decode(panel._render_image_jpeg(_page(3000, 4000), "image/jpeg", 760))
        self.assertLessEqual(out.size[0], 760)
        self.assertAlmostEqual(out.size[0] / out.size[1], 3000 / 4000, places=2)

    def test_the_render_budget_bounds_a_large_zoom(self) -> None:
        with mock.patch.object(upload_media, "DOCUMENT_MAX_RENDER_PIXELS", 200_000):
            out = self._decode(panel._render_image_jpeg(_page(3000, 4000), "image/jpeg", 2420))
        self.assertLessEqual(out.size[0] * out.size[1], 200_000 * 1.02)

    def test_a_transparent_png_reads_on_white(self) -> None:
        im = Image.new("RGBA", (200, 100), (0, 0, 0, 0)); buf = io.BytesIO(); im.save(buf, format="PNG")
        out = self._decode(panel._render_image_jpeg(buf.getvalue(), "image/png", 760)).convert("RGB")
        self.assertEqual(out.getpixel((10, 10)), (255, 255, 255))

    def test_an_undecodable_file_gives_none_so_the_viewer_falls_back(self) -> None:
        self.assertIsNone(panel._render_image_jpeg(b"\xff\xd8\xff garbage", "image/jpeg", 760))


@unittest.skipUnless(HAVE_HEIF and Image is not None, "pillow-heif not installed")
class AnIPhoneHeicPhoto(unittest.TestCase):
    def setUp(self) -> None:
        upload_media._HEIF_READY = None

    def test_is_identified_validated_and_drawn(self) -> None:
        data = _page(600, 800, fmt="HEIF")
        self.assertIn(upload_media.document_mime_type(data), ("image/heic", "image/heif"))
        raw, mime, err = media_storage.validate_document_bytes(data)
        self.assertEqual(err, "", mime)
        out = Image.open(io.BytesIO(panel._render_image_jpeg(data, mime, 760)))
        self.assertEqual(out.format, "JPEG")
        self.assertLess(out.size[0], out.size[1])


@unittest.skipIf(Image is None, "Pillow not installed")
class WithoutAHeicDecoder(unittest.TestCase):
    def test_a_heic_photo_is_kept_and_offered_for_download(self) -> None:
        heic_like = b"\0\0\0\x18ftypheic\0\0\0\0mif1heic" + b"\0" * 64
        with mock.patch.object(upload_media, "heif_support", return_value=False):
            raw, mime, err = media_storage.validate_document_bytes(heic_like)
            self.assertEqual((mime, err), ("image/heic", ""))
            self.assertIsNone(panel._render_image_jpeg(heic_like, "image/heic", 760))
        src = (ROOT / "song_document_panel.py").read_text(encoding="utf-8")
        self.assertIn("This photo is in HEIC format, which cannot be shown here. Download it to view it.", src)


class ReadingSizeAndWording(unittest.TestCase):
    SRC = (ROOT / "song_document_panel.py").read_text(encoding="utf-8")

    def test_fit_large_extra_large(self) -> None:
        self.assertEqual(panel.ZOOM_LEVELS, {"Fit": 1.0, "Large": 1.6, "Extra large": 2.2})

    def test_larger_sizes_scroll_sideways_without_stretching(self) -> None:
        body = self.SRC[self.SRC.index("def _show_page_image("):self.SRC.index("def _cached_helpers(")]
        self.assertIn("overflow-x:auto", body)
        self.assertIn("height:auto", body)
        self.assertIn("width:{pct}%", body)

    def test_pdf_pages_and_photos_both_use_the_reading_size(self) -> None:
        body = self.SRC[self.SRC.index("def _preview("):self.SRC.index("def render_song_document_reference(")]
        self.assertEqual(body.count("_zoom_choice(st, reader)"), 2)
        self.assertEqual(body.count("_show_page_image(st, "), 2)

    def test_each_reader_keeps_its_own_size(self) -> None:
        self.assertNotEqual(panel._reader_slug("::bk::doc-1::"), panel._reader_slug("::bk::doc-2::"))

    def test_the_uploader_offers_photos(self) -> None:
        self.assertIn('"Add sheet music for this song (PDF or photo)"', self.SRC)
        self.assertNotIn("Choose at least one PDF first.", self.SRC)
        self.assertEqual(set(upload_media.UPLOAD_DOCUMENT_FILE_TYPES), {"pdf", "jpg", "jpeg", "png", "heic", "heif"})

    def test_cloud_installs_the_readers(self) -> None:
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("pymupdf>=1.24,<2", req)
        self.assertIn("pillow-heif>=0.18,<2", req)


if __name__ == "__main__":
    unittest.main()

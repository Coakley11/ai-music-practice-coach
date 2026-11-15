"""My Uploaded Melodies: a real scanned-music PDF must be accepted, and refusals must say both sizes.

The musician's 26.5 MB scan of a sheet-music page was refused. The limit that refused it was 25 MB
and was stated nowhere; the only size visible in the product was the **500 MB recording** limit,
which belongs to audio uploads and never applied to documents. So the refusal looked arbitrary and
the stated maximum was twenty times the real one.

These tests pin the corrected behaviour, including a PDF built at the user's actual size so the
acceptance is not a matter of arithmetic about a constant.
"""

from __future__ import annotations

import unittest


def pdf_bytes(size_bytes: int, *, pages: int = 1, trailer: bool = True) -> bytes:
    """A byte string that passes the real validator's structural checks, at a chosen size.

    Not a real document - the validator checks the %PDF- signature, the page count and the %%EOF
    trailer, which is exactly what a truncated or mislabelled upload fails.
    """
    head = b"%PDF-1.7\n"
    body = b"".join(b"/Type /Page\n" for _ in range(pages))
    tail = b"\n%%EOF\n" if trailer else b"\n"
    filler_len = max(0, size_bytes - len(head) - len(body) - len(tail))
    return head + body + (b"0" * filler_len) + tail


class TheLimitIsFiftyMegabytes(unittest.TestCase):
    def test_the_default_document_limit_is_50_mb(self) -> None:
        from upload_media import DOCUMENT_MAX_SIZE_BYTES, DOCUMENT_MAX_SIZE_MB

        self.assertEqual(DOCUMENT_MAX_SIZE_MB, 50)
        self.assertEqual(DOCUMENT_MAX_SIZE_BYTES, 50 * 1024 * 1024)

    def test_it_is_not_the_recording_limit(self) -> None:
        """The two limits are different things; conflating them is what misinformed the musician."""
        from upload_media import DOCUMENT_MAX_SIZE_MB, UPLOAD_MAX_SIZE_MB

        self.assertEqual(UPLOAD_MAX_SIZE_MB, 500)
        self.assertLess(DOCUMENT_MAX_SIZE_MB, UPLOAD_MAX_SIZE_MB)

    def test_the_override_still_works_and_cannot_exceed_the_server_ceiling(self) -> None:
        """Resolved by calling the resolver, NOT by reloading the module.

        An earlier version of this test used ``importlib.reload(upload_media)``, which swaps the
        module object for everyone: three tests in ``test_upload_media.py`` that had already
        imported names from it then failed, purely because this file ran first. A test must not be
        able to break another one.
        """
        import os

        from upload_media import UPLOAD_MAX_SIZE_MB, _document_max_size_mb

        original = os.environ.get("MUSIC_DOCUMENT_MAX_SIZE_MB")
        try:
            os.environ["MUSIC_DOCUMENT_MAX_SIZE_MB"] = "120"
            self.assertEqual(_document_max_size_mb(), 120)

            os.environ["MUSIC_DOCUMENT_MAX_SIZE_MB"] = "9000"
            self.assertEqual(
                _document_max_size_mb(), UPLOAD_MAX_SIZE_MB,
                "a limit above server.maxUploadSize could never be enforced",
            )

            os.environ["MUSIC_DOCUMENT_MAX_SIZE_MB"] = "nonsense"
            self.assertEqual(_document_max_size_mb(), 50)

            os.environ.pop("MUSIC_DOCUMENT_MAX_SIZE_MB", None)
            self.assertEqual(_document_max_size_mb(), 50)
        finally:
            if original is None:
                os.environ.pop("MUSIC_DOCUMENT_MAX_SIZE_MB", None)
            else:
                os.environ["MUSIC_DOCUMENT_MAX_SIZE_MB"] = original


class TheUsersFileIsAccepted(unittest.TestCase):
    def test_a_26_5_mb_pdf_passes_validation(self) -> None:
        """The exact size that was refused: 27,090 KB."""
        from media_storage import validate_pdf_bytes

        raw, err = validate_pdf_bytes(pdf_bytes(27090 * 1024))
        self.assertEqual(err, "")
        self.assertIsNotNone(raw)
        self.assertEqual(len(raw or b""), 27090 * 1024)

    def test_a_file_at_the_limit_is_accepted(self) -> None:
        from media_storage import validate_pdf_bytes
        from upload_media import DOCUMENT_MAX_SIZE_BYTES

        raw, err = validate_pdf_bytes(pdf_bytes(DOCUMENT_MAX_SIZE_BYTES))
        self.assertEqual(err, "")
        self.assertIsNotNone(raw)

    def test_a_file_over_the_limit_is_still_refused(self) -> None:
        from media_storage import validate_pdf_bytes
        from upload_media import DOCUMENT_MAX_SIZE_BYTES

        raw, err = validate_pdf_bytes(pdf_bytes(DOCUMENT_MAX_SIZE_BYTES + 1024))
        self.assertIsNone(raw)
        self.assertEqual(err, "document_too_large")

    def test_a_malformed_or_truncated_file_is_still_refused(self) -> None:
        from media_storage import validate_pdf_bytes

        self.assertEqual(validate_pdf_bytes(b"not a pdf at all" * 100)[1], "not_a_pdf")
        self.assertEqual(
            validate_pdf_bytes(pdf_bytes(20000, trailer=False))[1], "pdf_truncated")
        self.assertEqual(validate_pdf_bytes(b"")[1], "missing_document")
        self.assertEqual(validate_pdf_bytes(None)[1], "missing_document")
        self.assertEqual(validate_pdf_bytes("a string")[1], "invalid_document_type")

    def test_a_page_bomb_is_still_refused(self) -> None:
        """Bytes never bounded the work: a small file can declare thousands of pages."""
        from media_storage import validate_pdf_bytes
        from upload_media import DOCUMENT_MAX_PAGES

        raw, err = validate_pdf_bytes(pdf_bytes(60000, pages=DOCUMENT_MAX_PAGES + 50))
        self.assertIsNone(raw)
        self.assertEqual(err, "too_many_pages")


class TheMessagesSayWhatIsWrong(unittest.TestCase):
    def test_the_limit_is_stated_before_a_file_is_chosen(self) -> None:
        from upload_media import DOCUMENT_MAX_SIZE_MB, document_limit_caption

        caption = document_limit_caption()
        self.assertIn(str(DOCUMENT_MAX_SIZE_MB), caption)
        self.assertIn("MB", caption)
        self.assertIn("PDF", caption)

    def test_a_refusal_gives_the_file_size_and_the_limit(self) -> None:
        from upload_media import document_too_large_message

        msg = document_too_large_message(56 * 1024 * 1024, filename="scan.pdf")
        self.assertIn("56.0 MB", msg)
        self.assertIn("50 MB", msg)
        self.assertIn("scan.pdf", msg)
        self.assertNotIn("too large", msg.lower(), "the uninformative wording is gone")

    def test_the_message_and_the_rule_cannot_disagree(self) -> None:
        """Both read ONE value, so a configured override moves them together.

        Deliberately not tested by reloading the module - the override is read at import, so
        validation would not follow a mid-process change either, and reloading broke other tests.
        What matters is that the number the musician is shown is the number that refused the file.
        """
        from media_storage import validate_pdf_bytes
        from upload_media import (
            DOCUMENT_MAX_SIZE_BYTES,
            DOCUMENT_MAX_SIZE_MB,
            document_limit_caption,
            document_too_large_message,
        )

        self.assertEqual(DOCUMENT_MAX_SIZE_BYTES, DOCUMENT_MAX_SIZE_MB * 1024 * 1024)
        stated = f"{DOCUMENT_MAX_SIZE_MB} MB"
        self.assertIn(stated, document_limit_caption())

        over = DOCUMENT_MAX_SIZE_BYTES + 1024
        self.assertEqual(validate_pdf_bytes(pdf_bytes(over))[1], "document_too_large")
        message = document_too_large_message(over)
        self.assertIn(stated, message, "the message quotes a different limit from the rule")
        self.assertIn(f"{over / (1024 * 1024):.1f} MB", message)

    def test_the_panel_uses_the_size_aware_refusal(self) -> None:
        from song_document_panel import _explain_failure

        msg = _explain_failure("big.pdf", "document_too_large", 56 * 1024 * 1024)
        self.assertIn("56.0 MB", msg)
        self.assertIn("50 MB", msg)

    def test_other_refusals_keep_their_wording(self) -> None:
        from song_document_panel import _explain_failure

        self.assertIn("not a PDF", _explain_failure("x.pdf", "not_a_pdf", 10))
        self.assertIn("incomplete", _explain_failure("x.pdf", "pdf_truncated", 10))
        self.assertIn("open a song first", _explain_failure("x.pdf", "unknown_song", 10))
        self.assertIn("x.pdf", _explain_failure("x.pdf", "not_a_pdf", 10))


class TheSaveButtonCarriesTheFloppyDisk(unittest.TestCase):
    def test_the_label_is_the_shared_convention(self) -> None:
        from music_feature_icons import action_label

        self.assertEqual(action_label("save", "Save to this song"), "💾 Save to this song")

    def test_the_panel_builds_its_label_that_way(self) -> None:
        from pathlib import Path

        panel = (Path(__file__).resolve().parents[1]
                 / "song_document_panel.py").read_text(encoding="utf-8")
        self.assertIn('action_label("save", "Save to this song")', panel)
        self.assertIn("st.form_submit_button(_save_label", panel)


class TheRenderingBudgetIsUnchanged(unittest.TestCase):
    """A bigger byte limit must not mean bigger rendering: those limits are separate on purpose."""

    def test_the_page_and_pixel_budgets_are_untouched(self) -> None:
        from upload_media import DOCUMENT_MAX_PAGES, DOCUMENT_MAX_RENDER_PIXELS

        self.assertEqual(DOCUMENT_MAX_PAGES, 500)
        self.assertEqual(DOCUMENT_MAX_RENDER_PIXELS, 4_000_000)

    def test_a_huge_page_is_scaled_down_rather_than_rendered_whole(self) -> None:
        """The panel's own budget arithmetic: a metre-wide page must not be rendered at full size."""
        from upload_media import DOCUMENT_MAX_RENDER_PIXELS

        page_w, page_h = 5000.0, 7000.0           # far beyond A4 at any sane dpi
        budget = (DOCUMENT_MAX_RENDER_PIXELS / (page_w * page_h)) ** 0.5
        self.assertLess(budget, 1.0, "a page this large must be scaled down")
        self.assertLessEqual((page_w * budget) * (page_h * budget),
                             DOCUMENT_MAX_RENDER_PIXELS + 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

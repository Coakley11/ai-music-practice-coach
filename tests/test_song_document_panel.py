"""The Practice-page panel: what it shows, and what it must never touch.

A reference is something to read while you play. Opening one is not a musical decision,
so the panel must not be able to change the Practice Key, the instrument, the active song
or any backing setting - including when the document carries a key *tag*, which is the
musician's note about the page and not an instruction to transpose anything.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import media_state
import song_document_panel as panel

SOURCE = Path(panel.__file__).read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """The module with comments and string literals removed.

    A prose scan is not a code scan: this file's own docstring says the panel touches no
    backing setting, and a naive search for "backing" finds that sentence. Only what the
    module actually executes is interesting here.
    """
    import io as _io
    import tokenize

    out = []
    for tok in tokenize.generate_tokens(_io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(tok.string)
    return " ".join(out)


CODE = _code_only(SOURCE)


class ItTouchesNothingMusical(unittest.TestCase):
    def test_it_never_writes_practice_key_or_instrument_state(self):
        for forbidden in (
            "practice_key_state", "set_practice_concert_key", "display_key",
            "set_display_key", "concert_key", "written_key", "transpos",
            "instrument\"]", "instrument']", "backing", "bpm", "groove",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CODE)

    def test_every_session_key_it_writes_is_its_own(self):
        """Any st.session_state[...] assignment must use the panel's own prefix."""
        writes = re.findall(r"st\.session_state\[([^\]]+)\]\s*=", SOURCE)
        self.assertTrue(writes, "expected the panel to write some state")
        for expr in writes:
            with self.subTest(key=expr):
                self.assertTrue(
                    expr.strip().rstrip(")").endswith("_KEY")
                    or expr.strip().startswith(("SELECTED", "CONFIRM", "PAGE", "NOTICE")),
                    f"{expr} is not one of the panel's own keys",
                )

    def test_its_key_constants_all_share_the_panel_prefix(self):
        for name in ("SELECTED_KEY", "CONFIRM_KEY", "PAGE_KEY", "UPLOAD_KEY", "NOTICE_KEY"):
            with self.subTest(constant=name):
                self.assertTrue(getattr(panel, name).startswith(panel.KEY_PREFIX))

    def test_the_key_tag_field_says_it_is_only_a_label(self):
        self.assertIn("does not change your Practice Key", SOURCE)


class ItTellsTheTruthAboutStorage(unittest.TestCase):
    def test_cloud_is_the_only_status_reported_as_plainly_saved(self):
        severity, message = panel._status_line(
            {"storage_status": media_state.DOCUMENT_STORAGE_CLOUD})
        self.assertEqual(severity, "ok")
        self.assertIn("Saved", message)

    def test_local_only_is_a_warning_that_names_the_limitation(self):
        severity, message = panel._status_line(
            {"storage_status": media_state.DOCUMENT_STORAGE_LOCAL_ONLY})
        self.assertEqual(severity, "warn")
        self.assertIn("this device only", message)
        self.assertIn("another device", message)

    def test_a_failed_save_is_an_error_and_says_why(self):
        severity, message = panel._status_line(
            {"storage_status": media_state.DOCUMENT_STORAGE_FAILED,
             "storage_error": "disk_full"})
        self.assertEqual(severity, "error")
        self.assertIn("disk_full", message)

    def test_a_missing_file_is_an_error(self):
        severity, _ = panel._status_line(
            {"storage_status": media_state.DOCUMENT_STORAGE_MISSING})
        self.assertEqual(severity, "error")

    def test_an_unknown_status_is_never_reported_as_saved(self):
        severity, _ = panel._status_line({"storage_status": "something_new"})
        self.assertNotEqual(severity, "ok")


class ItNeverHandsOutAUrl(unittest.TestCase):
    def test_no_object_or_signed_url_is_built(self):
        for marker in ("get_public_url", "create_signed_url", "public_url",
                       "supabase://", "createObjectURL"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, SOURCE)

    def test_every_preview_path_passes_bytes(self):
        """Image, st.pdf and download all take the data, never a location."""
        self.assertIn("st.image(png", SOURCE)
        self.assertIn("st.pdf(data", SOURCE)
        self.assertIn("data=data", SOURCE)


class ItDecodesOncePerPage(unittest.TestCase):
    def test_the_fetch_and_the_render_are_both_cached(self):
        self.assertEqual(SOURCE.count("@st.cache_data"), 3)

    def test_the_cache_key_includes_the_content_hash(self):
        """A document id alone is not safe: the bytes behind it can change."""
        for signature in ("def fetch(document_id: str, digest: str)",
                          "def render(document_id: str, digest: str, page_index: int, width: int)",
                          "def pages(document_id: str, digest: str, fallback: int)"):
            with self.subTest(signature=signature):
                self.assertIn(signature, SOURCE)


class ThePageRendererWorks(unittest.TestCase):
    MULTIPAGE = None

    @classmethod
    def setUpClass(cls):
        try:
            import pymupdf

            doc = pymupdf.open()
            for _ in range(3):
                doc.new_page()
            cls.MULTIPAGE = doc.tobytes()
            doc.close()
        except Exception:
            cls.MULTIPAGE = None

    def test_a_three_page_pdf_reports_three_pages(self):
        if not self.MULTIPAGE:
            self.skipTest("PyMuPDF unavailable")
        self.assertEqual(panel._page_count(self.MULTIPAGE, 1), 3)

    def test_each_page_renders_to_a_png(self):
        if not self.MULTIPAGE:
            self.skipTest("PyMuPDF unavailable")
        for page in range(3):
            with self.subTest(page=page):
                png = panel._render_page_png(self.MULTIPAGE, page, 600)
                self.assertTrue(png and png.startswith(b"\x89PNG"))

    def test_a_page_beyond_the_end_is_clamped_rather_than_crashing(self):
        if not self.MULTIPAGE:
            self.skipTest("PyMuPDF unavailable")
        self.assertTrue(panel._render_page_png(self.MULTIPAGE, 99, 600))

    def test_rubbish_bytes_render_nothing_instead_of_raising(self):
        self.assertIsNone(panel._render_page_png(b"not a pdf", 0, 600))
        self.assertEqual(panel._page_count(b"not a pdf", 7), 7)


class ThePracticePageUsesThePanel(unittest.TestCase):
    def setUp(self):
        self.app = (Path(panel.__file__).parent
                    / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

    def test_the_placeholder_is_gone(self):
        self.assertNotIn("This needs a verified private, per-user storage path", self.app)
        self.assertNotIn("nothing selected here is saved yet", self.app)

    def test_the_panel_is_rendered(self):
        self.assertIn("render_song_documents_panel(st, st.session_state)", self.app)

    def test_the_expander_is_named_for_the_feature(self):
        self.assertIn('"My Uploaded Melodies"', self.app)


if __name__ == "__main__":
    unittest.main()

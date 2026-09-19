"""AppTest-free CTA proofs for Save to Composition Library."""

from __future__ import annotations

import unittest
from unittest import mock


class TestCompositionLibrarySaveCta(unittest.TestCase):
    def test_render_library_sidebar_button_label(self) -> None:
        """Direct render of the library sidebar — avoids full-app chart-bundle gate."""
        import composition_studio_page as csp

        labels: list[str] = []

        class _Btn:
            def __init__(self, label, **_kwargs):
                labels.append(str(label))

            def __bool__(self):
                return False

        class _Exp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class _Col:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake_st = mock.MagicMock()
        fake_st.button.side_effect = lambda label, **kw: _Btn(label, **kw)
        fake_st.expander.side_effect = lambda *a, **k: _Exp()
        fake_st.columns.side_effect = lambda *a, **k: (_Col(), _Col())

        with mock.patch.object(csp, "st", fake_st):
            csp._render_library_sidebar({})

        self.assertIn("Save to Composition Library", labels)
        self.assertNotIn("Save song", labels)

    def test_explicit_save_messages_ignore_silent_begin_upsert(self) -> None:
        """Begin/auto upsert may seed the library; first explicit Save still says Saved."""
        from composition_document import bootstrap_from_vision
        from composition_session_state import (
            library_save_success_message,
            save_document_to_library,
            set_active_document,
        )

        ss: dict = {}
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", title="Msg", key="C major", bpm=100)
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)  # silent (Begin / _save_doc path)
        save_document_to_library(ss, doc, explicit=True)
        self.assertEqual(library_save_success_message(ss), "Saved to Composition Library.")
        save_document_to_library(ss, doc, explicit=True)
        self.assertEqual(library_save_success_message(ss), "Composition Library updated.")


if __name__ == "__main__":
    unittest.main()

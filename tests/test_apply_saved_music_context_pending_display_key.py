"""Regression: Catalog restore must not UnboundLocalError on PENDING_DISPLAY_KEY.

A nested ``from songs.key_state import PENDING_DISPLAY_KEY`` inside the
``composition::`` branch of ``apply_saved_music_context`` made the name local
for the entire function. Catalog restore then read it without assignment.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from song_catalog import format_pick_key
from songs.key_state import PENDING_DISPLAY_KEY
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    apply_saved_music_context,
)


ATTYA_LABEL = "All the Things You Are — Jerome Kern"
ATTYA_PICK = format_pick_key("Jazz", ATTYA_LABEL)

CATALOG = {
    "Jazz": {
        ATTYA_LABEL: {
            "title": "All the Things You Are",
            "artist": "Jerome Kern",
            "key": "Ab",
            "genre": "Jazz",
        },
        "Blue Bossa — Kenny Dorham": {
            "title": "Blue Bossa",
            "artist": "Kenny Dorham",
            "key": "C minor",
            "genre": "Jazz",
        },
    }
}


def _st(session: dict | None = None) -> MagicMock:
    ss = session if session is not None else {
        "instrument": "Voice",
        "level": "Intermediate",
        "focus": "Breath Control",
    }
    return MagicMock(session_state=ss)


class TestCatalogRestorePendingDisplayKey(unittest.TestCase):
    def test_catalog_attya_practice_key_g_does_not_unbound_pending_display_key(self) -> None:
        """Exact refresh repro: Catalog ATTYA + Practice Key G."""
        st = _st({"instrument": "Voice", "level": "Intermediate", "focus": "Breath Control", "display_key": "C"})
        saved = {
            "pick_key": ATTYA_PICK,
            "display_key": "G",
            "instrument": "Voice",
            "level": "Intermediate",
            "focus": "Breath Control",
            "song": "All the Things You Are",
            "artist": "Jerome Kern",
        }
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_music_context(st, saved, song_picker_catalog=CATALOG)

        self.assertTrue(ok)
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), ATTYA_PICK)
        self.assertEqual(st.session_state.get(PENDING_DISPLAY_KEY), "G")
        sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
        self.assertEqual(sel.get("title"), "All the Things You Are")

    def test_catalog_flat_key_restore(self) -> None:
        pick = format_pick_key("Jazz", "Blue Bossa — Kenny Dorham")
        st = _st()
        saved = {
            "pick_key": pick,
            "display_key": "Eb",
            "instrument": "Piano",
            "song": "Blue Bossa",
            "artist": "Kenny Dorham",
        }
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_music_context(st, saved, song_picker_catalog=CATALOG)
        self.assertTrue(ok)
        self.assertEqual(st.session_state.get(PENDING_DISPLAY_KEY), "Eb")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), pick)

    def test_catalog_restore_without_saved_display_key(self) -> None:
        st = _st()
        saved = {
            "pick_key": ATTYA_PICK,
            "instrument": "Voice",
            "song": "All the Things You Are",
            "artist": "Jerome Kern",
        }
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_music_context(st, saved, song_picker_catalog=CATALOG)
        self.assertTrue(ok)
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), ATTYA_PICK)
        sel = st.session_state.get(SELECTED_SONG_STATE_KEY) or {}
        self.assertEqual(sel.get("title"), "All the Things You Are")
        # No UnboundLocalError on the Catalog path (PENDING may be unset when
        # no saved display_key — original key is applied via identity sync).

    def test_nested_pending_display_import_absent_from_apply_saved_music_context(self) -> None:
        """Guard: do not re-introduce a function-local PENDING_DISPLAY_KEY import."""
        import inspect
        import songs.state as state_mod

        src = inspect.getsource(state_mod.apply_saved_music_context)
        self.assertNotIn(
            "from songs.key_state import PENDING_DISPLAY_KEY",
            src,
            "Local import of PENDING_DISPLAY_KEY shadows the module binding and "
            "breaks Catalog restore when the composition:: branch is not taken.",
        )


class TestCustomAndCompositionRestorePending(unittest.TestCase):
    def test_custom_pick_restore_sets_pending_display_key(self) -> None:
        from songs.state import apply_saved_custom_pick_key_context

        custom = {
            "id": "cust-restore-1",
            "name": "Restore Custom",
            "artist": "Your progression",
            "original_key_center": "D",
            "user_locked_home_key": True,
            "original_sections": {
                "Verse": [{"chord": "D", "bars": 2}, {"chord": "G", "bars": 2}],
            },
            "bpm": 100,
            "time_signature": "4/4",
        }
        st = _st(
            {
                "instrument": "Voice",
                "cpl_saved_progressions": {custom["name"]: custom},
            }
        )
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_custom_pick_key_context(
                st,
                "custom::cust-restore-1",
                saved={"display_key": "F"},
                song_picker_catalog=CATALOG,
                saved_display_key="F",
            )
        self.assertTrue(ok)
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), "custom::cust-restore-1")
        # Identity reset may clear PENDING; Practice Key lands on display_key.
        self.assertEqual(st.session_state.get("display_key"), "F")

    def test_composition_pick_restore_sets_pending_display_key(self) -> None:
        from composition_document import apply_section_chords, new_composition_document, parse_chord_paste
        from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library

        doc = new_composition_document(title="Comp Restore")
        doc["id"] = "comp-restore-1"
        doc["global"]["original_key_center"] = "A"
        order = list((doc.get("form") or {}).get("section_order") or [])
        if order:
            apply_section_chords(doc, order[0], parse_chord_paste("A D E"))
        ss = {
            "instrument": "Voice",
            "level": "Intermediate",
            "focus": "Breath Control",
            COMPOSER_LIBRARY_KEY: {},
        }
        save_document_to_library(ss, doc)
        st = _st(ss)
        saved = {
            "pick_key": "composition::comp-restore-1",
            "display_key": "Bb",
            "instrument": "Voice",
            "song": "Comp Restore",
        }
        with patch("songs.state.persist_music_local_state"):
            ok = apply_saved_music_context(st, saved, song_picker_catalog=CATALOG)
        self.assertTrue(ok)
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), "composition::comp-restore-1")
        self.assertEqual(st.session_state.get(PENDING_DISPLAY_KEY), "Bb")


if __name__ == "__main__":
    unittest.main()

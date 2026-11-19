"""Composition preview: Close removes the player and the armed WAV, and never touches the composition."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import composition_studio_page as page
from composition_preview import (
    COMPOSER_PREVIEW_AUTOPLAY_KEY,
    COMPOSER_PREVIEW_SLOT_KEY,
    invalidate_composer_preview,
    set_composer_preview,
)


def _armed_session():
    ss = {
        page.COMPOSER_ACTIVE_KEY if hasattr(page, "COMPOSER_ACTIVE_KEY") else "composer_active": {"title": "T", "sections": [{"id": "s1", "chords": ["D", "Bm"]}], "key_center": "D"},
        COMPOSER_PREVIEW_SLOT_KEY: "transport:composer_play_btn",
        "composer_preview_label": "Playing",
    }
    set_composer_preview(ss, b"RIFF" + b"\0" * 64, ("sig",))
    ss[COMPOSER_PREVIEW_SLOT_KEY] = "transport:composer_play_btn"
    return ss


class TestClosePreview(unittest.TestCase):
    def test_close_clears_only_preview_state(self) -> None:
        ss = _armed_session()
        before_doc = copy.deepcopy({k: v for k, v in ss.items() if k.startswith("composer_active") or k == "composer_active"})
        with mock.patch.object(page.st, "button", return_value=True) as b, mock.patch.object(page.st, "rerun") as rr:
            closed = page._render_preview_close_button(ss, slot="transport:composer_play_btn", dom_id="tr_play")
        self.assertTrue(closed)
        rr.assert_called_once()
        self.assertTrue(b.call_args.args[0].endswith("Close preview"))
        self.assertNotIn("composer_preview_wav", ss)
        self.assertNotIn(COMPOSER_PREVIEW_SLOT_KEY, ss)
        self.assertFalse(ss[COMPOSER_PREVIEW_AUTOPLAY_KEY])
        after_doc = {k: v for k, v in ss.items() if k.startswith("composer_active") or k == "composer_active"}
        self.assertEqual(before_doc, after_doc)

    def test_no_click_leaves_the_preview_armed(self) -> None:
        ss = _armed_session()
        with mock.patch.object(page.st, "button", return_value=False), mock.patch.object(page.st, "rerun") as rr:
            self.assertFalse(page._render_preview_close_button(ss, slot="transport:composer_play_btn"))
        rr.assert_not_called()
        self.assertIn("composer_preview_wav", ss)

    def test_button_keys_are_distinct_per_slot(self) -> None:
        keys = []
        with mock.patch.object(page.st, "button", side_effect=lambda *a, **k: keys.append(k["key"]) or False):
            page._render_preview_close_button({}, slot="chords:s1", dom_id="a")
            page._render_preview_close_button({}, slot="melody:s1", dom_id="a")
        self.assertEqual(len(set(keys)), 2)


if __name__ == "__main__":
    unittest.main()


class TestPreviewBelongsToItsSong(unittest.TestCase):
    def _doc(self, sid):
        from composition_document import new_composition_document

        d = new_composition_document(title="X")
        d["id"] = sid
        return d

    def test_switching_to_another_song_clears_the_armed_preview(self) -> None:
        import composition_session_state as CSS

        ss: dict = {}
        CSS.set_active_document(ss, self._doc("aaa"), checkpoint=False)
        set_composer_preview(ss, b"RIFF" + b"\0" * 64, ("sig",))
        CSS.set_active_document(ss, self._doc("bbb"), checkpoint=False)  # clear_preview NOT requested
        self.assertNotIn("composer_preview_wav", ss)

    def test_routine_save_of_the_same_song_keeps_the_preview(self) -> None:
        import composition_session_state as CSS

        ss: dict = {}
        CSS.set_active_document(ss, self._doc("aaa"), checkpoint=False)
        set_composer_preview(ss, b"RIFF" + b"\0" * 64, ("sig",))
        CSS.set_active_document(ss, self._doc("aaa"), checkpoint=False)
        self.assertIn("composer_preview_wav", ss)

"""Close editor sets closed idempotently (a second click on a stale Close cannot reopen)."""

from __future__ import annotations

import time
import unittest

from picker_song_editor import (
    PICKER_EDITOR_OPEN_KEY,
    PICKER_EDITOR_TAB_KEY,
    _JUMP_TO_CHART_EDITOR_KEY,
    _PENDING_OPEN_LYRICS_EDITOR_KEY,
    set_picker_editor_open,
)


class CloseEditorTests(unittest.TestCase):
    def test_close_is_idempotent_and_clears_pending_open_requests(self) -> None:
        ss = {
            PICKER_EDITOR_OPEN_KEY: True,
            "chart_edit_mode": True,
            _PENDING_OPEN_LYRICS_EDITOR_KEY: True,
            _JUMP_TO_CHART_EDITOR_KEY: True,
        }
        set_picker_editor_open(ss, False)
        set_picker_editor_open(ss, False)  # a second click on a stale Close
        self.assertFalse(ss[PICKER_EDITOR_OPEN_KEY])
        self.assertFalse(ss["chart_edit_mode"])
        self.assertNotIn(_PENDING_OPEN_LYRICS_EDITOR_KEY, ss)
        self.assertNotIn(_JUMP_TO_CHART_EDITOR_KEY, ss)

    def test_open_respects_the_selected_tab(self) -> None:
        ss = {PICKER_EDITOR_TAB_KEY: "Edit Song Chart"}
        set_picker_editor_open(ss, True)
        self.assertTrue(ss[PICKER_EDITOR_OPEN_KEY])
        self.assertTrue(ss["chart_edit_mode"])
        lyrics = {PICKER_EDITOR_TAB_KEY: "Lyrics & Cues"}
        set_picker_editor_open(lyrics, True)
        self.assertTrue(lyrics[PICKER_EDITOR_OPEN_KEY])
        self.assertFalse(lyrics.get("chart_edit_mode", False))


if __name__ == "__main__":
    unittest.main()

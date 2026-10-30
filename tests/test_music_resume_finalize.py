"""Continue deep-link must commit song selection after catalog load."""

from __future__ import annotations

import unittest

from song_catalog import format_pick_key
from songs.key_state import (
    PENDING_DISPLAY_KEY,
    PENDING_DISPLAY_KEY_PICK,
    PENDING_DISPLAY_KEY_SOURCE,
)
from songs.practice_key_state import get_practice_concert_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class _FakeQueryParams(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeSession(dict):
    @property
    def session_state(self):
        return self

    @property
    def query_params(self):
        return self._qp

    def __init__(self, qp: dict[str, str]):
        super().__init__()
        self._qp = _FakeQueryParams(qp)
        self["_music_entry_workspace_ready"] = True  # bootstrap completed in this fixture


def _mini_catalog():
    song_picker_catalog = {
        "Pop": {
            "Turn the Lights Back On — Billy Joel": {
                "title": "Turn the Lights Back On",
                "artist": "Billy Joel",
                "key": "Eb",
            },
            "Say — John Mayer": {
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
        }
    }
    song_library = {
        "Pop": {
            "Turn the Lights Back On": song_picker_catalog["Pop"]["Turn the Lights Back On — Billy Joel"],
            "Say": song_picker_catalog["Pop"]["Say — John Mayer"],
        }
    }
    return song_picker_catalog, song_library


class TestMusicResumeFinalize(unittest.TestCase):
    def test_finalize_resume_applies_pick_key_not_default(self) -> None:
        song_picker_catalog, song_library = _mini_catalog()
        pick_key = format_pick_key("Pop", "Turn the Lights Back On — Billy Joel")
        st = _FakeSession(
            {
                "suite_resume": f"song:{pick_key}",
                "suite_page": "practice",
                "suite_pick_key": pick_key,
                "suite_display_key": "Eb",
                "suite_instrument": "Piano",
            }
        )

        from suite_resume_launch import apply_suite_resume_launch, finalize_suite_resume_launch

        self.assertTrue(apply_suite_resume_launch(st, "music"))
        self.assertEqual(st.get(ACTIVE_CATALOG_PICK_KEY), pick_key)
        self.assertNotIn(SELECTED_SONG_STATE_KEY, st)

        self.assertTrue(
            finalize_suite_resume_launch(
                st,
                "music",
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
        )

        sel = st.get(SELECTED_SONG_STATE_KEY) or {}
        self.assertEqual(sel.get("title"), "Turn the Lights Back On")
        self.assertEqual(st.get(ACTIVE_CATALOG_PICK_KEY), pick_key)
        self.assertEqual(st.get("instrument"), "Piano")
        self.assertEqual(st.get(PENDING_DISPLAY_KEY), "Eb")
        self.assertEqual(st.get(PENDING_DISPLAY_KEY_PICK), pick_key)
        self.assertEqual(st.get(PENDING_DISPLAY_KEY_SOURCE), "suite_resume")
        self.assertEqual(get_practice_concert_key(st, pick_key), "Eb")

    def test_finalize_resume_key_replaces_stale_pick_sticky(self) -> None:
        song_picker_catalog, song_library = _mini_catalog()
        pick_key = format_pick_key("Pop", "Turn the Lights Back On â€” Billy Joel")
        st = _FakeSession(
            {
                "suite_resume": f"song:{pick_key}",
                "suite_page": "practice",
                "suite_pick_key": pick_key,
                "suite_display_key": "Cm",
                "practice_key_by_source": {pick_key: "Bm"},
            }
        )

        from suite_resume_launch import apply_suite_resume_launch, finalize_suite_resume_launch

        self.assertTrue(apply_suite_resume_launch(st, "music"))
        self.assertTrue(
            finalize_suite_resume_launch(
                st,
                "music",
                song_picker_catalog=song_picker_catalog,
                song_library=song_library,
            )
        )

        self.assertEqual(get_practice_concert_key(st, pick_key), "Cm")
        self.assertEqual(st.get(PENDING_DISPLAY_KEY), "Cm")
        self.assertEqual(st.get(PENDING_DISPLAY_KEY_PICK), pick_key)
        self.assertEqual(st.get(PENDING_DISPLAY_KEY_SOURCE), "suite_resume")


if __name__ == "__main__":
    unittest.main()

"""Continue deep-link must commit song selection after catalog load."""

from __future__ import annotations

import unittest

from song_catalog import format_pick_key
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


if __name__ == "__main__":
    unittest.main()

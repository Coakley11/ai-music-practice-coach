"""Custom Progression section lyrics persistence."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from custom_progression_lab import default_active_progression, ensure_original_structure
from songs.cpl_lyrics_runtime import (
    CPL_LYRICS_BY_SECTION_KEY,
    collect_cpl_lyrics_from_session,
    cpl_lyrics_widget_key,
    hydrate_cpl_lyrics_widgets,
    resolve_cpl_section_lyrics,
    save_cpl_lyrics_to_active,
)


def _fake_st(session: dict | None = None):
    ss = session if session is not None else {}
    return MagicMock(session_state=ss)


class TestCplLyricsRuntime(unittest.TestCase):
    def test_save_and_resolve_section_lyrics(self) -> None:
        active = ensure_original_structure(default_active_progression())
        active["id"] = "test-rev-1"
        active["original_sections"] = {
            "Verse": [{"chord": "C", "bars": 4}],
            "Chorus": [{"chord": "G", "bars": 4}],
        }
        st = _fake_st({})
        hydrate_cpl_lyrics_widgets(st.session_state, active)
        identity = "test-rev-1"
        st.session_state[cpl_lyrics_widget_key(identity, "Verse")] = "Hello verse"
        st.session_state[cpl_lyrics_widget_key(identity, "Chorus")] = "Hello chorus"

        with patch("songs.cpl_lyrics_runtime.persist_music_local_state", create=True):
            with patch("songs.state.persist_music_local_state"):
                updated = save_cpl_lyrics_to_active(st.session_state, active)

        self.assertEqual(updated[CPL_LYRICS_BY_SECTION_KEY]["Verse"], "Hello verse")
        self.assertEqual(updated[CPL_LYRICS_BY_SECTION_KEY]["Chorus"], "Hello chorus")
        resolved = resolve_cpl_section_lyrics(st.session_state, updated)
        self.assertEqual(resolved["Verse"], "Hello verse")

    def test_collect_lyrics_scoped_to_cpl_identity(self) -> None:
        active = ensure_original_structure(default_active_progression())
        active["id"] = "song-a"
        active["original_sections"] = {"Verse": [{"chord": "D", "bars": 4}]}
        session = {}
        hydrate_cpl_lyrics_widgets(session, active)
        session[cpl_lyrics_widget_key("song-a", "Verse")] = "Custom verse"
        collected = collect_cpl_lyrics_from_session(session, active)
        self.assertEqual(collected, {"Verse": "Custom verse"})


if __name__ == "__main__":
    unittest.main()

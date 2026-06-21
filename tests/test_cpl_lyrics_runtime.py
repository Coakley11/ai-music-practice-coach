"""Custom Progression section lyrics persistence."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from custom_progression_lab import (
    CPL_SAVED_KEY,
    default_active_progression,
    ensure_original_structure,
    save_progression,
)
from songs.cpl_lyrics_runtime import (
    CPL_LYRICS_BY_SECTION_KEY,
    collect_cpl_lyrics_from_session,
    cpl_lyrics_widget_key,
    hydrate_cpl_lyrics_widgets,
    resolve_cpl_section_lyrics,
    save_cpl_lyrics_to_active,
)
from songs.music_source import custom_display_title_for_pick_key


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

        with patch("songs.state.persist_music_local_state"):
            updated = save_cpl_lyrics_to_active(st.session_state, active)

        self.assertEqual(updated[CPL_LYRICS_BY_SECTION_KEY]["Verse"], "Hello verse")
        self.assertEqual(updated[CPL_LYRICS_BY_SECTION_KEY]["Chorus"], "Hello chorus")
        resolved = resolve_cpl_section_lyrics(st.session_state, updated)
        self.assertEqual(resolved["Verse"], "Hello verse")

    def test_save_lyrics_mirrors_into_saved_library(self) -> None:
        active = ensure_original_structure(default_active_progression())
        active["id"] = "DC8HCF997"
        active["name"] = "Trial Song"
        active["original_sections"] = {"Verse": [{"chord": "C", "bars": 4}]}
        store: dict = {}
        save_progression(store, "Trial Song", active)
        session = {
            "cpl_active_progression": active,
            CPL_SAVED_KEY: store,
        }
        hydrate_cpl_lyrics_widgets(session, active)
        session[cpl_lyrics_widget_key("DC8HCF997", "Verse")] = "Trial verse line"

        with patch("songs.state.persist_music_local_state"):
            save_cpl_lyrics_to_active(session, active)

        self.assertEqual(
            session[CPL_SAVED_KEY]["Trial Song"][CPL_LYRICS_BY_SECTION_KEY]["Verse"],
            "Trial verse line",
        )
        self.assertEqual(
            session["cpl_active_progression"][CPL_LYRICS_BY_SECTION_KEY]["Verse"],
            "Trial verse line",
        )

    def test_collect_lyrics_scoped_to_cpl_identity(self) -> None:
        active = ensure_original_structure(default_active_progression())
        active["id"] = "song-a"
        active["original_sections"] = {"Verse": [{"chord": "D", "bars": 4}]}
        session = {}
        hydrate_cpl_lyrics_widgets(session, active)
        session[cpl_lyrics_widget_key("song-a", "Verse")] = "Custom verse"
        collected = collect_cpl_lyrics_from_session(session, active)
        self.assertEqual(collected, {"Verse": "Custom verse"})


class TestCustomKaraokeDisplayTitle(unittest.TestCase):
    def test_custom_display_title_uses_saved_name_not_id(self) -> None:
        session = {
            "cpl_saved_progressions": {
                "Trial Song": {
                    "id": "DC8HCF997",
                    "name": "Trial Song",
                    "artist": "Daniel",
                }
            }
        }
        title = custom_display_title_for_pick_key(session, "custom::DC8HCF997")
        self.assertEqual(title, "Trial Song")


if __name__ == "__main__":
    unittest.main()

"""Authoritative display key — single source for cards and sidebar."""

from __future__ import annotations

import unittest

from songs.key_state import (
    DISPLAY_KEY_TRACE_KEY,
    get_authoritative_display_key,
    trace_display_key_surface,
)
from songs.music_source import resolve_active_song_keys
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class TestAuthoritativeDisplayKey(unittest.TestCase):
    def test_live_session_display_key_wins_over_stale_record_home(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "pk::Pop::Trial — Artist",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": "pk::Pop::Trial — Artist",
                "title": "Trial",
                "artist": "Artist",
                "key": "D",
            },
            "display_key": "D",
            "active_song_state": {
                "pick_key": "pk::Pop::Stay — Kid LAROI",
                "display_key": "G",
            },
        }
        stale_rec = {"key": "G", "title": "Stay"}
        _original, display, _written = resolve_active_song_keys(session, stale_rec)
        self.assertEqual(_original, "D")
        self.assertEqual(display, "D")

    def test_trace_records_surface_disagreement(self) -> None:
        session: dict = {}
        trace_display_key_surface(session, "sidebar", "D", pick_key="pk::1", source="test_sidebar")
        trace_display_key_surface(session, "song_card", "G", pick_key="pk::1", source="test_card")
        trace = session.get(DISPLAY_KEY_TRACE_KEY) or {}
        self.assertEqual((trace.get("sidebar") or {}).get("value"), "D")
        self.assertEqual((trace.get("song_card") or {}).get("value"), "G")

    def test_get_authoritative_display_key_prefers_live(self) -> None:
        session = {
            "display_key": "Eb",
            SELECTED_SONG_STATE_KEY: {"pick_key": "pk::1", "key": "C"},
            ACTIVE_CATALOG_PICK_KEY: "pk::1",
        }
        self.assertEqual(
            get_authoritative_display_key(session, original_key="C", surface="practice"),
            "Eb",
        )


if __name__ == "__main__":
    unittest.main()

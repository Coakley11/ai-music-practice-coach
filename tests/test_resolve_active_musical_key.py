"""Unified musical key resolver — concert, written, and guitar shape hierarchy."""

from __future__ import annotations

import unittest

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
)
from songs.key_state import resolve_active_musical_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class TestResolveActiveMusicalKey(unittest.TestCase):
    def test_concert_key_when_no_transposition(self) -> None:
        session = {
            "instrument": "Piano",
            "display_key": "C#m",
            "selected_song": {"key": "Bm", "pick_key": "pk::1"},
            "active_song_state": {"pick_key": "pk::1", "display_key": "C#m"},
        }
        ctx = resolve_active_musical_key(session, rec={"key": "Bm"}, surface="test")
        self.assertEqual(ctx.original_key, "Bm")
        self.assertEqual(ctx.concert_key, "C#m")
        self.assertEqual(ctx.musical_key, "C#m")
        self.assertEqual(ctx.chart_key_mode, "concert")

    def test_written_key_for_sax_when_chart_in_written_mode(self) -> None:
        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "F",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "F"}, surface="test")
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(ctx.musical_key, "G")
        self.assertEqual(ctx.chart_key_mode, "written")

    def test_guitar_shape_key_when_capo_enabled(self) -> None:
        session = {
            "instrument": "Guitar",
            ACTIVE_CATALOG_PICK_KEY: "pk::1",
            SELECTED_SONG_STATE_KEY: {"pick_key": "pk::1", "key": "Bm"},
            "active_song_state": {"pick_key": "pk::1", "display_key": "C#m"},
            "display_key": "C#m",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "Am",
            "guitar_capo_sounding_key": "C#m",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "Bm"}, surface="test")
        self.assertEqual(ctx.concert_key, "C#m")
        self.assertEqual(ctx.musical_key, "Am")
        self.assertEqual(ctx.chart_key_mode, "shape")


if __name__ == "__main__":
    unittest.main()

"""Unified musical key resolver — separate practice/concert, written, shape, and chart keys."""

from __future__ import annotations

import unittest

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    written_key_for_type,
)
from songs.key_state import resolve_active_musical_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY


class TestResolveActiveMusicalKey(unittest.TestCase):
    def test_practice_concert_key_when_no_transposition(self) -> None:
        session = {
            "instrument": "Piano",
            "display_key": "C#m",
            "selected_song": {"key": "Bm", "pick_key": "pk::1"},
            "active_song_state": {"pick_key": "pk::1", "display_key": "C#m"},
        }
        ctx = resolve_active_musical_key(session, rec={"key": "Bm"}, surface="test")
        self.assertEqual(ctx.original_key, "Bm")
        self.assertEqual(ctx.practice_concert_key, "C#m")
        self.assertEqual(ctx.concert_key, "C#m")
        self.assertEqual(ctx.chart_key, "C#m")
        self.assertEqual(ctx.written_key, "")
        self.assertEqual(ctx.shape_key, "")
        self.assertEqual(ctx.chart_key_mode, "concert")

    def test_written_chart_key_does_not_replace_practice_concert_key(self) -> None:
        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "F",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "F"}, surface="test")
        self.assertEqual(ctx.practice_concert_key, "F")
        self.assertEqual(ctx.written_key, written_key_for_type("F", "Tenor saxophone (Bb)"))
        self.assertEqual(ctx.chart_key, "G")
        self.assertEqual(ctx.shape_key, "")
        self.assertEqual(ctx.chart_key_mode, "written")

    def test_alto_sax_keeps_concert_e_with_written_chart(self) -> None:
        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "E",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "E"}, surface="test")
        self.assertEqual(ctx.practice_concert_key, "E")
        expected_written = written_key_for_type("E", "Alto saxophone (Eb)")
        self.assertEqual(ctx.written_key, expected_written)
        self.assertEqual(ctx.chart_key, expected_written)
        self.assertNotEqual(ctx.practice_concert_key, ctx.chart_key)

    def test_guitar_capo_keeps_concert_and_shape_separate(self) -> None:
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
        self.assertEqual(ctx.practice_concert_key, "C#m")
        self.assertEqual(ctx.shape_key, "A")
        self.assertEqual(ctx.chart_key, "Am")
        self.assertEqual(ctx.chart_key_mode, "shape")
        self.assertNotEqual(ctx.practice_concert_key, ctx.chart_key)

    def test_guitar_shape_tonic_inherits_concert_mode(self) -> None:
        session = {
            "instrument": "Guitar",
            "display_key": "C",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "D",
        }
        ctx = resolve_active_musical_key(session, rec={"key": "C"}, surface="test")
        self.assertEqual(ctx.practice_concert_key, "C")
        self.assertEqual(ctx.shape_key, "D")
        self.assertEqual(ctx.chart_key, "D")

        session["display_key"] = "F#m"
        session["guitar_capo_shape_key"] = "D"
        ctx = resolve_active_musical_key(session, rec={"key": "F#m"}, surface="test")
        self.assertEqual(ctx.practice_concert_key, "F#m")
        self.assertEqual(ctx.shape_key, "D")
        self.assertEqual(ctx.chart_key, "Dm")

        session["display_key"] = "C"
        session["guitar_capo_shape_key"] = "Am"
        ctx = resolve_active_musical_key(session, rec={"key": "C"}, surface="test")
        self.assertEqual(ctx.shape_key, "A")
        self.assertEqual(ctx.chart_key, "A")
        self.assertEqual(ctx.practice_concert_key, "C")


if __name__ == "__main__":
    unittest.main()

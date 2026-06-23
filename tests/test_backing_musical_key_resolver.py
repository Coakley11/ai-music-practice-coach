"""Regression: Backing Track card must call resolve_active_musical_key with keyword args."""

from __future__ import annotations

import unittest

from songs.key_state import resolve_active_musical_key


class TestBackingMusicalKeyResolver(unittest.TestCase):
    def test_backing_card_resolver_accepts_rec_keyword(self) -> None:
        """Mirrors streamlit_music_practice_app backing card call site."""
        session = {
            "instrument": "Piano",
            "display_key": "C#m",
            "selected_song": {"key": "Bm", "pick_key": "pk::1"},
            "active_song_state": {"pick_key": "pk::1", "display_key": "C#m"},
        }
        backing_card_record = {"title": "Song", "key": "Bm", "artist": "Artist"}

        ctx = resolve_active_musical_key(
            session,
            rec=backing_card_record,
            surface="backing_card",
        )

        self.assertEqual(ctx.original_key, "Bm")
        self.assertEqual(ctx.practice_concert_key, "C#m")
        self.assertEqual(ctx.chart_key, "C#m")

    def test_positional_rec_raises_type_error(self) -> None:
        session = {"instrument": "Piano", "display_key": "C"}
        with self.assertRaises(TypeError):
            resolve_active_musical_key(session, {"key": "C"}, surface="backing_card")


if __name__ == "__main__":
    unittest.main()

"""Backing Studio navigation intents and practice/backing source separation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import PENDING_BACKING_CONTEXT_APPLY, get_backing_context, open_backing_from_creative
from backing_source_navigation import (
    BACKING_INTENT_FROM_PRACTICE,
    BACKING_INTENT_RESTORE_LAST,
    PRACTICE_SOURCE_DISPLAY_KEY,
    consume_backing_open_intent,
    hydrate_backing_source_for_page,
    hydrate_practice_source_for_page,
    open_backing_for_practice_source,
    set_backing_open_intent,
    snapshot_practice_source_display_key,
)


class TestBackingSourceNavigation(unittest.TestCase):
    def test_pending_handoff_is_not_consumed_by_peek(self) -> None:
        from backing_context import flush_pending_backing_context_handoff

        session = {PENDING_BACKING_CONTEXT_APPLY: True}
        self.assertTrue(flush_pending_backing_context_handoff(session))
        self.assertTrue(session.get(PENDING_BACKING_CONTEXT_APPLY))

    def test_from_practice_intent_opens_regular_song_backing(self) -> None:
        session = {
            "selected_song": {"title": "Viva La Vida", "pick_key": "Pop::Viva La Vida"},
            "active_catalog_pick_key": "Pop::Viva La Vida",
            "display_key": "Bm",
            "concert_key": "Bm",
            "instrument": "Guitar",
            "backing_track_bpm": 120,
            "backing_groove_style": "Pop groove",
        }
        set_backing_open_intent(session, BACKING_INTENT_FROM_PRACTICE)
        ctx = open_backing_for_practice_source(session, st_like=SimpleNamespace(session_state=session))
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(consume_backing_open_intent(session), BACKING_INTENT_FROM_PRACTICE)

    def test_restore_last_reapplies_creative_backing(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_key": "D",
            "improv_style_bpm": 120,
            "improv_mood": "Mellow",
            "improv_groove": "Medium",
            "improv_difficulty": "Intermediate",
            "improv_style_meter": "4/4",
            "improv_generated_sections": {"Style Jam": ["Dmaj7", "Gmaj7", "A7", "Dmaj7"]},
            "display_key": "D",
            "concert_key": "D",
            "instrument": "Piano",
            "selected_song": {"title": "Shape of You", "pick_key": "Pop::Shape of You"},
            "active_catalog_pick_key": "Pop::Shape of You",
        }
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        snapshot_practice_source_display_key(session)
        session["display_key"] = "Bm"
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(str(session.get("display_key")), "D")
        self.assertTrue(session.get(PENDING_BACKING_CONTEXT_APPLY))

    def test_practice_page_restores_saved_practice_key(self) -> None:
        session = {
            "display_key": "D",
            "concert_key": "D",
            PRACTICE_SOURCE_DISPLAY_KEY: "Bm",
        }
        hydrate_practice_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertEqual(str(session.get("display_key")), "Bm")


if __name__ == "__main__":
    unittest.main()

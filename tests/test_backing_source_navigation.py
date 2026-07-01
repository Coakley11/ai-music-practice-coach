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

    def test_song_identity_change_updates_practice_source_key(self) -> None:
        from songs.music_source import on_active_song_identity_changed

        session = {
            "display_key": "D",
            "concert_key": "D",
            PRACTICE_SOURCE_DISPLAY_KEY: "D",
        }
        st_like = SimpleNamespace(session_state=session)
        on_active_song_identity_changed(
            st_like,
            pick_key="Pop::Shape of You",
            title="Shape of You",
            artist="Ed Sheeran",
            original_key="Bm",
            is_custom=False,
            sync_id="test",
            default_bpm=96,
            default_groove="Pop groove",
            default_meter="4/4",
            invalidate_backing=lambda _s: None,
            force_reset=True,
        )
        self.assertEqual(session.get(PRACTICE_SOURCE_DISPLAY_KEY), "Bm")
        self.assertEqual(str(session.get("display_key")), "Bm")

    def test_return_to_creative_merges_live_key_and_instrument(self) -> None:
        from backing_source_navigation import merge_live_practice_into_creative_session

        session = _style_jam_like_session()
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        session["display_key"] = "F"
        session["concert_key"] = "F"
        session["instrument"] = "Trumpet"
        merge_live_practice_into_creative_session(session)
        sess = session.get("creative_session")
        self.assertIsInstance(sess, dict)
        self.assertEqual(sess.get("concert_key"), "F")
        self.assertEqual(sess.get("instrument"), "Trumpet")


class TestCustomPracticeBackingOwnership(unittest.TestCase):
    def test_from_practice_opens_custom_not_creative(self) -> None:
        session = {
            "active_music_source": "custom_progression",
            "active_catalog_pick_key": "Pop::Say",
            "selected_song": {"title": "Say", "pick_key": "Pop::Say", "key": "G"},
            "display_key": "D",
            "concert_key": "D",
            "cpl_active_progression": {
                "id": "trial-rev",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [{"chord": "D", "bars": 1}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
                "bpm": 90,
            },
        }
        set_backing_open_intent(session, BACKING_INTENT_FROM_PRACTICE)
        ctx = open_backing_for_practice_source(session, st_like=SimpleNamespace(session_state=session))
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertNotEqual(ctx.source, "song_improv")

    def test_custom_context_valid_despite_stale_catalog_pick(self) -> None:
        from backing_context import (
            BACKING_CONTEXT_KEY,
            build_custom_progression_context,
            is_backing_context_valid,
        )

        session = {
            "active_catalog_pick_key": "Pop::Say",
            "cpl_active_progression": {
                "id": "trial-rev",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {
                    "Verse": [{"chord": "D", "bars": 1}],
                    "Chorus": [],
                    "Bridge": [],
                    "Intro": [],
                    "Outro": [],
                },
            },
        }
        ctx = build_custom_progression_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        self.assertTrue(is_backing_context_valid(session, ctx))

    def test_song_change_reset_uses_practice_concert_key_not_stale_display(self) -> None:
        from backing_context import get_backing_context, reset_backing_on_active_song_change

        session = {
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {"title": "Day Tripper", "pick_key": "Rock::Day Tripper", "key": "E"},
            "display_key": "D",
            "_pending_display_key": "E",
            "song": "Day Tripper",
        }
        reset_backing_on_active_song_change(session, practice_concert_key="E")
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ctx.song_title, "Day Tripper")


def _style_jam_like_session() -> dict:
    return {
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
        "selected_song": {"title": "Shape of You", "pick_key": "Pop::Shape of You", "key": "Bm"},
        "active_catalog_pick_key": "Pop::Shape of You",
    }


if __name__ == "__main__":
    unittest.main()

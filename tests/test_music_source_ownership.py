"""Tests for canonical music source ownership transitions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import (
    BACKING_CONTEXT_KEY,
    BACKING_PREF_CATALOG,
    BACKING_PREF_CREATIVE,
    BackingContext,
    get_backing_context,
    open_backing_from_creative,
    set_backing_context,
    set_backing_source_preference,
)
from music_source_ownership import (
    activate_catalog_ownership,
    intended_practice_owner,
    practice_backing_owners_align,
    reconcile_source_ownership,
)
from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY


def _stale_entry_jam_ctx(**overrides: object) -> dict:
    base = dict(
        source="entry_jam",
        source_label="Entry Jam",
        active_song_id="Rock::Day Tripper",
        song_title="Day Tripper",
        key="E",
        display_key="F",
        concert_key="F",
        bpm=100,
        style="Bossa Nova",
        groove="Medium",
        entry_mode="Style Jam Mode",
    )
    base.update(overrides)
    return BackingContext(**base).to_dict()  # type: ignore[arg-type]


class TestMusicSourceOwnership(unittest.TestCase):
    def test_intended_practice_owner_catalog_when_user_chose_catalog(self) -> None:
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Rock::Day Tripper",
        }
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        session[BACKING_CONTEXT_KEY] = _stale_entry_jam_ctx()
        self.assertEqual(intended_practice_owner(session), "catalog")

    def test_intended_practice_owner_none_during_intentional_creative_backing(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Pop::Shape of You",
            "improv_entry_mode": "Style Jam Mode",
        }
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        open_backing_from_creative(session, source="entry_jam")
        self.assertIsNone(intended_practice_owner(session))

    def test_reconcile_catalog_replaces_stale_entry_jam(self) -> None:
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": "Rock::Day Tripper",
                "key": "E",
                "bpm": 138,
                "genre": "Rock",
            },
            "song": "Day Tripper",
            "display_key": "F",
            "concert_key": "F",
        }
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        session[BACKING_CONTEXT_KEY] = _stale_entry_jam_ctx()
        self.assertFalse(practice_backing_owners_align(session))
        reconcile_source_ownership(session)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.bpm, 138)
        self.assertIn("Rock", str(ctx.groove or ""))

    def test_reconcile_skips_intentional_entry_jam_backing(self) -> None:
        session = {
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Pop::Shape of You",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": "Pop::Shape of You"},
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_bpm": 120,
            "improv_style_key": "D",
            "display_key": "D",
            "concert_key": "D",
        }
        open_backing_from_creative(session, source="entry_jam")
        before = get_backing_context(session)
        self.assertIsNotNone(before)
        changed = reconcile_source_ownership(session)
        self.assertFalse(changed)
        after = get_backing_context(session)
        self.assertEqual(getattr(before, "source", None), getattr(after, "source", None))

    def test_activate_catalog_ownership_sets_pref_and_context(self) -> None:
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": "Rock::Day Tripper",
                "key": "E",
                "bpm": 138,
                "genre": "Rock",
            },
            "song": "Day Tripper",
            "display_key": "E",
            "concert_key": "E",
        }
        activate_catalog_ownership(session)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertTrue(practice_backing_owners_align(session))


if __name__ == "__main__":
    unittest.main()

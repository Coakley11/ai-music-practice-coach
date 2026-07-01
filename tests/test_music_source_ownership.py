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

    def test_catalog_identity_false_when_pick_and_title_diverge(self) -> None:
        from music_source_ownership import catalog_identity_aligns

        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Trial Song",
                "pick_key": "custom::trial",
                "key": "D",
            },
            "song": "Trial Song",
            "active_song_title": "Trial Song",
        }
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        session[BACKING_CONTEXT_KEY] = _stale_entry_jam_ctx(
            source="regular_song",
            song_title="Trial Song",
            active_song_id="Rock::Day Tripper",
            bound_pick_key="Rock::Day Tripper",
            bpm=100,
            style="",
            groove="Pop groove",
        )
        self.assertFalse(catalog_identity_aligns(session))
        self.assertFalse(practice_backing_owners_align(session))

    def test_resolve_catalog_song_rejects_stale_selected_for_new_pick(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import resolve_catalog_song_for_pick

        pick = format_pick_key("Rock", "Day Tripper")
        catalog = {
            "Rock": {
                "Day Tripper": {
                    "title": "Day Tripper",
                    "artist": "The Beatles",
                    "key": "E",
                    "bpm": 138,
                    "genre": "Rock",
                }
            }
        }
        session = {
            "selected_song": {
                "title": "Trial Song",
                "pick_key": "custom::trial",
                "key": "D",
            },
            "_reconcile_song_picker_catalog": catalog,
        }
        selected, original = resolve_catalog_song_for_pick(session, pick)
        self.assertEqual(selected.get("title"), "Day Tripper")
        self.assertEqual(original, "E")
        self.assertEqual(selected.get("pick_key"), pick)

    def test_activate_catalog_pick_promotes_day_tripper_over_trial_song(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import activate_catalog_pick_for_backing

        pick = format_pick_key("Rock", "Day Tripper")
        catalog = {
            "Rock": {
                "Day Tripper": {
                    "title": "Day Tripper",
                    "artist": "The Beatles",
                    "key": "E",
                    "bpm": 138,
                    "genre": "Rock",
                }
            }
        }
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Trial Song",
                "pick_key": "custom::trial",
                "key": "D",
            },
            "song": "Trial Song",
            "active_song_title": "Trial Song",
            "display_key": "D",
            "concert_key": "D",
            "_reconcile_song_picker_catalog": catalog,
        }
        activate_catalog_pick_for_backing(session, pick)
        self.assertEqual(session.get("song"), "Day Tripper")
        self.assertEqual(session.get("active_song_title"), "Day Tripper")
        self.assertEqual(session["selected_song"]["title"], "Day Tripper")
        self.assertTrue(practice_backing_owners_align(session))

    def test_rebuild_catalog_backing_fixes_stale_bound_pick_and_transport(self) -> None:
        from song_catalog.catalog import format_pick_key
        from music_source_ownership import (
            catalog_identity_aligns,
            rebuild_catalog_backing_from_canonical_pick,
        )
        from songs.music_source import _pick_keys_match

        day_pick = format_pick_key("Rock", "Day Tripper")
        say_pick = format_pick_key("Pop", "Say")
        catalog = {
            "Rock": {
                "Day Tripper": {
                    "title": "Day Tripper",
                    "artist": "The Beatles",
                    "key": "E",
                    "bpm": 138,
                    "genre": "Rock",
                }
            },
            "Pop": {
                "Say": {
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                    "bpm": 100,
                    "genre": "Pop",
                }
            },
        }
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": day_pick,
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": day_pick,
                "key": "E",
                "bpm": 138,
                "genre": "Rock",
            },
            "song": "Day Tripper",
            "active_song_title": "Day Tripper",
            "display_key": "G",
            "concert_key": "G",
            "backing_track_bpm": 100,
            "_reconcile_song_picker_catalog": catalog,
        }
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        session[BACKING_CONTEXT_KEY] = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id=say_pick,
            song_title="Day Tripper",
            key="G",
            display_key="G",
            concert_key="G",
            bpm=100,
            style="",
            groove="Pop groove",
            bound_pick_key=say_pick,
        ).to_dict()
        self.assertFalse(catalog_identity_aligns(session))
        rebuild_catalog_backing_from_canonical_pick(session)
        self.assertTrue(catalog_identity_aligns(session))
        self.assertTrue(practice_backing_owners_align(session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertTrue(_pick_keys_match(ctx.bound_pick_key or "", day_pick, session_state=session))
        self.assertEqual(ctx.bpm, 138)
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get("concert_key"), "E")


if __name__ == "__main__":
    unittest.main()

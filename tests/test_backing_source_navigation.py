"""Backing Studio navigation intents and practice/backing source separation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import PENDING_BACKING_CONTEXT_APPLY, get_backing_context, open_backing_from_creative
from backing_source_navigation import (
    BACKING_INTENT_FROM_CREATIVE,
    BACKING_INTENT_FROM_PRACTICE,
    BACKING_INTENT_RESTORE_LAST,
    PRACTICE_SOURCE_DISPLAY_KEY,
    consume_backing_open_intent,
    hydrate_backing_source_for_page,
    hydrate_picker_source_for_page,
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

    def test_from_creative_intent_preserves_entry_jam_over_catalog_pick(self) -> None:
        from backing_context import BACKING_PREF_CREATIVE, get_backing_source_preference
        from music_source_ownership import current_backing_owner
        from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY

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
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_bpm": 120,
            "improv_style_key": "D",
            "improv_mood": "Mellow",
            "improv_groove": "Medium",
            "improv_difficulty": "Intermediate",
            "improv_style_meter": "4/4",
            "improv_generated_sections": {"Style Jam": ["Dmaj7", "Gmaj7", "A7", "Dmaj7"]},
            "display_key": "D",
            "concert_key": "D",
            "instrument": "Piano",
        }
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        set_backing_open_intent(session, BACKING_INTENT_FROM_CREATIVE)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(get_backing_source_preference(session), BACKING_PREF_CREATIVE)
        self.assertEqual(current_backing_owner(session), "entry_jam")
        self.assertEqual(consume_backing_open_intent(session), BACKING_INTENT_RESTORE_LAST)

    def test_from_creative_hydrate_syncs_sidebar_keys_from_backing_context(self) -> None:
        from songs.key_state import PENDING_DISPLAY_KEY
        from session_widget_safe import PENDING_IMPROV_STYLE_KEY

        session = {
            "studio_page": "backing",
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": "Rock::Day Tripper",
                "key": "E",
                "bpm": 138,
            },
            "display_key": "G",
            "concert_key": "G",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bright Bossa Nova",
            "improv_style_bpm": 75,
            "improv_style_key": "F",
            "improv_generated_sections": {"Style Jam": ["Fmaj7", "Bbmaj7", "C7", "Fmaj7"]},
        }
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        set_backing_open_intent(session, BACKING_INTENT_FROM_CREATIVE)
        hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertEqual(session.get("concert_key"), "F")
        self.assertEqual(session.get("display_key"), "G")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "F")
        self.assertEqual(session.get("improv_style_key"), "F")
        self.assertEqual(session.get(PENDING_IMPROV_STYLE_KEY), "F")

    def test_practice_page_restores_saved_practice_key(self) -> None:
        session = {
            "display_key": "D",
            "concert_key": "D",
            PRACTICE_SOURCE_DISPLAY_KEY: "Bm",
        }
        hydrate_practice_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertEqual(str(session.get("display_key")), "Bm")

    def test_picker_hydrate_rebuilds_stale_catalog_backing(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, BackingContext
        from music_source_ownership import (
            catalog_identity_aligns,
            practice_backing_owners_align,
        )
        from song_catalog.catalog import format_pick_key
        from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY

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
            "studio_page": "picker",
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
        }
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
        hydrate_picker_source_for_page(
            session,
            st_like=SimpleNamespace(session_state=session),
            song_picker_catalog=catalog,
        )
        self.assertTrue(catalog_identity_aligns(session))
        self.assertTrue(practice_backing_owners_align(session))
        self.assertTrue(session.get("catalog_rebuild_needed"))
        self.assertTrue(session.get("catalog_rebuild_ran"))
        self.assertEqual(session.get("last_reconcile_reason"), "picker_hydrate")
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.bpm, 138)
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(session.get("display_key"), "E")

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


    def test_hydrate_stale_entry_jam_yields_custom_for_trial_song(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, BACKING_PREF_CREATIVE, get_backing_context
        from backing_context import set_backing_source_preference

        session = {
            "active_music_source": "custom_progression",
            "display_key": "D",
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
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_label": "Entry & Jam",
                "active_song_id": "say",
                "song_title": "Say",
                "key": "G",
                "display_key": "G",
                "concert_key": "G",
                "bpm": 100,
                "style": "Bossa Nova",
                "groove": "Medium",
                "entry_mode": "Style Jam Mode",
                "bound_pick_key": "Pop::Say",
            },
        }
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.song_title, "Trial Song")

    def test_catalog_context_rebuild_uses_song_original_key_and_bpm(self) -> None:
        from backing_context import (
            BACKING_PREF_CATALOG,
            get_backing_context,
            reset_backing_on_active_song_change,
            set_backing_source_preference,
        )

        session = {
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": "Rock::Day Tripper",
                "key": "E",
                "bpm": 138,
                "genre": "Rock",
            },
            "display_key": "D",
            "concert_key": "D",
            "_pending_display_key": "D",
            "backing_track_bpm": 100,
            "song": "Day Tripper",
        }
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        reset_backing_on_active_song_change(session, practice_concert_key="E")
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.key, "E")
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ctx.bpm, 138)

    def test_sync_song_picker_source_widget_safe_when_locked(self) -> None:
        from songs.music_source import (
            PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_ACTIVE_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            sync_song_picker_source_widget,
        )

        session = {
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_music_source": "catalog",
            "display_key": "E",
        }
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        sync_song_picker_source_widget(session, force=True)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)

    def test_backing_page_transport_defaults_use_catalog_context(self) -> None:
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_PREF_CATALOG,
            backing_page_transport_defaults,
            set_backing_context,
            set_backing_source_preference,
        )
        from backing_context import build_regular_song_context

        session = {
            "active_music_source": "catalog",
            "active_catalog_pick_key": "Rock::Day Tripper",
            "selected_song": {
                "title": "Day Tripper",
                "pick_key": "Rock::Day Tripper",
                "key": "E",
                "bpm": 138,
                "genre": "Rock",
            },
            "display_key": "E",
            "concert_key": "E",
            "song": "Day Tripper",
        }
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        ctx = build_regular_song_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        bpm, groove, _meter = backing_page_transport_defaults(session)
        self.assertEqual(bpm, 138)
        self.assertIn("Rock", groove)

    def test_return_to_creative_restores_entry_jam_tool_type(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import prepare_return_to_backing_source
        from creative_session_state import get_creative_session

        session = _style_jam_like_session()
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        session["improv_entry_mode"] = "Song-Based Improvisation"
        prepare_return_to_backing_source(session)
        sess = get_creative_session(session)
        self.assertIsNotNone(sess)
        assert sess is not None
        self.assertEqual(sess.tool_type, "entry_style_jam")
        self.assertEqual(sess.entry_mode, "Style Jam Mode")
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")


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

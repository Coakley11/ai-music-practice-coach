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
    queue_backing_scope_from_practice_focus,
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

    def test_queue_backing_scope_from_practice_verse_focus(self) -> None:
        from custom_progression_lab import PENDING_BACKING_MULTI_SECTIONS, PENDING_BACKING_SCOPE, PENDING_BACKING_SINGLE_SECTION

        session = {
            "practice_focus_section": "Verse",
            "selected_song": {
                "sections": {
                    "Verse 1": ["Em", "Am"],
                    "Chorus": ["G", "D"],
                }
            },
        }
        queue_backing_scope_from_practice_focus(session)
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Selected sections")
        self.assertEqual(session.get(PENDING_BACKING_SINGLE_SECTION), "Verse 1")
        self.assertEqual(session.get(PENDING_BACKING_MULTI_SECTIONS), ["Verse 1"])

    def test_queue_backing_scope_from_practice_full_song(self) -> None:
        from custom_progression_lab import PENDING_BACKING_MULTI_SECTIONS, PENDING_BACKING_SCOPE, PENDING_BACKING_SINGLE_SECTION

        session = {"practice_focus_section": "Full Song"}
        queue_backing_scope_from_practice_focus(session)
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Full song")
        self.assertNotIn(PENDING_BACKING_SINGLE_SECTION, session)

    def test_queue_backing_scope_from_practice_multi_focus(self) -> None:
        from custom_progression_lab import PENDING_BACKING_MULTI_SECTIONS, PENDING_BACKING_SCOPE

        session = {
            "practice_focus_sections": ["Verse", "Chorus"],
            "selected_song": {
                "sections": {
                    "Verse 1": ["Em"],
                    "Chorus": ["G", "D"],
                    "Bridge": ["Am"],
                }
            },
        }
        queue_backing_scope_from_practice_focus(session)
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Selected sections")
        self.assertEqual(session.get(PENDING_BACKING_MULTI_SECTIONS), ["Verse 1", "Chorus"])

    def test_resolve_selected_section_names_preserves_song_order(self) -> None:
        from backing_track_state import resolve_selected_section_names

        session = {
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["Chorus", "Verse 1", "Bridge"],
        }
        ordered = ["Intro", "Verse 1", "Chorus", "Bridge", "Outro"]
        self.assertEqual(resolve_selected_section_names(session, ordered), ["Verse 1", "Chorus", "Bridge"])
        from custom_progression_lab import PENDING_BACKING_MULTI_SECTIONS, PENDING_BACKING_SCOPE, PENDING_BACKING_SINGLE_SECTION

        session = {
            "practice_focus_section": "Chorus",
            "selected_song": {
                "title": "Test",
                "sections": {
                    "Verse 1": ["Em"],
                    "Chorus": ["G", "D"],
                },
            },
            "active_catalog_pick_key": "Pop::Test",
            "display_key": "G",
            "concert_key": "G",
        }
        set_backing_open_intent(session, BACKING_INTENT_FROM_PRACTICE)
        hydrate_backing_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertEqual(session.get(PENDING_BACKING_SCOPE), "Selected sections")
        self.assertEqual(session.get(PENDING_BACKING_SINGLE_SECTION), "Chorus")
        self.assertEqual(session.get(PENDING_BACKING_MULTI_SECTIONS), ["Chorus"])

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

    def test_from_creative_hydrate_style_jam_concert_key_beats_stale_chart_display(self) -> None:
        """Style Jam backing concert F must win over stale catalog chart keys (B — authority)."""
        from songs.key_state import PENDING_DISPLAY_KEY
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            written_key_for_type,
        )

        def _style_jam_session_with_stale_chart(*, instrument: str, extra: dict | None = None) -> dict:
            base = {
                "studio_page": "backing",
                "instrument": instrument,
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
            if extra:
                base.update(extra)
            return base

        try:
            from music_restore_phase import complete_music_restore_phase
        except ImportError:
            complete_music_restore_phase = None  # type: ignore[misc,assignment]

        # Concert-pitch instrument: Style Jam F aligns concert and sidebar display; stale chart G must not stick.
        piano = _style_jam_session_with_stale_chart(instrument="Piano")
        if complete_music_restore_phase:
            complete_music_restore_phase(piano)
        st_like = SimpleNamespace(session_state=piano)
        open_backing_from_creative(piano, source="entry_jam", st_like=st_like)
        set_backing_open_intent(piano, BACKING_INTENT_FROM_CREATIVE)
        hydrate_backing_source_for_page(piano, st_like=st_like)
        self.assertEqual(piano.get("concert_key"), "F")
        self.assertEqual(piano.get("display_key"), "F")
        self.assertNotEqual(piano.get("display_key"), "G")
        self.assertEqual(piano.get("improv_style_key"), "F")
        self.assertNotIn(PENDING_DISPLAY_KEY, piano)

        # Transposing instrument: backing still establishes concert F; written chart differs only via transposition authority.
        alto = _style_jam_session_with_stale_chart(
            instrument="Saxophone",
            extra={
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
                CHART_IN_INSTRUMENT_KEY_KEY: True,
            },
        )
        if complete_music_restore_phase:
            complete_music_restore_phase(alto)
        st_alto = SimpleNamespace(session_state=alto)
        open_backing_from_creative(alto, source="entry_jam", st_like=st_alto)
        set_backing_open_intent(alto, BACKING_INTENT_FROM_CREATIVE)
        hydrate_backing_source_for_page(alto, st_like=st_alto)
        self.assertEqual(alto.get("concert_key"), "F")
        self.assertNotEqual(alto.get("display_key"), "G")
        written = written_key_for_type("F", "Alto saxophone (Eb)")
        from instrument_transposition import effective_chart_key

        chart_key, chart_mode = effective_chart_key("F", "Saxophone", alto)
        self.assertEqual(chart_key, written)
        self.assertEqual(chart_mode, "written")
        self.assertNotEqual("F", written)

    def test_practice_page_restores_saved_practice_key(self) -> None:
        session = {
            "display_key": "D",
            "concert_key": "D",
            PRACTICE_SOURCE_DISPLAY_KEY: "Bm",
        }
        hydrate_practice_source_for_page(session, st_like=SimpleNamespace(session_state=session))
        self.assertEqual(str(session.get("display_key")), "Bm")

    def test_practice_hydrate_reconcile_primes_bpm_with_streamlit_session_proxy(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, BackingContext
        from song_catalog.catalog import format_pick_key
        from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY
        from songs.playback_defaults import ACTIVE_SONG_BPM_KEY, BPM_WIDGET_KEY

        class _Proxy:
            def __init__(self, backing: dict) -> None:
                self._data = backing

            def __getitem__(self, key):  # type: ignore[no-untyped-def]
                return self._data[key]

            def __setitem__(self, key, value) -> None:  # type: ignore[no-untyped-def]
                self._data[key] = value

            def get(self, key, default=None):  # type: ignore[no-untyped-def]
                return self._data.get(key, default)

            def pop(self, key, default=None):  # type: ignore[no-untyped-def]
                if key in self._data:
                    return self._data.pop(key)
                return default

        day_pick = format_pick_key("Rock", "Day Tripper")
        say_pick = format_pick_key("Pop", "Say")
        session = {
            "studio_page": "practice",
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
        proxy = _Proxy(session)
        hydrate_practice_source_for_page(session, st_like=SimpleNamespace(session_state=proxy))
        self.assertEqual(session.get(BPM_WIDGET_KEY), 138)
        self.assertEqual(session.get(ACTIVE_SONG_BPM_KEY), 138)

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

    def test_sync_song_picker_source_widget_promotes_catalog_when_unlocked(self) -> None:
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
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIsNone(session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY))

    def test_sync_song_picker_source_widget_stages_catalog_when_widgets_locked(self) -> None:
        from session_widget_safe import apply_pending_widget_hydrates
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
            "_streamlit_widgets_locked_this_run": True,
        }
        try:
            from music_restore_phase import complete_music_restore_phase

            complete_music_restore_phase(session)
        except ImportError:
            pass
        sync_song_picker_source_widget(session, force=True)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        session.pop("_streamlit_widgets_locked_this_run", None)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get(SONG_PICKER_ACTIVE_SOURCE_KEY), SONG_PICKER_SOURCE_CATALOG)
        self.assertIsNone(session.get(PENDING_SONG_PICKER_ACTIVE_SOURCE_KEY))

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

    def test_backing_page_transport_defaults_ignore_stale_ctx_bpm(self) -> None:
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_PREF_CATALOG,
            BackingContext,
            backing_page_transport_defaults,
            set_backing_source_preference,
        )

        in_my_life_pick = "Pop::In My Life"
        session = {
            "active_music_source": "catalog",
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {
                "title": "In My Life",
                "pick_key": in_my_life_pick,
                "key": "A",
                "bpm": 100,
            },
            "display_key": "A",
            "concert_key": "A",
            "song": "In My Life",
            "backing_track_bpm": 82,
        }
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        session[BACKING_CONTEXT_KEY] = BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id=in_my_life_pick,
            bound_pick_key=in_my_life_pick,
            song_title="In My Life",
            key="A",
            display_key="A",
            concert_key="A",
            bpm=82,
            style="",
            groove="Pop groove",
        ).to_dict()
        bpm, _groove, _meter = backing_page_transport_defaults(session)
        self.assertEqual(bpm, 100)

    def test_jam_capture_snapshots_catalog_before_creative(self) -> None:
        from creative_session_state import capture_jam_session_generator_state
        from songs.music_source import CATALOG_BEFORE_CREATIVE_KEY

        in_my_life_pick = "Pop::In My Life"
        session = {
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick, "bpm": 100},
            "song": "In My Life",
            "display_key": "A",
            "user_catalog_source_choice": True,
        }
        capture_jam_session_generator_state(
            session,
            ensemble="Jazz trio",
            style="Blues",
            concert_key="Eb",
            bpm=90,
            mood="Mellow",
            jam_session={"title": "Jam", "sections": {"A": ["Eb7"]}},
        )
        snap = session.get(CATALOG_BEFORE_CREATIVE_KEY)
        self.assertIsInstance(snap, dict)
        assert isinstance(snap, dict)
        self.assertEqual(str(snap.get("pick_key") or ""), in_my_life_pick)

    def test_creative_jam_edit_preserves_catalog_pick_over_stale_dropdown(self) -> None:
        from active_song_state import mark_active_song_local_edit, prepare_active_song_context
        from creative_key_sync import (
            guard_creative_catalog_pick_before_edit,
            is_creative_catalog_pick_frozen,
            verify_creative_catalog_pick_after_edit,
        )
        from song_catalog.catalog import format_pick_key
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, reconcile_active_song_identity

        in_my_life_pick = format_pick_key("Pop", "In My Life — The Beatles")
        stay_pick = format_pick_key("Pop", "Stay — The Kid LAROI & Justin Bieber")
        catalog = {
            "Pop": {
                "In My Life — The Beatles": {"title": "In My Life", "artist": "The Beatles", "key": "A"},
                "Stay — The Kid LAROI & Justin Bieber": {
                    "title": "Stay",
                    "artist": "The Kid LAROI & Justin Bieber",
                    "key": "C",
                },
            },
        }
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            ACTIVE_CATALOG_PICK_KEY: in_my_life_pick,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": in_my_life_pick,
                "title": "In My Life",
                "artist": "The Beatles",
                "genre": "Pop",
                "key": "A",
            },
            "matching_song_dropdown": stay_pick,
            "song": "In My Life",
            "active_song_title": "In My Life",
            "user_catalog_source_choice": True,
        }
        self.assertTrue(is_creative_catalog_pick_frozen(session))
        before = guard_creative_catalog_pick_before_edit(session, writer="test_jam_tempo")
        mark_active_song_local_edit(session)
        master = reconcile_active_song_identity(session, catalog)
        self.assertEqual(master, in_my_life_pick)
        session[ACTIVE_CATALOG_PICK_KEY] = stay_pick
        session["song"] = "Stay"
        verify_creative_catalog_pick_after_edit(session, before_pick=before, writer="test_jam_tempo")
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), in_my_life_pick)
        self.assertEqual(session.get("song"), "In My Life")
        session["_reconcile_song_picker_catalog"] = catalog
        prepare_active_song_context(session)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), in_my_life_pick)

    def test_jam_setting_change_does_not_write_catalog_snapshot(self) -> None:
        from creative_key_sync import guard_creative_catalog_pick_before_edit
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CREATIVE_KEY

        in_my_life_pick = format_pick_key("Pop", "In My Life — The Beatles")
        say_pick = format_pick_key("Pop", "Stay — The Kid LAROI & Justin Bieber")
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick},
            "song": "In My Life",
            "user_catalog_source_choice": True,
            CATALOG_BEFORE_CREATIVE_KEY: {
                "pick_key": say_pick,
                "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick},
                "original_key": "G",
                "display_key": "G",
            },
            "last_catalog_song_writer": "snapshot_catalog_before_creative",
        }
        guard_creative_catalog_pick_before_edit(session, writer="on_improv_jam_setting_change")
        snap = session.get(CATALOG_BEFORE_CREATIVE_KEY)
        assert isinstance(snap, dict)
        self.assertEqual(str(snap.get("pick_key") or ""), say_pick)
        self.assertEqual(session.get("last_catalog_song_writer"), "snapshot_catalog_before_creative")

    def test_snapshot_refreshes_when_catalog_pick_changes_before_creative(self) -> None:
        from songs.music_source import CATALOG_BEFORE_CREATIVE_KEY, snapshot_catalog_before_creative

        say_pick = "Pop::Say"
        in_my_life_pick = "Pop::In My Life"
        session = {
            "active_catalog_pick_key": in_my_life_pick,
            "selected_song": {"title": "In My Life", "key": "A", "pick_key": in_my_life_pick},
            "song": "In My Life",
            "display_key": "A",
            "user_catalog_source_choice": True,
            CATALOG_BEFORE_CREATIVE_KEY: {
                "pick_key": say_pick,
                "selected_song": {"title": "Say", "key": "G", "pick_key": say_pick},
                "original_key": "G",
                "display_key": "G",
            },
        }
        snapshot_catalog_before_creative(session, refresh_if_pick_changed=True)
        snap = session.get(CATALOG_BEFORE_CREATIVE_KEY)
        assert isinstance(snap, dict)
        self.assertEqual(str(snap.get("pick_key") or ""), in_my_life_pick)

    def test_catalog_restore_pin_blocks_stale_dropdown_reconcile(self) -> None:
        from active_song_state import mark_active_song_local_edit
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_RESTORE_PIN_KEY, pin_catalog_restore_identity
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, reconcile_active_song_identity

        shape_pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        say_pick = format_pick_key("Pop", "Say — John Mayer")
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {"title": "Shape of You", "artist": "Ed Sheeran", "key": "Bm", "bpm": 96},
                "Say — John Mayer": {"title": "Say", "artist": "John Mayer", "key": "G", "bpm": 82},
            },
        }
        session = {
            ACTIVE_CATALOG_PICK_KEY: shape_pick,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": shape_pick,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "bpm": 96,
            },
            "song": "Shape of You",
            "matching_song_dropdown": say_pick,
            "user_catalog_source_choice": True,
        }
        pin_catalog_restore_identity(session, shape_pick, session[SELECTED_SONG_STATE_KEY])
        mark_active_song_local_edit(session)
        session[CATALOG_RESTORE_PIN_KEY] = shape_pick
        master = reconcile_active_song_identity(session, catalog)
        self.assertEqual(master, shape_pick)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), shape_pick)
        self.assertEqual(session.get("song"), "Shape of You")

    def test_ensure_improv_entry_mode_respects_user_touch_over_stale_session(self) -> None:
        from creative_session_state import CreativeSession, set_creative_session
        from studio_page_state import ensure_improv_entry_mode_restored

        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "_improv_tab_user_touched": True,
        }
        set_creative_session(
            session,
            CreativeSession(
                session_id="",
                tool_type="song_based_improvisation",
                entry_mode="Song-Based Improvisation",
                concert_key="A",
                display_key="A",
            ),
        )
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(entry, "Style Jam Mode")
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")

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

    def test_return_to_creative_uses_backing_key_over_catalog_display_key(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            prepare_return_to_backing_source,
        )
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession, get_creative_session
        from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY

        session = _style_jam_like_session()
        session.update(
            {
                USER_CATALOG_SOURCE_CHOICE_KEY: True,
                "active_music_source": SOURCE_CATALOG,
                "active_catalog_pick_key": "Rock::Day Tripper",
                "selected_song": {
                    "title": "Day Tripper",
                    "pick_key": "Rock::Day Tripper",
                    "key": "E",
                    "bpm": 138,
                },
                "display_key": "G",
                "concert_key": "G",
                "improv_style_key": "F",
                "improv_style": "Bright Bossa Nova",
                "improv_style_bpm": 75,
            }
        )
        session[CREATIVE_SESSION_KEY] = CreativeSession(
            session_id="stale-sbi",
            tool_type="song_based_improvisation",
            entry_mode="Song-Based Improvisation",
            concert_key="G",
            display_key="G",
            style="",
            bpm=96,
            sections={"Verse": ["Cm"]},
        ).to_dict()
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        session["studio_page"] = "backing"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        prepare_return_to_backing_source(session)
        self.assertTrue(session.get(CREATIVE_RESTORE_FROM_BACKING_KEY))
        sess = get_creative_session(session)
        self.assertIsNotNone(sess)
        assert sess is not None
        self.assertEqual(sess.tool_type, "entry_style_jam")
        self.assertEqual(sess.concert_key, "F")
        self.assertEqual(sess.style, "Bright Bossa Nova")
        self.assertEqual(sess.bpm, 75)
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("concert_key"), "F")


    def test_creative_page_hydrate_restores_from_backing_after_return(self) -> None:
        from backing_context import open_backing_from_creative
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            prepare_return_to_backing_source,
        )
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession, get_creative_session, hydrate_creative_session_for_page
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        session = _style_jam_like_session()
        session.update(
            {
                USER_CATALOG_SOURCE_CHOICE_KEY: True,
                "display_key": "G",
                "concert_key": "G",
                "improv_style_key": "F",
                "improv_style": "Bright Bossa Nova",
                "improv_style_bpm": 75,
            }
        )
        session[CREATIVE_SESSION_KEY] = CreativeSession(
            session_id="stale-sbi",
            tool_type="song_based_improvisation",
            entry_mode="Song-Based Improvisation",
            concert_key="G",
            display_key="G",
            sections={"Verse": ["Cm"]},
        ).to_dict()
        session["_creative_session_hydrated_creative"] = True
        open_backing_from_creative(session, source="entry_jam")
        prepare_return_to_backing_source(session)
        session["studio_page"] = "creative"
        session["display_key"] = "G"
        session["concert_key"] = "G"
        session[CREATIVE_RESTORE_FROM_BACKING_KEY] = True
        hydrate_creative_session_for_page(session)
        sess = get_creative_session(session)
        self.assertIsNotNone(sess)
        assert sess is not None
        self.assertEqual(sess.tool_type, "entry_style_jam")
        self.assertEqual(sess.concert_key, "F")
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")


    def test_ensure_improv_entry_mode_canonical_selector_precedes_creative_session(self) -> None:
        from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession
        from creative_tab_tool_persistence import CREATIVE_WORKSPACE_STATE_KEY
        from studio_page_state import ensure_improv_entry_mode_restored

        creative_blob = CreativeSession(
            session_id="entry-jam",
            tool_type="entry_style_jam",
            entry_mode="Style Jam Mode",
            concert_key="F",
            display_key="F",
            style="Bossa Nova",
            bpm=80,
            sections={"Style Jam": ["Fmaj7"]},
        ).to_dict()

        with_canonical = {
            "studio_page": "creative",
            "_creative_selector_hydration_complete": True,
            "improv_entry_mode": "Song-Based Improvisation",
            CREATIVE_WORKSPACE_STATE_KEY: {"improv_entry_mode": "Song-Based Improvisation"},
            CREATIVE_SESSION_KEY: creative_blob,
        }
        entry = ensure_improv_entry_mode_restored(with_canonical)
        self.assertEqual(entry, "Song-Based Improvisation")
        self.assertEqual(with_canonical.get("improv_entry_mode"), "Song-Based Improvisation")

        without_canonical = {
            "studio_page": "creative",
            "_creative_selector_hydration_complete": True,
            CREATIVE_SESSION_KEY: creative_blob,
        }
        entry_fallback = ensure_improv_entry_mode_restored(without_canonical)
        self.assertEqual(entry_fallback, "Style Jam Mode")
        self.assertEqual(without_canonical.get("improv_entry_mode"), "Style Jam Mode")

    def test_backing_context_overrides_stale_snapshot_entry_mode(self) -> None:
        """entry_jam backing context must win over a stale SBI page-snapshot value."""
        from backing_context import open_backing_from_creative
        from music_restore_phase import complete_music_restore_phase
        from studio_page_state import (
            ensure_creative_widgets_from_backing_context,
            ensure_improv_entry_mode_restored,
            ensure_improv_intelligence_tab_restored,
        )

        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "F",
            "improv_style_bpm": 80,
            "improv_generated_sections": {"Style Jam": ["Fmaj7", "Bbmaj7"]},
            "display_key": "F",
            "concert_key": "F",
            "instrument": "Piano",
            "studio_page": "creative",
        }
        complete_music_restore_phase(session)
        open_backing_from_creative(session, source="entry_jam")
        # Simulate page-snapshot restore clobbering the visible widgets with stale SBI state.
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Live Coach"
        session["_improv_tab_user_touched"] = True

        changed = ensure_creative_widgets_from_backing_context(session, restoring_from_backing=True)
        self.assertTrue(changed)
        tab = ensure_improv_intelligence_tab_restored(session)
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(tab, "Entry & Jam")
        self.assertEqual(entry, "Style Jam Mode")
        self.assertEqual(session.get("improv_intelligence_tab"), "Entry & Jam")
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertFalse(session.get("_improv_tab_user_touched"))

    def test_passive_creative_hydrate_keeps_user_live_coach_with_mission_backing(self) -> None:
        """Mission backing context alone must not clobber a user-selected Live Coach tab (passive rerun)."""
        from backing_context import (
            BACKING_CONTEXT_KEY,
            BACKING_PREF_CREATIVE,
            build_mission_context,
            set_backing_source_preference,
        )
        from music_restore_phase import complete_music_restore_phase
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY, ensure_improv_intelligence_tab_restored

        session = {
            "improv_active_mission": "Rhythm-first, note-second",
            "improv_intelligence_tab": "Live Coach",
            CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY: "Live Coach",
            "_improv_tab_user_touched": True,
            "improv_mission_progression": ["Em"],
            "ii_selected_chord": "Em",
            "display_key": "G",
            "concert_key": "G",
            "instrument": "Piano",
            "studio_page": "creative",
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "_creative_selector_hydration_complete": True,
        }
        complete_music_restore_phase(session)
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        session[BACKING_CONTEXT_KEY] = build_mission_context(session).to_dict()
        tab = ensure_improv_intelligence_tab_restored(session)
        self.assertEqual(tab, "Live Coach")
        self.assertEqual(session.get("improv_intelligence_tab"), "Live Coach")

    def test_intentional_return_to_mission_selects_missions_tab_and_restores_identity(self) -> None:
        from unittest import mock

        from mission_backing_alignment import build_mission_backing_alignment_payload
        from mission_return_destination import MISSION_CANONICAL_RETURN_DESTINATION_KEY, build_mission_return_destination
        from music_workflow_pending_mission_return import (
            consume_pending_mission_return_handoff,
            queue_pending_mission_return_from_backing,
        )
        from studio_page_state import ensure_improv_intelligence_tab_restored

        session: dict = {
            "studio_page": "backing",
            "improv_intelligence_tab": "Live Coach",
            "_improv_tab_user_touched": True,
            MISSION_CANONICAL_RETURN_DESTINATION_KEY: build_mission_return_destination(
                build_mission_backing_alignment_payload(
                    {},
                    mission="Mission A",
                    cur_chord="Bb",
                    section_label="Verse",
                    chord_idx=0,
                    song_title="Tune",
                    with_practice_lick=True,
                ),
                handoff_mode="practice_in_jam",
                with_practice_lick=True,
                request_seq=3,
            ),
        }
        queue_pending_mission_return_from_backing(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                with mock.patch("backing_context.get_backing_context", return_value=None):
                    phase = consume_pending_mission_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertEqual(session.get("improv_active_mission"), "Mission A")
        self.assertEqual(session.get("ii_selected_chord"), "Bb")
        self.assertEqual(session.get("ii_selected_section"), "Verse")
        tab = ensure_improv_intelligence_tab_restored(session)
        self.assertEqual(tab, "Missions")
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")

    def test_song_improv_backing_context_keeps_sbi_entry_mode(self) -> None:
        """song_improv backing context maps to Song-Based Improvisation, not Style Jam."""
        from backing_context import open_backing_from_creative
        from music_restore_phase import complete_music_restore_phase
        from studio_page_state import (
            ensure_creative_widgets_from_backing_context,
            ensure_improv_entry_mode_restored,
        )

        session = {
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_source": "Active song",
            "improv_style": "Rock",
            "improv_style_key": "C",
            "display_key": "C",
            "concert_key": "C",
            "instrument": "Piano",
            "studio_page": "creative",
        }
        complete_music_restore_phase(session)
        open_backing_from_creative(session, source="song_improv")
        session["improv_entry_mode"] = "Style Jam Mode"  # stale clobber

        ensure_creative_widgets_from_backing_context(session, restoring_from_backing=True)
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(entry, "Song-Based Improvisation")

    def test_no_backing_context_leaves_entry_mode_untouched(self) -> None:
        from music_restore_phase import complete_music_restore_phase
        from studio_page_state import (
            ensure_creative_widgets_from_backing_context,
            ensure_improv_entry_mode_restored,
        )

        session = {
            "improv_entry_mode": "Jam Session Generator",
            "display_key": "C",
            "concert_key": "C",
            "instrument": "Piano",
            "studio_page": "creative",
        }
        complete_music_restore_phase(session)
        changed = ensure_creative_widgets_from_backing_context(session, restoring_from_backing=True)
        entry = ensure_improv_entry_mode_restored(session)
        self.assertFalse(changed)
        self.assertEqual(entry, "Jam Session Generator")

    def test_resolve_entry_jam_prefers_jam_session_over_style_sections(self) -> None:
        from backing_source_navigation import resolve_entry_jam_entry_mode

        session = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_generated_sections": {"12-bar blues": ["G7", "C7", "D7"]},
            "improv_jam_session": {
                "title": "Jam",
                "sections": {"Blues (Jam)": ["F7", "Bb7", "C7"]},
            },
        }
        self.assertEqual(resolve_entry_jam_entry_mode(session), "Jam Session Generator")

    def test_jam_session_generate_syncs_creative_session(self) -> None:
        from creative_session_state import (
            CREATIVE_SESSION_KEY,
            capture_jam_session_generator_state,
            get_creative_session,
        )
        from improvisation_intelligence import generate_jam_session
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY

        jam = generate_jam_session(style="Blues", key_center="F", tempo=90, mood="Mellow")
        session = {
            "improv_entry_mode": "Style Jam Mode",
            PENDING_IMPROV_ENTRY_MODE_KEY: "Jam Session Generator",
            "improv_jam_style": "Blues",
            "improv_jam_key": "F",
            "improv_jam_bpm": 90,
            "improv_jam_mood": "Mellow",
            "improv_jam_session": jam,
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "G",
                "style": "Bossa Nova",
                "mood": "Bright",
                "sections": {"Rock jam": ["G", "C", "D"]},
            },
            "improv_style_meta": {
                "style": "Bossa Nova",
                "key": "C",
                "mood": "Bright",
                "entry_mode": "Style Jam Mode",
            },
            "studio_page": "creative",
        }
        capture_jam_session_generator_state(
            session,
            ensemble="Jazz trio",
            style="Blues",
            concert_key="F",
            bpm=90,
            mood="Mellow",
            jam_session=jam,
        )
        sess = get_creative_session(session)
        self.assertIsNotNone(sess)
        assert sess is not None
        self.assertEqual(sess.tool_type, "jam_session_generator")
        self.assertEqual(sess.entry_mode, "Jam Session Generator")
        self.assertEqual(sess.style, "Blues")
        self.assertEqual(sess.concert_key, "F")
        self.assertEqual(sess.mood, "Mellow")
        self.assertTrue(sess.sections)
        self.assertIn(CREATIVE_SESSION_KEY, session)

    def test_jam_session_generate_hydrate_preserves_widget_values(self) -> None:
        from creative_session_state import (
            capture_jam_session_generator_state,
            hydrate_creative_session_for_page,
        )
        from improvisation_intelligence import generate_jam_session
        from session_widget_safe import (
            PENDING_IMPROV_ENSEMBLE_KEY,
            PENDING_IMPROV_JAM_KEY,
            PENDING_IMPROV_JAM_MOOD_KEY,
            PENDING_IMPROV_JAM_STYLE_KEY,
            apply_pending_widget_hydrates,
        )

        jam = generate_jam_session(style="Jazz Swing", key_center="Eb", tempo=120, mood="Dark")
        session = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_key": "C",
            "improv_jam_bpm": 110,
            "improv_jam_mood": "Bright",
            "improv_ensemble": "Jazz trio",
            "_streamlit_widgets_locked_this_run": True,
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "C",
                "style": "Bossa Nova",
                "mood": "Bright",
                "sections": {"Bossa": ["Cmaj7"]},
            },
            "studio_page": "creative",
        }
        capture_jam_session_generator_state(
            session,
            ensemble="Latin quartet",
            style="Jazz Swing",
            concert_key="Eb",
            bpm=120,
            mood="Dark",
            jam_session=jam,
        )
        self.assertEqual(session.get(PENDING_IMPROV_JAM_STYLE_KEY), "Jazz Swing")
        self.assertEqual(session.get(PENDING_IMPROV_JAM_KEY), "Eb")
        self.assertEqual(session.get(PENDING_IMPROV_JAM_MOOD_KEY), "Dark")
        self.assertEqual(session.get(PENDING_IMPROV_ENSEMBLE_KEY), "Latin quartet")
        hydrate_creative_session_for_page(session)
        session.pop("_streamlit_widgets_locked_this_run", None)
        apply_pending_widget_hydrates(session)
        self.assertEqual(session.get("improv_jam_style"), "Jazz Swing")
        self.assertEqual(session.get("improv_jam_key"), "Eb")
        self.assertEqual(session.get("improv_jam_mood"), "Dark")
        self.assertEqual(session.get("improv_ensemble"), "Latin quartet")
        self.assertEqual(int(session.get("improv_jam_bpm") or 0), 120)

    def test_jam_session_open_backing_survives_custom_practice_and_double_hydrate(self) -> None:
        from backing_context import BACKING_PREF_CREATIVE, get_backing_context, get_backing_source_preference, open_backing_from_creative
        from creative_session_state import CREATIVE_SESSION_KEY
        from improvisation_intelligence import generate_jam_session
        from music_source_ownership import current_backing_owner, intended_practice_owner
        from songs.music_source import SOURCE_CUSTOM

        jam = generate_jam_session(style="Blues", key_center="F", tempo=90, mood="Mellow")
        session = {
            "active_music_source": SOURCE_CUSTOM,
            "cpl_active_progression": {
                "id": "custom-rev-trial",
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
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Blues",
            "improv_jam_key": "F",
            "improv_jam_bpm": 90,
            "improv_jam_mood": "Mellow",
            "improv_jam_session": jam,
            CREATIVE_SESSION_KEY: {
                "tool_type": "jam_session_generator",
                "entry_mode": "Jam Session Generator",
                "concert_key": "F",
                "display_key": "F",
                "style": "Blues",
                "mood": "Mellow",
                "bpm": 90,
                "sections": dict(jam.get("sections") or {}),
            },
            "display_key": "F",
            "concert_key": "F",
            "instrument": "Piano",
            "studio_page": "backing",
        }
        st_like = SimpleNamespace(session_state=session)
        open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        set_backing_open_intent(session, BACKING_INTENT_FROM_CREATIVE)
        hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertEqual(get_backing_source_preference(session), BACKING_PREF_CREATIVE)
        self.assertEqual(current_backing_owner(session), "entry_jam")
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(ctx.style, "Blues")
        self.assertIsNone(intended_practice_owner(session))
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx2 = get_backing_context(session)
        self.assertIsNotNone(ctx2)
        assert ctx2 is not None
        self.assertEqual(ctx2.source, "entry_jam")
        self.assertEqual(current_backing_owner(session), "entry_jam")

    def test_ensure_entry_mode_preserves_jam_after_stale_style_blob(self) -> None:
        from studio_page_state import ensure_improv_entry_mode_restored

        session = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_session": {
                "title": "Jam",
                "sections": {"Blues (Jam)": ["F7", "Bb7", "C7"]},
            },
            "creative_session": {
                "tool_type": "entry_style_jam",
                "entry_mode": "Style Jam Mode",
                "concert_key": "G",
                "style": "Blues",
                "sections": {"12-bar blues": ["G7", "C7", "D7"]},
            },
        }
        entry = ensure_improv_entry_mode_restored(session)
        self.assertEqual(entry, "Jam Session Generator")

    def test_build_entry_jam_context_ignores_stale_sbi_widget(self) -> None:
        from backing_context import build_entry_jam_context, open_backing_from_creative

        session = {
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_style": "Bossa Nova",
            "improv_style_key": "F",
            "improv_generated_sections": {"Style Jam": ["Fmaj7"]},
            "display_key": "F",
            "concert_key": "F",
            "instrument": "Piano",
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.source, "entry_jam")
        self.assertEqual(ctx.entry_mode, "Style Jam Mode")
        open_backing_from_creative(session, source="entry_jam")
        ctx2 = build_entry_jam_context(session)
        self.assertEqual(ctx2.entry_mode, "Style Jam Mode")

    def test_return_to_creative_authoritative_style_jam_before_entry_radios(self) -> None:
        """Return to Creative must land Style Jam Mode on the entry radio before widgets render."""
        from backing_context import open_backing_from_creative
        from backing_source_navigation import (
            CREATIVE_RESTORE_FROM_BACKING_KEY,
            prepare_return_to_backing_source,
            rehydrate_creative_from_backing_context,
        )
        from creative_session_state import CREATIVE_SESSION_KEY, get_creative_session
        from music_restore_phase import complete_music_restore_phase
        from studio_page_persistence import (
            _ACTIVE_PAGE_TRACKER,
            _PAGE_SNAPSHOTS_KEY,
            handle_studio_page_transition,
            save_page_snapshot,
        )
        from studio_page_state import (
            CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY,
            ensure_creative_widgets_from_backing_context,
            ensure_improv_entry_mode_restored,
            ensure_improv_intelligence_tab_restored,
        )

        def _widget_trace(session: dict, label: str) -> dict[str, object]:
            return {
                "label": label,
                "improv_entry_mode": session.get("improv_entry_mode"),
                "improv_intelligence_tab": session.get("improv_intelligence_tab"),
                CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY: session.get(CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY),
                "_pending_improv_entry_mode": session.get("_pending_improv_entry_mode"),
                "_pending_improv_intelligence_tab": session.get("_pending_improv_intelligence_tab"),
                "_improv_tab_user_touched": session.get("_improv_tab_user_touched"),
                "creative_session.tool": (
                    get_creative_session(session).tool_type if get_creative_session(session) else None
                ),
            }

        # User was on Creative in SBI, then opened Entry Jam backing.
        session = {
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Entry & Jam",
            CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY: "Entry & Jam",
            "_improv_tab_user_touched": True,
            "improv_style": "Bossa Nova",
            "improv_style_key": "F",
            "improv_style_bpm": 80,
            "improv_generated_sections": {"Style Jam": ["Fmaj7", "Bbmaj7"]},
            "display_key": "F",
            "concert_key": "F",
            "instrument": "Piano",
            "studio_page": "creative",
        }
        complete_music_restore_phase(session)
        save_page_snapshot(session, "creative")
        open_backing_from_creative(session, source="entry_jam")

        # Run N: user clicks Return to Creative on backing page.
        session["studio_page"] = "backing"
        session[_ACTIVE_PAGE_TRACKER] = "backing"
        page = prepare_return_to_backing_source(session)
        self.assertEqual(page, "creative")
        self.assertTrue(session.get(CREATIVE_RESTORE_FROM_BACKING_KEY))
        self.assertFalse(session.get("_improv_tab_user_touched"))
        after_prepare = _widget_trace(session, "after_prepare_return")

        # Run N+1: script reruns on creative page.
        session["studio_page"] = "creative"
        handle_studio_page_transition(session)
        after_transition = _widget_trace(session, "after_handle_studio_page_transition")
        # Snapshot skip + sync guard: canonical blob must survive transition.
        self.assertEqual(after_transition["creative_session.tool"], "entry_style_jam", after_transition)

        rehydrate_creative_from_backing_context(session)
        session.pop(CREATIVE_RESTORE_FROM_BACKING_KEY, None)
        ensure_creative_widgets_from_backing_context(session, restoring_from_backing=True)
        after_early_hydrate = _widget_trace(session, "after_early_creative_hydrate")

        # Render path: immediately before radios.
        tab = ensure_improv_intelligence_tab_restored(session)
        entry = ensure_improv_entry_mode_restored(session)
        before_radios = _widget_trace(session, "before_radios")

        self.assertEqual(after_prepare["creative_session.tool"], "entry_style_jam")
        self.assertEqual(before_radios["improv_entry_mode"], "Style Jam Mode", before_radios)
        self.assertEqual(before_radios["improv_intelligence_tab"], "Entry & Jam", before_radios)
        self.assertEqual(tab, "Entry & Jam")
        self.assertEqual(entry, "Style Jam Mode")
        self.assertIsNone(before_radios["_pending_improv_entry_mode"])
        self.assertIsNone(before_radios["_pending_improv_intelligence_tab"])
        self.assertFalse(before_radios["_improv_tab_user_touched"])
        # Prove the bug path: without snapshot skip, transition would force SBI.
        self.assertEqual(after_early_hydrate["improv_entry_mode"], "Style Jam Mode")


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

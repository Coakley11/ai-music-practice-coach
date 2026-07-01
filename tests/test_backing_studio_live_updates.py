"""Backing Studio — BPM init, written-key charts, and live context refresh."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    build_entry_jam_context,
    build_regular_song_context,
    build_song_improv_context,
    open_backing_from_creative,
    refresh_backing_context_from_session,
    reconcile_backing_context_on_backing_page,
    sections_dict_for_chart_display,
    sections_dict_from_backing_context,
    set_backing_context,
)
from backing_musical_state import (
    clear_stale_chart_session_keys,
    preserve_backing_musical_keys_after_generate,
    resolve_current_backing_musical_state,
    should_skip_regular_song_defaults,
)
from instrument_transposition import (
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    written_key_for_type,
)
from songs.bpm_state import BPM_WIDGET_KEY, LAST_BPM_SONG, PENDING_BACKING_TRACK_BPM
from songs.playback_defaults import (
    _CANONICAL_BACKING_ID_KEY,
    backing_bpm_slider_widget_key,
    canonicalize_backing_defaults_for_song,
    resolve_backing_bpm_for_slider,
)


def _shape_of_you_session(**overrides) -> dict:
    base = {
        "active_catalog_pick_key": "shape|edsheeran",
        "song": "Shape of You",
        "display_key": "Bm",
        "concert_key": "Bm",
        "instrument": "Saxophone",
        "show_chart_in_instrument_key": True,
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": "Bossa Nova",
        "improv_style_key": "F",
        "improv_style_bpm": 75,
        "improv_style_meta": {"style": "Bossa Nova", "bpm": 75, "groove": "Medium", "key": "F"},
        "improv_generated_sections": {"Head (Bossa Nova)": ["Gm7", "C7", "Fmaj7", "D7"]},
        "studio_page": "backing",
    }
    base.update(overrides)
    return base


def _entry_jam_session(*, bpm: int = 60, key: str = "C") -> dict:
    return {
        "active_catalog_pick_key": "say|artist",
        "song": "Say",
        "display_key": key,
        "concert_key": key,
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": "Bossa Nova",
        "improv_style_key": key,
        "improv_style_bpm": bpm,
        "improv_style_meta": {"style": "Bossa Nova", "bpm": bpm, "groove": "Medium"},
        "improv_generated_sections": {"Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
    }


class TestBackingStudioBpmInit(unittest.TestCase):
    def test_style_jam_60_initializes_slider_not_catalog_108(self) -> None:
        session = _entry_jam_session(bpm=60)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[BPM_WIDGET_KEY] = 108
        session["bpm"] = 108
        session[LAST_BPM_SONG] = "pk::catalog_song"
        session[backing_bpm_slider_widget_key("pk::catalog_song")] = 108
        st = SimpleNamespace(session_state=session)

        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=108,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertTrue(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 60)

        slider_bpm = resolve_backing_bpm_for_slider(
            st,
            sync_id=sync_id,
            default_bpm=60,
            song_just_reset=bool(canon["did_reset"]),
        )
        self.assertEqual(slider_bpm, 60)
        self.assertEqual(session[backing_bpm_slider_widget_key(sync_id)], 60)

    def test_same_source_bpm_override_persists(self) -> None:
        session = _entry_jam_session(bpm=60)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[_CANONICAL_BACKING_ID_KEY] = sync_id
        session[BPM_WIDGET_KEY] = 75
        session[LAST_BPM_SONG] = sync_id
        session[backing_bpm_slider_widget_key(sync_id)] = 75
        session["_backing_user_edited"] = True
        st = SimpleNamespace(session_state=session)

        with patch("backing_track_state.is_backing_user_dirty", return_value=True):
            canon = canonicalize_backing_defaults_for_song(
                st,
                sync_id=sync_id,
                active_song_bpm=60,
                active_song_groove="Pop groove",
                active_song_meter="4/4",
            )
        self.assertFalse(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 75)

    def test_new_source_resets_bpm(self) -> None:
        session = _entry_jam_session(bpm=80, key="G")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[_CANONICAL_BACKING_ID_KEY] = "creative:entry_jam:old_sig"
        session[BPM_WIDGET_KEY] = 120
        st = SimpleNamespace(session_state=session)

        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=120,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertTrue(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 80)


class TestTenorWrittenChartTranspose(unittest.TestCase):
    def _tenor_session(self, concert: str) -> dict:
        return {
            "display_key": concert,
            "concert_key": concert,
            "instrument": "Saxophone",
            "show_chart_in_instrument_key": True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": concert,
            "improv_generated_sections": {
                "Head": ["Bbm7", "Eb7", "Abmaj7", "Dbmaj7"],
            },
        }

    def test_tenor_concert_db_written_eb_chords(self) -> None:
        session = self._tenor_session("Db")
        written = written_key_for_type("Db", "Tenor saxophone (Bb)")
        self.assertEqual(written, "Eb")
        concert = {"Head": ["Bbm7", "Eb7", "Abmaj7", "Dbmaj7"]}
        chart = sections_dict_for_chart_display(session, concert, concert_key="Db")
        flat = " ".join(chart["Head"])
        self.assertIn("Cm7", flat)
        self.assertIn("Ebmaj7", flat)

    def test_tenor_concert_c_written_d_chords(self) -> None:
        session = {
            "display_key": "C",
            "concert_key": "C",
            "instrument": "Saxophone",
            "show_chart_in_instrument_key": True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        }
        written = written_key_for_type("C", "Tenor saxophone (Bb)")
        self.assertEqual(written, "D")
        concert = {"Head": ["Dm7", "G7", "Cmaj7", "A7"]}
        chart = sections_dict_for_chart_display(session, concert, concert_key="C")
        flat = " ".join(chart["Head"])
        self.assertIn("Em7", flat)
        self.assertIn("Dmaj7", flat)


class TestBackingContextLiveRefresh(unittest.TestCase):
    def test_refresh_updates_concert_key_from_session(self) -> None:
        session = _entry_jam_session(bpm=60, key="F")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["display_key"] = "C"
        session["improv_style_key"] = "C"
        session["concert_key"] = "C"

        refreshed = refresh_backing_context_from_session(session)
        assert refreshed is not None
        self.assertEqual(refreshed.concert_key, "C")
        self.assertNotEqual(refreshed.concert_key, ctx.concert_key)

    def test_reconcile_refreshes_context_and_flushes_bpm(self) -> None:
        session = _entry_jam_session(bpm=60, key="C")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session[BACKING_CONTEXT_KEY]["concert_key"] = "F"
        session[BACKING_CONTEXT_KEY]["bpm"] = 110
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        self.assertEqual(session.get("backing_track_bpm"), 60)
        self.assertEqual(getattr(refresh_backing_context_from_session(session), "concert_key", None), "C")

    def test_invalidate_refreshes_not_clears_entry_jam(self) -> None:
        from backing_context import get_backing_context
        from creative_key_sync import invalidate_creative_backing_context

        session = _entry_jam_session(bpm=60, key="G")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["improv_style_key"] = "A"
        session["display_key"] = "A"
        invalidate_creative_backing_context(session)
        live = get_backing_context(session)
        self.assertIsNotNone(live)
        self.assertEqual(live.source, "entry_jam")
        self.assertEqual(live.concert_key, "A")


class TestBackingMusicalStateResolver(unittest.TestCase):
    def test_shape_of_you_bm_style_jam_f_uses_concert_f_not_bm(self) -> None:
        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "F")
        self.assertEqual(state.key_mode, "major")
        self.assertNotEqual(state.practice_concert_key, "Bm")

    def test_alto_written_f_shows_d_not_g_sharp_minor(self) -> None:
        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.written_key, "D")
        self.assertEqual(state.chart_display_key, "D")
        self.assertNotIn("m", state.chart_display_key.lower())
        self.assertNotEqual(state.chart_display_key, "G#m")

    def test_written_chart_off_uses_concert_no_badge(self) -> None:
        session = _shape_of_you_session(show_chart_in_instrument_key=False)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["_creative_chart_display_key"] = "G#m"
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.chart_mode, "concert")
        self.assertEqual(state.chart_display_key, "F")
        self.assertFalse(state.show_chart_badge)
        self.assertNotIn("_creative_chart_display_key", session)

    def test_guitar_shape_off_uses_concert_no_badge(self) -> None:
        session = _shape_of_you_session(
            instrument="Guitar",
            show_chart_in_instrument_key=False,
            guitar_capo_enabled=False,
            guitar_capo_shape_key="Eb minor",
        )
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.chart_mode, "concert")
        self.assertEqual(state.chart_display_key, "F")
        self.assertFalse(state.show_chart_badge)

    def test_key_change_after_generation_updates_resolver(self) -> None:
        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["improv_style_key"] = "C"
        session["display_key"] = "C"
        session["concert_key"] = "C"
        session["improv_generated_sections"] = {
            "Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7", "A7"],
        }
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "C")
        self.assertEqual(state.written_key, "A")
        self.assertEqual(state.chart_display_key, "A")

    def test_new_jam_bpm_90_resets_after_open_backing(self) -> None:
        session = _entry_jam_session(bpm=75)
        ctx75 = build_entry_jam_context(session)
        set_backing_context(session, ctx75)
        session[_CANONICAL_BACKING_ID_KEY] = f"creative:entry_jam:{ctx75.source_signature}"
        session["improv_style_bpm"] = 90
        session["improv_style_meta"] = {"style": "Bossa Nova", "bpm": 90, "groove": "Medium", "key": "C"}
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        ctx90 = build_entry_jam_context(session)
        sync_id = f"creative:entry_jam:{ctx90.source_signature}"
        st = SimpleNamespace(session_state=session)
        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=108,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertTrue(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 90)

    def test_clear_stale_chart_keys_on_toggle(self) -> None:
        session = {"_creative_chart_display_key": "G#m", "_backing_creative_chart_sections": {"A": ["C"]}}
        clear_stale_chart_session_keys(session)
        self.assertNotIn("_creative_chart_display_key", session)
        self.assertNotIn("_backing_creative_chart_sections", session)


class TestGeneratePathResolver(unittest.TestCase):
    def test_generate_preserves_f_d_sidebar_not_bm(self) -> None:
        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        st = SimpleNamespace(session_state=session)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "F")
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        preserve_backing_musical_keys_after_generate(st, session, state)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("concert_key"), "F")

    def test_key_change_e_uses_concert_sections_not_original_f(self) -> None:
        from creative_key_sync import IMPROV_STYLE_KEY_TRACKER

        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["improv_style_key"] = "E"
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session[IMPROV_STYLE_KEY_TRACKER] = "F"
        session["improv_generated_sections"] = {
            "Head (Bossa Nova)": ["Gm7", "C7", "Fmaj7", "D7"],
        }
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "E")
        flat = " ".join(next(iter(state.concert_sections.values()), []))
        self.assertIn("F#m7", flat)
        self.assertNotIn("Gm7", flat)

    def test_creative_active_skips_catalog_defaults(self) -> None:
        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        self.assertTrue(should_skip_regular_song_defaults(session))

    def test_shape_of_you_background_cannot_leak_on_generate_preserve(self) -> None:
        session = _shape_of_you_session(show_chart_in_instrument_key=True)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        st = SimpleNamespace(session_state=session)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.written_key, "D")
        session["display_key"] = "Bm"
        preserve_backing_musical_keys_after_generate(st, session, state)
        restored = resolve_current_backing_musical_state(session)
        self.assertEqual(restored.practice_concert_key, "F")
        self.assertEqual(restored.written_key, "D")


class TestSongImprovBackingHandoff(unittest.TestCase):
    def _shape_improv_session(self, **overrides) -> dict:
        base = {
            "active_catalog_pick_key": "shape|edsheeran",
            "song": "Shape of You",
            "display_key": "Cm",
            "concert_key": "Cm",
            "instrument": "Guitar",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "Ebm",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_concert_sections": {
                "Verse": ["Cm", "Ab", "Eb", "Bb"],
            },
        }
        base.update(overrides)
        return base

    def test_song_improv_context_not_entry_jam(self) -> None:
        session = self._shape_improv_session()
        ctx = build_song_improv_context(session)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(ctx.song_title, "Shape of You")
        self.assertEqual(ctx.concert_key, "Cm")
        self.assertEqual(ctx.entry_mode, "Song-Based Improvisation")

    def test_open_backing_replaces_style_jam_with_song_improv(self) -> None:
        session = _entry_jam_session(bpm=75, key="F")
        old_ctx = build_entry_jam_context(session)
        set_backing_context(session, old_ctx)
        session.update(self._shape_improv_session())
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            open_backing_from_creative(session, source="song_improv", st_like=st_like)
        live = build_song_improv_context(session)
        self.assertEqual(live.source, "song_improv")
        self.assertNotEqual(live.source_signature, old_ctx.source_signature)

    def test_song_improv_resolver_uses_cm_not_bm(self) -> None:
        session = self._shape_improv_session()
        ctx = build_song_improv_context(session)
        set_backing_context(session, ctx)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "Cm")
        self.assertEqual(state.chart_mode, "shape")
        self.assertNotEqual(state.practice_concert_key, "Bm")


class TestBackingSourceNavigation(unittest.TestCase):
    def test_style_jam_restore_entry_mode_and_key(self) -> None:
        from backing_source_navigation import prepare_return_to_backing_source

        session = _entry_jam_session(bpm=75, key="F")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        page = prepare_return_to_backing_source(session)
        self.assertEqual(page, "creative")
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("improv_style_key"), "F")
        self.assertEqual(session.get("_pending_display_key"), "F")

    def test_song_improv_restore_shape_of_you(self) -> None:
        from backing_source_navigation import prepare_return_to_backing_source

        session = {
            "song": "Shape of You",
            "display_key": "Cm",
            "concert_key": "Cm",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_song_concert_sections": {"Verse": ["Cm", "Ab"]},
        }
        ctx = build_song_improv_context(session)
        set_backing_context(session, ctx)
        page = prepare_return_to_backing_source(session)
        self.assertEqual(page, "creative")
        self.assertEqual(session.get("improv_entry_mode"), "Song-Based Improvisation")
        self.assertEqual(session.get("_pending_display_key"), "Cm")

    def test_catalog_song_label_not_regular_song(self) -> None:
        from backing_context import format_backing_context_banner

        ctx = build_regular_song_context(
            {"song": "Day Tripper", "display_key": "G", "concert_key": "G"}
        )
        banner = format_backing_context_banner(ctx)
        self.assertIn("Catalog song", banner)
        self.assertNotIn("Regular song", banner)


class TestCreativePageKeySync(unittest.TestCase):
    def test_day_tripper_original_e_practice_g_sidebar_uses_g(self) -> None:
        from creative_key_sync import prepare_backing_context_sidebar_display_key, should_use_live_practice_key_sidebar

        session = {
            "studio_page": "creative",
            "song": "Day Tripper",
            "display_key": "G",
            "concert_key": "G",
            "improv_entry_mode": "Song-Based Improvisation",
        }
        self.assertTrue(should_use_live_practice_key_sidebar(session))
        st = SimpleNamespace(session_state=session)
        options = prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "G")
        self.assertIn("G", options)

    def test_song_improv_key_change_invalidates_context(self) -> None:
        from creative_key_sync import sync_sidebar_creative_concert_key

        session = _shape_of_you_session(improv_entry_mode="Song-Based Improvisation")
        session.update(
            {
                "display_key": "Cm",
                "concert_key": "Cm",
                "improv_song_concert_sections": {"Verse": ["Cm"]},
            }
        )
        ctx = build_song_improv_context(session)
        set_backing_context(session, ctx)
        session["display_key"] = "Dm"
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session.get("concert_key"), "Dm")


class TestRefreshPersistence(unittest.TestCase):
    def test_backing_context_in_persist_keys(self) -> None:
        from music_persistent_state import _PERSIST_KEYS

        self.assertIn("backing_context", _PERSIST_KEYS)
        self.assertIn("improv_entry_mode", _PERSIST_KEYS)
        self.assertIn("improv_generated_sections", _PERSIST_KEYS)

    def test_entry_jam_disk_roundtrip_restores_creative_not_catalog(self) -> None:
        from backing_context import active_creative_backing_context, get_backing_context
        from music_persistent_state import apply_music_disk_state, build_music_disk_state

        session = _entry_jam_session(bpm=82, key="D")
        session.update(
            {
                "active_catalog_pick_key": "daytripper|beatles",
                "song": "Day Tripper",
                "display_key": "G",
                "concert_key": "G",
                "improv_style": "Bossa Nova",
                "studio_page": "backing",
            }
        )
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            open_backing_from_creative(session, source="entry_jam", st_like=st_like)
        blob = build_music_disk_state(SimpleNamespace(session_state=session))
        restored: dict = {}
        st2 = SimpleNamespace(session_state=restored)
        apply_music_disk_state(st2, blob, song_picker_catalog={}, song_library={})
        ctx = get_backing_context(restored)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "entry_jam")
        self.assertIsNotNone(active_creative_backing_context(restored))
        state = resolve_current_backing_musical_state(restored)
        self.assertEqual(state.practice_concert_key, "D")
        self.assertNotEqual(ctx.song_title, "Day Tripper")


class TestKeyConsistencyCardSidebar(unittest.TestCase):
    def test_catalog_leak_sidebar_and_card_both_use_creative_f(self) -> None:
        from creative_key_sync import prepare_backing_context_sidebar_display_key

        session = _shape_of_you_session()
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        st = SimpleNamespace(session_state=session)
        prepare_backing_context_sidebar_display_key(st, session)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(state.practice_concert_key, "F")

    def test_style_jam_sidebar_prefers_backing_context_over_catalog_display_key(self) -> None:
        from creative_key_sync import prepare_creative_sidebar_display_key

        session = _entry_jam_session(bpm=75, key="F")
        session.update(
            {
                "studio_page": "backing",
                "active_catalog_pick_key": "Rock::Day Tripper",
                "song": "Day Tripper",
                "display_key": "G",
                "concert_key": "G",
            }
        )
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        st = SimpleNamespace(session_state=session)
        prepare_creative_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "F")
        self.assertEqual(session.get("concert_key"), "F")

    def test_sidebar_key_change_updates_resolver(self) -> None:
        from creative_key_sync import CREATIVE_CONCERT_KEY_SOURCE, invalidate_creative_backing_context

        session = _entry_jam_session(key="D")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["display_key"] = "E"
        session["concert_key"] = "E"
        session["improv_style_key"] = "E"
        session[CREATIVE_CONCERT_KEY_SOURCE] = "backing_sidebar"
        invalidate_creative_backing_context(session)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.practice_concert_key, "E")

    def test_alto_written_key_matches_between_resolver_and_sidebar(self) -> None:
        from creative_key_sync import prepare_backing_context_sidebar_display_key

        session = _shape_of_you_session(show_chart_in_instrument_key=True)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        st = SimpleNamespace(session_state=session)
        prepare_backing_context_sidebar_display_key(st, session)
        state = resolve_current_backing_musical_state(session)
        self.assertEqual(state.written_key, "D")
        self.assertEqual(state.chart_badge_value, "D")


class TestReturnButtonLabels(unittest.TestCase):
    def test_source_aware_return_labels(self) -> None:
        from backing_source_navigation import return_to_source_button_label

        entry = build_entry_jam_context(_entry_jam_session())
        self.assertEqual(return_to_source_button_label(entry), "🎨 Return to Creative Page")
        catalog = build_regular_song_context(
            {"song": "Day Tripper", "display_key": "G", "concert_key": "G"}
        )
        self.assertEqual(return_to_source_button_label(catalog), "🎵 Return to Catalog Song")


class TestSinglePlayTransport(unittest.TestCase):
    def test_play_button_label_in_step2(self) -> None:
        import inspect
        import streamlit_music_practice_app as app

        src = inspect.getsource(app._render_backing_step2_playback_action)
        self.assertIn("Play Backing Track", src)
        self.assertNotIn("gen_backing_btn", src)


class TestInstrumentChartModeReset(unittest.TestCase):
    def test_switch_flute_to_alto_written_off(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = {
            "instrument": "Alto Saxophone",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Flute",
            "display_key": "F",
            "concert_key": "F",
        }
        sync_written_key_instrument_anchor(session, "Alto Saxophone")
        self.assertFalse(session[CHART_IN_INSTRUMENT_KEY_KEY])

    def test_switch_sax_to_guitar_capo_off_shape_matches_concert(self) -> None:
        from instrument_transposition import (
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = {
            "instrument": "Guitar",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            "show_chart_in_instrument_key": True,
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "Am",
            "display_key": "C",
            "concert_key": "C",
        }
        sync_written_key_instrument_anchor(session, "Guitar")
        self.assertFalse(session["guitar_capo_enabled"])
        self.assertEqual(session["guitar_capo_shape_key"], "C")
        self.assertNotIn("_creative_chart_display_key", session)


if __name__ == "__main__":
    unittest.main()

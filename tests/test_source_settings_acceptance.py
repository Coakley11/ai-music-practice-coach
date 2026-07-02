"""Acceptance tests for per-source key/BPM isolation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession
from song_catalog.catalog import format_pick_key
from songs.key_state import mark_display_key_changed
from songs.playback_defaults import (
    active_song_sync_id,
    apply_backing_defaults_for_song,
    playback_song_id,
    sync_backing_bpm_from_slider,
)
from songs.practice_key_state import (
    BPM_BY_SOURCE_KEY,
    CREATIVE_STYLE_JAM_PICK,
    PRACTICE_KEY_BY_SOURCE_KEY,
    creative_jam_owns_practice_settings,
    get_practice_concert_key,
    get_source_bpm,
    resolve_practice_concert_key_for_pick,
    set_practice_concert_key,
    set_source_bpm,
)


def _shape_pick() -> str:
    return format_pick_key("Pop", "Shape of You")


class TestPerSourceKeyBacking(unittest.TestCase):
    def test_catalog_rebuild_uses_saved_practice_key(self) -> None:
        from music_source_ownership import rebuild_catalog_backing_from_canonical_pick

        pick = _shape_pick()
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": pick,
                "bpm": 96,
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        ctx = rebuild_catalog_backing_from_canonical_pick(
            session,
            pick_key=pick,
            reset_to_original=True,
        )
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(session.get("catalog_rebuild_result_key"), "Am")
        self.assertEqual(str(ctx.concert_key), "Am")
        self.assertEqual(str(ctx.display_key), "Am")

    def test_custom_backing_keeps_saved_eb_key(self) -> None:
        from backing_context import restore_custom_song_backing
        from custom_progression_lab import CPL_ACTIVE_KEY

        pick = "custom::trial-1"
        session = {
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
                "bpm": 100,
            },
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Eb"},
            "display_key": "Eb",
            "concert_key": "Eb",
        }
        restore_custom_song_backing(session)
        self.assertEqual(session.get("display_key"), "Eb")
        self.assertEqual(session.get("concert_key"), "Eb")

    def test_shape_am_refresh_stays_am(self) -> None:
        pick = _shape_pick()
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        resolved = resolve_practice_concert_key_for_pick(session, pick, original_key="Bm")
        self.assertEqual(resolved, "Am")


class TestCreativeCatalogIsolation(unittest.TestCase):
    def test_style_jam_key_does_not_write_shape_pick(self) -> None:
        shape = _shape_pick()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "C",
            "improv_style_bpm": 60,
            "improv_generated_sections": {"Style Jam": ["Cmaj7"]},
            "active_catalog_pick_key": shape,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape, "bpm": 96},
            "display_key": "C",
        }
        self.assertTrue(creative_jam_owns_practice_settings(session))
        st = SimpleNamespace(session_state=session)
        mark_display_key_changed(st)
        self.assertNotIn(shape, session.get(PRACTICE_KEY_BY_SOURCE_KEY, {}))
        self.assertEqual(session[PRACTICE_KEY_BY_SOURCE_KEY].get(CREATIVE_STYLE_JAM_PICK), "C")

    def test_style_jam_bpm_does_not_write_shape_bpm(self) -> None:
        shape = _shape_pick()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_bpm": 60,
            "active_catalog_pick_key": shape,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": shape, "bpm": 96},
        }
        st = SimpleNamespace(session_state=session)
        sync_backing_bpm_from_slider(st, slider_bpm=60)
        self.assertNotIn(shape, session.get(BPM_BY_SOURCE_KEY, {}))
        self.assertEqual(session[BPM_BY_SOURCE_KEY].get(CREATIVE_STYLE_JAM_PICK), 60)

    def test_catalog_rebuild_uses_bm_not_creative_leak(self) -> None:
        from music_source_ownership import rebuild_catalog_backing_from_canonical_pick

        shape = _shape_pick()
        session = {
            "active_catalog_pick_key": shape,
            "selected_song": {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": shape,
                "bpm": 96,
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {CREATIVE_STYLE_JAM_PICK: "C"},
            BPM_BY_SOURCE_KEY: {CREATIVE_STYLE_JAM_PICK: 60},
        }
        ctx = rebuild_catalog_backing_from_canonical_pick(
            session,
            pick_key=shape,
            reset_to_original=True,
        )
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(str(ctx.concert_key), "Bm")
        self.assertEqual(session.get("catalog_rebuild_result_bpm"), 96)


class TestCreativeRefreshPersistence(unittest.TestCase):
    def test_style_jam_hydrate_survives_stale_catalog_backing(self) -> None:
        from creative_session_state import hydrate_creative_session_for_page

        jam_sections = {"Bossa": ["Fmaj7", "Bbmaj7"]}
        shape = _shape_pick()
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "active_catalog_pick_key": shape,
            "backing_context": {
                "source": "regular_song",
                "song_title": "Shape of You",
                "key": "Bm",
                "concert_key": "Bm",
                "bpm": 96,
            },
            CREATIVE_SESSION_KEY: CreativeSession(
                session_id="style-jam",
                tool_type="entry_style_jam",
                entry_mode="Style Jam Mode",
                style="Bossa Nova",
                concert_key="F",
                display_key="F",
                bpm=75,
                mood="Bright",
                sections=jam_sections,
            ).to_dict(),
        }
        hydrate_creative_session_for_page(session)
        try:
            from session_widget_safe import apply_pending_widget_hydrates

            apply_pending_widget_hydrates(session)
        except ImportError:
            pass
        self.assertEqual(session.get("improv_entry_mode"), "Style Jam Mode")
        self.assertEqual(session.get("improv_style"), "Bossa Nova")
        self.assertEqual(session.get("improv_style_key"), "F")
        self.assertEqual(int(session.get("improv_style_bpm") or 0), 75)


class TestCustomKeySidebarPersistence(unittest.TestCase):
    def test_custom_sidebar_prefers_saved_practice_key_on_refresh(self) -> None:
        from creative_key_sync import prepare_backing_context_sidebar_display_key
        from custom_progression_lab import CPL_ACTIVE_KEY

        pick = "custom::trial-1"
        session = {
            "studio_page": "practice",
            "active_music_source": "custom",
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
            },
            "active_catalog_pick_key": pick,
            "backing_context": {
                "source": "custom_progression",
                "title": "Trial Song",
                "key": "D",
                "concert_key": "D",
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "E"},
            "display_key": "D",
            "concert_key": "D",
        }
        st = SimpleNamespace(session_state=session)
        prepare_backing_context_sidebar_display_key(st, session)
        self.assertEqual(session.get("display_key"), "E")
        self.assertEqual(session.get("concert_key"), "E")


class TestPerSourceBpmIsolation(unittest.TestCase):
    def test_switching_song_loads_default_not_previous_bpm(self) -> None:
        trial = "custom::trial-1"
        shape = _shape_pick()
        st = SimpleNamespace(
            session_state={
                "active_catalog_pick_key": shape,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape,
                    "bpm": 96,
                },
                BPM_BY_SOURCE_KEY: {trial: 120},
                "backing_track_bpm": 120,
                "bpm": 120,
            }
        )
        shape_pid = playback_song_id(
            is_custom=False,
            song_title="Shape of You",
            song_artist="Ed Sheeran",
        )
        sync_id = active_song_sync_id(pick_key=shape, playback_song_id=shape_pid, is_custom=False)
        bpm, _ = apply_backing_defaults_for_song(
            st,
            song_id=sync_id,
            default_bpm=96,
            default_groove="Pop groove",
        )
        self.assertEqual(bpm, 96)
        self.assertNotEqual(bpm, 120)

    def test_saved_bpm_restored_for_same_source(self) -> None:
        shape = _shape_pick()
        session = {
            "active_catalog_pick_key": shape,
            BPM_BY_SOURCE_KEY: {shape: 88},
        }
        self.assertEqual(get_source_bpm(session, shape, default=96), 88)

    def test_bpm_slider_writes_bpm_by_source(self) -> None:
        shape = _shape_pick()
        st = SimpleNamespace(
            session_state={
                "active_catalog_pick_key": shape,
                "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
            }
        )
        sync_backing_bpm_from_slider(st, slider_bpm=105)
        self.assertEqual(st.session_state[BPM_BY_SOURCE_KEY][shape], 105)

    def test_sources_do_not_share_keys(self) -> None:
        trial = "custom::trial-1"
        shape = _shape_pick()
        session = {
            "active_catalog_pick_key": trial,
            PRACTICE_KEY_BY_SOURCE_KEY: {shape: "Am", trial: "Eb"},
        }
        self.assertEqual(get_practice_concert_key(session, trial), "Eb")
        self.assertEqual(get_practice_concert_key(session, shape), "Am")


if __name__ == "__main__":
    unittest.main()

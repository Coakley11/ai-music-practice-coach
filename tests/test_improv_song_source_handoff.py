"""Tests for widget-safe Creative song source handoff."""

from __future__ import annotations

import unittest

from studio_page_state import (
    CREATIVE_BACKING_SONG_SOURCE_KEY,
    PENDING_IMPROV_SONG_SOURCE,
    apply_improv_song_source,
    flush_pending_improv_song_source,
    resolve_improv_song_source,
    sync_improv_song_source_for_handoff,
)


class TestImprovSongSourceHandoff(unittest.TestCase):
    def test_open_backing_handoff_does_not_write_widget_key(self) -> None:
        session = {
            "improv_song_source": "Custom progression",
            "creative_lab_analysis_mode": "Improvisation Intelligence",
        }
        catalog_calls: list[dict] = []
        custom_calls: list[dict] = []

        def _set_catalog(ss: dict) -> None:
            catalog_calls.append(dict(ss))

        def _set_custom(ss: dict) -> None:
            custom_calls.append(dict(ss))

        sync_improv_song_source_for_handoff(
            session,
            resolve_improv_song_source(session),
            set_catalog_source=_set_catalog,
            set_custom_source=_set_custom,
        )
        self.assertEqual(session["improv_song_source"], "Custom progression")
        self.assertEqual(session[CREATIVE_BACKING_SONG_SOURCE_KEY], "Custom progression")
        self.assertEqual(session[PENDING_IMPROV_SONG_SOURCE], "Custom progression")
        # SBI Custom is preview/handoff only — must not activate Global Custom.
        self.assertEqual(len(custom_calls), 0)
        self.assertEqual(len(catalog_calls), 0)

    def test_widget_safe_apply_skips_widget_key_and_global_source(self) -> None:
        from song_catalog.catalog import format_pick_key
        from source_session_state import SBI_PREVIEW_SOURCE_KEY

        shape_pick = format_pick_key("Pop", "Shape of You")
        session = {
            "improv_song_source": "Active song",
            "active_catalog_pick_key": shape_pick,
            "selected_song": {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": shape_pick,
            },
            "song": "Shape of You",
            "active_music_source": "catalog",
        }
        catalog_calls: list[dict] = []
        custom_calls: list[dict] = []

        def _set_catalog(ss: dict) -> None:
            catalog_calls.append(dict(ss))

        def _set_custom(ss: dict) -> None:
            custom_calls.append(dict(ss))

        apply_improv_song_source(
            session,
            "Custom progression",
            set_catalog_source=_set_catalog,
            set_custom_source=_set_custom,
            widget_safe=True,
        )
        self.assertEqual(session["improv_song_source"], "Active song")
        self.assertEqual(session[SBI_PREVIEW_SOURCE_KEY], "Custom progression")
        self.assertNotIn(CREATIVE_BACKING_SONG_SOURCE_KEY, session)
        self.assertEqual(session["active_catalog_pick_key"], shape_pick)
        self.assertEqual(session["song"], "Shape of You")
        self.assertEqual(len(custom_calls), 0)
        self.assertEqual(len(catalog_calls), 0)

        apply_improv_song_source(
            session,
            "Active song",
            set_catalog_source=_set_catalog,
            set_custom_source=_set_custom,
            widget_safe=True,
        )
        self.assertEqual(session[SBI_PREVIEW_SOURCE_KEY], "Active song")
        self.assertEqual(session["active_catalog_pick_key"], shape_pick)
        self.assertEqual(session["song"], "Shape of You")

    def test_flush_pending_seeds_widget_before_render(self) -> None:
        session = {PENDING_IMPROV_SONG_SOURCE: "Custom progression"}
        flush_pending_improv_song_source(session)
        self.assertEqual(session["improv_song_source"], "Custom progression")
        self.assertNotIn(PENDING_IMPROV_SONG_SOURCE, session)

    def test_resolve_prefers_preview_bucket_over_stale_handoff(self) -> None:
        from source_session_state import SBI_PREVIEW_SOURCE_KEY

        session = {
            "improv_song_source": "Active song",
            SBI_PREVIEW_SOURCE_KEY: "Custom progression",
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Active song",
        }
        self.assertEqual(resolve_improv_song_source(session), "Custom progression")

    def test_resolve_active_song_prefers_widget_over_custom_global_pick(self) -> None:
        from song_catalog.catalog import format_pick_key
        from source_session_state import SBI_PREVIEW_SOURCE_KEY

        shape_pick = format_pick_key("Pop", "Shape of You")
        session = {
            "improv_song_source": "Active song",
            SBI_PREVIEW_SOURCE_KEY: "Active song",
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Active song",
            "active_catalog_pick_key": "custom::trial-1",
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": "custom::trial-1"},
            "active_music_source": "custom_progression",
        }
        self.assertEqual(resolve_improv_song_source(session), "Active song")

    def test_preview_active_song_uses_catalog_snapshot_not_custom_pick(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY
        from source_session_state import SBI_PREVIEW_SOURCE_KEY

        shape_pick = format_pick_key("Pop", "Shape of You")
        session = {
            "improv_song_source": "Active song",
            SBI_PREVIEW_SOURCE_KEY: "Active song",
            "active_catalog_pick_key": "custom::trial-1",
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": "custom::trial-1"},
            "display_key": "E",
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape_pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape_pick,
                },
                "original_key": "Bm",
                "display_key": "Bm",
            },
            "catalog_session": {
                "pick_key": shape_pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape_pick,
                },
                "original_key": "Bm",
                "display_key": "Bm",
            },
        }
        from studio_page_state import resolve_improv_song_preview

        preview = resolve_improv_song_preview(session)
        self.assertEqual(preview["title"], "Shape of You")
        self.assertEqual(preview["source"], "Active song")
        self.assertEqual(preview["display_key"], "Bm")

    def test_handoff_back_to_active_song_restores_catalog_identity(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY, SOURCE_CATALOG

        shape_pick = format_pick_key("Pop", "Shape of You")
        session = {
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Active song",
            "active_catalog_pick_key": "custom::trial-1",
            "selected_song": {"title": "Trial Song", "key": "D", "pick_key": "custom::trial-1"},
            "song": "Trial Song",
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape_pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": shape_pick,
                },
                "original_key": "Bm",
            },
        }

        def _set_catalog(ss: dict) -> None:
            ss["active_music_source"] = SOURCE_CATALOG

        def _set_custom(_ss: dict) -> None:
            raise AssertionError("unexpected custom handoff")

        sync_improv_song_source_for_handoff(
            session,
            "Active song",
            set_catalog_source=_set_catalog,
            set_custom_source=_set_custom,
        )
        # Handoff stamps SBI preview only — does not mutate Global Active identity.
        self.assertEqual(session.get("improv_song_source"), "Active song")
        self.assertEqual(session.get(CREATIVE_BACKING_SONG_SOURCE_KEY), "Active song")
        self.assertEqual(session.get(PENDING_IMPROV_SONG_SOURCE), "Active song")
        self.assertEqual(session["active_catalog_pick_key"], "custom::trial-1")
        self.assertEqual(session["song"], "Trial Song")


class TestImprovTabSnapshot(unittest.TestCase):
    def test_creative_snapshot_includes_saved_sub_tab(self) -> None:
        from studio_page_persistence import capture_page_snapshot

        session = {
            "creative_improv_intelligence_tab": "Harmony Map",
            "improv_intelligence_tab": "Harmony Map",
        }
        snap = capture_page_snapshot(session, "creative")
        self.assertEqual(snap.get("creative_improv_intelligence_tab"), "Harmony Map")


if __name__ == "__main__":
    unittest.main()

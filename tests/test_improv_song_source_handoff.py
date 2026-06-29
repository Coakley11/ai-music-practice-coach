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
        self.assertEqual(len(custom_calls), 1)
        self.assertEqual(len(catalog_calls), 0)

    def test_widget_safe_apply_skips_widget_key(self) -> None:
        session = {"improv_song_source": "Active song"}

        def _set_catalog(_ss: dict) -> None:
            pass

        def _set_custom(_ss: dict) -> None:
            pass

        apply_improv_song_source(
            session,
            "Custom progression",
            set_catalog_source=_set_catalog,
            set_custom_source=_set_custom,
            widget_safe=True,
        )
        self.assertEqual(session["improv_song_source"], "Active song")
        self.assertEqual(session[CREATIVE_BACKING_SONG_SOURCE_KEY], "Custom progression")

    def test_flush_pending_seeds_widget_before_render(self) -> None:
        session = {PENDING_IMPROV_SONG_SOURCE: "Custom progression"}
        flush_pending_improv_song_source(session)
        self.assertEqual(session["improv_song_source"], "Custom progression")
        self.assertNotIn(PENDING_IMPROV_SONG_SOURCE, session)

    def test_resolve_prefers_saved_handoff_key(self) -> None:
        session = {
            "improv_song_source": "Active song",
            CREATIVE_BACKING_SONG_SOURCE_KEY: "Custom progression",
        }
        self.assertEqual(resolve_improv_song_source(session), "Custom progression")


if __name__ == "__main__":
    unittest.main()

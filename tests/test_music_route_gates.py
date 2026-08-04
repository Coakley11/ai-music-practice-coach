"""Route gates and navigation dedupe regression tests."""

from __future__ import annotations

import unittest
from typing import Any

from music_dev_route_baseline import route_perf_begin, route_perf_end
from music_nav_dedupe import save_page_snapshot_deduped
from music_route_gates import (
    guard_creative_tab_heavy,
    resolve_route_context,
    should_hydrate_catalog_on_creative_page,
    should_hydrate_creative_session_on_backing_page,
    should_restore_upload_analysis_session,
)


class TestRouteGates(unittest.TestCase):
    def test_generator_skips_catalog_hydrate(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
        }
        self.assertFalse(should_hydrate_catalog_on_creative_page(session))

    def test_song_based_hydrates_catalog(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Song-Based Improvisation",
            "improv_intelligence_tab": "Song-Based Improvisation",
        }
        self.assertTrue(should_hydrate_catalog_on_creative_page(session))

    def test_inactive_tab_blocks_missions_heavy(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Phrase / Motif",
        }
        self.assertFalse(guard_creative_tab_heavy(session, "Missions", "example_gen"))

    def test_regular_catalog_backing_skips_creative_hydrate(self) -> None:
        from backing_context import BackingContext, set_backing_context

        session: dict[str, Any] = {}
        set_backing_context(
            session,
            BackingContext(
                source="regular_song",
                source_label="Catalog",
                active_song_id="test-song",
                song_title="Test",
                key="C",
                display_key="C",
                concert_key="C",
                bpm=100,
                style="Pop",
                groove="Pop",
                progression=["C", "G"],
                sections=["Verse"],
                scope="Full song",
            ),
        )
        self.assertFalse(should_hydrate_creative_session_on_backing_page(session))

    def test_upload_restore_once_per_session(self) -> None:
        session: dict[str, Any] = {}
        self.assertTrue(should_restore_upload_analysis_session(session))
        session["_analysis_session_restore_done"] = True
        self.assertFalse(should_restore_upload_analysis_session(session))


class TestNavDedupe(unittest.TestCase):
    def test_duplicate_snapshot_save_skipped(self) -> None:
        session: dict[str, Any] = {"studio_page": "practice", "dev_mode": True}
        first = save_page_snapshot_deduped(session, "practice")
        second = save_page_snapshot_deduped(session, "practice")
        self.assertTrue(first)
        self.assertFalse(second)
        counters = session.get("_music_dev_perf_counters") or {}
        self.assertGreaterEqual(int(counters.get("page_snapshot_save_skipped") or 0), 1)


class TestRouteBaselineHistory(unittest.TestCase):
    def test_p50_recorded_after_runs(self) -> None:
        session: dict[str, Any] = {"dev_mode": True}
        for _ in range(5):
            route_perf_begin(session, "studio.creative")
            route_perf_end(session, "studio.creative")
        rec = (session.get("_music_dev_route_baselines") or {}).get("studio.creative")
        self.assertIsInstance(rec, dict)
        self.assertIsNotNone(rec.get("p50_ms"))
        self.assertGreaterEqual(int(rec.get("samples_n") or 0), 5)


if __name__ == "__main__":
    unittest.main()

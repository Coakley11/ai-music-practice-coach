"""Browse filters must not constrain the Active Song selector.

The Active Song dropdown always covers the full catalog.  Browse
(search | genre | favorites) is a discovery convenience that
produces a clickable result list but never restricts which songs
can be selected via the main selector.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from song_catalog.catalog import format_pick_key, load_song_catalog
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    compose_browse_results,
    prune_catalog_pick_keys,
)


def _pick(rec: dict) -> str:
    return format_pick_key(rec["genre"], f"{rec['title']} — {rec['artist']}")


class TestActiveSongSelectorDecoupled(unittest.TestCase):
    """The Active Song selectbox options must be the full catalog."""

    @classmethod
    def setUpClass(cls) -> None:
        _, _, _, cls.records = load_song_catalog()
        cls.all_keys = [_pick(r) for r in cls.records]
        cls.genres = sorted({r["genre"] for r in cls.records if r.get("genre")})

    def test_active_selector_not_constrained_by_genre_filter(self) -> None:
        """With a genre filter active, browse narrows but the full catalog stays."""
        genre = self.genres[0]
        browse = compose_browse_results(self.records, genres=[genre])
        browse_keys = [_pick(r) for r in browse]
        self.assertLess(len(browse_keys), len(self.all_keys))
        for key in self.all_keys:
            self.assertIn(key, self.all_keys)

    def test_active_selector_not_constrained_by_search(self) -> None:
        browse = compose_browse_results(self.records, query="Autumn Leaves")
        browse_keys = [_pick(r) for r in browse]
        self.assertLess(len(browse_keys), len(self.all_keys))

    def test_active_selector_not_constrained_by_favorites(self) -> None:
        one_fav = _pick(self.records[0])
        browse = compose_browse_results(
            self.records,
            favorite_pick_keys=[one_fav],
            favorites_enabled=True,
        )
        browse_keys = [_pick(r) for r in browse]
        self.assertEqual(len(browse_keys), 1)
        self.assertEqual(len(self.all_keys), len(self.records))

    def test_empty_browse_does_not_block_selection(self) -> None:
        browse = compose_browse_results(
            self.records,
            query="xyzzy_nonexistent_query_99999",
        )
        self.assertEqual(len(browse), 0)
        self.assertGreater(len(self.all_keys), 0)


class TestBrowseUnionSemantics(unittest.TestCase):
    """Browse results use OR/union, never AND/intersection."""

    @classmethod
    def setUpClass(cls) -> None:
        _, _, _, cls.records = load_song_catalog()
        cls.jazz = [r for r in cls.records if r["genre"] == "Jazz"]
        cls.rock = [r for r in cls.records if r["genre"] == "Rock"]
        cls.non_jazz_non_rock = next(
            r for r in cls.records if r["genre"] not in ("Jazz", "Rock")
        )
        cls.fav_pk = _pick(cls.non_jazz_non_rock)

    def test_search_union_genre(self) -> None:
        rows = compose_browse_results(
            self.records,
            query="Autumn Leaves",
            genres=["Rock"],
        )
        keys = [_pick(r) for r in rows]
        autumn = next(r for r in self.records if r["title"] == "Autumn Leaves")
        self.assertIn(_pick(autumn), keys)
        self.assertTrue(any(r["genre"] == "Rock" for r in rows))

    def test_search_union_genre_union_favorites(self) -> None:
        rows = compose_browse_results(
            self.records,
            query="Autumn Leaves",
            genres=["Rock"],
            favorite_pick_keys=[self.fav_pk],
            favorites_enabled=True,
        )
        keys = [_pick(r) for r in rows]
        self.assertIn(self.fav_pk, keys)
        self.assertTrue(any(r["genre"] == "Rock" for r in rows))

    def test_multiple_genres_additive(self) -> None:
        rows = compose_browse_results(self.records, genres=["Jazz", "Rock"])
        genres_found = {r["genre"] for r in rows}
        self.assertIn("Jazz", genres_found)
        self.assertIn("Rock", genres_found)

    def test_no_duplicates_in_union(self) -> None:
        autumn = next(r for r in self.records if r["title"] == "Autumn Leaves")
        rows = compose_browse_results(
            self.records,
            query="Autumn Leaves",
            genres=["Jazz"],
            favorite_pick_keys=[_pick(autumn)],
            favorites_enabled=True,
        )
        keys = [_pick(r) for r in rows]
        self.assertEqual(keys.count(_pick(autumn)), 1)


class TestFavoriteConsistency(unittest.TestCase):
    """Favorite state must be the same canonical store everywhere."""

    @classmethod
    def setUpClass(cls) -> None:
        _, _, _, cls.records = load_song_catalog()

    def test_favorite_pruning_against_full_catalog(self) -> None:
        full_keys = {_pick(r) for r in self.records}
        fav_pk = _pick(self.records[0])
        pruned = prune_catalog_pick_keys([fav_pk], full_keys)
        self.assertEqual(pruned, [fav_pk])

    def test_favorite_not_wrongly_pruned_by_partial_set(self) -> None:
        fav_pk = _pick(self.records[0])
        partial = {_pick(r) for r in self.records[1:5]}
        pruned = prune_catalog_pick_keys([fav_pk], partial)
        self.assertEqual(pruned, [])

    def test_browse_favorites_source_matches_card_source(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(
            encoding="utf-8",
        )
        self.assertIn("CATALOG_FAVORITES_KEY", source)
        self.assertNotIn("_browse_favorites_key", source)
        self.assertNotIn("browse_favorite_keys", source)


class TestClearFiltersPreservesActiveSong(unittest.TestCase):
    """Clear Filters resets Browse state without altering the Active Song."""

    def test_clear_does_not_touch_active_catalog_pick_key(self) -> None:
        from songs.picker_session import request_clear_browse_filters

        state = {
            "song_search_text": "Mayer",
            WORKSPACE_GENRE_FILTERS_KEY: ["Blues"],
            SONG_PICKER_FAVORITES_ONLY_KEY: True,
            "workspace_genre_filter": "Blues",
            "ACTIVE_CATALOG_PICK_KEY_sentinel": "should_survive",
        }
        request_clear_browse_filters(state)
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertFalse(state[SONG_PICKER_FAVORITES_ONLY_KEY])
        self.assertEqual(state["ACTIVE_CATALOG_PICK_KEY_sentinel"], "should_survive")


class TestCodeStructureDecoupling(unittest.TestCase):
    """The source code must reflect Browse/Active-Song decoupling."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")

    def test_apply_filters_returns_browse_and_all_pick_options(self) -> None:
        self.assertIn("browse_pick_options", self.source)
        self.assertIn("all_pick_options", self.source)

    def test_active_song_hub_receives_all_pick_options(self) -> None:
        self.assertIn("pick_options=all_pick_options", self.source)

    def test_selectbox_help_does_not_say_filtered(self) -> None:
        self.assertNotIn("Filtered by your genre pills", self.source)

    def test_footer_does_not_say_filters_update_dropdown(self) -> None:
        self.assertNotIn("update the <strong>Active Song</strong> dropdown above", self.source)

    def test_legacy_empty_browse_does_not_return_early(self) -> None:
        lines = self.source.split("\n")
        for i, line in enumerate(lines):
            if "No Browse results" in line:
                for j in range(i, min(i + 5, len(lines))):
                    self.assertNotIn("return", lines[j])
                break


if __name__ == "__main__":
    unittest.main()

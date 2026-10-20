"""Browse Search, Genre, and Favorites compose as independent union sources."""

from __future__ import annotations

import unittest
from pathlib import Path

from song_catalog.catalog import format_pick_key, load_song_catalog
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_TEXT_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    commit_browse_search_text,
    compose_browse_results,
    effective_browse_filters,
    request_clear_browse_filters,
)


class BrowseUnionAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _library, _picker, _genres, records = load_song_catalog()
        cls.records = records
        cls.autumn = next(row for row in records if row["title"] == "Autumn Leaves")
        cls.autumn_pk = cls.pick_key(cls.autumn)
        cls.favorite = next(row for row in records if row["genre"] not in {"Jazz", "Rock"})
        cls.favorite_pk = cls.pick_key(cls.favorite)

    @staticmethod
    def pick_key(row: dict) -> str:
        return format_pick_key(row["genre"], f"{row['title']} — {row['artist']}")

    def result(self, *, query="", genres=(), favorites=(), favorites_on=False):
        return compose_browse_results(
            self.records,
            query=query,
            genres=genres,
            favorite_pick_keys=favorites,
            favorites_enabled=favorites_on,
        )

    def keys(self, **kwargs) -> list[str]:
        return [self.pick_key(row) for row in self.result(**kwargs)]

    def test_browse1_no_filters_returns_full_catalog(self) -> None:
        self.assertEqual(self.keys(), [self.pick_key(row) for row in self.records])

    def test_browse2_search_only(self) -> None:
        rows = self.result(query="autumn leaves")
        self.assertIn(self.autumn_pk, [self.pick_key(row) for row in rows])

    def test_browse3_one_genre_only(self) -> None:
        rows = self.result(genres=["Jazz"])
        self.assertTrue(rows)
        self.assertTrue(all(row["genre"] == "Jazz" for row in rows))

    def test_browse4_two_genres_are_union(self) -> None:
        rows = self.result(genres=["Jazz", "Rock"])
        self.assertEqual({row["genre"] for row in rows}, {"Jazz", "Rock"})

    def test_browse5_favorites_only(self) -> None:
        self.assertEqual(
            self.keys(favorites=[self.favorite_pk], favorites_on=True),
            [self.favorite_pk],
        )

    def test_browse6_search_plus_matching_genre_is_union(self) -> None:
        keys = self.keys(query="autumn leaves", genres=["Jazz"])
        self.assertIn(self.autumn_pk, keys)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreater(len(keys), 1)

    def test_browse7_search_plus_unrelated_genre_keeps_both(self) -> None:
        rows = self.result(query="autumn leaves", genres=["Rock"])
        self.assertIn(self.autumn_pk, [self.pick_key(row) for row in rows])
        self.assertTrue(any(row["genre"] == "Rock" for row in rows))

    def test_browse8_search_plus_two_genres(self) -> None:
        rows = self.result(query="autumn leaves", genres=["Jazz", "Rock"])
        self.assertIn(self.autumn_pk, [self.pick_key(row) for row in rows])
        self.assertTrue(any(row["genre"] == "Jazz" for row in rows))
        self.assertTrue(any(row["genre"] == "Rock" for row in rows))

    def test_browse9_search_genre_and_favorites(self) -> None:
        rows = self.result(
            query="Ed Sheeran",
            genres=["Jazz"],
            favorites=[self.favorite_pk],
            favorites_on=True,
        )
        keys = [self.pick_key(row) for row in rows]
        self.assertTrue(any("Ed Sheeran" in row["artist"] for row in rows))
        self.assertTrue(any(row["genre"] == "Jazz" for row in rows))
        self.assertIn(self.favorite_pk, keys)

    def test_browse10_overlap_renders_once_by_canonical_pick_key(self) -> None:
        keys = self.keys(
            query="autumn leaves",
            genres=["Jazz"],
            favorites=[self.autumn_pk],
            favorites_on=True,
        )
        self.assertEqual(keys.count(self.autumn_pk), 1)

    def test_canonical_identity_is_not_display_title_alone(self) -> None:
        duplicate_titles = [
            {"genre": "Jazz", "title": "Same", "artist": "Artist"},
            {"genre": "Rock", "title": "Same", "artist": "Artist"},
        ]
        rows = compose_browse_results(duplicate_titles, genres=["Jazz", "Rock"])
        self.assertEqual(len(rows), 2)

    def test_browse11_favorites_off_removes_only_favorite_only_rows(self) -> None:
        base = set(self.keys(query="autumn leaves", genres=["Jazz"]))
        with_favorite = set(self.keys(
            query="autumn leaves", genres=["Jazz"],
            favorites=[self.favorite_pk], favorites_on=True,
        ))
        self.assertEqual(with_favorite - base, {self.favorite_pk})

    def test_browse12_removing_one_genre_removes_only_its_contribution(self) -> None:
        both = set(self.keys(genres=["Jazz", "Rock"]))
        jazz = set(self.keys(genres=["Jazz"]))
        rock = {self.pick_key(row) for row in self.records if row["genre"] == "Rock"}
        self.assertEqual(both - jazz, rock)

    def test_browse13_and_14_empty_search_is_authoritative(self) -> None:
        state = {SONG_SEARCH_TEXT_KEY: "stale saved value"}
        state[SONG_SEARCH_TEXT_KEY] = ""
        commit_browse_search_text(state)
        self.assertEqual(state[SONG_SEARCH_TEXT_KEY], "")
        self.assertTrue(state["_song_search_user_touched"])

    def test_browse15_clear_filters_resets_all_sources_and_legacy_state(self) -> None:
        state = {
            SONG_SEARCH_TEXT_KEY: "Autumn Leaves",
            WORKSPACE_GENRE_FILTERS_KEY: ["Jazz", "Rock"],
            SONG_PICKER_FAVORITES_ONLY_KEY: True,
            "workspace_genre_filter": "Jazz",
        }
        request_clear_browse_filters(state)
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertFalse(state[SONG_PICKER_FAVORITES_ONLY_KEY])
        self.assertEqual(state["workspace_genre_filter"], "All genres")
        self.assertTrue(state["song_search_reset_requested"])

    def test_filter_resolver_never_suspends_another_source(self) -> None:
        state = {
            WORKSPACE_GENRE_FILTERS_KEY: ["Jazz", "Rock"],
            SONG_PICKER_FAVORITES_ONLY_KEY: True,
            CATALOG_FAVORITES_KEY: [self.favorite_pk],
        }
        self.assertEqual(effective_browse_filters(state, "Autumn"), (["Jazz", "Rock"], True))

    def test_browse16_favorite_uses_normal_genre_renderer_and_star(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("genre_search_result_row_key", source)
        self.assertIn('favorite_star = "★ " if pk in favorite_keys else ""', source)
        self.assertIn("genre_search_result_css", source)

    def test_browse17_redundant_favorites_section_is_removed(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("def _render_active_song_favorites_switch", source)
        self.assertNotIn('key=f"favorite_pick_{pk}"', source)
        self.assertIn('key="picker_active_song_favorite"', source)
        self.assertIn("_render_last_catalog_song_shortcut", source)


if __name__ == "__main__":
    unittest.main()

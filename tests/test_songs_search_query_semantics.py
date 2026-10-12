"""Songs search: matching semantics, and filters that silently hide matches.

Reported: typing ``Scientist`` / ``Pop`` + Enter returned no songs. Both commits
before and after the styling merge match correctly; the zero came from a genre
pill / Favorites-only filter that is saved with the profile and AND-ed with the
typed query, with no visible cue. Matching itself is pinned here, and the filter
state is now described and clearable without losing the typed query.
"""

from __future__ import annotations

import unittest

from song_catalog.catalog import load_song_catalog, search_records
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    describe_active_browse_filters,
    request_clear_browse_filters,
    request_clear_genre_and_favorites_filters,
)


class TestSearchMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        library, picker, _g, _r = load_song_catalog()
        cls.records = [
            dict(rec, genre=genre) if "genre" not in rec else rec
            for genre, songs in picker.items()
            for rec in songs.values()
        ]

    def titles(self, query: str, **kw) -> list[str]:
        return [r["title"] for r in search_records(self.records, query, limit=500, **kw)]

    def test_title_substring(self) -> None:
        self.assertIn("The Scientist", self.titles("Scientist"))
        self.assertIn("The Scientist", self.titles("scient"))

    def test_artist_substring(self) -> None:
        found = search_records(self.records, "Mayer", limit=500)
        self.assertGreaterEqual(len(found), 5)
        self.assertTrue(all("Mayer" in r["artist"] for r in found))

    def test_genre_category_is_searchable(self) -> None:
        for genre in ("Pop", "Jewish", "Rock"):
            found = search_records(self.records, genre, limit=500)
            own = [r for r in found if r["genre"] == genre]
            self.assertGreaterEqual(len(own), 3, genre)

    def test_query_is_case_insensitive(self) -> None:
        self.assertEqual(self.titles("pOp"), self.titles("pop"))
        self.assertEqual(self.titles("POP"), self.titles("Pop"))
        self.assertEqual(self.titles("sCiEnTiSt"), self.titles("scientist"))

    def test_a_genre_pill_is_anded_with_the_query(self) -> None:
        """Pins the behaviour that made a leftover pill hide matches."""
        self.assertEqual(self.titles("Scientist", genres=["Jewish"]), [])
        self.assertIn("The Scientist", self.titles("Scientist", genres=["Pop"]))


class TestHiddenFilterNotice(unittest.TestCase):
    def test_describes_the_filters_that_narrow_the_search(self) -> None:
        self.assertEqual(describe_active_browse_filters({}), [])
        state = {WORKSPACE_GENRE_FILTERS_KEY: ["Jewish", "Blues"], SONG_PICKER_FAVORITES_ONLY_KEY: True}
        self.assertEqual(
            describe_active_browse_filters(state), ["genre Blues, Jewish", "Favorites only"]
        )

    def test_clearing_hidden_filters_keeps_the_typed_query(self) -> None:
        state = {
            WORKSPACE_GENRE_FILTERS_KEY: ["Jewish"],
            SONG_PICKER_FAVORITES_ONLY_KEY: True,
            "song_search_text": "Scientist",
            CATALOG_FAVORITES_KEY: ["x"],
        }
        request_clear_genre_and_favorites_filters(state)
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertFalse(state[SONG_PICKER_FAVORITES_ONLY_KEY])
        self.assertEqual(state["song_search_text"], "Scientist")
        self.assertEqual(state[CATALOG_FAVORITES_KEY], ["x"], "saved favorites are not deleted")

    def test_the_existing_clear_filters_button_is_unchanged(self) -> None:
        state = {WORKSPACE_GENRE_FILTERS_KEY: ["Rock"], SONG_PICKER_FAVORITES_ONLY_KEY: True}
        request_clear_browse_filters(state)
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertTrue(state.get("_song_search_reset_requested") or any(
            "reset" in k for k in state if state[k] is True
        ))


if __name__ == "__main__":
    unittest.main()

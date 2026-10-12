"""Songs search: matching semantics, and text search vs saved browsing filters.

Product rule: when the search box has any text, the search covers the whole
catalog and the saved genre pills / Favorites-only are *suspended* -- not erased.
With an empty box those saved filters apply as before.
(Reported symptom: ``Scientist`` / ``Pop`` + Enter returned nothing because a
leftover pill or Favorites toggle was AND-ed with the query.)
"""

from __future__ import annotations

import unittest

from song_catalog.catalog import load_song_catalog, search_records
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    effective_browse_filters,
    request_clear_browse_filters,
    text_search_active,
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


class TestTextSearchSuspendsBrowsingFilters(unittest.TestCase):
    SAVED = {
        WORKSPACE_GENRE_FILTERS_KEY: ["Jewish"],
        SONG_PICKER_FAVORITES_ONLY_KEY: True,
        CATALOG_FAVORITES_KEY: ["fav-1"],
    }

    def state(self, **over) -> dict:
        out = {k: (list(v) if isinstance(v, list) else v) for k, v in self.SAVED.items()}
        out.update(over)
        return out

    def test_empty_query_applies_the_saved_filters(self) -> None:
        for q in ("", "   ", None):
            genres, fav_only = effective_browse_filters(self.state(), q)
            self.assertEqual(genres, ["Jewish"], repr(q))
            self.assertTrue(fav_only, repr(q))

    def test_non_empty_query_bypasses_genre_and_favorites(self) -> None:
        for q in ("Scientist", "Pop", " Mayer ", "x"):
            self.assertEqual(effective_browse_filters(self.state(), q), ([], False), q)
            self.assertTrue(text_search_active(q))

    def test_saved_filters_are_never_written_or_erased(self) -> None:
        state = self.state(song_search_text="Scientist")
        before = {k: (list(v) if isinstance(v, list) else v) for k, v in state.items()}
        effective_browse_filters(state, "Scientist")
        self.assertEqual(state, before)

    def test_filters_resume_exactly_when_the_query_is_cleared(self) -> None:
        state = self.state(**{WORKSPACE_GENRE_FILTERS_KEY: ["Jewish", "Blues"]})
        self.assertEqual(effective_browse_filters(state, "Mayer"), ([], False))
        genres, fav_only = effective_browse_filters(state, "")
        self.assertEqual(sorted(genres), ["Blues", "Jewish"])
        self.assertTrue(fav_only)

    def test_result_sets_follow_the_rule_end_to_end(self) -> None:
        library, picker, _g, _r = load_song_catalog()
        records = [
            dict(rec, genre=genre) if "genre" not in rec else rec
            for genre, songs in picker.items()
            for rec in songs.values()
        ]

        def result(state: dict, query: str) -> list[str]:
            genres, _fav = effective_browse_filters(state, query)
            return [
                r["title"]
                for r in search_records(records, query, genres=genres or None, limit=500)
            ]

        jewish = self.state(**{SONG_PICKER_FAVORITES_ONLY_KEY: False})
        self.assertIn("The Scientist", result(jewish, "Scientist"))
        self.assertGreaterEqual(len(result(jewish, "Pop")), 20)
        browse = result(jewish, "")
        self.assertTrue(browse and len(browse) < len(records))
        self.assertNotIn("The Scientist", browse)   # Jewish browsing resumes on clear

    def test_the_old_recovery_ui_is_gone(self) -> None:
        from pathlib import Path

        src = (Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py").read_text(
            encoding="utf-8"
        )
        for gone in ("browse_search_clear_hidden_filters", "hidden by your active filter"):
            self.assertNotIn(gone, src)
        import songs.picker_session as ps

        self.assertFalse(hasattr(ps, "request_clear_genre_and_favorites_filters"))
        self.assertFalse(hasattr(ps, "describe_active_browse_filters"))

    def test_the_existing_clear_filters_button_is_unchanged(self) -> None:
        state = {WORKSPACE_GENRE_FILTERS_KEY: ["Rock"], SONG_PICKER_FAVORITES_ONLY_KEY: True}
        request_clear_browse_filters(state)
        self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertFalse(state[SONG_PICKER_FAVORITES_ONLY_KEY])


if __name__ == "__main__":
    unittest.main()

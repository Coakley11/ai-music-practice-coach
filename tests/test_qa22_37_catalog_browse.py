"""Issue 29: Songs Catalog browse data layer (search, genre, Favorites, Clear Filters) on the real 119-song catalog.

Browse semantics are ADDITIVE (Search | Genres | Favorites) by earlier product decision (5c0a45f5);
these tests pin the behaviours the QA issue lists that do hold, and document the additive rule explicitly.
"""
import unittest

from song_catalog.catalog import _merge_records, format_pick_key
from songs.picker_session import (
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_RESET_REQUESTED_KEY,
    SONG_SEARCH_TEXT_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    compose_browse_results,
    request_clear_browse_filters,
)

RECORDS = _merge_records()


def _pk(r):
    return format_pick_key(r["genre"], f"{r['title']} {chr(0x2014)} {r['artist']}")


def _titles(rows):
    return [r["title"] for r in rows]


class TestBrowse(unittest.TestCase):
    def test_catalog_size(self):
        self.assertGreaterEqual(len(RECORDS), 119)

    def test_title_search(self):
        for q, title in (("Attention", "Attention"), ("Blackbird", "Blackbird"), ("say", "Say")):
            self.assertIn(title, _titles(compose_browse_results(RECORDS, query=q)))
        self.assertEqual(_titles(compose_browse_results(RECORDS, query="Blackbird")), ["Blackbird"])

    def test_artist_search(self):
        rows = compose_browse_results(RECORDS, query="Beatles")
        self.assertTrue(rows)
        self.assertTrue(all("beatles" in r["artist"].lower() or "beatles" in str(r).lower() for r in rows))

    def test_genre_filter(self):
        rows = compose_browse_results(RECORDS, genres=["Blues"])
        self.assertTrue(rows)
        self.assertTrue(all(r["genre"] == "Blues" for r in rows))

    def test_favorites_only_shows_favorites_and_disabling_restores_all(self):
        favs = [_pk(RECORDS[3]), _pk(RECORDS[40])]
        shown = compose_browse_results(RECORDS, favorite_pick_keys=favs, favorites_enabled=True)
        self.assertEqual({_pk(r) for r in shown}, set(favs))
        self.assertEqual(len(compose_browse_results(RECORDS, favorite_pick_keys=favs, favorites_enabled=False)), len(RECORDS))

    def test_no_favorites_means_empty_result_not_everything(self):
        self.assertEqual(compose_browse_results(RECORDS, favorites_enabled=True), [])

    def test_no_match_search_is_empty(self):
        self.assertEqual(compose_browse_results(RECORDS, query="zzzz-no-such-song"), [])

    def test_additive_rule_is_documented_behaviour(self):
        both = {r["title"] for r in compose_browse_results(RECORDS, query="Attention", genres=["Blues"])}
        self.assertIn("Attention", both)
        self.assertTrue({r["title"] for r in compose_browse_results(RECORDS, genres=["Blues"])} <= both)

    def test_clear_filters_resets_everything_without_touching_favorites_or_active_song(self):
        ss = {
            WORKSPACE_GENRE_FILTERS_KEY: ["Blues"], SONG_PICKER_FAVORITES_ONLY_KEY: True, SONG_SEARCH_TEXT_KEY: "say",
            CATALOG_FAVORITES_KEY: ["a", "b"], "selected_song": {"title": "Say"},
        }
        request_clear_browse_filters(ss)
        self.assertTrue(ss[SONG_SEARCH_RESET_REQUESTED_KEY])
        apply_picker_session_resets(ss)
        self.assertEqual(ss[SONG_SEARCH_TEXT_KEY], "")
        self.assertEqual(ss[WORKSPACE_GENRE_FILTERS_KEY], [])
        self.assertFalse(ss[SONG_PICKER_FAVORITES_ONLY_KEY])
        self.assertEqual(ss[CATALOG_FAVORITES_KEY], ["a", "b"])
        self.assertEqual(ss["selected_song"], {"title": "Say"})
        self.assertEqual(len(compose_browse_results(RECORDS, query=ss[SONG_SEARCH_TEXT_KEY], genres=ss[WORKSPACE_GENRE_FILTERS_KEY])), len(RECORDS))


if __name__ == "__main__":
    unittest.main()

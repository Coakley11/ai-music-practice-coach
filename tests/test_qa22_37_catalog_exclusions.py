"""Issue 29 (final decision): Browse stays ADDITIVE (Search | Genres | Favorites) and each result has an X
that hides it from the current view only. Real 119-song catalog."""
import unittest

from song_catalog.catalog import _merge_records, format_pick_key
from songs.picker_session import (
    BROWSE_EXCLUDED_PICK_KEYS_KEY,
    CATALOG_FAVORITES_KEY,
    SONG_PICKER_FAVORITES_ONLY_KEY,
    SONG_SEARCH_RESET_REQUESTED_KEY,
    SONG_SEARCH_TEXT_KEY,
    WORKSPACE_GENRE_FILTERS_KEY,
    apply_picker_session_resets,
    browse_excluded_pick_keys,
    compose_browse_results,
    exclude_browse_pick_key,
    request_clear_browse_filters,
)

RECORDS = _merge_records()


def _pk(r):
    return format_pick_key(r["genre"], f"{r['title']} {chr(0x2014)} {r['artist']}")


def _browse(state, query=None):
    q = state.get(SONG_SEARCH_TEXT_KEY, "") if query is None else query
    return compose_browse_results(
        RECORDS, query=q, genres=state.get(WORKSPACE_GENRE_FILTERS_KEY) or [],
        favorite_pick_keys=state.get(CATALOG_FAVORITES_KEY) or [],
        favorites_enabled=bool(state.get(SONG_PICKER_FAVORITES_ONLY_KEY)),
        excluded_pick_keys=browse_excluded_pick_keys(state),
    )


class TestAdditiveWithExclusions(unittest.TestCase):
    def setUp(self):
        jazz = [r for r in RECORDS if r["genre"] == "Jazz"]
        self.assertTrue(jazz)
        self.favs = [_pk(RECORDS[0]), _pk(jazz[0]), _pk(next(r for r in RECORDS if r["genre"] == "Blues"))]
        self.state = {CATALOG_FAVORITES_KEY: list(self.favs)}

    def test_union_search_genre_favorites_unique(self):
        mayer = {_pk(r) for r in compose_browse_results(RECORDS, query="Mayer")}
        self.assertTrue(mayer)
        jazz = {_pk(r) for r in RECORDS if r["genre"] == "Jazz"}
        self.state.update({SONG_SEARCH_TEXT_KEY: "Mayer"})
        self.assertEqual({_pk(r) for r in _browse(self.state)}, mayer)
        self.state[WORKSPACE_GENRE_FILTERS_KEY] = ["Jazz"]
        rows = _browse(self.state)
        self.assertEqual({_pk(r) for r in rows}, mayer | jazz)
        self.assertEqual(len(rows), len({_pk(r) for r in rows}))                      # one row per song
        self.state[SONG_PICKER_FAVORITES_ONLY_KEY] = True
        rows = _browse(self.state)
        self.assertEqual({_pk(r) for r in rows}, mayer | jazz | set(self.favs))
        self.assertEqual(len(rows), len({_pk(r) for r in rows}))

    def test_x_removes_only_that_song_and_keeps_favorites_and_catalog(self):
        self.state.update({SONG_SEARCH_TEXT_KEY: "Mayer", WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"], SONG_PICKER_FAVORITES_ONLY_KEY: True})
        before = _browse(self.state)
        n = len(before)
        favs_before = list(self.state[CATALOG_FAVORITES_KEY])
        records_before = [dict(r) for r in RECORDS]
        victim = _pk(before[0])
        exclude_browse_pick_key(self.state, victim)
        after = _browse(self.state)
        self.assertEqual(len(after), n - 1)
        self.assertNotIn(victim, {_pk(r) for r in after})
        self.assertEqual({_pk(r) for r in before} - {victim}, {_pk(r) for r in after})
        self.assertEqual(self.state[CATALOG_FAVORITES_KEY], favs_before)
        self.assertEqual(RECORDS, records_before)

    def test_x_works_for_a_song_matching_every_source_and_for_several_removals(self):
        fav_jazz = self.favs[1]
        rec = next(r for r in RECORDS if _pk(r) == fav_jazz)
        self.state.update({SONG_SEARCH_TEXT_KEY: rec["title"], WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"], SONG_PICKER_FAVORITES_ONLY_KEY: True})
        self.assertIn(fav_jazz, {_pk(r) for r in _browse(self.state)})
        exclude_browse_pick_key(self.state, fav_jazz)                                 # matches search + genre + favorite
        self.assertNotIn(fav_jazz, {_pk(r) for r in _browse(self.state)})
        n = len(_browse(self.state))
        for r in _browse(self.state)[:3]:
            exclude_browse_pick_key(self.state, _pk(r))
        self.assertEqual(len(_browse(self.state)), n - 3)
        exclude_browse_pick_key(self.state, fav_jazz)                                 # idempotent
        self.assertEqual(self.state[BROWSE_EXCLUDED_PICK_KEYS_KEY].count(fav_jazz), 1)

    def test_exclusions_persist_across_reruns_and_filter_changes(self):
        self.state[WORKSPACE_GENRE_FILTERS_KEY] = ["Jazz"]
        victim = _pk(_browse(self.state)[0])
        exclude_browse_pick_key(self.state, victim)
        for _ in range(3):                                                            # reruns recompute the same view from the same state
            self.assertNotIn(victim, {_pk(r) for r in _browse(self.state)})
        self.state[SONG_SEARCH_TEXT_KEY] = "x"                                        # search edits don't resurrect it
        self.state[SONG_SEARCH_TEXT_KEY] = ""
        self.assertNotIn(victim, {_pk(r) for r in _browse(self.state)})

    def test_clear_filters_empties_browse_clears_exclusions_keeps_favorites(self):
        self.state.update({SONG_SEARCH_TEXT_KEY: "Mayer", WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"], SONG_PICKER_FAVORITES_ONLY_KEY: True,
                           "selected_song": {"pick_key": "keep-me"}})
        exclude_browse_pick_key(self.state, _pk(_browse(self.state)[0]))
        favs_before = list(self.state[CATALOG_FAVORITES_KEY])
        request_clear_browse_filters(self.state)
        self.assertTrue(self.state.get(SONG_SEARCH_RESET_REQUESTED_KEY))
        apply_picker_session_resets(self.state)                                       # next rerun, before the widget is drawn
        self.assertEqual(self.state[SONG_SEARCH_TEXT_KEY], "")
        self.assertEqual(browse_excluded_pick_keys(self.state), [])
        self.assertEqual(_browse(self.state), [])            # Clear Filters leaves an EMPTY list, not 119 songs
        self.assertGreaterEqual(len(RECORDS), 119)           # ... while the catalog itself is intact
        self.assertEqual(self.state[CATALOG_FAVORITES_KEY], favs_before)
        self.assertEqual(self.state["selected_song"], {"pick_key": "keep-me"})

    def test_search_deleted_returns_to_other_sources_and_empty_union_is_empty(self):
        self.state.update({SONG_SEARCH_TEXT_KEY: "Mayer", WORKSPACE_GENRE_FILTERS_KEY: ["Jazz"]})
        with_search = len(_browse(self.state))
        self.state[SONG_SEARCH_TEXT_KEY] = ""                                         # Backspace + Enter
        self.assertLess(len(_browse(self.state)), with_search)
        self.assertEqual(len(_browse(self.state)), len([r for r in RECORDS if r["genre"] == "Jazz"]))
        self.assertEqual(compose_browse_results(RECORDS, query="zzzznotasong"), [])


if __name__ == "__main__":
    unittest.main()

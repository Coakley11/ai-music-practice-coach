"""Songs Browser (Nov 3 2026 clarification): additive union of Search | Genres | Favorites, de-duplicated,
over an EMPTY default - no criterion active means no rows, never the whole catalog.

Removing one criterion removes only its unique contribution; removing the last one returns to zero.
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
    browse_excluded_pick_keys,
    compose_browse_results,
    exclude_browse_pick_key,
    request_clear_browse_filters,
    toggle_favorites_filter,
    toggle_genre_filter,
)

RECORDS = _merge_records()
QUERY = "Mayer"
GENRE = "Jazz"


def _pk(r):
    return format_pick_key(r["genre"], f"{r['title']} {chr(0x2014)} {r['artist']}")


def _keys(state):
    rows = compose_browse_results(
        RECORDS,
        query=state.get(SONG_SEARCH_TEXT_KEY, ""),
        genres=state.get(WORKSPACE_GENRE_FILTERS_KEY) or [],
        favorite_pick_keys=state.get(CATALOG_FAVORITES_KEY) or [],
        favorites_enabled=bool(state.get(SONG_PICKER_FAVORITES_ONLY_KEY)),
        excluded_pick_keys=browse_excluded_pick_keys(state),
    )
    return [_pk(r) for r in rows]


MAYER = {_pk(r) for r in compose_browse_results(RECORDS, query=QUERY)}
JAZZ = {_pk(r) for r in RECORDS if r["genre"] == GENRE}


class TestEmptyDefault(unittest.TestCase):
    def test_catalog_is_large_but_browse_opens_empty(self):
        self.assertGreaterEqual(len(RECORDS), 119)
        self.assertEqual(compose_browse_results(RECORDS), [])
        self.assertEqual(_keys({}), [])

    def test_blank_search_text_is_not_a_criterion(self):
        for blank in ("", "   ", None):
            self.assertEqual(compose_browse_results(RECORDS, query=blank), [], repr(blank))

    def test_favorites_on_with_no_favorites_is_empty_not_everything(self):
        self.assertEqual(compose_browse_results(RECORDS, favorites_enabled=True, favorite_pick_keys=[]), [])


class TestEachCriterionAlone(unittest.TestCase):
    def test_search_alone(self):
        rows = _keys({SONG_SEARCH_TEXT_KEY: QUERY})
        self.assertTrue(rows)
        self.assertEqual(set(rows), MAYER)
        self.assertLess(len(rows), len(RECORDS))

    def test_genre_alone(self):
        self.assertEqual(set(_keys({WORKSPACE_GENRE_FILTERS_KEY: [GENRE]})), JAZZ)

    def test_favorites_alone(self):
        favs = [_pk(RECORDS[3]), _pk(RECORDS[40])]
        state = {CATALOG_FAVORITES_KEY: favs, SONG_PICKER_FAVORITES_ONLY_KEY: True}
        self.assertEqual(set(_keys(state)), set(favs))


class TestUnionAndRemoval(unittest.TestCase):
    """The exact sequence from the assignment: build up, then peel back one criterion at a time."""

    def setUp(self):
        fav_rock = next(_pk(r) for r in RECORDS if r["genre"] == "Rock")
        fav_jazz = next(_pk(r) for r in RECORDS if r["genre"] == GENRE)          # overlaps the Jazz filter
        self.favs = [fav_rock, fav_jazz]
        self.state = {CATALOG_FAVORITES_KEY: list(self.favs)}

    def test_build_up_then_peel_back(self):
        s = self.state
        s[SONG_SEARCH_TEXT_KEY] = QUERY                                           # 1. search
        self.assertEqual(set(_keys(s)), MAYER)
        toggle_genre_filter(s, GENRE)                                             # 2. + Jazz
        self.assertEqual(set(_keys(s)), MAYER | JAZZ)
        toggle_favorites_filter(s)                                                # 3. + Favorites
        everything = MAYER | JAZZ | set(self.favs)
        self.assertEqual(set(_keys(s)), everything)
        self.assertEqual(len(_keys(s)), len(set(_keys(s))))                       # each song once

        s[SONG_SEARCH_TEXT_KEY] = ""                                              # backspace + Enter
        self.assertEqual(set(_keys(s)), JAZZ | set(self.favs))
        mayer_only = MAYER - JAZZ - set(self.favs)
        self.assertTrue(mayer_only)                                               # Mayer-only songs exist
        self.assertFalse(mayer_only & set(_keys(s)))                              # and they really left

        toggle_genre_filter(s, GENRE)                                             # untoggle Jazz
        self.assertEqual(set(_keys(s)), set(self.favs))

        toggle_favorites_filter(s)                                                # untoggle Favorites
        self.assertEqual(_keys(s), [])                                            # back to zero, NOT 119

    def test_a_song_matching_every_criterion_appears_once(self):
        fav_jazz = self.favs[1]
        rec = next(r for r in RECORDS if _pk(r) == fav_jazz)
        s = dict(self.state)
        s[SONG_SEARCH_TEXT_KEY] = rec["title"]
        s[WORKSPACE_GENRE_FILTERS_KEY] = [GENRE]
        s[SONG_PICKER_FAVORITES_ONLY_KEY] = True
        self.assertEqual(_keys(s).count(fav_jazz), 1)

    def test_reruns_are_stable(self):
        s = dict(self.state)
        s[SONG_SEARCH_TEXT_KEY] = QUERY
        s[WORKSPACE_GENRE_FILTERS_KEY] = [GENRE]
        first = _keys(s)
        for _ in range(3):
            self.assertEqual(_keys(s), first)


class TestClearFiltersFromAnyCombination(unittest.TestCase):
    def _combos(self):
        favs = [_pk(RECORDS[3])]
        out = []
        for extra in (
            {SONG_SEARCH_TEXT_KEY: QUERY},
            {WORKSPACE_GENRE_FILTERS_KEY: [GENRE]},
            {SONG_PICKER_FAVORITES_ONLY_KEY: True},
            {SONG_SEARCH_TEXT_KEY: QUERY, WORKSPACE_GENRE_FILTERS_KEY: [GENRE]},
            {SONG_SEARCH_TEXT_KEY: QUERY, WORKSPACE_GENRE_FILTERS_KEY: [GENRE],
             SONG_PICKER_FAVORITES_ONLY_KEY: True},
        ):
            state = {CATALOG_FAVORITES_KEY: list(favs)}
            state.update(extra)
            out.append(state)
        return out

    def test_clear_empties_browse_and_keeps_favorites_and_active_song(self):
        for i, state in enumerate(self._combos()):
            with self.subTest(combo=i):
                state["selected_song"] = {"pick_key": "keep-me"}
                favs_before = list(state[CATALOG_FAVORITES_KEY])
                showing = _keys(state)
                self.assertTrue(showing)                                          # something was showing
                exclude_browse_pick_key(state, showing[0])                        # and an X exclusion exists
                request_clear_browse_filters(state)
                self.assertTrue(state.get(SONG_SEARCH_RESET_REQUESTED_KEY))
                apply_picker_session_resets(state)
                self.assertEqual(state[SONG_SEARCH_TEXT_KEY], "")
                self.assertEqual(state[WORKSPACE_GENRE_FILTERS_KEY], [])
                self.assertFalse(state[SONG_PICKER_FAVORITES_ONLY_KEY])
                self.assertEqual(browse_excluded_pick_keys(state), [])
                self.assertEqual(_keys(state), [])                                # zero songs shown
                self.assertEqual(state[CATALOG_FAVORITES_KEY], favs_before)       # Favorites untouched
                self.assertEqual(state["selected_song"], {"pick_key": "keep-me"})


class TestExclusionsStillWork(unittest.TestCase):
    def test_x_hides_one_row_without_touching_catalog_or_favorites(self):
        favs = [_pk(RECORDS[3])]
        state = {CATALOG_FAVORITES_KEY: favs, SONG_SEARCH_TEXT_KEY: QUERY,
                 WORKSPACE_GENRE_FILTERS_KEY: [GENRE]}
        before = _keys(state)
        records_before = [dict(r) for r in RECORDS]
        exclude_browse_pick_key(state, before[0])
        self.assertEqual(_keys(state), before[1:])
        self.assertEqual(state[CATALOG_FAVORITES_KEY], favs)
        self.assertEqual(RECORDS, records_before)

    def test_exclusions_alone_never_resurrect_the_catalog(self):
        state = {SONG_SEARCH_TEXT_KEY: QUERY}
        for key in list(_keys(state)):
            exclude_browse_pick_key(state, key)
        self.assertEqual(_keys(state), [])                                        # all matches hidden -> empty


if __name__ == "__main__":
    unittest.main()

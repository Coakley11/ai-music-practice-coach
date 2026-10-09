"""Browse Library catalog search: the backend search/filter behavior behind
the Songs-page clickable results list (streamlit_music_practice_app.py's
_render_browse_search_results). Exercised against the real catalog -- not
invented data -- using the exact search terms from the feature request.
"""

from __future__ import annotations

import unittest

from song_catalog.catalog import (
    format_pick_key,
    load_song_catalog,
    search_records,
)

_LIBRARY, _PICKER, _GENRES, _RECORDS = load_song_catalog()


def _titles(rows: list[dict]) -> set[str]:
    return {r["title"] for r in rows}


class TestPartialAndExactTitleSearch(unittest.TestCase):
    def test_partial_title_shallow(self) -> None:
        rows = search_records(_RECORDS, "Shallow")
        self.assertIn("Shallow", _titles(rows))

    def test_partial_title_shape_finds_shape_of_you(self) -> None:
        rows = search_records(_RECORDS, "Shape")
        self.assertIn("Shape of You", _titles(rows))

    def test_exact_title_match_ranks_first(self) -> None:
        rows = search_records(_RECORDS, "Shape of You")
        self.assertTrue(rows)
        self.assertEqual(rows[0]["title"], "Shape of You")


class TestArtistSearch(unittest.TestCase):
    def test_search_by_artist_name(self) -> None:
        # Pick a real artist from the catalog rather than hardcoding one.
        artist = next(r["artist"] for r in _RECORDS if r.get("artist"))
        rows = search_records(_RECORDS, artist)
        self.assertTrue(rows)
        self.assertTrue(any(r.get("artist") == artist for r in rows))


class TestGenreSearch(unittest.TestCase):
    def test_search_jazz(self) -> None:
        rows = search_records(_RECORDS, "Jazz")
        self.assertTrue(rows)
        self.assertTrue(all("jazz" in (r.get("genre") or "").lower()
                             or "jazz" in " ".join(str(v) for v in r.values()).lower()
                             for r in rows[:5]))
        self.assertIn("Jazz", {r.get("genre") for r in rows})

    def test_search_rock(self) -> None:
        rows = search_records(_RECORDS, "Rock")
        self.assertTrue(rows)
        self.assertIn("Rock", {r.get("genre") for r in rows})


class TestDifficultyLevelSearch(unittest.TestCase):
    def test_search_beginner_returns_beginner_charts(self) -> None:
        rows = search_records(_RECORDS, "Beginner")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn("Beginner", (r.get("chart_versions") or {}).keys())


class TestMultipleMatchesAndNoMatches(unittest.TestCase):
    def test_common_query_returns_multiple_songs(self) -> None:
        rows = search_records(_RECORDS, "a")  # broad single-letter query
        self.assertGreater(len(rows), 1)

    def test_no_match_returns_empty_not_error(self) -> None:
        rows = search_records(_RECORDS, "zzzzznonexistentsongtitle123")
        self.assertEqual(rows, [])


class TestGenreFilterIntegration(unittest.TestCase):
    def test_search_combined_with_genre_filter_is_AND(self) -> None:
        """A search term plus a genre filter must narrow, not widen, results --
        the same ``filtered`` list both the dropdown and the new results list
        read from ``_apply_picker_catalog_filters``."""
        unfiltered = search_records(_RECORDS, "a")
        pop_only = search_records(_RECORDS, "a", genres=["Pop"])
        self.assertLessEqual(len(pop_only), len(unfiltered))
        self.assertTrue(all(r.get("genre") == "Pop" for r in pop_only))

    def test_genre_filter_alone_no_search_text(self) -> None:
        rows = search_records(_RECORDS, "", genres=["Jazz"])
        self.assertTrue(rows)
        self.assertTrue(all(r.get("genre") == "Jazz" for r in rows))


class TestCustomCompositionIsolation(unittest.TestCase):
    """Requirement: search applies only to the Song Catalog."""

    def test_catalog_records_never_carry_custom_or_composition_prefix(self) -> None:
        for r in search_records(_RECORDS, "a")[:50]:
            pk = format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
            self.assertFalse(pk.startswith("custom::"))
            self.assertFalse(pk.startswith("composition::"))

    def test_catalog_record_pool_has_no_custom_or_composition_entries(self) -> None:
        for r in _RECORDS:
            self.assertNotEqual(r.get("genre"), "Custom")
            self.assertNotEqual(r.get("genre"), "Composition")


class TestPickKeyRoundTrip(unittest.TestCase):
    """Each search result's pick key must resolve back to the same canonical
    catalog row used by activate_catalog_song_for_backing -- the same
    function the Active Song dropdown's on_change already calls."""

    def test_every_shape_result_pick_key_resolves_to_itself(self) -> None:
        from song_catalog.catalog import record_for_pick_key

        rows = search_records(_RECORDS, "Shape")
        for r in rows:
            pk = format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
            resolved = record_for_pick_key(_RECORDS, pk)
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved["title"], r["title"])
            self.assertEqual(resolved["artist"], r["artist"])


if __name__ == "__main__":
    unittest.main()

"""Tests for custom song cloud library + startup restore skip guard."""

from __future__ import annotations

import unittest


class TestMusicShouldSkipMasterSongInit(unittest.TestCase):
    def test_skips_when_custom_progression_active(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss = {"active_music_source": "custom_progression"}
        self.assertTrue(music_should_skip_master_song_init(ss))

    def test_skips_when_saved_custom_library_present(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss = {"cpl_saved_progressions": {"Trial Song": {"id": "abc", "name": "Trial Song"}}}
        self.assertTrue(music_should_skip_master_song_init(ss))

    def test_skips_when_non_practice_studio_page_in_workspace(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        ss = {"music_workspace_state": {"studio_page": "analysis"}}
        self.assertTrue(music_should_skip_master_song_init(ss))

    def test_does_not_skip_cold_start(self) -> None:
        from music_persistent_state import music_should_skip_master_song_init

        self.assertFalse(music_should_skip_master_song_init({}))


class TestCustomSongLibrary(unittest.TestCase):
    def test_merge_cloud_rows_into_local_store(self) -> None:
        from custom_song_library import _merge_progression_store

        local = {"Old": {"id": "1", "name": "Old", "updated_at": 1.0}}
        cloud_rows = [
            {
                "title": "Trial Song",
                "payload": {
                    "progression": {
                        "id": "2",
                        "name": "Trial Song",
                        "updated_at": 99.0,
                        "original_key_center": "D",
                    }
                },
            }
        ]
        merged = _merge_progression_store(local, cloud_rows)
        self.assertIn("Trial Song", merged)
        self.assertEqual(merged["Trial Song"]["original_key_center"], "D")
        self.assertIn("Old", merged)


class TestPopCatalogExtensions(unittest.TestCase):
    def test_new_songs_present(self) -> None:
        from song_catalog.pop_extensions_2026 import pop_extension_chart_overrides

        keys = set(pop_extension_chart_overrides())
        self.assertIn(("Marry You", "Bruno Mars"), keys)
        self.assertIn(("Man in the Mirror", "Michael Jackson"), keys)
        self.assertIn(("You Belong With Me", "Taylor Swift"), keys)
        self.assertEqual(pop_extension_chart_overrides()[("Heal The World", "Michael Jackson")]["key"], "A")

    def test_curated_records_include_marry_you(self) -> None:
        from song_catalog.curated_songs import curated_song_records

        titles = {(r["title"], r["artist"]) for r in curated_song_records()}
        self.assertIn(("Marry You", "Bruno Mars"), titles)


class TestGenreFilterWidgetKey(unittest.TestCase):
    def test_sanitizes_special_chars(self) -> None:
        from songs.picker_session import genre_filter_widget_key

        self.assertEqual(genre_filter_widget_key("Pop/Rock"), "Pop_Rock")


if __name__ == "__main__":
    unittest.main()

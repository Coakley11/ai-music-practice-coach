"""Import smoke for Songs Music Source Composition option helpers."""

from __future__ import annotations

import unittest


class TestSongPickerCompositionImports(unittest.TestCase):
    def test_music_source_exports_composition_option_label(self) -> None:
        from songs.music_source import (
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SONG_PICKER_SOURCE_COMPOSITION,
            music_picker_shows_composition_hub,
            music_picker_shows_custom_hub,
            on_song_picker_source_change,
            reconcile_music_picker_source_widget,
            song_picker_composition_option_label,
            sync_song_picker_source_widget,
        )

        label = song_picker_composition_option_label()
        self.assertIn("Composition", label)
        self.assertTrue(callable(on_song_picker_source_change))
        self.assertTrue(callable(reconcile_music_picker_source_widget))
        self.assertTrue(callable(sync_song_picker_source_widget))
        self.assertTrue(callable(music_picker_shows_composition_hub))
        self.assertTrue(callable(music_picker_shows_custom_hub))
        self.assertTrue(SONG_PICKER_SOURCE_CATALOG)
        self.assertTrue(SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(SONG_PICKER_SOURCE_COMPOSITION, "Composition")

    def test_package_reexport(self) -> None:
        from songs import song_picker_composition_option_label

        self.assertIn("Composition", song_picker_composition_option_label())

    def test_composition_bridge_imports(self) -> None:
        from composition_songs_bridge import (
            SOURCE_COMPOSITION,
            apply_pending_composition_active_song_activation_before_widgets,
            composition_pick_key_for,
            ensure_composition_library_hydrated,
            list_composition_songs_for_picker,
            navigate_new_composition_song,
            queue_composition_active_song_activation,
        )
        from songs.state import activate_active_song_by_pick_key

        self.assertEqual(SOURCE_COMPOSITION, "composition_song")
        self.assertTrue(callable(ensure_composition_library_hydrated))
        self.assertTrue(callable(list_composition_songs_for_picker))
        self.assertTrue(callable(navigate_new_composition_song))
        self.assertTrue(callable(queue_composition_active_song_activation))
        self.assertTrue(callable(apply_pending_composition_active_song_activation_before_widgets))
        self.assertTrue(callable(composition_pick_key_for))
        self.assertTrue(callable(activate_active_song_by_pick_key))


if __name__ == "__main__":
    unittest.main()

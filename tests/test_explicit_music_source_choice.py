"""Regression: explicit Songs source stamp outranks stale pick / same-rerun reclaim."""

from __future__ import annotations

import unittest

from music_source_ownership import intended_practice_owner
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
    EXPLICIT_MUSIC_SOURCE_SEQ_KEY,
    SONG_PICKER_ACTIVE_SOURCE_KEY,
    SONG_PICKER_SOURCE_CUSTOM,
    SOURCE_CATALOG,
    SOURCE_COMPOSITION,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    commit_explicit_music_source_choice,
    composition_song_is_active,
    custom_progression_is_active,
    hydrate_explicit_music_source_from_active,
    reconcile_music_picker_source_widget,
    song_picker_composition_option_label,
    source_ownership_snapshot,
)


class ExplicitMusicSourceChoiceTests(unittest.TestCase):
    def test_commit_bumps_seq_and_clears_composition_oneshots(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            "_force_composition_backing_open": True,
            "_composition_hub_promote_token": "composition::x",
            "composition_hub_backing": True,
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_SEQ_KEY], 1)
        self.assertNotIn("_force_composition_backing_open", ss)
        self.assertNotIn("composition_hub_backing", ss)
        self.assertFalse(composition_song_is_active(ss))
        self.assertTrue(custom_progression_is_active(ss))

    def test_stale_composition_pick_cannot_win_after_custom_stamp(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            "active_song_state": {
                "music_source": SOURCE_COMPOSITION,
                "pick_key": "composition::doc1",
            },
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        self.assertFalse(composition_song_is_active(ss))
        self.assertTrue(custom_progression_is_active(ss))
        self.assertEqual(intended_practice_owner(ss), "custom")

    def test_reconcile_does_not_overwrite_custom_radio_with_composition_pick(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "studio_page": "picker",
            "page": "picker",
        }
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        self.assertFalse(composition_song_is_active(ss))

    def test_reconcile_does_not_overwrite_composition_radio_with_custom_pick(self) -> None:
        label = song_picker_composition_option_label()
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::mine",
            SONG_PICKER_ACTIVE_SOURCE_KEY: label,
            "studio_page": "picker",
            "page": "picker",
        }
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_COMPOSITION)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_COMPOSITION)
        self.assertTrue(composition_song_is_active(ss))
        self.assertFalse(custom_progression_is_active(ss))
        self.assertIsNone(intended_practice_owner(ss))

    def test_catalog_stamp_outranks_composition_pick(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
        }
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        self.assertTrue(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertFalse(composition_song_is_active(ss))
        self.assertEqual(intended_practice_owner(ss), "catalog")

    def test_hydrate_explicit_from_active_after_refresh(self) -> None:
        ss = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM, "active_catalog_pick_key": "custom::mine"}
        hydrate_explicit_music_source_from_active(ss)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        # Second hydrate must not clobber a newer Composition stamp.
        commit_explicit_music_source_choice(ss, SOURCE_COMPOSITION, clear_composition_oneshots=False)
        hydrate_explicit_music_source_from_active(ss)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_COMPOSITION)

    def test_snapshot_includes_required_ownership_fields(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::mine",
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        snap = source_ownership_snapshot(ss)
        for key in (
            "radio",
            "explicit",
            "explicit_seq",
            "active_music_source",
            "pick",
            "force_composition_backing",
            "composition_active",
            "custom_active",
        ):
            self.assertIn(key, snap)
        self.assertEqual(snap["explicit"], SOURCE_CUSTOM)
        self.assertTrue(snap["custom_active"])
        self.assertFalse(snap["composition_active"])


    def test_live_composition_radio_outranks_stale_custom_explicit(self) -> None:
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::mine",
            SONG_PICKER_ACTIVE_SOURCE_KEY: song_picker_composition_option_label(),
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            EXPLICIT_MUSIC_SOURCE_SEQ_KEY: 3,
        }
        # Radio is Composition — ownership readers must not stay on Custom.
        self.assertTrue(composition_song_is_active(ss))
        self.assertFalse(custom_progression_is_active(ss))
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_COMPOSITION)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_COMPOSITION)
        self.assertIsNone(intended_practice_owner(ss))



    def test_clear_flags_preserves_in_flight_hub_click(self) -> None:
        from songs.music_source import clear_composition_one_shot_nav_flags

        ss = {
            "_composition_hub_backing_clicked": True,
            "_force_composition_backing_open": True,
            "composition_hub_backing": True,
        }
        clear_composition_one_shot_nav_flags(ss)
        self.assertTrue(ss.get("_composition_hub_backing_clicked"))
        self.assertTrue(ss.get("_force_composition_backing_open"))
        self.assertTrue(ss.get("composition_hub_backing"))

    def test_catalog_commit_clears_leftover_hub_click_force(self) -> None:
        """Catalog radio leave pops hub-click first, then commit clears leftovers."""
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            "_composition_hub_backing_clicked": True,
            "_force_composition_backing_open": True,
            "composition_hub_backing": True,
        }
        # Radio on_change pops the in-flight guard before commit.
        ss.pop("_composition_hub_backing_clicked", None)
        ss.pop("_force_composition_backing_open", None)
        commit_explicit_music_source_choice(ss, SOURCE_CATALOG)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)
        self.assertTrue(ss.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertNotIn("_composition_hub_backing_clicked", ss)
        self.assertNotIn("_force_composition_backing_open", ss)
        self.assertNotIn("composition_hub_backing", ss)
        self.assertFalse(composition_song_is_active(ss))

    def test_commit_custom_preserves_in_flight_composition_hub_click(self) -> None:
        """Mid-run Custom reconcile must not drop Composition hub Backing on_click."""
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            "_composition_hub_backing_clicked": True,
            "_force_composition_backing_open": True,
            "_composition_hub_backing_pending": True,
            "composition_hub_backing": True,
        }
        commit_explicit_music_source_choice(ss, SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertTrue(ss.get("_composition_hub_backing_clicked"))
        self.assertTrue(ss.get("_force_composition_backing_open"))
        self.assertTrue(ss.get("_composition_hub_backing_pending"))
        self.assertTrue(ss.get("composition_hub_backing"))

    def test_pending_alone_blocks_clear_composition_oneshots(self) -> None:
        from songs.music_source import clear_composition_one_shot_nav_flags

        ss = {
            "_composition_hub_backing_pending": True,
            "_force_composition_backing_open": True,
        }
        clear_composition_one_shot_nav_flags(ss)
        self.assertTrue(ss.get("_composition_hub_backing_pending"))
        self.assertTrue(ss.get("_force_composition_backing_open"))


if __name__ == "__main__":
    unittest.main()

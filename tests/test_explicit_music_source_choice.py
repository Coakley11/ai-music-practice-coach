"""Regression: explicit Songs source stamp outranks stale pick / same-rerun reclaim."""

from __future__ import annotations

import unittest
from unittest import mock

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

    def test_reconcile_snaps_custom_radio_to_composition_active_without_explicit(self) -> None:
        """Without an explicit stamp, hydrate from ACTIVE — do not promote live radio."""
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "studio_page": "picker",
            "page": "picker",
        }
        reconcile_music_picker_source_widget(ss)
        # No explicit → sync aligns radio to ACTIVE Composition; does not invent Custom.
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_COMPOSITION)
        self.assertNotEqual(ss.get(EXPLICIT_MUSIC_SOURCE_CHOICE_KEY), SOURCE_CUSTOM)
        self.assertEqual(
            ss[SONG_PICKER_ACTIVE_SOURCE_KEY], song_picker_composition_option_label()
        )

    def test_reconcile_snaps_composition_radio_to_custom_explicit(self) -> None:
        """Leftover Composition radio must not steal a committed Custom leave."""
        label = song_picker_composition_option_label()
        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::mine",
            SONG_PICKER_ACTIVE_SOURCE_KEY: label,
            "studio_page": "picker",
            "page": "picker",
        }
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        self.assertFalse(composition_song_is_active(ss))

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
        # Remount leftover Composition radio must not steal committed Custom.
        # Real Composition clicks commit via on_change before reconcile.
        self.assertFalse(composition_song_is_active(ss))
        self.assertTrue(custom_progression_is_active(ss))
        changed = reconcile_music_picker_source_widget(ss)
        self.assertTrue(changed)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(intended_practice_owner(ss), "custom")



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

    def test_sync_skips_snap_when_mounted_radio_differs_from_last(self) -> None:
        """prepare commits before sync; sync alone may snap if prepare did not run."""
        from songs.music_source import (
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY,
            SONGS_SOURCE_RADIO_MOUNTED_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            prepare_song_picker_source_radio,
        )

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            SONGS_SOURCE_RADIO_MOUNTED_KEY: True,
            "active_catalog_pick_key": "custom::mine",
            "studio_page": "picker",
        }
        reran = {"n": 0}

        class _St:
            session_state = ss

            def rerun(self) -> None:
                reran["n"] += 1

        with mock.patch(
            "songs.music_source.switch_to_catalog_from_custom",
            return_value=None,
        ):
            prepare_song_picker_source_radio(
                _St(),
                song_picker_catalog={},
                song_library={},
                invalidate_backing=lambda: None,
            )
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)
        self.assertGreaterEqual(reran["n"], 1)

    def test_upload_remount_snaps_stale_catalog_when_not_mounted(self) -> None:
        """Custom→Upload→Songs: off-Songs snap keeps radio aligned; prepare no-ops."""
        from songs.music_source import (
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            prepare_song_picker_source_radio,
            reconcile_picker_music_source,
        )

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY: SONG_PICKER_SOURCE_CUSTOM,
            "studio_page": "upload",
            "page": "upload",
            "active_catalog_pick_key": "custom::mine",
        }

        class _St:
            session_state = ss

            def rerun(self) -> None:
                raise AssertionError("aligned remount must not commit via on_change rerun")

        # Off Songs aligns dormant radio + last to explicit Custom.
        reconcile_picker_music_source(ss)
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(ss[LAST_SONG_PICKER_SOURCE_CHOICE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        ss["studio_page"] = "picker"
        ss["page"] = "picker"
        # Aligned return: live already matches explicit — prepare must not steal.
        prepare_song_picker_source_radio(
            _St(),
            song_picker_catalog={},
            song_library={},
            invalidate_backing=lambda: None,
        )
        self.assertEqual(ss[SONG_PICKER_ACTIVE_SOURCE_KEY], SONG_PICKER_SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)

        # Leftover Catalog after off-Songs snap is treated as a Songs click
        # (prepare cannot distinguish remount reset from a real click). Off-Songs
        # alignment is the guard against Upload→Songs steal.
        ss[SONG_PICKER_ACTIVE_SOURCE_KEY] = SONG_PICKER_SOURCE_CATALOG
        with mock.patch(
            "songs.music_source.switch_to_catalog_from_custom",
            return_value=None,
        ):
            class _St2:
                session_state = ss

                def rerun(self) -> None:
                    pass

            prepare_song_picker_source_radio(
                _St2(),
                song_picker_catalog={},
                song_library={},
                invalidate_backing=lambda: None,
            )
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)

    def test_set_custom_source_does_not_clobber_composition_explicit(self) -> None:
        from songs.music_source import set_custom_source

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_COMPOSITION,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_COMPOSITION,
            "active_catalog_pick_key": "composition::doc1",
        }
        set_custom_source(ss)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_COMPOSITION)

    def test_set_custom_source_soft_aligns_catalog_stamp(self) -> None:
        from songs.music_source import set_custom_source

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
        }
        set_custom_source(ss)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CUSTOM)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CUSTOM)
        self.assertNotIn(USER_CATALOG_SOURCE_CHOICE_KEY, ss)

    def test_commit_pending_when_last_already_matches_live_catalog(self) -> None:
        """on_change may set last=Catalog before explicit commits — still commit."""
        from songs.music_source import (
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY,
            SONGS_SOURCE_RADIO_MOUNTED_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            commit_pending_song_picker_radio_click,
        )

        ss = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CUSTOM,
            SONG_PICKER_ACTIVE_SOURCE_KEY: SONG_PICKER_SOURCE_CATALOG,
            # Poisoned last: matches live Catalog while explicit still Custom.
            LAST_SONG_PICKER_SOURCE_CHOICE_KEY: SONG_PICKER_SOURCE_CATALOG,
            SONGS_SOURCE_RADIO_MOUNTED_KEY: True,
            "active_catalog_pick_key": "custom::mine",
            "studio_page": "picker",
        }
        reran = {"n": 0}

        class _St:
            session_state = ss

            def rerun(self) -> None:
                reran["n"] += 1

        with mock.patch(
            "songs.music_source.switch_to_catalog_from_custom",
            return_value=None,
        ):
            ok = commit_pending_song_picker_radio_click(
                _St(),
                song_picker_catalog={},
                song_library={},
                invalidate_backing=lambda: None,
            )
        self.assertTrue(ok)
        self.assertEqual(ss[EXPLICIT_MUSIC_SOURCE_CHOICE_KEY], SOURCE_CATALOG)
        self.assertGreaterEqual(reran["n"], 1)


if __name__ == "__main__":
    unittest.main()

"""H5/H9 ownership: SBI Custom must not steal Global; Custom Active outranks Mission seal."""

from __future__ import annotations

import unittest
from types import SimpleNamespace


class TestH5H9OwnershipTransitions(unittest.TestCase):
    def test_restore_song_improv_custom_does_not_set_custom_source(self) -> None:
        from backing_context import BackingContext
        from backing_source_navigation import restore_session_widgets_from_backing_context
        from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG, SOURCE_CUSTOM

        session = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            "active_catalog_pick_key": "Pop\x1fShape of You — Ed Sheeran",
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "display_key": "C#m",
        }
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id="custom::trial-1",
            song_title="Trial Song",
            key="D",
            display_key="D",
            concert_key="D",
            chart_display_key="D",
            bpm=100,
            style="",
            groove="",
            section="",
            sections=[],
            scope="Full song",
            loops=2,
            progression=["D", "G", "A"],
            progression_label="Trial Song",
            section_labels=["A"],
            loop=True,
            entry_mode="Song-Based Improvisation",
            mode_label="Song-Based Improvisation",
            bound_pick_key="custom::trial-1",
            custom_revision_id="trial-1",
        )
        restore_session_widgets_from_backing_context(session, ctx, widget_safe=False)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertNotEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get("improv_song_source"), "Custom progression")
        self.assertEqual(session.get("song"), "Shape of You")

    def test_custom_practice_makes_mission_ctx_stale(self) -> None:
        from backing_context import BackingContext, ctx_is_stale_creative_for_practice
        from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CUSTOM

        session = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::trial-1",
            "song": "Trial Song",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="Pop\x1fShape of You — Ed Sheeran",
            song_title="Shape of You",
            key="Bm",
            display_key="C#m",
            concert_key="C#m",
            chart_display_key="C#m",
            bpm=96,
            style="",
            groove="",
            section="",
            sections=[],
            scope="Full song",
            loops=2,
            progression=["C#m"],
            progression_label="Mission",
            section_labels=[],
            loop=True,
            entry_mode="Song-Based Improvisation",
            mode_label="Mission",
            bound_pick_key="Pop\x1fShape of You — Ed Sheeran",
            mission_id="chord-tones",
        )
        self.assertTrue(ctx_is_stale_creative_for_practice(session, ctx))

    def test_shape_original_key_ignores_polluted_selected_c(self) -> None:
        from songs.music_source import _catalog_original_key_for_session

        pick = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {
                "pick_key": pick,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "C",  # Custom contamination
            },
            "_reconcile_song_picker_catalog": {
                "Pop": {
                    "Shape of You — Ed Sheeran": {"key": "Bm", "title": "Shape of You", "artist": "Ed Sheeran"},
                }
            },
        }
        self.assertEqual(_catalog_original_key_for_session(session), "Bm")
        self.assertEqual(session["selected_song"]["key"], "C")  # heal happens via resolve path
        # With catalog row present, polluted selected.key / rec must not win:
        self.assertEqual(_catalog_original_key_for_session(session, rec={"key": "Bm"}), "Bm")
        self.assertEqual(_catalog_original_key_for_session(session, rec={"key": "C"}), "Bm")

    def test_songs_use_custom_overrides_post_h9_catalog_latches(self) -> None:
        """H1/H8: explicit Songs Custom must retire Use-catalog force/block/USER_CATALOG."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
            LAST_CUSTOM_STATE_KEY,
            PENDING_CUSTOM_ACTIVE_SONG_KEY,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
        )

        trial = {
            "name": "Trial Song",
            "original_key": "D",
            "written_key": "D",
            "original_sections": {"A": ["D", "A", "Bm", "G"]},
        }
        session = {
            "studio_page": "picker",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY: 999.0,
            "_block_stale_custom_radio_reclaim": 4,
            "_force_catalog_backing_after_use_catalog": 4,
            "active_catalog_pick_key": "Pop\x1fShape of You — Ed Sheeran",
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            LAST_CUSTOM_STATE_KEY: {"active": trial},
            "cpl_active_progression": trial,
            "_script_run_seq": 10,
        }
        # Songs Use Custom after Catalog must clear the multi-run Catalog guard.
        session.pop("_catalog_owns_until_custom_click", None)
        self.assertTrue(reconcile_picker_music_source(session))
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertFalse(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))
        self.assertIsNone(session.get(EXPLICIT_CATALOG_SELECTION_EPOCH_KEY))
        self.assertIsNone(session.get("_block_stale_custom_radio_reclaim"))
        self.assertIsNone(session.get("_force_catalog_backing_after_use_catalog"))
        self.assertIsInstance(session.get(PENDING_CUSTOM_ACTIVE_SONG_KEY), dict)
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CUSTOM)

    def test_catalog_guard_blocks_custom_radio_reclaim(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            reconcile_picker_music_source,
        )

        session = {
            "studio_page": "picker",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "custom::My Progression",
            "_script_run_seq": 3,
            "_catalog_owns_until_custom_click": True,
        }
        self.assertTrue(reconcile_picker_music_source(session))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)

    def test_same_run_catalog_switch_blocks_lagging_custom_radio(self) -> None:
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            CATALOG_SWITCH_APPLIED_THIS_RUN_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            reconcile_picker_music_source,
        )

        session = {
            "studio_page": "picker",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "active_catalog_pick_key": "Pop\x1fShape of You — Ed Sheeran",
            "_script_run_seq": 7,
            # Stamp without forcing the widget yet — mimics lag after Catalog switch.
            CATALOG_SWITCH_APPLIED_THIS_RUN_KEY: 7,
        }
        self.assertTrue(reconcile_picker_music_source(session))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)

    def test_set_custom_source_stamps_before_custom_from_live_shape(self) -> None:
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_RECENT_PICK_KEYS,
            LAST_CATALOG_STATE_KEY,
            SOURCE_CATALOG,
            set_custom_source,
        )

        pick = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": pick,
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "display_key": "C#m",
            "selected_song": {
                "pick_key": pick,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            # Stale Say residue that must not win when live identity is Shape.
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": "Pop\x1fSay — John Mayer",
                "original_key": "G",
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": "Pop\x1fSay — John Mayer",
                "original_key": "G",
            },
            CATALOG_RECENT_PICK_KEYS: [pick, "Pop\x1fSay — John Mayer"],
            "_reconcile_song_picker_catalog": {
                "Pop": {
                    "Shape of You — Ed Sheeran": {
                        "key": "Bm",
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                    }
                }
            },
        }
        set_custom_source(session)
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), pick)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")

    def test_capture_before_custom_prefers_live_title_over_stale_say_pick(self) -> None:
        """Live Global Active Shape + stale Say pick/LAST/BEFORE → stamp Shape Bm."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_RECENT_PICK_KEYS,
            LAST_CATALOG_STATE_KEY,
            capture_catalog_before_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        session = {
            "active_catalog_pick_key": say,
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "display_key": "C#m",
            "selected_song": {
                "pick_key": say,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"title": "Say", "pick_key": say, "key": "G"},
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"title": "Say", "pick_key": say, "key": "G"},
            },
            # Say listed first — must not win over title-matched Shape.
            CATALOG_RECENT_PICK_KEYS: [say, shape],
            "_reconcile_song_picker_catalog": {
                "Pop": {
                    "Shape of You — Ed Sheeran": {
                        "key": "Bm",
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                    },
                    "Say — John Mayer": {
                        "key": "G",
                        "title": "Say",
                        "artist": "John Mayer",
                    },
                }
            },
        }
        self.assertTrue(capture_catalog_before_custom(session))
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")
        self.assertNotIn("Say", str(before.get("pick_key") or ""))

    def test_capture_before_custom_uses_catalog_session_after_custom_title_flip(self) -> None:
        """When BEFORE is missing under Custom, catalog_session Shape beats LAST Say."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            capture_catalog_before_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        session = {
            "active_catalog_pick_key": "custom::abc",
            "song": "My Progression",
            "active_song_title": "My Progression",
            "catalog_session": {
                "pick_key": shape,
                "original_key": "Bm",
                "display_key": "C#m",
                "selected_song": {
                    "pick_key": shape,
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                },
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"title": "Say", "pick_key": say, "key": "G"},
            },
        }
        self.assertTrue(capture_catalog_before_custom(session))
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")

    def test_set_custom_source_heals_stale_say_pick_when_title_is_shape(self) -> None:
        """Stale Say pick must not wipe Shape catalog_session before BEFORE stamp."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            set_custom_source,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        shape_snap = {
            "pick_key": shape,
            "original_key": "Bm",
            "display_key": "C#m",
            "selected_song": {
                "pick_key": shape,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        }
        say_snap = {
            "pick_key": say,
            "original_key": "G",
            "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
        }
        session = {
            # UI/Global title is Shape, but pick alias still Say (hydration skew).
            "active_catalog_pick_key": say,
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "display_key": "C#m",
            "selected_song": say_snap["selected_song"],
            "catalog_session": shape_snap,
            CATALOG_BEFORE_CUSTOM_KEY: say_snap,
            LAST_CATALOG_STATE_KEY: say_snap,
            "active_music_source": "catalog_song",
            "_reconcile_song_picker_catalog": {
                "Pop": {
                    "Shape of You — Ed Sheeran": {
                        "key": "Bm",
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                    }
                }
            },
        }
        set_custom_source(session)
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")
        self.assertEqual(session.get("active_catalog_pick_key"), shape)

    def test_capture_does_not_overwrite_shape_before_after_custom_owns_global(self) -> None:
        """Reload/reconcile must not replace Shape BEFORE with Say catalog_session."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY,
            CATALOG_RECENT_PICK_KEYS,
            LAST_CATALOG_STATE_KEY,
            capture_catalog_before_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        session = {
            "active_catalog_pick_key": "custom::My Progression",
            "song": "My Progression",
            "active_song_title": "My Progression",
            "active_music_source": "custom_progression",
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape,
                "original_key": "Bm",
                "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
            },
            CATALOG_BEFORE_CUSTOM_LOCK_KEY: shape,
            "catalog_session": {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
            CATALOG_RECENT_PICK_KEYS: [shape, say],
        }
        self.assertFalse(capture_catalog_before_custom(session))
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")
        self.assertEqual(session.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY), shape)

    def test_capture_lock_survives_empty_title_reload_hydrate(self) -> None:
        """Mid-hydrate (empty titles) + Say catalog_session must not wipe Shape lock."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY,
            LAST_CATALOG_STATE_KEY,
            capture_catalog_before_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        session = {
            "active_music_source": "custom_progression",
            # Titles not restored yet (reload hydrate race).
            "song": "",
            "active_song_title": "",
            "active_catalog_pick_key": say,
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape,
                "original_key": "Bm",
                "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
            },
            CATALOG_BEFORE_CUSTOM_LOCK_KEY: shape,
            "catalog_session": {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
            LAST_CATALOG_STATE_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
        }
        self.assertFalse(capture_catalog_before_custom(session))
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(session.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY), shape)
        self.assertNotIn("Say", str(before.get("pick_key") or ""))

    def test_capture_heals_say_before_back_to_shape_lock(self) -> None:
        """If BEFORE was already restamped Say, lock must heal it back to Shape."""
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY,
            capture_catalog_before_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        shape_snap = {
            "pick_key": shape,
            "original_key": "Bm",
            "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
        }
        session = {
            "active_music_source": "custom_progression",
            "song": "My Progression",
            "active_song_title": "My Progression",
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
            CATALOG_BEFORE_CUSTOM_LOCK_KEY: shape,
            # No Shape catalog_session — heal must rebuild from lock pick.
            "catalog_session": {
                "pick_key": say,
                "original_key": "G",
                "selected_song": {"pick_key": say, "title": "Say", "key": "G"},
            },
            "_last_catalog_song_state": shape_snap,
        }
        self.assertFalse(capture_catalog_before_custom(session))
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(str(before.get("original_key") or ""), "Bm")

    def test_apply_pick_key_blocked_while_custom_owns_global(self) -> None:
        """Reload/widget must not apply Say (and restamp BEFORE) while Custom owns."""
        from types import SimpleNamespace

        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY,
        )
        from songs.state import apply_pick_key

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                },
                "Say — John Mayer": {
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                },
            }
        }
        session = {
            "active_music_source": "custom_progression",
            "song": "My Progression",
            "active_song_title": "My Progression",
            "active_catalog_pick_key": "custom::My Progression",
            "_last_pick_key": "custom::My Progression",
            "selected_song": {
                "pick_key": "custom::My Progression",
                "title": "My Progression",
                "key": "C",
            },
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": shape,
                "original_key": "Bm",
                "selected_song": {"pick_key": shape, "title": "Shape of You", "key": "Bm"},
            },
            CATALOG_BEFORE_CUSTOM_LOCK_KEY: shape,
        }
        st = SimpleNamespace(session_state=session)
        result = apply_pick_key(st, say, catalog, persist=False, origin="user")
        self.assertEqual(result.get("title"), "My Progression")
        self.assertEqual(session.get("active_music_source"), "custom_progression")
        self.assertEqual(session.get("song"), "My Progression")
        before = session.get(CATALOG_BEFORE_CUSTOM_KEY) or {}
        self.assertEqual(before.get("pick_key"), shape)
        self.assertEqual(session.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY), shape)

    def test_display_key_context_shape_not_custom_c_when_radio_lags(self) -> None:
        """After Use Catalog, lagging Custom radio must not show Shape Original Key C."""
        from songs.music_source import display_key_context

        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            "active_music_source": "catalog_song",
            "song": "Shape of You",
            "active_song_title": "Shape of You",
            "active_catalog_pick_key": shape,
            "song_picker_active_source": "Use Custom Progression / Create Your Own Song",
            "selected_song": {
                "pick_key": shape,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "cpl_active_progression": {
                "name": "My Progression",
                "original_key_center": "C",
            },
            "_reconcile_song_picker_catalog": {
                "Pop": {
                    "Shape of You — Ed Sheeran": {
                        "title": "Shape of You",
                        "artist": "Ed Sheeran",
                        "key": "Bm",
                    }
                }
            },
        }
        catalog_data = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
        }
        original, _ident = display_key_context(
            session,
            catalog_song_data=catalog_data,
            cpl_active_key="cpl_active_progression",
        )
        self.assertEqual(original, "Bm")

    def test_switch_prefers_lock_over_say_before_and_loads_empty_catalog(self) -> None:
        """Use Catalog: Shape lock wins over Say BEFORE; empty picker loads from disk."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            CATALOG_BEFORE_CUSTOM_KEY,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY,
            LAST_CATALOG_STATE_KEY,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            switch_to_catalog_from_custom,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        say = "Pop\x1fSay — John Mayer"
        shape_snap = {
            "pick_key": shape,
            "original_key": "Bm",
            "display_key": "Bm",
            "selected_song": {
                "pick_key": shape,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        }
        say_snap = {
            "pick_key": say,
            "original_key": "G",
            "display_key": "G",
            "selected_song": {
                "pick_key": say,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
        }
        session = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM,
            "song": "My Progression",
            "active_song_title": "My Progression",
            "active_catalog_pick_key": "custom::My Progression",
            "selected_song": {"title": "My Progression", "key": "C"},
            CATALOG_BEFORE_CUSTOM_KEY: say_snap,
            LAST_CATALOG_STATE_KEY: say_snap,
            CATALOG_BEFORE_CUSTOM_LOCK_KEY: shape,
            # Intentionally no reconcile/backup — switch must load catalog.
        }
        # Seed lock-matching snap via catalog_session so lock restore has Shape row meta.
        session["catalog_session"] = shape_snap
        st = SimpleNamespace(session_state=session)
        ok = switch_to_catalog_from_custom(
            st,
            song_picker_catalog={},
            invalidate_backing=lambda _st: None,
            force=True,
        )
        self.assertTrue(ok)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(session.get("active_catalog_pick_key"), shape)
        self.assertNotIn("Say", str(session.get("song") or ""))
        self.assertFalse(session.get(CATALOG_BEFORE_CUSTOM_LOCK_KEY))

    def test_backing_block_still_heals_stale_custom_radio(self) -> None:
        """H9: on Backing, block latch still suppresses lagging Custom radio."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
        )

        session = {
            "studio_page": "backing",
            "song_picker_active_source": SONG_PICKER_SOURCE_CUSTOM,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "_block_stale_custom_radio_reclaim": 2,
        }
        self.assertTrue(reconcile_picker_music_source(session))
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertTrue(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))

    def test_apply_saved_custom_pick_blocked_after_use_catalog(self) -> None:
        """Disk custom:: core must not reclaim after Use Catalog restored Shape (H7)."""
        from songs.state import apply_saved_custom_pick_key_context
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY,
            SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY,
        )

        shape = "Pop\x1fShape of You — Ed Sheeran"
        session = {
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            EXPLICIT_CATALOG_SELECTION_EPOCH_KEY: 1.0e9,
            "active_catalog_pick_key": shape,
            "song": "Shape of You",
            "selected_song": {
                "pick_key": shape,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "cpl_active_progression": {
                "id": "x",
                "name": "My Progression",
                "original_key_center": "C",
                "original_sections": {"Verse": [{"chord": "C", "bars": 1}]},
            },
        }
        st = SimpleNamespace(session_state=session)
        ok = apply_saved_custom_pick_key_context(
            st,
            "custom::My Progression",
            {"pick_key": "custom::My Progression"},
            song_picker_catalog={},
        )
        self.assertFalse(ok)
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")

    def test_catalog_owns_guard_survives_catalog_radio_reconcile(self) -> None:
        """After Use Catalog, Catalog radio must not clear the owns-until-Custom guard."""
        from songs.music_source import (
            ACTIVE_MUSIC_SOURCE_KEY,
            SONG_PICKER_SOURCE_CATALOG,
            SONG_PICKER_SOURCE_CUSTOM,
            SOURCE_CATALOG,
            SOURCE_CUSTOM,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            reconcile_picker_music_source,
        )

        session = {
            "studio_page": "picker",
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "_catalog_owns_until_custom_click": True,
            "song": "Shape of You",
            "active_catalog_pick_key": "Pop\x1fShape of You — Ed Sheeran",
        }
        reconcile_picker_music_source(session)
        self.assertTrue(session.get("_catalog_owns_until_custom_click"))
        # Lagging Custom radio while guard is live must heal Catalog, not reclaim.
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CUSTOM
        reconcile_picker_music_source(session)
        self.assertTrue(session.get("_catalog_owns_until_custom_click"))
        self.assertEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CATALOG)
        self.assertNotEqual(session.get(ACTIVE_MUSIC_SOURCE_KEY), SOURCE_CUSTOM)
        self.assertEqual(session.get("song_picker_active_source"), SONG_PICKER_SOURCE_CATALOG)

    def test_release_mission_clears_sealed_mission_ctx(self) -> None:
        from backing_context import BackingContext, get_backing_context, set_backing_context
        from backing_source_navigation import release_mission_creative_page_ownership

        session: dict = {
            "improv_mission_backing_handoff": True,
            "_backing_explicit_handoff_source": "mission",
            "improv_intelligence_tab": "Missions",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            active_song_id="x",
            song_title="Shape of You",
            key="Bm",
            display_key="C#m",
            concert_key="C#m",
            chart_display_key="C#m",
            bpm=96,
            style="",
            groove="",
            section="",
            sections=[],
            scope="Full song",
            loops=2,
            progression=["C#m"],
            progression_label="Mission",
            section_labels=[],
            loop=True,
            entry_mode="Song-Based Improvisation",
            mode_label="Mission",
            bound_pick_key="x",
            mission_id="chord-tones",
        )
        set_backing_context(session, ctx)
        release_mission_creative_page_ownership(session, reason="test", force_entry_jam_tab=True)
        self.assertIsNone(get_backing_context(session))
        self.assertFalse(session.get("improv_mission_backing_handoff"))
        self.assertTrue(session.get("_backing_released_specialized_context"))
        self.assertEqual(session.get("improv_intelligence_tab"), "Entry & Jam")


if __name__ == "__main__":
    unittest.main()

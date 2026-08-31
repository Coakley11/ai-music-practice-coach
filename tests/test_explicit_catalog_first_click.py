"""First-click Songs picker must commit Shape, not leftover Say.

Explicit catalog pick > current owner > pending/pin/master/first_valid.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.music_source import (
    CATALOG_RESTORE_PIN_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    begin_explicit_catalog_selection,
    pin_catalog_restore_identity,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    EXPLICIT_CATALOG_PICK_COMMITTED_KEY,
    PENDING_MATCHING_SONG_DROPDOWN,
    SELECTED_SONG_STATE_KEY,
    _LAST_PICK_KEY,
    apply_explicit_catalog_dropdown_pick,
    apply_pick_key,
    consume_uncommitted_catalog_dropdown,
    reconcile_active_song_identity,
    sync_matching_song_dropdown_before_widget,
)


PK_SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")
PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")

CATALOG = {
    "Pop": {
        "Say — John Mayer": {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "sections": {"Verse": ["G", "D", "Em", "C"]},
        },
        "Perfect — Ed Sheeran": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "sections": {"Verse": ["G", "Em", "C", "D"]},
        },
        "Shape of You — Ed Sheeran": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "sections": {"Verse": ["F#m", "C#m", "Bm", "E"]},
        },
    }
}


def _st(session: dict) -> SimpleNamespace:
    return SimpleNamespace(session_state=session, rerun=lambda: None)


class TestExplicitCatalogFirstClick(unittest.TestCase):
    def test_stale_pending_say_does_not_overwrite_shape_widget(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SHAPE,
            "matching_song_dropdown": PK_SHAPE,
            PENDING_MATCHING_SONG_DROPDOWN: PK_SAY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_SHAPE,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        }
        st = _st(session)
        options = [PK_SAY, PK_PERFECT, PK_SHAPE]
        active = sync_matching_song_dropdown_before_widget(
            st, options, PK_SAY, song_picker_catalog=CATALOG
        )
        self.assertEqual(active, PK_SHAPE)
        self.assertEqual(session["matching_song_dropdown"], PK_SHAPE)

    def test_widget_shape_while_live_say_commits_shape(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            "matching_song_dropdown": PK_SHAPE,
            _LAST_PICK_KEY: PK_SAY,
            "active_music_source": SOURCE_CATALOG,
            "song": "Say",
            "active_song_title": "Say",
            "display_key": "G",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            live = consume_uncommitted_catalog_dropdown(
                st, [PK_SAY, PK_SHAPE, PK_PERFECT], CATALOG
            )
        self.assertEqual(live, PK_SHAPE)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertEqual(session.get(EXPLICIT_CATALOG_PICK_COMMITTED_KEY), PK_SHAPE)
        self.assertEqual(session.get(CATALOG_RESTORE_PIN_KEY), PK_SHAPE)

    def test_master_already_shape_while_live_say_commits_shape(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            "matching_song_dropdown": PK_SHAPE,
            _LAST_PICK_KEY: PK_SHAPE,
            "active_music_source": SOURCE_CATALOG,
            "song": "Say",
            "active_song_title": "Say",
            "display_key": "G",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertEqual(session.get(EXPLICIT_CATALOG_PICK_COMMITTED_KEY), PK_SHAPE)

    def test_consume_shape_even_if_committed_was_stamped_say(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            "matching_song_dropdown": PK_SHAPE,
            _LAST_PICK_KEY: PK_SAY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_SAY,
            "active_music_source": SOURCE_CATALOG,
            "song": "Say",
            "display_key": "G",
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            live = consume_uncommitted_catalog_dropdown(
                st, [PK_SAY, PK_SHAPE, PK_PERFECT], CATALOG
            )
        self.assertEqual(live, PK_SHAPE)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(str(session.get("display_key") or ""), "Bm")

    def test_first_valid_widget_lag_keeps_committed_shape(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SHAPE,
            "matching_song_dropdown": PK_SAY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_SHAPE,
            "active_music_source": SOURCE_CATALOG,
            "song": "Shape of You",
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            live = consume_uncommitted_catalog_dropdown(
                st, [PK_SAY, PK_SHAPE, PK_PERFECT], CATALOG
            )
        self.assertEqual(live, PK_SHAPE)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)

    def test_stale_say_restore_pin_cannot_overwrite_committed_shape(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SHAPE,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "matching_song_dropdown": PK_SHAPE,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_SHAPE,
            CATALOG_RESTORE_PIN_KEY: PK_SAY,
        }
        master = reconcile_active_song_identity(session, CATALOG)
        self.assertEqual(master, PK_SHAPE)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song") or session[SELECTED_SONG_STATE_KEY]["title"], "Shape of You")

    def test_reconcile_recommits_shape_after_restore_reverts_active(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            SELECTED_SONG_STATE_KEY: {
                "pick_key": PK_SAY,
                "title": "Say",
                "artist": "John Mayer",
                "key": "G",
            },
            "matching_song_dropdown": PK_SHAPE,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_SHAPE,
            CATALOG_RESTORE_PIN_KEY: PK_SAY,
            "song": "Say",
        }
        master = reconcile_active_song_identity(session, CATALOG)
        self.assertEqual(master, PK_SHAPE)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song") or session[SELECTED_SONG_STATE_KEY]["title"], "Shape of You")

    def test_custom_trial_then_explicit_shape_is_fresh_bm(self) -> None:
        from songs.music_source import commit_custom_active_song

        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            _LAST_PICK_KEY: PK_SHAPE,
            "matching_song_dropdown": PK_SHAPE,
            "song": "Say",
            "display_key": "G",
            CATALOG_RESTORE_PIN_KEY: PK_SAY,
            "_reconcile_song_picker_catalog": CATALOG,
        }
        trial = {
            "id": "trial-first-click",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {
                "Verse": [
                    {"chord": "Em", "bars": 1},
                    {"chord": "Em", "bars": 1},
                    {"chord": "D", "bars": 1},
                    {"chord": "D", "bars": 1},
                ],
            },
            "bpm": 100,
            "progression_style": "Pop",
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"), patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(st, trial, invalidate_backing=lambda *_a, **_k: None)
            self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
            session["matching_song_dropdown"] = PK_SHAPE
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertEqual(session.get(CATALOG_RESTORE_PIN_KEY), PK_SHAPE)
        master = reconcile_active_song_identity(session, CATALOG)
        self.assertEqual(master, PK_SHAPE)

    def test_shape_perfect_shape_fresh_keys(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            "matching_song_dropdown": PK_SAY,
            "active_music_source": SOURCE_CATALOG,
            "display_key": "G",
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
            self.assertEqual(session.get("song"), "Shape of You")
            self.assertEqual(str(session.get("display_key") or ""), "Bm")
            apply_explicit_catalog_dropdown_pick(st, PK_PERFECT, CATALOG)
            self.assertEqual(session.get("song"), "Perfect")
            self.assertEqual(str(session.get("display_key") or ""), "G")
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertEqual(session.get("matching_song_dropdown") or session.get(PENDING_MATCHING_SONG_DROPDOWN), PK_SHAPE)

    def test_accidental_say_still_blocked_while_custom_owns(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "active_music_source": SOURCE_CUSTOM,
            "song": "Trial Song",
            "active_song_title": "Trial Song",
            SELECTED_SONG_STATE_KEY: {"title": "Trial Song", "pick_key": "custom::trial-1"},
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            result = apply_pick_key(st, PK_SAY, CATALOG, persist=False, origin="user")
        self.assertIn("Trial", str((result or {}).get("title") or session.get("song") or ""))
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)

    def test_pin_say_then_explicit_shape_survives_reconcile(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            "matching_song_dropdown": PK_SAY,
            "active_music_source": SOURCE_CATALOG,
            "display_key": "G",
            "_reconcile_song_picker_catalog": CATALOG,
        }
        pin_catalog_restore_identity(
            session,
            PK_SAY,
            {"pick_key": PK_SAY, "title": "Say", "artist": "John Mayer", "key": "G"},
        )
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get(CATALOG_RESTORE_PIN_KEY), PK_SHAPE)
        master = reconcile_active_song_identity(session, CATALOG)
        self.assertEqual(master, PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")


if __name__ == "__main__":
    unittest.main()

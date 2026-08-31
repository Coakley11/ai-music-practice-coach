"""First-click Songs picker must commit Shape, not leftover Say.

Explicit catalog pick > current owner > pending/pin/master/first_valid.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.music_source import (
    CATALOG_PICKER_PENDING_EXPLICIT_KEY,
    CATALOG_RESTORE_PIN_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    begin_explicit_catalog_selection,
    pin_catalog_restore_identity,
    switch_to_catalog_from_custom,
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

    def _trial_row(self) -> dict:
        return {
            "id": "trial-owner-switch",
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

    def test_pending_picker_hides_custom_hub_when_radio_still_custom(self) -> None:
        from songs.music_source import music_picker_shows_custom_hub

        session = {
            CATALOG_PICKER_PENDING_EXPLICIT_KEY: True,
            "song_picker_active_source": "Use Custom Progression / Create Your Own Song",
            "active_music_source": SOURCE_CUSTOM,
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
        }
        self.assertFalse(music_picker_shows_custom_hub(session))

    def test_sync_does_not_put_custom_pick_in_catalog_dropdown(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "matching_song_dropdown": "custom::trial-1",
            "active_music_source": SOURCE_CUSTOM,
            "song": "Trial Song",
            "active_song_title": "Trial Song",
        }
        st = _st(session)
        options = [PK_SAY, PK_SHAPE, PK_PERFECT]
        sync_matching_song_dropdown_before_widget(
            st, options, PK_SAY, song_picker_catalog=CATALOG
        )
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), "custom::trial-1")
        self.assertEqual(session.get("matching_song_dropdown"), PK_SAY)
        self.assertIn("Trial", str(session.get("song") or ""))
        self.assertNotEqual(str(session.get("song") or ""), "Say")

    def test_explicit_shape_from_custom_blocks_lagging_custom_radio(self) -> None:
        from songs.music_source import (
            CATALOG_SWITCH_APPLIED_THIS_RUN_KEY,
            commit_custom_active_song,
        )

        session = {
            "studio_page": "picker",
            "_script_run_seq": 10,
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            _LAST_PICK_KEY: PK_SAY,
            "song": "Say",
            "display_key": "G",
            "_reconcile_song_picker_catalog": CATALOG,
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"), patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(st, self._trial_row(), invalidate_backing=lambda *_a, **_k: None)
            self.assertTrue(str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("custom::"))
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertIsNotNone(session.get(CATALOG_SWITCH_APPLIED_THIS_RUN_KEY))

    def test_use_catalog_without_last_song_does_not_canonicalize_say(self) -> None:
        from songs.music_source import commit_custom_active_song

        session = {
            "studio_page": "picker",
            "active_music_source": SOURCE_CATALOG,
            ACTIVE_CATALOG_PICK_KEY: PK_SAY,
            _LAST_PICK_KEY: PK_SAY,
            "song": "Say",
            "active_song_title": "Say",
            "display_key": "G",
            "_reconcile_song_picker_catalog": CATALOG,
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"), patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(st, self._trial_row(), invalidate_backing=lambda *_a, **_k: None)
            self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
            self.assertIn("Trial", str(session.get("song") or ""))
            ok = switch_to_catalog_from_custom(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda *_a, **_k: None,
                force=True,
            )
        self.assertTrue(ok)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial", str(session.get("song") or ""))
        self.assertTrue(session.get(CATALOG_PICKER_PENDING_EXPLICIT_KEY))
        self.assertNotEqual(str(session.get("song") or ""), "Say")
        session["matching_song_dropdown"] = PK_SHAPE
        with patch("songs.state.persist_music_local_state"):
            apply_explicit_catalog_dropdown_pick(st, PK_SHAPE, CATALOG)
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertFalse(session.get(CATALOG_PICKER_PENDING_EXPLICIT_KEY))

    def test_consume_first_valid_while_custom_does_not_apply_say(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "matching_song_dropdown": PK_SAY,
            "active_music_source": SOURCE_CUSTOM,
            "song": "Trial Song",
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            live = consume_uncommitted_catalog_dropdown(
                st, [PK_SAY, PK_SHAPE, PK_PERFECT], CATALOG
            )
        self.assertEqual(live, "custom::trial-1")
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial", str(session.get("song") or ""))

    def test_consume_shape_while_custom_commits_catalog_shape(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: "custom::trial-1",
            "matching_song_dropdown": PK_SHAPE,
            _LAST_PICK_KEY: PK_SAY,
            "active_music_source": SOURCE_CUSTOM,
            "song": "Trial Song",
            "display_key": "D",
        }
        st = _st(session)
        with patch("songs.state.persist_music_local_state"):
            live = consume_uncommitted_catalog_dropdown(
                st, [PK_SAY, PK_SHAPE, PK_PERFECT], CATALOG
            )
        self.assertEqual(live, PK_SHAPE)
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")

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

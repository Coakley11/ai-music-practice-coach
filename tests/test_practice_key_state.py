"""Tests for per-source practice concert key persistence."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import CPL_ACTIVE_KEY, CPL_LAST_DISPLAY_KEY
from songs.key_state import (
    IDENTITY_KEY,
    apply_display_key_for_active_song,
    mark_display_key_changed,
    song_display_identity,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


class TestPracticeKeyBySource(unittest.TestCase):
    def test_saved_key_survives_refresh_same_pick(self) -> None:
        pick = "Pop::Shape of You"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Am"},
        }
        st = SimpleNamespace(session_state=session)
        identity = song_display_identity("Shape of You", "Ed Sheeran", "Bm", pick_key=pick)
        apply_display_key_for_active_song(st, "Bm", identity)
        self.assertEqual(session.get("display_key"), "Am")

    def test_new_pick_uses_original_not_previous_saved_key(self) -> None:
        shape = "Pop::Shape of You"
        photo = "Pop::Photograph"
        session = {
            "active_catalog_pick_key": photo,
            "selected_song": {"title": "Photograph", "key": "E", "pick_key": photo},
            PRACTICE_KEY_BY_SOURCE_KEY: {shape: "Am"},
            IDENTITY_KEY: shape,
        }
        st = SimpleNamespace(session_state=session)
        identity = song_display_identity("Photograph", "Ed Sheeran", "E", pick_key=photo)
        apply_display_key_for_active_song(st, "E", identity)
        self.assertEqual(session.get("display_key"), "E")

    def test_custom_progression_key_persists(self) -> None:
        pick = "custom::trial-1"
        session = {
            "active_catalog_pick_key": pick,
            CPL_ACTIVE_KEY: {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "original_sections": {"Verse": [{"chord": "D", "bars": 4}]},
            },
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "E"},
            CPL_LAST_DISPLAY_KEY: "E",
        }
        saved = get_practice_concert_key(session, pick)
        self.assertEqual(saved, "E")

    def test_mark_display_key_changed_writes_practice_key_map(self) -> None:
        pick = "Pop::Shape of You"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            "display_key": "E",
        }
        st = SimpleNamespace(session_state=session)
        with patch("active_song_state.flush_active_song_edits_and_save", create=True, return_value=True):
            with patch("songs.state.persist_music_local_state"):
                with patch("custom_progression_lab.on_global_display_key_change", return_value=False):
                    mark_display_key_changed(st)
        saved = get_practice_concert_key(session, pick)
        self.assertTrue(saved)
        # Sidebar may normalize quality (E → Em) for a minor song; persistence is the contract.
        self.assertTrue(
            any(str(v).strip() for v in session.get(PRACTICE_KEY_BY_SOURCE_KEY, {}).values())
        )
        self.assertEqual(saved, session.get("display_key"))

    def test_set_practice_concert_key_round_trip(self) -> None:
        session: dict = {}
        set_practice_concert_key(session, "E", pick_key="custom::trial-1")
        self.assertEqual(get_practice_concert_key(session, "custom::trial-1"), "E")

    def test_legacy_double_colon_pick_aliases_canonical_sep(self) -> None:
        """Sticky under Genre::Label must resolve when lookup uses Genre\\x1fLabel."""
        from song_catalog.catalog import format_pick_key

        legacy = "Pop::Shape of You — Ed Sheeran"
        canonical = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        session: dict = {PRACTICE_KEY_BY_SOURCE_KEY: {legacy: "C#m"}}
        self.assertEqual(get_practice_concert_key(session, canonical), "C#m")
        set_practice_concert_key(session, "C#m", pick_key=legacy)
        self.assertEqual(get_practice_concert_key(session, canonical), "C#m")
        # Canonical write migrates away from the legacy alias.
        self.assertNotIn(legacy, session[PRACTICE_KEY_BY_SOURCE_KEY])
        self.assertEqual(session[PRACTICE_KEY_BY_SOURCE_KEY].get(canonical), "C#m")

    def test_remount_original_does_not_wipe_sticky(self) -> None:
        """H2: silent Original reseed must not overwrite sticky Dm/C#m."""
        pick = "Pop::Shape of You"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Dm"},
        }
        with patch(
            "songs.music_source._catalog_original_key_for_session",
            return_value="Bm",
        ):
            set_practice_concert_key(session, "Bm", pick_key=pick)
        self.assertEqual(get_practice_concert_key(session, pick), "Dm")

    def test_user_sidebar_can_restore_catalog_original(self) -> None:
        """Explicit Practice Key return to Original (Dm → Bm) must stick."""
        pick = "Pop::Shape of You"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Dm"},
            "display_key_change_source": "sidebar_on_change",
        }
        with patch(
            "songs.music_source._catalog_original_key_for_session",
            return_value="Bm",
        ):
            set_practice_concert_key(session, "Bm", pick_key=pick)
        self.assertEqual(get_practice_concert_key(session, pick), "Bm")

    def test_allow_restore_original_flag_writes_home(self) -> None:
        pick = "Pop::Shape of You"
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": pick},
            PRACTICE_KEY_BY_SOURCE_KEY: {pick: "Dm"},
        }
        with patch(
            "songs.music_source._catalog_original_key_for_session",
            return_value="Bm",
        ):
            set_practice_concert_key(
                session, "Bm", pick_key=pick, allow_restore_original=True
            )
        self.assertEqual(get_practice_concert_key(session, pick), "Bm")


if __name__ == "__main__":
    unittest.main()

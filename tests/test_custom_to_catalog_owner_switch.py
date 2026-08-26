"""Explicit Custom → Catalog owner switch is not a permanent Custom lock.

Product order:
  EXPLICIT USER SONG PICK > CURRENT GLOBAL ACTIVE OWNER > LAST_CUSTOM / sticky

Shape Bm → Dm, then Trial Set-as-Active, then explicit Shape must become
Catalog / Shape of You at fresh Original B minor. Accidental Say apply while
Custom owns must stay blocked (E5).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.music_source import (
    CATALOG_BEFORE_CUSTOM_KEY,
    CATALOG_BEFORE_CUSTOM_LOCK_KEY,
    EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY,
    LAST_CUSTOM_STATE_KEY,
    SONG_PICKER_SOURCE_CUSTOM,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    begin_explicit_catalog_selection,
    commit_custom_active_song,
    custom_progression_is_active,
    explicit_catalog_selection_is_authoritative,
    set_custom_source,
    switch_to_catalog_from_custom,
)
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, _LAST_PICK_KEY, apply_pick_key
from workflow_musical_authority import custom_owns_active_song_material


PK_SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")
PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")

CATALOG = {
    "Pop": {
        "Shape of You — Ed Sheeran": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "sections": {"Verse": ["F#m", "C#m", "Bm", "E"]},
        },
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
    }
}


def _trial_active() -> dict:
    return {
        "id": "trial-rev-owner-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Intro": [],
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ],
            "Pre-Chorus": [],
            "Chorus": [],
            "Bridge": [],
            "Solo": [],
            "Outro": [],
        },
        "bpm": 100,
        "progression_style": "Pop",
        "groove_style": "Pop",
    }


def _shape_catalog_session(*, practice_key: str = "Dm") -> dict:
    return {
        "studio_page": "picker",
        "active_music_source": SOURCE_CATALOG,
        ACTIVE_CATALOG_PICK_KEY: PK_SHAPE,
        _LAST_PICK_KEY: PK_SHAPE,
        "song": "Shape of You",
        "active_song_title": "Shape of You",
        "display_key": practice_key,
        "concert_key": practice_key,
        SELECTED_SONG_STATE_KEY: {
            "pick_key": PK_SHAPE,
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
        },
        PRACTICE_KEY_BY_SOURCE_KEY: {PK_SHAPE: practice_key},
        CATALOG_BEFORE_CUSTOM_KEY: {
            "pick_key": PK_SHAPE,
            "original_key": "Bm",
            "display_key": practice_key,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        },
        CATALOG_BEFORE_CUSTOM_LOCK_KEY: PK_SHAPE,
        "catalog_session": {
            "pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        },
        "_reconcile_song_picker_catalog": CATALOG,
    }


class TestCustomToCatalogOwnerSwitch(unittest.TestCase):
    def _activate_trial(self, session: dict) -> SimpleNamespace:
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with patch("songs.state.persist_music_local_state"), patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(
                st,
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        return st

    def test_accidental_say_apply_still_blocked_while_custom_owns(self) -> None:
        session = _shape_catalog_session()
        st = self._activate_trial(session)
        self.assertTrue(custom_progression_is_active(session))
        result = apply_pick_key(st, PK_SAY, CATALOG, persist=False, origin="user")
        self.assertEqual(result.get("title"), "Trial Song")
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial Song", str(session.get("song") or ""))

    def test_explicit_shape_pick_releases_custom_even_if_master_pick_still_shape(
        self,
    ) -> None:
        """First blocker: Custom GA + _master_song_pick_key still Shape no-ops the pick."""
        session = _shape_catalog_session()
        st = self._activate_trial(session)
        self.assertTrue(custom_owns_active_song_material(session))
        # Reproduce the live leftover: Custom owns, but last master pick is still Shape.
        session[_LAST_PICK_KEY] = PK_SHAPE

        begin_explicit_catalog_selection(session)
        self.assertTrue(explicit_catalog_selection_is_authoritative(session))
        self.assertFalse(custom_owns_active_song_material(session))

        with patch("songs.state.persist_music_local_state"):
            result = apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        self.assertEqual(result.get("title"), "Shape of You")
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get(ACTIVE_CATALOG_PICK_KEY), PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertFalse(custom_progression_is_active(session))
        self.assertFalse(custom_owns_active_song_material(session))
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        last_custom = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((last_custom.get("active") or {}).get("name") or last_custom.get("name") or ""), "Trial Song")

    def test_shape_dm_trial_d_shape_fresh_bm(self) -> None:
        session = _shape_catalog_session(practice_key="Dm")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Dm")
        st = self._activate_trial(session)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial Song", str(session.get("song") or ""))
        self.assertEqual(str(session.get("display_key") or ""), "D")
        # Prior Shape Dm must not survive Trial becoming Global Active.
        self.assertFalse(get_practice_concert_key(session, PK_SHAPE))

        begin_explicit_catalog_selection(session)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")
        self.assertNotEqual(get_practice_concert_key(session, PK_SHAPE), "Dm")

        set_practice_concert_key(session, "Dm", pick_key=PK_SHAPE)
        session["display_key"] = "Dm"
        session["concert_key"] = "Dm"
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Dm")
        self.assertEqual(session.get("display_key"), "Dm")

    def test_switch_to_catalog_from_custom_is_fresh_shape_bm(self) -> None:
        session = _shape_catalog_session(practice_key="Dm")
        st = self._activate_trial(session)
        session["song_picker_active_source"] = SONG_PICKER_SOURCE_CUSTOM
        with patch("songs.state.persist_music_local_state"), patch(
            "songs.state.apply_pick_key", wraps=apply_pick_key
        ):
            ok = switch_to_catalog_from_custom(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda *_a, **_k: None,
            )
        self.assertTrue(ok)
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("song"), "Shape of You")
        self.assertEqual(str(session.get("display_key") or ""), "Bm")

    def test_shape_perfect_trial_fresh_activations(self) -> None:
        session = _shape_catalog_session(practice_key="Bm")
        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        begin_explicit_catalog_selection(session)
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_PERFECT, CATALOG, persist=False, origin="user")
        self.assertEqual(session.get("song"), "Perfect")
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(str(session.get("display_key") or ""), "G")

        self._activate_trial(session)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertIn("Trial Song", str(session.get("song") or ""))
        self.assertEqual(str(session.get("display_key") or ""), "D")
        last_custom = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((last_custom.get("active") or {}).get("name") or last_custom.get("name") or ""), "Trial Song")

    def test_custom_owns_yields_after_explicit_catalog_even_if_pick_still_custom(self) -> None:
        session = _shape_catalog_session()
        self._activate_trial(session)
        self.assertTrue(custom_owns_active_song_material(session))
        begin_explicit_catalog_selection(session)
        # Partial switch: identity still custom:: until apply_pick_key lands.
        self.assertTrue(str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").startswith("custom::"))
        self.assertFalse(custom_owns_active_song_material(session))
        self.assertTrue(session.get(USER_CATALOG_SOURCE_CHOICE_KEY))

    def test_catalog_seal_heal_does_not_overwrite_custom_ga_practice_key(self) -> None:
        from source_session_state import heal_sealed_catalog_sidebar_if_needed

        session = _shape_catalog_session(practice_key="G")
        st = self._activate_trial(session)
        session["studio_page"] = "picker"
        session["display_key"] = "D"
        session["concert_key"] = "D"
        session["_sbi_custom_sealed_catalog_pk"] = "G"
        session["_sbi_custom_sealed_catalog_pick"] = PK_PERFECT
        healed = heal_sealed_catalog_sidebar_if_needed(st, session)
        self.assertEqual(healed, "")
        self.assertEqual(session.get("display_key"), "D")
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)

    def test_set_custom_source_clears_shape_sticky_only_when_leaving_catalog(self) -> None:
        session = _shape_catalog_session(practice_key="Dm")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Dm")
        set_custom_source(session)
        self.assertEqual(session.get("active_music_source"), SOURCE_CUSTOM)
        self.assertFalse(get_practice_concert_key(session, PK_SHAPE))
        # Second call while already Custom must not need leftover catalog sticky.
        session[PRACTICE_KEY_BY_SOURCE_KEY] = {PK_SHAPE: "Dm"}
        session[EXPLICIT_CUSTOM_ACTIVATION_EPOCH_KEY] = 1.0
        set_custom_source(session)
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Dm")


if __name__ == "__main__":
    unittest.main()

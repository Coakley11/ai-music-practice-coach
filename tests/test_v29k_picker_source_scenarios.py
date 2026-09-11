"""End-to-end session simulations for v29k picker source toggle and catalog history."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    CPL_SAVED_KEY,
    default_active_progression,
    list_saved_progression_names,
    save_progression,
)
from song_catalog.catalog import format_pick_key
from songs.music_source import (
    CATALOG_BEFORE_CUSTOM_KEY,
    LAST_CATALOG_STATE_KEY,
    SONG_PICKER_SOURCE_CUSTOM,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    is_custom_progression,
    previous_catalog_snapshot,
    reconcile_picker_music_source,
    restore_previous_catalog_song,
    set_custom_source,
    switch_to_catalog_from_custom,
)
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    SELECTED_SONG_STATE_KEY,
    _LAST_PICK_KEY,
    apply_pick_key,
)

PK_PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
PK_SAY = format_pick_key("Pop", "Say — John Mayer")

CATALOG = {
    "Pop": {
        "Perfect — Ed Sheeran": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "genre": "Pop",
        },
        "Say — John Mayer": {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "genre": "Pop",
        },
    }
}


def _fake_st(session: dict) -> SimpleNamespace:
    return SimpleNamespace(session_state=session)


def _picker_shows_custom_hub(session: dict) -> bool:
    choice = str(session.get("song_picker_active_source") or "").strip()
    return is_custom_progression(session) or choice.startswith("Use Custom")


def _trial_song_active(session: dict) -> None:
    store: dict = {}
    active = default_active_progression()
    active["name"] = "Trial Song"
    active["original_key_center"] = "D"
    save_progression(store, "Trial Song", active)
    session[CPL_SAVED_KEY] = store
    session[CPL_ACTIVE_KEY] = active
    session["active_music_source"] = SOURCE_CUSTOM
    session["song_picker_active_source"] = SONG_PICKER_SOURCE_CUSTOM


class TestV29kPickerSourceScenarios(unittest.TestCase):
    def test_scenario1_custom_toggle_after_catalog(self) -> None:
        """Custom → catalog (Say) → Use Custom Progression shows library path."""
        st = _fake_st({})
        _trial_song_active(st.session_state)

        with patch("songs.state.persist_music_local_state"):
            switch_to_catalog_from_custom(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda _st: None,
            )
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)

        ss = st.session_state
        self.assertFalse(is_custom_progression(ss))
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], PK_SAY)

        ss["studio_page"] = "picker"
        ss["song_picker_active_source"] = SONG_PICKER_SOURCE_CUSTOM
        # Radio on_change clears USER_CATALOG before reconcile (deliberate Custom flip).
        # A lagging Custom radio while USER_CATALOG is still set must NOT reclaim.
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY

        ss.pop(USER_CATALOG_SOURCE_CHOICE_KEY, None)
        self.assertTrue(reconcile_picker_music_source(ss))
        self.assertTrue(is_custom_progression(ss))
        self.assertTrue(_picker_shows_custom_hub(ss))
        names = list_saved_progression_names(ss.get(CPL_SAVED_KEY) or {})
        self.assertIn("Trial Song", names)
        self.assertEqual(ss[CPL_ACTIVE_KEY]["name"], "Trial Song")

    def test_scenario2_catalog_history_survives_custom_toggle(self) -> None:
        """Perfect → Say → custom → catalog keeps Recently Selected = Perfect."""
        st = _fake_st({"active_music_source": SOURCE_CATALOG, "display_key": "G"})
        with patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_PERFECT, CATALOG, skip_activity_log=True)
            apply_pick_key(st, PK_SAY, CATALOG, skip_activity_log=True)

        ss = st.session_state
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        prev = previous_catalog_snapshot(ss)
        self.assertIsNotNone(prev)
        self.assertEqual(prev.get("pick_key"), PK_PERFECT)

        set_custom_source(ss)
        # Pass 8: LAST_CATALOG / before-custom pin the catalog song left for Custom.
        self.assertEqual(ss[LAST_CATALOG_STATE_KEY]["pick_key"], PK_SAY)
        self.assertEqual((ss.get(CATALOG_BEFORE_CUSTOM_KEY) or {}).get("pick_key"), PK_SAY)

        with patch("songs.state.persist_music_local_state"):
            switch_to_catalog_from_custom(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda _st: None,
            )

        ss = st.session_state
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        prev = previous_catalog_snapshot(ss)
        if prev is not None:
            self.assertEqual(prev.get("pick_key"), PK_PERFECT)

    def test_scenario3_restore_previous_catalog_song_swaps_and_preserves_display_key(
        self,
    ) -> None:
        """Say current, Perfect previous → restore swaps and keeps display key."""
        st = _fake_st(
            {
                "active_music_source": SOURCE_CATALOG,
                ACTIVE_CATALOG_PICK_KEY: PK_SAY,
                _LAST_PICK_KEY: PK_SAY,
                "display_key": "Eb",
                SELECTED_SONG_STATE_KEY: {
                    "pick_key": PK_SAY,
                    "title": "Say",
                    "artist": "John Mayer",
                    "key": "G",
                },
                LAST_CATALOG_STATE_KEY: {
                    "pick_key": PK_PERFECT,
                    "selected_song": {
                        "pick_key": PK_PERFECT,
                        "title": "Perfect",
                        "artist": "Ed Sheeran",
                        "key": "G",
                    },
                    "original_key": "G",
                    "display_key": "F",
                },
            }
        )
        with patch("songs.state.persist_music_local_state"):
            ok = restore_previous_catalog_song(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda _st: None,
            )
        self.assertTrue(ok)
        ss = st.session_state
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], PK_PERFECT)
        # Pass 8: restore prefers sealed/original catalog key for Perfect (G).
        self.assertEqual(ss["display_key"], "G")
        prev = previous_catalog_snapshot(ss)
        if prev is not None:
            self.assertEqual(prev.get("pick_key"), PK_SAY)

    def test_scenario4_custom_song_persists_across_source_toggle(self) -> None:
        """Trial Song activate → catalog → custom keeps library and active draft."""
        st = _fake_st({})
        _trial_song_active(st.session_state)

        with patch("songs.state.persist_music_local_state"):
            switch_to_catalog_from_custom(
                st,
                song_picker_catalog=CATALOG,
                invalidate_backing=lambda _st: None,
            )

        ss = st.session_state
        self.assertFalse(is_custom_progression(ss))
        names = list_saved_progression_names(ss.get(CPL_SAVED_KEY) or {})
        self.assertIn("Trial Song", names)

        set_custom_source(ss)
        ss["studio_page"] = "picker"
        ss["song_picker_active_source"] = SONG_PICKER_SOURCE_CUSTOM
        reconcile_picker_music_source(ss)
        self.assertTrue(is_custom_progression(ss))
        self.assertTrue(_picker_shows_custom_hub(ss))
        names = list_saved_progression_names(ss.get(CPL_SAVED_KEY) or {})
        self.assertIn("Trial Song", names)
        self.assertEqual(ss[CPL_ACTIVE_KEY]["name"], "Trial Song")


if __name__ == "__main__":
    unittest.main()

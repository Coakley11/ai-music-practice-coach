"""Slice 1: SBI Custom visit Practice Key owner bind + no premature Backing stamp."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from custom_progression_lab import CPL_ACTIVE_KEY
from practice_focus_creative import format_creative_practice_focus_caption
from song_catalog.catalog import format_pick_key
from songs.key_state import get_authoritative_display_key
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)
from source_session_state import (
    SBI_PREVIEW_SOURCE_KEY,
    custom_sbi_owns_sidebar_practice_key,
    install_sbi_custom_identity_before_widgets,
    note_explicit_sbi_source_selection,
    prepare_sbi_custom_sidebar_display_key,
    resolve_sidebar_original_key_for_caption,
    restore_sbi_active_catalog_identity_before_widgets,
    set_sbi_preview_source,
    stamp_sbi_active_leave_intent,
)


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _trial() -> dict:
    return {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
        "bpm": 100,
        "time_signature": "4/4",
        "progression_style": "Pop",
    }


def _perfect_ga_with_last_custom_trial() -> dict:
    trial = _trial()
    ss = {
        "studio_page": "creative",
        "instrument": "Guitar",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "active_music_source": "catalog",
        "explicit_music_source_choice": "catalog",
        "active_catalog_pick_key": PERFECT_PICK,
        "original_key": "G",
        "display_key": "C",
        "concert_key": "C",
        "catalog_session": {
            "pick_key": PERFECT_PICK,
            "original_key": "G",
            "selected_song": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "genre": "Pop",
                "key": "G",
                "pick_key": PERFECT_PICK,
            },
        },
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C", TRIAL_PICK: "F"},
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": trial,
        },
        "improv_jam_style": "Jewish ballad",
        "improv_song_source": "Active song",
        SBI_PREVIEW_SOURCE_KEY: "Active song",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_intelligence_tab": "Song-Based Improvisation",
    }
    set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
    mark_practice_key_user_override(ss, PERFECT_PICK)
    set_practice_concert_key(ss, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
    mark_practice_key_user_override(ss, TRIAL_PICK)
    return ss


def _enter_sbi_custom(ss: dict) -> None:
    ss["studio_page"] = "creative"
    note_explicit_sbi_source_selection(ss, "Custom progression")
    set_sbi_preview_source(ss, "Custom progression")
    ss["improv_song_source"] = "Custom progression"
    install_sbi_custom_identity_before_widgets(ss)
    prepare_sbi_custom_sidebar_display_key(_st(ss), ss)


def _enter_sbi_active(ss: dict) -> None:
    ss["studio_page"] = "creative"
    note_explicit_sbi_source_selection(ss, "Active song")
    stamp_sbi_active_leave_intent(ss)
    set_sbi_preview_source(ss, "Active song")
    ss["improv_song_source"] = "Active song"
    restore_sbi_active_catalog_identity_before_widgets(ss)
    install_sbi_custom_identity_before_widgets(ss)


class Slice1CaseACustomVisitOverPerfectGA(unittest.TestCase):
    def test_custom_visit_binds_practice_f_preserves_perfect_c(self) -> None:
        ss = _perfect_ga_with_last_custom_trial()
        _enter_sbi_custom(ss)

        self.assertTrue(custom_sbi_owns_sidebar_practice_key(ss))
        self.assertEqual(str((ss.get(CPL_ACTIVE_KEY) or {}).get("name") or ""), "Trial Song")
        self.assertEqual(resolve_sidebar_original_key_for_caption(ss, current_original="G"), "D")
        self.assertEqual(get_practice_concert_key(ss), "F")
        self.assertEqual(get_authoritative_display_key(ss, original_key="G"), "F")
        self.assertEqual(str(ss.get("display_key") or ""), "F")
        self.assertEqual(str(ss.get("concert_key") or ""), "F")
        focus = format_creative_practice_focus_caption(ss)
        self.assertIn("SBI Custom", focus)
        self.assertIn("Trial Song", focus)
        # Perfect C remains saved on the catalog pick.
        self.assertEqual(get_practice_concert_key(ss, PERFECT_PICK), "C")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")

    def test_saved_f_on_live_uuid_alias_surfaces_as_d_f(self) -> None:
        """Disk seed id vs live CPL UUID: Practice F on either alias → Custom visit D/F."""
        from source_session_state import resolve_sbi_custom_practice_key

        seed_pick = "custom::trial-phase-b-seed"
        live_pick = "custom::live-cpl-uuid"
        trial = _trial()
        trial["id"] = "trial-phase-b-seed"
        live = dict(trial)
        live["id"] = "live-cpl-uuid"
        ss = _perfect_ga_with_last_custom_trial()
        ss[LAST_CUSTOM_STATE_KEY] = {
            "pick_key": seed_pick,
            "custom_home_key": "D",
            "active": trial,
            "name": "Trial Song",
        }
        ss[CPL_ACTIVE_KEY] = live
        ss[PRACTICE_KEY_BY_SOURCE_KEY] = {PERFECT_PICK: "C", live_pick: "F"}
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        set_practice_concert_key(ss, "F", pick_key=live_pick, allow_restore_original=True)
        mark_practice_key_user_override(ss, live_pick)
        # Seed pick has no sticky yet — visit must still resolve F via alias.
        self.assertEqual(get_practice_concert_key(ss, seed_pick, default=""), "")

        _enter_sbi_custom(ss)
        self.assertEqual(resolve_sbi_custom_practice_key(ss), "F")
        self.assertEqual(get_practice_concert_key(ss), "F")
        self.assertEqual(resolve_sidebar_original_key_for_caption(ss, current_original="G"), "D")
        self.assertEqual(get_practice_concert_key(ss, PERFECT_PICK), "C")

    def test_catalog_reclaim_does_not_clear_custom_practice_sticky(self) -> None:
        """Save→Custom GA→Perfect reclaim must keep Trial Practice F parked."""
        from songs.practice_key_state import clear_practice_concert_key

        ss = _perfect_ga_with_last_custom_trial()
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")
        # Simulate songs/state.py catalog reclaim clearing prior pick.
        prev = TRIAL_PICK
        pick_key = PERFECT_PICK
        clear_practice_concert_key(ss, pick_key)
        if not str(prev).startswith(("custom::", "custom\x1f", "composition::", "composition\x1f")):
            clear_practice_concert_key(ss, prev)
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "F")
        set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT_PICK)
        _enter_sbi_custom(ss)
        self.assertEqual(get_practice_concert_key(ss), "F")

    def test_leave_active_perfect_restores_g_c_return_custom_restores_d_f(self) -> None:
        ss = _perfect_ga_with_last_custom_trial()
        _enter_sbi_custom(ss)
        self.assertEqual(get_practice_concert_key(ss), "F")

        _enter_sbi_active(ss)
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(ss))
        self.assertEqual(get_practice_concert_key(ss, PERFECT_PICK), "C")
        # Bare read follows Active / Global Active again.
        self.assertEqual(get_practice_concert_key(ss), "C")
        orig = resolve_sidebar_original_key_for_caption(ss, current_original="G")
        self.assertTrue(str(orig).upper().startswith("G"), orig)

        _enter_sbi_custom(ss)
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(ss))
        self.assertEqual(resolve_sidebar_original_key_for_caption(ss, current_original="G"), "D")
        self.assertEqual(get_practice_concert_key(ss), "F")
        self.assertEqual(get_practice_concert_key(ss, PERFECT_PICK), "C")


class Slice1CaseBSongsSidebarAuthority(unittest.TestCase):
    def test_picker_perfect_no_mixed_original_d_practice_c(self) -> None:
        ss = _perfect_ga_with_last_custom_trial()
        # Stale Custom memory after a prior Creative visit.
        ss["_sbi_custom_sidebar_overlay"] = True
        ss["improv_song_source"] = "Custom progression"
        set_sbi_preview_source(ss, "Custom progression")
        ss["studio_page"] = "picker"

        self.assertFalse(custom_sbi_owns_sidebar_practice_key(ss))
        orig = resolve_sidebar_original_key_for_caption(ss, current_original="G")
        pk = get_practice_concert_key(ss)
        self.assertTrue(str(orig).upper().startswith("G"), orig)
        self.assertEqual(pk, "C")
        # Mixed owner pair Original D / Practice C must not appear.
        self.assertFalse(str(orig).upper().startswith("D") and pk == "C")


class Slice1CaseCNoPrematureBackingStamp(unittest.TestCase):
    def test_sbi_custom_preview_does_not_stamp_backing_handoff(self) -> None:
        ss = _perfect_ga_with_last_custom_trial()
        _enter_sbi_custom(ss)

        self.assertFalse(bool(ss.get("_nested_custom_sbi_backing")))
        self.assertNotEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "song_improv")
        # Visit identity still established.
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(ss))
        self.assertEqual(get_practice_concert_key(ss), "F")

    def test_pages_backing_from_creative_still_stamps_on_launch(self) -> None:
        from backing_source_navigation import prepare_global_backing_navigation

        ss = _perfect_ga_with_last_custom_trial()
        _enter_sbi_custom(ss)
        self.assertFalse(bool(ss.get("_nested_custom_sbi_backing")))

        prepare_global_backing_navigation(ss, from_page="creative")
        self.assertTrue(bool(ss.get("_nested_custom_sbi_backing")))
        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "song_improv")


if __name__ == "__main__":
    unittest.main()

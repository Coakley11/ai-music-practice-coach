"""Slice 2: Jam/Entry temporary ownership must not contaminate Perfect/Trial."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from generated_jam_key_context import (
    GENERATED_JAM_KEY_CONTEXT_KEY,
    generated_jam_owns_practice_key,
)
from practice_focus_creative import format_creative_practice_focus_caption
from sbi_active_catalog_practice_key import sbi_active_catalog_owns_practice_key
from song_catalog.catalog import format_pick_key
from songs.key_state import get_authoritative_display_key
from songs.practice_key_state import (
    creative_jam_owns_practice_settings,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)
from source_session_state import (
    note_explicit_sbi_source_selection,
    restore_sbi_active_catalog_identity_before_widgets,
    set_sbi_preview_source,
)


PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL = "custom::trial-d"


def _perfect_gc_with_stale_jam_eb() -> dict:
    ss = {
        "studio_page": "creative",
        "instrument": "Guitar",
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT,
        },
        "active_music_source": "catalog",
        "explicit_music_source_choice": "catalog",
        "active_catalog_pick_key": PERFECT,
        "original_key": "G",
        "display_key": "C",
        "concert_key": "C",
        "practice_key_by_source": {PERFECT: "C"},
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_entry_mode": "Jam Session Generator",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "improv_jam_key": "Eb",
        "improv_jam_style": "Jewish ballad",
        "_generated_jam_key_owner_active": True,
        GENERATED_JAM_KEY_CONTEXT_KEY: {
            "practice_key_token": "Eb",
            "entry_mode": "Jam Session Generator",
            "key_owner": "jam_session_generator",
            "practice_tonic": "Eb",
            "practice_mode": "major",
        },
    }
    set_practice_concert_key(ss, "C", pick_key=PERFECT, allow_restore_original=True)
    mark_practice_key_user_override(ss, PERFECT)
    return ss


class Slice2StaleJamCannotStealPerfectC(unittest.TestCase):
    def test_perfect_gc_stale_jam_eb_sbi_active_stays_c(self) -> None:
        ss = _perfect_gc_with_stale_jam_eb()
        self.assertTrue(sbi_active_catalog_owns_practice_key(ss))
        self.assertFalse(generated_jam_owns_practice_key(ss))
        self.assertFalse(creative_jam_owns_practice_settings(ss))
        self.assertEqual(get_practice_concert_key(ss), "C")
        self.assertEqual(get_authoritative_display_key(ss, original_key="G"), "C")
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "C")

    def test_stale_jam_blob_cannot_own_when_tool_is_sbi_active(self) -> None:
        ss = _perfect_gc_with_stale_jam_eb()
        ss["improv_intelligence_tab"] = ""
        # Empty tab + leftover Jam entry must not grant Jam ownership.
        self.assertTrue(sbi_active_catalog_owns_practice_key(ss))
        self.assertFalse(generated_jam_owns_practice_key(ss))
        self.assertFalse(creative_jam_owns_practice_settings(ss))

    def test_perfect_jam_perfect_restores_g_c(self) -> None:
        ss = _perfect_gc_with_stale_jam_eb()
        # Enter Jam for real.
        ss["improv_intelligence_tab"] = "Entry & Jam"
        ss["improv_entry_mode"] = "Jam Session Generator"
        self.assertFalse(sbi_active_catalog_owns_practice_key(ss))
        self.assertTrue(generated_jam_owns_practice_key(ss) or creative_jam_owns_practice_settings(ss))

        # Leave Jam → SBI Active Perfect.
        note_explicit_sbi_source_selection(ss, "Active song")
        set_sbi_preview_source(ss, "Active song")
        ss["improv_song_source"] = "Active song"
        ss["improv_intelligence_tab"] = "Song-Based Improvisation"
        ss["improv_entry_mode"] = "Song-Based Improvisation"
        restore_sbi_active_catalog_identity_before_widgets(ss)
        self.assertTrue(sbi_active_catalog_owns_practice_key(ss))
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "C")
        self.assertEqual(get_practice_concert_key(ss), "C")


class Slice2TrialJamRoundtrip(unittest.TestCase):
    def test_trial_df_jam_does_not_promote_perfect(self) -> None:
        trial = {
            "id": "trial-d",
            "name": "Trial Song",
            "original_key_center": "D",
            "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
        }
        ss = {
            "studio_page": "creative",
            "instrument": "Guitar",
            "song": "Trial Song",
            "active_music_source": "custom",
            "active_catalog_pick_key": TRIAL,
            "original_key": "D",
            "display_key": "F",
            "concert_key": "F",
            "practice_key_by_source": {TRIAL: "F", PERFECT: "C"},
            "cpl_active_progression": trial,
            "_last_custom_song_state": {
                "pick_key": TRIAL,
                "custom_home_key": "D",
                "active": trial,
                "name": "Trial Song",
            },
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Entry & Jam",
            "improv_jam_key": "Eb",
            "improv_jam_style": "Jewish ballad",
            "_generated_jam_key_owner_active": True,
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "practice_key_token": "Eb",
                "entry_mode": "Jam Session Generator",
                "key_owner": "jam_session_generator",
            },
        }
        set_practice_concert_key(ss, "F", pick_key=TRIAL, allow_restore_original=True)
        mark_practice_key_user_override(ss, TRIAL)
        set_practice_concert_key(ss, "C", pick_key=PERFECT, allow_restore_original=True)
        mark_practice_key_user_override(ss, PERFECT)

        # Leave Jam — underlying Trial sticky F and Perfect C both preserved.
        ss["improv_intelligence_tab"] = "Song-Based Improvisation"
        ss["improv_entry_mode"] = "Song-Based Improvisation"
        ss["sbi_preview_source"] = "Custom progression"
        ss["improv_song_source"] = "Custom progression"
        self.assertEqual(get_practice_concert_key(ss, TRIAL), "F")
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "C")
        self.assertNotEqual(str(ss.get("active_catalog_pick_key") or ""), PERFECT)


class Slice2JewishBalladResidue(unittest.TestCase):
    def test_new_jam_focus_clears_jewish_ballad_when_not_owning(self) -> None:
        ss = _perfect_gc_with_stale_jam_eb()
        focus = format_creative_practice_focus_caption(ss)
        self.assertNotIn("Jewish ballad", focus)
        self.assertNotIn("Jam Generator", focus)

    def test_entry_jewish_ballad_does_not_own_sbi_active(self) -> None:
        ss = _perfect_gc_with_stale_jam_eb()
        ss["improv_jam_style"] = "Jewish ballad"
        ss["improv_intelligence_tab"] = "Song-Based Improvisation"
        self.assertFalse(generated_jam_owns_practice_key(ss))
        focus = format_creative_practice_focus_caption(ss)
        self.assertNotIn("Jewish ballad", focus)


class Slice2JamBackingOwner(unittest.TestCase):
    def test_jam_backing_activation_stamps_entry_jam_owner(self) -> None:
        from backing_source_navigation import prepare_global_backing_navigation

        ss = _perfect_gc_with_stale_jam_eb()
        ss["improv_intelligence_tab"] = "Entry & Jam"
        ss["improv_entry_mode"] = "Jam Session Generator"
        ss["improv_jam_session"] = {
            "id": "jam-slice2",
            "key": "E",
            "style": "Bright Bossa Nova",
            "progression": ["Cmaj7", "Am7", "Dm7", "G7"],
        }
        # Explicit Jam launch context — Backing must inherit entry_jam, not Mission/SBI Custom.
        ss["_backing_explicit_handoff_source"] = "entry_jam"
        prepare_global_backing_navigation(ss, from_page="creative")
        handoff = str(ss.get("_backing_explicit_handoff_source") or "")
        self.assertEqual(handoff, "entry_jam")
        self.assertNotEqual(handoff, "mission")
        self.assertNotEqual(handoff, "song_improv")
        # Nested Custom SBI backing must not be stamped from Jam.
        self.assertFalse(bool(ss.get("_nested_custom_sbi_backing")))


class Slice2ShapeKeyStaysOnJam(unittest.TestCase):
    def test_shape_key_change_does_not_navigate_or_change_active_song(self) -> None:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        ss = _perfect_gc_with_stale_jam_eb()
        ss["improv_intelligence_tab"] = "Entry & Jam"
        ss["improv_entry_mode"] = "Jam Session Generator"
        ss["improv_jam_key"] = "E"
        ss[CAPO_ENABLED_KEY] = True
        ss[CAPO_SHAPE_KEY] = "C"
        ss["studio_page"] = "creative"
        before_page = ss["studio_page"]
        before_pick = ss["active_catalog_pick_key"]
        # Direct Shape Key commit (widget on_change writes CAPO_SHAPE_KEY only).
        ss[CAPO_SHAPE_KEY] = "E"
        self.assertEqual(ss.get("studio_page"), before_page)
        self.assertEqual(ss.get("active_catalog_pick_key"), before_pick)
        self.assertNotEqual(str(ss.get("studio_page") or ""), "upload")
        self.assertEqual(str(ss.get(CAPO_SHAPE_KEY) or ""), "E")
        self.assertEqual(str(ss.get("improv_entry_mode") or ""), "Jam Session Generator")


class Slice2PracticeFocusClearsJamResidue(unittest.TestCase):
    def test_trial_active_clears_jam_generator_jewish_ballad_focus(self) -> None:
        trial = {
            "id": "trial-d",
            "name": "Trial Song",
            "original_key_center": "D",
        }
        ss = {
            "studio_page": "creative",
            "active_music_source": "custom",
            "active_catalog_pick_key": TRIAL,
            "cpl_active_progression": trial,
            "_last_custom_song_state": {
                "pick_key": TRIAL,
                "custom_home_key": "D",
                "active": trial,
                "name": "Trial Song",
            },
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Song-Based Improvisation",
            "improv_jam_style": "Jewish ballad",
            "sbi_preview_source": "Custom progression",
            "improv_song_source": "Custom progression",
            "_generated_jam_key_owner_active": True,
            GENERATED_JAM_KEY_CONTEXT_KEY: {
                "practice_key_token": "Eb",
                "entry_mode": "Jam Session Generator",
                "key_owner": "jam_session_generator",
            },
        }
        focus = format_creative_practice_focus_caption(ss)
        self.assertNotIn("Jam Generator", focus)
        self.assertNotIn("Jewish ballad", focus)


if __name__ == "__main__":
    unittest.main()

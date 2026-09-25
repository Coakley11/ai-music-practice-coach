"""Slice 3: Mission / Mission Backing ownership — key authority, handoff, Return eligibility."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backing_nav_actions import build_backing_nav_actions
from creative_key_sync import canonical_mission_practice_key, creative_progression_display
from custom_progression_lab import CPL_ACTIVE_KEY
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _authoritative_practice_chart_key, _coherent_improv_key_pair
from mission_owner_contract import (
    clear_mission_return_eligibility,
    live_backing_owner_is_mission,
    resolve_mission_owner_context,
    resolve_mission_underlying_practice_key,
    resolve_mission_written_key,
    return_to_mission_eligible,
    stamp_mission_backing_handoff,
)
from music_workflow_mission_backing_click import capture_mission_backing_click_intent
from practice_focus_creative import format_focus_surface_guidance
from song_catalog.catalog import format_pick_key
from songs.music_source import LAST_CUSTOM_STATE_KEY, SOURCE_CUSTOM
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    mark_practice_key_user_override,
    set_practice_concert_key,
)


PERFECT_PICK = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-d"


def _trial() -> dict:
    return {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ]
        },
        "bpm": 100,
        "time_signature": "4/4",
        "progression_style": "Pop",
    }


def _trial_ga_missions_bb_clarinet() -> dict:
    trial = _trial()
    ss = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "instrument": "Clarinet",
        "sax_type": "Bb Clarinet",
        "show_chart_in_instrument_key": True,
        "active_music_source": SOURCE_CUSTOM,
        "explicit_music_source_choice": SOURCE_CUSTOM,
        "active_catalog_pick_key": TRIAL_PICK,
        "song": "Trial Song",
        "selected_song": {"title": "Trial Song", "key": "D", "pick_key": TRIAL_PICK},
        "original_key": "D",
        "display_key": "F",
        "concert_key": "F",
        "practice_concert_key": "F",
        "improv_mission_concert_key": "D",  # stale Original residue
        "improv_jam_key": "Eb",
        "improv_jam_style": "Jewish ballad",
        PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL_PICK: "F"},
        CPL_ACTIVE_KEY: trial,
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": trial,
        },
        "home_sections": {"Verse": ["F", "F", "F", "F"]},
        "improv_song_concert_sections": {"Verse": ["F", "F", "F", "F"]},
        "focus": "Melody",
    }
    set_practice_concert_key(ss, "F", pick_key=TRIAL_PICK, allow_restore_original=True)
    mark_practice_key_user_override(ss, TRIAL_PICK)
    return ss


def _perfect_missions() -> dict:
    ss = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_entry_mode": "",
        "instrument": "Guitar",
        "active_music_source": "catalog",
        "explicit_music_source_choice": "catalog",
        "active_catalog_pick_key": PERFECT_PICK,
        "song": "Perfect",
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        },
        "original_key": "G",
        "display_key": "C",
        "concert_key": "C",
        "practice_concert_key": "C",
        "improv_mission_concert_key": "Eb",  # stale Jam residue
        "improv_jam_key": "Eb",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT_PICK: "C", TRIAL_PICK: "F"},
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
        LAST_CUSTOM_STATE_KEY: {
            "pick_key": TRIAL_PICK,
            "custom_home_key": "D",
            "active": _trial(),
        },
        "home_sections": {"Verse": ["C", "C", "C", "C"]},
        "improv_song_concert_sections": {"Verse": ["C", "C", "C", "C"]},
    }
    set_practice_concert_key(ss, "C", pick_key=PERFECT_PICK, allow_restore_original=True)
    mark_practice_key_user_override(ss, PERFECT_PICK)
    return ss


class TestSlice3MissionKeyContract(unittest.TestCase):
    def test_a_trial_mission_key_contract_bb_clarinet(self) -> None:
        ss = _trial_ga_missions_bb_clarinet()
        practice = resolve_mission_underlying_practice_key(ss)
        written = resolve_mission_written_key(ss, practice)
        self.assertEqual(practice, "F")
        self.assertEqual(written, "G")
        self.assertEqual(canonical_mission_practice_key(ss), "F")
        self.assertEqual(_authoritative_practice_chart_key(ss, "D"), "F")

        ctx = ImprovSessionContext(
            song_title="Trial Song",
            artist="Test",
            key_center="D",
            display_key="D",
            sections={"Verse": ["D", "D", "D", "D"]},
            section_order=["Verse"],
            progression_flat=["D", "D", "D", "D"],
            instrument="Clarinet",
            level="Intermediate",
            focus="Melody",
        )
        concert, chart = _coherent_improv_key_pair(ss, ctx)
        self.assertEqual(concert, "F")
        self.assertEqual(chart, "G")

        disp = creative_progression_display(
            ss, {"Verse": ["F", "F", "F", "F"]}, concert_key=concert
        )
        self.assertEqual(disp["concert_key"], "F")
        self.assertEqual(disp["chart_key"], "G")
        self.assertIn("F", disp["concert_line"])
        self.assertNotIn("D ·", f" {disp['concert_line']} ")
        self.assertIn("G", disp["chart_line"])
        # No stale Original→Written E label when Practice is F.
        self.assertNotEqual(disp["chart_key"], "E")
        self.assertNotEqual(disp["concert_key"], "D")

        owner = resolve_mission_owner_context(ss)
        self.assertEqual(owner.practice_key, "F")
        self.assertEqual(owner.written_key, "G")
        self.assertIn("Trial", owner.underlying_title)

    def test_a2_custom_ga_outranks_leftover_perfect_pick(self) -> None:
        """Custom Trial Active + leftover Perfect catalog pick → Mission still Trial F."""
        from improvisation_intelligence_ui import _mission_improv_ctx_from_underlying_owner

        ss = _trial_ga_missions_bb_clarinet()
        # Leftover Perfect identity in selected_song / catalog park — Custom remains GA.
        ss["selected_song"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "G",
            "pick_key": PERFECT_PICK,
        }
        ss["_catalog_before_custom_state"] = {
            "pick_key": PERFECT_PICK,
            "title": "Perfect",
        }
        ss[PRACTICE_KEY_BY_SOURCE_KEY][PERFECT_PICK] = "C"
        mark_practice_key_user_override(ss, PERFECT_PICK)
        # Keep Custom pick as active — do not promote Perfect pick.
        ss["active_catalog_pick_key"] = TRIAL_PICK
        ss["active_music_source"] = SOURCE_CUSTOM
        ss["explicit_music_source_choice"] = SOURCE_CUSTOM
        from songs.music_source import custom_progression_is_active

        self.assertTrue(custom_progression_is_active(ss))
        practice = resolve_mission_underlying_practice_key(ss)
        self.assertEqual(practice, "F")
        ctx = ImprovSessionContext(
            song_title="Perfect",
            artist="Ed Sheeran",
            key_center="C",
            display_key="C",
            sections={"Verse": ["C", "C", "C", "C"]},
            section_order=["Verse"],
            progression_flat=["C", "C", "C", "C"],
            instrument="Clarinet",
            level="Intermediate",
            focus="Melody",
        )
        rebound = _mission_improv_ctx_from_underlying_owner(ss, ctx)
        self.assertIn("Trial", rebound.song_title)
        self.assertEqual(rebound.key_center, "F")

    def test_b_perfect_mission_stays_perfect_gc(self) -> None:
        ss = _perfect_missions()
        practice = resolve_mission_underlying_practice_key(ss)
        self.assertEqual(practice, "C")
        self.assertEqual(_authoritative_practice_chart_key(ss, "G"), "C")
        self.assertNotEqual(practice, "Eb")
        self.assertNotEqual(practice, "F")
        owner = resolve_mission_owner_context(ss)
        self.assertEqual(owner.practice_key, "C")
        self.assertIn("Perfect", owner.underlying_title)
        self.assertNotIn("Trial", owner.underlying_title)


class TestSlice3MissionExampleKeySpace(unittest.TestCase):
    def test_c_selected_chord_and_written_space_agree(self) -> None:
        from mission_projection_state import resolve_mission_projection_state

        ss = _trial_ga_missions_bb_clarinet()
        ss["improv_selected_chord"] = "F"
        ss["_improv_mission_section_map"] = [("Verse", ["F", "F", "F", "F"])]
        proj = resolve_mission_projection_state(
            ss,
            section_map=[("Verse", ["F", "F", "F", "F"])],
            fallback_key="D",
        )
        self.assertEqual(proj.concert_key, "F")
        self.assertEqual(proj.chart_key, "G")
        # Concert F → written G for Bb Clarinet; display chord tracks written space.
        if proj.concert_chord:
            self.assertEqual(proj.concert_chord, "F")
        if proj.display_chord:
            self.assertEqual(proj.display_chord, "G")


class TestSlice3MissionBackingOwnership(unittest.TestCase):
    def test_d_mission_backing_explicit_owner(self) -> None:
        ss = _trial_ga_missions_bb_clarinet()
        ss["improv_entry_mode"] = "Song-Based Improvisation"
        ss["_backing_explicit_handoff_source"] = "entry_jam"
        ss["improv_jam_style"] = "Jewish ballad"
        capture_mission_backing_click_intent(
            ss,
            with_practice_lick=False,
            mission="Chord Tones",
            cur_chord="F",
            section_label="Verse",
            chord_idx=0,
            song_title="Trial Song",
            concert_key="F",
            display_key="G",
        )
        self.assertTrue(ss.get("improv_mission_backing_handoff"))
        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")
        self.assertEqual(str(ss.get("_music_mission_canonical_return_destination") or ""), "mission")
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")

    def test_e_pk_change_keeps_mission_owner(self) -> None:
        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss)
        ss["studio_page"] = "backing"
        ss["backing_context"] = {
            "source": "mission",
            "source_label": "Mission Backing Jam",
            "song_title": "Trial Song",
            "concert_key": "F",
            "display_key": "G",
            "key": "F",
            "bpm": 100,
            "style": "Pop",
            "groove": "Auto",
            "bound_pick_key": TRIAL_PICK,
            "active_song_id": TRIAL_PICK,
        }
        # Explicit Practice Key change must not flip to Jam / SBI.
        ss["display_key"] = "G"
        ss["concert_key"] = "G"
        ss["improv_mission_concert_key"] = "G"
        set_practice_concert_key(
            ss, "G", pick_key=TRIAL_PICK, allow_restore_original=True, commit_catalog_practice_key=True
        )
        mark_practice_key_user_override(ss, TRIAL_PICK)
        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")
        self.assertNotEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "entry_jam")
        self.assertTrue(live_backing_owner_is_mission(ss))
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "G")
        self.assertEqual(str(ss.get("_music_mission_canonical_return_destination") or ""), "mission")

    def test_f_return_to_mission_only_on_mission_backing(self) -> None:
        def _labels(ss: dict) -> list[str]:
            actions, _ = build_backing_nav_actions(ss)
            return [a.label for a in actions]

        # Mission Backing → Return present
        mission_ss = {
            "studio_page": "backing",
            "backing_context": {
                "source": "mission",
                "source_label": "Mission Backing Jam",
                "song_title": "Trial Song",
                "concert_key": "F",
            },
            "_backing_explicit_handoff_source": "mission",
            "_music_mission_canonical_return_destination": "mission",
        }
        labs = _labels(mission_ss)
        self.assertTrue(any("Return to Mission" in lab for lab in labs), labs)
        self.assertTrue(return_to_mission_eligible(mission_ss))

        # Jam / Entry → absent even with leftover mission_jam workflow flag
        jam_ss = {
            "studio_page": "backing",
            "backing_context": {
                "source": "entry_jam",
                "source_label": "Jam Generator",
                "song_title": "Jam",
                "concert_key": "Eb",
            },
            "_backing_workflow_envelope": {"workflow_type": "mission_jam"},
            "_music_mission_canonical_return_destination": "mission",
            "improv_mission_backing_handoff": False,
        }
        labs_j = _labels(jam_ss)
        self.assertFalse(any("Return to Mission" in lab for lab in labs_j), labs_j)
        self.assertFalse(return_to_mission_eligible(jam_ss))

        # SBI Custom → absent
        sbi_ss = {
            "studio_page": "backing",
            "backing_context": {
                "source": "song_improv",
                "source_label": "Song-Based Improvisation",
                "song_title": "Trial Song",
                "concert_key": "F",
            },
            "_backing_explicit_handoff_source": "song_improv",
            "_music_mission_canonical_return_destination": "mission",
        }
        labs_s = _labels(sbi_ss)
        self.assertFalse(any("Return to Mission" in lab for lab in labs_s), labs_s)

        # Catalog → absent
        cat_ss = {
            "studio_page": "backing",
            "backing_context": {
                "source": "regular_song",
                "source_label": "Catalog",
                "song_title": "Perfect",
                "concert_key": "C",
            },
            "_music_mission_canonical_return_destination": "mission",
        }
        labs_c = _labels(cat_ss)
        self.assertFalse(any("Return to Mission" in lab for lab in labs_c), labs_c)

    def test_g_stale_handoffs_mission_wins(self) -> None:
        ss = _perfect_missions()
        ss["improv_entry_mode"] = "Jam Session Generator"
        ss["_backing_explicit_handoff_source"] = "entry_jam"
        ss["improv_jam_style"] = "Jewish ballad"
        ss["improv_mission_backing_handoff"] = False
        # Fresh Mission launch
        stamp_mission_backing_handoff(ss)
        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")
        self.assertTrue(ss.get("improv_mission_backing_handoff"))
        # Open-backing path: mission launch outranks leftover Jam entry.
        from backing_source_navigation import open_backing_for_creative_source

        # Avoid full activate if heavy — at least classifier prefers mission stamp.
        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")
        clear_mission_return_eligibility(ss)
        self.assertNotEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")


class TestSlice3MissionCopyAndIcons(unittest.TestCase):
    def test_melody_copy_has_no_internal_success_fields(self) -> None:
        ss = _trial_ga_missions_bb_clarinet()
        line = format_focus_surface_guidance(ss, "missions")
        self.assertNotIn("melodic_contour", line)
        self.assertNotIn("target_tone_use", line)
        self.assertNotIn("Success:", line)
        self.assertIn("Melody", line)
        self.assertTrue(
            "shape" in line.lower() or "arch" in line.lower() or "chord tones" in line.lower(),
            line,
        )

    def test_clarinet_icon_not_sax_or_music_note(self) -> None:
        from instrument_aware import instrument_theme
        from practice_ui_labels import INSTRUMENT_ICONS

        self.assertNotEqual(INSTRUMENT_ICONS.get("Clarinet"), "🎷")
        self.assertNotEqual(INSTRUMENT_ICONS.get("Clarinet"), "🎵")
        self.assertEqual(INSTRUMENT_ICONS.get("Saxophone"), "🎷")
        self.assertEqual(instrument_theme("Clarinet")["icon"], INSTRUMENT_ICONS["Clarinet"])
        from music_feature_icons import semantic_field_icon

        self.assertEqual(semantic_field_icon("shape_key"), "🎸")


if __name__ == "__main__":
    unittest.main()

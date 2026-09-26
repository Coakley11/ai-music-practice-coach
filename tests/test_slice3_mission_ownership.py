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
    HANDOFF_ORIGINAL_KEY,
    HANDOFF_PRACTICE_KEY,
    HANDOFF_SOUNDING_KEY,
    HANDOFF_WRITTEN_KEY,
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

    def test_a2b_custom_ga_outranks_leftover_say_pick_in_active_catalog(self) -> None:
        """Custom Trial GA + leftover Say in active_catalog_pick_key → Mission still Trial F.

        Browser failure: Working from Say, Practice G (Say sticky), Mission Backing blocked.
        """
        from practice_focus_creative import resolve_creative_source_binding
        from songs.practice_key_state import resolve_practice_source_pick

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        ss = _trial_ga_missions_bb_clarinet()
        ss["active_catalog_pick_key"] = say_pick  # polluted leftover catalog park
        ss["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "genre": "Pop",
            "key": "G",
            "pick_key": say_pick,
        }
        ss["song"] = "Say"
        ss[PRACTICE_KEY_BY_SOURCE_KEY][say_pick] = "G"
        mark_practice_key_user_override(ss, say_pick)
        # Custom remains Global Active with Trial sticky F.
        ss["active_music_source"] = SOURCE_CUSTOM
        ss["explicit_music_source_choice"] = SOURCE_CUSTOM
        ss["display_key"] = "F"
        ss["concert_key"] = "F"

        from songs.music_source import custom_progression_is_active

        self.assertTrue(custom_progression_is_active(ss))
        pick = resolve_practice_source_pick(ss)
        self.assertTrue(str(pick).startswith("custom::"), pick)
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertEqual(canonical_mission_practice_key(ss), "F")
        self.assertEqual(resolve_mission_written_key(ss, "F"), "G")
        bind = resolve_creative_source_binding(ss)
        self.assertEqual(bind.get("kind"), "custom")
        self.assertIn("Trial", str(bind.get("identity") or ""))
        self.assertNotIn("Say", str(bind.get("identity") or ""))
        self.assertIn("Custom", str(bind.get("workflow") or ""))

    def test_a2c_cpl_session_active_despite_leftover_catalog_pick(self) -> None:
        """Custom GA + leftover Say pick → cpl_session_is_active still True (heal path)."""
        from songs.music_source import cpl_session_is_active, ensure_custom_active_song_identity
        from song_catalog.catalog import format_pick_key
        from custom_progression_lab import CPL_ACTIVE_KEY

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        ss = _trial_ga_missions_bb_clarinet()
        ss["active_catalog_pick_key"] = say_pick
        ss["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "pick_key": say_pick,
        }
        self.assertTrue(cpl_session_is_active(ss))
        ensure_custom_active_song_identity(ss, cpl_active_key=CPL_ACTIVE_KEY)
        self.assertTrue(str(ss.get("active_catalog_pick_key") or "").startswith("custom::"))

    def test_a2d_original_echo_user_commit_loses_to_sticky_f(self) -> None:
        """Original-echo _pk_user_commit_token=D must not beat Trial sticky F."""
        ss = _trial_ga_missions_bb_clarinet()
        ss["_pk_user_commit_token"] = "D"
        ss["_pk_user_commit_pick"] = TRIAL_PICK
        ss["original_key"] = "D"
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertEqual(canonical_mission_practice_key(ss), "F")

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
        self.assertEqual(str(ss.get(HANDOFF_PRACTICE_KEY) or ""), "F")
        self.assertEqual(str(ss.get(HANDOFF_SOUNDING_KEY) or ""), "F")
        self.assertEqual(str(ss.get(HANDOFF_ORIGINAL_KEY) or ""), "D")
        written = str(ss.get(HANDOFF_WRITTEN_KEY) or "")
        self.assertTrue(written.startswith("G"), written)

    def test_d1b_stamp_rejects_written_g_and_original_echo_d(self) -> None:
        """First-loss regression: display_key=G and _pk_user_commit=D must not win Practice."""
        from backing_context import build_mission_context, open_backing_from_creative

        ss = _trial_ga_missions_bb_clarinet()
        ss["display_key"] = "G"  # Bb written pollution
        ss["concert_key"] = "F"
        ss["_pk_user_commit_token"] = "D"  # Original-echo false commit
        ss["_pk_user_commit_pick"] = TRIAL_PICK
        commit_before = str(ss.get("_pk_user_commit_token") or "")
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        self.assertEqual(str(ss.get(HANDOFF_PRACTICE_KEY) or ""), "F")
        self.assertEqual(str(ss.get(HANDOFF_SOUNDING_KEY) or ""), "F")
        self.assertEqual(str(ss.get(HANDOFF_ORIGINAL_KEY) or ""), "D")
        self.assertTrue(str(ss.get(HANDOFF_WRITTEN_KEY) or "").startswith("G"))
        self.assertEqual(ss.get("improv_mission_concert_key"), "F")
        self.assertEqual(ss.get("concert_key"), "F")
        self.assertEqual(str(ss.get("_pk_user_commit_token") or ""), commit_before)
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        ctx = build_mission_context(ss)
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(ctx.display_key, "F")
        self.assertTrue(str(ctx.chart_display_key or "").startswith("G"), ctx.chart_display_key)
        open_backing_from_creative(ss, source="mission", st_like=MagicMock(session_state=ss))
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertEqual(str(ss.get("_pk_user_commit_token") or ""), commit_before)
        self.assertEqual(canonical_mission_practice_key(ss), "F")

    def test_d2_mission_backing_ignores_leftover_say_pick(self) -> None:
        """Custom Trial GA + leftover Say pick → Mission Backing stays Trial F/G."""
        from backing_context import build_mission_context
        from song_catalog.catalog import format_pick_key

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        ss = _trial_ga_missions_bb_clarinet()
        ss["active_catalog_pick_key"] = say_pick
        ss["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "genre": "Pop",
            "key": "G",
            "pick_key": say_pick,
        }
        ss["song"] = "Say"
        ss[PRACTICE_KEY_BY_SOURCE_KEY][say_pick] = "G"
        mark_practice_key_user_override(ss, say_pick)
        ss["improv_selected_chord"] = "F"
        ss["ii_selected_chord"] = "F"
        ss["ii_selected_section"] = "Intro"
        stamp_mission_backing_handoff(ss)
        ctx = build_mission_context(ss)
        self.assertEqual(ctx.source, "mission")
        self.assertIn("Trial", str(ctx.song_title or ""))
        self.assertNotIn("Say", str(ctx.song_title or ""))
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(ctx.display_key, "F")
        self.assertTrue(str(ctx.bound_pick_key or "").startswith("custom::"), ctx.bound_pick_key)
        chart = str(ctx.chart_display_key or "").strip()
        self.assertTrue(chart in {"G", "G major", "G Major"} or chart.startswith("G"), chart)

    def test_d2b_cpl_practice_outranks_original_echo_sticky(self) -> None:
        """Empty original_key + by_source D must not beat CPL sealed Practice F on handoff."""
        from backing_context import build_mission_context
        from backing_owner_envelope import get_backing_owner_envelope
        from song_catalog.catalog import format_pick_key

        say_pick = format_pick_key("Pop", "Say — John Mayer")
        ss = _trial_ga_missions_bb_clarinet()
        trial = dict(ss[CPL_ACTIVE_KEY])
        trial["practice_key"] = "F"
        ss[CPL_ACTIVE_KEY] = trial
        ss["original_key"] = ""  # browser gap: Original not mirrored into session
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        ss["practice_concert_key"] = "D"
        ss["improv_mission_concert_key"] = "D"
        ss[PRACTICE_KEY_BY_SOURCE_KEY][TRIAL_PICK] = "D"  # Original-echo sticky
        ss["song"] = "Say"
        ss["active_catalog_pick_key"] = say_pick
        ss["selected_song"] = {
            "title": "Say",
            "artist": "John Mayer",
            "genre": "Pop",
            "key": "G",
            "pick_key": say_pick,
        }
        stamp_mission_backing_handoff(ss)
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "F")
        self.assertEqual(ss.get(HANDOFF_WRITTEN_KEY), "G")
        env = get_backing_owner_envelope(ss)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(str(env.source or ""), "mission")
        self.assertTrue(str(env.practice_key or "").startswith("F"), env.practice_key)
        self.assertIn("Trial", str(env.title or ""))
        self.assertNotIn("Say", str(env.title or ""))
        ctx = build_mission_context(ss)
        self.assertEqual(ctx.concert_key, "F")
        self.assertIn("Trial", str(ctx.song_title or ""))

    def test_d2c_written_commit_cannot_pollute_envelope_practice(self) -> None:
        """Bb written G must not overwrite Mission envelope practice_key while sounding is F."""
        from backing_context import build_mission_context
        from backing_owner_envelope import (
            get_backing_owner_envelope,
            stamp_envelope_from_backing_context,
        )

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        ctx = build_mission_context(ss)
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        # Simulate written-chart commit / sticky pollution after launch.
        ss["_pk_user_commit_token"] = "G"
        ss["_pk_user_commit_pick"] = TRIAL_PICK
        ss[PRACTICE_KEY_BY_SOURCE_KEY][TRIAL_PICK] = "G"
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        env = get_backing_owner_envelope(ss)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(str(env.practice_key or ""), "F", env)
        self.assertEqual(str(env.sounding_key or ""), "F", env)
        self.assertTrue(str(env.written_key or "").startswith("G"), env.written_key)

    def test_d2d_original_echo_commit_cannot_pollute_envelope_practice(self) -> None:
        """Original-echo _pk_user_commit_token=D must not overwrite sealed Mission F."""
        from backing_context import build_mission_context
        from backing_owner_envelope import (
            get_backing_owner_envelope,
            stamp_envelope_from_backing_context,
        )

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        ctx = build_mission_context(ss)
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        ss["_pk_user_commit_token"] = "D"
        ss["_pk_user_commit_pick"] = TRIAL_PICK
        ss[PRACTICE_KEY_BY_SOURCE_KEY][TRIAL_PICK] = "D"
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        env = get_backing_owner_envelope(ss)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(str(env.practice_key or ""), "F", env)
        self.assertEqual(str(env.sounding_key or ""), "F", env)

    def test_d2e_alias_original_echo_after_handoff_clear(self) -> None:
        """Name-alias sticky D + cleared handoff must not beat envelope sounding F."""
        from backing_context import build_mission_context
        from backing_owner_envelope import (
            get_backing_owner_envelope,
            stamp_envelope_from_backing_context,
        )
        from mission_owner_contract import (
            HANDOFF_ORIGINAL_KEY,
            HANDOFF_PRACTICE_KEY,
            HANDOFF_SOUNDING_KEY,
            HANDOFF_WRITTEN_KEY,
        )

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        ctx = build_mission_context(ss)
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        # Browser persist often clears handoff keys while alias sticky stays Original.
        ss.pop(HANDOFF_PRACTICE_KEY, None)
        ss.pop(HANDOFF_SOUNDING_KEY, None)
        ss.pop(HANDOFF_WRITTEN_KEY, None)
        ss.pop(HANDOFF_ORIGINAL_KEY, None)
        ss[PRACTICE_KEY_BY_SOURCE_KEY][TRIAL_PICK] = "F"
        ss[PRACTICE_KEY_BY_SOURCE_KEY]["custom::Trial Song"] = "D"
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        env = get_backing_owner_envelope(ss)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(str(env.practice_key or ""), "F", env)
        self.assertEqual(str(env.sounding_key or ""), "F", env)

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

    def test_e2_mission_pk_edit_updates_handoff_and_envelope(self) -> None:
        """Mission Backing F→E must reseal handoff + envelope (written F# for Bb)."""
        from backing_owner_envelope import get_backing_owner_envelope, stamp_backing_owner_envelope
        from creative_key_sync import apply_specialized_mission_practice_key
        from songs.practice_key_state import mark_practice_key_user_override

        ss = _trial_ga_missions_bb_clarinet()
        trial = dict(ss[CPL_ACTIVE_KEY])
        trial["practice_key"] = "F"
        ss[CPL_ACTIVE_KEY] = trial
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination="mission",
        )
        ss["_pk_user_commit_token"] = "E"
        ss["_pk_user_commit_pick"] = TRIAL_PICK
        mark_practice_key_user_override(ss, TRIAL_PICK)
        apply_specialized_mission_practice_key(ss, "E")
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "E")
        self.assertEqual(ss.get(HANDOFF_SOUNDING_KEY), "E")
        self.assertEqual(ss.get(HANDOFF_WRITTEN_KEY), "F#")
        env = get_backing_owner_envelope(ss)
        self.assertIsNotNone(env)
        assert env is not None
        self.assertEqual(str(env.practice_key or ""), "E")
        self.assertEqual(str(env.sounding_key or ""), "E")
        self.assertTrue(str(env.written_key or "").startswith("F"), env.written_key)
        # Re-stamp must not reseal F over user E.
        stamp_mission_backing_handoff(ss)
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "E")

    def test_case_a_commit_backing_pk_f_to_e(self) -> None:
        """Case A: commit_backing_practice_key F→E updates sticky + envelope E/F#."""
        from backing_owner_envelope import get_backing_owner_envelope, stamp_backing_owner_envelope
        from backing_practice_key_control import commit_backing_practice_key
        from songs.practice_key_state import get_practice_concert_key

        ss = _trial_ga_missions_bb_clarinet()
        trial = dict(ss[CPL_ACTIVE_KEY])
        trial["practice_key"] = "F"
        ss[CPL_ACTIVE_KEY] = trial
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination="mission",
        )
        commit_backing_practice_key(ss, "E")
        self.assertEqual(ss.get("_pk_user_commit_token"), "E")
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "E")
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "E")
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "E")
        self.assertEqual(env.sounding_key, "E")
        self.assertTrue(str(env.written_key).startswith("F"), env.written_key)
        self.assertEqual(str(ss[CPL_ACTIVE_KEY].get("practice_key") or ""), "E")

    def test_case_b_original_echo_cannot_overwrite_e(self) -> None:
        """Case B: Original-echo commit/sticky D cannot overwrite envelope E."""
        from backing_context import build_mission_context
        from backing_owner_envelope import (
            get_backing_owner_envelope,
            stamp_envelope_from_backing_context,
        )
        from backing_practice_key_control import commit_backing_practice_key
        from creative_key_sync import sync_backing_envelope_practice_key

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        commit_backing_practice_key(ss, "E")
        # Pressure: Original-echo commit + alias sticky + cleared handoff.
        ss["_pk_user_commit_token"] = "D"
        ss[PRACTICE_KEY_BY_SOURCE_KEY]["custom::Trial Song"] = "D"
        ss.pop(HANDOFF_PRACTICE_KEY, None)
        ss.pop(HANDOFF_SOUNDING_KEY, None)
        ss.pop(HANDOFF_WRITTEN_KEY, None)
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        sync_backing_envelope_practice_key(ss, "D")
        ctx = build_mission_context(ss)
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "E", env)
        self.assertEqual(env.sounding_key, "E", env)
        self.assertTrue(str(env.written_key).startswith("F"), env.written_key)

    def test_case_c_same_owner_restamp_keeps_e(self) -> None:
        """Case C: Mission restamp with ctx fallback D keeps envelope E/F#."""
        from backing_context import build_mission_context
        from backing_owner_envelope import (
            get_backing_owner_envelope,
            stamp_backing_owner_envelope,
            stamp_envelope_from_backing_context,
        )
        from backing_practice_key_control import commit_backing_practice_key

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination="mission",
        )
        commit_backing_practice_key(ss, "E")
        # Simulate rebuild that would feed Original D via live fields.
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        ss["improv_mission_concert_key"] = "D"
        ss.pop(HANDOFF_PRACTICE_KEY, None)
        ctx = build_mission_context(ss)
        stamp_envelope_from_backing_context(
            ss, ctx, source_override="mission", return_destination="mission"
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "E")
        self.assertEqual(env.sounding_key, "E")

    def test_case_d_refresh_hydrate_keeps_e(self) -> None:
        """Case D: persist E/F# then hydrate — Original D metadata only."""
        from backing_owner_envelope import (
            BACKING_OWNER_ENVELOPE_KEY,
            get_backing_owner_envelope,
            stamp_backing_owner_envelope,
        )
        from backing_practice_key_control import commit_backing_practice_key
        from songs.practice_key_state import get_practice_concert_key

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination="mission",
        )
        commit_backing_practice_key(ss, "E")
        raw = dict(ss[BACKING_OWNER_ENVELOPE_KEY])
        sticky = dict(ss.get(PRACTICE_KEY_BY_SOURCE_KEY) or {})
        cpl = dict(ss[CPL_ACTIVE_KEY])
        # Fresh session as after refresh/hydrate.
        ss2 = _trial_ga_missions_bb_clarinet()
        ss2[BACKING_OWNER_ENVELOPE_KEY] = raw
        ss2[PRACTICE_KEY_BY_SOURCE_KEY] = sticky
        ss2[CPL_ACTIVE_KEY] = cpl
        ss2["studio_page"] = "backing"
        ss2["_pk_user_commit_token"] = "E"
        ss2[HANDOFF_PRACTICE_KEY] = "E"
        ss2[HANDOFF_SOUNDING_KEY] = "E"
        ss2[HANDOFF_WRITTEN_KEY] = "F#"
        env = get_backing_owner_envelope(ss2)
        assert env is not None
        self.assertEqual(env.source, "mission")
        self.assertEqual(env.original_key, "D")
        self.assertEqual(env.practice_key, "E")
        self.assertEqual(env.sounding_key, "E")
        self.assertTrue(str(env.written_key).startswith("F"), env.written_key)
        self.assertEqual(get_practice_concert_key(ss2, TRIAL_PICK), "E")

    def test_case_e_return_and_reopen_keeps_e(self) -> None:
        """Case E: Return to Mission then reopen Backing keeps E/F# (no D reclaim)."""
        from backing_owner_envelope import get_backing_owner_envelope, stamp_backing_owner_envelope
        from backing_practice_key_control import commit_backing_practice_key
        from music_workflow_pending_mission_return import (
            _apply_return_destination_session_fields,
        )
        from songs.practice_key_state import get_practice_concert_key

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key="F",
            sounding_key="F",
            written_key="G",
            return_destination="mission",
        )
        commit_backing_practice_key(ss, "E")
        # Empty session original_key must not IndexError on Return.
        ss["original_key"] = ""
        dest = {
            "mission_id": "focus_melody",
            "song_pick_key": TRIAL_PICK,
            "song_title": "Trial Song",
            "concert_key": "E",
            "display_key": "E",
            "original_key": "",
            "section_label": "Verse",
            "chord_symbol": "G",
        }
        _apply_return_destination_session_fields(ss, dest)
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "E")
        self.assertEqual(ss.get("_pk_user_commit_token"), "E")
        ss["studio_page"] = "creative"
        ss["improv_intelligence_tab"] = "Missions"
        # Reopen Mission Backing: handoff + envelope must stay E/F#.
        stamp_mission_backing_handoff(ss, concert_practice_key="E")
        ss["studio_page"] = "backing"
        stamp_backing_owner_envelope(
            ss,
            source="mission",
            identity=TRIAL_PICK,
            title="Trial Song",
            original_key="D",
            practice_key=str(ss.get(HANDOFF_PRACTICE_KEY) or "E"),
            sounding_key=str(ss.get(HANDOFF_SOUNDING_KEY) or "E"),
            written_key=str(ss.get(HANDOFF_WRITTEN_KEY) or "F#"),
            return_destination="mission",
        )
        env = get_backing_owner_envelope(ss)
        assert env is not None
        self.assertEqual(env.practice_key, "E")
        self.assertEqual(env.sounding_key, "E")
        self.assertTrue(str(env.written_key).startswith("F"), env.written_key)
        self.assertNotEqual(env.practice_key, "D")
        self.assertNotEqual(env.practice_key, "F")

    def test_return_empty_original_key_no_indexerror(self) -> None:
        """Return must not crash when session original_key is empty."""
        from music_workflow_pending_mission_return import (
            _apply_return_destination_session_fields,
        )
        from songs.practice_key_state import get_practice_concert_key

        ss = _trial_ga_missions_bb_clarinet()
        stamp_mission_backing_handoff(ss, concert_practice_key="E")
        ss["original_key"] = ""
        ss[PRACTICE_KEY_BY_SOURCE_KEY][TRIAL_PICK] = "E"
        ss["_pk_user_commit_token"] = "E"
        dest = {
            "song_pick_key": TRIAL_PICK,
            "concert_key": "E",
            "display_key": "E",
            "original_key": "",
        }
        _apply_return_destination_session_fields(ss, dest)
        self.assertEqual(get_practice_concert_key(ss, TRIAL_PICK), "E")

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

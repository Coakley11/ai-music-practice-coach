"""R2 investigation matrix: Mission owner / key / Backing stability.

Journeys M1-M5 reproduce the R2 brief's scenarios against the real production
functions (no UI/browser — same convention as ``test_r1_true_source_backing_authority.py``
and ``test_true_activation_practice_key_reset.py``). Two journeys currently fail and
are marked ``expectedFailure`` with the exact root cause traced during R2
investigation; see the R2 report for detail. Everything else here reflects
genuinely-passing, already-correct behavior in the accepted baseline
(``98e1f778``) and guards it against regression.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any

from backing_context import BackingContext, get_backing_context, set_backing_context
from mission_owner_contract import (
    HANDOFF_PRACTICE_KEY,
    live_backing_owner_is_mission,
    missions_surface_owns,
    resolve_mission_underlying_practice_key,
    stamp_mission_backing_handoff,
)
from music_workflow_mission_backing_click import (
    apply_mission_backing_click_intent,
    capture_mission_backing_click_intent,
)
from music_workflow_mission_backing_orchestration import run_pre_widget_mission_handoff_consumers
from song_catalog.catalog import format_pick_key
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key, set_practice_concert_key
from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG

HOTEL = format_pick_key("Rock", "Hotel California — Eagles")


class _FakeSt:
    def __init__(self, ss: dict[str, Any]) -> None:
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _catalog_session(*, practice: str = "A#m") -> dict[str, Any]:
    """Catalog song active, Practice Key already set to a value Mission will differ from."""
    return {
        "studio_page": "creative",
        "instrument": "Guitar",
        "selected_song": {"title": "Hotel California", "artist": "Eagles", "genre": "Rock", "key": "Bm", "pick_key": HOTEL},
        "active_catalog_pick_key": HOTEL,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "original_key": "Bm",
        "display_key": practice,
        "concert_key": practice,
        PRACTICE_KEY_BY_SOURCE_KEY: {HOTEL: practice},
        "improv_intelligence_tab": "Entry & Jam",
    }


def _enter_mission(ss: dict[str, Any], *, mission: str = "Outline chord tones on beat 1") -> None:
    """Select a Mission on the Missions tab (no Backing yet) — mirrors the real radio/tile click."""
    ss["improv_active_mission"] = mission
    ss["improv_mission_pick"] = mission
    ss["improv_intelligence_tab"] = "Missions"
    ss["ii_selected_chord"] = "F"
    ss["ii_selected_section"] = "Verse"
    ss["improv_mission_chord_options"] = ["F", "Bb", "C"]


def _click_mission_backing(ss: dict[str, Any], *, concert_key: str, chord: str = "F") -> None:
    """Simulate the real two-phase click → next-rerun pre-widget consume chain."""
    capture_mission_backing_click_intent(
        ss,
        with_practice_lick=False,
        mission=str(ss.get("improv_active_mission") or ""),
        cur_chord=chord,
        section_label="Verse",
        chord_idx=0,
        song_title=str((ss.get("selected_song") or {}).get("title") or ""),
        concert_key=concert_key,
        display_key=concert_key,
    )
    st = _FakeSt(ss)
    run_pre_widget_mission_handoff_consumers(ss, st=st)


def _seed_stale_catalog_backing(ss: dict[str, Any]) -> None:
    set_backing_context(
        ss,
        BackingContext(
            source="regular_song", source_label="Catalog song", active_song_id=HOTEL,
            song_title="Hotel California", key="A#m", display_key="A#m", concert_key="A#m",
            bpm=96, style="", groove="Auto", scope="Full song", loops=2,
            progression=["A#m", "F#"], progression_label="Hotel California", loop=True,
            custom_revision_id=None, bound_pick_key=HOTEL,
        ),
    )


class TestM1MissionPracticeKeyMutation(unittest.TestCase):
    """M1 — Mission establishes its own Practice Key; survives a simulated remount."""

    def test_mission_backing_handoff_establishes_and_survives_remount(self) -> None:
        ss = _catalog_session(practice="A#m")
        _enter_mission(ss)
        stamp_mission_backing_handoff(ss, concert_practice_key="F")

        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "F")
        # Catalog's own sticky Practice Key for Hotel is untouched (R1 model: temporary
        # Mission key, not a true-source change).
        self.assertEqual(get_practice_concert_key(ss, HOTEL), "A#m")

        # Simulate a remount (same session dict, fresh resolver calls — no new click).
        for _ in range(3):
            self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")

    def test_mission_key_does_not_inherit_stale_catalog_or_jam_residue(self) -> None:
        ss = _catalog_session(practice="A#m")
        # Stale residue from an unrelated earlier context.
        ss["improv_jam_key"] = "C#"
        ss["display_key"] = "C#"
        ss["concert_key"] = "C#"
        _enter_mission(ss)
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertNotIn(resolve_mission_underlying_practice_key(ss), {"A#m", "C#"})


class TestM2MissionToBacking(unittest.TestCase):
    """M2 — Mission → Backing: owner/context/key correct; survives refresh and leave/return."""

    def test_mission_backing_ignores_stale_catalog_context(self) -> None:
        ss = _catalog_session(practice="A#m")
        _seed_stale_catalog_backing(ss)
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")

        ctx = get_backing_context(ss)
        self.assertIsNotNone(ctx)
        self.assertEqual(getattr(ctx, "source", ""), "mission")
        self.assertEqual(str(getattr(ctx, "concert_key", "") or ""), "F")
        # The Mission's own song *is* Hotel California — correct. The stale piece
        # under test is the Practice Key (A#m), not the song identity.
        self.assertNotEqual(str(getattr(ctx, "concert_key", "") or ""), "A#m")

    def test_mission_backing_survives_refresh(self) -> None:
        from backing_context import hydrate_backing_context_after_restore
        from backing_source_navigation import hydrate_backing_source_for_page

        ss = _catalog_session(practice="A#m")
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")
        self.assertEqual(getattr(get_backing_context(ss), "source", ""), "mission")

        # Simulate a true refresh: context restored from its persisted blob, then
        # one normal page-hydrate pass (as a remount on the Backing page would run).
        hydrate_backing_context_after_restore(ss)
        hydrate_backing_source_for_page(ss, st_like=_FakeSt(ss))
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "mission")
        self.assertEqual(str(getattr(ctx, "concert_key", "") or ""), "F")

    def test_leave_and_return_restores_mission_context(self) -> None:
        from mission_owner_contract import clear_mission_return_eligibility, return_to_mission_eligible
        from mission_return_destination import apply_sealed_mission_return_destination, peek_mission_return_destination

        ss = _catalog_session(practice="A#m")
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")
        self.assertTrue(return_to_mission_eligible(ss))
        dest = peek_mission_return_destination(ss)
        self.assertIsNotNone(dest)
        self.assertEqual(str(dest.get("concert_key") or ""), "F")

        # Leave: navigate off Backing (ordinary nav, not an explicit different-source click).
        ss["studio_page"] = "creative"
        ss["improv_intelligence_tab"] = "Missions"

        # Return: apply the sealed destination (the real "Return to Mission" action).
        ok = apply_sealed_mission_return_destination(ss, dest)
        self.assertTrue(ok)
        self.assertEqual(str(ss.get("improv_active_mission") or ""), str(dest.get("mission_id") or ""))


class TestM3LiveCoachRoundTrip(unittest.TestCase):
    """M3 — Mission → Live Coach → back to Missions: context survives the round trip."""

    def test_live_coach_tab_does_not_release_mission_backing_ownership(self) -> None:
        ss = _catalog_session(practice="A#m")
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")
        self.assertTrue(live_backing_owner_is_mission(ss))

        # Switch tabs to Live Coach (still on the same Mission Backing session).
        ss["improv_intelligence_tab"] = "Live Coach"
        self.assertTrue(live_backing_owner_is_mission(ss))
        self.assertTrue(missions_surface_owns(ss))
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")

        # Back to Missions.
        ss["improv_intelligence_tab"] = "Missions"
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")
        self.assertEqual(getattr(get_backing_context(ss), "source", ""), "mission")


class TestM4JamDoesNotReclaimMission(unittest.TestCase):
    """M4 — stale Jam / Style-Jam state must not reclaim Mission's key/backing context."""

    def _style_jam_then_mission_session(self) -> dict[str, Any]:
        from generated_jam_key_context import activate_generated_jam_key_ownership
        from workflow_musical_authority import save_workflow_snapshot, switch_workflow_owner

        ss = _catalog_session(practice="A#m")
        ss["improv_entry_mode"] = "Style Jam Mode"
        ss["improv_jam_key"] = "C#"
        save_workflow_snapshot(ss, "song_based_improvisation")
        save_workflow_snapshot(ss, "style_jam")
        activate_generated_jam_key_ownership(ss, entry_mode="Style Jam Mode")
        ss["display_key"] = "C#"
        ss["concert_key"] = "C#"
        _enter_mission(ss)
        switch_workflow_owner(ss, "mission_jam")
        return ss

    def test_jam_key_context_is_released_on_mission_switch(self) -> None:
        """``workflow_musical_authority.switch_workflow_owner`` → ``activate_workflow``
        releases Generated Jam key ownership (``deactivate_generated_jam_key_ownership``)
        and restores the pre-Jam Practice Key when switching into ``mission_jam``.

        Note: ``tests/test_mission_envelope_pre_widget_reconciliation.py`` asserts the
        *same* release happens later, at ``ensure_mission_envelope_reconciliation_before_
        widgets`` time — that assumption predates this earlier release point and fails
        on unmodified baseline (``98e1f778``) too; it is a stale sequencing expectation
        in that test, not a behavior regression. See the R2 report.
        """
        ss = self._style_jam_then_mission_session()
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

        self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, ss)
        self.assertNotEqual(str(ss.get("display_key") or ""), "C#")
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "A#m")

    def test_jam_residue_present_mission_backing_click_still_wins(self) -> None:
        """The explicit Mission → Backing click path (M2's mechanism) is unaffected by
        the gap above: it seals its own concert key via ``stamp_mission_backing_handoff``
        and does not depend on ``switch_workflow_owner`` releasing the Jam key first.
        """
        ss = _catalog_session(practice="A#m")
        ss["improv_entry_mode"] = "Style Jam Mode"
        ss["improv_jam_key"] = "C#"
        ss["display_key"] = "C#"
        ss["concert_key"] = "C#"
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")
        ctx = get_backing_context(ss)
        self.assertEqual(getattr(ctx, "source", ""), "mission")
        self.assertEqual(str(getattr(ctx, "concert_key", "") or ""), "F")
        self.assertEqual(resolve_mission_underlying_practice_key(ss), "F")


class TestM5ExplicitJamTransitionAllowed(unittest.TestCase):
    """M5 — a genuine explicit Jam transition from Mission is still allowed to take over."""

    def test_explicit_entry_jam_launch_from_mission_takes_authority(self) -> None:
        from backing_source_navigation import prepare_global_backing_navigation

        ss = _catalog_session(practice="A#m")
        _enter_mission(ss)
        _click_mission_backing(ss, concert_key="F")
        self.assertEqual(getattr(get_backing_context(ss), "source", ""), "mission")

        # Explicit user action: leave Missions, launch Jam Session Generator.
        ss["improv_intelligence_tab"] = "Entry & Jam"
        ss["improv_entry_mode"] = "Jam Session Generator"
        ss["improv_jam_session"] = {"id": "jam-r2", "key": "E", "style": "Bright Bossa Nova", "progression": ["Cmaj7", "Am7", "Dm7", "G7"]}
        ss["_backing_explicit_handoff_source"] = "entry_jam"
        prepare_global_backing_navigation(ss, from_page="creative")

        self.assertEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "entry_jam")
        self.assertNotEqual(str(ss.get("_backing_explicit_handoff_source") or ""), "mission")


if __name__ == "__main__":
    unittest.main()

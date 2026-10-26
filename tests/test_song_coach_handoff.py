"""Song-Aware Coaching S7 — the Song-Based Improvisation handoff and the shared navigation helper (pure)."""

from __future__ import annotations

import dataclasses
import json
import unittest
from unittest import mock

from song_coach_plan import FOCUS_MOTIF
from song_coach_state import (
    HANDOFF_STALE,
    HANDOFF_VALID,
    SONG_COACH_STATE_KEY,
    CoachState,
    build_plan_for,
    handoff_record,
    handoff_status,
    parse_state,
    reconcile,
    with_built_plan,
    with_check,
    with_handoff,
    with_stage,
)
from tests.test_song_coach_examples import _scope

SAVE_REQUESTS: list[str] = []
_SAVE_PATCH = None


def setUpModule() -> None:
    global _SAVE_PATCH
    _SAVE_PATCH = mock.patch(
        "creative_context_snapshot_persistence.request_context_cloud_save",
        side_effect=lambda session, *, save_reason: SAVE_REQUESTS.append(save_reason) or True,
    )
    _SAVE_PATCH.start()


def tearDownModule() -> None:
    if _SAVE_PATCH is not None:
        _SAVE_PATCH.stop()


def _lesson():
    ctx, _ = _scope("perfect")
    ctx = dataclasses.replace(ctx, instrument="Saxophone")
    rec = reconcile({}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
    plan, scope = build_plan_for(ctx, rec.state.draft)
    state = with_check(with_stage(with_built_plan(rec.state, plan), 2, len(plan.challenges)), 2, 0, True)
    return ctx, plan, scope, state


class TestHandoffRecord(unittest.TestCase):
    def test_the_record_says_where_the_musician_was_and_nothing_more(self) -> None:
        ctx, plan, scope, state = _lesson()
        h = handoff_record(state, ctx, scope, at="2026-10-16T10:00:00+00:00")
        self.assertEqual(h["identity"], ctx.identity)
        self.assertEqual((h["fingerprint"], h["concert_key"], h["instrument"]), (ctx.fingerprint, ctx.concert_key, "Saxophone"))
        self.assertEqual((h["section_id"], h["start_bar"], h["end_bar"]), (state.built.section_id, state.built.start_bar, state.built.end_bar))
        self.assertEqual((h["plan_id"], h["source_kind"]), (plan.plan_id, ctx.source_kind))
        self.assertNotIn("challenges", json.dumps(h), "the plan itself is never stored")
        with_h = with_handoff(state, h)
        self.assertEqual((with_h.stage, with_h.checks, with_h.plan_id), (state.stage, state.checks, state.plan_id))
        parsed, status = parse_state(json.loads(json.dumps(with_h.to_dict())))
        self.assertEqual((parsed, status), (with_h, ""))

    def test_damaged_handoffs_are_dropped_not_trusted(self) -> None:
        ctx, _plan, scope, state = _lesson()
        good = with_handoff(state, handoff_record(state, ctx, scope, at="t")).to_dict()
        for bad in ("x", {"identity": ""}, {**good["handoff"], "start_bar": "two"}, {**good["handoff"], "end_bar": 0}):
            parsed, status = parse_state({**good, "handoff": bad})
            with self.subTest(bad=str(bad)[:40]):
                self.assertEqual(status, "repaired")
                self.assertEqual(parsed.handoff, {})
                self.assertEqual(parsed.plan_id, state.plan_id, "the lesson is kept")

    def test_validity_follows_song_chart_key_and_plan_but_not_instrument(self) -> None:
        ctx, _plan, scope, state = _lesson()
        st = with_handoff(state, handoff_record(state, ctx, scope, at="t"))
        self.assertEqual(handoff_status(st, ctx), HANDOFF_VALID)
        self.assertEqual(handoff_status(st, dataclasses.replace(ctx, instrument="Piano")), HANDOFF_VALID)
        for changed in (dataclasses.replace(ctx, identity="catalog|Other"), dataclasses.replace(ctx, fingerprint="edited"),
                        dataclasses.replace(ctx, concert_key="A")):
            self.assertEqual(handoff_status(st, changed), HANDOFF_STALE)
        self.assertEqual(handoff_status(dataclasses.replace(st, plan_id="other"), ctx), HANDOFF_STALE)
        self.assertEqual(handoff_status(state, ctx), "")

    def test_a_new_plan_or_an_invalidation_drops_the_handoff(self) -> None:
        ctx, plan, scope, state = _lesson()
        st = with_handoff(state, handoff_record(state, ctx, scope, at="t"))
        self.assertEqual(with_built_plan(st, plan).handoff, {})
        rec = reconcile({SONG_COACH_STATE_KEY: st.to_dict()}, dataclasses.replace(ctx, fingerprint="edited"),
                        level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.state.handoff, {})


# --------------------------------------------------------------------------- the shared helper


def _creative_session(**extra) -> dict:
    return {"studio_page": "creative", "improv_intelligence_tab": "Song-Aware Coaching",
            "creative_improv_intelligence_tab": "Song-Aware Coaching", "improv_entry_mode": "Style Jam Mode",
            "_history_live_creative_dest": "creative::Song-Aware Coaching", "concert_key": "G", "display_key": "G",
            "instrument": "Saxophone", "active_music_source": "catalog_song", **extra}


class TestNavigationHelper(unittest.TestCase):
    def test_outside_creative_nothing_changes(self) -> None:
        from creative_sbi_navigation import request_song_based_improvisation

        session = {"studio_page": "practice", "improv_intelligence_tab": "Missions"}
        self.assertFalse(request_song_based_improvisation(session, "test"))
        self.assertEqual(session, {"studio_page": "practice", "improv_intelligence_tab": "Missions"})

    def test_one_step_to_song_based_with_one_back_entry(self) -> None:
        from creative_sbi_navigation import request_song_based_improvisation
        from studio_nav_history import NAV_BACK_STACK, history_destination_id

        session = _creative_session(_pending_improv_intelligence_tab="Missions", _pending_improv_entry_mode="Style Jam Mode")
        self.assertTrue(request_song_based_improvisation(session, "test"))
        self.assertEqual((session["improv_intelligence_tab"], session["creative_improv_intelligence_tab"],
                          session["improv_entry_mode"]), ("Entry & Jam", "Entry & Jam", "Song-Based Improvisation"))
        self.assertTrue(session.get("_improv_tab_user_touched"))
        self.assertNotIn("_pending_improv_intelligence_tab", session, "an older queued tab can't win")
        self.assertNotIn("_pending_improv_entry_mode", session)
        back = [history_destination_id(entry=e) for e in session.get(NAV_BACK_STACK) or []]
        self.assertEqual(back, ["creative::Song-Aware Coaching"])
        self.assertEqual(session["_history_live_creative_dest"], "creative::SBI")
        self.assertEqual(session.get("backing_track_scope"), "Full song", "the Song-Based entry defaults apply")
        for key, value in (("concert_key", "G"), ("display_key", "G"), ("instrument", "Saxophone"),
                           ("active_music_source", "catalog_song")):
            self.assertEqual(session[key], value)
        self.assertNotIn("_backing_play_request", session)
        self.assertNotEqual(session.get("backing_transport_status"), "playing")

    def test_an_explicit_request_outranks_a_back_restore_seal(self) -> None:
        from creative_sbi_navigation import request_song_based_improvisation
        from studio_nav_history import set_creative_history_seal

        session = _creative_session()
        set_creative_history_seal(session, "creative::Song-Aware Coaching")  # as just after a Back
        self.assertTrue(request_song_based_improvisation(session, "test"))
        self.assertNotIn("_pending_history_creative_dest", session)
        self.assertNotIn("_studio_history_creative_dest_seal", session)
        self.assertEqual(session["improv_intelligence_tab"], "Entry & Jam")

    def test_the_lane_follows_the_global_owner_only_when_asked(self) -> None:
        from creative_sbi_navigation import request_song_based_improvisation

        stale = _creative_session(improv_song_source="Custom progression")
        request_song_based_improvisation(stale, "test")
        self.assertEqual(stale["improv_song_source"], "Custom progression", "manual-style call keeps the preview")
        synced = _creative_session(improv_song_source="Custom progression")
        with mock.patch("source_session_state.global_music_source_owner", return_value="catalog"):
            request_song_based_improvisation(synced, "test", sync_source_to_global_owner=True)
        self.assertEqual(synced["improv_song_source"], "Active song", "a stale Custom preview is dropped")

    def test_apply_song_based_entry_is_the_entry_radios_branch(self) -> None:
        from creative_sbi_navigation import apply_song_based_entry

        with mock.patch("backing_source_navigation.release_mission_creative_page_ownership") as release, \
                mock.patch("song_improv_scope_authority.apply_song_improv_entry_defaults") as defaults:
            session = {}
            apply_song_based_entry(session)
        release.assert_called_once_with(session, reason="entry_mode_song_based", force_entry_jam_tab=True)
        defaults.assert_called_once_with(session, source="entry_mode_song_based")

    def test_the_entry_radio_uses_the_shared_helper(self) -> None:
        import inspect

        import improvisation_intelligence_ui as ui

        src = inspect.getsource(ui)
        block = src[src.index("def _on_entry_mode_change"): src.index("ensure_improv_entry_mode_restored(session_state)")]
        self.assertIn("apply_song_based_entry(session_state)", block)
        self.assertNotIn("apply_song_improv_entry_defaults", block)


# --------------------------------------------------------------------------- the coaching button


class TestContinueButton(unittest.TestCase):
    def test_continue_records_the_handoff_and_leaves_the_lesson_untouched(self) -> None:
        from song_coach_ui import on_continue_sbi

        ctx, _plan, _scope_, state = _lesson()
        session = _creative_session(**{SONG_COACH_STATE_KEY: state.to_dict()})
        SAVE_REQUESTS.clear()
        on_continue_sbi(session, ctx)
        saved = CoachState.from_dict(session[SONG_COACH_STATE_KEY])
        self.assertEqual((saved.plan_id, saved.stage, saved.checks, saved.built), (state.plan_id, 2, {"2": (0,)}, state.built))
        self.assertEqual(saved.handoff["identity"], ctx.identity)
        self.assertEqual(handoff_status(saved, ctx), HANDOFF_VALID)
        self.assertEqual(session["improv_entry_mode"], "Song-Based Improvisation")
        self.assertEqual(session["_song_coach_last_commit"]["interaction"], "handoff_sbi")
        self.assertEqual(len(SAVE_REQUESTS), 1)

    def test_no_plan_no_handoff(self) -> None:
        from song_coach_ui import FLASH_KEY, on_continue_sbi

        ctx, _plan, _scope_, _state = _lesson()
        session = _creative_session()
        on_continue_sbi(session, ctx)
        self.assertIn(FLASH_KEY, session)
        self.assertEqual(session["improv_intelligence_tab"], "Song-Aware Coaching", "nothing navigates")


if __name__ == "__main__":
    unittest.main()

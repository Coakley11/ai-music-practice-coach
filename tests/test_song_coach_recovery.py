"""Song-Aware Coaching S6 — persistence, identity and recovery (pure).

Saved records are read field by field and never trusted: the plan is rebuilt and its id
verified; damaged fields fall back with a clear notice; records from earlier slices (S3–S5)
still load; a different song, chart or Practice Key invalidates; an instrument change keeps the
concert-pitch progress.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import unittest

from song_coach_plan import FOCUS_MOTIF, FOCUS_RHYTHMIC
from song_coach_state import (
    LOOP_RANGE_CHALLENGE,
    LOOP_RANGE_SELECTION,
    NOTICE_CHART_CHANGED,
    NOTICE_MESSAGES,
    NOTICE_OTHER_SONG,
    NOTICE_PLAN_STALE,
    NOTICE_STATE_NEWER,
    NOTICE_STATE_REPAIRED,
    NOTICE_STATE_UNREADABLE,
    SONG_COACH_STATE_KEY,
    STATE_VERSION,
    CoachState,
    Selection,
    build_plan_for,
    example_for,
    parse_state,
    reconcile,
    with_built_plan,
    with_check,
    with_example,
    with_loop,
    with_new_example_idea,
    with_stage,
)
from tests.test_song_coach_examples import _scope

SAVE_REQUESTS: list[str] = []
_SAVE_PATCH = None


def setUpModule() -> None:
    global _SAVE_PATCH
    from unittest import mock

    _SAVE_PATCH = mock.patch(
        "creative_context_snapshot_persistence.request_context_cloud_save",
        side_effect=lambda session, *, save_reason: SAVE_REQUESTS.append(save_reason) or True,
    )
    _SAVE_PATCH.start()


def tearDownModule() -> None:
    if _SAVE_PATCH is not None:
        _SAVE_PATCH.stop()


def _lesson(name: str = "perfect", instrument: str = "Piano"):
    """A lesson in progress: built plan, challenge 2, a tick, an example, a new idea, loop prefs."""
    ctx, _ = _scope(name)
    ctx = dataclasses.replace(ctx, instrument=instrument)
    rec = reconcile({}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
    plan, scope = build_plan_for(ctx, rec.state.draft)
    state = with_built_plan(rec.state, plan)
    state = with_stage(state, 1, len(plan.challenges))
    state = with_check(state, 1, 0, True)
    state = with_new_example_idea(with_example(state, 1, True))
    state = with_loop(state, bpm=70, loop_range=LOOP_RANGE_SELECTION)
    return ctx, plan, scope, state


def _session(state) -> dict:
    return {SONG_COACH_STATE_KEY: json.loads(json.dumps(state.to_dict()))}


# --------------------------------------------------------------------------- reading saved records


class TestParsing(unittest.TestCase):
    def test_a_clean_record_round_trips(self) -> None:
        _ctx, _plan, _scope_, state = _lesson()
        parsed, status = parse_state(state.to_dict())
        self.assertEqual((parsed, status), (state, ""))

    def test_records_from_earlier_slices_still_load(self) -> None:
        _ctx, _plan, _scope_, state = _lesson()
        full = state.to_dict()
        s3 = {k: v for k, v in full.items() if k not in ("examples", "example_nonce", "loop_bpm", "loop_range")}
        s4 = {k: v for k, v in full.items() if k not in ("loop_bpm", "loop_range")}
        for label, raw, expect in (("S3", s3, ((), 0, 0, LOOP_RANGE_CHALLENGE)), ("S4", s4, ((1,), 1, 0, LOOP_RANGE_CHALLENGE)),
                                   ("S5", full, ((1,), 1, 70, LOOP_RANGE_SELECTION))):
            parsed, status = parse_state(raw)
            with self.subTest(slice=label):
                self.assertEqual(status, "")
                self.assertEqual((parsed.examples, parsed.example_nonce, parsed.loop_bpm, parsed.loop_range), expect)
                self.assertEqual((parsed.plan_id, parsed.stage, parsed.checks), (state.plan_id, 1, {"1": (0,)}))

    def test_damaged_fields_fall_back_and_the_rest_is_kept(self) -> None:
        _ctx, _plan, _scope_, state = _lesson()
        good = state.to_dict()
        damage = {
            "stage": "two", "examples": ["x", 1], "example_nonce": -3, "loop_bpm": 999, "loop_range": "everything",
            "checks": {"1": ["a", 0], "oops": [1]}, "draft": {**good["draft"], "level": "Expert"},
            "built": {**good["built"], "focus": "unknown_focus"}, "instrument": 42,
        }
        for field_name, bad in damage.items():
            raw = {**good, field_name: bad}
            parsed, status = parse_state(raw)
            with self.subTest(field=field_name):
                self.assertEqual(status, "repaired")
                self.assertEqual(parsed.identity, state.identity)
                self.assertEqual(parsed.plan_id, state.plan_id)
        parsed, _ = parse_state({**good, **damage})
        self.assertEqual((parsed.stage, parsed.example_nonce, parsed.loop_bpm, parsed.loop_range), (0, 0, 0, LOOP_RANGE_CHALLENGE))
        self.assertEqual(parsed.examples, (1,))
        self.assertEqual(parsed.checks, {"1": (0,)})
        self.assertEqual((parsed.draft.level, parsed.built.focus, parsed.instrument), ("", "", ""))

    def test_unreadable_and_newer_records(self) -> None:
        for raw in ("not a record", ["a", "list"], 42, {"plan_id": "x"}, {"identity": 5, "stage": "z"}):
            with self.subTest(raw=str(raw)[:30]):
                self.assertEqual(parse_state(raw), (None, "unreadable"))
        self.assertEqual(parse_state(None), (None, ""))
        self.assertEqual(parse_state({"identity": "catalog|x", "version": STATE_VERSION + 1}), (None, "newer"))
        self.assertIsNone(CoachState.from_dict("garbage"))

    def test_bars_in_the_wrong_order_are_dropped(self) -> None:
        parsed, status = parse_state({"identity": "catalog|x", "draft": {"section_id": "v", "start_bar": 8, "end_bar": 2,
                                                                         "level": "Beginner", "focus": FOCUS_MOTIF}})
        self.assertEqual(status, "repaired")
        self.assertEqual(parsed.draft, Selection(level="Beginner", focus=FOCUS_MOTIF))


# --------------------------------------------------------------------------- reconcile


class TestRecovery(unittest.TestCase):
    def test_a_saved_lesson_is_restored_after_a_refresh(self) -> None:
        ctx, plan, _scope_, state = _lesson()
        rec = reconcile(_session(state), ctx, level="Beginner", focus=FOCUS_RHYTHMIC)
        self.assertEqual(rec.notice, "")
        self.assertIsNotNone(rec.plan)
        self.assertEqual(rec.plan.plan_id, plan.plan_id, "rebuilt deterministically, id verified")
        self.assertEqual((rec.state.stage, rec.state.checks, rec.state.examples, rec.state.example_nonce),
                         (1, {"1": (0,)}, (1,), 1))
        self.assertEqual((rec.state.loop_bpm, rec.state.loop_range), (70, LOOP_RANGE_SELECTION))
        self.assertEqual(rec.state.draft, state.draft, "the draft is not replaced by the global level / focus")

    def test_damaged_and_unreadable_records_recover_with_a_message(self) -> None:
        ctx, _plan, _scope_, state = _lesson()
        rec = reconcile({SONG_COACH_STATE_KEY: "garbage"}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.notice, NOTICE_STATE_UNREADABLE)
        self.assertIsNone(rec.plan)
        self.assertEqual(rec.state.identity, ctx.identity)
        newer = {**state.to_dict(), "version": STATE_VERSION + 1}
        self.assertEqual(reconcile({SONG_COACH_STATE_KEY: newer}, ctx, level="Intermediate", focus=FOCUS_MOTIF).notice,
                         NOTICE_STATE_NEWER)
        damaged = {**state.to_dict(), "loop_bpm": 999, "examples": "x"}
        rec = reconcile({SONG_COACH_STATE_KEY: damaged}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.notice, NOTICE_STATE_REPAIRED)
        self.assertIsNotNone(rec.plan, "the valid part of the lesson is kept")
        self.assertEqual((rec.state.loop_bpm, rec.state.examples, rec.state.stage), (0, (), 1))
        for notice in (NOTICE_STATE_UNREADABLE, NOTICE_STATE_NEWER, NOTICE_STATE_REPAIRED):
            self.assertTrue(NOTICE_MESSAGES[notice])

    def test_a_corrupted_level_or_focus_never_reaches_the_widgets(self) -> None:
        ctx, _plan, _scope_, state = _lesson()
        raw = state.to_dict()
        raw["draft"] = {**raw["draft"], "level": "Expert", "focus": "nope"}
        rec = reconcile({SONG_COACH_STATE_KEY: raw}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
        from song_coach_plan import FOCUSES, LEVELS

        self.assertIn(rec.state.draft.level, LEVELS)
        self.assertIn(rec.state.draft.focus, FOCUSES)

    def test_tampered_plan_ids_and_bars_are_not_trusted(self) -> None:
        ctx, _plan, _scope_, state = _lesson()
        for change in ({"plan_id": "forged"}, {"built": {**state.to_dict()["built"], "end_bar": 99}},
                       {"built": {**state.to_dict()["built"], "section_id": "no-such-section"}}):
            raw = {**state.to_dict(), **change}
            rec = reconcile({SONG_COACH_STATE_KEY: raw}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
            with self.subTest(change=list(change)):
                self.assertEqual(rec.notice, NOTICE_PLAN_STALE)
                self.assertIsNone(rec.plan)
                self.assertEqual((rec.state.examples, rec.state.example_nonce, rec.state.stage, rec.state.checks),
                                 ((), 0, 0, {}))
                self.assertEqual((rec.state.loop_bpm, rec.state.loop_range), (70, LOOP_RANGE_SELECTION),
                                 "practice preferences survive")

    def test_out_of_range_progress_is_clamped(self) -> None:
        ctx, plan, _scope_, state = _lesson()
        raw = {**state.to_dict(), "stage": 50, "examples": [0, 1, 40]}
        rec = reconcile({SONG_COACH_STATE_KEY: raw}, ctx, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.state.stage, len(plan.challenges) - 1)
        self.assertEqual(rec.state.examples, (0, 1))

    def test_song_chart_and_key_changes_invalidate(self) -> None:
        ctx, _plan, _scope_, state = _lesson()
        session = _session(state)
        other = dataclasses.replace(ctx, identity="catalog|Another Song")
        rec = reconcile(session, other, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.notice, NOTICE_OTHER_SONG)
        self.assertIsNone(rec.plan)
        self.assertEqual(rec.state.identity, other.identity)
        for changed in (dataclasses.replace(ctx, fingerprint="edited-chart"),
                        dataclasses.replace(ctx, fingerprint="another-key")):
            rec = reconcile(session, changed, level="Intermediate", focus=FOCUS_MOTIF)
            self.assertEqual(rec.notice, NOTICE_CHART_CHANGED)
            self.assertEqual((rec.plan, rec.state.examples, rec.state.example_nonce, rec.state.plan_id), (None, (), 0, ""))
        # Visiting another song is read-only: the first song's lesson is still there afterwards.
        self.assertEqual(reconcile(session, ctx, level="Intermediate", focus=FOCUS_MOTIF).state.stage, 1)

    def test_an_instrument_change_keeps_the_concert_lesson(self) -> None:
        ctx, plan, scope, state = _lesson(instrument="Piano")
        session = _session(state)
        sax = dataclasses.replace(ctx, instrument="Saxophone")
        rec = reconcile(session, sax, level="Intermediate", focus=FOCUS_MOTIF)
        self.assertEqual(rec.notice, "")
        self.assertIsNotNone(rec.plan)
        self.assertEqual((rec.state.plan_id, rec.state.stage, rec.state.checks, rec.state.examples),
                         (state.plan_id, 1, {"1": (0,)}, (1,)))
        a = example_for({}, state, plan, scope, 1)
        b = example_for({}, rec.state, rec.plan, rec.scope, 1)
        self.assertEqual([s.motif["midi"] for s in a.segments], [s.motif["midi"] for s in b.segments],
                         "the same concert example; only its written display changes")

    def test_the_loop_follows_the_lesson_not_the_instrument(self) -> None:
        from song_coach_backing import loop_request
        from song_coach_player import loop_bars

        ctx, plan, scope, state = _lesson()
        sax = dataclasses.replace(ctx, instrument="Saxophone", chart_key="E")
        a = loop_request(ctx, scope, start_bar=plan.start_bar, end_bar=plan.end_bar, bpm=70, style="Ballad")
        b = loop_request(sax, scope, start_bar=plan.start_bar, end_bar=plan.end_bar, bpm=70, style="Ballad")
        self.assertEqual(a.signature(), b.signature(), "concert audio is instrument-independent")
        self.assertEqual(loop_bars(plan, plan.challenges[1], LOOP_RANGE_SELECTION), (plan.start_bar, plan.end_bar))


# --------------------------------------------------------------------------- player: never starts by itself


class TestResumeRule(unittest.TestCase):
    def test_the_player_resumes_only_on_the_tempo_signal(self) -> None:
        from song_coach_backing import render_loop
        from song_coach_player import CHANNEL, player_html, resume_signal_html
        from tests.test_song_coach_backing import _request

        loop = render_loop(_request("composition", start_bar=1, end_bar=2))
        doc = player_html(loop)
        self.assertIn("function tryResume(token)", doc)
        self.assertIn('window.sessionStorage.getItem("songCoachLoopResume")', doc)
        self.assertNotIn("if (prev && prev.range === CFG.range && Date.now() - Number(prev.t || 0) < 4000) play();\n  } catch",
                         doc.split("function tryResume")[0], "no unconditional resume before the rule")
        signal = resume_signal_html(loop.request.range_key())
        self.assertIn(loop.request.range_key(), signal)
        self.assertIn(CHANNEL, signal)
        self.assertNotIn("<audio", signal + doc)

    def test_only_a_tempo_change_sets_the_signal(self) -> None:
        from song_coach_player import LOOP_RESUME_KEY, W_LOOP_BPM, W_LOOP_RANGE, on_loop_range, on_loop_tempo, song_bpm

        ctx, _plan, _scope_, state = _lesson()
        session = _session(state)
        session[W_LOOP_RANGE] = LOOP_RANGE_CHALLENGE
        on_loop_range(session, ctx)
        self.assertNotIn(LOOP_RESUME_KEY, session)
        session[W_LOOP_BPM] = 80
        on_loop_tempo(session, ctx)
        self.assertTrue(session.get(LOOP_RESUME_KEY))
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).loop_bpm, 80)
        session.pop(LOOP_RESUME_KEY)
        session[W_LOOP_BPM] = 80
        on_loop_tempo(session, ctx)  # unchanged: no write, no signal
        self.assertNotIn(LOOP_RESUME_KEY, session)
        session[W_LOOP_BPM] = song_bpm(ctx)
        on_loop_tempo(session, ctx)
        self.assertEqual(CoachState.from_dict(session[SONG_COACH_STATE_KEY]).loop_bpm, 0, "song tempo is stored as 0")


if __name__ == "__main__":
    unittest.main()

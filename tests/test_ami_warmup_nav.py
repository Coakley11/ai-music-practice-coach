"""Warmup card navigation: Next exercise / Previous exercise / Whole warmup.

Drives the REAL button renderer (`applied_math_return_insight._render_warmup_nav`) with a minimal Streamlit stand-in, and the typed path through
`run_coach_submit`. Navigation is a view change: it must not change the stored warmup (musical content), create an undo version, or touch the
account / workspace context or any other session state.
"""
from __future__ import annotations

import contextlib
import copy

import pytest

import applied_math_return_insight as ami_card
from music_coach_ami import warmup_plan as wp
from music_coach_ami.claude_client import AnthropicTransport
from tests.test_ami_warmups import ALTO, ask, plan_of, session


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


class _Rerun(Exception):
    pass


class FakeSt:
    """Just enough Streamlit for the nav row: columns, button, warning, rerun, session_state."""

    def __init__(self, session_state: dict, press: str | None = None):
        self.session_state = session_state
        self.press = press
        self.buttons: list[tuple[str, str, str]] = []   # (label, key, type)
        self.warnings: list[str] = []

    def columns(self, n):
        return [contextlib.nullcontext() for _ in range(n)]

    def button(self, label, key=None, use_container_width=False, type="secondary", **kw):
        self.buttons.append((label, key, type))
        return label == self.press

    def warning(self, msg):
        self.warnings.append(str(msg))

    def rerun(self):
        raise _Rerun()


def _card_from(resp) -> dict:
    """What submit_integration stores for the page: the response's nav + notation, as the card sees it."""
    return {"warmup_nav": dict(resp.diagnostics["warmup_nav"]), "conclusion": resp.composed_markdown(), "notation_abc": str(resp.notation_abc or ""),
            "notation_abc_sections": [str(x) for x in resp.notation_abc_sections]}


def _press(session_state: dict, card: dict, label: str) -> tuple[FakeSt, dict]:
    st = FakeSt(session_state, press=label)
    with pytest.raises(_Rerun):
        ami_card._render_warmup_nav(st, card, app="music")
    return st, session_state[ami_card.SESSION_PENDING_KEY]


def _draw(session_state: dict, card: dict) -> FakeSt:
    st = FakeSt(session_state)
    ami_card._render_warmup_nav(st, card, app="music")
    return st


def _labels(st: FakeSt) -> list[str]:
    return [b[0] for b in st.buttons]


def _fresh(minutes: int = 5):
    s = session("Saxophone", ALTO)
    resp = ask(s, f"Give me a {minutes}-minute warmup", instrument="Saxophone")
    return s, resp


def _signature(s: dict) -> dict:
    return {k: copy.deepcopy(v) for k, v in s.items() if k != ami_card.SESSION_PENDING_KEY and not k.startswith("_ami_conv_")}


class TestWhichButtonsAppear:
    def test_the_whole_plan_offers_only_next_exercise(self):
        s, resp = _fresh()
        assert _labels(_draw(s, _card_from(resp))) == ["Next exercise"]

    def test_a_middle_exercise_offers_previous_next_and_whole(self):
        s, resp = _fresh()
        card = _card_from(resp)
        _, card = _press(s, card, "Next exercise")
        _, card = _press(s, card, "Next exercise")
        assert _labels(_draw(s, card)) == ["Previous exercise", "Next exercise", "Whole warmup"]

    def test_the_first_exercise_has_no_previous_and_the_last_has_no_next(self):
        s, resp = _fresh()
        card = _card_from(resp)
        _, card = _press(s, card, "Next exercise")
        assert _labels(_draw(s, card)) == ["Next exercise", "Whole warmup"]
        n = len(plan_of(s)["items"])
        for _ in range(n - 1):
            _, card = _press(s, card, "Next exercise")
        assert card["warmup_nav"]["index"] == n - 1
        assert _labels(_draw(s, card)) == ["Previous exercise", "Whole warmup"]

    def test_no_buttons_for_a_card_without_a_warmup_and_none_outside_the_music_app(self):
        s, resp = _fresh()
        assert _draw(s, {}).buttons == []
        assert _draw(s, {"warmup_nav": {"count": 0}}).buttons == []
        st = FakeSt(s)
        ami_card._render_warmup_nav(st, _card_from(resp), app="finance")
        assert st.buttons == []

    def test_button_keys_change_with_the_view_so_streamlit_never_reuses_a_stale_one(self):
        s, resp = _fresh()
        card = _card_from(resp)
        keys_plan = {b[1] for b in _draw(s, card).buttons}
        _, card = _press(s, card, "Next exercise")
        keys_item = {b[1] for b in _draw(s, card).buttons}
        assert keys_plan.isdisjoint(keys_item)


class TestNavigationChangesOnlyTheView:
    def test_next_shows_that_exercises_own_notation_and_the_card_is_updated(self):
        s, resp = _fresh()
        plan = plan_of(s)
        _, card = _press(s, _card_from(resp), "Next exercise")
        assert card["warmup_nav"]["mode"] == "item" and card["warmup_nav"]["index"] == 0
        assert card["notation_abc_sections"] == [plan["items"][0]["abc"]]
        assert f"Exercise 1 of {len(plan['items'])}" in card["conclusion"]
        _, card = _press(s, card, "Next exercise")
        assert card["notation_abc_sections"] == [plan["items"][1]["abc"]] and card["warmup_nav"]["index"] == 1

    def test_previous_goes_back_exactly_and_whole_warmup_restores_every_staff(self):
        s, resp = _fresh()
        whole = _card_from(resp)
        plan = plan_of(s)
        _, card = _press(s, whole, "Next exercise")
        first = copy.deepcopy(card["notation_abc_sections"])
        _, card = _press(s, card, "Next exercise")
        _, card = _press(s, card, "Previous exercise")
        assert card["notation_abc_sections"] == first and card["warmup_nav"]["index"] == 0
        _, card = _press(s, card, "Whole warmup")
        assert card["warmup_nav"]["mode"] == "plan"
        assert card["notation_abc_sections"] == [r["abc"] for r in plan["items"]] == whole["notation_abc_sections"]

    def test_the_stored_warmup_is_identical_after_any_amount_of_navigation(self):
        s, resp = _fresh(10)
        before = copy.deepcopy(plan_of(s))
        card = _card_from(resp)
        for label in ["Next exercise", "Next exercise", "Previous exercise", "Whole warmup", "Next exercise", "Whole warmup"]:
            _, card = _press(s, card, label)
        assert plan_of(s) == before

    def test_navigation_creates_no_undo_version_and_does_not_disturb_undo_or_redo(self):
        s, resp = _fresh(10)
        ask(s, "Make the whole warmup shorter", instrument="Saxophone")
        ask(s, "Undo that")
        info = copy.deepcopy(wp.history(s))
        assert info["can_redo"] and info["versions"] >= 2
        card = _card_from(wp.step_view(s, 0))
        for label in ["Next exercise", "Next exercise", "Previous exercise", "Whole warmup"]:
            _, card = _press(s, card, label)
        assert wp.history(s) == info          # same versions, same cursor, redo still available
        ask(s, "Redo")
        assert wp.history(s)["can_undo"] and not wp.history(s)["can_redo"]

    def test_navigation_does_not_touch_the_account_workspace_or_any_other_session_value(self):
        s, resp = _fresh()
        s["practice_key"] = "Bb"
        s["backing_bpm"] = 84
        before = _signature(s)
        card = _card_from(resp)
        for label in ["Next exercise", "Next exercise", "Whole warmup"]:
            _, card = _press(s, card, label)
        assert _signature(s) == before
        assert s["_suite_auth_user_id"] == "u1" and s["_suite_active_workspace_id"] == "daniel"

    def test_a_revision_after_navigating_still_applies_to_the_whole_warmup_and_keeps_the_untouched_exercises(self):
        s, resp = _fresh(10)
        before = copy.deepcopy(plan_of(s))
        card = _card_from(resp)
        for _ in range(2):
            _, card = _press(s, card, "Next exercise")
        ask(s, "Make the second exercise slower", instrument="Saxophone")
        after = plan_of(s)
        assert after["items"][1]["bpm"] < before["items"][1]["bpm"]
        for i, (a, b) in enumerate(zip(after["items"], before["items"])):
            if i != 1:
                assert a["abc"] == b["abc"] and a["bpm"] == b["bpm"]


class TestNavigationRespectsOwnership:
    def test_a_card_from_another_account_is_refused_and_changes_nothing(self):
        s, resp = _fresh()
        card = _card_from(resp)
        other = session("Saxophone", ALTO, user="someone-else")
        before = _signature(other)
        st = FakeSt(other, press="Next exercise")
        ami_card._render_warmup_nav(st, card, app="music")      # no rerun: nothing happened
        assert st.warnings and "no longer the working one" in st.warnings[0]
        assert _signature(other) == before and ami_card.SESSION_PENDING_KEY not in other
        assert wp.current(other) is None and "_ami_conv_warmup" not in other     # only the ownership stamp may appear

    def test_a_card_after_a_workspace_switch_cannot_step_the_old_warmup(self):
        s, resp = _fresh()
        card = _card_from(resp)
        s["_suite_active_workspace_id"] = "another-workspace"
        assert wp.step_view(s, 1) is None
        st = FakeSt(s, press="Next exercise")
        ami_card._render_warmup_nav(st, card, app="music")
        assert st.warnings and ami_card.SESSION_PENDING_KEY not in s

    def test_after_a_normal_exercise_replaces_the_warmup_the_old_card_buttons_do_nothing(self):
        from music_coach_ami.pipeline import run_coach_submit
        from tests.test_ami_warmups import ctx

        s = session("Flute")
        card = _card_from(ask(s, "Give me a warmup"))
        resp = run_coach_submit("Give me an advanced scale pattern over Blue Bossa.", s, ami_ctx={
            **ctx("Flute", "Advanced", "Cm"), "active_song": {"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
            "chart_sections": {"Section A": ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]}, "chart_sections_key": "Cm"})[1]
        assert resp.diagnostics.get("generated_exercise_id") and not wp.is_active(s)
        st = FakeSt(s, press="Next exercise")
        ami_card._render_warmup_nav(st, card, app="music")
        assert st.warnings and "no longer the working one" in st.warnings[0]
        assert ami_card.SESSION_PENDING_KEY not in s


class TestSubmitIntegrationCarriesTheNav:
    def test_the_response_nav_is_what_the_card_receives(self):
        s, resp = _fresh()
        nav = resp.diagnostics["warmup_nav"]
        assert nav["count"] == len(plan_of(s)["items"]) and nav["mode"] == "plan" and nav["can_next"] and not nav["can_prev"]
        # the card only needs these keys; a view change rewrites them, nothing else
        assert {"plan_id", "count", "mode", "index", "can_next", "can_prev", "can_all"} <= set(nav)

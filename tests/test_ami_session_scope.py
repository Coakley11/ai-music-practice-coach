"""AMI conversation state belongs to one account in one workspace: sign-out, account switch and stale reads."""

from __future__ import annotations

import pytest

import suite_auth
from music_coach_ami import conversation_state as cs
from music_coach_ami import session_scope as scope
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_followup import last_exercise
from music_coach_ami.pipeline import run_coach_submit

CTX = {
    "instrument": "Flute", "level": "Intermediate", "focus": "Improvisation",
    "active_song": {"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
    "chart_sections": {"A": ["Cm7", "Fm7", "Dm7b5", "G7"]}, "chart_sections_key": "Cm", "bpm": 96, "practice_key_hint": "Cm",
}
# State other parts of the app own; no AMI conversation event may touch any of it.
UNRELATED = {
    "practice_key": "Fm", "chart_practice_key": "Fm", "key_cycle_active": True, "key_cycle_index": 3,
    "backing_enabled": True, "backing_bpm": 112, "composition_title": "My tune", "improv_active_mission": "pentatonic",
    "_ami_pending_insight": {"id": "i1"}, "_ami_insight_active_id": "i1",
}


def _session(user: str, workspace: str = "daniel") -> dict:
    return {"_suite_auth_session": True, "_suite_auth_user_id": user, "_suite_auth_user_email": f"{user}@example.com",
            "_suite_active_workspace_id": workspace, **UNRELATED}


def _ask(session: dict, question: str):
    return run_coach_submit(question, session, ami_ctx=dict(CTX))[1]


def _make_exercise(session: dict) -> str:
    resp = _ask(session, "Give me a guide tone line over Cm7")
    assert resp.diagnostics.get("generated_exercise_id"), "fixture exercise was not created"
    return resp.diagnostics["generated_exercise_id"]


def _unrelated_intact(session: dict) -> bool:
    return all(session.get(k) == v for k, v in UNRELATED.items())


# ---- owner token ------------------------------------------------------------------------------------------------
def test_owner_token_names_account_and_workspace():
    assert scope.owner_token(_session("u1", "Daniel")) == "u1|daniel"
    assert scope.owner_token({}) == "anonymous|"
    assert scope.owner_token(_session("U1")) != scope.owner_token(_session("u2"))


# ---- sign-out ---------------------------------------------------------------------------------------------------
def test_sign_out_clears_conversation_state_and_nothing_else(monkeypatch):
    s = _session("u1")
    _make_exercise(s)
    s["_ami_claude_cache"] = {"fp": "x"}
    assert AMI_LAST_EXERCISE_KEY in s and cs.STATE_KEY in s
    suite_auth._clear_auth_session(s)
    assert not [k for k in s if scope.is_conversation_key(k)]
    assert "_suite_auth_user_id" not in s
    assert _unrelated_intact(s)


def test_logout_function_also_clears_it():
    s = _session("u1")
    _make_exercise(s)
    suite_auth.logout(s, st=None)
    assert AMI_LAST_EXERCISE_KEY not in s and cs.STATE_KEY not in s and _unrelated_intact(s)


# ---- account change ---------------------------------------------------------------------------------------------
def test_signing_in_as_a_different_account_drops_the_previous_accounts_conversation():
    s = _session("u1")
    _make_exercise(s)
    suite_auth._apply_authenticated_user(s, {"id": "u2", "email": "u2@example.com"})
    assert AMI_LAST_EXERCISE_KEY not in s and cs.STATE_KEY not in s
    assert _unrelated_intact(s)


def test_signing_in_again_as_the_same_account_keeps_it():
    s = _session("u1")
    _make_exercise(s)
    suite_auth._apply_authenticated_user(s, {"id": "u1", "email": "u1@example.com"})
    assert AMI_LAST_EXERCISE_KEY in s and cs.current_version(s) is not None


# ---- reads reject mismatches (not only writes) --------------------------------------------------------------------
def test_stale_exercise_from_another_account_is_not_readable_even_without_a_purge():
    s = _session("u1")
    _make_exercise(s)
    assert last_exercise(s) is not None
    s["_suite_auth_user_id"] = "u2"          # the account changed under us; nothing purged yet
    assert last_exercise(s) is None


def test_stale_exercise_from_another_workspace_is_not_readable():
    s = _session("u1", "daniel")
    _make_exercise(s)
    s["_suite_active_workspace_id"] = "ariel"
    assert last_exercise(s) is None
    assert cs.current_version(s) is None


def test_unstamped_legacy_exercise_is_refused_for_a_signed_in_account_but_not_for_anonymous():
    s = _session("u1")
    _make_exercise(s)
    raw = scope.unstamped(s[AMI_LAST_EXERCISE_KEY])
    legacy = {AMI_LAST_EXERCISE_KEY: dict(raw)}
    assert last_exercise(legacy) is not None            # anonymous session: nothing to leak across
    s[AMI_LAST_EXERCISE_KEY] = dict(raw)
    assert last_exercise(s) is None                     # signed-in: unstamped means unknown owner


def test_a_forged_owner_field_does_not_help():
    a, b = _session("u1"), _session("u2")
    _make_exercise(a)
    b[AMI_LAST_EXERCISE_KEY] = dict(a[AMI_LAST_EXERCISE_KEY])     # u1's stamped object lands in u2's session
    assert last_exercise(b) is None


def test_ensure_owner_purges_foreign_state_before_a_submit_can_read_it():
    s = _session("u1")
    _make_exercise(s)
    s["_ami_claude_cache"] = {"fp": "secret-ish"}
    s["_suite_auth_user_id"] = "u2"
    resp = _ask(s, "Make it slower")
    assert "no exercise from this conversation" in resp.direct_answer.lower()
    assert "_ami_claude_cache" not in s
    assert s[scope.OWNER_KEY] == "u2|daniel"
    assert _unrelated_intact(s)


def test_the_developer_mode_flag_survives_an_ownership_purge():
    s = _session("u1")
    _make_exercise(s)
    s["_suite_auth_user_id"] = "u2"
    s["_ami_claude_dev_mode"] = True
    scope.ensure_owner(s)
    assert s.get("_ami_claude_dev_mode") is True


# ---- two accounts, repeatedly, in one browser session --------------------------------------------------------------
def test_two_accounts_signing_in_and_out_repeatedly_never_see_each_others_exercises():
    s = _session("u1")
    seen: dict[str, str] = {}
    for round_no in range(3):
        for user in ("u1", "u2"):
            suite_auth._clear_auth_session(s)                                   # sign out
            s.update({"_suite_auth_session": True, "_suite_active_workspace_id": "daniel", **UNRELATED})
            suite_auth._apply_authenticated_user(s, {"id": user, "email": f"{user}@example.com"})  # sign in
            assert last_exercise(s) is None and cs.current_version(s) is None, f"round {round_no}: {user} inherited state"
            resp = _ask(s, "Make it slower")
            assert "no exercise from this conversation" in resp.direct_answer.lower()
            seen[user] = _make_exercise(s)
            resp = _ask(s, "Make it slower")
            assert "BPM" in resp.direct_answer
            assert _unrelated_intact(s)
    assert seen["u1"] and seen["u2"]


def test_two_accounts_in_two_sessions_have_independent_histories():
    a, b = _session("u1"), _session("u2")
    _make_exercise(a)
    _ask(a, "Make it slower")
    _make_exercise(b)
    assert cs.history(a)["versions"] == 2 and cs.history(b)["versions"] == 1
    _ask(b, "Set it to 120 BPM")
    assert cs.working_tempo(a) == 86 and cs.working_tempo(b) == 120


# ---- workspace switch (the app's own handler) ----------------------------------------------------------------------
def test_workspace_switch_drops_the_conversation_and_keeps_unrelated_state():
    import suite_workspace

    class _St:
        pass

    st = _St()
    st.session_state = _session("u1")
    _make_exercise(st.session_state)
    suite_workspace._on_active_workspace_changed(st)
    assert not [k for k in st.session_state if scope.is_conversation_key(k)]
    assert st.session_state["practice_key"] == "Fm" and st.session_state["backing_bpm"] == 112 and st.session_state["composition_title"] == "My tune"


@pytest.mark.parametrize("key", ["_ami_conv_state", "_ami_conv_owner", "_ami_claude_cache", "_ami_claude_last", "_ami_last_generated_exercise"])
def test_every_conversation_key_is_recognised(key):
    assert scope.is_conversation_key(key)


def test_unrelated_ami_keys_are_not_conversation_keys():
    assert not scope.is_conversation_key("_ami_pending_insight") and not scope.is_conversation_key("practice_key")

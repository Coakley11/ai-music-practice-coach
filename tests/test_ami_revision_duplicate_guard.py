"""The duplicate-send guard and revision requests, through the real Music Coach submit path.

A revision ("Undo that", "Make it more advanced", "Change it to fourths") acts on the version the conversation is at, so the same words are
a new request each time the version moves, and a duplicate only when nothing has moved. Reruns cannot replay a send because every send
bumps the question widget's generation. A revision never reaches the Claude enrichment.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from music_coach_ami import conversation_state as cs
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.semantic_fingerprint import music_coach_semantic_fingerprint
from suite_analytical_question import _execute_coach_question_submit
from tests.test_ami_scale_pattern_recipe import ASK_CHORDS, ctx, session

GEN_KEY = "_ami_send_gen_music_practice"


@pytest.fixture(autouse=True)
def _count_api_calls(monkeypatch):
    calls = []

    def boom(self, **kw):
        calls.append(kw)
        raise AssertionError("LIVE API CALL")

    monkeypatch.setattr(AnthropicTransport, "complete", boom)
    return calls


def send(ss, q, *, generation=None):
    st = MagicMock()
    st.session_state = ss
    with patch("suite_analytical_question.submit_analytical_question") as legacy, \
            patch("applied_math_return_insight.store_applied_math_insight", return_value="ins"), \
            patch("applied_math_return_insight.stage_pending_insight"):
        out = _execute_coach_question_submit(
            st, MagicMock(), ss, question_raw=q, source_app="music", source_page="practice", page_suffix="practice",
            send_gen=int(ss.get(GEN_KEY) or 0) if generation is None else generation,
            context=dict(ctx(), coach_page="practice"), source_state_builder=lambda: {"source_page": "practice"},
        )
    assert legacy.call_count == 0
    return out


def where(ss):
    h = cs.history(ss)
    return h["versions"], h["cursor"]


def started():
    ss = session()
    assert send(ss, ASK_CHORDS)["duplicate"] is False
    return ss


def test_the_same_revision_twice_in_a_row_is_applied_twice():
    ss = started()
    for expected in (2, 3):
        out = send(ss, "Make it more advanced")
        assert out["duplicate"] is False
        assert where(ss)[0] == expected


def test_consecutive_undo_and_redo_each_move_the_version():
    ss = started()
    for q in ("Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated"):
        assert send(ss, q)["duplicate"] is False
    assert where(ss) == (4, 3)
    for cursor in (2, 1, 0):
        assert send(ss, "Undo that")["duplicate"] is False
        assert where(ss)[1] == cursor
    for cursor in (1, 2, 3):
        assert send(ss, "Redo")["duplicate"] is False
        assert where(ss)[1] == cursor


def test_a_genuine_duplicate_is_still_suppressed_and_changes_nothing():
    ss = started()
    assert where(ss) == (1, 0)
    first = send(ss, "Change it to sixths")               # refused: nothing moves
    again = send(ss, "Change it to sixths")
    assert first["duplicate"] is False and again["duplicate"] is True
    assert where(ss) == (1, 0)
    assert where(ss) == (1, 0)


def test_an_exercise_request_sent_twice_is_still_a_duplicate():
    ss = started()
    assert send(ss, ASK_CHORDS)["duplicate"] is True
    assert where(ss) == (1, 0)


def test_an_undo_with_nothing_to_undo_is_not_replayed_either():
    ss = started()
    send(ss, "Undo that")                                  # at the first version already
    assert send(ss, "Undo that")["duplicate"] is True
    assert where(ss) == (1, 0)


def test_a_new_question_is_never_a_duplicate_and_ordinary_questions_keep_their_fingerprint():
    ss = started()
    send(ss, "Change it to fourths")
    out = send(ss, "What is a ii-V-I?")
    assert out["duplicate"] is False
    c = dict(ctx(), coach_page="practice")
    before = music_coach_semantic_fingerprint("What is a ii-V-I?", c)
    send(ss, "Undo that")
    assert music_coach_semantic_fingerprint("What is a ii-V-I?", c) == before       # no revision state leaks into other questions


def test_every_send_moves_the_widget_generation_so_a_rerun_cannot_resend():
    ss = session()
    send(ss, ASK_CHORDS)
    assert ss[GEN_KEY] == 1
    send(ss, "Change it to fourths")
    assert ss[GEN_KEY] == 2
    send(ss, "Change it to fourths")                        # already in fourths: refused, but still a consumed send
    assert ss[GEN_KEY] == 3


def test_revisions_never_reach_claude_even_with_enrichment_fully_enabled(monkeypatch, _count_api_calls):
    from music_coach_ami import claude_enrichment as ce
    from music_coach_ami.claude_settings import ClaudeSettings

    real = ce.load_claude_settings()
    on = ClaudeSettings(**{**real.__dict__, "master_enabled": True}) if hasattr(real, "__dict__") else real
    monkeypatch.setattr(ce, "load_claude_settings", lambda: on)
    ss = session()
    ss["_ami_claude_dev_mode"] = True
    ss["_ami_claude_dev_enabled"] = True
    send(ss, ASK_CHORDS)
    for q in ("Change it to fourths", "Make it more advanced", "Add chromatic approaches", "Make the rhythm more syncopated", "Undo that", "Redo"):
        send(ss, q)
    assert _count_api_calls == []
    assert not ss.get(ce.CACHE_KEY)

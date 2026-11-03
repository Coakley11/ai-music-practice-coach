"""AMI M1b-4: the experimental Claude *interpretation* layer — every case with a fake transport; no network, no key, no spend.

The contract under test:

* nothing is sent unless every gate is open (master + interpret switch + developer mode + developer toggle + priced model), and the deterministic
  answer stands whenever the layer is off, unavailable, over budget, or its proposal is rejected;
* Claude only chooses from a closed vocabulary; the proposal is validated (known operation, allowed argument, no conflicts, the player's "keep"
  respected, instrument supported, section on the chart) before any engine runs;
* the existing engines produce, verify and version the music, so rhythm/pitch/instrument contracts hold exactly as for typed requests;
* what is sent contains no notes, chords or account data; every request is in the ledger; an identical request is never charged twice.
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from music_coach_ami import claude_interpret as ci
from music_coach_ami import claude_settings as cset
from music_coach_ami import conversation_state as cs
from music_coach_ami import exercise_scale_pattern as sp
from music_coach_ami.claude_client import TransportError, TransportResult
from music_coach_ami.pipeline import run_coach_submit
from tests.test_ami_scale_pattern_recipe import (  # noqa: F401
    ASK_CHORDS,
    _no_live_api,
    assert_sound,
    begin,
    ctx,
    failed,
    rhythm_sig,
    session,
)

SECTIONS = ["Section A", "Section B"]


class Fake:
    """A scripted transport: records every call, answers from a queue (a string is the model's text, an Exception is raised)."""

    instances: list["Fake"] = []

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def __call__(self, api_key):            # used as the transport factory
        return self

    def complete(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, stop = reply if isinstance(reply, tuple) else (reply, "end_turn")
        return TransportResult(text=text, usage={"input_tokens": 700, "output_tokens": 60}, request_id=f"req_fake_{len(self.calls)}", stop_reason=stop,
                               model=kw["model"])


def reply(ops=(), keep=(), clarify="", confidence="high"):
    return json.dumps({"operations": [{"op": o, "arg": a} for o, a in ops], "keep": list(keep), "clarify": clarify, "confidence": confidence})


@pytest.fixture
def lab(monkeypatch, tmp_path):
    """The layer fully enabled, with a fake transport, a fake key and a temporary ledger."""
    monkeypatch.setenv("AMI_CLAUDE_LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    real = cset.load_claude_settings()
    on = cset.ClaudeSettings(**{**real.__dict__, "master_enabled": True, "interpret_enabled": True, "budget_usd": 1.0, "session_call_cap": 10})
    monkeypatch.setattr(cset, "load_claude_settings", lambda: on)
    monkeypatch.setattr(ci, "load_claude_settings", lambda: on)
    import anthropic_secrets_config as asc

    monkeypatch.setattr(asc, "resolve_anthropic_api_key", lambda: ("sk-ant-FAKE-NOT-A-KEY", None))
    fake = Fake([])
    monkeypatch.setattr(ci, "AnthropicTransport", fake)
    return fake, tmp_path / "ledger.jsonl", on


def open_session(name="Flute"):
    s, _resp, _inst = begin(ASK_CHORDS, name)
    s["_ami_claude_dev_mode"] = True
    s["_ami_claude_dev_enabled"] = True
    return s


def say(s, q, name="Flute", **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(instrument=name, **kw))[1]


def ex_of(s):
    return sp.GeneratedExercise.from_dict(copy.deepcopy(cs.current_version(s)["exercise"]))


def where(s):
    h = cs.history(s)
    return h["versions"], h["cursor"]


# ================================================================ gates
def test_nothing_is_sent_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AMI_CLAUDE_LEDGER_PATH", str(tmp_path / "l.jsonl"))
    fake = Fake([reply([("sync_less", "")])])
    monkeypatch.setattr(ci, "AnthropicTransport", fake)
    s, _r, _i = begin(ASK_CHORDS, "Flute")
    s["_ami_claude_dev_mode"], s["_ami_claude_dev_enabled"] = True, True
    n0 = where(s)
    resp = say(s, "Make it a little smoother")
    assert fake.calls == [] and where(s) == n0
    assert failed(resp) and "unchanged" in resp.direct_answer.lower()          # today's deterministic answer, exactly as before
    assert not (tmp_path / "l.jsonl").exists()


@pytest.mark.parametrize("closed", ["interpret_enabled", "master_enabled", "dev_mode", "dev_enabled"])
def test_each_gate_keeps_the_layer_shut(lab, closed):
    fake, ledger, cfg = lab
    s = open_session()
    if closed == "interpret_enabled":
        cfg2 = cset.ClaudeSettings(**{**cfg.__dict__, "interpret_enabled": False})
        import music_coach_ami.claude_interpret as m

        m.load_claude_settings = lambda: cfg2
    elif closed == "master_enabled":
        import music_coach_ami.claude_interpret as m

        cfg2 = cset.ClaudeSettings(**{**cfg.__dict__, "master_enabled": False})
        m.load_claude_settings = lambda: cfg2
    elif closed == "dev_mode":
        s["_ami_claude_dev_mode"] = False
    else:
        s["_ami_claude_dev_enabled"] = False
    fake.replies = [reply([("sync_less", "")])]
    say(s, "Make it a little smoother")
    assert fake.calls == []
    assert not ledger.exists()


def test_a_revision_the_rules_understand_never_calls_claude(lab):
    fake, ledger, _cfg = lab
    s = open_session()
    for q in ("Change it to fourths", "Make it faster", "Add chromatic approaches", "Make it suitable for alto saxophone", "Apply it to Section B",
              "Show me the guide tones", "Undo that", "Redo"):
        say(s, q)
    assert fake.calls == []


def test_a_fresh_exercise_request_never_calls_claude(lab):
    fake, _l, _c = lab
    s = open_session()
    say(s, "Give me a C major scale pattern")
    assert fake.calls == []


# ================================================================ a proposal is carried out by the engines
def test_a_vague_request_is_read_into_operations_and_executed(lab):
    fake, ledger, _c = lab
    fake.replies = [reply([("interval_advance", "")], keep=["rhythm"])]
    s = open_session()
    before = ex_of(s)
    resp = say(s, "Make that pattern a little more sophisticated, but keep the rhythm")
    assert len(fake.calls) == 1 and not failed(resp), resp.direct_answer[:300]
    after = ex_of(s)
    assert where(s) == (2, 1) and rhythm_sig(after.to_dict()) == rhythm_sig(before.to_dict())
    assert list(after.midi) != list(before.midi)
    assert "I read that as: more varied intervals" in resp.direct_answer
    assert_sound(after.to_dict())
    d = resp.diagnostics
    assert d["claude_interpretation"]["status"] == "accepted" and d["interpreted_ops"] == [["interval_advance", ""]]
    # undo is exact, as for any typed revision
    abc1 = cs.current_version(s)["abc"]
    say(s, "Undo that")
    assert ex_of(s).id == before.id
    say(s, "Redo")
    assert cs.current_version(s)["abc"] == abc1


def test_an_instrument_request_in_other_words(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("instrument", "tenor")])]
    s = open_session()
    resp = say(s, "I'd like the tenor sax edition of what you gave me")
    assert not failed(resp) and ex_of(s).context.notation_instrument == "Tenor Saxophone" and where(s) == (2, 1)
    assert "for tenor" in resp.direct_answer


def test_a_section_request_in_other_words(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("section", "Section B")])]
    s = open_session()
    resp = say(s, "Keep what you gave me, but make it more appropriate for the second part")
    assert not failed(resp) and ex_of(s).context.section == "Section B"


def test_an_explanation_in_other_words_changes_nothing(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("explain", "why_notes")])]
    s = open_session()
    n0 = where(s)
    resp = say(s, "Help me understand the thinking behind this exercise")
    assert len(fake.calls) == 1 and where(s) == n0
    assert resp.diagnostics.get("exercise_explanation") == "why_notes" and "I read that as: explain why notes" in resp.direct_answer


def test_a_combined_pattern_request_is_one_version(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("approach_more", ""), ("shape", "fourths")], keep=["tempo"])]
    s = open_session()
    resp = say(s, "Make it feel more adventurous, in the way a modern player might")
    assert not failed(resp) and where(s) == (2, 1)
    assert sp.recipe_of(ex_of(s)).shape == "fourths" and sp.recipe_of(ex_of(s)).has_chromatic()


# ================================================================ a proposal that breaks a rule is rejected, never guessed
@pytest.mark.parametrize("name, body", [
    ("keep rhythm but change it", reply([("sync_more", "")], keep=["rhythm"])),
    ("keep notes but change them", reply([("shape", "fourths")], keep=["notes"])),
    ("keep instrument but change it", reply([("instrument", "flute")], keep=["instrument"])),
    ("unknown operation", json.dumps({"operations": [{"op": "rewrite_everything", "arg": ""}], "keep": [], "clarify": "", "confidence": "high"})),
    ("bad argument", reply([("shape", "sevenths")])),
    ("argument for a no-argument op", reply([("wider", "a lot")])),
    ("unsupported instrument", reply([("instrument", "tuba")])),
    ("unknown section", reply([("section", "Bridge")])),
    ("conflicting ops", reply([("approach", "both"), ("approach_off", "")])),
    ("sync conflict", reply([("sync_more", ""), ("sync_less", "")])),
    ("two kinds at once", reply([("instrument", "alto"), ("shape", "fourths")])),
    ("too many ops", reply([("wider", ""), ("sync_more", ""), ("approach_more", ""), ("anticipate", "on")])),
    ("ops plus clarify", reply([("wider", "")], clarify="which_change")),
    ("extra fields", json.dumps({"operations": [], "keep": [], "clarify": "which_change", "confidence": "high", "notes": ["C", "E", "G"]})),
    ("not json", "Sure! Here are some notes: C D E F"),
    ("code fence", "```json\n" + reply([("wider", "")]) + "\n```"),
])
def test_invalid_proposals_change_nothing(lab, name, body):
    fake, ledger, _c = lab
    fake.replies = [body]
    s = open_session()
    n0, before = where(s), copy.deepcopy(cs.current_version(s))
    resp = say(s, "Make it a bit more interesting but keep it close to what you gave me")
    assert len(fake.calls) == 1 or name == "x"
    assert where(s) == n0 and cs.current_version(s) == before, name
    assert resp is None or failed(resp) or resp.diagnostics.get("exercise_revision_kind") != "interpreted" or not resp.diagnostics.get("generated_exercise_id")
    rows = [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]
    assert [r["type"] for r in rows] == ["reserve", "settle"]


def test_a_clarification_is_asked_without_changing_anything(lab):
    fake, _l, _c = lab
    fake.replies = [reply([], clarify="which_change", confidence="low")]
    s = open_session()
    n0 = where(s)
    resp = say(s, "Make it a little smoother")
    assert failed(resp) and "not sure which change" in resp.direct_answer and where(s) == n0
    assert resp.diagnostics["exercise_revision_failure_reason"] == "clarify:which_change"


def test_a_sentence_that_is_not_about_the_exercise_falls_through(lab):
    fake, _l, _c = lab
    fake.replies = [reply([], clarify="not_about_the_exercise")]
    s = open_session()
    resp = say(s, "Make it a point to practice daily")
    assert resp is None or not resp.diagnostics.get("exercise_revision_failure_reason", "").startswith("clarify")


@pytest.mark.parametrize("failure", [
    TransportError("timeout", error_type="APITimeoutError"), TransportError("client_error", error_type="BadRequestError", billed="no"),
    TransportError("rate_limit", error_type="RateLimitError", billed="no"), TransportError("server", error_type="InternalServerError"),
    ("", "refusal"), (reply([("wider", "")]), "max_tokens"),
])
def test_an_unavailable_or_failed_call_leaves_the_deterministic_answer(lab, failure):
    fake, _l, _c = lab
    fake.replies = [failure]
    s = open_session()
    n0 = where(s)
    resp = say(s, "Make it a bit more interesting but keep it close to what you gave me")
    assert where(s) == n0
    assert resp is None or failed(resp)
    assert len(fake.calls) == 1


def test_no_api_key_means_no_call(lab, monkeypatch):
    fake, ledger, _c = lab
    import anthropic_secrets_config as asc

    monkeypatch.setattr(asc, "resolve_anthropic_api_key", lambda: ("", None))
    s = open_session()
    say(s, "Make it a little smoother")
    assert fake.calls == [] and not ledger.exists()


def test_the_budget_stops_the_layer(lab):
    fake, ledger, cfg = lab
    import music_coach_ami.claude_interpret as m

    tiny = cset.ClaudeSettings(**{**cfg.__dict__, "budget_usd": 0.0})
    m.load_claude_settings = lambda: tiny
    fake.replies = [reply([("wider", "")])]
    s = open_session()
    n0 = where(s)
    say(s, "Make it a bit more interesting but keep it close to what you gave me")
    assert fake.calls == [] and where(s) == n0


# ================================================================ what is sent, and what it costs
def test_the_prompt_carries_no_notes_chords_or_account_data(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("wider", "")])]
    s = open_session()
    say(s, "Make it a little more interesting")
    sent = fake.calls[0]["user"] + fake.calls[0]["system"]
    assert not re.search(r"\b[A-G][b#]?(?:m|maj|min|dim|aug)?(?:7|9|11|13)\b", fake.calls[0]["user"]), "a chord symbol was sent"
    assert '"u1"' not in sent and "u1|" not in sent and "daniel" not in sent and "sk-ant" not in sent
    payload = json.loads(fake.calls[0]["user"].split("(JSON):\n", 1)[1].split("\n\nReturn", 1)[0])
    assert set(payload) == {"request", "exercise", "available_sections", "recent_requests"}
    assert set(payload["exercise"]) == {"kind", "instrument", "bars", "section", "recipe"}
    assert fake.calls[0]["schema"] == ci.INTERPRETATION_JSON_SCHEMA and fake.calls[0]["max_output_tokens"] <= 400


def test_every_request_is_in_the_ledger_and_an_identical_one_is_not_charged_twice(lab):
    fake, ledger, _c = lab
    fake.replies = [reply([("wider", "")])]
    s = open_session()
    say(s, "Make it a little more interesting")
    rows = [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]
    assert [r["type"] for r in rows] == ["reserve", "settle"]
    assert rows[1]["request_id"] == "req_fake_1" and rows[1]["cost_micro_usd"] > 0
    say(s, "Undo that")
    fake.replies = [reply([("wider", "")])]
    say(s, "Make it a little more interesting")             # same sentence, but the exercise is now a different version: a different request
    assert len(fake.calls) in (1, 2)
    n = len(fake.calls)
    say(s, "Undo that")
    say(s, "Make it a little more interesting")             # the same sentence on the same exercise: cached, free
    assert len(fake.calls) == n


def test_the_session_call_cap_is_enforced(lab):
    fake, ledger, cfg = lab
    import music_coach_ami.claude_interpret as m

    capped = cset.ClaudeSettings(**{**cfg.__dict__, "session_call_cap": 1})
    m.load_claude_settings = lambda: capped
    fake.replies = [reply([("wider", "")]), reply([("narrower", "")])]
    s = open_session()
    say(s, "Make it a little more interesting")
    say(s, "Make it a little more sophisticated please")
    assert len(fake.calls) == 1


def test_the_layer_is_isolated_per_account(lab):
    fake, _l, _c = lab
    fake.replies = [reply([("wider", "")])]
    a = open_session()
    say(a, "Make it a little more interesting")
    b = copy.deepcopy(a)
    b["_suite_auth_user_id"] = "u2"
    n = len(fake.calls)
    r = run_coach_submit("Make it a little more interesting", b, ami_ctx=ctx())[1]
    assert len(fake.calls) == n and (r is None or not r.diagnostics.get("generated_exercise_id"))

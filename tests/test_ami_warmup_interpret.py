"""AMI adaptive warmups: the experimental Claude *planning* layer — every case with a fake transport; no network, no key, no spend.

The contract under test mirrors the exercise interpretation layer's: nothing is sent unless every gate is open; Claude chooses only from a closed
vocabulary and the proposal is validated before any engine runs; the rules win wherever they found something explicit; the deterministic reading
stands whenever the layer is off, unavailable, over budget or rejected; what is sent contains no notes, keys, chords or account data.
"""

from __future__ import annotations

import json

import pytest

from music_coach_ami import claude_settings as cset
from music_coach_ami import warmup_interpret as wi
from music_coach_ami import warmup_plan as wp
from music_coach_ami.claude_client import TransportError, TransportResult
from tests.test_ami_warmups import ctx, plan_of, session  # noqa: F401


class Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def __call__(self, api_key):
        return self

    def complete(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, stop = reply if isinstance(reply, tuple) else (reply, "end_turn")
        return TransportResult(text=text, usage={"input_tokens": 600, "output_tokens": 70}, request_id=f"req_fake_{len(self.calls)}", stop_reason=stop, model=kw["model"])


def payload(**kw):
    base = {"families": [], "excluded": [], "intervals": [], "articulation": [], "minutes": 0, "level": "", "emphasis": [], "focus": "", "clarify": ""}
    base.update(kw)
    return json.dumps(base)


@pytest.fixture
def lab(monkeypatch, tmp_path):
    monkeypatch.setenv("AMI_CLAUDE_LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    real = cset.load_claude_settings()
    on = cset.ClaudeSettings(**{**real.__dict__, "master_enabled": True, "interpret_enabled": True, "budget_usd": 1.0, "session_call_cap": 10})
    monkeypatch.setattr(cset, "load_claude_settings", lambda: on)
    monkeypatch.setattr(wi, "load_claude_settings", lambda: on)
    import anthropic_secrets_config as asc

    monkeypatch.setattr(asc, "resolve_anthropic_api_key", lambda: ("sk-ant-FAKE-NOT-A-KEY", None))
    fake = Fake([])
    monkeypatch.setattr(wi, "AnthropicTransport", fake)
    return fake, tmp_path / "ledger.jsonl", on


def dev_session():
    s = session("Flute")
    s["_ami_claude_dev_mode"] = True
    s["_ami_claude_dev_enabled"] = True
    return s


class TestValidation:
    def ok(self, **kw):
        return wi.validate(json.loads(payload(**kw)))

    def test_a_clean_proposal_is_accepted(self):
        r = self.ok(families=["scale", "articulation"], excluded=["long_tones"], articulation=["two_note"], minutes=12, level="Advanced", emphasis=["articulation"],
                    focus="technique")
        assert r.ok and r.request["minutes"] == 12.0 and r.request["artic"] == ["two_note"]

    @pytest.mark.parametrize("kw,reason", [
        ({"families": ["scales"]}, "unknown_families"), ({"excluded": ["tonguing"]}, "unknown_excluded"), ({"intervals": ["ninths"]}, "unknown_intervals"),
        ({"articulation": ["double_tongue"]}, "unknown_articulation"), ({"families": ["scale"], "excluded": ["scale"]}, "family_both_included_and_excluded"),
        ({"minutes": 45}, "minutes_out_of_range"), ({"minutes": 1}, "minutes_out_of_range"), ({"level": "Expert"}, "unknown_level"), ({"focus": "jazz"}, "unknown_focus"),
        ({"families": ["scale"], "intervals": ["thirds"]}, "intervals_without_the_intervals_family"),
        ({"families": ["scale"], "emphasis": ["scale"], "excluded": []}, None), ({"emphasis": ["scale"], "excluded": ["scale"]}, "emphasis_on_an_excluded_family"),
        ({"families": ["scale", "scale"]}, "duplicate_families")])
    def test_rejections(self, kw, reason):
        r = self.ok(**kw)
        if reason is None:
            assert r.ok
        else:
            assert not r.ok and r.reason.startswith(reason), r.reason

    def test_extra_fields_and_non_objects_are_rejected(self):
        assert wi.validate({**json.loads(payload()), "notes": "C D E"}).reason.startswith("unknown_fields")
        assert wi.validate(["x"]).reason == "not_an_object"
        assert wi.validate({**json.loads(payload()), "minutes": "ten"}).reason == "bad_minutes"
        assert wi.validate({**json.loads(payload()), "minutes": True}).reason == "bad_minutes"

    def test_clarifications_are_not_plans(self):
        assert wi.validate(json.loads(payload(clarify="not_a_warmup"))).clarify == "not_a_warmup"
        assert not wi.validate(json.loads(payload(clarify="which_instrument"))).ok

    def test_the_schema_has_only_the_closed_vocabulary(self):
        props = wi.WARMUP_JSON_SCHEMA["properties"]
        assert set(props["families"]["items"]["enum"]) == {"long_tones", "scale", "intervals", "articulation"}
        assert not any(k in props for k in ("notes", "key", "chords", "tempo", "pitches"))
        assert wi.WARMUP_JSON_SCHEMA["additionalProperties"] is False


class TestMerging:
    def test_the_rules_win_where_they_found_something(self):
        parsed = wp.parse_request("Give me a five-minute flute scale warmup")
        interp = wi.validate(json.loads(payload(families=["long_tones"], minutes=20, level="Beginner")))
        merged = wi.merge_into(parsed, interp)
        assert merged["families"] == ["scale"] and merged["minutes"] == 5.0 and merged["level"] == "Beginner"

    def test_claude_fills_what_the_rules_left_empty_and_exclusions_accumulate(self):
        parsed = wp.parse_request("Give me a warmup, skip the scales")
        interp = wi.validate(json.loads(payload(families=["long_tones", "articulation"], excluded=["intervals"], minutes=8, emphasis=["articulation"])))
        merged = wi.merge_into(parsed, interp)
        assert merged["families"] == ["long_tones", "articulation"] and set(merged["excluded"]) == {"scale", "intervals"} and merged["minutes"] == 8.0
        assert merged["more"] == {"articulation": 1.6}

    def test_where_the_rules_read_a_family_they_win_but_claudes_exclusions_still_apply(self):
        parsed = wp.parse_request("Something to get my tongue ready, short on scales")      # the rules hear 'scales' as a wish
        assert parsed["families"] == ["scale", "articulation"]
        merged = wi.merge_into(parsed, wi.validate(json.loads(payload(families=["long_tones", "articulation"], excluded=["scale"]))))
        assert merged["families"] == ["articulation"] and merged["excluded"] == ["scale"]

    def test_a_rejected_proposal_changes_nothing(self):
        parsed = wp.parse_request("Give me a warmup")
        assert wi.merge_into(parsed, wi.validate({"families": ["nope"]})) == parsed


class TestTheLayerEndToEnd:
    def test_gates_closed_nothing_is_sent(self, lab):
        fake, _ledger, _cfg = lab
        interp, rec = wi.interpret("Give me a warmup", "Intermediate", session("Flute"))        # not developer mode
        assert interp is None and rec["status"] == "skipped" and fake.calls == []

    def test_an_accepted_interpretation_builds_a_warmup_the_engines_verified(self, lab):
        fake, ledger, _ = lab
        fake.replies = [payload(families=["long_tones", "articulation"], excluded=["scale"], minutes=8, emphasis=["articulation"], clarify="")]
        s = dev_session()
        q = "Something quick before the gig, easy on the scales"
        interp, rec = wi.interpret(q, "Intermediate", s)
        assert rec["status"] == "accepted" and interp.ok and len(fake.calls) == 1 and rec["request_id"] == "req_fake_1"
        merged = wi.merge_into(wp.parse_request(q), interp)
        resp = wp.create(q, s, ctx(), request=merged)
        plan = plan_of(s)
        assert {r["family"] for r in plan["items"]} == {"long_tones", "articulation"} and plan["minutes"] == 8.0
        assert "scale" in merged["excluded"]
        assert abs(plan["total_seconds"] - 480) <= 60 and not resp.diagnostics.get("warmup_failed")
        rows = [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]
        assert [r["type"] for r in rows] == ["reserve", "settle"] and rows[-1]["status"] == "accepted"

    def test_what_is_sent_contains_only_the_sentence_and_the_level(self, lab):
        fake, _ledger, _ = lab
        fake.replies = [payload()]
        wi.interpret("Give me a warmup for my tenor sax", "Advanced", dev_session())
        sent = fake.calls[0]
        text = sent["user"]
        assert json.loads(text.split("REQUEST (JSON):\n", 1)[1].split("\n\nReturn", 1)[0]) == {"sentence": "Give me a warmup for my tenor sax", "level_on_the_page": "Advanced"}
        assert "u1" not in text and "daniel" not in text and sent["schema"] is wi.WARMUP_JSON_SCHEMA

    def test_the_same_sentence_is_never_charged_twice(self, lab):
        fake, ledger, _ = lab
        fake.replies = [payload(minutes=6)]
        s = dev_session()
        wi.interpret("a six minute one", "Intermediate", s)
        interp, rec = wi.interpret("a six minute one", "Intermediate", s)
        assert len(fake.calls) == 1 and rec["cache_hit"] and rec["cost_usd"] == 0.0 and interp.ok

    @pytest.mark.parametrize("reply,status", [("not json", "invalid_json"), (("{}", "max_tokens"), "incomplete:max_tokens"), (("{}", "refusal"), "refusal"),
                                              (payload(families=["scale"], excluded=["scale"]), "rejected")])
    def test_bad_answers_never_reach_the_engines(self, lab, reply, status):
        fake, _ledger, _ = lab
        fake.replies = [reply]
        interp, rec = wi.interpret("Give me a warmup", "Intermediate", dev_session())
        assert rec["status"] == status and (interp is None or not interp.ok)

    def test_an_api_error_falls_back_to_the_rules(self, lab):
        fake, _ledger, _ = lab
        fake.replies = [TransportError("timeout", error_type="Timeout", billed="no")]
        s = dev_session()
        interp, rec = wi.interpret("Give me a warmup", "Intermediate", s)
        assert interp is None and rec["status"].startswith("api_error")
        resp = wp.create("Give me a warmup", s, ctx())
        assert not resp.diagnostics.get("warmup_failed")

    def test_over_budget_refuses_before_sending(self, lab, monkeypatch):
        fake, _ledger, cfg = lab
        monkeypatch.setattr(wi, "load_claude_settings", lambda: cset.ClaudeSettings(**{**cfg.__dict__, "budget_usd": 0.0}))
        interp, rec = wi.interpret("Give me a warmup", "Intermediate", dev_session())
        assert interp is None and rec["status"] == "refused" and fake.calls == []

    def test_the_layer_is_not_called_by_the_live_warmup_path(self, lab):
        fake, _ledger, _ = lab
        s = dev_session()
        for q in ("Give me a warmup", "Make it shorter", "Undo that", "Next exercise"):
            from music_coach_ami.pipeline import run_coach_submit

            run_coach_submit(q, s, ami_ctx=ctx())
        assert fake.calls == []

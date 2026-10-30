"""Claude enrichment orchestration with mocked transports. No network, ever."""

from __future__ import annotations

import json

import pytest

from music_coach_ami import claude_enrichment as ce
from music_coach_ami import claude_usage as cu
from music_coach_ami.claude_client import AnthropicTransport, TransportError
from music_coach_ami.types import CoachIntent
from tests.claude_enrichment_fixtures import (
    CHART,
    FAKE_KEY,
    GOOD_PAYLOAD,
    FakeTransport,
    make_req,
    make_resp,
    make_settings,
)


@pytest.fixture(autouse=True)
def _no_live_api_and_isolated_ledger(tmp_path, monkeypatch):
    def _boom(self, **kwargs):
        raise AssertionError("LIVE API CALL ATTEMPTED IN TEST")

    monkeypatch.setattr(AnthropicTransport, "complete", _boom)
    monkeypatch.setenv(cu.LEDGER_ENV, str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(
        "anthropic_secrets_config.resolve_anthropic_api_key", lambda: (FAKE_KEY, object())
    )
    return tmp_path / "ledger.jsonl"


def _state(**kw):
    s = {"_ami_claude_dev_mode": True, "ami_claude_dev_enabled": True}
    s.update(kw)
    return s


def _run(transport, *, state=None, settings=None, req=None, resp=None):
    state = _state() if state is None else state
    resp = make_resp() if resp is None else resp
    out = ce.maybe_enrich_song_coaching(
        req or make_req(), resp, state, transport_factory=transport.factory(), settings=settings or make_settings()
    )
    return out, state


def _ledger(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_disabled_by_default_leaves_everything_untouched(monkeypatch):
    monkeypatch.setattr("music_coach_ami.claude_settings._secret_value", lambda name: "")
    resp = make_resp()
    before = (resp.composed_markdown(), dict(resp.diagnostics))

    def factory(_k):
        raise AssertionError("transport must not even be constructed")

    out = ce.maybe_enrich_song_coaching(make_req(), resp, _state(), transport_factory=factory)
    assert (out.composed_markdown(), out.diagnostics) == before and out.enrichment is None


@pytest.mark.parametrize(
    "state",
    [{}, {"_ami_claude_dev_mode": True}, {"ami_claude_dev_enabled": True}, {"_ami_claude_dev_mode": False, "ami_claude_dev_enabled": True}],
)
def test_requires_developer_mode_and_toggle(state, _no_live_api_and_isolated_ledger):
    t = FakeTransport()
    out, _ = _run(t, state=state)
    assert t.calls == [] and out.enrichment is None
    assert not _no_live_api_and_isolated_ledger.exists()


def test_accepted_enrichment_is_appended_without_changing_deterministic_answer(_no_live_api_and_isolated_ledger):
    baseline = make_resp().composed_markdown()
    t = FakeTransport()
    out, state = _run(t)
    assert len(t.calls) == 1 and out.enrichment is not None
    md = out.composed_markdown()
    assert md.startswith(baseline) and len(md) > len(baseline)
    assert "AI-assisted" in md and "**Dm7**" in md
    assert out.direct_answer == make_resp().direct_answer
    assert out.practice_steps == make_resp().practice_steps
    rec = out.diagnostics["ai_enrichment"]
    assert rec["status"] == "accepted" and rec["request_id"] == "req_fake_001"
    assert rec["cost_usd"] == 0.0064 and rec["usage"]["input_tokens"] == 1200
    kinds = [r["type"] for r in _ledger(_no_live_api_and_isolated_ledger)]
    assert kinds == ["reserve", "settle"]


def test_call_uses_configured_model_effort_and_no_sdk_retries_param(_no_live_api_and_isolated_ledger):
    t = FakeTransport()
    _run(t, settings=make_settings(max_output_tokens=900, effort="medium", timeout_s=7.0))
    call = t.calls[0]
    assert call["model"] == "claude-sonnet-5-5" and call["max_output_tokens"] == 900
    assert call["effort"] == "medium" and call["timeout_s"] == 7.0
    assert "FACTS" in call["user"] and "Dm7" in call["user"]
    assert FAKE_KEY not in call["user"] and FAKE_KEY not in call["system"]


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"payload": {**GOOD_PAYLOAD, "guidance": ["Play {{chord:Fm7}} loudly.", "Loop it."]}}, "rejected"),
        ({"text": "not json at all"}, "invalid_json"),
        ({"text": ""}, "invalid_json"),
        ({"stop_reason": "refusal"}, "refusal"),
        ({"stop_reason": "max_tokens"}, "incomplete:max_tokens"),
    ],
)
def test_unverified_or_incomplete_output_never_replaces_or_extends_answer(kwargs, status, _no_live_api_and_isolated_ledger):
    baseline = make_resp().composed_markdown()
    out, _ = _run(FakeTransport(**kwargs))
    assert out.enrichment is None and out.composed_markdown() == baseline
    rec = out.diagnostics["ai_enrichment"]
    assert rec["status"] == status
    settled = [r for r in _ledger(_no_live_api_and_isolated_ledger) if r["type"] == "settle"]
    assert len(settled) == 1 and settled[0]["cost_micro_usd"] == 6400  # tokens were consumed, so they are billed
    if status == "rejected":
        assert "chord_not_in_facts:Fm7" in rec["violations"]


def test_billing_unknown_failure_is_charged_at_worst_case(_no_live_api_and_isolated_ledger):
    t = FakeTransport(error=TransportError("timeout", error_type="APITimeoutError", billed="unknown"))
    baseline = make_resp().composed_markdown()
    out, _ = _run(t)
    assert out.composed_markdown() == baseline
    settle = [r for r in _ledger(_no_live_api_and_isolated_ledger) if r["type"] == "settle"][0]
    reserve = [r for r in _ledger(_no_live_api_and_isolated_ledger) if r["type"] == "reserve"][0]
    assert settle["cost_micro_usd"] == reserve["worst_case_micro_usd"] > 0


def test_provably_unbilled_failure_releases_reservation(_no_live_api_and_isolated_ledger):
    t = FakeTransport(error=TransportError("client_error", error_type="AuthenticationError", billed="no"))
    out, _ = _run(t)
    assert out.enrichment is None
    assert [r["type"] for r in _ledger(_no_live_api_and_isolated_ledger)] == ["reserve", "release"]
    assert cu.usage_summary(make_settings(), "x")["committed_usd"] == 0


def test_streamlit_rerun_does_not_charge_twice(_no_live_api_and_isolated_ledger):
    t = FakeTransport()
    state = _state()
    first, _ = _run(t, state=state)
    second, _ = _run(t, state=state, resp=make_resp())
    assert len(t.calls) == 1
    assert second.enrichment == first.enrichment
    assert second.diagnostics["ai_enrichment"]["cache_hit"] is True
    assert second.diagnostics["ai_enrichment"]["cost_usd"] == 0.0
    assert len(_ledger(_no_live_api_and_isolated_ledger)) == 2


def test_rejected_result_is_cached_too_so_reruns_do_not_retry_and_rebill(_no_live_api_and_isolated_ledger):
    t = FakeTransport(text="garbage")
    state = _state()
    _run(t, state=state)
    _run(t, state=state)
    assert len(t.calls) == 1


def test_unresolved_inflight_duplicate_is_refused(_no_live_api_and_isolated_ledger):
    t1 = FakeTransport()
    state = _state(_ami_claude_sid="sess-1")
    facts, _ = ce.build_fact_sheet(make_req(), make_resp())
    cu.reserve_budget(
        make_settings(), session_id="sess-1", fingerprint=facts.fingerprint("claude-sonnet-5-5"),
        intent="song_coaching", model="claude-sonnet-5-5", worst_case_micro_usd=20_000,
    )
    out, _ = _run(t1, state=state)
    assert t1.calls == [] and out.diagnostics["ai_enrichment"]["reason"] == "duplicate_inflight"


def test_per_session_cap_and_budget_are_enforced_across_calls(_no_live_api_and_isolated_ledger):
    t = FakeTransport()
    cap = make_settings(session_call_cap=1)
    state = _state()
    _run(t, state=state, settings=cap)
    other = make_req(chart={**CHART, "chart_sections": {"Verse": ["Em7", "A7"]}})
    out, _ = _run(t, state=state, settings=cap, req=other)
    assert len(t.calls) == 1 and out.diagnostics["ai_enrichment"]["reason"] == "session_call_cap"

    tiny = make_settings(budget_usd=0.001)
    out, _ = _run(FakeTransport(), state=_state(), settings=tiny)
    assert out.diagnostics["ai_enrichment"]["reason"] == "budget_exhausted"


def test_corrupt_ledger_blocks_the_call(_no_live_api_and_isolated_ledger):
    _no_live_api_and_isolated_ledger.write_text("corrupt\n", encoding="utf-8")
    t = FakeTransport()
    baseline = make_resp().composed_markdown()
    out, _ = _run(t)
    assert t.calls == [] and out.composed_markdown() == baseline
    assert out.diagnostics["ai_enrichment"]["reason"].startswith("ledger_unavailable")


def test_unwritable_ledger_blocks_the_call(tmp_path, monkeypatch):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv(cu.LEDGER_ENV, str(blocker / "ledger.jsonl"))
    t = FakeTransport()
    out, _ = _run(t)
    assert t.calls == [] and out.diagnostics["ai_enrichment"]["reason"].startswith("ledger_unavailable")


def test_ledger_failure_after_response_keeps_reservation_counted(_no_live_api_and_isolated_ledger, monkeypatch):
    def broken_settle(*a, **k):
        raise cu.LedgerError("append_failed")

    monkeypatch.setattr(ce, "settle", broken_settle)
    out, _ = _run(FakeTransport())
    assert out.diagnostics["ai_enrichment"]["ledger_degraded"] is True
    assert cu.usage_summary(make_settings(), "x")["unresolved_reservations"] == 1  # still counted, fail closed


def test_missing_key_means_no_call(monkeypatch):
    monkeypatch.setattr("anthropic_secrets_config.resolve_anthropic_api_key", lambda: ("", object()))
    t = FakeTransport()
    out, _ = _run(t)
    assert t.calls == [] and out.diagnostics["ai_enrichment"]["reason"] == "no_api_key"


def test_sdk_not_installed_falls_back(monkeypatch):
    def missing(_key):
        raise TransportError("sdk_unavailable", billed="no")

    out = ce.maybe_enrich_song_coaching(make_req(), make_resp(), _state(), transport_factory=missing, settings=make_settings())
    assert out.enrichment is None and out.diagnostics["ai_enrichment"]["reason"] == "sdk_unavailable"


@pytest.mark.parametrize(
    ("req", "reason"),
    [
        (make_req(intent=CoachIntent.PRACTICE_PLAN), "intent_not_supported"),
        (make_req(chart={**CHART, "chart_available": False}), "no_verified_chart"),
        (make_req(chart={**CHART, "sections_in_practice_key": False}), "chart_not_in_practice_key"),
    ],
)
def test_unverified_context_skips_enrichment(req, reason):
    t = FakeTransport()
    out, _ = _run(t, req=req)
    assert t.calls == [] and out.diagnostics["ai_enrichment"]["reason"] == reason


def test_section_missing_from_chart_skips():
    t = FakeTransport()
    out, _ = _run(t, resp=make_resp(section="Bridge"))
    assert t.calls == [] and out.diagnostics["ai_enrichment"]["reason"] == "section_not_in_chart"


@pytest.mark.parametrize("label", ["Full Song", "full song"])
def test_full_song_target_means_no_specific_section_not_a_skip(label):
    facts, reason = ce.build_fact_sheet(make_req(), make_resp(section=label))
    assert reason == "ok" and facts is not None and facts.section == ""
    assert {n for n, _c in facts.sections} == {"Verse", "Chorus"}
    t = FakeTransport()
    out, _ = _run(t, resp=make_resp(section=label))
    assert len(t.calls) == 1 and out.enrichment is not None


def test_ungrounded_answer_skips():
    t = FakeTransport()
    out, _ = _run(t, resp=make_resp(grounded=False))
    assert t.calls == [] and out.diagnostics["ai_enrichment"]["reason"] == "not_song_grounded"


def test_internal_bug_never_breaks_the_answer(monkeypatch):
    monkeypatch.setattr(ce, "build_fact_sheet", lambda *a, **k: 1 / 0)
    baseline = make_resp().composed_markdown()
    out, _ = _run(FakeTransport())
    assert out.composed_markdown() == baseline
    assert out.diagnostics["ai_enrichment"]["status"] == "internal_error"


def test_secrets_never_reach_diagnostics_ledger_or_markdown(_no_live_api_and_isolated_ledger):
    out, state = _run(FakeTransport())
    blob = json.dumps(out.diagnostics) + json.dumps(state, default=str) + out.composed_markdown()
    blob += _no_live_api_and_isolated_ledger.read_text(encoding="utf-8")
    assert FAKE_KEY not in blob and "sk-ant" not in blob


def test_pipeline_hook_is_wired_and_off_by_default(monkeypatch):
    from music_coach_ami import pipeline

    req, resp = make_req(), make_resp()
    monkeypatch.setattr(pipeline, "route_question", lambda *a, **k: req)
    monkeypatch.setitem(pipeline.SOLVER_REGISTRY, CoachIntent.SONG_COACHING, lambda r: resp)
    monkeypatch.setattr("music_coach_ami.claude_settings._secret_value", lambda name: "")
    _, out = pipeline.run_coach_submit("practice the verse", {})
    assert out.enrichment is None and "ai_enrichment" not in out.diagnostics

    t = FakeTransport()
    monkeypatch.setattr(ce, "AnthropicTransport", lambda key: t)
    monkeypatch.setattr(ce, "load_claude_settings", lambda: make_settings())
    state = _state()
    _, out = pipeline.run_coach_submit("practice the verse", state)
    assert out.enrichment is not None and len(t.calls) == 1

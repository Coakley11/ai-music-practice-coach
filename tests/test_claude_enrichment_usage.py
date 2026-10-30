"""Usage ledger: exact costs, reserve/settle accounting, concurrency, and fail-closed behaviour."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from music_coach_ami import claude_usage as cu
from tests.claude_enrichment_fixtures import make_settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv(cu.LEDGER_ENV, str(path))
    return path


def _reserve(settings=None, *, sid="s1", fp="f1", worst=10_000):
    return cu.reserve_budget(
        settings or make_settings(),
        session_id=sid,
        fingerprint=fp,
        intent="song_coaching",
        model="claude-sonnet-5-5",
        worst_case_micro_usd=worst,
    )


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cost_is_exact_and_rounded_up():
    usage = {"input_tokens": 1000, "output_tokens": 500, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 3}
    # 1000*2 + 500*10 + 10*0.10 + 3*2.50 = 7008.5 micro-USD -> 7009
    assert cu.compute_cost_micro_usd("claude-sonnet-5-5", usage) == 7009


def test_worst_case_bounds_realistic_cost():
    worst = cu.estimate_worst_case_micro_usd("claude-sonnet-5-5", prompt_chars=4000, max_output_tokens=1500)
    actual = cu.compute_cost_micro_usd("claude-sonnet-5-5", {"input_tokens": 1500, "output_tokens": 1500})
    assert worst >= actual
    assert worst < 50_000  # a single call stays well under 5 cents


def test_unpriced_model_fails_closed():
    with pytest.raises(cu.LedgerError):
        cu.compute_cost_micro_usd("claude-mystery-9", {"input_tokens": 1})


def test_reserve_then_settle_updates_committed_cost(ledger):
    res = _reserve(worst=30_000)
    state = cu._summarize(cu._read_records(ledger), session_id="s1", fingerprint="x", now=0)
    assert state.committed_micro_usd == 30_000 and state.unresolved == 1
    cost = cu.settle(res, model="claude-sonnet-5-5", usage={"input_tokens": 1000, "output_tokens": 500},
                     request_id="req_1", status="accepted")
    assert cost == 7000
    state = cu._summarize(cu._read_records(ledger), session_id="s1", fingerprint="x", now=0)
    assert state.committed_micro_usd == 7000 and state.unresolved == 0 and state.session_calls == 1


def test_release_returns_budget_and_session_slot(ledger):
    res = _reserve(worst=30_000)
    cu.release(res, status="api_error:client_error", error_type="AuthenticationError")
    state = cu._summarize(cu._read_records(ledger), session_id="s1", fingerprint="x", now=0)
    assert state.committed_micro_usd == 0 and state.session_calls == 0


def test_unresolved_reservation_stays_counted_at_worst_case(ledger):
    _reserve(worst=1_000_000)  # simulates a crash between reserve and settle
    with pytest.raises(cu.BudgetRefused) as exc:
        _reserve(make_settings(budget_usd=1.5), fp="other", worst=600_000)
    assert exc.value.reason == "budget_exhausted"


def test_budget_is_cumulative_and_capped(ledger):
    s = make_settings(budget_usd=0.05)
    r = _reserve(s, worst=30_000)
    cu.settle(r, model="claude-sonnet-5-5", usage={"input_tokens": 5000, "output_tokens": 1500}, request_id="", status="accepted")
    # settled 5000*2 + 1500*10 = 25_000; another 30_000 worst case would reach 55_000 > 50_000
    with pytest.raises(cu.BudgetRefused) as exc:
        _reserve(s, fp="f2", worst=30_000)
    assert exc.value.reason == "budget_exhausted"


def test_application_budget_ceiling_is_five_dollars():
    from music_coach_ami import claude_settings as cs

    assert cs.HARD_BUDGET_CEILING_USD == 5.0
    assert cs._as_float("500", 5.0, 0.0, cs.HARD_BUDGET_CEILING_USD) == 5.0


def test_session_call_cap(ledger):
    s = make_settings(session_call_cap=2)
    _reserve(s, fp="a")
    _reserve(s, fp="b")
    with pytest.raises(cu.BudgetRefused) as exc:
        _reserve(s, fp="c")
    assert exc.value.reason == "session_call_cap"
    _reserve(s, sid="other-session", fp="c")  # cap is per session


def test_zero_cap_and_zero_budget_always_refuse(ledger):
    with pytest.raises(cu.BudgetRefused):
        _reserve(make_settings(session_call_cap=0))
    with pytest.raises(cu.BudgetRefused):
        _reserve(make_settings(budget_usd=0.0))


def test_duplicate_inflight_same_session_and_fingerprint(ledger):
    _reserve(fp="same")
    with pytest.raises(cu.BudgetRefused) as exc:
        _reserve(fp="same")
    assert exc.value.reason == "duplicate_inflight"


@pytest.mark.parametrize(
    "content",
    [
        "{not json}\n",
        '{"v":1,"type":"reserve","rid":"a","ts_epoch":1,"worst_case_micro_usd":5}',  # truncated tail (no newline)
        '{"v":2,"type":"reserve","rid":"a","ts_epoch":1,"worst_case_micro_usd":5}\n',
        '{"v":1,"type":"reserve","rid":"a","ts_epoch":1,"worst_case_micro_usd":-5}\n',
        '{"v":1,"type":"settle","rid":"ghost","ts_epoch":1,"cost_micro_usd":5}\n',
    ],
)
def test_corrupt_or_inconsistent_ledger_fails_closed(ledger, content):
    ledger.write_text(content, encoding="utf-8")
    with pytest.raises(cu.LedgerError):
        _reserve()


def test_unreadable_ledger_fails_closed(ledger):
    ledger.mkdir()  # a directory where the file should be: cannot be read
    with pytest.raises(cu.LedgerError):
        _reserve()


def test_unwritable_ledger_fails_closed(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    monkeypatch.setenv(cu.LEDGER_ENV, str(blocker / "ledger.jsonl"))
    with pytest.raises(cu.LedgerError):
        _reserve()


def test_usage_summary_reports_unavailable_instead_of_raising(ledger):
    ledger.write_text("garbage\n", encoding="utf-8")
    summary = cu.usage_summary(make_settings(), "s1")
    assert summary["ok"] is False


def test_ledger_never_stores_prompt_text_or_secrets(ledger):
    r = _reserve()
    cu.settle(r, model="claude-sonnet-5-5", usage={"input_tokens": 10, "output_tokens": 5},
              request_id="req_abc", status="accepted", violations=("chord_not_in_facts:Fm7",))
    raw = ledger.read_text(encoding="utf-8")
    assert "sk-ant" not in raw
    assert set(json.loads(raw.splitlines()[-1])) <= {
        "v", "ts", "ts_epoch", "type", "rid", "model", "request_id", "status", "violations", "usage", "cost_micro_usd",
    }


def test_threads_cannot_overspend(ledger):
    s = make_settings(budget_usd=5.0, session_call_cap=50)
    results: list[str] = []

    def attempt(i: int) -> None:
        try:
            _reserve(s, fp=f"fp{i}", worst=1_000_000)
            results.append("ok")
        except cu.BudgetRefused:
            results.append("refused")

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 5 and results.count("refused") == 7


_CHILD = """
import sys
from music_coach_ami import claude_usage as cu
from tests.claude_enrichment_fixtures import make_settings
try:
    cu.reserve_budget(make_settings(budget_usd=5.0, session_call_cap=50), session_id="proc" + sys.argv[1],
                      fingerprint="fp" + sys.argv[1], intent="song_coaching", model="claude-sonnet-5-5",
                      worst_case_micro_usd=1_000_000)
    print("ok")
except cu.BudgetRefused:
    print("refused")
"""


def test_separate_processes_cannot_overspend(ledger):
    env = {**__import__("os").environ, cu.LEDGER_ENV: str(ledger), "PYTHONPATH": str(REPO_ROOT)}
    procs = [
        subprocess.Popen([sys.executable, "-c", _CHILD, str(i)], cwd=REPO_ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for i in range(10)
    ]
    outs = [p.communicate(timeout=120)[0].strip() for p in procs]
    assert outs.count("ok") == 5, outs
    assert outs.count("refused") == 5, outs
    assert len(_records(ledger)) == 5

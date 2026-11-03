"""Controlled live experiment for Claude-assisted warmup PLANNING: does Claude read sentences the fixed warmup rules do not?

Two modes:

  DRY (default)        python scripts/ami_warmup_planning_experiment.py
                       For every corpus sentence: what the fixed rules read, the warmup they build, and whether it meets the sentence's checks;
                       the size and worst-case cost of what WOULD be sent. No network, no spend.

  LIVE                 AMI_WARMUP_LIVE=1 python scripts/ami_warmup_planning_experiment.py --approve-spend
                       Uses the DIRECT Anthropic Messages API (anthropic SDK, no retries) through AMI's own transport with the owner's
                       ANTHROPIC_API_KEY (environment / Streamlit secrets, never printed) behind hard limits: at most MAX_REQUESTS requests and
                       MAX_USD of recorded cost, abort on the first unexpected API outcome or any request above PER_REQUEST_USD.
                       Every request is in a dedicated AMI usage-ledger file with its request id and token usage. It never uses Claude Code,
                       the Agent SDK, a launcher or a subscription login.

Claude proposes a closed-vocabulary plan request; ``warmup_interpret.validate`` rejects anything outside it and ``warmup_plan.create`` (the
deterministic planner and engines) builds, verifies and times every exercise. Claude never supplies notes, durations, keys, chords or transpositions.

Scoring is deterministic and identical for both conditions ("rules only" and "rules + Claude"): each sentence has checks on the warmup that is
actually built (families, level, length, intervals, time shares, variety). A sentence that asks for a *revision* of an existing warmup is also sent,
because it shows what the closed vocabulary cannot express.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import warnings
from typing import Any

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

MAX_REQUESTS = 10
MAX_USD = 0.20                 # application-level ceiling (the owner's authorization of 2026-11-02)
PER_REQUEST_USD = 0.03
LIVE = os.environ.get("AMI_WARMUP_LIVE") == "1" and "--approve-spend" in sys.argv
TAG = "warmup_live" if LIVE else "warmup_dry"
OUT = pathlib.Path(os.environ.get("AMI_WARMUP_OUT", ROOT / "data" / "experiments"))
OUT.mkdir(parents=True, exist_ok=True)
os.environ["AMI_CLAUDE_ENABLED"] = "true"
os.environ["AMI_CLAUDE_INTERPRET_ENABLED"] = "true"
os.environ["AMI_CLAUDE_BUDGET_USD"] = str(MAX_USD)
os.environ["AMI_CLAUDE_SESSION_CALL_CAP"] = str(MAX_REQUESTS)
os.environ["AMI_CLAUDE_LEDGER_PATH"] = str(OUT / f"{TAG}_ledger.jsonl")

from music_coach_ami import warmup_engine as we  # noqa: E402
from music_coach_ami import warmup_interpret as wi  # noqa: E402
from music_coach_ami import warmup_plan as wp  # noqa: E402
from music_coach_ami.claude_client import AnthropicTransport, TransportError  # noqa: E402
from music_coach_ami.claude_settings import load_claude_settings  # noqa: E402
from music_coach_ami.claude_usage import estimate_worst_case_micro_usd  # noqa: E402


# ---------------------------------------------------------------- the corpus and its deterministic checks

def _fam(plan: dict) -> list[str]:
    return [r["family"] for r in plan["items"]]


def _secs(plan: dict, family: str) -> float:
    return sum(r["seconds"] for r in plan["items"] if r["family"] == family)


def _share(plan: dict, family: str) -> float:
    total = sum(r["seconds"] for r in plan["items"]) or 1.0
    return _secs(plan, family) / total


def _variety(plan: dict) -> int:
    return len({(r["family"], str(r["params"].get("interval") or r["params"].get("pattern") or ""), r["bpm"], r["bars"]) for r in plan["items"]})


def _total(plan: dict) -> float:
    return sum(r["seconds"] for r in plan["items"]) + (len(plan["items"]) - 1) * plan["transition_seconds"]


def _widths(plan: dict) -> list[int]:
    return [we.INTERVALS[r["params"]["interval"]] for r in plan["items"] if r["family"] == "intervals"]


CORPUS: list[dict[str, Any]] = [
    {"id": "S1", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "Give me an advanced flute warmup emphasizing articulation but not scales.",
     "checks": {"level is Advanced": lambda p: p["level"] == "Advanced", "no scales": lambda p: "scale" not in _fam(p),
                "articulation present": lambda p: "articulation" in _fam(p),
                "articulation is the largest share": lambda p: _secs(p, "articulation") == max(_secs(p, f) for f in set(_fam(p)))}},
    {"id": "S2", "kind": "plan", "instrument": "Saxophone", "level": "Intermediate",
     "q": "Prepare a ten-minute saxophone warmup with long tones and increasingly difficult intervals.",
     "checks": {"about ten minutes": lambda p: abs(_total(p) - 600) <= 48, "long tones present": lambda p: "long_tones" in _fam(p),
                "intervals present": lambda p: "intervals" in _fam(p),
                "intervals widen (never narrower again)": lambda p: len(_widths(p)) >= 2 and _widths(p) == sorted(_widths(p)) and len(set(_widths(p))) >= 2,
                "page level kept (not silently Advanced)": lambda p: p["level"] == "Intermediate"}},
    {"id": "S3", "kind": "revision", "instrument": "Saxophone", "level": "Intermediate",
     "q": "Make the second exercise more challenging, but keep the first exactly as it is.",
     "checks": {}},
    {"id": "S4", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "Give me a beginner warmup focused on tone and finger coordination.",
     "checks": {"level is Beginner": lambda p: p["level"] == "Beginner", "long tones (tone)": lambda p: "long_tones" in _fam(p),
                "fingers: scales or intervals": lambda p: bool({"scale", "intervals"} & set(_fam(p))),
                "not a single-kind plan": lambda p: len(set(_fam(p))) >= 2}},
    {"id": "S5", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "Give me a warmup with no long tones and more rhythmic variety.",
     "checks": {"no long tones": lambda p: "long_tones" not in _fam(p), "at least three kinds of exercise": lambda p: len(set(_fam(p))) >= 3,
                "varied (>= 5 distinct exercises)": lambda p: _variety(p) >= 5}},
    {"id": "S6", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "I've got a gig tonight — something short to get my fingers and tongue moving, not much on long tones",
     "checks": {"short (<= 8 minutes)": lambda p: _total(p) <= 8 * 60 + 20, "fingers: scales or intervals": lambda p: bool({"scale", "intervals"} & set(_fam(p))),
                "tongue: articulation": lambda p: "articulation" in _fam(p), "little time on long tones": lambda p: _share(p, "long_tones") <= 0.15}},
    {"id": "S7", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "I want to work on my double-tonguing and finger speed in a quick warmup",
     "checks": {"articulation present": lambda p: "articulation" in _fam(p), "scales or intervals for finger speed": lambda p: bool({"scale", "intervals"} & set(_fam(p))),
                "quick (<= 8 minutes)": lambda p: _total(p) <= 8 * 60 + 20}},
    {"id": "S8", "kind": "plan", "instrument": "Saxophone", "level": "Intermediate",
     "q": "Give me a fifteen-minute warmup with a bit of everything but make the intervals wider than thirds",
     "checks": {"about fifteen minutes": lambda p: abs(_total(p) - 900) <= 72, "all four kinds of exercise": lambda p: len(set(_fam(p))) == 4,
                "no thirds": lambda p: all(r["params"].get("interval") != "thirds" for r in p["items"]),
                "wider intervals present": lambda p: any(w >= 3 for w in _widths(p))}},
    {"id": "S9", "kind": "plan", "instrument": "Flute", "level": "Intermediate",
     "q": "Warm me up for soloing over Blue Bossa",
     "checks": {"builds an ordinary warmup": lambda p: len(p["items"]) >= 3}},
]
assert len(CORPUS) <= MAX_REQUESTS


# ---------------------------------------------------------------- transports

class Dry:
    def __init__(self, key):
        pass

    def complete(self, **kw):
        raise TransportError("dry_run", error_type="Dry", billed="no")


class Capped:
    count = 0
    last_seconds = 0.0

    def __init__(self, key):
        self._inner = AnthropicTransport(key)

    def complete(self, **kw):
        if Capped.count >= MAX_REQUESTS:
            raise TransportError("harness_cap", error_type="HarnessCap", billed="no")
        Capped.count += 1
        t0 = time.perf_counter()
        try:
            return self._inner.complete(**kw)
        finally:
            Capped.last_seconds = time.perf_counter() - t0


wi.AnthropicTransport = Capped if LIVE else Dry


def spent() -> float:
    p = pathlib.Path(os.environ["AMI_CLAUDE_LEDGER_PATH"])
    if not p.exists():
        return 0.0
    return sum(json.loads(x)["cost_micro_usd"] for x in p.read_text().splitlines() if x.strip() and json.loads(x)["type"] == "settle") / 1e6


def session(instrument="Flute"):
    return {"_suite_auth_user_id": "experiment", "_suite_active_workspace_id": "experiment", "instrument": instrument,
            "_ami_claude_dev_mode": True, "_ami_claude_dev_enabled": True}


def ctx(instrument="Flute", level="Intermediate"):
    return {"instrument": instrument, "level": level, "focus": "Improvisation", "display_key": "C", "bpm": 100}


def score(s: dict, entry: dict) -> dict[str, Any]:
    plan = wp.current(s)
    if plan is None:
        return {"built": False, "checks": {n: False for n in entry["checks"]}, "passed": 0, "total": len(entry["checks"])}
    results = {}
    for name, fn in entry["checks"].items():
        try:
            results[name] = bool(fn(plan))
        except Exception:                      # a check that cannot be evaluated counts as failed, never as passed
            results[name] = False
    return {"built": True, "families": _fam(plan), "level": plan["level"], "total_seconds": round(_total(plan), 1), "distinct_exercises": _variety(plan),
            "intervals": [r["params"].get("interval") for r in plan["items"] if r["family"] == "intervals"],
            "checks": results, "passed": sum(results.values()), "total": len(results)}


def _claude_row(interp, record: dict, wall: float) -> dict[str, Any]:
    called = record.get("status") not in (None, "skipped", "refused")
    return {"status": record.get("status"), "reason": record.get("reason"), "violations": record.get("violations"),
            "request": interp.request if interp is not None and interp.ok else None, "clarify": interp.clarify if interp is not None else None,
            "request_id": record.get("request_id"), "usage": record.get("usage"), "cost_usd": record.get("cost_usd"), "stop_reason": record.get("stop_reason"),
            "seconds": round(Capped.last_seconds, 2) if LIVE and called else None, "wall_seconds": round(wall, 2)}


def run_plan_sentence(entry: dict) -> dict[str, Any]:
    q, inst, lvl = entry["q"], entry["instrument"], entry["level"]
    parsed = wp.parse_request(q)
    s_rules = session(inst)
    resp_rules = wp.create(q, s_rules, ctx(inst, lvl))
    rules = score(s_rules, entry)
    rules["says_it_cannot_use_chords"] = "can't use" in resp_rules.composed_markdown().lower() or "cannot use" in resp_rules.composed_markdown().lower()
    s = session(inst)
    t0 = time.perf_counter()
    interp, record = wi.interpret(q, lvl, s)
    wall = time.perf_counter() - t0
    merged = wi.merge_into(parsed, interp) if interp is not None and interp.ok else parsed
    resp = wp.create(q, s, ctx(inst, lvl), request=merged)
    return {"rules_only": {"reading": {k: parsed[k] for k in ("families", "excluded", "minutes", "level", "intervals", "artic", "focus", "progressive")}, **rules},
            "claude": _claude_row(interp, record, wall), "with_claude": score(s, entry), "answer_head": resp.direct_answer.split("\n")[0][:140]}


def run_revision_sentence(entry: dict) -> dict[str, Any]:
    """A revision of an existing warmup: the rules' deterministic revision, and what the plan-request vocabulary can say about it."""
    q, inst, lvl = entry["q"], entry["instrument"], entry["level"]
    s_rules = session(inst)
    wp.create("Give me a 10-minute warmup", s_rules, ctx(inst, lvl))
    before = json.loads(json.dumps(wp.current(s_rules)))
    wp.handle(q, s_rules, ctx(inst, lvl))
    after = wp.current(s_rules)
    rules_checks = {"first exercise exactly as it was": after["items"][0]["abc"] == before["items"][0]["abc"] and after["items"][0]["bpm"] == before["items"][0]["bpm"],
                    "second exercise is harder (faster)": after["items"][1]["bpm"] > before["items"][1]["bpm"],
                    "every other exercise unchanged": all(a["abc"] == b["abc"] and a["bpm"] == b["bpm"] for i, (a, b) in enumerate(zip(after["items"], before["items"])) if i != 1),
                    "level unchanged": after["level"] == before["level"]}
    s = session(inst)
    t0 = time.perf_counter()
    interp, record = wi.interpret(q, lvl, s)
    wall = time.perf_counter() - t0
    req = interp.request if interp is not None and interp.ok else None
    # The plan-request vocabulary has no way to say "exercise 2" or "keep exercise 1": any concrete request would apply to the WHOLE warmup.
    would_change_whole = bool(req and (req["level"] or req["families"] or req["excluded"] or req["intervals"] or req["artic"] or req["emphasis"] or req["focus"]))
    claude_checks = {"cannot express an item-level change, so it must decline / stay inert": not would_change_whole}
    return {"rules_only": {"checks": rules_checks, "passed": sum(rules_checks.values()), "total": len(rules_checks)}, "claude": _claude_row(interp, record, wall),
            "with_claude": {"checks": claude_checks, "passed": sum(claude_checks.values()), "total": len(claude_checks), "would_change_whole_warmup": would_change_whole},
            "answer_head": "(revision)"}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def total(cond: str) -> str:
        return "%d/%d" % (sum(r[cond]["passed"] for r in rows), sum(r[cond]["total"] for r in rows))

    api = [r["claude"] for r in rows if r["claude"].get("status") not in (None, "skipped", "refused")]
    usage = {k: sum(int((c.get("usage") or {}).get(k, 0)) for c in api) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
    secs = [c["seconds"] for c in api if c.get("seconds") is not None]
    return {"mode": "LIVE" if LIVE else "DRY", "sentences": len(rows), "requests": Capped.count if LIVE else 0, "recorded_cost_usd": round(spent(), 6),
            "adherence_rules_only": total("rules_only"), "adherence_with_claude": total("with_claude"),
            "claude_statuses": [c.get("status") for c in api], "validation_rejections": sum(1 for c in api if c.get("status") in ("rejected", "invalid_json")),
            "unsupported_proposals": sum(1 for c in api if c.get("clarify") == "unsupported_request" or c.get("status") == "rejected"),
            "tokens": usage, "seconds_each": secs, "seconds_mean": round(sum(secs) / len(secs), 2) if secs else None, "seconds_max": max(secs) if secs else None,
            "request_ids": [c.get("request_id") for c in api]}


def main() -> None:
    cfg = load_claude_settings()
    rows: list[dict[str, Any]] = []
    for entry in CORPUS:
        row = {"id": entry["id"], "sentence": entry["q"], "kind": entry["kind"], **(run_plan_sentence(entry) if entry["kind"] == "plan" else run_revision_sentence(entry))}
        chars = len(wi.SYSTEM_PROMPT) + len(json.dumps(wi.build_context(entry["q"], entry["level"]))) + 80
        worst = estimate_worst_case_micro_usd(cfg.model, prompt_chars=chars, max_output_tokens=min(cfg.max_output_tokens, 300))
        row["would_send"] = {"model": cfg.model, "prompt_chars": chars, "worst_case_usd": round(worst / 1e6, 5)}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False, default=str), flush=True)
        (OUT / f"{TAG}_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        if LIVE:
            status = str(row["claude"].get("status") or "")
            if status.startswith(("api_error", "billing_unknown", "incomplete", "internal_error")) or status in ("refusal", "refused"):
                print("ABORT: unexpected API outcome", status)
                break
            if (row["claude"].get("cost_usd") or 0) > PER_REQUEST_USD or spent() >= MAX_USD:
                print("ABORT: cost limit")
                break
    summary = summarize(rows)
    (OUT / f"{TAG}_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    main()

"""Controlled live experiment for Claude-assisted warmup PLANNING: does Claude read sentences the fixed warmup rules do not?

NOT RUN without explicit owner approval. Two modes:

  DRY (default)        python scripts/ami_warmup_planning_experiment.py
                       Records, for every corpus sentence, what the fixed rules read and the warmup they would build, and the size and worst-case
                       cost of what would be sent. No network, no spend.

  LIVE                 AMI_WARMUP_LIVE=1 python scripts/ami_warmup_planning_experiment.py --approve-spend
                       Uses the DIRECT Anthropic Messages API through AMI's own transport (the route that already worked) with the owner's
                       ANTHROPIC_API_KEY (loaded from the environment / Streamlit secrets, never printed) behind hard limits: at most MAX_REQUESTS
                       requests and MAX_USD of recorded cost, no SDK retries, abort on the first API error or any request above PER_REQUEST_USD.
                       Every request is in a dedicated AMI usage-ledger file with its request id and token usage. It never uses Claude Code, the
                       Agent SDK, a launcher or a subscription login.

For each sentence it prints: the fixed rules' reading, Claude's validated plan request (or why it was rejected), and the warmup the engines then
built (families, minutes, level, planned seconds). It never prints a key or a full prompt.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

MAX_REQUESTS = 10
MAX_USD = 1.00
PER_REQUEST_USD = 0.05
LIVE = os.environ.get("AMI_WARMUP_LIVE") == "1" and "--approve-spend" in sys.argv
TAG = "warmup_live" if LIVE else "warmup_dry"
OUT = pathlib.Path(os.environ.get("AMI_WARMUP_OUT", ROOT / "data" / "experiments"))
OUT.mkdir(parents=True, exist_ok=True)
os.environ["AMI_CLAUDE_ENABLED"] = "true"
os.environ["AMI_CLAUDE_INTERPRET_ENABLED"] = "true"
os.environ["AMI_CLAUDE_BUDGET_USD"] = str(MAX_USD)
os.environ["AMI_CLAUDE_SESSION_CALL_CAP"] = str(MAX_REQUESTS)
os.environ["AMI_CLAUDE_LEDGER_PATH"] = str(OUT / f"{TAG}_ledger.jsonl")

from music_coach_ami import warmup_interpret as wi  # noqa: E402
from music_coach_ami import warmup_plan as wp  # noqa: E402
from music_coach_ami.claude_client import AnthropicTransport, TransportError  # noqa: E402
from music_coach_ami.claude_settings import load_claude_settings  # noqa: E402
from music_coach_ami.claude_usage import estimate_worst_case_micro_usd  # noqa: E402

CORPUS = [
    "I've got a gig tonight — something short to get my fingers and tongue moving, not much on long tones",
    "Ten minutes for my tone first thing in the morning, mostly long tones and a little slurring",
    "I want to work on my double-tonguing and finger speed in a quick warmup",
    "Give me a warmup that's heavy on articulation but still has some scales",
    "I'm a beginner, can you do a gentle five minute warmup?",
    "Warm me up for soloing over Blue Bossa",
    "Fifteen minutes: a bit of everything but make the intervals wider than thirds",
    "No scales today, just tone and intervals",
    "Something quick for my lips before rehearsal",
    "Make me a warmup with slurs, then tongued pairs, then fourths",
]


class Dry:
    def __init__(self, key):
        pass

    def complete(self, **kw):
        raise TransportError("dry_run", error_type="Dry", billed="no")


class Capped:
    count = 0

    def __init__(self, key):
        self._inner = AnthropicTransport(key)

    def complete(self, **kw):
        if Capped.count >= MAX_REQUESTS:
            raise TransportError("harness_cap", error_type="HarnessCap", billed="no")
        Capped.count += 1
        return self._inner.complete(**kw)


wi.AnthropicTransport = Capped if LIVE else Dry


def spent() -> float:
    p = pathlib.Path(os.environ["AMI_CLAUDE_LEDGER_PATH"])
    if not p.exists():
        return 0.0
    return sum(json.loads(x)["cost_micro_usd"] for x in p.read_text().splitlines() if x.strip() and json.loads(x)["type"] == "settle") / 1e6


def session(instrument="Flute"):
    return {"_suite_auth_user_id": "experiment", "_suite_active_workspace_id": "experiment", "instrument": instrument,
            "_ami_claude_dev_mode": True, "_ami_claude_dev_enabled": True}


def ctx(instrument="Flute"):
    return {"instrument": instrument, "level": "Intermediate", "focus": "Improvisation", "display_key": "C", "bpm": 100}


def summary(resp) -> dict:
    d = resp.diagnostics or {}
    return {"failed": d.get("warmup_failure_reason"), "level": d.get("warmup_level"), "minutes": d.get("warmup_minutes"),
            "planned_seconds": d.get("warmup_total_seconds"),
            "exercises": [f"{i['family']}:{(i.get('params') or {}).get('interval') or (i.get('params') or {}).get('pattern') or ''}" for i in d.get("warmup_items", [])]}


def main() -> None:
    rows = []
    for q in CORPUS:
        parsed = wp.parse_request(q)
        s_rules = session()
        rules = wp.create(q, s_rules, ctx())
        s = session()
        interp, record = wi.interpret(q, "Intermediate", s)
        merged = wi.merge_into(parsed, interp) if interp is not None and interp.ok else parsed
        built = wp.create(q, s, ctx(), request=merged)
        ctx_sent = wi.build_context(q, "Intermediate")
        cfg = load_claude_settings()
        worst = estimate_worst_case_micro_usd(cfg.model, prompt_chars=len(wi.SYSTEM_PROMPT) + len(json.dumps(ctx_sent)) + 80, max_output_tokens=min(cfg.max_output_tokens, 300))
        row = {"sentence": q, "would_send": {"model": cfg.model, "prompt_chars": len(wi.SYSTEM_PROMPT) + len(json.dumps(ctx_sent)) + 80, "worst_case_usd": round(worst / 1e6, 5)},
               "rules_only": {"families": parsed["families"], "excluded": parsed["excluded"], "minutes": parsed["minutes"], "level": parsed["level"],
                              "plan": summary(rules)},
               "claude": {"status": record.get("status"), "reason": record.get("reason"), "violations": record.get("violations"),
                          "request": interp.request if interp is not None and interp.ok else None, "clarify": interp.clarify if interp is not None else None,
                          "request_id": record.get("request_id"), "usage": record.get("usage"), "cost_usd": record.get("cost_usd")},
               "with_claude": {"plan": summary(built)}}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        (OUT / f"{TAG}_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        if LIVE:
            status = str(record.get("status") or "")
            if status.startswith(("api_error", "billing_unknown", "incomplete")) or status == "refusal":
                print("ABORT: unexpected API outcome", status)
                break
            if (record.get("cost_usd") or 0) > PER_REQUEST_USD or spent() >= MAX_USD:
                print("ABORT: cost limit")
                break
    print(json.dumps({"mode": "LIVE" if LIVE else "DRY", "requests": Capped.count if LIVE else 0, "recorded_cost_usd": round(spent(), 6)}))


if __name__ == "__main__":
    main()

"""Controlled live experiment for the M1b-4 Claude interpretation layer: does it understand sentences the fixed rules do not?

NOT RUN without explicit owner approval. Two modes:

  DRY (default)        python scripts/ami_interpret_experiment.py
                       Records, for every corpus sentence, what the fixed rules do and what would be sent (size and worst-case cost). No network, no spend.

  LIVE                 AMI_INTERPRET_LIVE=1 python scripts/ami_interpret_experiment.py --approve-spend
                       Uses the real transport and the owner's ANTHROPIC_API_KEY (loaded from the environment / Streamlit secrets, never printed) behind hard
                       limits: at most MAX_REQUESTS requests and MAX_USD of recorded cost, no SDK retries, abort on the first API error or any request above
                       PER_REQUEST_USD. Every request is in the AMI usage ledger (a dedicated file) with its request id and token usage.

For each sentence it prints: the fixed rules' outcome, Claude's validated interpretation (or why it was rejected), and what the engines then did.
It never prints a key or a full prompt.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

MAX_REQUESTS = 10
MAX_USD = 1.00
PER_REQUEST_USD = 0.05
LIVE = os.environ.get("AMI_INTERPRET_LIVE") == "1" and "--approve-spend" in sys.argv
TAG = "interpret_live" if LIVE else "interpret_dry"
OUT = pathlib.Path(os.environ.get("AMI_INTERPRET_OUT", ROOT / "data" / "experiments"))
OUT.mkdir(parents=True, exist_ok=True)
os.environ["AMI_CLAUDE_ENABLED"] = "true"
os.environ["AMI_CLAUDE_INTERPRET_ENABLED"] = "true"
os.environ["AMI_CLAUDE_BUDGET_USD"] = str(MAX_USD)
os.environ["AMI_CLAUDE_SESSION_CALL_CAP"] = str(MAX_REQUESTS)
os.environ["AMI_CLAUDE_LEDGER_PATH"] = str(OUT / f"{TAG}_ledger.jsonl")

from music_coach_ami import claude_interpret as ci  # noqa: E402
from music_coach_ami import conversation_state as cs  # noqa: E402
from music_coach_ami.claude_client import AnthropicTransport, TransportError, TransportResult  # noqa: E402
from music_coach_ami.pipeline import run_coach_submit  # noqa: E402
from tests.test_ami_scale_pattern_recipe import ASK_CHORDS, ctx, session  # noqa: E402

CORPUS = [
    "Make that pattern a little more sophisticated, but keep the rhythm",
    "I want the flute version to sound smoother",
    "Keep what you gave me, but make it more appropriate for the bridge",
    "Give it more of an advanced jazz character",
    "Keep the same idea, but make it more useful for soloing",
    "Make it a little smoother",
    "Can we hear it with wider leaps?",
    "Let's get the tenor sax version of this",
    "Same pattern, but over the second half of the tune",
    "Tone down the chromatic stuff",
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


ci.AnthropicTransport = Capped if LIVE else Dry


def spent() -> float:
    p = pathlib.Path(os.environ["AMI_CLAUDE_LEDGER_PATH"])
    if not p.exists():
        return 0.0
    return sum(json.loads(x)["cost_micro_usd"] for x in p.read_text().splitlines() if x.strip() and json.loads(x)["type"] == "settle") / 1e6


def main() -> None:
    rows = []
    for q in CORPUS:
        # the rules alone (gate shut)
        s = session("Flute")
        run_coach_submit(ASK_CHORDS, s, ami_ctx=ctx())
        n0 = cs.history(s)["versions"]
        rules = run_coach_submit(q, s, ami_ctx=ctx())[1]
        rules_kind = "general-coach" if rules is None or not (rules.diagnostics or {}).get("exercise_revision_kind") else (rules.diagnostics or {}).get("exercise_revision_kind")
        rules_changed = cs.history(s)["versions"] != n0
        # with the layer open
        s2 = session("Flute")
        run_coach_submit(ASK_CHORDS, s2, ami_ctx=ctx())
        s2["_ami_claude_dev_mode"] = True
        s2["_ami_claude_dev_enabled"] = True
        before = cs.history(s2)["versions"]
        resp = run_coach_submit(q, s2, ami_ctx=ctx())[1]
        d = (resp.diagnostics or {}) if resp else {}
        rec = d.get("claude_interpretation") or (s2.get(ci.LAST_KEY) or {})
        row = {"sentence": q, "rules_only": {"outcome": rules_kind, "changed_exercise": rules_changed},
               "claude": {"status": rec.get("status"), "reason": rec.get("reason"), "violations": rec.get("violations"), "ops": d.get("interpreted_ops"),
                          "clarify": d.get("exercise_revision_failure_reason"), "request_id": rec.get("request_id"), "usage": rec.get("usage"), "cost_usd": rec.get("cost_usd")},
               "engines": {"version_added": cs.history(s2)["versions"] != before, "answer_head": (resp.direct_answer[:140] if resp else None)}}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        (OUT / f"{TAG}_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        if LIVE:
            if rec.get("status", "").startswith(("api_error", "billing_unknown", "incomplete")) or rec.get("status") == "refusal":
                print("ABORT: unexpected API outcome", rec.get("status"))
                break
            if (rec.get("cost_usd") or 0) > PER_REQUEST_USD or spent() >= MAX_USD:
                print("ABORT: cost limit")
                break
    print(json.dumps({"mode": "LIVE" if LIVE else "DRY", "requests": Capped.count if LIVE else 0, "recorded_cost_usd": round(spent(), 6)}))


if __name__ == "__main__":
    main()

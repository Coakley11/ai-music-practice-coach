"""Run the same test IDs on two worktrees and compare every outcome, not just failures.

Comparing failing IDs alone cannot tell you that a previously passing test still runs:
a test that disappears, errors at collection, or is skipped leaves the failure list
identical while the pass count drops. This records an outcome per test ID on each side
and reports every ID whose outcome changed, plus anything present on one side only.

Usage: python scripts/_matched_test_run.py <baseline_dir> <candidate_dir> <testlist> [label]

Its parsing is covered by tests/test_matched_test_run_parsing.py - see the note on
SUBFAILED there before changing OUTCOME.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# pytest-subtests prints "SUBFAILED(params...) nodeid", not "SUBFAIL nodeid", so a
# pattern expecting whitespace after the status skipped every subtest failure - and the
# parent still prints PASSED, so a test whose subtests all failed looked clean. The
# trailing group is optional and non-greedy for exactly that reason.
OUTCOME = re.compile(
    r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS|SUBFAILED|SUBPASS)(?:\(.*?\))?\s+(\S+)")


def run(worktree: str, tests: list[str], tag: str, out_dir: Path) -> dict:
    # A single collection error otherwise aborts the whole run and compares nothing.
    # It is still recorded as an ERROR outcome on each side, so one appearing on only
    # one side is still reported as a difference.
    cmd = [sys.executable, "-m", "pytest", *tests, "-p", "no:randomly",
           "--tb=no", "-q", "-rA", "--continue-on-collection-errors"]
    proc = subprocess.run(cmd, cwd=worktree, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=5400)
    (out_dir / f"{tag}.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    outcomes: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        m = OUTCOME.match(line.strip())
        if not m:
            continue
        status, nodeid = m.group(1), m.group(2)
        # A subtest failure belongs to its parent test id.
        nodeid = nodeid.split(" ")[0]
        if status.startswith("SUB"):
            status = "FAILED" if status == "SUBFAILED" else outcomes.get(nodeid, "PASSED")
        prev = outcomes.get(nodeid)
        if prev in ("FAILED", "ERROR"):
            continue
        outcomes[nodeid] = status
    tail = [l for l in proc.stdout.splitlines() if " passed" in l or " failed" in l]
    return {"outcomes": outcomes, "summary": tail[-1] if tail else "", "rc": proc.returncode}


def main() -> int:
    baseline, candidate, listfile = sys.argv[1], sys.argv[2], sys.argv[3]
    label = sys.argv[4] if len(sys.argv) > 4 else "matched"
    out_dir = Path(__file__).resolve().parent / "matched"
    out_dir.mkdir(parents=True, exist_ok=True)
    tests = [t.strip() for t in Path(listfile).read_text().splitlines() if t.strip()]

    print(f"[{label}] {len(tests)} test files, sequential")
    base = run(baseline, tests, f"{label}-baseline", out_dir)
    print(f"  baseline  {base['summary']}")
    cand = run(candidate, tests, f"{label}-candidate", out_dir)
    print(f"  candidate {cand['summary']}")

    b, c = base["outcomes"], cand["outcomes"]
    only_base = sorted(set(b) - set(c))
    only_cand = sorted(set(c) - set(b))
    changed = sorted(i for i in (set(b) & set(c)) if b[i] != c[i])
    regressed = [i for i in changed if b[i] == "PASSED" and c[i] != "PASSED"]

    print(f"  test ids: baseline={len(b)} candidate={len(c)}")
    print(f"  only in baseline (disappeared): {len(only_base)}")
    for i in only_base[:10]:
        print(f"     - {i} was {b[i]}")
    print(f"  only in candidate (new): {len(only_cand)}")
    for i in only_cand[:10]:
        print(f"     + {i} is {c[i]}")
    print(f"  outcome changed: {len(changed)}")
    for i in changed[:20]:
        print(f"     ~ {i}: {b[i]} -> {c[i]}")
    print(f"  REGRESSIONS (passed -> not passed): {len(regressed)}")
    for i in regressed:
        print(f"     ! {i}")

    (out_dir / f"{label}-compare.json").write_text(json.dumps(
        {"baseline_summary": base["summary"], "candidate_summary": cand["summary"],
         "baseline_ids": len(b), "candidate_ids": len(c),
         "only_baseline": only_base, "only_candidate": only_cand,
         "changed": {i: [b[i], c[i]] for i in changed}, "regressions": regressed},
        indent=1), encoding="utf-8")
    print("VERDICT:", "CLEAN" if not regressed and not only_base else "INVESTIGATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

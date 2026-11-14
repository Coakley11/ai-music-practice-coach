"""Run a matched baseline-vs-candidate comparison in memory-bounded chunks.

``_matched_test_run.py`` runs the whole suite on each worktree in one pytest process.
On this machine that peaked high enough to be killed silently - no traceback, no output,
no compare file - while another agent's headless browser held ~780 MB and free physical
RAM fell below 0.5 GB.

So the same comparison is done here in chunks of test files. Peak memory is bounded by
the chunk, memory is released between chunks, a kill costs one chunk rather than the
whole run, and each chunk waits for free RAM before it starts. The comparison itself is
unchanged: the same test IDs run on both worktrees and every outcome is compared, so a
test that vanishes or starts erroring is still caught, not just one that starts failing.

Usage:
  python scripts/_matched_chunked.py <baseline_dir> <candidate_dir> <label> [chunk_size]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "matched"
OUT.mkdir(parents=True, exist_ok=True)

MIN_FREE_GB = 1.6
WAIT_STEP_SEC = 30
MAX_WAIT_SEC = 1800


def free_gb() -> float:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out) / (1024 * 1024)
    except Exception:
        return 99.0


def wait_for_memory(tag: str) -> float:
    waited = 0
    while waited < MAX_WAIT_SEC:
        g = free_gb()
        if g >= MIN_FREE_GB:
            return g
        print(f"  [{tag}] free RAM {g:.2f} GB < {MIN_FREE_GB} GB, waiting "
              f"({waited}s so far)", flush=True)
        time.sleep(WAIT_STEP_SEC)
        waited += WAIT_STEP_SEC
    g = free_gb()
    print(f"  [{tag}] proceeding at {g:.2f} GB after waiting {waited}s", flush=True)
    return g


OUTCOME_RE = None


def parse_outcomes(text: str) -> dict[str, str]:
    import re

    global OUTCOME_RE
    if OUTCOME_RE is None:
        # Same pattern as _matched_test_run: pytest-subtests prints
        # "SUBFAILED(params) nodeid", so the parenthesised group must be optional and
        # non-greedy or every subtest failure is skipped while the parent still says
        # PASSED.
        OUTCOME_RE = re.compile(
            r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS|SUBFAILED|SUBPASS)"
            r"(?:\(.*?\))?\s+(\S+)")
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = OUTCOME_RE.match(line.strip())
        if not m:
            continue
        status, node = m.group(1), m.group(2)
        prev = out.get(node)
        # A SUBFAILED must not be overwritten by the parent's PASSED.
        if prev and prev in ("FAILED", "ERROR", "SUBFAILED"):
            continue
        out[node] = status
    return out


def run_chunk(worktree: str, files: list[str], tag: str) -> dict[str, str]:
    wait_for_memory(tag)
    cmd = [sys.executable, "-m", "pytest", *files, "-p", "no:randomly",
           "--tb=no", "-q", "-rA", "--continue-on-collection-errors"]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=worktree, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=2700)
    (OUT / f"{tag}.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    got = parse_outcomes(proc.stdout)
    print(f"  [{tag}] {len(got)} outcomes, rc={proc.returncode}, "
          f"{time.time() - t0:.0f}s", flush=True)
    if not got:
        print(f"  [{tag}] WARNING: no outcomes parsed - see {tag}.txt", flush=True)
    return got


def main() -> int:
    baseline, candidate, label = sys.argv[1], sys.argv[2], sys.argv[3]
    chunk_size = int(sys.argv[4]) if len(sys.argv) > 4 else 40

    # Chunk by the BASELINE's file list, then run the same list on both sides, so a
    # file that exists only in the candidate is reported as candidate-only rather than
    # quietly changing what each side ran.
    all_files = sorted(
        p.name for p in (Path(baseline) / "tests").glob("test_*.py"))
    cand_files = sorted(
        p.name for p in (Path(candidate) / "tests").glob("test_*.py"))
    only_candidate = [f for f in cand_files if f not in all_files]
    only_baseline = [f for f in all_files if f not in cand_files]
    union = all_files + only_candidate
    chunks = [union[i:i + chunk_size] for i in range(0, len(union), chunk_size)]
    print(f"{len(union)} test files in {len(chunks)} chunks of up to {chunk_size}")
    print(f"candidate-only files: {only_candidate or 'none'}")
    print(f"baseline-only files:  {only_baseline or 'none'}")

    base_all: dict[str, str] = {}
    cand_all: dict[str, str] = {}
    for i, chunk in enumerate(chunks, 1):
        print(f"\n=== chunk {i}/{len(chunks)} ({len(chunk)} files) ===", flush=True)
        paths = [f"tests/{f}" for f in chunk]
        base_all.update(run_chunk(baseline, paths, f"{label}-base-{i:02d}"))
        cand_all.update(run_chunk(candidate, paths, f"{label}-cand-{i:02d}"))

    changed = {}
    for node, b in base_all.items():
        c = cand_all.get(node)
        if c is None:
            changed[node] = {"baseline": b, "candidate": "ABSENT"}
        elif c != b:
            changed[node] = {"baseline": b, "candidate": c}
    added = {n: c for n, c in cand_all.items() if n not in base_all}

    def tally(d):
        out: dict[str, int] = {}
        for v in d.values():
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items()))

    report = {
        "label": label,
        "baseline_dir": baseline,
        "candidate_dir": candidate,
        "baseline_total": len(base_all),
        "candidate_total": len(cand_all),
        "baseline_tally": tally(base_all),
        "candidate_tally": tally(cand_all),
        "changed_outcomes": changed,
        "candidate_only_tests": sorted(added),
        "candidate_only_count": len(added),
        "candidate_only_tally": tally(added),
        "only_candidate_files": only_candidate,
        "only_baseline_files": only_baseline,
    }
    (OUT / f"{label}-chunked-compare.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")

    print("\n================ MATCHED COMPARISON ================")
    print(f"baseline  {len(base_all)} outcomes  {tally(base_all)}")
    print(f"candidate {len(cand_all)} outcomes  {tally(cand_all)}")
    print(f"new tests on the candidate side: {len(added)} {tally(added)}")
    if changed:
        print(f"\nDIFFERENCES: {len(changed)} test ID(s) changed outcome")
        for node, v in sorted(changed.items())[:60]:
            print(f"  {v['baseline']} -> {v['candidate']}  {node}")
    else:
        print("\nCLEAN: every shared test ID has the same outcome on both sides")
    print(f"\nreport: {OUT / f'{label}-chunked-compare.json'}")
    return 0 if not changed else 1


if __name__ == "__main__":
    raise SystemExit(main())

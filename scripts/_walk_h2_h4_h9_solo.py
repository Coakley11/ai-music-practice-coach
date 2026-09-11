"""Run H2 / H4 / H9 alone (or all three) against a live app.

Usage:
  python scripts/_walk_h2_h4_h9_solo.py http://127.0.0.1:8512
  python scripts/_walk_h2_h4_h9_solo.py http://127.0.0.1:8512 H2
  python scripts/_walk_h2_h4_h9_solo.py http://127.0.0.1:8512 H4 H9
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_remaining_h_gates import (  # noqa: E402
    OUT,
    URL as DEFAULT_URL,
    meta,
    run_h2,
    run_h4,
    run_h9,
)
from walk_creative_backing_matrix import wait_idle  # noqa: E402

ARGS = [a for a in sys.argv[1:] if a]
URL = DEFAULT_URL
GATES: list[str] = []
for a in ARGS:
    if a.startswith("http"):
        URL = a
    else:
        GATES.append(a.upper())
if not GATES:
    GATES = ["H2", "H4", "H9"]


def main() -> int:
    notes: list[str] = []
    results: dict = {"meta": meta(), "url": URL, "gates": GATES}
    runners = {"H2": run_h2, "H4": run_h4, "H9": run_h9}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for gate in GATES:
            fn = runners.get(gate)
            if not fn:
                results[gate] = {"ok": False, "reason": "unknown_gate"}
                continue
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(URL, wait_until="domcontentloaded")
            wait_idle(page, 4000)
            results[gate] = fn(page, notes)
            page.close()
        browser.close()

    results["notes"] = notes[-40:]
    out = OUT / f"solo-{'-'.join(GATES).lower()}-results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    failed = [k for k in GATES if not (results.get(k) or {}).get("ok")]
    print("FAILED:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

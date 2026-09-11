"""Re-run only H1/H6/H8/H7/H10 against a live app (after H2–H9 already exercised)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_remaining_h_gates import meta, run_h1_h6_h8_h7_h10
from walk_creative_backing_matrix import wait_idle

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL, wait_until="domcontentloaded")
        wait_idle(page, 4000)
        out = {"meta": meta()}
        out.update(run_h1_h6_h8_h7_h10(page, notes))
        browser.close()
    print(json.dumps(out, indent=2))
    failed = [k for k, v in out.items() if k.startswith("H") and isinstance(v, dict) and not v.get("ok")]
    print("FAILED:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

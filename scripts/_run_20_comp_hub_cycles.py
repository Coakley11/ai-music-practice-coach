"""20× Custom → Composition → one hub Backing click."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location(
    "v", ROOT / "_source_identity_browser_verify.py"
)
v = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v)


def main() -> int:
    cycles = 20
    results = []
    v.reset_ensure_songs_stats()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        print("loaded", flush=True)
        for i in range(1, cycles + 1):
            t0 = time.time()
            try:
                v.ensure_songs(page)
                v.select_music_source(page, "Custom Progression")
                v.select_music_source(page, "Composition")
                marker = v.wait_composition_hub_ready(page, timeout_ms=30000)
                loc = page.locator(".st-key-composition_hub_backing button")
                clicked = False
                for j in range(loc.count()):
                    btn = loc.nth(j)
                    if not btn.is_visible() or not v._marker_is_live(btn):
                        continue
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=8000)
                    clicked = True
                    break
                if not clicked:
                    raise RuntimeError("no live hub button")
                if not v._await_backing_studio(
                    page, timeout_ms=45000, prefer="composition"
                ):
                    raise RuntimeError(
                        "backing not open page=%r" % (v._studio_page_id(page),)
                    )
                row = {
                    "cycle": i,
                    "ok": True,
                    "dt": round(time.time() - t0, 1),
                    "pick": marker.get("pick"),
                }
                # Reset to Songs before next cycle (avoids stale nav after Backing).
                try:
                    v.ensure_songs(page)
                except Exception:
                    page.goto(
                        v.URL + "/?dev=1",
                        wait_until="domcontentloaded",
                        timeout=120_000,
                    )
                    v.wait_streamlit(page, 4000)
            except Exception as exc:
                row = {
                    "cycle": i,
                    "ok": False,
                    "error": str(exc)[:300],
                    "dt": round(time.time() - t0, 1),
                }
                try:
                    page.goto(
                        v.URL + "/?dev=1",
                        wait_until="domcontentloaded",
                        timeout=120_000,
                    )
                    v.wait_streamlit(page, 3000)
                except Exception:
                    pass
            results.append(row)
            print(row, flush=True)
        browser.close()
    okn = sum(1 for r in results if r.get("ok"))
    print(f"RESULT {okn}/{cycles}", flush=True)
    print(f"ENSURE_SONGS_STATS {json.dumps(v.ENSURE_SONGS_STATS)}", flush=True)
    (OUT / "instr_20_cycles.json").write_text(
        json.dumps(
            {
                "results": results,
                "ensure_songs_stats": dict(v.ENSURE_SONGS_STATS),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if okn == cycles else 1


if __name__ == "__main__":
    raise SystemExit(main())

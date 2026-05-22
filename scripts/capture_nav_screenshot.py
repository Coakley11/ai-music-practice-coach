"""Capture top-nav screenshot and measure segment heights (requires running Streamlit)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed; run: pip install playwright && playwright install chromium")
    sys.exit(1)

URL = "http://localhost:8503"
OUT = Path(__file__).resolve().parent / "nav_screenshot.png"
METRICS = Path(__file__).resolve().parent / "nav_metrics.json"


def main() -> int:
    time.sleep(2)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(4000)

        testids = page.evaluate(
            """() => [...new Set([...document.querySelectorAll('[data-testid]')].map(e => e.getAttribute('data-testid')))].sort()"""
        )
        seg = page.locator(
            '[data-testid="stBaseButton-segmented_control"], '
            '[data-testid="stBaseButton-segmented_controlActive"]'
        )
        count = seg.count()
        heights = []
        for i in range(count):
            box = seg.nth(i).bounding_box()
            if box:
                heights.append(round(box["height"], 2))

        group = page.locator('[data-testid="stButtonGroup"]').first
        if group.count() > 0:
            group.screenshot(path=str(OUT))
        elif page.locator(".ui-studio-nav-segmented").count() > 0:
            page.locator(".ui-studio-nav-segmented").first.screenshot(path=str(OUT))
        else:
            page.screenshot(path=str(OUT), full_page=False)
        browser.close()

    metrics = {
        "segment_count": count,
        "heights_px": heights,
        "max_delta_px": max(heights) - min(heights) if heights else None,
        "testids_sample": [t for t in testids if "egment" in t.lower() or "adio" in t or "utton" in t][:20],
    }
    METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"screenshot: {OUT}")
    if not heights or len(heights) < 8:
        return 2
    if max(heights) - min(heights) > 2:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

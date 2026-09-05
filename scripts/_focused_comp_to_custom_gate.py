"""Focused Composition → Custom leave cycles (no recovery). Same SHA package adjunct."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import _gate_workspace as gw  # noqa: E402
import _source_identity_browser_verify as v  # noqa: E402


def main() -> int:
    cycles = int(os.environ.get("FOCUSED_LEAVE_CYCLES") or "20")
    fails = 0
    ws, url = gw.prepare_isolated_workspace("gate_comp_to_custom", seed="catalog")
    print(f"[focused_leave] ws={ws} cycles={cycles} url={url}", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1500, "height": 1200}).new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 10000)
        gw.land_songs_with_source_radio(page, v)
        # Seed linger path once: Custom → Composition
        v.select_music_source(page, "Custom Progression")
        v.select_music_source(page, "Composition")
        v.wait_composition_hub_ready(page, timeout_ms=30000)
        for i in range(1, cycles + 1):
            try:
                if not v.assert_radio_selected(page, "Composition"):
                    v.select_music_source(page, "Composition")
                    v.wait_composition_hub_ready(page, timeout_ms=30000)
                v.select_music_source(page, "Custom Progression")
                if not v.assert_radio_selected(page, "Custom Progression"):
                    raise RuntimeError("Custom radio not selected after leave")
                if not page.locator(".st-key-custom_hub_backing").count():
                    # Hub mount may lag one idle; wait once without reload recovery.
                    v.wait_streamlit_idle(page, timeout_ms=12000)
                custom_ok = v.assert_radio_selected(page, "Custom Progression")
                print(
                    f"[cycle {i}/{cycles}] custom={custom_ok} "
                    f"comp={v.assert_radio_selected(page, 'Composition')}",
                    flush=True,
                )
                if not custom_ok:
                    fails += 1
                    print(f"[FAIL] cycle {i}: composition reclaimed or radio stuck", flush=True)
                    break
                # Return to Composition for next leave (no second Custom attempt).
                v.select_music_source(page, "Composition")
                v.wait_composition_hub_ready(page, timeout_ms=30000)
            except Exception as exc:
                fails += 1
                print(f"[FAIL] cycle {i}: {exc}", flush=True)
                break
        browser.close()
    print(f"[focused_leave] fails={fails}/{cycles}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

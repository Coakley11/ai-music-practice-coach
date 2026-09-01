"""Stress: Catalog → Custom → Composition → Composition Backing (20+ consecutive)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _source_identity_browser_verify as v  # noqa: E402

URL = v.URL


def _boot_songs(page) -> None:
    """Match verify main() cold entry."""
    page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
    page.wait_for_timeout(10000)
    v.ensure_songs(page)


def _run_full_prefix(page) -> None:
    """Replay verify sections 1–3 so switch runs after the same session load."""
    v.ensure_songs(page)
    v.select_music_source(page, "Custom Progression")
    v.open_custom_backing_from_hub(page)
    page.wait_for_timeout(2500)
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 10000)
    v.ensure_songs(page)
    v.select_music_source(page, "Custom Progression")
    v.open_custom_backing_from_hub(page)

    v.ensure_songs(page)
    v.select_music_source(page, "Composition")
    for _ in range(8):
        text = v.body_text(page)
        if (
            v.assert_radio_selected(page, "Composition")
            and "My Composition" in text
            and "This is a" in text
        ):
            v.wait_streamlit(page, 2500)
            break
        v.wait_streamlit(page, 2500)
    v.wait_composition_hub_ready(page, timeout_ms=25000)
    v.open_composition_backing_from_hub(page)
    page.wait_for_timeout(2500)
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 10000)
    v.ensure_songs(page)
    v.select_music_source(page, "Composition")
    for _ in range(8):
        text = v.body_text(page)
        if (
            v.assert_radio_selected(page, "Composition")
            and "My Composition" in text
            and "This is a" in text
        ):
            v.wait_streamlit(page, 2500)
            break
        v.wait_streamlit(page, 2500)
    v.wait_composition_hub_ready(page, timeout_ms=25000)
    v.open_composition_backing_from_hub(page)
    v.ensure_songs(page)
    v.wait_streamlit(page, 2000)
    v.open_composition_backing_from_hub(page)


def run_switch_once(page, cycle: int) -> tuple[bool, str]:
    v.ensure_songs(page)
    v.capture_switch_telemetry(page, f"stress{cycle}:start")
    v.select_music_source(page, "Catalog")
    v.open_catalog_backing_from_hub(page)
    v.ensure_songs(page)
    v.select_music_source(page, "Custom Progression")
    v.open_custom_backing_from_hub(page)
    v.ensure_songs(page)
    v.select_music_source(page, "Composition")
    for _ in range(4):
        text = v.body_text(page)
        if (
            v.assert_radio_selected(page, "Composition")
            and "My Composition" in text
            and "This is a" in text
        ):
            v.wait_streamlit(page, 2500)
            break
        v.wait_streamlit(page, 2000)
    v.open_composition_backing_from_hub(page)
    owner = v.read_live_backing_card_owner(page)
    if owner != "composition":
        return False, f"owner={owner!r} page={v._studio_page_id(page)!r}"
    return True, "ok"


def main() -> int:
    cycles = int(os.environ.get("SWITCH_COMP_CYCLES", "20"))
    full_prefix = os.environ.get("SWITCH_FULL_PREFIX", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        _boot_songs(page)
        if full_prefix:
            _run_full_prefix(page)

        for i in range(1, cycles + 1):
            t0 = time.time()
            ok, detail = run_switch_once(page, i)
            elapsed = round(time.time() - t0, 1)
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] stress cycle {i}/{cycles} ({elapsed}s): {detail}", flush=True)
            if not ok:
                fails += 1
                v.dump_debug(page, f"stress_switch_{i}")
                break
            page.wait_for_timeout(800)

        browser.close()

    print(f"\nStress cycles: {cycles} Failures: {fails} recovery=False", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

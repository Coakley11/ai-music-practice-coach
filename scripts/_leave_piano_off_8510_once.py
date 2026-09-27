"""One-shot leave: cycling Off, Piano/concert."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright  # noqa: E402

from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    instrument_select_value,
    set_instrument,
)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(
                "http://127.0.0.1:8510/?dev=1",
                wait_until="domcontentloaded",
                timeout=120000,
            )
            page.wait_for_timeout(4000)
            expand_sidebar(page)
            for _ in range(4):
                set_cycle_mode(page, False)
                page.wait_for_timeout(1500)
                ui = cycle_ui(page) or {}
                if not ui.get("playbar"):
                    break
            inst = ""
            for _ in range(5):
                set_instrument(page, "Piano")
                page.wait_for_timeout(1600)
                inst = str(instrument_select_value(page) or "")
                if inst.startswith("Piano"):
                    break
            for _ in range(3):
                set_cycle_mode(page, False)
                page.wait_for_timeout(1200)
                if not (cycle_ui(page) or {}).get("playbar"):
                    break
            page.evaluate(
                """() => {
                  const boxes = [...document.querySelectorAll('input[type="checkbox"]')];
                  for (const b of boxes) {
                    const lab = ((b.closest('label') || b.parentElement || b).innerText || '');
                    if (/written|instrument key|Shape|Capo shape/i.test(lab) && b.checked) {
                      b.click();
                    }
                  }
                }"""
            )
            page.wait_for_timeout(1200)
            ui = cycle_ui(page) or {}
            out = {
                "cycle_off": not bool(ui.get("playbar")),
                "instrument": instrument_select_value(page),
            }
            print(json.dumps(out, indent=2), flush=True)
            return 0 if out["cycle_off"] and str(out["instrument"] or "").startswith("Piano") else 1
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())

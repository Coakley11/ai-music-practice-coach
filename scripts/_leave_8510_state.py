"""Leave 8510 cycling Off, Piano/concert. KC_SHORT_PASS_* unset. No proof jobs."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode
from walk_creative_backing_matrix import expand_sidebar, instrument_select_value, set_instrument

OUT = ROOT / "scripts" / "evidence-key-cycle" / "leave_8510_state.json"
BASE = "http://127.0.0.1:8510"


def main() -> int:
    report: dict = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(3500)
            expand_sidebar(page)
            set_cycle_mode(page, False)
            page.wait_for_timeout(1500)
            set_instrument(page, "Piano")
            page.wait_for_timeout(2000)
            # Best-effort Written/Shape off
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
            page.wait_for_timeout(1500)
            ui = cycle_ui(page) or {}
            report["cycle_off"] = not bool(ui.get("playbar"))
            report["instrument"] = instrument_select_value(page)
            report["ui"] = {k: ui.get(k) for k in ("pause", "sounding", "playbar")}
            report["short_env"] = {
                k: os.environ.get(k) for k in (
                    "KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS",
                    "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS",
                )
            }
            report["ok"] = bool(report["cycle_off"]) and str(report.get("instrument") or "").startswith("Piano")
            print(json.dumps(report, indent=2), flush=True)
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            browser.close()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

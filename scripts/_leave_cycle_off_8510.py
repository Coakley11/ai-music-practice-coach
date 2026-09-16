"""Leave 8510 Key cycling Off."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda p, ms=900: p.wait_for_timeout(ms)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(3500)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)
        for _ in range(12):
            page.evaluate(
                """() => {
                  for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
                    if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
                    if (!(el.open === true || el.getAttribute('open') !== null)) {
                      (el.querySelector('summary') || el.querySelector('button') || el).click();
                    }
                  }
                  const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
                  const opts = root ? [...root.querySelectorAll('[data-testid="stRadioOption"]')] : [];
                  if (opts[0]) opts[0].click();
                  const stop = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"] button');
                  if (stop) stop.click();
                }"""
            )
            page.wait_for_timeout(900)
            playbar = page.locator('[class*="st-key-backing_key_cycle_advance_btn"]').count()
            if playbar == 0:
                break
        state = page.evaluate(
            """() => {
              const playbar = !!document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
              const opts = [...document.querySelectorAll(
                '[class*="st-key-backing_key_cycle_enabled_ui"] [data-testid="stRadioOption"]'
              )].map((el) => el.getAttribute('data-selected'));
              return {playbar, opts};
            }"""
        )
        print(json.dumps(state))
        browser.close()


if __name__ == "__main__":
    main()

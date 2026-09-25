"""Force key cycling Off on 8510."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import walk_creative_backing_matrix as m
from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(3000)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Backing")
    page.wait_for_timeout(2000)
    for _ in range(4):
        set_cycle_mode(page, False)
        page.wait_for_timeout(900)
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find((el) =>
                /Turn off cycling/i.test(el.innerText || '')
              );
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(900)
        if not cycle_ui(page).get("playbar"):
            break
    ui = cycle_ui(page)
    print("playbar", ui.get("playbar"), "pause", ui.get("pause"))
    browser.close()

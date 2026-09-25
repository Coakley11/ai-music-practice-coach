"""Fast catalog-only Key Cycle browser check + leave clean on 8510."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import walk_creative_backing_matrix as m
import walk_practice_loop_backing as wpl
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar, set_baseweb_select
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)


def wait_idle(page, ms=800):
    page.wait_for_timeout(ms)


m.wait_idle = wait_idle
wpl.wait_idle = wait_idle
wpl.settle = lambda page, seconds=1.2: wait_idle(page, int(seconds * 1000))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def body(page):
    return page.inner_text("body") or ""


def on_backing(page):
    b = body(page)
    return ("Play Backing Track" in b) or ("Quick BPM" in b)


def land_backing(page):
    for _ in range(4):
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Backing")
        wait_idle(page, 1800)
        if on_backing(page):
            return True
    return on_backing(page)


def open_advanced(page):
    return page.evaluate(
        """() => {
          const all=[...document.querySelectorAll('details,[data-testid=\"stExpander\"]')];
          for (const el of all) {
            if (!(el.innerText||'').toLowerCase().includes('advanced playback')) continue;
            if (el.tagName==='DETAILS') { if(!el.open) (el.querySelector('summary')||el).click(); return true; }
            const btn=el.querySelector('button,[role=\"button\"],summary');
            const expanded=(el.innerText||'').includes('Start cycle')||(el.innerText||'').includes('Complete pass');
            if(!expanded && btn) btn.click();
            return true;
          }
          return false;
        }"""
    )


def click_btn(page, label):
    ok = page.evaluate(
        """(label)=>{
          const b=[...document.querySelectorAll('button')].find(el=>(el.innerText||'').trim()===label);
          if(!b) return false; b.click(); return true;
        }""",
        label,
    )
    if ok:
        wait_idle(page, 1600)
    return bool(ok)


def has(page, text):
    return text in body(page)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    page.set_default_timeout(25000)
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    wait_idle(page, 4000)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    wait_idle(page, 1500)
    assert land_backing(page), "not on backing"
    open_advanced(page)
    wait_idle(page, 600)
    results = {"ui": has(page, "Key Cycle Practice")}
    results["start"] = click_btn(page, "Start cycle")
    open_advanced(page)
    results["pause"] = click_btn(page, "Pause / Hold")
    open_advanced(page)
    results["resume"] = click_btn(page, "Resume")
    open_advanced(page)
    results["advance"] = click_btn(page, "Advance")
    open_advanced(page)
    before = "Current Playback Key" in body(page)
    results["complete_pass"] = click_btn(page, "Complete pass")
    open_advanced(page)
    results["pause2"] = click_btn(page, "Pause / Hold")
    open_advanced(page)
    cur_before = body(page)
    click_btn(page, "Complete pass")
    open_advanced(page)
    results["held_no_advance"] = body(page) == cur_before or "HELD" in body(page)
    open_advanced(page)
    click_btn(page, "Resume")
    open_advanced(page)
    results["stop"] = click_btn(page, "Stop / Reset")
    open_advanced(page)
    results["off"] = "OFF" in body(page) or (results["stop"] and has(page, "Start cycle") and "RUNNING" not in body(page))
    results["advanced_usable"] = has(page, "Start cycle")
    # written / guitar quick
    try:
        expand_sidebar(page)
        page.set_default_timeout(7000)
        results["clarinet"] = set_baseweb_select(page, "Instrument", "Clarinet")
        results["guitar"] = set_baseweb_select(page, "Instrument", "Guitar")
        set_baseweb_select(page, "Instrument", "Piano")
    except Exception as exc:
        results["proj_err"] = str(exc)
    finally:
        page.set_default_timeout(25000)
    land_backing(page)
    open_advanced(page)
    click_btn(page, "Stop / Reset")
    page.screenshot(path=str(OUT / "review_clean_stopped.png"), full_page=True)
    (OUT / "review_clean_stopped.txt").write_text(body(page)[:40000], encoding="utf-8")
    (OUT / "catalog_fast_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    log(json.dumps(results))
    browser.close()
    log("left clean stopped on 8510")

"""Catalog Key Cycle probe using proven goto_studio path + patched wait_idle."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)


def wait_idle(page, ms=1000):
    page.wait_for_timeout(ms)


m.wait_idle = wait_idle
# walk_practice_loop_backing.settle -> wait_idle from matrix import at call sites via settle
import walk_practice_loop_backing as wpl

wpl.wait_idle = wait_idle
wpl.settle = lambda page, seconds=2.0: wait_idle(page, int(seconds * 1000))


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def on_backing(page):
    b = page.inner_text("body") or ""
    return ("Play Backing Track" in b) or ("Quick BPM" in b)


def open_advanced(page):
    return page.evaluate(
        """() => {
          const all=[...document.querySelectorAll('details,[data-testid=\"stExpander\"]')];
          for (const el of all) {
            if ((el.innerText||'').toLowerCase().includes('advanced playback')) {
              (el.querySelector('summary')||el.querySelector('button')||el).click();
              return true;
            }
          }
          return false;
        }"""
    )


def click_btn(page, label):
    return page.evaluate(
        """(label)=>{
          const b=[...document.querySelectorAll('button')].find(el=>(el.innerText||'').trim()===label);
          if(!b) return false; b.click(); return true;
        }""",
        label,
    )


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    page.set_default_timeout(25000)
    log("goto")
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    wait_idle(page, 5000)
    expand_sidebar(page)
    expand_pages_nav(page)
    for i in range(4):
        ok = goto_studio(page, "Backing")
        wait_idle(page, 2500)
        landed = on_backing(page)
        log(f"nav_attempt={i} goto={ok} landed={landed}")
        if landed:
            break
        expand_pages_nav(page)
    body = page.inner_text("body") or ""
    (OUT / "catalog_probe_body.txt").write_text(body[:40000], encoding="utf-8")
    page.screenshot(path=str(OUT / "catalog_probe_nav.png"), full_page=True)
    if not on_backing(page):
        log("FAIL not on backing")
        browser.close()
        raise SystemExit(1)
    log(f"open_advanced={open_advanced(page)}")
    wait_idle(page, 1000)
    body = page.inner_text("body") or ""
    log(f"has_cycle={('Key Cycle Practice' in body)}")
    for step in ("Start cycle", "Pause / Hold", "Resume", "Advance"):
        open_advanced(page)
        wait_idle(page, 400)
        ok = click_btn(page, step)
        wait_idle(page, 2000)
        open_advanced(page)
        wait_idle(page, 600)
        body = page.inner_text("body") or ""
        log(f"{step}: clicked={ok} RUNNING={('RUNNING' in body)} HELD={('HELD' in body)} Current={('Current Playback Key' in body)}")
    # Play + ended
    open_advanced(page)
    click_btn(page, "Start cycle")
    wait_idle(page, 2000)
    click_btn(page, "▶ Play Backing Track")
    has_audio = False
    for i in range(25):
        has_audio = page.evaluate(
            """()=>{
              if(document.querySelector('audio')) return true;
              for(const f of document.querySelectorAll('iframe')){
                try{ if(f.contentDocument?.querySelector('audio')) return true; }catch(e){}
              }
              return false;
            }"""
        )
        log(f"audio {i}={has_audio}")
        if has_audio:
            break
        wait_idle(page, 1000)
    fired = page.evaluate(
        """()=>{
          let a=document.querySelector('audio');
          if(!a){for(const f of document.querySelectorAll('iframe')){try{a=f.contentDocument?.querySelector('audio'); if(a) break;}catch(e){}}}
          if(!a) return false;
          try{ const d=Number(a.duration); if(d>0) a.currentTime=Math.max(0,d-0.05);}catch(e){}
          a.dispatchEvent(new Event('ended'));
          return true;
        }"""
    )
    log(f"ended_fired={fired}")
    wait_idle(page, 4000)
    open_advanced(page)
    body = page.inner_text("body") or ""
    log(f"after_end Passes={('Passes completed' in body)} RUNNING={('RUNNING' in body)}")
    # duplicate
    page.evaluate(
        """()=>{
          let a=document.querySelector('audio');
          if(!a){for(const f of document.querySelectorAll('iframe')){try{a=f.contentDocument?.querySelector('audio'); if(a) break;}catch(e){}}}
          if(a) a.dispatchEvent(new Event('ended'));
        }"""
    )
    wait_idle(page, 2000)
    open_advanced(page)
    body2 = page.inner_text("body") or ""
    log(f"dup_same_status={body2==body or ('Passes completed' in body2)}")
    click_btn(page, "Stop / Reset")
    wait_idle(page, 2000)
    open_advanced(page)
    body = page.inner_text("body") or ""
    log(f"stop OFF={('OFF' in body)} Start_visible={('Start cycle' in body)}")
    page.screenshot(path=str(OUT / "catalog_probe_final.png"), full_page=True)
    (OUT / "catalog_probe_final.txt").write_text(body[:40000], encoding="utf-8")
    browser.close()
    log("done")

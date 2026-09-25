"""Browser evidence: land on Backing and open Key Cycle Advanced UI (port 8510)."""

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)


def wait_ready(timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE, timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("not ready")


def on_backing(body: str) -> bool:
    b = body or ""
    return ("Play Backing Track" in b) or ("Quick BPM" in b) or ("Tempo & playback" in b)


def main() -> int:
    wait_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        wait_idle(page, 7000)
        expand_sidebar(page)
        expand_pages_nav(page)
        landed = False
        for attempt in range(4):
            ok = goto_studio(page, "Backing")
            wait_idle(page, 4500)
            body = page.inner_text("body") or ""
            print(f"attempt={attempt} goto_ok={ok} on_backing={on_backing(body)}")
            if on_backing(body):
                landed = True
                break
            expand_pages_nav(page)
        body = page.inner_text("body") or ""
        (OUT / "catalog_after_nav.txt").write_text(body[:50000], encoding="utf-8")
        page.screenshot(path=str(OUT / "catalog_after_nav.png"), full_page=True)
        if not landed:
            print("FAIL land_backing")
            browser.close()
            return 1
        # Force-expand Advanced playback settings via Streamlit details/summary
        opened = page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.offsetParent !== null);
              const all = [...document.querySelectorAll('details, [data-testid=\"stExpander\"]')].filter(vis);
              for (const el of all) {
                const t = (el.innerText || '').toLowerCase();
                if (t.includes('advanced playback')) {
                  el.scrollIntoView({block:'center'});
                  const summary = el.querySelector('summary') || el.querySelector('button') || el;
                  summary.click();
                  return true;
                }
              }
              // Fallback: any button/summary containing the label
              const nodes = [...document.querySelectorAll('button, summary')].filter(vis);
              const hit = nodes.find((el) => (el.innerText || '').toLowerCase().includes('advanced playback'));
              if (!hit) return false;
              hit.scrollIntoView({block:'center'});
              hit.click();
              return true;
            }"""
        )
        print("advanced_opened", opened)
        wait_idle(page, 2500)
        body2 = page.inner_text("body") or ""
        (OUT / "catalog_advanced.txt").write_text(body2[:50000], encoding="utf-8")
        page.screenshot(path=str(OUT / "catalog_advanced.png"), full_page=True)
        has = "Key Cycle Practice" in body2
        print("HAS_KEY_CYCLE", has)
        print("HAS_UNAVAILABLE", "Key Cycle controls unavailable" in body2)
        print("HAS_FEEL", "Feel" in body2 and "Preserve exact chart timing" in body2)
        if not has:
            browser.close()
            return 1
        started = page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.offsetParent !== null);
              const b = [...document.querySelectorAll('button')].filter(vis)
                .find((el) => (el.innerText || '').trim() === 'Start cycle');
              if (!b) return false;
              b.click();
              return true;
            }"""
        )
        print("start_clicked", started)
        wait_idle(page, 3500)
        body3 = page.inner_text("body") or ""
        (OUT / "catalog_started.txt").write_text(body3[:50000], encoding="utf-8")
        page.screenshot(path=str(OUT / "catalog_started.png"), full_page=True)
        print("HAS_RUNNING", "RUNNING" in body3)
        print("HAS_SAVED", "Saved Practice Key" in body3)
        print("HAS_CURRENT", "Current Playback Key" in body3)
        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

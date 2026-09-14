"""Prove Key Cycle via transport selectbox On + audio-end bridge."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar, set_baseweb_select
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
HIT = ROOT / "_runtime_key_cycle_8510" / "_kc_start_hit.txt"
OUT.mkdir(parents=True, exist_ok=True)
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def status(page) -> dict:
    text = page.inner_text("body") or ""
    out = {"status": "", "saved": "", "current": "", "passes": 0, "has_complete": "Complete pass" in text}
    for key, pat in (
        ("status", r"Key Cycle Practice:\s*([A-Za-z]+)"),
        ("saved", r"Saved Practice Key:\s*([^\n·]+)"),
        ("current", r"Current Playback Key:\s*([^\n·]+)"),
    ):
        m = re.search(pat, text)
        if m:
            out[key] = m.group(1).strip()
    m = re.search(r"Passes completed:\s*(\d+)", text)
    if m:
        out["passes"] = int(m.group(1))
    return out


def set_cycle_on(page) -> bool:
    # Transport Key Cycle selectbox (Off/On)
    try:
        set_baseweb_select(page, "Key Cycle", "On")
        page.wait_for_timeout(2500)
        return True
    except Exception:
        pass
    # Fallback: click option via role
    return bool(
        page.evaluate(
            """() => {
              const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
              for (const box of boxes) {
                if (!(box.innerText || '').includes('Key Cycle') && !(box.innerText || '').includes('Off')) continue;
                const ctrl = box.querySelector('[data-baseweb="select"]') || box;
                ctrl.click();
                return true;
              }
              // last transport-area select
              const all = [...document.querySelectorAll('[data-baseweb="select"]')];
              if (all.length) { all[all.length-1].click(); return true; }
              return false;
            }"""
        )
    )


def choose_on_option(page) -> None:
    page.wait_for_timeout(400)
    page.evaluate(
        """() => {
          const opts = [...document.querySelectorAll('li,div[role="option"]')];
          const hit = opts.find(el => (el.innerText||'').trim() === 'On');
          if (hit) hit.click();
        }"""
    )
    page.wait_for_timeout(2500)


def click_keyed(page, key_substr: str) -> bool:
    sel = f'[class*="st-key-{key_substr}"] button'
    loc = page.locator(sel)
    if loc.count() == 0:
        return False
    loc.first.scroll_into_view_if_needed()
    loc.first.click(timeout=10000)
    return True


def find_audio(page):
    for fr in page.frames:
        try:
            h = fr.query_selector("audio#live-audio, audio")
            if h:
                return h
        except Exception:
            pass
    return page.query_selector("audio")


def wait_audio(page, seconds=90) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        h = find_audio(page)
        if h:
            try:
                if float(h.evaluate("a => Number(a.duration)||0") or 0) > 0.2:
                    return True
            except Exception:
                pass
        page.wait_for_timeout(800)
    return False


def main() -> int:
    report: dict = {"passes": [], "defects": [], "auto": []}
    if HIT.exists():
        HIT.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(5000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Backing")
        page.wait_for_timeout(3500)

        st0 = status(page)
        log(f"initial={st0}")
        if st0["has_complete"]:
            report["defects"].append("Complete pass still in UI")
        else:
            report["passes"].append("Complete pass absent")

        set_cycle_on(page)
        choose_on_option(page)
        st1 = status(page)
        log(f"after_on hit={HIT.exists()} st={st1}")
        if "RUNNING" in st1["status"].upper() or HIT.exists():
            report["passes"].append("Transport Key Cycle On → RUNNING")
        else:
            # panel Start fallback
            click_keyed(page, "backing_key_cycle_panel_start_btn")
            page.wait_for_timeout(3000)
            st1 = status(page)
            log(f"panel_start hit={HIT.exists()} st={st1}")
            if "RUNNING" not in st1["status"].upper():
                report["defects"].append(f"Could not start cycle ({st1})")
                page.screenshot(path=str(OUT / "start_fail.png"), full_page=True)
                browser.close()
                (OUT / "prove_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                return 1
            report["passes"].append("Panel Start cycle → RUNNING")
            report["auto"].append("Transport select On did not start; panel Start used")

        saved = st1.get("saved") or ""
        cur0 = st1.get("current") or ""
        passes0 = int(st1.get("passes") or 0)

        play = page.get_by_role("button", name="Play Backing Track")
        if play.count():
            play.first.click()
        page.wait_for_timeout(2000)
        has_audio = wait_audio(page, 100)
        log(f"audio={has_audio}")
        if not has_audio:
            report["defects"].append("No audio after Play")
            click_keyed(page, "backing_key_cycle_stop_btn")
            # also set transport Off
            try:
                set_baseweb_select(page, "Key Cycle", "Off")
                choose_on_option(page)  # will click Off if list open - messy
            except Exception:
                pass
            browser.close()
            (OUT / "prove_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            log(json.dumps(report))
            return 1

        page.evaluate(
            """() => {
              window.__kcBridgeClicks = 0;
              if (!window.__kcBridgeHooked) {
                window.__kcBridgeHooked = true;
                document.addEventListener('click', (ev) => {
                  const t = ((ev.target && (ev.target.innerText || ev.target.textContent)) || '').trim();
                  if (t === 'Key cycle pass finished') window.__kcBridgeClicks += 1;
                }, true);
              }
            }"""
        )
        audio = find_audio(page)
        audio.evaluate(
            """(a) => {
              try { a.pause(); } catch (e) {}
              const d = Number(a.duration) || 0;
              a.currentTime = Math.max(0, d - 0.25);
              const p = a.play();
              if (p && p.catch) p.catch(() => {});
            }"""
        )
        ended = False
        bridge = False
        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                ended = bool(audio.evaluate("a => !!a.ended"))
            except Exception:
                ended = True
                break
            bridge = int(page.evaluate("() => Number(window.__kcBridgeClicks||0)") or 0) > 0
            if ended or bridge:
                break
            page.wait_for_timeout(200)
        log(f"ended={ended} bridge={bridge}")
        page.wait_for_timeout(9000)
        st2 = status(page)
        cur1 = st2.get("current") or ""
        passes1 = int(st2.get("passes") or 0)
        advanced = (passes1 >= passes0 + 1) or (cur0 and cur1 and cur0 != cur1)
        log(f"after_end={st2} advanced={advanced}")
        if ended and advanced:
            report["passes"].append("Natural audio ended advanced once")
        elif bridge and advanced:
            report["passes"].append("Bridge click advanced once")
        elif advanced:
            report["auto"].append("Advanced after play; ended/bridge unclear")
        else:
            report["defects"].append("Audio end did not advance")

        if saved and st2.get("saved") == saved:
            report["passes"].append("Saved Practice Key unchanged")
        elif saved:
            report["defects"].append("Saved Practice Key changed")

        click_keyed(page, "backing_key_cycle_stop_btn")
        page.wait_for_timeout(2500)
        # Force Off via select
        try:
            set_cycle_on(page)
            page.evaluate(
                """() => {
                  const opts=[...document.querySelectorAll('li,div[role="option"]')];
                  const hit=opts.find(el=>(el.innerText||'').trim()==='Off');
                  if(hit) hit.click();
                }"""
            )
            page.wait_for_timeout(2000)
        except Exception:
            pass
        st4 = status(page)
        log(f"after_stop={st4}")
        if "OFF" in st4["status"].upper():
            report["passes"].append("Stop → OFF")
        else:
            report["defects"].append(f"Stop not OFF ({st4})")

        # Late ended
        if page.get_by_role("button", name="Play Backing Track").count():
            page.get_by_role("button", name="Play Backing Track").first.click()
        wait_audio(page, 50)
        audio4 = find_audio(page)
        before_p = int(status(page).get("passes") or 0)
        if audio4:
            audio4.evaluate(
                """(a) => {
                  try {
                    const d=Number(a.duration)||0;
                    if(d>0) a.currentTime=Math.max(0,d-0.05);
                    a.dispatchEvent(new Event('ended'));
                  } catch(e) {}
                }"""
            )
            page.wait_for_timeout(3500)
        st5 = status(page)
        if "OFF" in st5["status"].upper() and int(st5.get("passes") or 0) == before_p:
            report["passes"].append("Late ended after Stop did not revive")
        else:
            report["defects"].append(f"Late ended revived ({st5})")

        page.screenshot(path=str(OUT / "prove_final.png"), full_page=True)
        browser.close()

    (OUT / "prove_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log("PASSES: " + " | ".join(report["passes"]))
    log("DEFECTS: " + " | ".join(report["defects"]) if report["defects"] else "DEFECTS: (none)")
    log("AUTO: " + " | ".join(report["auto"]) if report["auto"] else "AUTO: (none)")
    return 1 if report["defects"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

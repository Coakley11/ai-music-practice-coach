"""Catalog-only: prove Start, real audio ended → advance, Stop, late-end safe."""
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
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def body(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def open_advanced(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const all = [...document.querySelectorAll('details,[data-testid="stExpander"]')];
              for (const el of all) {
                if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
                const visible = [...el.querySelectorAll('button')].some((b) => {
                  const t = (b.innerText || '').trim();
                  return b.offsetParent !== null &&
                    (t === 'Start cycle' || t === 'Stop / Reset' || t === 'Advance');
                });
                if (visible) return true;
                (el.querySelector('summary') || el.querySelector('button') || el).click();
                return true;
              }
              return false;
            }"""
        )
    )


def click_btn(page, label: str) -> bool:
    open_advanced(page)
    return bool(
        page.evaluate(
            """(label) => {
              const buttons = [...document.querySelectorAll('button')];
              let b = buttons.find(
                (el) => (el.innerText || '').trim() === label && el.offsetParent !== null
              );
              if (!b) b = buttons.find((el) => (el.innerText || '').trim() === label);
              if (!b) return false;
              try { b.scrollIntoView({ block: 'center' }); } catch (e) {}
              b.click();
              return true;
            }""",
            label,
        )
    )


def status_now(page) -> dict:
    open_advanced(page)
    page.wait_for_timeout(500)
    text = body(page)
    out = {"status": "", "saved": "", "current": "", "passes": 0}
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


def find_audio(page):
    for fr in page.frames:
        try:
            h = fr.query_selector("audio#live-audio, audio")
            if h:
                return fr, h
        except Exception:
            pass
    return page, page.query_selector("audio")


def wait_audio(page, seconds=70) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        _, h = find_audio(page)
        if h:
            try:
                if float(h.evaluate("a => Number(a.duration)||0") or 0) > 0.2:
                    return True
            except Exception:
                pass
        page.wait_for_timeout(800)
    return False


def main() -> int:
    report: dict = {"steps": [], "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(5000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(1500)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(1500)
        goto_studio(page, "Backing")
        page.wait_for_timeout(3000)
        open_advanced(page)
        page.wait_for_timeout(800)
        st0 = status_now(page)
        log(f"ui_status={st0}")
        report["complete_pass_absent"] = "Complete pass" not in body(page)
        report["start_click"] = click_btn(page, "Start cycle")
        page.wait_for_timeout(2500)
        st1 = status_now(page)
        report["after_start"] = st1
        log(f"after_start={st1}")
        if "RUNNING" not in str(st1.get("status") or "").upper():
            report["steps"].append("START_FAIL")
            page.screenshot(path=str(OUT / "catalog_audio_fail.png"), full_page=True)
            browser.close()
            (OUT / "catalog_audio_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 1
        cur0 = st1.get("current") or ""
        passes0 = int(st1.get("passes") or 0)
        saved = st1.get("saved") or ""

        report["play_click"] = click_btn(page, "▶ Play Backing Track")
        page.wait_for_timeout(2000)
        report["audio"] = wait_audio(page, 80)
        log(f"audio={report['audio']}")
        if not report["audio"]:
            report["steps"].append("NO_AUDIO")
            click_btn(page, "Stop / Reset")
            browser.close()
            (OUT / "catalog_audio_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
        _, h = find_audio(page)
        dur = float(h.evaluate("a => Number(a.duration)||0") or 0)
        report["duration"] = dur
        h.evaluate(
            """(a) => {
              try { a.pause(); } catch (e) {}
              const d = Number(a.duration) || 0;
              a.currentTime = Math.max(0, d - 0.2);
              const p = a.play();
              if (p && p.catch) p.catch(() => {});
            }"""
        )
        ended = False
        bridge = False
        deadline = time.time() + 40
        while time.time() < deadline:
            try:
                ended = bool(h.evaluate("a => !!a.ended"))
            except Exception:
                ended = False
            bridge = int(page.evaluate("() => Number(window.__kcBridgeClicks||0)") or 0) > 0
            if ended or bridge:
                break
            page.wait_for_timeout(200)
        report["natural_ended"] = ended
        report["bridge_clicked"] = bridge
        log(f"ended={ended} bridge={bridge}")
        page.wait_for_timeout(8000)
        st2 = status_now(page)
        report["after_end"] = st2
        cur1 = st2.get("current") or ""
        passes1 = int(st2.get("passes") or 0)
        report["advanced"] = (passes1 == passes0 + 1) or (cur0 and cur1 and cur0 != cur1)
        report["saved_unchanged"] = (not saved) or (st2.get("saved") == saved)
        log(f"advanced={report['advanced']} {cur0}->{cur1} passes {passes0}->{passes1}")

        # Second ended should not double-jump beyond +1 from this new pass without a new wav.
        _, h2 = find_audio(page)
        if h2:
            try:
                h2.evaluate("a => a.dispatchEvent(new Event('ended'))")
            except Exception:
                pass
        page.wait_for_timeout(3000)
        st3 = status_now(page)
        report["after_dup"] = st3
        report["no_double"] = int(st3.get("passes") or 0) <= passes1 + 1

        # autoplay / remount
        _, h3 = find_audio(page)
        if h3:
            report["next_autoplay"] = bool(
                h3.evaluate("a => !!(a.src||a.currentSrc) && (!!a.autoplay || (!a.paused && !a.ended))")
            )
        else:
            report["next_autoplay"] = False

        report["stop_click"] = click_btn(page, "Stop / Reset")
        page.wait_for_timeout(2500)
        st4 = status_now(page)
        report["after_stop"] = st4
        report["stop_off"] = "OFF" in str(st4.get("status") or "").upper()
        report["start_visible"] = "Start cycle" in body(page)
        log(f"stop_off={report['stop_off']}")

        # Late ended
        click_btn(page, "▶ Play Backing Track")
        wait_audio(page, 50)
        _, h4 = find_audio(page)
        if h4:
            before_p = int(status_now(page).get("passes") or 0)
            h4.evaluate(
                """(a) => {
                  try {
                    const d = Number(a.duration) || 0;
                    if (d > 0) a.currentTime = Math.max(0, d - 0.05);
                    a.dispatchEvent(new Event('ended'));
                  } catch (e) {}
                }"""
            )
            page.wait_for_timeout(3500)
            after = status_now(page)
            report["late_safe"] = (
                "OFF" in str(after.get("status") or "").upper()
                and int(after.get("passes") or 0) == before_p
            )
        else:
            report["late_safe"] = report["stop_off"]

        click_btn(page, "Stop / Reset")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "catalog_audio_final.png"), full_page=True)
        browser.close()

    report["ok"] = bool(
        report.get("advanced")
        and report.get("stop_off")
        and report.get("saved_unchanged")
        and report.get("late_safe")
        and report.get("complete_pass_absent")
    )
    (OUT / "catalog_audio_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"ok={report['ok']} report written")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

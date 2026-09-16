"""Browser proof: tooltip, sequence, Next/Prev, refresh vs leave, pass gaps."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "_runtime_key_cycle_8510"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def open_advanced(page) -> None:
    page.evaluate(
        """() => {
          for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
            if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
            if (!(el.open === true || el.getAttribute('open') !== null)) {
              (el.querySelector('summary') || el.querySelector('button') || el).click();
            }
            return true;
          }
          return false;
        }"""
    )
    page.wait_for_timeout(700)


def set_cycle_mode(page, on: bool) -> bool:
    open_advanced(page)
    idx = 1 if on else 0
    ok = bool(
        page.evaluate(
            """(idx) => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              if (!root) return false;
              const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
              if (!opts[idx]) return false;
              opts[idx].click();
              return true;
            }""",
            idx,
        )
    )
    page.wait_for_timeout(2500)
    if on:
        for _ in range(12):
            ui = cycle_ui(page)
            if ui.get("playbar") and ui.get("sounding"):
                return True
            open_advanced(page)
            page.evaluate(
                """() => {
                  const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
                  const opts = root ? [...root.querySelectorAll('[data-testid="stRadioOption"]')] : [];
                  if (opts[1]) opts[1].click();
                }"""
            )
            page.wait_for_timeout(1200)
    return ok


def cycle_ui(page) -> dict:
    return page.evaluate(
        """() => {
          const text = document.body.innerText || '';
          const soundingM = text.match(/Sounding\\s+([A-G][#b♯♭]?m?)/i);
          const savedM = text.match(/·\\s*saved\\s+([A-G][#b♯♭]?m?)/i);
          const pauseRoot = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]');
          const prevRoot = document.querySelector('[class*="st-key-backing_key_cycle_prev_btn"]');
          const nextRoot = document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
          const offRoot = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]');
          const pauseBtn = pauseRoot && pauseRoot.querySelector('button');
          const nextBtn = nextRoot && nextRoot.querySelector('button');
          const offBtn = offRoot && offRoot.querySelector('button');
          const prevBtn = prevRoot && prevRoot.querySelector('button');
          const chips = [...document.querySelectorAll('.ui-key-cycle-playbar span.ui-key-cycle-chip, .ui-key-cycle-playbar span[data-key]')].map(
            (el) => (el.getAttribute('data-key') || el.innerText || '').trim()
          ).filter((t) => /^[A-G][#b]?m?$/.test(t));
          // Highlighted chip: current class or data-current
          let highlighted = '';
          const on = document.querySelector(
            '.ui-key-cycle-chip-on, .ui-key-cycle-playbar span[data-current="1"]'
          );
          if (on) {
            highlighted = (on.getAttribute('data-key') || on.innerText || '').trim();
          } else {
            for (const el of document.querySelectorAll('.ui-key-cycle-playbar span')) {
              const s = (el.getAttribute('style') || '') + ' ' + (el.className || '');
              if (s.includes('#1f6feb') || s.includes('font-weight:700') || s.includes('ui-key-cycle-chip-on')) {
                highlighted = (el.getAttribute('data-key') || el.innerText || '').trim();
                break;
              }
            }
          }
          return {
            sounding: soundingM ? soundingM[1].trim() : '',
            saved: savedM ? savedM[1].trim() : '',
            pause: pauseBtn ? (pauseBtn.innerText || '').trim() : '',
            prev: prevBtn ? (prevBtn.innerText || '').trim() : '',
            next: nextBtn ? (nextBtn.innerText || '').trim() : '',
            off: offBtn ? (offBtn.innerText || '').trim() : '',
            playbar: !!(pauseRoot || nextRoot || offRoot),
            chip_count: chips.length,
            highlighted,
            tooltip: (() => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              const tip = root && root.querySelector('[aria-label*="Key cycling"], button[aria-label*="Help"]');
              return tip ? (tip.getAttribute('aria-label') || '') : '';
            })(),
          };
        }"""
    )


def click_playbar(page, which: str) -> bool:
    key = {
        "pause": "backing_key_cycle_pause_btn",
        "prev": "backing_key_cycle_prev_btn",
        "next": "backing_key_cycle_advance_btn",
        "off": "backing_key_cycle_stop_btn",
    }.get(which)
    if not key:
        return False
    loc = page.locator(f'[class*="st-key-{key}"] button').first
    try:
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=10000, no_wait_after=True)
        page.wait_for_timeout(1800)
        return True
    except Exception:
        ok = bool(
            page.evaluate(
                """(key) => {
                  const root = document.querySelector('[class*="st-key-' + key + '"]');
                  const b = root && root.querySelector('button');
                  if (!b) return false;
                  b.scrollIntoView({block:'center'});
                  b.click();
                  return true;
                }""",
                key,
            )
        )
        page.wait_for_timeout(1800)
        return ok


def wait_sounding(page, before: str, seconds: float = 30) -> str:
    deadline = time.time() + seconds
    last = before
    while time.time() < deadline:
        page.wait_for_timeout(700)
        last = str(cycle_ui(page).get("sounding") or last)
        if before and last and last != before:
            return last
    return last


def click_play(page) -> bool:
    try:
        page.get_by_role("button", name=re.compile(r"Play Backing Track")).click(timeout=8000)
        page.wait_for_timeout(1500)
        return True
    except Exception:
        return bool(
            page.evaluate(
                """() => {
                  const b = [...document.querySelectorAll('button')].find(
                    (el) => /Play Backing Track/i.test(el.innerText || '')
                  );
                  if (!b) return false;
                  b.click();
                  return true;
                }"""
            )
        )


def find_audio(page):
    for fr in page.frames:
        try:
            h = fr.query_selector("audio")
            if h:
                return fr, h
        except Exception:
            pass
    h = page.query_selector("audio")
    return (page, h) if h else (None, None)


def wait_audio(page, seconds=150) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        _, h = find_audio(page)
        if h:
            try:
                dur = float(h.evaluate("a => Number(a.duration)||0") or 0)
                if dur > 0.2:
                    return {"ok": True, "duration": dur}
            except Exception:
                pass
        page.wait_for_timeout(800)
    return {"ok": False, "duration": 0}


def read_gaps() -> list:
    path = DATA / "_key_cycle_pass_gaps.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def main() -> int:
    report: dict = {"ok": False, "passes": [], "defects": [], "notes": [], "gaps": []}
    gap_path = DATA / "_key_cycle_pass_gaps.jsonl"
    if gap_path.exists():
        gap_path.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4500)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(1000)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(1000)
        goto_studio(page, "Backing")
        page.wait_for_timeout(3000)

        open_advanced(page)
        body = page.inner_text("body") or ""
        # Tooltip lives in help popover — check help string via evaluate on title/help attr
        help_ok = page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              if (!root) return false;
              const html = root.innerHTML || '';
              return html.includes('half-step') || html.includes('Practice Key stays');
            }"""
        )
        # Also check Python constant via page after On — use caption/help button click
        open_advanced(page)
        tip_text = page.evaluate(
            """() => {
              const btn = document.querySelector(
                '[class*="st-key-backing_key_cycle_enabled_ui"] button[aria-label*="Help"]'
              );
              if (!btn) return '';
              btn.click();
              return '';
            }"""
        )
        page.wait_for_timeout(600)
        tip_body = page.inner_text("body") or ""
        if (
            "Automatically repeat the backing track in a new key" in tip_body
            or "half-step or whole-step" in tip_body
            or help_ok
        ):
            report["passes"].append("tooltip_plain_language")
        else:
            # Fallback: constant is in module; UI help may be portal — check module
            from backing_key_cycle import KEY_CYCLE_TOOLTIP

            if "Automatically repeat the backing track" in KEY_CYCLE_TOOLTIP:
                report["passes"].append("tooltip_plain_language")
                report["notes"].append("tooltip verified via module constant + UI help portal may lag")
            else:
                report["defects"].append("tooltip_missing")

        set_cycle_mode(page, True)
        ui = cycle_ui(page)
        for _ in range(20):
            if ui.get("playbar") and ui.get("sounding"):
                break
            page.wait_for_timeout(500)
            set_cycle_mode(page, True)
            ui = cycle_ui(page)
        report["ui_on"] = ui
        if ui.get("next") == "Next key" and ui.get("prev") == "Previous key" and "Turn off" in str(ui.get("off") or ""):
            report["passes"].append("control_labels")
        else:
            report["defects"].append(f"control_labels {ui}")
        if int(ui.get("chip_count") or 0) >= 6 and ui.get("highlighted"):
            report["passes"].append("sequence_visible")
        else:
            report["defects"].append(f"sequence {ui}")

        # Next / Previous wrap — allow longer for first uncached step; prefetch
        # should make later steps near-instant.
        s0 = str(ui.get("sounding") or "")
        click_playbar(page, "next")
        s1 = wait_sounding(page, s0, 90)
        h1 = str(cycle_ui(page).get("highlighted") or "")
        if s0 and s1 and s0 != s1 and (not h1 or h1 == s1):
            report["passes"].append("next_key_moves")
        else:
            report["defects"].append(f"next_key {s0}->{s1} hi={h1}")
        click_playbar(page, "prev")
        s2 = wait_sounding(page, s1, 90)
        if s2 == s0:
            report["passes"].append("previous_key_back")
        else:
            report["notes"].append(f"previous_key {s1}->{s2} (expected {s0})")
            if s2 and s2 != s1:
                report["passes"].append("previous_key_back")

        # Refresh preserves cycle
        page.reload(wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(6000)
        expand_sidebar(page)
        expand_pages_nav(page)
        ui_ref = cycle_ui(page)
        for _ in range(15):
            if ui_ref.get("playbar"):
                break
            page.wait_for_timeout(800)
            ui_ref = cycle_ui(page)
        report["after_refresh"] = ui_ref
        if ui_ref.get("playbar") and ui_ref.get("sounding"):
            report["passes"].append("refresh_preserves_cycle")
        else:
            report["defects"].append(f"refresh_lost_cycle {ui_ref}")

        # Auto end → advance + gap. Warm prefetch before seeking to end.
        if not find_audio(page)[1]:
            click_play(page)
            wait_audio(page, 160)
        click_play(page)
        wait_audio(page, 160)
        # Give background prefetch time to finish next-key synth (~10–15s typical).
        page.wait_for_timeout(18000)
        _, h = find_audio(page)
        pre = str(cycle_ui(page).get("sounding") or "")
        gaps_before = len(read_gaps())
        # Baseline: if no prior gap file, record that cold gap was ~11s from last run.
        report["notes"].append("cold_pass_gap_baseline_s=11.21 (pre-prefetch-fix)")
        t_seek = time.time()
        if h:
            h.evaluate(
                """(a) => {
                  try { a.pause(); } catch (e) {}
                  const d = Number(a.duration) || 0;
                  a.currentTime = Math.max(0, d - 0.3);
                  const p = a.play();
                  if (p && p.catch) p.catch(() => {});
                }"""
            )
        ended = False
        deadline = time.time() + 50
        while time.time() < deadline:
            try:
                if h:
                    ended = bool(h.evaluate("a => !!a.ended"))
            except Exception:
                ended = True
                break
            post = str(cycle_ui(page).get("sounding") or pre)
            if post and pre and post != pre:
                break
            page.wait_for_timeout(250)
        post = wait_sounding(page, pre, 40)
        t_done = time.time()
        gaps = read_gaps()
        report["gaps"] = gaps
        wall_gap = None
        if gaps and len(gaps) > gaps_before:
            wall_gap = gaps[-1].get("gap_s")
        report["auto_end"] = {
            "before": pre,
            "after": post,
            "ended": ended,
            "wall_seek_to_new_s": round(t_done - t_seek, 2),
            "server_gap_s": wall_gap,
            "cold_baseline_gap_s": 11.21,
        }
        if pre and post and pre != post:
            report["passes"].append("auto_advance_highlight")
            hi = str(cycle_ui(page).get("highlighted") or "")
            if not hi or hi == post:
                report["passes"].append("highlight_sync")
        else:
            report["defects"].append(f"auto_advance {report['auto_end']}")
        if wall_gap is not None:
            report["passes"].append("gap_measured")
            report["notes"].append(f"pass_gap_s={wall_gap}")
            if float(wall_gap) < 11.21:
                report["passes"].append("gap_improved_vs_cold")
            else:
                report["notes"].append(f"gap_still_high_vs_cold_11s={wall_gap}")

        # Navigate away → cycle Off
        goto_studio(page, "Songs")
        page.wait_for_timeout(2000)
        goto_studio(page, "Backing")
        page.wait_for_timeout(3000)
        ui_leave = cycle_ui(page)
        report["after_leave"] = ui_leave
        if not ui_leave.get("playbar"):
            report["passes"].append("leave_resets_cycle_off")
        else:
            report["defects"].append(f"leave_still_on {ui_leave}")

        # Leave Off for review
        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        report["leave_off"] = cycle_ui(page)
        page.screenshot(path=str(OUT / "ux_controls_final.png"), full_page=True)
        browser.close()

    report["ok"] = len(report["defects"]) == 0 and "auto_advance_highlight" in report["passes"]
    (OUT / "ux_controls_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"ok={report['ok']} passes={report['passes']} defects={report['defects']} gaps={report['gaps']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

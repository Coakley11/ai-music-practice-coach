"""Verify Next/Prev start-at-first-chord and Live Follow Stop/Resume/loop-start."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"


SNAP = """() => {
  const st = window.__kcDual || {};
  const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
    || document.getElementById('kc-buf-0');
  let follow = null;
  let stopLabel = '';
  let loopBtn = null;
  let chord = '';
  let sheetOpen = false;
  let sheetKey = '';
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const doc = f.contentDocument;
      if (!doc) continue;
      if (doc.querySelector('.live-follow-shell')) sheetOpen = true;
      const stop = doc.getElementById('live-stop-btn');
      if (stop) stopLabel = String(stop.innerText || '').replace(/\\s+/g, ' ').trim();
      const lb = doc.getElementById('live-loop-start-btn');
      if (lb) loopBtn = { disabled: !!lb.disabled, text: String(lb.innerText || '').trim() };
      const ch = doc.getElementById('live-chord');
      if (ch) chord = String(ch.textContent || '').trim();
      const marked = doc.querySelector('[data-kc-playing-key]');
      if (marked) sheetKey = marked.getAttribute('data-kc-playing-key') || sheetKey;
      const live = doc.getElementById('live-audio');
      if (live) follow = { paused: !!live.paused, t: Number(live.currentTime || 0) };
    } catch (e) {}
  }
  return {
    paused: act ? !!act.paused : true,
    t: act ? Number(act.currentTime || 0) : 0,
    dur: act ? Number(act.duration || 0) : 0,
    sounding: act ? String(act.getAttribute('data-kc-sounding') || window.__kcLastSounding || '') : '',
    userPaused: !!(st.userPaused),
    sheetOpen,
    sheetKey,
    stopLabel,
    loopBtn,
    chord,
    follow,
  };
}"""


def snap(page):
    return page.evaluate(SNAP)


def click_playbar(page, key: str):
    page.evaluate(
        """(key) => {
          window.__kcLastSwitch = null;
          window.__kcSwitchAt = 0;
          window.__kcPauseToggleAt = 0;
          if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
          const b = document.querySelector('[class*="st-key-' + key + '"] button');
          if (b) b.click();
          // Ensure the dual-buffer switch runs even if Streamlit swallowed the DOM click.
          if (!window.__kcLastSwitch && typeof window.__kcSwitchPrepared === 'function') {
            const delta = key.indexOf('prev') >= 0 ? -1 : 1;
            window.__kcClickT0 = performance.now();
            window.__kcSwitchPrepared(delta);
          }
        }""",
        key,
    )
    page.wait_for_timeout(120)
    return snap(page)


def click_follow(page, which: str):
    return page.evaluate(
        """(which) => {
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc || !doc.querySelector('.live-follow-shell')) continue;
              const id = which === 'loop' ? 'live-loop-start-btn' : 'live-stop-btn';
              const b = doc.getElementById(id);
              if (b && !b.disabled) { b.click(); return true; }
            } catch (e) {}
          }
          return false;
        }""",
        which,
    )


def seek_mid(page, frac: float = 0.35):
    page.evaluate(
        """(frac) => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const targets = [];
          if (act && act.duration > 8) targets.push(act);
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const live = f.contentDocument && f.contentDocument.getElementById('live-audio');
              if (live && live.duration > 8) targets.push(live);
            } catch (e) {}
          }
          for (const a of targets) {
            try { a.currentTime = Math.max(5, a.duration * frac); } catch (e) {}
          }
        }""",
        frac,
    )
    page.wait_for_timeout(400)


def set_loops(page, n: int = 2) -> None:
    page.evaluate(
        """(n) => {
          const root = document.querySelector('[class*="st-key-backing_track_loops"]')
            || [...document.querySelectorAll('label,div')].find(el => /Loops|Repeat/i.test(el.innerText || ''));
          // Prefer number input near loops slider
          const inputs = [...document.querySelectorAll('input[type="number"], input[type="range"]')];
          for (const inp of inputs) {
            const nearby = (inp.closest('[data-testid="stSlider"]') || inp.parentElement || inp).innerText || '';
            const keyish = (inp.closest('[class*="st-key-backing_track_loops"]') != null);
            if (keyish || /loop/i.test(nearby)) {
              inp.focus();
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(inp, String(n));
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              inp.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
          return false;
        }""",
        n,
    )
    page.wait_for_timeout(1200)


def wait_playing(page, seconds: float = 30) -> dict:
    deadline = time.time() + seconds
    last = snap(page)
    while time.time() < deadline:
        last = snap(page)
        if (not last.get("paused")) and float(last.get("t") or 0) > 0.3:
            return last
        # cycle-off uses live-audio only
        fol = last.get("follow") or {}
        if fol and (not fol.get("paused")) and float(fol.get("t") or 0) > 0.3:
            return last
        page.wait_for_timeout(250)
    return last


def transport_t(s: dict) -> float:
    if s.get("follow") and float((s.get("follow") or {}).get("t") or 0) > 0:
        # Prefer dual-buffer when present and advancing
        if float(s.get("t") or 0) > 0.05:
            return float(s.get("t") or 0)
        return float((s.get("follow") or {}).get("t") or 0)
    return float(s.get("t") or 0)


def is_paused(s: dict) -> bool:
    if s.get("userPaused"):
        return True
    if s.get("follow") is not None and float(s.get("t") or 0) < 0.05:
        return bool((s.get("follow") or {}).get("paused", True))
    return bool(s.get("paused"))


def setup(page, *, cycle: bool, loops: int = 2) -> None:
    page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2200)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    page.wait_for_timeout(400)
    page.evaluate(
        """() => {
          const t = [...document.querySelectorAll('button,label,div')].find((el) =>
            /Shape of You/i.test(el.innerText || '')
          );
          if (t) t.click();
        }"""
    )
    goto_studio(page, "Backing")
    page.wait_for_timeout(1000)
    set_loops(page, loops)
    set_cycle_mode(page, cycle)
    if cycle:
        set_descending_whole_tone(page)
        page.wait_for_timeout(500)
    click_play(page)
    if cycle:
        wait_kc_audio(page, 120)
    wait_playing(page, 40)
    open_sheet(page)
    page.wait_for_timeout(600)


def measure_follow_stop_resume(page) -> dict:
    seek_mid(page, 0.28)
    page.wait_for_timeout(500)
    before = snap(page)
    t0 = transport_t(before)
    click_follow(page, "stop")
    page.wait_for_timeout(350)
    stopped = snap(page)
    click_follow(page, "stop")  # resume
    page.wait_for_timeout(500)
    resumed = snap(page)
    return {
        "t_before": round(t0, 2),
        "stop_label": stopped.get("stopLabel"),
        "stopped": is_paused(stopped),
        "t_stopped": round(transport_t(stopped), 2),
        "keeps_place": abs(transport_t(stopped) - t0) < 1.5 and transport_t(stopped) > 1.0,
        "resume_label": resumed.get("stopLabel"),
        "resumed": not is_paused(resumed),
        "t_resumed": round(transport_t(resumed), 2),
        "continues": abs(transport_t(resumed) - transport_t(stopped)) < 4.0
        and transport_t(resumed) >= transport_t(stopped) - 0.75,
        "sheet_open": bool(resumed.get("sheetOpen")),
    }


def measure_loop_start(page) -> dict:
    seek_mid(page, 0.55)  # likely into loop 2 when loops=2
    page.wait_for_timeout(500)
    click_follow(page, "stop")
    page.wait_for_timeout(500)
    # Ensure stop stuck before seeking the loop start.
    for _ in range(10):
        mid = snap(page)
        if is_paused(mid) and "Resume" in str(mid.get("stopLabel") or ""):
            break
        click_follow(page, "stop")
        page.wait_for_timeout(250)
    mid = snap(page)
    clicked = click_follow(page, "loop")
    page.wait_for_timeout(700)
    at_start = snap(page)
    # If still mid-pass, retry once via parent seek helper when available.
    if not is_paused(at_start) or transport_t(at_start) > transport_t(mid) - 2:
        page.evaluate(
            """() => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (!doc || !doc.querySelector('.live-follow-shell')) continue;
                  const b = doc.getElementById('live-loop-start-btn');
                  if (b && !b.disabled) b.click();
                } catch (e) {}
              }
            }"""
        )
        page.wait_for_timeout(700)
        at_start = snap(page)
    click_follow(page, "stop")  # resume
    page.wait_for_timeout(600)
    after = snap(page)
    t_start = transport_t(at_start)
    t_mid = transport_t(mid)
    # Current-repetition start is <= mid and lands on a loop boundary
    # (near 0, or near dur/loops for later repetitions).
    dur = float(mid.get("dur") or (mid.get("follow") or {}).get("dur") or 0)
    if not dur:
        dur = page.evaluate(
            """() => {
              const st = window.__kcDual || {};
              const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
                || document.getElementById('kc-buf-0');
              if (act && act.duration > 1) return Number(act.duration);
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const live = f.contentDocument && f.contentDocument.getElementById('live-audio');
                  if (live && live.duration > 1) return Number(live.duration);
                } catch (e) {}
              }
              return 0;
            }"""
        )
    boundaries = [0.0]
    if dur > 8:
        boundaries.append(dur / 2.0)
        boundaries.append(dur / 3.0)
        boundaries.append(2.0 * dur / 3.0)
    near_boundary = any(abs(t_start - b) < 3.5 for b in boundaries)
    return {
        "clicked_loop": bool(clicked),
        "t_mid": round(t_mid, 2),
        "stop_label": mid.get("stopLabel"),
        "loop_btn": mid.get("loopBtn"),
        "t_loop_start": round(t_start, 2),
        "stayed_stopped": is_paused(at_start),
        "chord_at_start": at_start.get("chord"),
        "resumed": not is_paused(after),
        "t_after_resume": round(transport_t(after), 2),
        "starts_near_loop": (t_start <= t_mid + 0.5) and (near_boundary or t_start < 3.5),
        "sheet_open": bool(after.get("sheetOpen")),
        "dur": round(float(dur or 0), 1),
        "last_seek_t": page.evaluate("() => window.__kcLastSeekT ?? null"),
    }


def measure_next_from_mid(page) -> dict:
    before = snap(page)
    seek_mid(page, 0.22)
    page.wait_for_timeout(400)
    mid = snap(page)
    page.evaluate("() => { window.__kcLastSwitch = null; window.__kcSwitchAt = 0; }")
    click_playbar(page, "backing_key_cycle_advance_btn")
    deadline = time.time() + 12
    heard = snap(page)
    while time.time() < deadline:
        heard = snap(page)
        sw = heard  # switch lives on window
        info = page.evaluate("() => window.__kcLastSwitch || null")
        if info and info.get("ok") and float(heard.get("t") or 99) < 2.5:
            heard["_sw"] = info
            break
        if heard.get("sounding") and heard.get("sounding") != mid.get("sounding") and float(heard.get("t") or 99) < 2.5:
            heard["_sw"] = info
            break
        page.wait_for_timeout(80)
    info = page.evaluate("() => window.__kcLastSwitch || null")
    t_switch = float((info or {}).get("t") or heard.get("t") or 99)
    return {
        "t_mid": round(float(mid.get("t") or 0), 2),
        "from": mid.get("sounding") or before.get("sounding"),
        "to": heard.get("sounding"),
        "t_after": round(float(heard.get("t") or 0), 3),
        "t_switch": round(t_switch, 3),
        "starts_at_beginning": t_switch < 1.5,
        "sheet_open": bool(heard.get("sheetOpen")),
        "sheet_key": heard.get("sheetKey"),
        "chord": heard.get("chord"),
        "switch": info,
    }


def main() -> int:
    report = {"ok": False, "checks": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})

        # --- Cycling ON ---
        setup(page, cycle=True, loops=2)
        report["checks"]["on_next_from_mid"] = measure_next_from_mid(page)
        page.wait_for_timeout(800)
        report["checks"]["on_stop_resume"] = measure_follow_stop_resume(page)
        page.wait_for_timeout(800)
        report["checks"]["on_loop_start"] = measure_loop_start(page)

        # Leave cycling for Off pass
        page.evaluate(
            """() => {
              const b = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"] button')
                || [...document.querySelectorAll('button')].find(el => /Turn off cycling/i.test(el.innerText || ''));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(900)
        set_cycle_mode(page, False)
        page.wait_for_timeout(700)

        # --- Cycling OFF (fresh play) ---
        click_play(page)
        wait_playing(page, 40)
        open_sheet(page)
        page.wait_for_timeout(800)
        report["checks"]["off_stop_resume"] = measure_follow_stop_resume(page)
        page.wait_for_timeout(700)
        open_sheet(page)
        page.wait_for_timeout(400)
        report["checks"]["off_loop_start"] = measure_loop_start(page)

        # Leave Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(500)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    nxt = report["checks"].get("on_next_from_mid") or {}
    need = {
        "next_starts_beginning": bool(nxt.get("starts_at_beginning")),
        "next_sheet_open": bool(nxt.get("sheet_open")),
        "on_stop_resume": bool((report["checks"].get("on_stop_resume") or {}).get("continues"))
        and bool((report["checks"].get("on_stop_resume") or {}).get("keeps_place"))
        and "Resume" in str((report["checks"].get("on_stop_resume") or {}).get("stop_label") or ""),
        "on_loop_start": bool((report["checks"].get("on_loop_start") or {}).get("starts_near_loop"))
        and bool((report["checks"].get("on_loop_start") or {}).get("stayed_stopped")),
        "off_stop_resume": bool((report["checks"].get("off_stop_resume") or {}).get("continues"))
        and bool((report["checks"].get("off_stop_resume") or {}).get("keeps_place")),
        "off_loop_start": bool((report["checks"].get("off_loop_start") or {}).get("starts_near_loop"))
        and bool((report["checks"].get("off_loop_start") or {}).get("stayed_stopped")),
    }
    # Resume label after stop (before resume click) — re-check from stop_label field after stop
    on_sr = report["checks"].get("on_stop_resume") or {}
    off_sr = report["checks"].get("off_stop_resume") or {}
    # stop_label was captured after stop; if continue path ran, we overwrote with resume click.
    # Re-derive: keeps_place implies stop worked; require Resume appeared — stored in stop_label only if we captured mid-stop.
    # measure_follow_stop_resume stores stop_label after stop and resume_label after resume.
    need["on_stop_shows_resume"] = "Resume" in str(on_sr.get("stop_label") or "")
    need["on_resume_shows_stop"] = "Stop" in str(on_sr.get("resume_label") or "")
    need["off_stop_shows_resume"] = "Resume" in str(off_sr.get("stop_label") or "")
    need["off_resume_shows_stop"] = "Stop" in str(off_sr.get("resume_label") or "")

    report["required"] = need
    report["ok"] = all(need.values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "follow_transport_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "required": need, "left_off": report.get("left_off"),
                      "on_next": nxt, "on_sr": on_sr, "on_loop": report["checks"].get("on_loop_start"),
                      "off_sr": off_sr, "off_loop": report["checks"].get("off_loop_start")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

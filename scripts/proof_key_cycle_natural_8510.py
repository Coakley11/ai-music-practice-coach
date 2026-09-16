"""Natural end→playing gaps on 8510 — no seek, no synthetic ended events.

Uses short real passes (Intro / Selected sections, loops=1) and waits for
the audio element to reach natural `ended`. Reports end→playing and chart
update delay separately.
"""
from __future__ import annotations

import json
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
from proof_key_cycle_seamless_8510 import read_bridges, read_gaps, wait_kc_audio, wait_next_preloaded, wait_prefetch
from proof_key_cycle_ux_8510 import (
    click_play,
    cycle_ui,
    open_advanced,
    set_cycle_mode,
    wait_sounding,
)

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
DATA = ROOT / "_runtime_key_cycle_8510"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def configure_short_pass(page) -> dict:
    """Selected sections + Intro (or shortest available) + loops=1."""
    info: dict = {"scope": False, "section": "", "loops": False, "bpm_boost": False}
    # Playback scope → Selected sections via radio option text
    info["scope"] = bool(
        page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('label, [data-testid="stRadioOption"]')];
              const sel = labels.find((l) => /^Selected sections$/i.test((l.innerText || '').trim())
                || /Selected sections/i.test(l.innerText || ''));
              if (!sel) return false;
              sel.click();
              return true;
            }"""
        )
    )
    page.wait_for_timeout(500)
    # Clear multiselect then pick Intro if present
    page.evaluate(
        """() => {
          const clear = document.querySelector('[data-baseweb="tag"] [aria-label="Clear all"], [aria-label="Clear"]');
          if (clear) clear.click();
        }"""
    )
    page.wait_for_timeout(300)
    for name in ("Intro", "Intro 1", "Verse 1", "Verse"):
        clicked = page.evaluate(
            """(name) => {
              // Open multiselect
              const input = document.querySelector('[class*="stMultiSelect"] input, [data-baseweb="select"] input');
              if (input) { input.click(); input.focus(); }
              const nodes = [...document.querySelectorAll('li, [role="option"], label')];
              const el = nodes.find((n) => (n.innerText || '').trim() === name);
              if (el) { el.click(); return true; }
              return false;
            }""",
            name,
        )
        if clicked:
            info["section"] = name
            break
    page.wait_for_timeout(400)
    # Loops → 1
    info["loops"] = bool(
        page.evaluate(
            """() => {
              const sliders = [...document.querySelectorAll('input[type="range"]')];
              let target = null;
              for (const s of sliders) {
                const wrap = s.closest('[data-testid="stSlider"]') || s.closest('div');
                const txt = (wrap && wrap.innerText) || '';
                if (/loop|repeat/i.test(txt) || Number(s.max) === 10) { target = s; break; }
              }
              if (!target) return false;
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(target, '1');
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return Number(target.value) === 1;
            }"""
        )
    )
    page.wait_for_timeout(400)
    info["bpm_boost"] = bool(
        page.evaluate(
            """() => {
              const sliders = [...document.querySelectorAll('input[type="range"]')];
              let target = null;
              for (const s of sliders) {
                const wrap = s.closest('[data-testid="stSlider"]') || s.closest('div');
                const txt = ((wrap && wrap.innerText) || '').toLowerCase();
                if (txt.includes('bpm') || (Number(s.max) >= 180 && Number(s.min) <= 60 && Number(s.max) !== 10)) {
                  target = s; break;
                }
              }
              if (!target) return false;
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              const v = String(Math.min(Number(target.max) || 200, 160));
              setter.call(target, v);
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }"""
        )
    )
    page.wait_for_timeout(800)
    return info


def wait_natural_ended_and_playing(page, before: str, max_wait_s: float = 240) -> dict:
    """Wait for natural audio end → next key playing. No seek / no forced ended."""
    gaps_before = len(read_gaps())
    bridges_before = len(read_bridges())
    t0 = time.time()
    page.evaluate(
        """() => {
          window.__kcLastGapMs = null;
          window.__kcLastChartMs = null;
          window.__kcProofNatural = { endedAt: null, playingAt: null, chartKey: null };
          const hook = () => {
            const st = window.__kcDual;
            if (!st) return;
            // Observe chart key after ended
            const obs = () => {
              const el = document.getElementById('kc-chart-live');
              const key = (el && (el.getAttribute('data-kc-playing-key') || el.innerText)) || '';
              if (window.__kcLastGapMs != null && window.__kcProofNatural.playingAt == null) {
                window.__kcProofNatural.playingAt = performance.now();
                window.__kcProofNatural.chartKey = key;
              }
            };
            setInterval(obs, 30);
          };
          hook();
          // Mark when active buffer ends naturally
          ['kc-buf-0','kc-buf-1'].forEach((id) => {
            const a = document.getElementById(id);
            if (!a || a.__kcProofEndedHook) return;
            a.__kcProofEndedHook = true;
            const prev = a.onended;
            a.addEventListener('ended', () => {
              window.__kcProofNatural.endedAt = performance.now();
              window.__kcProofNatural.naturalEnded = true;
            });
          });
        }"""
    )
    # Poll until sounding changes or playing ack lands
    deadline = time.time() + max_wait_s
    post = before
    while time.time() < deadline:
        post = str(cycle_ui(page).get("sounding") or "")
        gaps = read_gaps()
        bridges = read_bridges()
        browser = page.evaluate(
            """() => ({
              gap: window.__kcLastGapMs,
              chart: window.__kcLastChartMs,
              natural: !!(window.__kcProofNatural && window.__kcProofNatural.naturalEnded),
              chartKey: (document.getElementById('kc-chart-live') || {}).getAttribute
                ? document.getElementById('kc-chart-live').getAttribute('data-kc-playing-key')
                : null,
              paused: (() => {
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                return a ? !!a.paused : true;
              })(),
              t: (() => {
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                return a ? Number(a.currentTime)||0 : 0;
              })(),
              d: (() => {
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                return a ? Number(a.duration)||0 : 0;
              })(),
            })"""
        )
        if (post and before and post != before) or len(bridges) > bridges_before:
            # Require natural ended flag OR a playing ack with natural:true
            new_bridges = bridges[bridges_before:]
            playing_acks = [
                b
                for b in new_bridges
                if b.get("natural") or str(b.get("ack_kind") or "") == "playing"
            ]
            if playing_acks or browser.get("natural"):
                break
            if post and before and post != before and browser.get("gap") is not None:
                break
        page.wait_for_timeout(500)

    gaps = read_gaps()[gaps_before:]
    bridges = read_bridges()[bridges_before:]
    playing = [g for g in gaps if g.get("kind") == "playing"]
    chart_gaps = [g for g in gaps if g.get("kind") == "chart"]
    bridge = bridges[-1] if bridges else {}
    browser_gap = page.evaluate("() => window.__kcLastGapMs")
    browser_chart = page.evaluate("() => window.__kcLastChartMs")
    chart_key = page.evaluate(
        """() => {
          const el = document.getElementById('kc-chart-live');
          return el ? (el.getAttribute('data-kc-playing-key') || '') : '';
        }"""
    )
    streamlit_chart_delay_s = None
    # Approximate Streamlit playbar catch-up after browser chart swap
    if bridge.get("t") and post and before and post != before:
        # wall from bridge write isn't exact; use wait_sounding remainder
        pass
    return {
        "before": before,
        "after": post,
        "wall_s": round(time.time() - t0, 3),
        "method": "natural_ended",
        "seek_or_forced": False,
        "gap_playing_s": playing[-1]["gap_s"] if playing else (
            float(browser_gap) / 1000.0 if browser_gap is not None else None
        ),
        "browser_gap_ms": browser_gap,
        "chart_update_ms": browser_chart
        if browser_chart is not None
        else (bridge.get("chart_ms") if bridge else None),
        "chart_gap_s": chart_gaps[-1]["gap_s"] if chart_gaps else None,
        "chart_key_at_handoff": chart_key,
        "seamless": bool(bridge.get("seamless")),
        "ack_kind": bridge.get("ack_kind"),
        "natural_ack": bool(bridge.get("natural")),
        "advanced": bool(before and post and before != post),
        "bridge": {
            k: bridge.get(k)
            for k in ("gap_ms", "chart_ms", "playing_key", "seamless", "advanced")
        },
    }


def main() -> int:
    for name in (
        "_key_cycle_pass_gaps.jsonl",
        "_kc_prefetch.jsonl",
        "_key_cycle_bridge_clicks.jsonl",
        "_kc_handoff_acks.jsonl",
    ):
        p = DATA / name
        if p.exists():
            p.unlink()

    report: dict = {
        "ok": False,
        "timing_method": "natural_audio_ended",
        "seek_or_forced_ended": False,
        "short_pass_env": {
            "KC_SHORT_PASS_BARS": __import__("os").environ.get("KC_SHORT_PASS_BARS"),
            "KC_SHORT_PASS_LOOPS": __import__("os").environ.get("KC_SHORT_PASS_LOOPS"),
        },
        "transitions": [],
        "notes": (
            "Prior seamless_gap_report.json included seek/forced ended timings; "
            "this report uses only natural ended events on short real passes "
            "(KC_SHORT_PASS_BARS/LOOPS when set for local 8510 proofs)."
        ),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(800)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2500)

        short = configure_short_pass(page)
        report["short_pass_config"] = short
        log(f"short_pass={short}")

        set_cycle_mode(page, True)
        for _ in range(20):
            ui = cycle_ui(page)
            if ui.get("sounding") and ui.get("playbar"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(500)
        log(f"on sounding={cycle_ui(page).get('sounding')}")

        click_play(page)
        audio = wait_kc_audio(page, 200)
        log(f"audio={audio}")
        report["first_pass_duration_s"] = audio.get("duration")
        pref = wait_prefetch(page, 120)
        log(f"prefetch_ok={bool(pref)}")
        preloaded = wait_next_preloaded(page, 90)
        log(f"next_preloaded={preloaded}")
        report["next_preloaded"] = preloaded

        sounding = str(cycle_ui(page).get("sounding") or "")
        for i in range(3):
            log(f"wait natural transition {i+1} from {sounding} (dur~{audio.get('duration')})")
            # Ensure still playing so natural end can fire
            page.evaluate(
                """() => {
                  const a0 = document.getElementById('kc-buf-0');
                  const a1 = document.getElementById('kc-buf-1');
                  const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                  if (a && a.paused) { const p = a.play(); if (p && p.catch) p.catch(()=>{}); }
                }"""
            )
            tr = wait_natural_ended_and_playing(page, sounding, max_wait_s=300)
            report["transitions"].append(tr)
            log(f"transition={tr}")
            if not tr.get("advanced"):
                break
            sounding = str(tr.get("after") or cycle_ui(page).get("sounding") or "")
            # After handoff, wait for next buffer again before next natural end
            wait_next_preloaded(page, 90)
            audio = page.evaluate(
                """() => {
                  const a0 = document.getElementById('kc-buf-0');
                  const a1 = document.getElementById('kc-buf-1');
                  const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                  return {duration: a ? Number(a.duration)||0 : 0, paused: a ? !!a.paused : true};
                }"""
            )

        natural_ok = [
            t
            for t in report["transitions"]
            if t.get("advanced")
            and not t.get("seek_or_forced")
            and t.get("method") == "natural_ended"
            and (t.get("natural_ack") or t.get("ack_kind") == "playing" or t.get("browser_gap_ms") is not None)
        ]
        report["ok"] = len(natural_ok) >= 3
        report["natural_playing_gaps_ms"] = [
            t.get("browser_gap_ms") or (t.get("gap_playing_s") or 0) * 1000 for t in natural_ok
        ]
        report["chart_update_ms"] = [t.get("chart_update_ms") for t in natural_ok]
        gaps = [g for g in report["natural_playing_gaps_ms"] if g is not None]
        report["natural_end_to_playing_median_ms"] = (
            sorted(gaps)[len(gaps) // 2] if gaps else None
        )

        # Leave cycling Off for review
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        report["left_off"] = not bool(cycle_ui(page).get("on"))
        browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "natural_gap_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {out_path} ok={report['ok']}")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

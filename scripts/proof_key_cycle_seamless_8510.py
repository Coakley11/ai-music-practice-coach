"""Measure end→playing gaps across consecutive Key-cycle transitions on 8510."""
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
from proof_key_cycle_ux_8510 import (
    click_play,
    cycle_ui,
    find_audio,
    open_advanced,
    set_cycle_mode,
    wait_audio,
    wait_sounding,
)

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
DATA = ROOT / "_runtime_key_cycle_8510"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


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


def read_bridges() -> list:
    path = DATA / "_key_cycle_bridge_clicks.jsonl"
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


def wait_prefetch(page, seconds: float = 120, min_ready: int = 1) -> list:
    deadline = time.time() + seconds
    path = DATA / "_kc_prefetch.jsonl"
    while time.time() < deadline:
        if path.exists():
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
            ready_keys = {
                str(r.get("target") or r.get("key") or r.get("sounding_key") or "")
                for r in rows
                if r.get("ok") and (r.get("cached") or r.get("published"))
            }
            ready_keys.discard("")
            if len(ready_keys) >= int(min_ready) or (
                min_ready <= 1
                and any(r.get("ok") and (r.get("cached") or r.get("published")) for r in rows)
            ):
                return rows
        page.wait_for_timeout(1500)
    return []


def wait_kc_audio(page, seconds: float = 180) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        info = page.evaluate(
            """() => {
              const a0 = document.getElementById('kc-buf-0');
              const a1 = document.getElementById('kc-buf-1');
              const a = [a0, a1].find((el) => el && el.style && el.style.display !== 'none' && el.src)
                || a0 || a1;
              if (!a) return {ok: false, duration: 0, src: '', ready: 0, paused: true};
              // Nudge play if URL is present but stalled.
              if (a.src && a.paused && a.readyState >= 1) {
                try { const p = a.play(); if (p && p.catch) p.catch(() => {}); } catch (e) {}
              }
              const dur = Number(a.duration) || 0;
              const ready = Number(a.readyState) || 0;
              return {
                ok: dur > 0.2 || ready >= 2,
                duration: dur,
                src: a.getAttribute('data-kc-url') || a.src || '',
                ready: ready,
                paused: !!a.paused,
              };
            }"""
        )
        if info.get("ok"):
            if info.get("paused"):
                page.evaluate(
                    """() => {
                      const a0 = document.getElementById('kc-buf-0');
                      const a = a0 && a0.style.display !== 'none' ? a0 : document.getElementById('kc-buf-1');
                      if (!a) return;
                      const p = a.play();
                      if (p && p.catch) p.catch(() => {});
                    }"""
                )
            return info
        page.wait_for_timeout(800)
    return {"ok": False, "duration": 0}


def seek_near_end(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const a0 = document.getElementById('kc-buf-0');
              const a1 = document.getElementById('kc-buf-1');
              const active = [a0, a1].find((a) => a && a.style.display !== 'none' && a.src);
              const a = active || a0 || a1;
              if (!a) return false;
              const d = Number(a.duration) || 0;
              if (!(d > 0.5)) return false;
              // Reset pass-consumed so a forced ended can signal Python again.
              try { window.__backingKeyCyclePassConsumed = null; } catch (e) {}
              try { window.__kcLastGapMs = null; } catch (e) {}
              try { a.pause(); } catch (e) {}
              const target = Math.max(0, d - 0.35);
              const fire = () => {
                try { a.dispatchEvent(new Event('ended')); } catch (e) {}
              };
              const onSeeked = () => {
                const p = a.play();
                if (p && p.catch) p.catch(() => {});
                // Natural ended may take ~350ms; also force so large-WAV seek stalls
                // cannot block the handoff measurement.
                window.setTimeout(fire, 50);
              };
              a.addEventListener('seeked', onSeeked, { once: true });
              try { a.currentTime = target; } catch (e) { fire(); return true; }
              // If seek never completes (common for huge WAVs without Range), force.
              window.setTimeout(() => {
                if (!(window.__kcDual && (window.__kcDual.ending || window.__kcDual.swapping || window.__kcDual.endedAt))) {
                  fire();
                }
              }, 600);
              return true;
            }"""
        )
    )


def wait_next_preloaded(page, seconds: float = 60) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        ok = page.evaluate(
            """() => {
              const a0 = document.getElementById('kc-buf-0');
              const a1 = document.getElementById('kc-buf-1');
              const st = window.__kcDual;
              if (!a0 || !a1 || !st) return false;
              const idle = st.active === 0 ? a1 : a0;
              const urlOk = !!(idle && (idle.getAttribute('data-kc-url') || idle.src) && idle.readyState >= 2);
              // Sounding may arrive slightly later via applyCmd / URL map.
              if (urlOk && st.nextSounding) {
                idle.setAttribute('data-kc-sounding', String(st.nextSounding));
              }
              return urlOk;
            }"""
        )
        if ok:
            return True
        page.wait_for_timeout(500)
    return False


def measure_one_transition(page, before: str) -> dict:
    gaps_before = len(read_gaps())
    bridges_before = len(read_bridges())
    t0 = time.time()
    browser_gap = page.evaluate(
        """() => {
          const prev = window.__kcLastGapMs;
          window.__kcLastGapMs = null;
          return prev;
        }"""
    )
    seek_near_end(page)
    post = wait_sounding(page, before, 45)
    # Wait for playing gap log / bridge
    deadline = time.time() + 20
    while time.time() < deadline:
        gaps = read_gaps()
        bridges = read_bridges()
        if len(gaps) > gaps_before or len(bridges) > bridges_before:
            break
        page.wait_for_timeout(250)
    gaps = read_gaps()[gaps_before:]
    bridges = read_bridges()[bridges_before:]
    playing = [g for g in gaps if g.get("kind") == "playing"]
    ready = [g for g in gaps if g.get("kind") == "ready"]
    gap_playing = playing[-1]["gap_s"] if playing else None
    gap_ready = ready[-1]["gap_s"] if ready else None
    bridge = bridges[-1] if bridges else {}
    browser_gap_after = page.evaluate("() => window.__kcLastGapMs")
    # Only report a fresh browser gap (ignore stale value from prior transition).
    fresh_browser = None
    if browser_gap_after is not None and browser_gap_after != browser_gap:
        fresh_browser = browser_gap_after
    elif bridge.get("gap_ms") is not None:
        fresh_browser = float(bridge["gap_ms"])
    return {
        "before": before,
        "after": post,
        "wall_s": round(time.time() - t0, 3),
        "gap_playing_s": gap_playing,
        "gap_ready_s": gap_ready,
        "browser_gap_ms": fresh_browser,
        "seamless": bool(bridge.get("seamless")),
        "bridge_gap_ms": bridge.get("gap_ms"),
        "advanced": bool(before and post and before != post),
    }


def main() -> int:
    for name in (
        "_key_cycle_pass_gaps.jsonl",
        "_kc_prefetch.jsonl",
        "_key_cycle_bridge_clicks.jsonl",
    ):
        p = DATA / name
        if p.exists():
            p.unlink()

    report: dict = {"ok": False, "transitions": [], "baseline_ready_gap_s": 5.03}

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
        pref = wait_prefetch(page, 90)
        log(f"prefetch={pref[:2]}")
        # Confirm persistent player present
        has_persist = page.evaluate("() => !!document.getElementById('kc-persistent-root')")
        report["persistent_player"] = bool(has_persist)
        log(f"persistent_player={has_persist}")

        sounding = str(cycle_ui(page).get("sounding") or "")
        for i in range(3):
            preloaded = wait_next_preloaded(page, 90)
            log(f"next_preloaded={preloaded}")
            row = measure_one_transition(page, sounding)
            report["transitions"].append(row)
            log(f"t{i+1}={row}")
            sounding = str(row.get("after") or sounding)
            page.wait_for_timeout(5000)

        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        # Confirm parent player stopped
        report["after_off"] = page.evaluate(
            """() => {
              const a0 = document.getElementById('kc-buf-0');
              const a1 = document.getElementById('kc-buf-1');
              return {
                playbar: !!document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]'),
                a0_paused: a0 ? a0.paused : true,
                a0_src: a0 ? (a0.getAttribute('src') || '') : '',
              };
            }"""
        )
        browser.close()

    playing_gaps = [
        float(t["gap_playing_s"])
        for t in report["transitions"]
        if t.get("gap_playing_s") is not None
    ]
    browser_gaps = [
        float(t["browser_gap_ms"]) / 1000.0
        for t in report["transitions"]
        if t.get("browser_gap_ms") is not None
    ]
    report["playing_gaps_s"] = playing_gaps
    report["browser_gaps_s"] = browser_gaps
    report["median_playing_s"] = (
        sorted(playing_gaps)[len(playing_gaps) // 2] if playing_gaps else None
    )
    report["median_browser_s"] = (
        sorted(browser_gaps)[len(browser_gaps) // 2] if browser_gaps else None
    )
    advanced_ok = all(t.get("advanced") for t in report["transitions"])
    seamless_n = sum(1 for t in report["transitions"] if t.get("seamless"))
    report["seamless_count"] = seamless_n
    # Success: at least 2 advances and browser end→playing gap under 0.5s median
    target = report.get("median_browser_s") or report.get("median_playing_s")
    report["ok"] = bool(
        advanced_ok
        and len(report["transitions"]) >= 3
        and target is not None
        and float(target) < 0.5
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "seamless_gap_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    log(f"ok={report['ok']} median_browser={report.get('median_browser_s')} median_playing={report.get('median_playing_s')}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify full selected section + real lead sheet on 8510 (no SHORT_PASS overrides)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import (
    click_play,
    cycle_ui,
    open_advanced,
    set_cycle_mode,
)
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle" / "full_section_leadsheet_report.json"
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "_runtime_key_cycle_8510"))
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)

for _k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS"):
    os.environ.pop(_k, None)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def configure_verse_pass(page, loops: int = 1) -> dict:
    """Selected sections → Verse (prefer longest verse name) + loops."""
    info: dict = {"scope": False, "section": "", "loops": False, "loops_value": loops}
    info["scope"] = bool(
        page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('label, [data-testid="stRadioOption"]')];
              const sel = labels.find((l) => /Selected sections/i.test(l.innerText || ''));
              if (!sel) return false;
              sel.click();
              return true;
            }"""
        )
    )
    page.wait_for_timeout(500)
    page.evaluate(
        """() => {
          const clear = document.querySelector('[data-baseweb="tag"] [aria-label="Clear all"], [aria-label="Clear"]');
          if (clear) clear.click();
        }"""
    )
    page.wait_for_timeout(300)
    for name in ("Verse 1", "Verse", "Verse 2"):
        clicked = page.evaluate(
            """(name) => {
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
    info["loops"] = bool(
        page.evaluate(
            """(n) => {
              const sliders = [...document.querySelectorAll('input[type="range"]')];
              let target = null;
              for (const s of sliders) {
                const wrap = s.closest('[data-testid="stSlider"]') || s.closest('div');
                const txt = (wrap && wrap.innerText) || '';
                if (/loop|repeat/i.test(txt) || Number(s.max) === 10) { target = s; break; }
              }
              if (!target) return false;
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(target, String(n));
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return Number(target.value) === Number(n);
            }""",
            int(loops),
        )
    )
    page.wait_for_timeout(400)
    # Modest tempo via normal BPM control — full arrangement, faster verify.
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
              const v = String(Math.min(Number(target.max) || 200, 140));
              setter.call(target, v);
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }"""
        )
    )
    page.wait_for_timeout(600)
    return info


def open_lead_sheet(page) -> bool:
    if page.locator(".backing-chart-sheet, .lead-sheet").count():
        return True
    try:
        btn = page.get_by_role("button", name="Open lead sheet")
        if btn.count():
            btn.first.click(timeout=4000)
            page.wait_for_timeout(1000)
            return page.locator(".backing-chart-sheet, .lead-sheet").count() > 0
    except Exception:
        pass
    return False


def snap_chart(page) -> dict:
    return page.evaluate(
        """() => {
          const sheet = document.querySelector('.backing-chart-sheet, .lead-sheet');
          const cells = sheet ? [...sheet.querySelectorAll('.live-chart-cell, .chord-cell')] : [];
          const rawGrid = !!(
            document.querySelector('.kc-chart-full, #kc-full-chart-host, #kc-chart-live, .kc-chord-cell')
          );
          const pills = sheet
            ? [...sheet.querySelectorAll('.meta-pill')].map((e) => (e.textContent || '').trim())
            : [];
          const formBars = pills.find((t) => /\\bbars\\b/i.test(t)) || '';
          const keyPill = pills.find((t) => /^Key:/i.test(t)) || '';
          // Detect raw playback tokens like A#:3.5|D#:0.5p in visible chart cells only.
          const rawTok = cells.some((c) => /:\\d/.test(c.textContent || '') && (c.textContent || '').includes('|'));
          return {
            has_lead_sheet: !!sheet,
            cell_count: cells.length,
            has_raw_grid: rawGrid,
            has_raw_playback_token_in_cells: rawTok,
            form_bars_text: formBars,
            key_pill: keyPill,
            sample_cells: cells.slice(0, 8).map((c) => (c.textContent || '').replace(/\\s+/g, ' ').trim()),
          };
        }"""
    )


def audio_duration(page) -> float:
    return float(
        page.evaluate(
            """() => {
              const st = window.__kcDual;
              const a0 = document.getElementById('kc-buf-0');
              const a1 = document.getElementById('kc-buf-1');
              const act = st ? (st.active === 1 ? a1 : a0) : null;
              const a = act || a0 || a1 || document.querySelector('audio');
              const d = a ? Number(a.duration || 0) : 0;
              return Number.isFinite(d) && d > 0 ? d : 0;
            }"""
        )
        or 0
    )


def wait_key_change(page, from_key: str, timeout_s: float) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ui = cycle_ui(page)
        sk = str(ui.get("sounding") or "")
        if from_key and sk and sk != from_key:
            return {"ok": True, "from": from_key, "to": sk, "waited_s": time.time() - t0}
        page.wait_for_timeout(700)
    ui = cycle_ui(page)
    return {
        "ok": False,
        "from": from_key,
        "to": ui.get("sounding"),
        "waited_s": time.time() - t0,
    }


def main() -> int:
    assert not os.environ.get("KC_SHORT_PASS_BARS")
    assert not os.environ.get("KC_SHORT_PASS_LOOPS")
    report: dict = {
        "ok": False,
        "short_pass_env_cleared": True,
        "checks": {},
        "left_off": False,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.set_default_timeout(20000)
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
        # Nav can bounce picker←→backing on restore; retry until Play control exists.
        for _ in range(8):
            body = page.inner_text("body") or ""
            if "Play Backing Track" in body or "Selected sections" in body:
                break
            goto_studio(page, "Backing")
            page.wait_for_timeout(2000)
        body = page.inner_text("body") or ""
        report["checks"]["on_backing"] = "Play Backing Track" in body or "Selected sections" in body
        log(f"on_backing={report['checks']['on_backing']}")

        cfg1 = configure_verse_pass(page, loops=1)
        report["checks"]["configure_1"] = cfg1
        log(f"configure loops=1 {cfg1}")

        # --- OFF baseline ---
        set_cycle_mode(page, False)
        click_play(page)
        audio_off = wait_kc_audio(page, 180)
        if not audio_off.get("ok"):
            click_play(page)
            audio_off = wait_kc_audio(page, 180)
        dur_off = float(audio_off.get("duration") or audio_duration(page) or 0)
        open_lead_sheet(page)
        chart_off = snap_chart(page)
        report["checks"]["off"] = {
            "duration_s": dur_off,
            "chart": chart_off,
            "bar_count": chart_off.get("cell_count"),
            "audio": audio_off,
        }
        log(f"OFF dur={dur_off:.2f} bars={chart_off.get('cell_count')} raw={chart_off.get('has_raw_grid')}")

        # --- ON one loop ---
        set_cycle_mode(page, True)
        for _ in range(16):
            if cycle_ui(page).get("playbar"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(600)
        click_play(page)
        audio_on = wait_kc_audio(page, 180)
        if not audio_on.get("ok"):
            click_play(page)
            audio_on = wait_kc_audio(page, 180)
        dur_on = float(audio_on.get("duration") or audio_duration(page) or 0)
        open_lead_sheet(page)
        chart_on = snap_chart(page)
        start = str(cycle_ui(page).get("sounding") or "")
        report["checks"]["on_1_loop"] = {
            "duration_s": dur_on,
            "chart": chart_on,
            "bar_count": chart_on.get("cell_count"),
            "sounding": start,
            "expected_duration_s": dur_off,
            "audio": audio_on,
        }
        parity = dur_off > 8 and dur_on > 8 and abs(dur_off - dur_on) <= max(2.0, 0.1 * dur_off)
        report["checks"]["duration_parity"] = {"ok": parity, "off": dur_off, "on": dur_on}
        report["checks"]["bars_gt_4"] = int(chart_on.get("cell_count") or 0) > 4
        report["checks"]["no_raw_grid"] = (
            bool(chart_on.get("has_lead_sheet"))
            and not chart_on.get("has_raw_grid")
            and not chart_on.get("has_raw_playback_token_in_cells")
        )
        log(f"ON1 dur={dur_on:.2f} key={start} bars={chart_on.get('cell_count')} parity={parity}")

        change1 = wait_key_change(page, start, max(180.0, dur_on * 1.6 + 30))
        chart_x = snap_chart(page)
        report["checks"]["one_key_change"] = change1
        report["checks"]["chart_after_change"] = chart_x
        report["checks"]["no_raw_grid_after_change"] = (
            bool(chart_x.get("has_lead_sheet")) and not chart_x.get("has_raw_grid")
        )
        log(f"change1={change1} raw={chart_x.get('has_raw_grid')}")

        # --- Two loops ---
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        cfg2 = configure_verse_pass(page, loops=2)
        report["checks"]["configure_2"] = cfg2
        set_cycle_mode(page, True)
        click_play(page)
        audio2 = wait_kc_audio(page, 240)
        if not audio2.get("ok"):
            click_play(page)
            audio2 = wait_kc_audio(page, 180)
        dur2 = float(audio2.get("duration") or audio_duration(page) or 0)
        start2 = str(cycle_ui(page).get("sounding") or "")
        loops_dur_ok = dur2 > 8 and (dur_on < 8 or dur2 >= dur_on * 1.6)
        report["checks"]["two_loops"] = {
            "duration_s": dur2,
            "expected_min_s": (dur_on * 1.7) if dur_on > 8 else None,
            "duration_ok": loops_dur_ok,
            "start_key": start2,
            "loops": 2,
            "bar_count_one_pass": chart_on.get("cell_count"),
            "audio": audio2,
        }
        change2 = wait_key_change(page, start2, max(260.0, dur2 * 1.5 + 40))
        early = bool(change2.get("ok") and float(change2.get("waited_s") or 0) < dur2 * 0.72)
        report["checks"]["two_loops_key_change"] = change2
        report["checks"]["two_loops_not_early"] = {
            "ok": bool(change2.get("ok")) and not early,
            "waited_s": change2.get("waited_s"),
            "early": early,
            "threshold_s": dur2 * 0.72,
        }
        log(f"ON2 dur={dur2:.2f} change={change2} early={early}")

        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    report["selected_section"] = cfg1.get("section")
    report["bar_count"] = chart_on.get("cell_count")
    report["loop_count_1"] = 1
    report["loop_count_2"] = 2
    report["expected_duration_1_s"] = dur_off
    report["actual_duration_1_s"] = dur_on
    report["actual_duration_2_s"] = dur2

    report["ok"] = bool(
        report["checks"].get("no_raw_grid")
        and report["checks"].get("bars_gt_4")
        and report["checks"].get("duration_parity", {}).get("ok")
        and report["checks"].get("one_key_change", {}).get("ok")
        and report["checks"].get("two_loops", {}).get("duration_ok")
        and report["checks"].get("two_loops_not_early", {}).get("ok")
        and report["checks"].get("no_raw_grid_after_change")
        and report.get("left_off")
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {OUT} ok={report['ok']}")
    print(json.dumps({k: report[k] for k in report if k != "checks"}, indent=2))
    print(json.dumps(report["checks"], indent=2, default=str)[:5000])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

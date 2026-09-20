"""Focused Prev/Next + Turn-off on fresh 8510 session (after restart)."""
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
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_kc_settings_focused_8510 import (
    current_key,
    log,
    set_loops,
    set_practice_key,
    set_scope_selected_section,
    snap,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"


def wait_idle(page, ms: int = 16000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(400)


def sheet_detail(page) -> dict:
    return page.evaluate(
        """() => {
          let live = false, highlight = '', first = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              if (!doc.querySelector('.live-follow-shell')) continue;
              live = true;
              const cur = doc.querySelector('.live-chart-cell.current-chord, .chord-cell.current-chord');
              if (cur) highlight = (cur.innerText || '').trim().slice(0, 32);
              const cell = doc.querySelector('.live-chart-cell, .chord-cell');
              if (cell) first = (cell.innerText || '').trim().slice(0, 32);
              break;
            } catch (e) {}
          }
          const close = /Close lead sheet/i.test(document.body.innerText || '');
          return {live, close, highlight, firstChord: first, open: live || close};
        }"""
    )


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime || 0) : 0,
            sounding: String(
              (act && act.getAttribute('data-kc-sounding')) || window.__kcLastSounding || ''
            ).trim(),
            enabled: dual.enabled !== false,
          };
        }"""
    )


def wait_step(page, want: str, *, timeout_s: float = 55.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        ui = cycle_ui(page)
        a = audio_snap(page)
        sh = sheet_detail(page)
        s = snap(page)
        chip = str(ui.get("highlighted") or "")
        label = str(ui.get("sounding") or "")
        audible = str(a.get("sounding") or "")
        key = current_key(s) or audible or label
        near0 = float(a.get("t") or 99) < 8.0
        playing = (not a.get("paused")) and float(a.get("t") or 0) >= 0
        key_agree = (
            key == want
            and (audible == want or not audible)
            and (label == want or label == audible or not label)
            and (chip == want or not chip)
            and bool(sh.get("open"))
        )
        agree = key_agree and near0 and playing
        last = {
            "want": want,
            "key": key,
            "chip": chip,
            "label": label,
            "audible": audible,
            "t": a.get("t"),
            "paused": a.get("paused"),
            "sheet": sh,
            "key_agree": key_agree,
            "ok": agree,
        }
        if key_agree and near0 and playing:
            return last
        if key_agree and float(a.get("t") or 0) < 8.0 and playing:
            page.wait_for_timeout(200)
            continue
        page.wait_for_timeout(350)
    if last.get("key_agree") and last.get("sheet", {}).get("open"):
        last["ok"] = float(last.get("t") or 99) < 14.0
    return last


def ensure_descending_whole(page) -> dict:
    set_descending_whole_tone(page)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    return page.evaluate(
        """() => {
          const step = document.querySelector('[class*="st-key-backing_key_cycle_step_ui"]');
          const dir = document.querySelector('[class*="st-key-backing_key_cycle_direction_ui"]');
          const stepOn = step && [...step.querySelectorAll('[data-testid="stRadioOption"]')]
            .find(o => o.getAttribute('aria-checked') === 'true' || o.querySelector('input:checked'));
          const dirOn = dir && [...dir.querySelectorAll('[data-testid="stRadioOption"]')]
            .find(o => o.getAttribute('aria-checked') === 'true' || o.querySelector('input:checked'));
          const chips = [...document.querySelectorAll('.ui-key-cycle-playbar span[data-key], .ui-key-cycle-chip')]
            .map(el => (el.getAttribute('data-key') || el.innerText || '').trim())
            .filter(t => /^[A-G][#b]?m?$/.test(t));
          return {
            step: ((stepOn && stepOn.innerText) || '').trim(),
            direction: ((dirOn && dirOn.innerText) || '').trim(),
            chips: chips.slice(0, 8),
          };
        }"""
    )


def setup(page) -> dict:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
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
    set_practice_key(page, "Gm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_cycle_mode(page, True)
    wait_idle(page)
    cfg = ensure_descending_whole(page)
    open_sheet(page)
    click_play(page)
    wait_kc_audio(page, 90)
    return cfg


def turn_off(page) -> dict:
    before = audio_snap(page)
    ok_click = click_playbar(page, "off")
    playbar_gone_at = None
    audio_ok_at = None
    last_ui = {}
    last_a = {}
    deadline = time.time() + 35
    while time.time() < deadline:
        wait_idle(page, 8000)
        last_ui = cycle_ui(page)
        last_a = audio_snap(page)
        if playbar_gone_at is None and not last_ui.get("playbar"):
            playbar_gone_at = time.time()
        if audio_ok_at is None and (
            bool(last_a.get("paused"))
            or float(last_a.get("t") or 0) < 0.2
            or last_a.get("enabled") is False
        ):
            audio_ok_at = time.time()
        if playbar_gone_at is not None and audio_ok_at is not None:
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(2500)
    late_ui = cycle_ui(page)
    late_a = audio_snap(page)
    return {
        "clicked": ok_click,
        "before_t": before.get("t"),
        "playbar_gone": playbar_gone_at is not None and not bool(late_ui.get("playbar")),
        "audio": last_a,
        "late_playbar": bool(late_ui.get("playbar")),
        "late_audio": late_a,
        "ok": playbar_gone_at is not None
        and not bool(late_ui.get("playbar"))
        and (
            bool(late_a.get("paused"))
            or float(late_a.get("t") or 0) < 0.2
            or late_a.get("enabled") is False
        )
        and not (
            (not late_a.get("paused"))
            and float(late_a.get("t") or 0) > 0.5
            and late_a.get("enabled") is not False
        ),
    }


def main() -> int:
    report: dict = {"ok": False, "browser": {}}
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            log("setup Gm descending")
            cfg = setup(page)
            report["browser"]["cycle_cfg"] = cfg
            gm0 = wait_step(page, "Gm", timeout_s=40)
            report["browser"]["at_gm"] = gm0
            # Do not re-toggle Advanced settings mid-play — that burns the pass
            # clock and races natural handoff before Next/Prev.

            log("Next Gm → Fm")
            click_playbar(page, "next")
            wait_idle(page)
            fm = wait_step(page, "Fm")
            report["browser"]["gm_to_fm"] = fm

            log("Prev Fm → Gm")
            click_playbar(page, "prev")
            wait_idle(page)
            gm1 = wait_step(page, "Gm")
            report["browser"]["fm_to_gm"] = gm1

            log("Prev Gm → Am")
            click_playbar(page, "prev")
            wait_idle(page)
            am = wait_step(page, "Am")
            report["browser"]["gm_to_am"] = am

            report["browser"]["prev_next_ok"] = all(
                bool(x.get("ok")) for x in (fm, gm1, am)
            )

            log("Turn off while playing")
            # Ensure still On and playing
            if not cycle_ui(page).get("playbar"):
                set_cycle_mode(page, True)
                wait_idle(page)
                click_play(page)
                wait_kc_audio(page, 60)
            click_playbar(page, "next")
            page.wait_for_timeout(700)
            off = turn_off(page)
            report["browser"]["turn_off"] = off

            report["ok"] = bool(
                report["browser"]["prev_next_ok"] and off.get("ok")
            )
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                if cycle_ui(page).get("playbar"):
                    click_playbar(page, "off")
                    wait_idle(page)
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()

    path = OUT / "prev_next_off_focus_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:4500])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

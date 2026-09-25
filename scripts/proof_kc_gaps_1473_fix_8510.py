"""Focused gap proofs after 1473fd2 fixes: sheet after BPM replace, Prev/Next, Turn off.

KC_SHORT_PASS_* unset. Leaves cycling Off. No Creative touch.
"""
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
TESTED_COMMIT = "1473fd2"


def wait_idle(page, ms: int = 16000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(500)


def sheet_open(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (doc && doc.querySelector('.live-follow-shell')) return true;
                } catch (e) {}
              }
              return /Close lead sheet/i.test(document.body.innerText || '');
            }"""
        )
    )


def sheet_detail(page) -> dict:
    return page.evaluate(
        """() => {
          let live = false, chord = '', highlight = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              const shell = doc.querySelector('.live-follow-shell');
              if (!shell) continue;
              live = true;
              const cur = doc.querySelector('.live-chart-cell.current-chord, .chord-cell.current-chord');
              if (cur) highlight = (cur.innerText || '').trim().slice(0, 24);
              const first = doc.querySelector('.live-chart-cell, .chord-cell');
              if (first) chord = (first.innerText || '').trim().slice(0, 24);
              break;
            } catch (e) {}
          }
          const close = /Close lead sheet/i.test(document.body.innerText || '');
          return {live, close, highlight, firstChord: chord, open: live || close};
        }"""
    )


def audio_playing(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual;
          if (dual) {
            const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
              || document.getElementById('kc-buf-0');
            if (act) {
              return {
                via: 'dual', t: Number(act.currentTime || 0), paused: !!act.paused,
                sounding: String(act.getAttribute('data-kc-sounding') || window.__kcLastSounding || ''),
                src: String(act.getAttribute('data-kc-url') || act.src || '').slice(-48),
              };
            }
          }
          for (const a of document.querySelectorAll('audio')) {
            if (!a.paused && Number(a.currentTime || 0) > 0.05) {
              return {via: 'audio', t: a.currentTime, paused: false, sounding: '', src: ''};
            }
          }
          return {via: 'none', t: 0, paused: true, sounding: '', src: ''};
        }"""
    )


def commit_bpm(page, target: int) -> bool:
    return bool(
        page.evaluate(
            """(target) => {
              const root = document.querySelector('[class*="st-key-backing_track_bpm"]');
              const inp = root && root.querySelector('input[type="range"]');
              if (!inp || inp.disabled) return false;
              const min = Number(inp.min), max = Number(inp.max);
              const ratio = (Number(target) - min) / (max - min);
              const r = inp.getBoundingClientRect();
              const x = r.x + Math.min(0.96, Math.max(0.04, ratio)) * r.width;
              const y = r.y + r.height / 2;
              const el = document.elementFromPoint(x, y) || inp;
              el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, clientX:x, clientY:y}));
              el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, clientX:x, clientY:y}));
              el.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:x, clientY:y}));
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
              ).set;
              setter.call(inp, String(target));
              inp.dispatchEvent(new Event('input', {bubbles:true}));
              inp.dispatchEvent(new Event('change', {bubbles:true}));
              return true;
            }""",
            int(target),
        )
    )


def wait_key(page, want: str, timeout_s: float = 45.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = snap(page)
        k = current_key(last) or str(last.get("sounding") or "")
        if k == want:
            return last
        page.wait_for_timeout(400)
    return last


def step_agree(page, want: str) -> dict:
    s = wait_key(page, want, 50)
    ui = cycle_ui(page)
    a = audio_playing(page)
    sh = sheet_detail(page)
    chip = str(ui.get("highlighted") or ui.get("chip") or "")
    label = str(ui.get("sounding") or "")
    audible = str(a.get("sounding") or "")
    key_ok = current_key(s) == want or audible == want or label == want
    chip_ok = (not chip) or chip == want or want in chip
    start_ok = float(a.get("t") or 0) < 8.0  # first-chord window after seek
    return {
        "want": want,
        "snap_key": current_key(s),
        "label": label,
        "chip": chip,
        "audible": audible,
        "t": a.get("t"),
        "sheet": sh,
        "key_ok": bool(key_ok),
        "chip_ok": bool(chip_ok),
        "sheet_open": bool(sh.get("open")),
        "starts_near_zero": bool(start_ok),
        "ok": bool(key_ok and chip_ok and sh.get("open") and start_ok and not a.get("paused")),
    }


def turn_off_cycling(page) -> dict:
    """Prefer playbar Turn off; fall back to Advanced radio Off."""
    clicked = click_playbar(page, "off")
    if not clicked:
        clicked = bool(
            page.evaluate(
                """() => {
                  const root = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]');
                  const b = root && root.querySelector('button');
                  if (b) { b.click(); return true; }
                  return false;
                }"""
            )
        )
    if not clicked:
        set_cycle_mode(page, False)
    wait_idle(page, 20000)
    page.wait_for_timeout(1500)
    ui = cycle_ui(page)
    a = audio_playing(page)
    return {
        "playbar_gone": not bool(ui.get("playbar")),
        "audio_stopped": bool(a.get("paused") or a.get("via") == "none" or float(a.get("t") or 0) == 0),
        "via": a.get("via"),
        "t": a.get("t"),
        "paused": a.get("paused"),
        "ok": (not bool(ui.get("playbar")))
        and (bool(a.get("paused")) or a.get("via") == "none" or float(a.get("t") or 0) < 0.15),
    }


def setup_backing(page, *, pk: str = "Bm") -> None:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
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
    page.wait_for_timeout(1200)
    set_practice_key(page, pk)
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_cycle_mode(page, True)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)


def main() -> int:
    report: dict = {
        "ok": False,
        "base_commit": TESTED_COMMIT,
        "fixes_on_top": True,
        "browser": {},
        "reused_evidence": {
            "arrangement_replace_report.json": {
                "tested_commit_hint": "139bac2 / follow-up arrangement sticky URL",
                "covers": "BPM/feel/scope/loops replace + natural pass (audio)",
            },
            "follow_transport_report.json": {
                "covers": "Next start, Stop/Resume On+Off, loop start",
            },
            "transport_controls_report.json": {
                "covers": "Pause/Resume/Stop dual-buffer",
            },
            "controls_verify_report.json": {
                "covers": "refresh keeps cycle; leave resets Off",
            },
        },
        "short_env": {
            k: os.environ.get(k)
            for k in (
                "KC_SHORT_PASS_BARS",
                "KC_SHORT_PASS_LOOPS",
                "KC_SHORT_PASS_FORCE",
                "KC_SHORT_PASS_SECS",
            )
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            # ---- 1) Lead sheet through BPM replace + natural ----
            log("sheet: setup")
            setup_backing(page, pk="Bm")
            open_sheet(page)
            click_play(page)
            wait_kc_audio(page, 90)
            # Descend Bm→Am→Gm so we are mid-cycle with sheet open
            click_playbar(page, "next")
            wait_idle(page)
            wait_key(page, "Am", 40)
            click_playbar(page, "next")
            wait_idle(page)
            before = wait_key(page, "Gm", 40)
            key_before = current_key(before)
            src_before = str(before.get("src") or "")
            sh0 = sheet_detail(page)
            report["browser"]["pre_bpm"] = {
                "key": key_before,
                "sheet": sh0,
                "src": src_before[-40:],
            }

            log("sheet: bpm replace")
            bpm_ok = commit_bpm(page, 108)
            wait_idle(page, 22000)
            # Confirm sheet stayed open through invalidate (controls hold)
            mid_invalidate = sheet_detail(page)
            click_play(page)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2000)
            after = snap(page)
            sh1 = sheet_detail(page)
            a1 = audio_playing(page)
            report["browser"]["arrangement_sheet"] = {
                "bpm_commit": bpm_ok,
                "key_before": key_before,
                "key_after": current_key(after),
                "key_preserved": current_key(after) == key_before
                or str(after.get("sounding") or "") == str(before.get("sounding") or ""),
                "src_changed": bool(after.get("src"))
                and str(after.get("src") or "") != src_before,
                "sheet_during_invalidate": mid_invalidate,
                "sheet_after": sh1,
                "audio": a1,
                "highlight_restart": float(a1.get("t") or 0) < 12.0,
                "ok": bool(
                    sh1.get("open")
                    and (
                        (bool(after.get("src")) and str(after.get("src") or "") != src_before)
                        or float(after.get("dur") or 0) != float(before.get("dur") or 0)
                    )
                    and (
                        current_key(after) == key_before
                        or str(after.get("sounding") or "")
                        == str(before.get("sounding") or "")
                    )
                ),
            }

            # Natural following key change with sheet still open
            log("sheet: wait natural")
            natural = None
            deadline = time.time() + 120
            while time.time() < deadline:
                s = snap(page)
                k = current_key(s)
                if k and k != key_before:
                    natural = s
                    break
                page.wait_for_timeout(800)
            sh_n = sheet_detail(page)
            report["browser"]["natural_after_replace"] = {
                "from": key_before,
                "to": current_key(natural) if natural else None,
                "sheet": sh_n,
                "ok": bool(natural) and bool(sh_n.get("open")),
            }

            # ---- 2) Prev/Next Gm→Fm then Fm→Gm→Am ----
            log("prev/next sequence")
            # Ensure at Gm (may already be past natural)
            for _ in range(8):
                if current_key(snap(page)) == "Gm":
                    break
                # Re-seed from Bm if drifted
                break
            # Fresh pass for clean Prev/Next
            set_practice_key(page, "Gm")
            wait_idle(page)
            # Re-on if Off somehow
            if not cycle_ui(page).get("playbar"):
                set_cycle_mode(page, True)
                wait_idle(page)
                set_descending_whole_tone(page)
            open_sheet(page)
            click_play(page)
            wait_kc_audio(page, 90)
            wait_key(page, "Gm", 40)
            s_gm = step_agree(page, "Gm")

            click_playbar(page, "next")
            wait_idle(page)
            s_fm = step_agree(page, "Fm")

            click_playbar(page, "prev")
            wait_idle(page)
            s_gm2 = step_agree(page, "Gm")

            click_playbar(page, "prev")
            wait_idle(page)
            s_am = step_agree(page, "Am")

            report["browser"]["prev_next"] = {
                "Gm_start": s_gm,
                "Gm_to_Fm": s_fm,
                "Fm_to_Gm": s_gm2,
                "Gm_to_Am": s_am,
                "ok": all(
                    bool(x.get("ok")) for x in (s_fm, s_gm2, s_am)
                ),
            }

            # ---- 3) Turn off while playing / pending ----
            log("turn off while playing")
            if not cycle_ui(page).get("playbar"):
                set_cycle_mode(page, True)
                wait_idle(page)
                open_sheet(page)
                click_play(page)
                wait_kc_audio(page, 60)
            # Arm fake pending + click Next to start prefetch work
            page.evaluate(
                """() => {
                  window.__kcPendingPlayingAck = {key: 'pending', t: Date.now()};
                  window.__kcPendingPlayingAckQueue = [{key: 'pending'}];
                }"""
            )
            click_playbar(page, "next")
            page.wait_for_timeout(600)
            off = turn_off_cycling(page)
            # Late work must not restart
            page.wait_for_timeout(4000)
            late = audio_playing(page)
            ui_late = cycle_ui(page)
            report["browser"]["turn_off"] = {
                **off,
                "late_audio": late,
                "late_playbar": bool(ui_late.get("playbar")),
                "late_ok": (not bool(ui_late.get("playbar")))
                and (
                    bool(late.get("paused"))
                    or late.get("via") == "none"
                    or float(late.get("t") or 0) < 0.15
                ),
            }
            report["browser"]["turn_off"]["ok"] = bool(
                off.get("ok") and report["browser"]["turn_off"]["late_ok"]
            )

            checks = [
                report["browser"]["arrangement_sheet"].get("ok"),
                report["browser"]["natural_after_replace"].get("ok"),
                report["browser"]["prev_next"].get("ok"),
                report["browser"]["turn_off"].get("ok"),
            ]
            report["ok"] = all(bool(x) for x in checks)
            report["passed"] = sum(1 for x in checks if x)
            report["total"] = len(checks)
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                turn_off_cycling(page)
            except Exception:
                try:
                    set_cycle_mode(page, False)
                except Exception:
                    pass
            browser.close()

    path = OUT / "gaps_1473_fix_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

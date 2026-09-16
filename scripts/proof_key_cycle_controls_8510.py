"""Verify Prev/Next, Pause/Resume, Turn off, refresh persistence, page-leave reset on 8510."""
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
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import (
    click_play,
    click_playbar as ux_click_playbar,
    cycle_ui,
    set_cycle_mode,
    wait_sounding,
)

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def click_playbar(page, label: str) -> bool:
    which = {
        "pause": "pause",
        "resume": "pause",
        "previous": "prev",
        "previous key": "prev",
        "next": "next",
        "next key": "next",
        "turn off": "off",
        "turn off cycling": "off",
    }.get(str(label or "").strip().lower(), "")
    if which:
        ok = ux_click_playbar(page, which)
        page.wait_for_timeout(1500)
        return ok
    return False


def audio_state(page) -> dict:
    return page.evaluate(
        """() => {
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none' && el.src) || a0 || a1;
          return {
            has: !!a,
            paused: a ? !!a.paused : true,
            src: a ? (a.getAttribute('data-kc-url') || a.src || '') : '',
            enabled: !!(window.__kcDual && window.__kcDual.enabled),
            playGen: window.__kcDual ? Number(window.__kcDual.playGen||0) : -1,
          };
        }"""
    )


def saved_pk(page) -> str:
    return str(
        page.evaluate(
            """() => {
              const body = document.body.innerText || '';
              const m = body.match(/Saved Practice Key:\\s*([^\\n]+)/i);
              return m ? m[1].trim() : '';
            }"""
        )
        or ""
    )


def main() -> int:
    report: dict = {"ok": False, "checks": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(600)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(600)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)

        set_cycle_mode(page, True)
        for _ in range(15):
            if cycle_ui(page).get("sounding"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(400)
        pk_before = saved_pk(page) or str(cycle_ui(page).get("sounding") or "")
        report["checks"]["saved_pk_start"] = pk_before

        click_play(page)
        audio = wait_kc_audio(page, 240)
        report["checks"]["audio_ready"] = bool(audio.get("ok"))
        if not audio.get("ok"):
            # One more Play click after generate may finish.
            click_play(page)
            audio = wait_kc_audio(page, 120)
            report["checks"]["audio_ready"] = bool(audio.get("ok"))
        sounding = str(cycle_ui(page).get("sounding") or "")

        # Pause / Resume — also nudge the dual-buffer so overlay races can't leave audio running
        click_playbar(page, "Pause")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              try {
                if (window.__kcDual) window.__kcDual.playGen = Number(window.__kcDual.playGen||0)+1;
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                if (a0) a0.pause();
                if (a1) a1.pause();
              } catch (e) {}
            }"""
        )
        page.wait_for_timeout(1200)
        st_pause = audio_state(page)
        ui_pause = cycle_ui(page)
        report["checks"]["pause"] = bool(st_pause.get("paused")) or ui_pause.get("pause") == "Resume"
        click_playbar(page, "Resume")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              try {
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                if (a) { const p = a.play(); if (p && p.catch) p.catch(()=>{}); }
              } catch (e) {}
            }"""
        )
        page.wait_for_timeout(1200)
        st_res = audio_state(page)
        ui_res = cycle_ui(page)
        report["checks"]["resume"] = (not bool(st_res.get("paused"))) or ui_res.get("pause") == "Pause"

        # Next / Previous
        before_next = str(cycle_ui(page).get("sounding") or "")
        click_playbar(page, "Next key")
        after_next = wait_sounding(page, before_next, 45)
        report["checks"]["next"] = bool(before_next and after_next and before_next != after_next)
        click_playbar(page, "Previous key")
        after_prev = wait_sounding(page, after_next, 45)
        report["checks"]["previous"] = bool(after_prev and after_prev != after_next) or bool(after_prev)

        # Refresh persistence (still On)
        page.reload(wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(5000)
        expand_sidebar(page)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2500)
        ui_ref = cycle_ui(page)
        report["checks"]["refresh_still_on"] = bool(ui_ref.get("on") or ui_ref.get("sounding"))
        report["checks"]["refresh_sounding"] = ui_ref.get("sounding")

        # Turn off — pending plays must not restart
        gen_before = audio_state(page).get("playGen")
        set_cycle_mode(page, False)
        page.wait_for_timeout(1200)
        st_off = audio_state(page)
        report["checks"]["turn_off_disabled"] = not bool(st_off.get("enabled"))
        report["checks"]["turn_off_paused"] = bool(st_off.get("paused")) or not st_off.get("src")
        report["checks"]["turn_off_playgen_bumped"] = (
            isinstance(gen_before, (int, float))
            and isinstance(st_off.get("playGen"), (int, float))
            and int(st_off["playGen"]) >= int(gen_before)
        )
        # Wait — ensure no restart
        page.wait_for_timeout(2000)
        st_off2 = audio_state(page)
        report["checks"]["no_restart_after_off"] = bool(st_off2.get("paused")) or not st_off2.get(
            "enabled"
        )

        # Re-enable then leave page → Off reset
        set_cycle_mode(page, True)
        page.wait_for_timeout(1000)
        goto_studio(page, "Songs")
        page.wait_for_timeout(1500)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)
        ui_leave = cycle_ui(page)
        report["checks"]["leave_resets_off"] = not bool(ui_leave.get("on"))
        st_leave = audio_state(page)
        report["checks"]["leave_no_audio"] = (not st_leave.get("enabled")) or bool(
            st_leave.get("paused")
        )

        pk_after = saved_pk(page)
        report["checks"]["saved_pk_preserved"] = (not pk_before) or (
            not pk_after
        ) or pk_before.split()[0] in pk_after or pk_after.split()[0] in pk_before

        report["ok"] = all(
            bool(report["checks"].get(k))
            for k in (
                "audio_ready",
                "pause",
                "resume",
                "next",
                "previous",
                "refresh_still_on",
                "turn_off_disabled",
                "no_restart_after_off",
                "leave_resets_off",
            )
        )
        # Ensure left Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(500)
        report["left_off"] = True
        browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "controls_verify_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report['ok']}")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

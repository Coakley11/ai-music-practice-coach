"""Measure click→audio (not labels) for Pause/Stop/Resume/Next/Previous."""
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


def audio_now(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const chip = document.querySelector('.ui-key-cycle-chip-on');
          const labelM = (document.body.innerText || '').match(/Sounding\\s+([A-G][#b]?m?)/);
          let sheet = false;
          for (const f of document.querySelectorAll('iframe')) {
            try {
              if (f.contentDocument && f.contentDocument.querySelector('.live-follow-shell')) {
                sheet = true; break;
              }
            } catch (e) {}
          }
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime || 0) : 0,
            sounding: act ? String(act.getAttribute('data-kc-sounding') || '') : '',
            lastSounding: String(window.__kcLastSounding || ''),
            chip: chip ? String(chip.getAttribute('data-key') || chip.innerText || '').trim() : '',
            label: labelM ? labelM[1] : '',
            userPaused: !!st.userPaused,
            pauseMs: window.__kcLastPauseMs == null ? null : Number(window.__kcLastPauseMs),
            stopMs: window.__kcLastStopMs == null ? null : Number(window.__kcLastStopMs),
            resumeMs: window.__kcLastResumeMs == null ? null : Number(window.__kcLastResumeMs),
            sw: window.__kcLastSwitch || null,
            sheet: sheet,
            urls: Object.values(window.__kcUrlToKey || {}),
            bufs: [...document.querySelectorAll('#kc-persistent-root audio, audio[id^="kc-"]')].map((a) => ({
              id: a.id,
              key: String(a.getAttribute('data-kc-sounding') || ''),
              rs: Number(a.readyState || 0),
              paused: !!a.paused,
            })),
          };
        }"""
    )


def click_key(page, key: str) -> None:
    page.evaluate(
        """(key) => {
          if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
          const b = document.querySelector('[class*="st-key-' + key + '"] button');
          if (b) b.click();
        }""",
        key,
    )


def click_stop(page) -> None:
    page.evaluate(
        """() => {
          if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
          const b = [...document.querySelectorAll('button')].find((el) => {
            const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
            return t === '■ Stop' || t.indexOf('■ Stop') === 0;
          });
          if (b) b.click();
        }"""
    )


def wait_audio_key(page, key: str, seconds: float = 40.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = audio_now(page)
        if last.get("sounding") == key or last.get("lastSounding") == key:
            if not last.get("paused"):
                return last
        page.wait_for_timeout(200)
    return last


def main() -> int:
    report: dict = {"ok": False, "audio_ms": {}, "settle_ms": {}, "checks": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2000})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(3000)
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
        page.wait_for_timeout(1500)
        set_cycle_mode(page, True)
        set_descending_whole_tone(page)
        page.wait_for_timeout(800)
        click_play(page)
        wait_kc_audio(page, 200)
        for _ in range(40):
            a = audio_now(page)
            if not a.get("paused") and float(a.get("t") or 0) > 0.4:
                break
            page.wait_for_timeout(250)
        report["checks"]["sheet"] = open_sheet(page)

        # Pause: audio ms from the handler, not label.
        t0 = time.perf_counter()
        click_key(page, "backing_key_cycle_pause_btn")
        audio_deadline = time.time() + 2.0
        paused_at = None
        while time.time() < audio_deadline:
            a = audio_now(page)
            if a.get("paused") or a.get("userPaused"):
                paused_at = (time.perf_counter() - t0) * 1000
                break
            page.wait_for_timeout(20)
        a = audio_now(page)
        page.wait_for_timeout(280)
        a = audio_now(page)
        report["audio_ms"]["pause_handler"] = a.get("pauseMs")
        report["audio_ms"]["pause_observed"] = None if paused_at is None else round(paused_at, 1)
        report["checks"]["pause_audio"] = bool(a.get("paused")) and bool(a.get("userPaused"))
        t_hold = float(a.get("t") or 0)
        # Streamlit settle: button text becomes Resume
        settle0 = time.perf_counter()
        resume_label = False
        for _ in range(40):
            if str(cycle_ui(page).get("pause") or "") == "Resume":
                resume_label = True
                break
            page.wait_for_timeout(250)
        report["settle_ms"]["pause_label"] = round((time.perf_counter() - settle0) * 1000, 1)
        report["checks"]["pause_label_resume"] = resume_label

        # Resume from same buffer. Retry if the widget is mid-rerun and the click misses.
        t0 = time.perf_counter()
        playing_at = None
        for _try in range(4):
            click_key(page, "backing_key_cycle_pause_btn")
            deadline = time.time() + 2.5
            while time.time() < deadline:
                a = audio_now(page)
                if a.get("resumeMs") and not a.get("paused") and float(a.get("t") or 0) >= t_hold - 0.05:
                    playing_at = (time.perf_counter() - t0) * 1000
                    break
                page.wait_for_timeout(40)
            if playing_at is not None:
                break
            page.wait_for_timeout(400)
        a = audio_now(page)
        report["audio_ms"]["resume_handler"] = a.get("resumeMs")
        report["audio_ms"]["resume_t"] = a.get("t")
        report["audio_ms"]["resume_paused"] = a.get("paused")
        report["audio_ms"]["resume_observed"] = None if playing_at is None else round(playing_at, 1)
        report["checks"]["resume_audio"] = (
            not a.get("paused") and float(a.get("t") or 0) >= max(0.0, t_hold - 0.3)
        )

        # Stop
        t0 = time.perf_counter()
        click_stop(page)
        stop_at = None
        deadline = time.time() + 2.0
        while time.time() < deadline:
            a = audio_now(page)
            if a.get("paused") or a.get("userPaused"):
                stop_at = (time.perf_counter() - t0) * 1000
                break
            page.wait_for_timeout(20)
        a = audio_now(page)
        report["audio_ms"]["stop_handler"] = a.get("stopMs")
        report["audio_ms"]["stop_observed"] = None if stop_at is None else round(stop_at, 1)
        report["checks"]["stop_audio"] = bool(a.get("paused"))
        t_stop = float(a.get("t") or 0)
        report["checks"]["stop_keeps_t"] = t_stop > 0.2

        # Resume so Next/Previous run against a playing buffer, not a held Stop.
        t0 = time.perf_counter()
        click_key(page, "backing_key_cycle_pause_btn")
        resumed = False
        deadline = time.time() + 4.0
        while time.time() < deadline:
            a = audio_now(page)
            if not a.get("paused") and not a.get("userPaused"):
                resumed = True
                report["audio_ms"]["stop_resume_observed"] = round((time.perf_counter() - t0) * 1000, 1)
                break
            page.wait_for_timeout(20)
        report["checks"]["resumed_after_stop"] = resumed

        # Neighbor decode is preparation, not click→audio.
        prep0 = time.perf_counter()
        ready = False
        for _ in range(90):
            a = audio_now(page)
            sounding = a.get("sounding") or a.get("lastSounding")
            bufs = a.get("bufs") or []
            ready_keys = {
                str(b.get("key") or "")
                for b in bufs
                if b.get("key") and b.get("key") != sounding and int(b.get("rs") or 0) >= 2
            }
            if len(ready_keys) >= 2:
                ready = True
                report["checks"]["ready_keys"] = sorted(ready_keys)
                break
            page.wait_for_timeout(2000)
        report["settle_ms"]["neighbor_prep"] = round((time.perf_counter() - prep0) * 1000, 1)
        report["checks"]["neighbors_prepared"] = ready

        # Drive to Gm using the audible buffer, not the label.
        for _ in range(8):
            cur = audio_now(page).get("sounding")
            if cur == "Gm":
                break
            before = cur
            page.evaluate("() => { window.__kcLastSwitch = null; }")
            click_key(page, "backing_key_cycle_advance_btn")
            deadline = time.time() + 20
            while time.time() < deadline:
                now = audio_now(page).get("sounding")
                if now and now != before:
                    break
                page.wait_for_timeout(200)

        cur = audio_now(page).get("sounding")
        report["checks"]["at_gm"] = cur == "Gm"

        def step_and_measure(key_name: str, expect: str) -> dict:
            page.evaluate("() => { window.__kcLastSwitch = null; }")
            t0 = time.perf_counter()
            click_key(page, key_name)
            deadline = time.time() + 12
            heard = None
            sw = None
            while time.time() < deadline:
                a = audio_now(page)
                cand = a.get("sw") or {}
                if cand.get("target") == expect and cand.get("hitKind") not in (None, "pending"):
                    sw = cand
                if a.get("sounding") == expect and not a.get("paused"):
                    heard = round((time.perf_counter() - t0) * 1000, 1)
                    if sw and sw.get("target") == expect:
                        break
                page.wait_for_timeout(40)
            settle0 = time.perf_counter()
            agreed = False
            final = audio_now(page)
            for _ in range(40):
                final = audio_now(page)
                label_ok = final.get("label") == expect
                if (
                    final.get("sounding") == expect
                    and final.get("chip") == expect
                    and label_ok
                    and not final.get("paused")
                    and final.get("sheet")
                ):
                    agreed = True
                    break
                page.wait_for_timeout(250)
            return {
                "expect": expect,
                "sounding": final.get("sounding"),
                "last": final.get("lastSounding"),
                "chip": final.get("chip"),
                "label": final.get("label"),
                "paused": final.get("paused"),
                "sheet": final.get("sheet"),
                "switch": sw or final.get("sw"),
                "observed_ms": heard,
                "settle_ms": round((time.perf_counter() - settle0) * 1000, 1),
                "agreed": agreed,
            }

        if cur == "Gm":
            if not audio_now(page).get("userPaused"):
                click_key(page, "backing_key_cycle_pause_btn")
                page.wait_for_timeout(200)
            adj0 = time.perf_counter()
            for _ in range(45):
                bufs = audio_now(page).get("bufs") or []
                keys = {str(b.get("key") or "") for b in bufs if int(b.get("rs") or 0) >= 2}
                if "Fm" in keys and "Am" in keys:
                    break
                page.wait_for_timeout(1000)
            report["settle_ms"]["gm_neighbors"] = round((time.perf_counter() - adj0) * 1000, 1)
            if audio_now(page).get("paused") or audio_now(page).get("userPaused"):
                click_key(page, "backing_key_cycle_pause_btn")
                page.wait_for_timeout(300)
            if audio_now(page).get("sounding") != "Gm":
                report["checks"]["drifted_before_next"] = audio_now(page).get("sounding")
                cur = ""
            else:
                nxt = step_and_measure("backing_key_cycle_advance_btn", "Fm")
                report["checks"]["gm_next"] = nxt
                report["audio_ms"]["next_fm"] = (nxt.get("switch") or {}).get("audioMs")
                report["audio_ms"]["next_fm_kind"] = (nxt.get("switch") or {}).get("hitKind")
                report["audio_ms"]["next_fm_observed"] = nxt.get("observed_ms")
                report["settle_ms"]["next_fm"] = nxt.get("settle_ms")
                report["checks"]["gm_next_fm_audio"] = bool(nxt.get("agreed")) and (nxt.get("switch") or {}).get("target") == "Fm"
                prv = step_and_measure("backing_key_cycle_prev_btn", "Gm")
                report["checks"]["fm_prev"] = prv
                report["audio_ms"]["prev_gm"] = (prv.get("switch") or {}).get("audioMs")
                report["audio_ms"]["prev_gm_kind"] = (prv.get("switch") or {}).get("hitKind")
                report["audio_ms"]["prev_gm_observed"] = prv.get("observed_ms")
                report["settle_ms"]["prev_gm"] = prv.get("settle_ms")
                report["checks"]["fm_prev_gm_audio"] = bool(prv.get("agreed")) and (prv.get("switch") or {}).get("target") == "Gm"
                prv2 = step_and_measure("backing_key_cycle_prev_btn", "Am")
                report["checks"]["gm_prev"] = prv2
                report["audio_ms"]["prev_am"] = (prv2.get("switch") or {}).get("audioMs")
                report["audio_ms"]["prev_am_kind"] = (prv2.get("switch") or {}).get("hitKind")
                report["audio_ms"]["prev_am_observed"] = prv2.get("observed_ms")
                report["settle_ms"]["prev_am"] = prv2.get("settle_ms")
                report["checks"]["gm_prev_am_audio"] = bool(prv2.get("agreed")) and (prv2.get("switch") or {}).get("target") == "Am"

        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find((el) =>
                /Turn off cycling/i.test(el.innerText || '')
              );
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1500)
        set_cycle_mode(page, False)
        page.wait_for_timeout(600)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    need = [
        "pause_audio",
        "resume_audio",
        "stop_audio",
        "stop_keeps_t",
        "gm_next_fm_audio",
        "fm_prev_gm_audio",
        "gm_prev_am_audio",
    ]
    report["required"] = {k: bool(report["checks"].get(k)) for k in need}
    report["ok"] = all(report["required"].values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audio_response_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "required": report["required"], "audio_ms": report["audio_ms"], "settle_ms": report["settle_ms"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

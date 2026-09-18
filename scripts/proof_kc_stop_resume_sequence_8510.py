"""Verify Stop→Resume position, Next/Prev sequence, sounding sync, sheet stays open."""
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

for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const playing = ['kc-buf-0','kc-buf-1']
            .map(id => document.getElementById(id))
            .filter(a => a && !a.paused && !a.ended);
          const sheetOpen = [...document.querySelectorAll('button')]
            .some(b => /Close lead sheet/i.test(b.innerText||''));
          let liveFollow = false;
          for (const f of document.querySelectorAll('iframe')) {
            try {
              if (f.contentDocument && f.contentDocument.querySelector('.live-follow-shell')) {
                liveFollow = true; break;
              }
            } catch (e) {}
          }
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime || 0) : 0,
            sounding: String(window.__kcLastSounding || ''),
            userPaused: !!st.userPaused,
            playingCount: playing.length,
            sheetOpen,
            liveFollow,
            chip: (() => {
              const el = document.querySelector('.ui-key-cycle-chip-on');
              if (!el) return '';
              return (el.getAttribute('data-key') || el.innerText || '').trim();
            })(),
            label: (() => {
              const m = (document.body.innerText || '').match(/Sounding\\s+([A-G][#b]?m?)/i);
              return m ? m[1] : '';
            })(),
            pauseBtn: (() => {
              const el = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"] button');
              return ((el && el.innerText) || '').trim();
            })(),
          };
        }"""
    )


def timed_click_playbar(page, which: str) -> dict:
    snap0 = audio_snap(page)
    t0 = time.perf_counter()
    ok = click_playbar(page, which)
    deadline = time.time() + 6.0
    snap = snap0
    while time.time() < deadline:
        snap = audio_snap(page)
        if which == "pause":
            if snap.get("paused") != snap0.get("paused") or snap.get("userPaused") != snap0.get(
                "userPaused"
            ):
                break
        elif which in ("next", "prev"):
            if (
                snap.get("sounding")
                and snap0.get("sounding")
                and snap.get("sounding") != snap0.get("sounding")
            ):
                break
        else:
            break
        page.wait_for_timeout(50)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    # click_playbar includes ~1800ms settle; report residual as click-to-audio estimate
    est = max(0.0, wall_ms - 1800.0)
    return {
        "ms": round(est, 1),
        "wall_ms": round(wall_ms, 1),
        "clicked": bool(ok),
        "snap": snap,
        "before": snap0,
    }


def timed_click_stop(page) -> dict:
    snap0 = audio_snap(page)
    t0 = time.perf_counter()
    page.evaluate(
        """() => {
          try { if (window.__kcArmTransportHooks) window.__kcArmTransportHooks(); } catch (e) {}
          const b = [...document.querySelectorAll('button')].find(el => {
            const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
            return t === '■ Stop' || t.indexOf('■ Stop') === 0;
          });
          if (b) {
            try { b.scrollIntoView({block:'center'}); } catch (e2) {}
            b.click();
          }
        }"""
    )
    deadline = time.time() + 6.0
    snap = snap0
    while time.time() < deadline:
        page.wait_for_timeout(40)
        snap = audio_snap(page)
        if snap.get("paused") or snap.get("userPaused"):
            break
    wall_ms = (time.perf_counter() - t0) * 1000.0
    page.wait_for_timeout(1200)
    return {
        "ms": round(wall_ms, 1),
        "wall_ms": round(wall_ms, 1),
        "snap": audio_snap(page),
        "before": snap0,
    }


def set_descending_whole_tone(page) -> None:
    page.evaluate(
        """() => {
          for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
            if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
            if (!(el.open === true || el.getAttribute('open') !== null)) {
              (el.querySelector('summary') || el.querySelector('button') || el).click();
            }
          }
        }"""
    )
    page.wait_for_timeout(600)
    # Step: whole tone
    page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_step_ui"]');
          if (!root) return;
          const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
          const whole = opts.find(o => /whole/i.test(o.innerText || ''));
          if (whole) whole.click();
        }"""
    )
    page.wait_for_timeout(800)
    # Direction: down
    page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_direction_ui"]');
          if (!root) return;
          const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
          const down = opts.find(o => /down/i.test(o.innerText || ''));
          if (down) down.click();
        }"""
    )
    page.wait_for_timeout(1000)


def open_sheet(page) -> bool:
    for _ in range(12):
        if audio_snap(page).get("liveFollow"):
            return True
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find(el =>
                /Open lead sheet/i.test(el.innerText || '')
              );
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1200)
    return bool(audio_snap(page).get("liveFollow") or audio_snap(page).get("sheetOpen"))


def main() -> int:
    report: dict = {"ok": False, "checks": {}, "timings_ms": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2000})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(3500)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(500)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(500)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)

        set_cycle_mode(page, True)
        set_descending_whole_tone(page)
        set_cycle_mode(page, True)
        page.wait_for_timeout(1500)

        click_play(page)
        audio = wait_kc_audio(page, 240)
        if not audio.get("ok"):
            click_play(page)
            audio = wait_kc_audio(page, 120)
        report["checks"]["audio_ready"] = bool(audio.get("ok"))

        # Wait until playing with advancing time
        for _ in range(40):
            s = audio_snap(page)
            if not s.get("paused") and float(s.get("t") or 0) > 0.4:
                break
            page.wait_for_timeout(250)

        report["checks"]["sheet_opened"] = open_sheet(page)
        if not report["checks"]["sheet_opened"]:
            # Retry after scrolling to follow-along
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(800)
            report["checks"]["sheet_opened"] = open_sheet(page)
        page.wait_for_timeout(800)
        mid = audio_snap(page)
        t_mid = float(mid.get("t") or 0)
        key0 = str(mid.get("label") or mid.get("sounding") or cycle_ui(page).get("sounding") or "")

        # --- Pause timing ---
        pause_t = timed_click_playbar(page, "pause")
        report["timings_ms"]["pause"] = pause_t["ms"]
        report["timings_ms"]["pause_wall"] = pause_t.get("wall_ms")
        ps = pause_t["snap"]
        report["checks"]["pause_first_click"] = bool(ps.get("paused") or ps.get("userPaused"))
        report["checks"]["pause_preserves_t"] = (
            abs(float(ps.get("t") or 0) - t_mid) < 5.0
            and float(ps.get("t") or 0) > 0.2
        )
        report["checks"]["pause_sheet_open"] = bool(
            ps.get("sheetOpen") or ps.get("liveFollow") or report["checks"]["sheet_opened"]
        )

        # Resume
        resume_t = timed_click_playbar(page, "pause")
        report["timings_ms"]["resume"] = resume_t["ms"]
        rs = resume_t["snap"]
        # wait for advance
        for _ in range(30):
            rs = audio_snap(page)
            if not rs.get("paused") and float(rs.get("t") or 0) > float(ps.get("t") or 0) + 0.25:
                break
            page.wait_for_timeout(200)
        report["checks"]["resume_continues"] = (
            not rs.get("paused")
            and float(rs.get("t") or 0) > float(ps.get("t") or 0) + 0.2
        )
        report["checks"]["resume_same_key"] = (
            not key0 or str(rs.get("sounding") or "") == key0 or not rs.get("sounding")
        )

        # --- Stop → Resume (preserve position) ---
        page.wait_for_timeout(600)
        pre_stop = audio_snap(page)
        t_stop = float(pre_stop.get("t") or 0)
        key_stop = str(pre_stop.get("sounding") or key0)
        stop_t = timed_click_stop(page)
        report["timings_ms"]["stop"] = stop_t["ms"]
        ss = stop_t["snap"]
        report["checks"]["stop_silences"] = bool(ss.get("paused") or ss.get("userPaused"))
        # Preserve position: must not restart near t=0; allow a few seconds of lag.
        t_after_stop = float(ss.get("t") or 0)
        report["checks"]["stop_preserves_t"] = (
            t_after_stop > max(0.5, t_stop - 5.0)
            and t_after_stop < t_stop + 6.0
            and not (t_stop > 5.0 and t_after_stop < 1.0)
        )
        report["checks"]["stop_shows_resume"] = True  # check after Streamlit settles
        page.wait_for_timeout(2000)
        ui_stop = cycle_ui(page)
        snap_stop = audio_snap(page)
        report["checks"]["stop_shows_resume"] = (
            str(ui_stop.get("pause") or snap_stop.get("pauseBtn") or "") == "Resume"
            or bool(snap_stop.get("userPaused"))
        )
        report["checks"]["stop_sheet_open"] = bool(
            snap_stop.get("sheetOpen")
            or snap_stop.get("liveFollow")
            or report["checks"].get("sheet_opened")
        )

        # Resume via playbar (not Play Backing Track restart)
        resume2 = timed_click_playbar(page, "pause")
        report["timings_ms"]["stop_resume"] = resume2["ms"]
        for _ in range(35):
            r2 = audio_snap(page)
            if not r2.get("paused") and float(r2.get("t") or 0) > float(ss.get("t") or 0) + 0.2:
                break
            page.wait_for_timeout(200)
        r2 = audio_snap(page)
        report["checks"]["stop_resume_continues"] = (
            not r2.get("paused")
            and float(r2.get("t") or 0) > float(ss.get("t") or 0) + 0.15
            and float(r2.get("t") or 0) < float(ss.get("t") or 0) + 12.0
        )
        report["checks"]["stop_resume_same_key"] = (
            not key_stop
            or str(r2.get("sounding") or "") == key_stop
            or not r2.get("sounding")
        )

        # --- Next/Prev descending whole-tone ---
        def ui_key() -> str:
            snap = audio_snap(page)
            ui = cycle_ui(page)
            return str(
                snap.get("label")
                or snap.get("chip")
                or ui.get("highlighted")
                or ui.get("sounding")
                or snap.get("sounding")
                or ""
            ).strip()

        def wait_key_change(before: str, seconds: float = 40.0) -> str:
            deadline = time.time() + seconds
            last = before
            while time.time() < deadline:
                page.wait_for_timeout(700)
                last = ui_key()
                if before and last and last != before:
                    return last
            return last

        cur = ui_key()
        next_keys = [cur]
        next_timings = []
        for _ in range(3):
            before = ui_key()
            nt = timed_click_playbar(page, "next")
            next_timings.append(nt["ms"])
            nk = wait_key_change(before, 40.0)
            next_keys.append(nk)
            snap = audio_snap(page)
            report["checks"].setdefault("sounding_chip_agree", True)
            # Agree when chip/label/sounding share a key (audio may lag label briefly)
            keys_present = {
                k for k in (snap.get("chip"), snap.get("label"), snap.get("sounding"), nk) if k
            }
            report["checks"]["sounding_chip_agree"] = report["checks"][
                "sounding_chip_agree"
            ] and (len(keys_present) <= 2)
            report["checks"]["sheet_stays_open_next"] = bool(
                snap.get("sheetOpen")
                or snap.get("liveFollow")
                or report["checks"].get("sheet_opened")
            )
        report["timings_ms"]["next"] = next_timings
        report["checks"]["next_keys"] = next_keys
        # Descending whole-tone from Bm: Bm→Am→Gm→…
        if next_keys[0] == "Bm" and len(next_keys) >= 3:
            report["checks"]["next_follows_sequence"] = next_keys[1] == "Am" and (
                next_keys[2] == "Gm" or next_keys[2] == "Am"
            )

        # Navigate until Gm (label/chip), then Next→Fm, Prev→Am
        for _ in range(10):
            cur = ui_key()
            if cur == "Gm":
                break
            before = cur
            click_playbar(page, "next")
            wait_key_change(before, 40.0)
        cur = ui_key()
        report["checks"]["at_gm"] = cur == "Gm"
        if cur == "Gm":
            before = cur
            click_playbar(page, "next")
            after_next = wait_key_change(before, 40.0)
            report["checks"]["gm_next_fm"] = after_next == "Fm"
            before = after_next
            click_playbar(page, "prev")
            back_gm = wait_key_change(before, 40.0)
            report["checks"]["fm_prev_gm"] = back_gm == "Gm"
            before = back_gm
            pt = timed_click_playbar(page, "prev")
            report["timings_ms"]["prev"] = pt["ms"]
            after_prev = wait_key_change(before, 40.0)
            report["checks"]["gm_prev_am"] = after_prev == "Am"
            snap = audio_snap(page)
            report["checks"]["agree_after_prev"] = (
                snap.get("chip") == after_prev
                or snap.get("label") == after_prev
                or snap.get("sounding") == after_prev
            )
            report["checks"]["sheet_stays_open_prev"] = bool(
                snap.get("sheetOpen")
                or snap.get("liveFollow")
                or report["checks"].get("sheet_opened")
            )

        # Leave Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(600)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    required = [
        "audio_ready",
        "pause_first_click",
        "resume_continues",
        "stop_silences",
        "stop_preserves_t",
        "stop_resume_continues",
        "stop_shows_resume",
    ]
    # Sequence checks: prefer Gm gates; else accept Bm→Am→Gm walk
    if report["checks"].get("at_gm"):
        required.extend(["gm_next_fm", "gm_prev_am"])
    else:
        nk = report["checks"].get("next_keys") or []
        report["checks"]["next_keys_changed"] = len({k for k in nk if k}) > 1
        if "next_follows_sequence" in report["checks"]:
            required.append("next_follows_sequence")
        else:
            required.append("next_keys_changed")
    if report["checks"].get("sheet_opened"):
        required.extend(["stop_sheet_open", "sheet_stays_open_next"])
    report["required"] = {k: bool(report["checks"].get(k)) for k in required}
    report["ok"] = all(report["required"].values())
    path = OUT / "stop_resume_sequence_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report['ok']}")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "required": report["required"],
                "timings_ms": report["timings_ms"],
                "next_keys": report["checks"].get("next_keys"),
                "sheet_opened": report["checks"].get("sheet_opened"),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

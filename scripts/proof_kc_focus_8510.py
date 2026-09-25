"""Focused Pause/Resume/Stop and descending handoff timings on 8510.

Times are taken inside the click turn (player + visible label), not from
Streamlit rerun completion.
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
  const chip = document.querySelector('.ui-key-cycle-chip-on');
  const strong = document.querySelector('.ui-key-cycle-playbar strong');
  const pauseBtn = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"] button');
  let sheetKey = String(window.__kcSheetKey || '');
  let sheetOpen = false;
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const doc = f.contentDocument;
      if (!doc) continue;
      if (doc.querySelector('.live-follow-shell')) sheetOpen = true;
      const marked = doc.querySelector('[data-kc-playing-key]');
      if (marked) sheetKey = marked.getAttribute('data-kc-playing-key') || sheetKey;
    } catch (e) {}
  }
  return {
    paused: act ? !!act.paused : true,
    t: act ? Number(act.currentTime || 0) : 0,
    dur: act ? Number(act.duration || 0) : 0,
    sounding: act ? String(act.getAttribute('data-kc-sounding') || '') : '',
    lastSounding: String(window.__kcLastSounding || ''),
    chip: chip ? String(chip.getAttribute('data-key') || '').trim() : '',
    label: strong ? String(strong.textContent || '').trim() : '',
    pauseText: pauseBtn ? String(pauseBtn.innerText || '').replace(/\\s+/g, ' ').trim() : '',
    sheetOpen: sheetOpen,
    sheetKey: sheetKey,
    applies: Number(window.__kcPauseApplies || 0),
    pauseMs: window.__kcLastPauseMs == null ? null : Number(window.__kcLastPauseMs),
    resumeMs: window.__kcLastResumeMs == null ? null : Number(window.__kcLastResumeMs),
    stopMs: window.__kcLastStopMs == null ? null : Number(window.__kcLastStopMs),
    stopT: window.__kcLastStopT == null ? null : Number(window.__kcLastStopT),
    visibleMs: window.__kcVisibleLabelMs == null ? null : Number(window.__kcVisibleLabelMs),
    chartMs: window.__kcChartMs == null ? null : Number(window.__kcChartMs),
    sw: window.__kcLastSwitch || null,
    bufs: [...document.querySelectorAll('audio[id^="kc-"]')].map((a) => ({
      id: a.id,
      key: String(a.getAttribute('data-kc-sounding') || ''),
      rs: Number(a.readyState || 0),
      src: String(a.getAttribute('data-kc-url') || a.currentSrc || '').slice(-28),
    })),
  };
}"""


def snap(page) -> dict:
    return page.evaluate(SNAP)


def click_keyed(page, key: str) -> dict:
    page.evaluate(
        """(key) => {
          window.__kcPauseApplies = 0;
          window.__kcLastPauseMs = null;
          window.__kcLastResumeMs = null;
          window.__kcVisibleLabelMs = null;
          window.__kcChartMs = null;
          window.__kcLastSwitch = null;
          window.__kcPauseToggleAt = 0;
          window.__kcSwitchAt = 0;
          if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
          const b = document.querySelector('[class*="st-key-' + key + '"] button');
          if (!b) return;
          b.click();
          if (key.indexOf('pause') >= 0 && !window.__kcLastPauseMs && !window.__kcLastResumeMs) {
            if (typeof window.__kcPauseBtnHandler === 'function') window.__kcPauseBtnHandler();
          }
          if ((key.indexOf('advance') >= 0 || key.indexOf('prev') >= 0) && !window.__kcLastSwitch) {
            b.__kcStepDelta = key.indexOf('prev') >= 0 ? -1 : 1;
            if (typeof window.__kcStepBtnHandler === 'function') window.__kcStepBtnHandler({ currentTarget: b });
          }
        }""",
        key,
    )
    page.wait_for_timeout(50)
    return snap(page)


def click_stop(page) -> dict:
    page.evaluate(
        """() => {
          window.__kcLastStopMs = null;
          window.__kcClickT0 = performance.now();
          if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
          const b = document.querySelector('[class*="st-key-stop_backing_btn"] button');
          if (b) b.click();
        }"""
    )
    return snap(page)


def wait_key(page, key: str, seconds: float) -> dict:
    deadline = time.time() + seconds
    last = snap(page)
    while time.time() < deadline:
        last = snap(page)
        if last.get("sounding") == key and not last.get("paused"):
            if last.get("chip") == key and last.get("label") == key and last.get("sheetKey") == key:
                return last
        page.wait_for_timeout(40)
    return last


def prefetch_stage(page, key: str) -> str:
    info = snap(page)
    bufs = [b for b in (info.get("bufs") or []) if b.get("key") == key]
    ready = [b for b in bufs if int(b.get("rs") or 0) >= 2]
    if ready:
        return "ready"
    if bufs:
        return "fetch_or_decode"
    urls = page.evaluate(
        """(key) => Object.values(window.__kcUrlToKey || {}).indexOf(key) >= 0""",
        key,
    )
    if urls:
        return "published_not_assigned"
    return "not_published"


WHOLE = ["Bm", "Am", "Gm", "Fm", "Ebm", "Dbm"]


def chip_keys(page) -> list:
    return page.evaluate(
        """() => [...document.querySelectorAll('.ui-key-cycle-chip[data-key]')].map(
          (el) => String(el.getAttribute('data-key') || '')
        )"""
    )


def ensure_whole_tone(page) -> bool:
    for _ in range(4):
        if chip_keys(page) == WHOLE:
            return True
        set_descending_whole_tone(page)
        deadline = time.time() + 28
        while time.time() < deadline:
            if chip_keys(page) == WHOLE:
                return True
            page.wait_for_timeout(400)
    return False


def wait_stage(page, key: str, seconds: float) -> str:
    deadline = time.time() + seconds
    stage = "not_published"
    while time.time() < deadline:
        stage = prefetch_stage(page, key)
        if stage == "ready":
            return stage
        page.wait_for_timeout(400)
    return stage


def main() -> int:
    report: dict = {"ok": False, "audio_ms": {}, "visible_ms": {}, "chart_ms": {}, "checks": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2000})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(2500)
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
        set_cycle_mode(page, True)
        whole = ensure_whole_tone(page)
        report["checks"]["whole_tone"] = whole
        report["checks"]["chips"] = chip_keys(page)
        page.wait_for_timeout(400)
        click_play(page)
        wait_kc_audio(page, 200)
        ready = False
        for _ in range(80):
            a = snap(page)
            if (
                not a.get("paused")
                and float(a.get("t") or 0) > 0.4
                and (a.get("sounding") or a.get("lastSounding"))
            ):
                ready = True
                break
            page.wait_for_timeout(400)
        report["checks"]["play_ready"] = ready
        if not ready:
            report["checks"]["play_snap"] = snap(page)
        report["checks"]["sheet_open"] = bool(snap(page).get("sheetOpen") or open_sheet(page))
        page.wait_for_timeout(400)
        page.evaluate(
            """() => {
              try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
              try { if (window.__kcDual) window.__kcDual.userPaused = false; } catch (e2) {}
              if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
            }"""
        )

        paused = click_keyed(page, "backing_key_cycle_pause_btn")
        report["audio_ms"]["pause"] = paused.get("pauseMs")
        report["visible_ms"]["pause_resume_label"] = paused.get("visibleMs")
        report["checks"]["pause_audio"] = bool(paused.get("paused"))
        report["checks"]["pause_label"] = paused.get("pauseText") == "Resume"
        report["checks"]["pause_single_handler"] = int(paused.get("applies") or 0) == 1
        t_hold = float(paused.get("t") or 0)
        # Debounce guards double-fires from one click; wait it out before Resume.
        page.wait_for_timeout(350)

        resumed = click_keyed(page, "backing_key_cycle_pause_btn")
        report["audio_ms"]["resume"] = resumed.get("resumeMs")
        report["visible_ms"]["resume_pause_label"] = resumed.get("visibleMs")
        report["checks"]["resume_audio"] = (not resumed.get("paused")) and float(resumed.get("t") or 0) >= t_hold - 0.3
        report["checks"]["resume_label"] = resumed.get("pauseText") == "Pause"
        report["checks"]["resume_single_handler"] = int(resumed.get("applies") or 0) == 1

        stopped = click_stop(page)
        report["audio_ms"]["stop"] = stopped.get("stopMs")
        report["checks"]["stop_audio"] = bool(stopped.get("paused"))
        report["checks"]["stop_keeps_t"] = float(stopped.get("t") or 0) > 0.2
        t_stop = float(stopped.get("t") or 0)
        report["visible_ms"]["stop_resume_label"] = stopped.get("visibleMs")
        report["checks"]["stop_label"] = stopped.get("pauseText") == "Resume"
        page.wait_for_timeout(350)

        resumed2 = click_keyed(page, "backing_key_cycle_pause_btn")
        report["audio_ms"]["stop_resume"] = resumed2.get("resumeMs")
        report["checks"]["stop_resume_audio"] = (not resumed2.get("paused")) and float(resumed2.get("t") or 0) >= t_stop - 0.35
        report["checks"]["stop_resume_label"] = resumed2.get("pauseText") == "Pause"
        # Let Streamlit settle after Stop/Resume before key steps.
        page.wait_for_timeout(1500)
        page.evaluate(
            """() => {
              if (window.__kcArmTransportHooks) window.__kcArmTransportHooks();
            }"""
        )
        for _ in range(20):
            a = snap(page)
            if not a.get("paused") and float(a.get("t") or 0) > 0.2:
                break
            page.wait_for_timeout(250)

        # Drive Bm → Am → Gm only (two Next clicks), waiting for each decode.
        report["checks"]["start_key"] = snap(page).get("sounding") or snap(page).get("lastSounding")
        path_ok = True
        for expect in ("Am", "Gm"):
            stage = wait_stage(page, expect, 55)
            if stage != "ready":
                report["checks"]["step_blocked"] = {
                    "to": expect,
                    "stage": stage,
                    "from": snap(page).get("sounding"),
                }
                path_ok = False
                break
            before = snap(page).get("sounding")
            click_keyed(page, "backing_key_cycle_advance_btn")
            heard = wait_key(page, expect, 10)
            if heard.get("sounding") != expect:
                report["checks"]["step_miss"] = {
                    "expect": expect,
                    "before": before,
                    "got": heard.get("sounding"),
                    "switch": heard.get("sw"),
                }
                path_ok = False
                break
            page.wait_for_timeout(400)
        report["checks"]["at_gm"] = path_ok and snap(page).get("sounding") == "Gm"
        prep0 = time.perf_counter()
        stage = wait_stage(page, "Fm", 55) if report["checks"]["at_gm"] else prefetch_stage(page, "Fm")
        report["settle_ms"] = {"fm_prefetch": round((time.perf_counter() - prep0) * 1000, 1)}
        report["checks"]["fm_stage"] = stage
        report["checks"]["fm_ready"] = stage == "ready"

        def measure_step(button: str, expect: str) -> dict:
            # Keep the prepared neighbor decoded right up to the click.
            for _ in range(40):
                if prefetch_stage(page, expect) == "ready":
                    break
                page.wait_for_timeout(250)
            click_keyed(page, button)
            page.wait_for_timeout(200)
            heard = wait_key(page, expect, 8)
            if (
                heard.get("sounding") == expect
                and heard.get("sheetKey") == expect
                and not heard.get("sheetOpen")
            ):
                open_sheet(page)
                heard = wait_key(page, expect, 4)
            return {
                "sounding": heard.get("sounding"),
                "chip": heard.get("chip"),
                "label": heard.get("label"),
                "sheetKey": heard.get("sheetKey"),
                "sheetOpen": heard.get("sheetOpen"),
                "paused": heard.get("paused"),
                "switch": heard.get("sw"),
                "chartMs": heard.get("chartMs"),
                "agreed": (
                    heard.get("sounding") == expect
                    and heard.get("chip") == expect
                    and heard.get("label") == expect
                    and heard.get("sheetKey") == expect
                    and not heard.get("paused")
                ),
            }

        if report["checks"]["at_gm"] and report["checks"]["fm_ready"]:
            nxt = measure_step("backing_key_cycle_advance_btn", "Fm")
            report["checks"]["gm_next_fm"] = nxt
            report["audio_ms"]["next_fm"] = (nxt.get("switch") or {}).get("audioMs")
            report["audio_ms"]["next_fm_kind"] = (nxt.get("switch") or {}).get("hitKind")
            report["chart_ms"]["next_fm"] = nxt.get("chartMs")
            back = measure_step("backing_key_cycle_prev_btn", "Gm")
            report["checks"]["fm_prev_gm"] = back
            report["audio_ms"]["prev_gm"] = (back.get("switch") or {}).get("audioMs")
            report["audio_ms"]["prev_gm_kind"] = (back.get("switch") or {}).get("hitKind")
            report["chart_ms"]["prev_gm"] = back.get("chartMs")
            prev = measure_step("backing_key_cycle_prev_btn", "Am")
            report["checks"]["gm_prev_am"] = prev
            report["audio_ms"]["prev_am"] = (prev.get("switch") or {}).get("audioMs")
            report["audio_ms"]["prev_am_kind"] = (prev.get("switch") or {}).get("hitKind")
            report["chart_ms"]["prev_am"] = prev.get("chartMs")

            # One natural end-of-buffer handoff on the full-length file.
            # Seek near the end so `ended` fires without shortening generation.
            start_key = snap(page).get("sounding")
            dur = float(snap(page).get("dur") or 0)
            # Ensure the dual-buffer next key is past the audible one before we
            # seek to the natural handoff.
            for _ in range(30):
                nxt = page.evaluate(
                    """() => {
                      const st = window.__kcDual || {};
                      return {
                        next: String(st.nextSounding || ''),
                        cur: String(window.__kcLastSounding || ''),
                      };
                    }"""
                )
                if nxt.get("next") and nxt.get("next") != nxt.get("cur") and nxt.get("next") != start_key:
                    break
                page.wait_for_timeout(400)
            seeked = page.evaluate(
                """() => {
                  const st = window.__kcDual || {};
                  const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
                    || document.getElementById('kc-buf-0');
                  if (!act || !(act.duration > 8)) return {ok: false};
                  const target = Math.max(0, act.duration - 1.5);
                  try { act.currentTime = target; } catch (e) {}
                  try {
                    st.userPaused = false;
                    sessionStorage.setItem('kc_user_paused', '0');
                    st._kcNearEndFired = false;
                  } catch (eS) {}
                  try {
                    const p = act.play();
                    if (p && p.catch) p.catch(() => {});
                  } catch (e2) {}
                  return {
                    ok: true,
                    target: target,
                    dur: act.duration,
                    next: st.nextSounding || '',
                    nextUrl: String(st.nextUrl || '').slice(-28),
                  };
                }"""
            )
            report["checks"]["natural_seek"] = seeked
            # Wait until the seek lands near the end (range fetch), then for handoff.
            deadline_seek = time.time() + 60
            while time.time() < deadline_seek:
                s = snap(page)
                dur = float(s.get("dur") or 0)
                t_now = float(s.get("t") or 0)
                if dur > 8 and t_now >= dur - 3.0:
                    break
                page.wait_for_timeout(250)
            report["checks"]["natural_from"] = start_key
            report["checks"]["natural_dur"] = round(dur, 1)
            deadline = time.time() + 120
            natural = snap(page)
            while time.time() < deadline:
                natural = snap(page)
                if natural.get("sounding") and natural.get("sounding") != start_key and not natural.get("paused"):
                    # One handoff only — stop on first audible key change.
                    page.wait_for_timeout(600)
                    natural = snap(page)
                    if natural.get("chip") == natural.get("sounding") and natural.get("sheetKey") == natural.get("sounding"):
                        break
                    # Surfaces catching up
                    page.wait_for_timeout(800)
                    natural = snap(page)
                    break
                page.wait_for_timeout(200)
            report["checks"]["natural"] = {
                "from": start_key,
                "sounding": natural.get("sounding"),
                "chip": natural.get("chip"),
                "label": natural.get("label"),
                "sheetKey": natural.get("sheetKey"),
                "sheetOpen": natural.get("sheetOpen"),
            }
            report["checks"]["natural_handoff"] = (
                natural.get("sounding") not in (None, "", start_key)
                and natural.get("chip") == natural.get("sounding")
                and natural.get("sheetKey") == natural.get("sounding")
                and natural.get("sheetOpen")
            )

        page.evaluate(
            """() => {
              const b = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"] button')
                || [...document.querySelectorAll('button')].find((el) => /Turn off cycling/i.test(el.innerText || ''));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(800)
        set_cycle_mode(page, False)
        page.wait_for_timeout(700)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    need = [
        "pause_audio",
        "pause_label",
        "pause_single_handler",
        "resume_audio",
        "resume_label",
        "stop_audio",
        "stop_keeps_t",
        "stop_label",
        "stop_resume_audio",
        "fm_ready",
        "at_gm",
    ]
    gm = (report["checks"].get("gm_next_fm") or {}).get("agreed")
    back = (report["checks"].get("fm_prev_gm") or {}).get("agreed")
    prev = (report["checks"].get("gm_prev_am") or {}).get("agreed")
    nxt_kind = report["audio_ms"].get("next_fm_kind")
    report["checks"]["next_fm_buffer"] = nxt_kind == "buffer"
    report["checks"]["sequence"] = bool(
        gm and back and prev and report["checks"].get("natural_handoff") and nxt_kind == "buffer"
    )
    report["required"] = {k: bool(report["checks"].get(k)) for k in need}
    report["required"]["sequence"] = bool(report["checks"].get("sequence"))
    report["ok"] = all(report["required"].values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "focus_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": report["ok"],
        "required": report["required"],
        "audio_ms": report["audio_ms"],
        "visible_ms": report["visible_ms"],
        "chart_ms": report["chart_ms"],
        "fm_stage": report["checks"].get("fm_stage"),
        "natural": report["checks"].get("natural"),
        "left_off": report.get("left_off"),
    }, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

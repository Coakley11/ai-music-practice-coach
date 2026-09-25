"""Verify loops=2 natural advance (3 consecutive) + loops 1 and 1→2→1 on 8510."""
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
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui
from proof_verse_verify_8510 import (
    _read_loops_now,
    audio_snap,
    close_lead_sheet,
    configure_verse,
    expected_duration,
    goto_backing_shape,
    open_lead_sheet,
    play_and_measure,
    read_canon,
    set_cycle_mode,
    set_loops,
    snap_chart,
)
from proof_verse_verify_8510 import wait_key_change as _wait_key_change_ui


def wait_key_change(page, from_key: str, timeout_s: float) -> dict:
    """Wait until playbar sounding OR browser __kcLastSounding advances."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ui = cycle_ui(page)
        sk = str(ui.get("sounding") or "")
        try:
            browser = page.evaluate("() => String(window.__kcLastSounding || '')")
        except Exception:
            browser = ""
        for cand in (sk, browser):
            if from_key and cand and cand != from_key:
                return {
                    "ok": True,
                    "from": from_key,
                    "to": cand,
                    "waited_s": time.time() - t0,
                    "via": "ui" if cand == sk else "browser",
                }
        page.wait_for_timeout(700)
    # Fall back to stock helper result shape
    out = _wait_key_change_ui(page, from_key, 0.1)
    out["waited_s"] = time.time() - t0
    return out

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle" / "loops2_natural_advance_report.json"


def soft_off(page) -> None:
    try:
        click_playbar(page, "off")
    except Exception:
        pass
    set_cycle_mode(page, False)
    page.wait_for_timeout(900)
    close_lead_sheet(page)
    # Hard-clear parent dual-buffer identity so the next On starts a fresh cycleId.
    try:
        page.evaluate(
            """() => {
              try {
                if (window.__kcApplyCmd) {
                  window.__kcApplyCmd({enabled: false});
                }
              } catch (e) {}
              try {
                window.__kcDual = null;
                window.__kcPendingPlayingAck = null;
                window.__kcPendingPlayingAckQueue = [];
                window.__kcAckLog = [];
                window.__kcLastSounding = '';
                window.__kcEndedWatchInstalled = false;
                if (window.__kcEndedWatch) {
                  clearInterval(window.__kcEndedWatch);
                  window.__kcEndedWatch = null;
                }
                const a0 = document.getElementById('kc-buf-0');
                const a1 = document.getElementById('kc-buf-1');
                if (a0) { a0.pause(); a0.removeAttribute('src'); }
                if (a1) { a1.pause(); a1.removeAttribute('src'); }
                const root = document.getElementById('kc-persistent-root');
                if (root) root.remove();
              } catch (e2) {}
            }"""
        )
    except Exception:
        pass
    page.wait_for_timeout(400)


def dump_dual(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const pick = (a) => a ? {
            id: a.id,
            dur: Number(a.duration) || 0,
            ready: Number(a.readyState) || 0,
            paused: !!a.paused,
            ended: !!a.ended,
            src: (a.getAttribute('data-kc-url') || a.src || '').slice(-40),
            sounding: a.getAttribute('data-kc-sounding') || '',
            ct: Number(a.currentTime) || 0,
          } : null;
          return {
            enabled: !!st.enabled,
            active: st.active,
            nextUrl: (st.nextUrl || '').slice(-40),
            nextSounding: st.nextSounding || '',
            nextReady: Number(st.nextBufferReadyState || 0),
            followingUrl: (st.followingUrl || '').slice(-40),
            followingSounding: st.followingSounding || '',
            lastSounding: window.__kcLastSounding || '',
            ackLog: (window.__kcAckLog || []).slice(-6).map(x => ({
              from: x.fromKey, to: x.playingKey, gapMs: x.gapMs
            })),
            onEndedTrace: (window.__kcOnEndedTrace || []).slice(-4),
            playDiagTail: (window.__kcPlayDiag || []).slice(-8).map(x => x.ev),
            a0: pick(a0), a1: pick(a1),
            lastCmdNext: ((window.__kcLastCmd || {}).nextUrl || '').slice(-40),
            lastCmdLoopsHint: (window.__kcLastCmd || {}).passToken || '',
          };
        }"""
    )


def wait_prefetch_ready(page, exp2: float, timeout_s: float = 90.0) -> dict:
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout_s:
        last = dump_dual(page)
        idle = last.get("a0") if last.get("active") == 1 else last.get("a1")
        idle_dur = float((idle or {}).get("dur") or 0)
        if idle_dur >= exp2 * 0.75 or int(last.get("nextReady") or 0) >= 2:
            last["waited_s"] = time.time() - t0
            last["ok"] = True
            return last
        # Also accept nextUrl present with idle src even if metadata slow
        if last.get("nextUrl") and (idle or {}).get("src"):
            if int((idle or {}).get("ready") or 0) >= 2:
                last["waited_s"] = time.time() - t0
                last["ok"] = True
                return last
        page.wait_for_timeout(1500)
    last["waited_s"] = time.time() - t0
    last["ok"] = False
    return last


def run_three_loops2(page, exp2: float) -> dict:
    soft_off(page)
    if not (read_canon(page).get("has_ms") or _read_loops_now(page) > 0):
        goto_backing_shape(page)
        configure_verse(page, loops=2)
    assert set_loops(page, 2) and _read_loops_now(page) == 2
    set_cycle_mode(page, True)
    for _ in range(12):
        if cycle_ui(page).get("playbar"):
            break
        set_cycle_mode(page, True)
        page.wait_for_timeout(600)
    open_lead_sheet(page)
    measured = play_and_measure(page, cycling=True, timeout=240, min_duration=exp2 * 0.75)
    # Do NOT click Play again — that can pause and stall natural advance.
    start = str(cycle_ui(page).get("sounding") or "")
    pref = wait_prefetch_ready(page, exp2, 100.0)
    transitions = []
    cur = start
    for i in range(3):
        before_ack = page.evaluate("() => (window.__kcAckLog || []).length")
        t0 = time.time()
        ch = wait_key_change(page, cur, max(200.0, exp2 * 1.6 + 60))
        waited = float(ch.get("waited_s") or (time.time() - t0))
        open_lead_sheet(page)
        page.wait_for_timeout(800)
        chart = snap_chart(page)
        dual = dump_dual(page)
        acks = dual.get("ackLog") or []
        new_acks = page.evaluate(
            """(n) => (window.__kcAckLog || []).slice(n).map(x => ({
              from: x.fromKey, to: x.playingKey, gapMs: x.gapMs
            }))""",
            before_ack,
        )
        gap_ms = None
        if new_acks:
            gap_ms = new_acks[-1].get("gapMs")
        elif acks:
            gap_ms = acks[-1].get("gapMs")
        row = {
            "i": i,
            "from": cur,
            "to": ch.get("to"),
            "ok": bool(ch.get("ok")),
            "pass_duration_s": waited,  # wall time from prior key → new key (includes gap)
            "transition_gap_ms": gap_ms,
            "chart_key": chart.get("key_pill"),
            "form_bars": chart.get("form_bars_text"),
            "max_bar": chart.get("max_bar"),
            "has_lead_sheet": chart.get("has_lead_sheet"),
            "no_raw": (not chart.get("has_raw_grid"))
            and (not chart.get("has_raw_playback_token_in_cells")),
            "acks": new_acks,
            "dual_nextReady": dual.get("nextReady"),
            "dual_nextUrl": dual.get("nextUrl"),
        }
        # Pass duration should be ~exp2; gap reported separately.
        row["pass_ok"] = bool(
            ch.get("ok")
            and waited >= exp2 * 0.72
            and waited <= exp2 * 1.55 + 45
        )
        transitions.append(row)
        print(
            f"L2 T{i}: {cur}->{ch.get('to')} waited={waited:.1f}s gap={gap_ms} "
            f"sheet={chart.get('key_pill')} nextReady={dual.get('nextReady')}",
            flush=True,
        )
        if not ch.get("ok"):
            break
        cur = str(ch.get("to") or "")
        # Give prefetch a moment to arm +2 for the next handoff
        wait_prefetch_ready(page, exp2, 45.0)
    return {
        "start": start,
        "duration_s": measured["duration_s"],
        "prefetch": pref,
        "transitions": transitions,
        "ok": (
            measured["duration_s"] >= exp2 * 0.7
            and len(transitions) == 3
            and all(t.get("ok") and t.get("pass_ok") for t in transitions)
            and all(t.get("has_lead_sheet") and t.get("no_raw") for t in transitions)
            and all(int(t.get("max_bar") or 0) >= 5 for t in transitions)
        ),
    }


def main() -> int:
    report: dict = {"ok": False, "short_unset": True}
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4500)
        assert goto_backing_shape(page)
        cfg = configure_verse(page, loops=1)
        bpm = float((cfg.get("canon") or read_canon(page)).get("bpm_slider") or 96)
        exp1 = expected_duration(16, bpm, 1)
        exp2 = expected_duration(16, bpm, 2)
        report["exp1"] = exp1
        report["exp2"] = exp2
        report["bpm"] = bpm
        print(f"exp1={exp1:.1f} exp2={exp2:.1f} bpm={bpm}", flush=True)

        # --- loops=1 sanity ---
        set_cycle_mode(page, True)
        open_lead_sheet(page)
        on1 = play_and_measure(page, cycling=True, timeout=120, min_duration=exp1 * 0.75)
        start1 = str(cycle_ui(page).get("sounding") or "")
        pref1 = wait_prefetch_ready(page, exp1, 40.0)
        ch1 = wait_key_change(page, start1, max(100.0, exp1 * 1.7 + 25))
        open_lead_sheet(page)
        chart1 = snap_chart(page)
        report["loops1"] = {
            "dur": on1["duration_s"],
            "start": start1,
            "prefetch": {
                "ok": pref1.get("ok"),
                "nextReady": pref1.get("nextReady"),
                "nextUrl": pref1.get("nextUrl"),
            },
            "change": ch1,
            "chart": {
                "key_pill": chart1.get("key_pill"),
                "form_bars_text": chart1.get("form_bars_text"),
                "max_bar": chart1.get("max_bar"),
                "has_lead_sheet": chart1.get("has_lead_sheet"),
            },
            "ok": bool(
                on1["duration_s"] >= exp1 * 0.7
                and ch1.get("ok")
                and float(ch1.get("waited_s") or 0) >= exp1 * 0.72
                and chart1.get("has_lead_sheet")
            ),
        }
        print("loops1", report["loops1"]["ok"], report["loops1"]["dur"], ch1, flush=True)

        # Full page reload between loops1 and loops2 so dual-buffer / handoff
        # component cannot keep a prior cycleId or setComponentValue.
        soft_off(page)
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(3500)
        assert goto_backing_shape(page)
        configure_verse(page, loops=2)

        # --- loops=2 three consecutive natural transitions ---
        report["loops2_x3"] = run_three_loops2(page, exp2)
        print("loops2_x3", report["loops2_x3"]["ok"], flush=True)

        # --- loops 1→2→1 stale/cache ---
        soft_off(page)
        if not (read_canon(page).get("has_ms") or _read_loops_now(page) > 0):
            goto_backing_shape(page)
            configure_verse(page, loops=1)
        assert set_loops(page, 1) and _read_loops_now(page) == 1
        set_cycle_mode(page, True)
        open_lead_sheet(page)
        a = play_and_measure(page, cycling=True, timeout=120, min_duration=exp1 * 0.75)
        soft_off(page)
        assert set_loops(page, 2) and _read_loops_now(page) == 2
        set_cycle_mode(page, True)
        open_lead_sheet(page)
        b2 = play_and_measure(page, cycling=True, timeout=240, min_duration=exp2 * 0.75)
        soft_off(page)
        assert set_loops(page, 1) and _read_loops_now(page) == 1
        set_cycle_mode(page, True)
        open_lead_sheet(page)
        c = play_and_measure(page, cycling=True, timeout=120, min_duration=exp1 * 0.75)
        report["loops_toggle"] = {
            "d1": a["duration_s"],
            "d2": b2["duration_s"],
            "d1_again": c["duration_s"],
            "ok": (
                a["duration_s"] >= exp1 * 0.7
                and b2["duration_s"] >= exp2 * 0.7
                and c["duration_s"] >= exp1 * 0.7
                and abs(c["duration_s"] - a["duration_s"]) <= 3.0
                and b2["duration_s"] >= a["duration_s"] * 1.6
            ),
        }
        print("toggle", report["loops_toggle"], flush=True)

        soft_off(page)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        report["ok"] = bool(
            report["loops1"]["ok"]
            and report["loops2_x3"]["ok"]
            and report["loops_toggle"]["ok"]
            and report["left_off"]
        )
        OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"ok": report["ok"], "left_off": report["left_off"]}, indent=2), flush=True)
        b.close()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

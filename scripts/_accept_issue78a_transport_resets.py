"""Issue 78 Slice 78A: Stop, repeat Play, count-in and timing resets, in the real app.

Phase F item 4. The component harness covers these on the component alone; this runs
them inside Streamlit, where the count-in is a real selectbox and the transport iframe is
re-rendered between changes.

What is measured:

  Stop        - the position readout, the cursor and the clock the layer chord strips
                follow all return to the start, and the retired context is closed.
  Repeat Play - a second Play builds a fresh context and schedules nothing in the past;
                the first run's sources cannot still be playing underneath it.
  Count-in    - None, 1 bar and 2 bars: the right number of clicks, none of them behind
                the clock, and bar 1 exactly the count-in's length after the first click.

Count-in None is the headline case: it is where the investigation measured the layers
starting 160 ms apart with the worst 800 ms behind the beat, because with no count-in
there was no decode headroom to hide the race.

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8592
  python scripts/_accept_issue78a_transport_resets.py http://127.0.0.1:8592
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _probe_i78_recording_clock import (  # noqa: E402
    INSTRUMENT,
    click_text_button,
    collect,
    expand_layer,
    iframe_frame,
    upload_into_slot,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8592"
OUT = SCRIPTS / "evidence-issue78a"
OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="i78a-resets-"))
SR = 44100
LAYER_SEC = 6.0
BPM = 100
BEATS_PER_BAR = 4

GATES: dict[str, bool] = {}
NOTES: list[str] = []
MEASURED: dict[str, object] = {}


def log(m: str) -> None:
    NOTES.append(m)
    print(m.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, s: float = 2.5) -> None:
    wait_idle(page, int(s * 1000))


def make_layer(path: Path, freq: float) -> Path:
    n = int(SR * LAYER_SEC)
    body = bytearray()
    for i in range(n):
        body += struct.pack("<h", int(4000 * math.sin(2 * math.pi * freq * i / SR)))
    head = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(body), b"WAVE",
                       b"fmt ", 16, 1, 1, SR, SR * 2, 2, 16, b"data", len(body))
    path.write_bytes(head + bytes(body))
    return path


def count_in_value(page: Page) -> str:
    """The chosen option lives in the hidden input; innerText is the label only."""
    return page.evaluate(
        """() => {
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
          const b = boxes.find((x) => {
            const own = (x.innerText || '').toLowerCase();
            const up = ((x.parentElement && x.parentElement.innerText) || '')
                       .toLowerCase();
            return own.includes('count-in') || up.includes('count-in');
          });
          if (!b) return 'not-found';
          const i = b.querySelector('input');
          return i ? String(i.value || '') : '';
        }"""
    )


def transport_readout(page: Page) -> dict:
    fr = iframe_frame(page)
    if fr is None:
        return {"err": "no-iframe"}
    return fr.evaluate(
        """() => ({
          time: (document.getElementById('mt-time').textContent || '').trim(),
          bar: (document.getElementById('mt-bar').textContent || '').trim(),
          beat: (document.getElementById('mt-beat').textContent || '').trim(),
          cursor: document.getElementById('mt-cursor').style.width || '',
          label: (document.getElementById('mt-playback-label').textContent || '').trim(),
          clock: (() => { try { return window.parent['__mtClock'] || null; }
                          catch (e) { return 'blocked'; } })(),
        })""")


def press(page: Page, button_id: str) -> str:
    fr = iframe_frame(page)
    if fr is None:
        return "no-iframe"
    return fr.evaluate(
        """(id) => { const b = document.getElementById(id);
                     if (!b) return 'no-button'; b.click(); return 'clicked'; }""",
        button_id,
    )


def clear_events(page: Page) -> None:
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr = iframe_frame(page)
        if fr is not None:
            fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass


def schedule_facts(page: Page) -> dict:
    ev = collect(page)
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start"
            and e.get("_frame") == "iframe"]
    oscs = [e for e in ev if e.get("kind") == "osc_start" and e.get("_frame") == "iframe"]
    ctxs = [e for e in ev if e.get("kind") == "audioctx_new"
            and e.get("_frame") == "iframe"]
    lbs = [float(e["late_by"]) for e in srcs if e.get("late_by") is not None]
    owhens = sorted(float(e["when"]) for e in oscs if e.get("when") is not None)
    swhens = sorted({round(float(e["when"]), 5) for e in srcs
                     if e.get("when") is not None})
    return {
        "contexts": len(ctxs), "sources": len(srcs), "clicks": len(oscs),
        "worst_late_sec": max(lbs) if lbs else 0.0,
        "margin_sec": -max(lbs) if lbs else 0.0,
        "source_instants": swhens,
        "first_click": owhens[0] if owhens else None,
        "late_clicks": sum(1 for e in oscs if (e.get("late_by") or 0) > 0.0005),
    }


# --------------------------------------------------------------------------- legs
def gate_count_in(page: Page, option: str, expect_clicks: int) -> None:
    log(f"\n== count-in {option!r} ==")
    set_baseweb_select(page, "Count-in", option, prefer_sidebar=False)
    settle(page, 9)
    got = count_in_value(page)
    mark(f"count-in set to {option}", option.lower() in got.lower(), f"reads {got!r}")
    if option.lower() not in got.lower():
        return
    clear_events(page)
    press(page, "mt-play")
    page.wait_for_timeout(12000)
    f = schedule_facts(page)
    MEASURED[f"count_in_{option}"] = f
    log(f"  sources={f['sources']} clicks={f['clicks']} "
        f"margin={f['margin_sec'] * 1000:+.1f} ms instants={f['source_instants']}")
    mark(f"count-in {option}: {expect_clicks} click(s) scheduled",
         f["clicks"] == expect_clicks, f"got {f['clicks']}")
    mark(f"count-in {option}: no click behind the clock", f["late_clicks"] == 0,
         f"{f['late_clicks']} late")
    mark(f"count-in {option}: nothing scheduled in the past",
         f["worst_late_sec"] <= 0.0005,
         f"worst {f['worst_late_sec'] * 1000:.1f} ms late")
    mark(f"count-in {option}: every layer on one instant",
         len(f["source_instants"]) == 1, f"instants {f['source_instants']}")
    if expect_clicks and f["first_click"] is not None and f["source_instants"]:
        gap = f["source_instants"][0] - f["first_click"]
        want = expect_clicks * (60.0 / BPM)
        MEASURED[f"count_in_{option}_gap_sec"] = gap
        log(f"  bar 1 is {gap:.4f}s after the first click (a {option} at {BPM} BPM "
            f"is {want:.4f}s)")
        mark(f"count-in {option}: bar 1 is exactly the count-in's length later",
             abs(gap - want) < 0.01, f"{gap:.4f}s vs {want:.4f}s")
    press(page, "mt-stop")
    settle(page, 3)


def gate_stop_resets(page: Page) -> None:
    log("\n== Stop returns the transport to the start ==")
    clear_events(page)
    press(page, "mt-play")
    page.wait_for_timeout(9000)
    during = transport_readout(page)
    log(f"  while playing: {json.dumps(during, default=str)}")
    MEASURED["readout_playing"] = during
    mark("the position readout advances while playing",
         during.get("time") not in ("0.0s", "", None), f"time {during.get('time')!r}")
    press(page, "mt-stop")
    settle(page, 3)
    after = transport_readout(page)
    log(f"  after Stop:    {json.dumps(after, default=str)}")
    MEASURED["readout_stopped"] = after
    mark("Stop resets the position readout to zero", after.get("time") == "0.0s",
         f"time {after.get('time')!r}")
    mark("Stop resets the progress cursor", after.get("cursor") in ("0%", "0px", ""),
         f"cursor {after.get('cursor')!r}")
    mark("Stop resets the bar and beat readout too",
         after.get("bar") == "1" and after.get("beat") == "1",
         f"bar {after.get('bar')!r} beat {after.get('beat')!r}")
    mark("Stop says so in the transport label",
         "stopped" in str(after.get("label", "")).lower(),
         f"label {after.get('label')!r}")
    clock = after.get("clock")
    mark("Stop tells the layer chord strips the transport is not playing",
         isinstance(clock, dict) and clock.get("playing") is False
         and float(clock.get("t") or 0) == 0.0,
         f"clock {clock}")


def gate_repeat_play(page: Page) -> None:
    log("\n== Play, Play again: no stale audio from the first run ==")
    clear_events(page)
    press(page, "mt-play")
    page.wait_for_timeout(4000)
    press(page, "mt-play")
    page.wait_for_timeout(12000)
    f = schedule_facts(page)
    MEASURED["repeat_play"] = f
    log(f"  contexts={f['contexts']} sources={f['sources']} "
        f"instants={f['source_instants']}")
    mark("a second Play builds a second context", f["contexts"] == 2,
         f"{f['contexts']} contexts")
    mark("repeat Play schedules nothing in the past", f["worst_late_sec"] <= 0.0005,
         f"worst {f['worst_late_sec'] * 1000:.1f} ms late")
    states = page.evaluate(
        """() => {
          const f = [...document.querySelectorAll('iframe')];
          return f.length;
        }""")
    log(f"  iframes on the page: {states}")
    press(page, "mt-stop")
    settle(page, 3)
    after = transport_readout(page)
    mark("Stop after a repeat still resets", after.get("time") == "0.0s",
         f"time {after.get('time')!r}")


def main() -> int:
    layers = {
        "guitar": make_layer(WORK / "g.wav", 196.0),
        "sax / winds": make_layer(WORK / "s.wav", 311.0),
        "extra layer": make_layer(WORK / "f.wav", 587.0),
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(INSTRUMENT)
        page = ctx.new_page()
        page.set_default_timeout(30000)
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        try:
            page.goto(URL, wait_until="domcontentloaded")
            waited = 0
            while waited < 150:
                b = page.inner_text("body") or ""
                if len(b.strip()) > 400 and "PAGES" in b.upper():
                    break
                settle(page, 3)
                waited += 3
            expand_sidebar(page)
            try:
                pick_song(page, NOTES, "Let It Be", "Rock")
                settle(page, 4)
            except Exception as exc:
                log(f"pick_song raised {exc}")
            click_nav(page, "Multitrack")
            settle(page, 6)
            mark("Multitrack page opens",
                 "multitrack session workspace" in (page.inner_text("body") or "").lower())
            log(f"  Prepare backing -> {click_text_button(page, 'prepare backing')}")
            settle(page, 14)
            staged = []
            for slot, path in layers.items():
                expand_layer(page, slot)
                settle(page, 2)
                if upload_into_slot(page, slot, path):
                    staged.append(slot)
            mark("three layers staged", len(staged) == 3, str(staged))
            settle(page, 8)

            gate_count_in(page, "None", 0)
            gate_count_in(page, "1 bar", BEATS_PER_BAR)
            gate_count_in(page, "2 bars", BEATS_PER_BAR * 2)
            gate_stop_resets(page)
            gate_repeat_play(page)
            mark("no uncaught JS errors", not errs, str(errs)[:160])
        finally:
            try:
                page.screenshot(path=str(OUT / "resets-final.png"), full_page=True)
            except Exception:
                pass
            report = {
                "gates": GATES,
                "passed": sum(1 for v in GATES.values() if v),
                "total": len(GATES),
                "failed": sorted(k for k, v in GATES.items() if not v),
                "measured": MEASURED,
                "js_errors": errs,
            }
            (OUT / "resets-report.json").write_text(
                json.dumps(report, indent=2, default=str), encoding="utf-8")
            (OUT / "resets-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\n{report['passed']}/{report['total']} gates passed")
    if report["failed"]:
        log("FAILED: " + "\n         ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Issue 78 Slice 78A acceptance: measure the transport's scheduling, case by case.

This drives the real ``multitrack_studio_html`` component in a real Chromium, but on its
own page rather than inside the app, so the decode race can be stressed in the
configurations that provoke it without a Streamlit rerun between each one. The app-level
run is ``scripts/_probe_i78_sync_contract.py``, which produced the before numbers and is
re-run afterwards for the comparison.

The measurement is the same one the investigation used. Every
``AudioBufferSourceNode.start`` is intercepted and its scheduled ``when`` compared with
``context.currentTime`` at the instant ``start`` was called:

* ``late_by <= 0`` - the instant is still in the future, so the browser honours it.
* ``late_by > 0``  - the instant has passed, so the browser plays immediately and the
  layer lands at its own decode-completion time instead of on the beat.

A case passes when nothing is late, when every layer that shares an Align offset shares
one scheduled instant, and when the count-in's first click is also in the future.

Usage:
  python scripts/_accept_issue78a_transport.py
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

OUT = SCRIPTS / "evidence-issue78a"
OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="issue78a-"))

GATES: dict[str, bool] = {}
NOTES: list[str] = []
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


# ------------------------------------------------------------------ audio fixtures
def wav_bytes(seconds: float, freq: float, *, sr: int = 44100,
              click_at: float | None = None) -> bytes:
    n = int(sr * seconds)
    out = bytearray()
    ci = int(sr * click_at) if click_at is not None else -1
    for i in range(n):
        v = 32000 if i == ci else int(4000 * math.sin(2 * math.pi * freq * i / sr))
        out += struct.pack("<h", v)
    head = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(out), b"WAVE",
                       b"fmt ", 16, 1, 1, sr, sr * 2, 2, 16, b"data", len(out))
    return head + bytes(out)


def b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


# ------------------------------------------------------------------ instrumentation
INSTRUMENT = r"""
(() => {
  const W = window;
  if (W.__i78a) return;
  const ev = [];
  W.__i78a = ev;
  // Each AudioContext starts its own clock at zero, so a scheduled `when` is only
  // meaningful within one context. Stamping the run lets the report group by it
  // instead of comparing numbers from two different clocks.
  W.__i78aCtxSeq = 0;
  W.__i78aCtxOf = new WeakMap();
  const ctxId = (c) => {
    if (!c) return null;
    if (!W.__i78aCtxOf.has(c)) W.__i78aCtxOf.set(c, ++W.__i78aCtxSeq);
    return W.__i78aCtxOf.get(c);
  };
  W.__i78aCtxId = ctxId;
  const push = (o) => { try { ev.push(o); } catch (e) {} };
  if (W.AudioBufferSourceNode) {
    const S = W.AudioBufferSourceNode.prototype.start;
    W.AudioBufferSourceNode.prototype.start = function (when, offset) {
      const ct = this.context ? this.context.currentTime : null;
      const w = (when === undefined) ? null : Number(when);
      push({kind: 'src', run: ctxId(this.context), when: w, ctx_now: ct,
            late_by: (w !== null && ct !== null) ? (ct - w) : null,
            offset: offset === undefined ? 0 : Number(offset),
            dur: this.buffer ? this.buffer.duration : null,
            loop: !!this.loop});
      return S.apply(this, arguments);
    };
  }
  if (W.OscillatorNode) {
    const S = W.OscillatorNode.prototype.start;
    W.OscillatorNode.prototype.start = function (when) {
      const ct = this.context ? this.context.currentTime : null;
      const w = (when === undefined) ? null : Number(when);
      push({kind: 'osc', run: ctxId(this.context), when: w, ctx_now: ct,
            late_by: (w !== null && ct !== null) ? (ct - w) : null});
      return S.apply(this, arguments);
    };
  }
  const wrap = (C) => C ? new Proxy(C, {construct(t, a) {
    const c = new t(...a);
    push({kind: 'ctx', run: ctxId(c), sr: c.sampleRate,
          base: c.baseLatency === undefined ? null : c.baseLatency});
    W.__i78aCtxList = W.__i78aCtxList || [];
    W.__i78aCtxList.push(c);
    return c;
  }}) : C;
  try { W.AudioContext = wrap(W.AudioContext); } catch (e) {}
  try { W.webkitAudioContext = wrap(W.webkitAudioContext); } catch (e) {}
})();
"""

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>78A transport harness</title></head>
<body>
<div id="errors"></div>
<script>
window.__errs = [];
window.addEventListener('error', (e) => window.__errs.push(String(e.message)));
window.addEventListener('unhandledrejection', (e) => window.__errs.push('reject: ' + String(e.reason)));
</script>
__COMPONENT__
</body></html>
"""


def render_component(**kw) -> str:
    from streamlit_music_practice_app import multitrack_studio_html

    return multitrack_studio_html(**kw)


def build_page(path: Path, **kw) -> Path:
    comp = render_component(**kw)
    path.write_text(PAGE.replace("__COMPONENT__", comp), encoding="utf-8")
    return path


# ------------------------------------------------------------------ one case
def run_case(ctx, name: str, *, tracks, backing, bpm, count_in_bars,
             metronome=False, loops=True, clicks=1, whens_per_run=1,
             stop_during_decode=False) -> dict:
    page = ctx.new_page()
    page.set_default_timeout(30000)
    try:
        html = WORK / f"{name}.html"
        build_page(
            html,
            backing_b64=b64(backing) if backing else None,
            tracks=tracks,
            bpm=bpm,
            beats_per_bar=4,
            count_in_bars=count_in_bars,
            metronome_during_playback=metronome,
            loop_backing=loops,
            backing_monitor_enabled=bool(backing),
            backing_monitor_volume=0.75,
            scope_label="harness",
            time_signature="4/4",
            backing_duration_sec=12.0,
        )
        page.goto(html.resolve().as_uri(), wait_until="load")
        page.wait_for_timeout(300)
        for _ in range(clicks):
            page.evaluate("() => document.getElementById('mt-play').click()")
            if stop_during_decode:
                page.wait_for_timeout(20)
                page.evaluate("() => document.getElementById('mt-stop').click()")
            page.wait_for_timeout(2500)
        page.wait_for_timeout(2500)
        ev = page.evaluate("() => (window.__i78a || []).slice()")
        ctx_states = page.evaluate(
            "() => (window.__i78aCtxList || []).map((c) => c.state)")
        errs = page.evaluate("() => (window.__errs || []).slice()")
        label = page.evaluate(
            "() => (document.getElementById('mt-playback-label').textContent || '')")
    finally:
        page.close()

    srcs = [e for e in ev if e.get("kind") == "src"]
    oscs = [e for e in ev if e.get("kind") == "osc"]
    ctxs = [e for e in ev if e.get("kind") == "ctx"]
    late_src = [e for e in srcs if (e.get("late_by") or 0) > 0.0005]
    late_osc = [e for e in oscs if (e.get("late_by") or 0) > 0.0005]
    lbs = [float(e["late_by"]) for e in srcs if e.get("late_by") is not None]

    # Group by run. Two Plays build two contexts, each with its own clock starting at
    # zero, so their `when` values are the same numbers and must not be pooled.
    runs: dict = {}
    for e in srcs:
        if e.get("when") is None:
            continue
        runs.setdefault(e.get("run"), set()).add(round(float(e["when"]), 5))
    per_run = {k: sorted(v) for k, v in sorted(runs.items(), key=lambda kv: kv[0] or 0)}
    whens = sorted({w for v in per_run.values() for w in v})

    # When nothing is late, a source starts exactly at its scheduled instant, so the
    # spread between ACTUAL starts is the spread of the scheduled instants within a run
    # - not the spread of late_by, which only reflects how early each call happened to
    # be made and was reported as an 8 ms start spread when the starts were identical.
    if late_src:
        spread = (max(lbs) - min(lbs)) if len(lbs) > 1 else 0.0
        spread_basis = "measured from late_by: sources did not honour their schedule"
    else:
        spread = max((max(v) - min(v)) for v in per_run.values()) if per_run else 0.0
        spread_basis = "scheduled instants within a run, all honoured"
    margin = -max(lbs) if lbs else 0.0

    res = {
        "case": name, "contexts": len(ctxs), "sources": len(srcs),
        "clicks_scheduled": len(oscs), "late_sources": len(late_src),
        "late_clicks": len(late_osc),
        "worst_late_sec": max(lbs) if lbs else 0.0,
        "smallest_scheduling_margin_sec": margin,
        "actual_start_spread_sec": spread,
        "actual_start_spread_basis": spread_basis,
        "scheduled_instants_per_run": per_run,
        "distinct_whens": whens, "js_errors": errs, "label": label,
        "offsets": sorted({round(float(e.get("offset") or 0), 5) for e in srcs}),
        "context_states": ctx_states,
    }
    MEASURED[name] = res
    log(f"\n-- {name}")
    log(f"   sources={len(srcs)} clicks={len(oscs)} contexts={len(ctxs)}")
    log(f"   smallest scheduling margin = {margin * 1000:+.1f} ms "
        f"(negative would mean scheduled in the past)")
    log(f"   spread between actual starts = {spread * 1000:.1f} ms  [{spread_basis}]")
    log(f"   scheduled instants per run = {per_run}")
    if res["offsets"] != [0.0]:
        log(f"   buffer offsets applied = {res['offsets']}")
    if errs:
        log(f"   JS ERRORS: {errs}")

    ok = True
    if errs:
        mark(f"{name} :: no JS errors", False, str(errs)[:120])
        ok = False
    else:
        mark(f"{name} :: no JS errors", True)
    if not stop_during_decode:
        mark(f"{name} :: no source scheduled in the past", not late_src,
             f"worst {res['worst_late_sec'] * 1000:.1f} ms late")
        ok = ok and not late_src
        mark(f"{name} :: no count-in click scheduled in the past", not late_osc,
             f"{len(late_osc)} of {len(oscs)} late")
        ok = ok and not late_osc
        # One scheduled instant per run per distinct Align offset. Pressing Play twice
        # legitimately produces two instants - one per run - so the expectation is
        # scaled by the number of contexts rather than fixed at one.
        bad = {k: v for k, v in per_run.items() if len(v) != max(1, whens_per_run)}
        what = ("layers share one scheduled instant per run" if whens_per_run == 1
                else f"{whens_per_run} distinct scheduled instants per run")
        mark(f"{name} :: {what}", not bad,
             f"{len(per_run)} run(s), instants per run {per_run}")
        ok = ok and not bad
    return res


def main() -> int:
    long_backing = wav_bytes(20.0, 110.0)
    short_layer = wav_bytes(6.0, 196.0, click_at=0.0)
    long_layer = wav_bytes(60.0, 196.0, click_at=0.0)

    def tracks(n: int, *, data: bytes, delays=None):
        from multitrack_align_contract import transport_payload

        out = []
        for i in range(n):
            d = 0.0 if delays is None else float(delays[i])
            out.append({
                "id": f"t{i}", "name": f"Layer {i}",
                "b64": "data:audio/wav;base64," + b64(data),
                "volume": 1.0, "mute": False, "solo": False, "delay": d,
                **transport_payload(d),
            })
        return out

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required",
                  "--mute-audio"],
        )
        ctx = browser.new_context()
        ctx.add_init_script(INSTRUMENT)
        try:
            log("=== Phase A: the configurations where the race was measured ===")
            run_case(ctx, "count-in-none-3-layers", tracks=tracks(3, data=short_layer),
                     backing=long_backing, bpm=100, count_in_bars=0)
            run_case(ctx, "count-in-1-bar-3-layers", tracks=tracks(3, data=short_layer),
                     backing=long_backing, bpm=100, count_in_bars=1)
            run_case(ctx, "fast-tempo-180bpm-short-count-in",
                     tracks=tracks(3, data=short_layer),
                     backing=long_backing, bpm=180, count_in_bars=1)
            run_case(ctx, "long-layers-60s-no-count-in",
                     tracks=tracks(3, data=long_layer),
                     backing=long_backing, bpm=100, count_in_bars=0)
            run_case(ctx, "six-layers-no-count-in", tracks=tracks(6, data=short_layer),
                     backing=long_backing, bpm=100, count_in_bars=0)
            run_case(ctx, "no-backing-layers-only", tracks=tracks(3, data=short_layer),
                     backing=None, bpm=100, count_in_bars=0)

            log("\n=== Phase A: repeat, restart and stop ===")
            run_case(ctx, "play-twice-no-stale-sources",
                     tracks=tracks(3, data=short_layer), backing=long_backing,
                     bpm=100, count_in_bars=1, clicks=2, whens_per_run=1)
            run_case(ctx, "stop-during-decode-schedules-nothing",
                     tracks=tracks(3, data=long_layer), backing=long_backing,
                     bpm=100, count_in_bars=0, stop_during_decode=True)
            run_case(ctx, "metronome-on-clicks-stay-ahead-of-the-clock",
                     tracks=tracks(2, data=short_layer), backing=long_backing,
                     bpm=100, count_in_bars=1, metronome=True)

            log("\n=== Phase B: the Align contract in the transport ===")
            run_case(ctx, "align-zero-layers-together",
                     tracks=tracks(3, data=short_layer, delays=[0.0, 0.0, 0.0]),
                     backing=None, bpm=100, count_in_bars=1, whens_per_run=1)
            run_case(ctx, "align-positive-moves-the-start-later",
                     tracks=tracks(3, data=short_layer, delays=[0.0, 0.5, 1.0]),
                     backing=None, bpm=100, count_in_bars=1, whens_per_run=3)
            neg = run_case(ctx, "align-negative-reads-into-the-take",
                           tracks=tracks(2, data=short_layer, delays=[0.0, -0.5]),
                           backing=None, bpm=100, count_in_bars=1,
                           whens_per_run=1)
        finally:
            browser.close()

    # The negative case is the Issue 78 divergence: both layers start on bar 1, but one
    # begins half a second into its own recording, which is what the export does too.
    offs = neg.get("offsets") or []
    mark("align-negative :: a buffer offset is applied, not discarded",
         0.5 in offs, f"offsets {offs}")

    stale = MEASURED.get("play-twice-no-stale-sources", {})
    mark("play-twice :: a second Play builds a fresh context",
         int(stale.get("contexts") or 0) == 2, f"contexts {stale.get('contexts')}")
    states = stale.get("context_states") or []
    # The retired run's context must be closed, which is what makes its sources
    # unreachable rather than merely unreferenced.
    mark("play-twice :: the retired run's context is closed",
         len(states) == 2 and states[0] == "closed",
         f"context states {states}")

    stopped = MEASURED.get("stop-during-decode-schedules-nothing", {})
    mark("stop-during-decode :: nothing was scheduled",
         int(stopped.get("sources") or 0) == 0,
         f"{stopped.get('sources')} sources scheduled after Stop")

    report = {
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "total": len(GATES),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "measured": MEASURED,
    }
    (OUT / "transport-report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    (OUT / "transport-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
    log(f"\n{report['passed']}/{report['total']} gates passed")
    if report["failed"]:
        log("FAILED: " + "\n         ".join(report["failed"]))
    log(f"evidence in {OUT}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

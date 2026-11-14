"""Issue 78 read-only probe 3: the synchronization contract, measured.

Probe 1 measured the transport clock with a one-bar count-in and found every layer
scheduled on time with about 1.8 s of headroom. That headroom is the only thing keeping
the transport aligned, because ``playSession`` fixes ``musicStart`` from
``audioCtx.currentTime`` *before* it awaits a single ``decodeAudioData``. This probe
measures what happens when that headroom is gone, which the UI can produce on its own:

  LEG E  Count-in = "None".  ``musicStart`` then equals the instant Play was pressed, so
         every ``start(musicStart)`` call is issued after the decode that precedes it and
         lands in the past. Measures how far behind each layer actually begins, and the
         spread between the first and last - which is how far apart the layers sound. Q4

  LEG F  Record, then Play, then Stop, with no rerun in between: the wall-clock distance
         from ``MediaRecorder.start`` to the transport's musical beat 1. Q1/Q3

  LEG H  Align timing set negative on one layer.  The transport computes
         ``musicStart + Math.max(0, track.delay)``, so a negative align cannot move a
         layer earlier in the preview, while the export mixer does ``y = y[-ds:]`` and
         removes that much from the front of the take. Measures the preview half. Q6

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8590
  python scripts/_probe_i78_sync_contract.py http://127.0.0.1:8590
"""

from __future__ import annotations

import json
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
    fmt,
    iframe_frame,
    make_wav,
    upload_into_slot,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8590"
OUT = SCRIPTS / "evidence-issue78"
OUT.mkdir(parents=True, exist_ok=True)

NOTES: list[str] = []
FINDINGS: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, seconds: float = 2.5) -> None:
    wait_idle(page, int(seconds * 1000))


def low(s: str) -> str:
    return (s or "").lower()


def boot(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    waited = 0
    while waited < 120:
        body = page.inner_text("body") or ""
        if len(body.strip()) > 400 and "PAGES" in body.upper():
            return True
        settle(page, 3)
        waited += 3
    return False


def goto_multitrack(page: Page) -> bool:
    if "multitrack session workspace" in low(page.inner_text("body") or ""):
        return True
    click_nav(page, "Multitrack")
    settle(page, 5)
    return "multitrack session workspace" in low(page.inner_text("body") or "")


def selectbox_value(page: Page, label: str) -> str:
    """The option a selectbox is showing, not its label.

    A Streamlit selectbox renders its label and its chosen option in the same element,
    so reading ``innerText`` returns both. The option is the last non-empty line. The
    earlier probe read the whole string, compared it against the option and concluded the
    control had not moved when in fact it had.
    """
    return page.evaluate(
        """(label) => {
          const want = label.toLowerCase();
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
          // The chosen option is the hidden input's value. The container's innerText is
          // the LABEL only, which an earlier reader returned - so it compared "Count-in"
          // against "None", reported the control had not moved, and bailed out of a leg
          // whose control it had in fact already changed.
          const b = boxes.find((x) => {
            const own = (x.innerText || '').toLowerCase();
            const up = ((x.parentElement && x.parentElement.innerText) || '')
                       .toLowerCase();
            return own.includes(want) || up.includes(want);
          });
          if (!b) return 'not-found';
          const inp = b.querySelector('input');
          return inp ? String(inp.value || '') : '';
        }""",
        label,
    )


def set_slider(page: Page, slot: str, label: str, target: float) -> str:
    """Drive one of this layer's sliders with the keyboard, then read it back."""
    return page.evaluate(
        """([slot, label, target]) => {
          const s = slot.toLowerCase(), l = label.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          if (!el) return 'layer-not-found';
          const sliders = [...el.querySelectorAll('[data-testid="stSlider"]')];
          const sl = sliders.find((x) => (x.innerText || '').toLowerCase().includes(l));
          if (!sl) return 'slider-not-found';
          const thumb = sl.querySelector('[role="slider"]');
          if (!thumb) return 'thumb-not-found';
          thumb.scrollIntoView({block: 'center'});
          thumb.focus();
          return 'focused:' + (thumb.getAttribute('aria-valuenow') || '?');
        }""",
        [slot, label, target],
    )


def slider_value(page: Page, slot: str, label: str) -> str:
    return page.evaluate(
        """([slot, label]) => {
          const s = slot.toLowerCase(), l = label.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          if (!el) return 'layer-not-found';
          const sliders = [...el.querySelectorAll('[data-testid="stSlider"]')];
          const sl = sliders.find((x) => (x.innerText || '').toLowerCase().includes(l));
          if (!sl) return 'slider-not-found';
          const thumb = sl.querySelector('[role="slider"]');
          return thumb ? String(thumb.getAttribute('aria-valuenow')) : 'no-thumb';
        }""",
        [slot, label],
    )


def audio_input_button(page: Page, slot: str, which: str) -> str:
    return page.evaluate(
        """([slot, which]) => {
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          const scope = el || document;
          const rec = scope.querySelector('[data-testid="stAudioInput"]');
          if (!rec) return 'no-widget';
          const btns = [...rec.querySelectorAll('button')];
          const want = which.toLowerCase();
          let b = btns.find((x) => {
            const t = ((x.getAttribute('aria-label') || '') + ' '
                       + (x.innerText || '')).toLowerCase();
            return t.includes(want);
          });
          if (!b) b = btns[0];
          if (!b) return 'no-button';
          b.scrollIntoView({block: 'center'});
          const lbl = (b.getAttribute('aria-label') || b.innerText || '').slice(0, 40);
          b.click();
          return 'clicked:' + lbl;
        }""",
        [slot, which],
    )


def play_and_collect(page: Page, fr, wait_ms: int = 12000) -> list[dict]:
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    got = fr.evaluate(
        """() => {
          const b = document.getElementById('mt-play');
          if (!b) return 'no-button';
          b.click();
          return 'clicked';
        }"""
    )
    log(f"  mt-play -> {got}")
    page.wait_for_timeout(wait_ms)
    return collect(page)


def report_schedule(ev: list[dict], tag: str) -> dict:
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start" and e.get("_frame") == "iframe"]
    oscs = [e for e in ev if e.get("kind") == "osc_start" and e.get("_frame") == "iframe"]
    decs = [e for e in ev if e.get("kind") == "decode" and e.get("_frame") == "iframe"]
    ctxs = [e for e in ev if e.get("kind") == "audioctx_new" and e.get("_frame") == "iframe"]
    log(f"  iframe events: {len(ctxs)} context, {len(oscs)} click, "
        f"{len(decs)} decode, {len(srcs)} source")
    for e in decs:
        log(f"    decode {e.get('bytes')}B -> {e.get('buffer_sec')}s took "
            f"{fmt(e.get('wall_ms'), 1)} ms")
    lbs = []
    for e in srcs:
        lb = e.get("late_by")
        lbs.append(float(lb) if lb is not None else 0.0)
        if lb is None:
            v = "no scheduled time"
        elif lb <= 0:
            v = f"ON TIME ({fmt(-lb)}s headroom)"
        else:
            v = f"LATE by {fmt(lb)}s -> starts immediately"
        log(f"    start(when={fmt(e.get('when'))}) clock {fmt(e.get('ctx_now'))} -> {v}"
            f"   [{e.get('buffer_sec')}s loop={e.get('loop')}]")
    out = {"tag": tag, "sources": len(srcs), "clicks": len(oscs),
           "late_by": lbs,
           "spread_sec": (max(lbs) - min(lbs)) if len(lbs) > 1 else None,
           "worst_late_sec": max(lbs) if lbs else None}
    if out["spread_sec"] is not None:
        log(f"  >> layers actually begin {fmt(out['spread_sec'], 3)}s "
            f"({fmt(out['spread_sec'] * 1000, 0)} ms) apart")
    if lbs and max(lbs) > 0.001:
        log(f"  >> worst layer is {fmt(max(lbs), 3)}s behind its scheduled beat")
    return out


# ------------------------------------------------------------------------- legs
def leg_zero_headroom(page: Page) -> None:
    log("\n== LEG E: Count-in = None removes the transport's decode headroom ==")
    log(f"  Count-in shows {selectbox_value(page, 'count-in')!r}")
    set_baseweb_select(page, "Count-in", "None", prefer_sidebar=False)
    settle(page, 8)
    now = selectbox_value(page, "count-in")
    log(f"  Count-in now shows {now!r}")
    FINDINGS["count_in_value"] = now
    try:
        if "none" not in low(now):
            log("  !! Count-in did not move to None - leg not valid")
            FINDINGS["zero_headroom_valid"] = False
            return
        FINDINGS["zero_headroom_valid"] = True
        fr = iframe_frame(page)
        if fr is None:
            log("  !! transport iframe not found")
            return
        ev = play_and_collect(page, fr)
        FINDINGS["zero_headroom"] = report_schedule(ev, "count_in_none")
    finally:
        # Restore on every path. An earlier run bailed out before restoring and left
        # Count-in at None, which silently removed the count-in from a later leg.
        set_baseweb_select(page, "Count-in", "1 bar", prefer_sidebar=False)
        settle(page, 8)
        log(f"  Count-in restored to {selectbox_value(page, 'count-in')!r}")


def leg_negative_align(page: Page) -> None:
    log("\n== LEG H: a negative Align in the transport preview ==")
    slot = "guitar"
    expand_layer(page, slot)
    settle(page, 2)
    log(f"  Align slider focus: {set_slider(page, slot, 'align timing', -1.0)}")
    for _ in range(20):
        page.keyboard.press("ArrowLeft")
    settle(page, 8)
    val = slider_value(page, slot, "align timing")
    log(f"  Align timing for {slot} now reads {val}")
    FINDINGS["negative_align_value"] = val
    try:
        if float(val) >= 0:
            log("  !! could not drive Align negative - leg not valid")
            FINDINGS["negative_align_valid"] = False
            return
    except Exception:
        FINDINGS["negative_align_valid"] = False
        return
    FINDINGS["negative_align_valid"] = True
    fr = iframe_frame(page)
    if fr is None:
        log("  !! transport iframe not found")
        return
    delays = fr.evaluate(
        "() => (typeof tracks !== 'undefined' ? tracks.map("
        "(t) => ({name: t.name, delay: t.delay})) : null)")
    log(f"  the transport was handed these delays: {json.dumps(delays)}")
    FINDINGS["transport_delays"] = delays
    ev = play_and_collect(page, fr)
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start" and e.get("_frame") == "iframe"]
    whens = sorted({round(float(e["when"]), 4) for e in srcs if e.get("when") is not None})
    log(f"  distinct scheduled start times: {whens}")
    FINDINGS["negative_align_whens"] = whens
    if len(whens) == 1:
        log("  >> every layer was scheduled at the SAME instant, so the negative Align "
            "moved nothing in the preview (Math.max(0, delay) discards it)")
    else:
        log("  >> the preview did place layers at different times")


def leg_record_then_play(page: Page) -> None:
    log("\n== LEG F: Record, then Play, with no rerun between them ==")
    slot = "vocals"
    expand_layer(page, slot)
    settle(page, 3)
    fr = iframe_frame(page)
    if fr is None:
        log("  !! transport iframe not found")
        return
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    log(f"  arm recorder: {audio_input_button(page, slot, 'record')}")
    page.wait_for_timeout(800)
    alive = fr.evaluate("() => !!document.getElementById('mt-play')")
    log(f"  transport iframe still alive after arming the mic: {alive}")
    FINDINGS["iframe_survives_arming"] = bool(alive)
    if not alive:
        log("  >> arming the microphone tore the transport iframe down")
        return
    fr.evaluate("() => { const b = document.getElementById('mt-play'); if (b) b.click(); }")
    log("  pressed Play with count-in")
    page.wait_for_timeout(13000)
    ev = collect(page)
    FINDINGS["record_then_play_events"] = ev
    mr = [e for e in ev if e.get("kind") == "mediarecorder_start"]
    ctxs = [e for e in ev if e.get("kind") == "audioctx_new"
            and e.get("_frame") == "iframe"]
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start"
            and e.get("_frame") == "iframe"]
    oscs = [e for e in ev if e.get("kind") == "osc_start" and e.get("_frame") == "iframe"]
    if not (mr and ctxs and (srcs or oscs)):
        log(f"  !! could not anchor the clocks: recorder={len(mr)} ctx={len(ctxs)} "
            f"sources={len(srcs)} clicks={len(oscs)}")
        log(f"  stop recorder: {audio_input_button(page, slot, 'stop')}")
        return
    anchor = ctxs[0]
    wall0 = float(anchor["wall"])
    ct0 = float(anchor.get("currentTime") or 0.0)
    rec_wall = float(mr[0]["wall"])
    log(f"  MediaRecorder.start wall {rec_wall:.1f}")
    log(f"  transport AudioContext built wall {wall0:.1f} at currentTime {ct0:.4f} "
        f"(sr={anchor.get('sampleRate')}, baseLatency={anchor.get('baseLatency')}, "
        f"outputLatency={anchor.get('outputLatency')})")
    if oscs:
        cw = min(float(e["when"]) for e in oscs if e.get("when") is not None)
        click_wall = wall0 + (cw - ct0) * 1000.0
        FINDINGS["capture_to_first_click_ms"] = click_wall - rec_wall
        log(f"  >> first count-in click is {click_wall - rec_wall:.1f} ms after "
            f"capture start")
    if srcs:
        mw = min(float(e["when"]) for e in srcs if e.get("when") is not None)
        music_wall = wall0 + (mw - ct0) * 1000.0
        FINDINGS["capture_to_beat1_ms"] = music_wall - rec_wall
        log(f"  >> musical beat 1 is {music_wall - rec_wall:.1f} ms after capture start")
        log("     This is the amount of audio the take carries before bar 1, measured on")
        log("     the scheduling side only. It excludes device capture latency, the gap")
        log("     between MediaRecorder.start and its first encoded sample, and output")
        log("     latency - none of which JavaScript can observe. The app stores no")
        log("     timestamp for it either way, so nothing downstream knows this number.")
    log(f"  stop recorder: {audio_input_button(page, slot, 'stop')}")
    settle(page, 10)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="issue78-probe3-"))
    click_wav = make_wav("transient3.wav", freq=220.0, seconds=6.0, click_at=0.5)
    layer_wavs = {
        "guitar": make_wav("g3.wav", freq=196.0, seconds=6.0, click_at=0.0),
        "sax / winds": make_wav("s3.wav", freq=311.0, seconds=6.0, click_at=0.0),
        "extra layer": make_wav("f3.wav", freq=587.0, seconds=6.0, click_at=0.0),
    }
    log(f"scratch {tmp}; fake capture device fed {click_wav}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={click_wav}",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                  permissions=["microphone"])
        ctx.add_init_script(INSTRUMENT)
        page = ctx.new_page()
        page.set_default_timeout(25000)
        try:
            if not boot(page):
                log("app did not boot")
                return 1
            expand_sidebar(page)
            try:
                pick_song(page, NOTES, "Let It Be", "Rock")
                settle(page, 4)
            except Exception as exc:
                log(f"pick_song raised ({exc}) - continuing")
            if not goto_multitrack(page):
                log("could not reach the Multitrack page")
                return 1
            log("on the Multitrack page")
            log(f"  Prepare backing -> {click_text_button(page, 'prepare backing')}")
            settle(page, 12)
            staged = []
            for slot, path in layer_wavs.items():
                expand_layer(page, slot)
                settle(page, 2)
                if upload_into_slot(page, slot, Path(path)):
                    staged.append(slot)
            log(f"  layers staged: {staged}")
            FINDINGS["staged"] = staged
            settle(page, 8)

            leg_zero_headroom(page)
            leg_negative_align(page)
            leg_record_then_play(page)
        finally:
            try:
                page.screenshot(path=str(OUT / "probe3-final.png"), full_page=True)
                (OUT / "probe3-body.txt").write_text(
                    (page.inner_text("body") or "")[:40000], encoding="utf-8")
            except Exception:
                pass
            (OUT / "probe3-findings.json").write_text(
                json.dumps(FINDINGS, indent=2, default=str), encoding="utf-8")
            (OUT / "probe3-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\nevidence in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

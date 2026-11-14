"""Issue 78 read-only probe 2: what actually lands in a layer, and the zero-headroom case.

Probe 1 measured the transport's clock. This one measures the two things probe 1 left
open, and both are measurements rather than code predictions:

  LEG D  Capture content.  Drive a real microphone recording through
         ``st.audio_input`` with Chromium's fake capture device fed a known WAV that
         carries one full-scale transient every 6 s, then read the bytes the app
         actually stored for that layer back out of the page and parse them.  This
         gives the stored sample rate, channel count, duration and the position of
         every recovered transient - so it answers whether the notes survive capture
         (Q6) and what bandwidth the stored take really has (Q5).

  LEG E  Zero headroom.  Set Count-in to "None" and press Play.  With no count-in the
         transport schedules every layer at the instant Play was pressed, while still
         having to decode each buffer first, so every ``start`` call lands in the past.
         This measures how far apart the layers then actually begin (Q4).

  LEG F  Measured offset between capture start and musical beat 1 (Q1/Q3), computed by
         anchoring the transport's ``AudioContext.currentTime`` to wall clock at
         construction and comparing with the wall clock at ``MediaRecorder.start``.

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8590
  python scripts/_probe_i78_capture_content.py http://127.0.0.1:8590
"""

from __future__ import annotations

import base64
import io
import json
import math
import struct
import sys
import tempfile
import wave
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
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8590"
OUT = SCRIPTS / "evidence-issue78"
OUT.mkdir(parents=True, exist_ok=True)
AUDIO = Path(tempfile.mkdtemp(prefix="issue78-probe2-"))

NOTES: list[str] = []
FINDINGS: dict[str, object] = {}

TRANSIENT_PERIOD = 6.0  # the fake capture file is 6 s long and loops
TRANSIENT_AT = 0.5      # with one full-scale sample 0.5 s in


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, seconds: float = 2.5) -> None:
    wait_idle(page, int(seconds * 1000))


def low(s: str) -> str:
    return (s or "").lower()


# ------------------------------------------------------------------ wav reading
def describe_wav(raw: bytes) -> dict:
    """Parse a stored take without librosa, and locate its transients."""
    out: dict = {"bytes": len(raw), "riff": raw[:4].decode("latin-1", "replace")}
    try:
        with wave.open(io.BytesIO(raw), "rb") as wf:
            ch = wf.getnchannels()
            sr = wf.getframerate()
            sw = wf.getsampwidth()
            n = wf.getnframes()
            frames = wf.readframes(n)
        out.update({"channels": ch, "sample_rate": sr, "sample_width": sw,
                    "frames": n, "duration_sec": round(n / sr, 4) if sr else None,
                    "nyquist_hz": sr // 2 if sr else None})
        if sw != 2:
            out["note"] = "not 16-bit; peaks not scanned"
            return out
        import array
        a = array.array("h")
        a.frombytes(frames[: (len(frames) // 2) * 2])
        if ch > 1:
            a = array.array("h", [a[i] for i in range(0, len(a) - ch + 1, ch)])
        peak = max((abs(v) for v in a), default=0)
        out["peak_abs"] = peak
        out["peak_dbfs"] = round(20 * math.log10(peak / 32768.0), 2) if peak else None
        rms = math.sqrt(sum(float(v) * v for v in a) / len(a)) if len(a) else 0.0
        out["rms_dbfs"] = round(20 * math.log10(rms / 32768.0), 2) if rms else None
        # Transients: a sample well above the surrounding tone, with a refractory gap.
        thresh = max(int(peak * 0.75), 1)
        hits = []
        last = -10 ** 9
        for i, v in enumerate(a):
            if abs(v) >= thresh and (i - last) > sr * 0.25:
                hits.append(round(i / sr, 4))
                last = i
        out["transients_sec"] = hits[:24]
        out["transient_count"] = len(hits)
        if len(hits) >= 2:
            gaps = [round(hits[i + 1] - hits[i], 4) for i in range(len(hits) - 1)]
            out["transient_gaps_sec"] = gaps[:12]
        # Any energy above 8 kHz? A 16 kHz file cannot hold any, by definition.
        out["can_hold_above_8k"] = bool(sr and sr > 16000)
    except Exception as exc:
        out["parse_error"] = str(exc)
    return out


def read_layer_bytes(page: Page, slot: str) -> bytes | None:
    """Fetch the audio the page is actually serving for this layer.

    ``st.audio(saved_audio)`` renders the stored bytes through a media endpoint, so
    fetching that element's ``src`` returns exactly what the session holds - not the
    file the browser recorded, and not a re-encode by this probe.
    """
    b64 = page.evaluate(
        """async (slot) => {
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          const scope = el || document;
          const au = [...scope.querySelectorAll('audio')].filter((a) => a.src);
          if (!au.length) return null;
          const src = au[au.length - 1].src;
          const r = await fetch(src);
          const buf = await r.arrayBuffer();
          let bin = '';
          const v = new Uint8Array(buf);
          const CH = 0x8000;
          for (let i = 0; i < v.length; i += CH) {
            bin += String.fromCharCode.apply(null, v.subarray(i, i + CH));
          }
          return btoa(bin);
        }""",
        slot,
    )
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


# ------------------------------------------------------------------ app driving
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


def on_multitrack(page: Page) -> bool:
    return "multitrack session workspace" in low(page.inner_text("body") or "")


def goto_multitrack(page: Page) -> bool:
    if on_multitrack(page):
        return True
    click_nav(page, "Multitrack")
    settle(page, 5)
    return on_multitrack(page)


def count_in_value(page: Page) -> str:
    """Read the live Count-in selectbox, never trust a setter's return value."""
    return page.evaluate(
        """() => {
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
          const b = boxes.find((x) => (x.innerText || '').toLowerCase()
                     .includes('count-in'));
          if (!b) return 'not-found';
          const v = b.querySelector('[data-baseweb="select"] div[value], '
                    + '[data-baseweb="select"] span');
          return ((v && v.innerText) || b.innerText || '').trim().slice(0, 40);
        }"""
    )


def audio_input_button(page: Page, slot: str, which: str) -> str:
    """Click this layer's recorder control. ``which`` is 'record' or 'stop'."""
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


# ------------------------------------------------------------------------- legs
def leg_zero_headroom(page: Page) -> None:
    log("\n== LEG E: Count-in = None, so the transport has no decode headroom ==")
    before = count_in_value(page)
    log(f"  Count-in reads {before!r} before the change")
    set_baseweb_select(page, "Count-in", "None", prefer_sidebar=False)
    settle(page, 6)
    after = count_in_value(page)
    log(f"  Count-in reads {after!r} after the change")
    FINDINGS["count_in_set_to"] = after
    if "none" not in low(after):
        log("  !! could not set Count-in to None - this leg is not valid, skipping")
        FINDINGS["zero_headroom_valid"] = False
        return
    FINDINGS["zero_headroom_valid"] = True
    fr = iframe_frame(page)
    if fr is None:
        log("  !! transport iframe not found")
        return
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    fr.evaluate("() => { const b = document.getElementById('mt-play'); if (b) b.click(); }")
    page.wait_for_timeout(12000)
    ev = collect(page)
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start"]
    oscs = [e for e in ev if e.get("kind") == "osc_start"]
    decs = [e for e in ev if e.get("kind") == "decode"]
    FINDINGS["zero_headroom_events"] = ev
    log(f"  count-in clicks scheduled: {len(oscs)} (expected 0 with Count-in None)")
    for e in decs:
        log(f"  decodeAudioData {e.get('bytes')} bytes -> {e.get('buffer_sec')}s "
            f"took {fmt(e.get('wall_ms'), 1)} ms")
    lbs = []
    for e in srcs:
        lb = e.get("late_by")
        lbs.append(lb if lb is not None else 0.0)
        verdict = ("ON TIME" if (lb or 0) <= 0
                   else f"LATE by {fmt(lb)}s - starts immediately instead")
        log(f"  source.start(when={fmt(e.get('when'))}) clock at "
            f"{fmt(e.get('ctx_now'))} -> {verdict}   [{e.get('buffer_sec')}s]")
    if len(lbs) > 1:
        spread = max(lbs) - min(lbs)
        FINDINGS["zero_headroom_spread_sec"] = spread
        log(f"  >> MEASURED: the layers actually begin {fmt(spread, 3)}s apart "
            f"({fmt(spread * 1000, 0)} ms)")
        log(f"  >> worst single layer is {fmt(max(lbs), 3)}s behind the beat it was "
            f"scheduled on")
    # restore
    set_baseweb_select(page, "Count-in", "1 bar", prefer_sidebar=False)
    settle(page, 6)
    log(f"  Count-in restored to {count_in_value(page)!r}")


def leg_capture_content(page: Page) -> None:
    log("\n== LEG D/F: a real microphone take, and what the app stores for it ==")
    slot = "vocals"
    expand_layer(page, slot)
    settle(page, 3)
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    log(f"  arm recorder on {slot}: {audio_input_button(page, slot, 'record')}")
    page.wait_for_timeout(1500)
    fr = iframe_frame(page)
    if fr is not None:
        fr.evaluate(
            "() => { const b = document.getElementById('mt-play'); if (b) b.click(); }")
        log("  pressed Play with count-in while the recorder was already running")
    page.wait_for_timeout(14000)
    log(f"  stop recorder: {audio_input_button(page, slot, 'stop')}")
    settle(page, 12)

    ev = collect(page)
    FINDINGS["capture_events"] = ev
    mr = [e for e in ev if e.get("kind") == "mediarecorder_start"]
    ctxs = [e for e in ev if e.get("kind") == "audioctx_new"
            and e.get("label") in ("AudioContext", "webkitAudioContext")]
    oscs = [e for e in ev if e.get("kind") == "osc_start"]
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start"]
    if mr and ctxs and srcs:
        anchor = ctxs[-1]
        wall0 = float(anchor["wall"])
        ct0 = float(anchor.get("currentTime") or 0.0)
        music_when = min(float(e["when"]) for e in srcs if e.get("when") is not None)
        music_wall = wall0 + (music_when - ct0) * 1000.0
        rec_wall = float(mr[-1]["wall"])
        offset_ms = music_wall - rec_wall
        FINDINGS["capture_to_beat1_offset_ms"] = offset_ms
        log(f"  MediaRecorder.start at wall {rec_wall:.1f}")
        log(f"  transport AudioContext built at wall {wall0:.1f}, currentTime {ct0:.4f}")
        log(f"  musical beat 1 scheduled at ctx {music_when:.4f} "
            f"-> wall {music_wall:.1f}")
        log(f"  >> MEASURED offset from capture start to musical beat 1: "
            f"{offset_ms:.1f} ms")
        log("     (a lower bound: it excludes device capture latency, the gap between "
            "MediaRecorder.start and its first encoded sample, and output latency)")
        if oscs:
            cw = min(float(e["when"]) for e in oscs if e.get("when") is not None)
            click_wall = wall0 + (cw - ct0) * 1000.0
            FINDINGS["capture_to_first_click_offset_ms"] = click_wall - rec_wall
            log(f"  >> first count-in click lands {click_wall - rec_wall:.1f} ms after "
                f"capture start")
    else:
        log(f"  !! could not anchor the clocks: mediarecorder={len(mr)} "
            f"audioctx={len(ctxs)} sources={len(srcs)}")

    raw = read_layer_bytes(page, slot)
    if not raw:
        log(f"  !! no stored audio recovered for {slot}")
        FINDINGS["stored_take"] = None
        return
    (OUT / "stored-take-vocals.wav").write_bytes(raw)
    desc = describe_wav(raw)
    FINDINGS["stored_take"] = desc
    log(f"  recovered {len(raw)} bytes the app stored for {slot}")
    log(f"  STORED FORMAT: {desc.get('channels')} ch @ {desc.get('sample_rate')} Hz, "
        f"{desc.get('sample_width')} bytes/sample, "
        f"{desc.get('duration_sec')}s  (Nyquist {desc.get('nyquist_hz')} Hz)")
    log(f"  level: peak {desc.get('peak_dbfs')} dBFS, rms {desc.get('rms_dbfs')} dBFS")
    log(f"  transients recovered: {desc.get('transient_count')} at "
        f"{desc.get('transients_sec')}")
    if desc.get("transient_gaps_sec"):
        log(f"  gaps between transients: {desc.get('transient_gaps_sec')} "
            f"(the capture file repeats every {TRANSIENT_PERIOD}s)")
    log(f"  can this stored format hold anything above 8 kHz? "
        f"{desc.get('can_hold_above_8k')}")
    if desc.get("parse_error"):
        log(f"  parse error: {desc.get('parse_error')}")


def main() -> int:
    click_wav = make_wav("transient.wav", freq=220.0, seconds=TRANSIENT_PERIOD,
                         click_at=TRANSIENT_AT)
    layer_wavs = {
        "guitar": make_wav("guitar.wav", freq=196.0, seconds=6.0, click_at=0.0),
        "sax / winds": make_wav("sax.wav", freq=311.0, seconds=6.0, click_at=0.0),
        "extra layer": make_wav("flute.wav", freq=587.0, seconds=6.0, click_at=0.0),
    }
    log(f"probe audio in {AUDIO}")
    log(f"fake capture device fed {click_wav} "
        f"({TRANSIENT_PERIOD}s, full-scale transient at {TRANSIENT_AT}s, looping)")

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

            from pathlib import Path as _P
            from _probe_i78_recording_clock import upload_into_slot
            staged = []
            for slot, path in layer_wavs.items():
                expand_layer(page, slot)
                settle(page, 2)
                if upload_into_slot(page, slot, _P(path)):
                    staged.append(slot)
            log(f"  layers staged for the headroom test: {staged}")
            settle(page, 8)

            leg_zero_headroom(page)
            leg_capture_content(page)
        finally:
            try:
                page.screenshot(path=str(OUT / "probe2-final.png"), full_page=True)
                (OUT / "probe2-body.txt").write_text(
                    (page.inner_text("body") or "")[:40000], encoding="utf-8")
            except Exception:
                pass
            (OUT / "probe2-findings.json").write_text(
                json.dumps(FINDINGS, indent=2, default=str), encoding="utf-8")
            (OUT / "probe2-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\nevidence in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

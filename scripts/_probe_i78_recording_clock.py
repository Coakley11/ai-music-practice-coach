"""Issue 78 read-only probe: measure the Multitrack recording/playback timing contract.

Nothing in the app is changed. All measurement is browser-side instrumentation injected
with Playwright ``add_init_script``, which applies to every frame - including the
``components.html`` transport iframe, which is a separate document from the Streamlit
page that owns ``st.audio_input``.

What is hooked, and which question each hook answers:

  navigator.mediaDevices.getUserMedia   -> the constraints the recorder actually asks
                                           for, and the settings the browser actually
                                           grants (sample rate, echoCancellation,
                                           noiseSuppression, autoGainControl).  Q5
  MediaRecorder.start / .stop           -> the wall-clock instant capture begins.  Q1/Q3
  AudioContext construction             -> the transport clock's own sample rate and
                                           output latency, plus a wall-clock anchor so
                                           ``currentTime`` can be compared with the
                                           recorder's clock.  Q2
  BaseAudioContext.decodeAudioData      -> how long each layer takes to decode, measured
                                           against the transport clock.  Q4
  AudioBufferSourceNode.start           -> the scheduled ``when`` versus the clock at the
                                           moment ``start`` was called.  A positive
                                           ``late_by`` means the scheduled instant had
                                           already passed, so the browser starts that
                                           layer immediately instead.  Q4/Q6
  OscillatorNode.start                  -> the count-in clicks.  Q3

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8590
  python scripts/_probe_i78_recording_clock.py http://127.0.0.1:8590
"""

from __future__ import annotations

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

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8590"
OUT = SCRIPTS / "evidence-issue78"
OUT.mkdir(parents=True, exist_ok=True)
AUDIO = Path(tempfile.mkdtemp(prefix="issue78-probe-"))

NOTES: list[str] = []
FINDINGS: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, seconds: float = 2.5) -> None:
    wait_idle(page, int(seconds * 1000))


def low(s: str) -> str:
    return (s or "").lower()


# ---------------------------------------------------------------- probe audio
def make_wav(name: str, *, freq: float, seconds: float, rate: int = 44100,
             click_at: float | None = None) -> Path:
    """A tone, optionally with a sharp transient at ``click_at`` seconds.

    The transient is what makes a start offset measurable: it is a single full-scale
    sample, so its position in a recovered file is unambiguous.
    """
    path = AUDIO / name
    frames = bytearray()
    n = int(rate * seconds)
    click_i = int(rate * click_at) if click_at is not None else -1
    for i in range(n):
        if i == click_i:
            value = 32000
        else:
            value = int(9000 * math.sin(2 * math.pi * freq * i / rate))
        frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(bytes(frames))
    return path


# ---------------------------------------------------------------- instrument
INSTRUMENT = r"""
(() => {
  const W = window;
  if (W.__i78) return;
  const ev = [];
  W.__i78 = ev;
  const now = () => performance.timeOrigin + performance.now();
  const push = (o) => {
    try {
      ev.push(Object.assign({wall: now(), href: String(location.href).slice(0, 70)}, o));
    } catch (e) {}
  };
  W.__i78push = push;

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    const orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async function (c) {
      let dumped = null;
      try { dumped = JSON.parse(JSON.stringify(c || {})); } catch (e) { dumped = String(c); }
      push({kind: 'gum_request', constraints: dumped});
      const s = await orig(c);
      try {
        const tr = s.getAudioTracks()[0];
        push({kind: 'gum_settings', settings: tr ? tr.getSettings() : null});
      } catch (e) { push({kind: 'gum_settings_error', err: String(e)}); }
      return s;
    };
  }

  if (W.MediaRecorder) {
    const S = W.MediaRecorder.prototype.start;
    const T = W.MediaRecorder.prototype.stop;
    W.MediaRecorder.prototype.start = function () {
      push({kind: 'mediarecorder_start', mimeType: this.mimeType,
            audioBitsPerSecond: this.audioBitsPerSecond});
      return S.apply(this, arguments);
    };
    W.MediaRecorder.prototype.stop = function () {
      push({kind: 'mediarecorder_stop'});
      return T.apply(this, arguments);
    };
  }

  const wrapCtor = (Ctor, label) => {
    if (!Ctor) return Ctor;
    return new Proxy(Ctor, {
      construct(target, args) {
        const c = new target(...args);
        push({kind: 'audioctx_new', label: label, sampleRate: c.sampleRate,
              baseLatency: c.baseLatency === undefined ? null : c.baseLatency,
              outputLatency: c.outputLatency === undefined ? null : c.outputLatency,
              currentTime: c.currentTime});
        return c;
      },
    });
  };
  try { W.AudioContext = wrapCtor(W.AudioContext, 'AudioContext'); } catch (e) {}
  try { W.webkitAudioContext = wrapCtor(W.webkitAudioContext, 'webkitAudioContext'); } catch (e) {}
  try { W.OfflineAudioContext = wrapCtor(W.OfflineAudioContext, 'OfflineAudioContext'); } catch (e) {}

  if (W.BaseAudioContext) {
    const D = W.BaseAudioContext.prototype.decodeAudioData;
    W.BaseAudioContext.prototype.decodeAudioData = function (buf) {
      const t0 = now();
      const ct0 = this.currentTime;
      const bytes = buf && buf.byteLength;
      const self = this;
      const r = D.apply(this, arguments);
      if (r && typeof r.then === 'function') {
        return r.then((b) => {
          push({kind: 'decode', bytes: bytes, wall_ms: now() - t0,
                ctx_before: ct0, ctx_after: self.currentTime,
                buffer_sec: b ? b.duration : null,
                buffer_sr: b ? b.sampleRate : null});
          return b;
        });
      }
      return r;
    };
  }

  if (W.AudioBufferSourceNode) {
    const S = W.AudioBufferSourceNode.prototype.start;
    W.AudioBufferSourceNode.prototype.start = function (when) {
      const ct = this.context ? this.context.currentTime : null;
      const w = (when === undefined) ? null : Number(when);
      push({kind: 'bufsrc_start', when: w, ctx_now: ct,
            late_by: (w !== null && ct !== null) ? (ct - w) : null,
            buffer_sec: this.buffer ? this.buffer.duration : null,
            buffer_sr: this.buffer ? this.buffer.sampleRate : null,
            loop: !!this.loop});
      return S.apply(this, arguments);
    };
  }

  if (W.OscillatorNode) {
    const S = W.OscillatorNode.prototype.start;
    W.OscillatorNode.prototype.start = function (when) {
      const ct = this.context ? this.context.currentTime : null;
      const w = (when === undefined) ? null : Number(when);
      push({kind: 'osc_start', when: w, ctx_now: ct,
            freq: this.frequency ? this.frequency.value : null});
      return S.apply(this, arguments);
    };
  }
})();
"""


def collect(page: Page) -> list[dict]:
    """Drain __i78 from every frame, tagging which document each event came from."""
    out: list[dict] = []
    for fr in page.frames:
        try:
            got = fr.evaluate("() => (window.__i78 || []).slice()")
        except Exception:
            continue
        if not got:
            continue
        for e in got:
            e["_frame"] = "main" if fr is page.main_frame else "iframe"
        out.extend(got)
    out.sort(key=lambda e: e.get("wall") or 0)
    return out


# ---------------------------------------------------------------- app driving
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


def click_text_button(page: Page, text: str) -> str:
    """Click a Streamlit button by its visible label, via a dispatched event."""
    return page.evaluate(
        """(want) => {
          const w = want.toLowerCase();
          const btns = [...document.querySelectorAll('button')];
          const el = btns.find((b) => (b.innerText || '').toLowerCase().includes(w));
          if (!el) return 'not-found';
          el.scrollIntoView({block: 'center'});
          el.click();
          return 'clicked';
        }""",
        text,
    )


def expand_layer(page: Page, slot: str) -> str:
    return page.evaluate(
        """(slot) => {
          const want = 'layer controls';
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes(want) && t.includes(s);
          });
          if (!el) return 'not-found';
          const sum = el.querySelector('summary');
          sum.scrollIntoView({block: 'center'});
          if (!el.hasAttribute('open')) sum.click();
          return el.hasAttribute('open') ? 'open' : 'clicked';
        }""",
        slot,
    )


def upload_into_slot(page: Page, slot: str, path: Path) -> bool:
    """Drop a file on this slot's uploader - the same store-a-take code path."""
    idx = page.evaluate(
        """(slot) => {
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('[data-testid="stFileUploader"]')];
          for (let i = 0; i < all.length; i++) {
            const t = (all[i].innerText || '').toLowerCase();
            if (t.includes('upload') && t.includes(s)) return i;
          }
          return -1;
        }""",
        slot,
    )
    if idx is None or idx < 0:
        return False
    inputs = page.locator('[data-testid="stFileUploader"] input[type="file"]')
    try:
        inputs.nth(idx).set_input_files(str(path))
    except Exception as exc:
        log(f"    upload into {slot} raised: {exc}")
        return False
    settle(page, 5)
    return True


def iframe_frame(page: Page):
    for fr in page.frames:
        try:
            if fr.evaluate("() => !!document.getElementById('mt-play')"):
                return fr
        except Exception:
            continue
    return None


def fmt(v, nd=4):
    try:
        return f"{float(v):.{nd}f}"
    except Exception:
        return str(v)


# ---------------------------------------------------------------- the legs
def leg_mic_contract(page: Page) -> None:
    """Q5 + Q1: what the microphone recorder actually asks for and is granted."""
    log("\n== LEG A: microphone capture contract ==")
    expand_layer(page, "guitar")
    settle(page, 2)
    res = page.evaluate(
        """() => {
          const recs = [...document.querySelectorAll('[data-testid="stAudioInput"]')];
          if (!recs.length) return {found: 0};
          const btns = [...recs[0].querySelectorAll('button')];
          const b = btns[0];
          if (!b) return {found: recs.length, clicked: false};
          b.scrollIntoView({block: 'center'});
          b.click();
          return {found: recs.length, clicked: true,
                  label: (b.getAttribute('aria-label') || b.innerText || '').slice(0, 60)};
        }"""
    )
    log(f"  audio_input widgets found: {res}")
    settle(page, 5)
    ev = collect(page)
    gum_req = [e for e in ev if e.get("kind") == "gum_request"]
    gum_set = [e for e in ev if e.get("kind") == "gum_settings"]
    mr = [e for e in ev if e.get("kind") == "mediarecorder_start"]
    FINDINGS["gum_request"] = gum_req
    FINDINGS["gum_settings"] = gum_set
    FINDINGS["mediarecorder_start"] = mr
    for e in gum_req:
        log(f"  getUserMedia CONSTRAINTS asked for: {json.dumps(e.get('constraints'))}")
    for e in gum_set:
        log(f"  track settings GRANTED:            {json.dumps(e.get('settings'))}")
    for e in mr:
        log(f"  MediaRecorder started, mimeType={e.get('mimeType')!r} "
            f"bitrate={e.get('audioBitsPerSecond')}")
    if not gum_req:
        log("  !! no getUserMedia observed - the record button may not have armed")


def leg_transport_clock(page: Page, layers: list[str]) -> None:
    """Q2/Q3/Q4: one Play with count-in, fully instrumented."""
    log("\n== LEG B: transport clock, count-in and layer scheduling ==")
    fr = iframe_frame(page)
    if fr is None:
        log("  !! transport iframe not found")
        return
    log(f"  transport iframe located, {len(layers)} layer(s) staged")
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    t_click = fr.evaluate(
        """() => {
          const b = document.getElementById('mt-play');
          if (!b) return null;
          const t = performance.timeOrigin + performance.now();
          b.click();
          return t;
        }"""
    )
    FINDINGS["play_clicked_wall"] = t_click
    log(f"  Play with count-in clicked at wall {t_click}")
    page.wait_for_timeout(12000)
    ev = collect(page)
    FINDINGS["transport_events"] = ev
    ctxs = [e for e in ev if e.get("kind") == "audioctx_new"]
    oscs = [e for e in ev if e.get("kind") == "osc_start"]
    decs = [e for e in ev if e.get("kind") == "decode"]
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start"]
    for e in ctxs:
        log(f"  AudioContext({e.get('label')}) sr={e.get('sampleRate')} "
            f"baseLatency={e.get('baseLatency')} outputLatency={e.get('outputLatency')}")
    whens = [e["when"] for e in oscs if e.get("when") is not None]
    if whens:
        log(f"  count-in clicks scheduled: {len(oscs)}; "
            f"first when={fmt(min(whens))} last when={fmt(max(whens))}")
    else:
        log(f"  count-in clicks scheduled: {len(oscs)}")
    for e in decs:
        log(f"  decodeAudioData {e.get('bytes')} bytes -> {e.get('buffer_sec')}s "
            f"@{e.get('buffer_sr')}Hz took {fmt(e.get('wall_ms'), 1)} ms "
            f"(ctx {fmt(e.get('ctx_before'))} -> {fmt(e.get('ctx_after'))})")
    for e in srcs:
        lb = e.get("late_by")
        if lb is None:
            verdict = "no scheduled time"
        elif lb <= 0:
            verdict = f"ON TIME ({fmt(-lb)}s of headroom)"
        else:
            verdict = f"LATE by {fmt(lb)}s - starts immediately instead"
        log(f"  source.start(when={fmt(e.get('when'))}) with clock at "
            f"{fmt(e.get('ctx_now'))} -> {verdict}   "
            f"[{e.get('buffer_sec')}s @{e.get('buffer_sr')}Hz loop={e.get('loop')}]")
    late = [e for e in srcs if (e.get("late_by") or 0) > 0.001]
    FINDINGS["late_sources"] = late
    lbs = [e["late_by"] for e in srcs if e.get("late_by") is not None]
    if late:
        log(f"  >> {len(late)} of {len(srcs)} scheduled sources missed their slot; "
            f"worst {fmt(max(lbs), 3)}s late")
    if len(lbs) > 1:
        log(f"  >> spread between earliest and latest actual start = "
            f"{fmt(max(lbs) - min(lbs), 3)}s - that is how far apart the layers begin")


def leg_iframe_can_capture(page: Page) -> None:
    """Q7 feasibility: can the transport iframe itself open the microphone?

    If it can, capture and playback can share one ``AudioContext``, and alignment stops
    being a clock-reconciliation problem - the capture node and the backing source read
    the same ``currentTime``. Streamlit renders ``components.html`` with
    ``allow="... microphone ..."`` and ``sandbox="... allow-same-origin allow-scripts"``,
    so this is expected to work; expected is not measured, hence this leg.
    """
    log("\n== LEG C: can the transport iframe open the microphone itself? ==")
    fr = iframe_frame(page)
    if fr is None:
        log("  !! transport iframe not found")
        return
    attrs = page.evaluate(
        """() => {
          const fs = [...document.querySelectorAll('iframe')];
          return fs.map((f) => ({
            allow: f.getAttribute('allow') || null,
            sandbox: f.getAttribute('sandbox') || null,
            srcdoc: !!f.getAttribute('srcdoc'),
            src: (f.getAttribute('src') || '').slice(0, 60),
          }));
        }"""
    )
    FINDINGS["iframe_attrs"] = attrs
    for a in attrs:
        if a.get("srcdoc") or "mt-" in str(a.get("src")):
            log(f"  iframe allow={str(a.get('allow'))[:150]}")
            log(f"  iframe sandbox={a.get('sandbox')}")
    res = fr.evaluate(
        """async () => {
          const out = {secureContext: window.isSecureContext,
                       origin: String(location.origin),
                       hasMD: !!(navigator.mediaDevices
                                 && navigator.mediaDevices.getUserMedia)};
          if (!out.hasMD) return out;
          try {
            const s = await navigator.mediaDevices.getUserMedia({audio: {
              echoCancellation: false, noiseSuppression: false,
              autoGainControl: false, sampleRate: 48000, channelCount: 1}});
            const tr = s.getAudioTracks()[0];
            out.granted = true;
            out.settings = tr ? tr.getSettings() : null;
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            out.ctxSampleRate = ctx.sampleRate;
            try {
              const node = ctx.createMediaStreamSource(s);
              out.sourceNodeOnSameContext = !!node;
              out.ctxCurrentTime = ctx.currentTime;
              out.ctxBaseLatency = ctx.baseLatency === undefined ? null : ctx.baseLatency;
              out.ctxOutputLatency =
                ctx.outputLatency === undefined ? null : ctx.outputLatency;
              const rec = window.MediaRecorder
                ? MediaRecorder.isTypeSupported('audio/webm;codecs=opus') : null;
              out.mediaRecorderOpus = rec;
              out.hasAudioWorklet = !!(ctx.audioWorklet);
            } catch (e) { out.sourceNodeError = String(e); }
            ctx.close();
            s.getTracks().forEach((t) => t.stop());
          } catch (e) {
            out.granted = false;
            out.error = String(e);
          }
          return out;
        }"""
    )
    FINDINGS["iframe_capture"] = res
    log(f"  secure context: {res.get('secureContext')}   origin: {res.get('origin')}")
    log(f"  getUserMedia inside the transport iframe granted: {res.get('granted')}"
        + (f"   error={res.get('error')}" if res.get("error") else ""))
    if res.get("settings") is not None:
        log(f"  granted settings with explicit constraints: "
            f"{json.dumps(res.get('settings'))}")
    log(f"  playback AudioContext sampleRate={res.get('ctxSampleRate')} "
        f"baseLatency={res.get('ctxBaseLatency')} "
        f"outputLatency={res.get('ctxOutputLatency')}")
    log(f"  capture node created on the SAME context as playback: "
        f"{res.get('sourceNodeOnSameContext')}"
        + (f"   error={res.get('sourceNodeError')}" if res.get("sourceNodeError") else ""))
    log(f"  AudioWorklet available: {res.get('hasAudioWorklet')}   "
        f"MediaRecorder opus: {res.get('mediaRecorderOpus')}")


def main() -> int:
    click_wav = make_wav("transient.wav", freq=220.0, seconds=6.0, click_at=0.5)
    layer_wavs = {
        "guitar": make_wav("guitar.wav", freq=196.0, seconds=6.0, click_at=0.0),
        "sax / winds": make_wav("sax.wav", freq=311.0, seconds=6.0, click_at=0.0),
        "extra layer": make_wav("flute.wav", freq=587.0, seconds=6.0, click_at=0.0),
    }
    log(f"probe audio in {AUDIO}")

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
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            permissions=["microphone"],
        )
        ctx.add_init_script(INSTRUMENT)
        page = ctx.new_page()
        page.set_default_timeout(25000)
        try:
            if not boot(page):
                log("app did not boot")
                return 1
            expand_sidebar(page)
            log("app booted")
            try:
                pick_song(page, NOTES, "Let It Be", "Rock")
                settle(page, 4)
                log("active song: Let It Be")
            except Exception as exc:
                log(f"pick_song raised ({exc}) - continuing with whatever is active")
            if not goto_multitrack(page):
                log("could not reach the Multitrack page")
                return 1
            log("on the Multitrack page")

            log(f"  Prepare backing -> {click_text_button(page, 'prepare backing')}")
            settle(page, 12)
            FINDINGS["frames"] = [f.url[:90] for f in page.frames]
            log(f"  frames now: {FINDINGS['frames']}")

            staged = []
            for slot, path in layer_wavs.items():
                expand_layer(page, slot)
                settle(page, 2)
                if upload_into_slot(page, slot, path):
                    staged.append(slot)
                    log(f"  staged a layer into {slot}")
            log(f"  layers staged: {staged}")
            settle(page, 8)

            leg_transport_clock(page, staged)
            leg_mic_contract(page)
            leg_iframe_can_capture(page)
        finally:
            try:
                page.screenshot(path=str(OUT / "probe-final.png"), full_page=True)
                (OUT / "probe-body.txt").write_text(
                    (page.inner_text("body") or "")[:40000], encoding="utf-8")
            except Exception:
                pass
            (OUT / "probe-findings.json").write_text(
                json.dumps(FINDINGS, indent=2, default=str), encoding="utf-8")
            (OUT / "probe-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\nevidence in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

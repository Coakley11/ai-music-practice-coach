"""Issue 78 Slice 78A acceptance, in the real app.

The component harness (``_accept_issue78a_transport.py``) measures the transport's
scheduling in isolation. This one runs the same change inside Streamlit, where the
payload, the session and the export all participate, and measures the thing Phase B is
actually about:

  **the same Align offset must put the audio in the same place in the transport preview
  and in the exported WAV.**

It is measured, not asserted. A layer carries one full-scale transient at a known second.
The exported WAV is fetched back out of the page and the transient located, which gives
its position relative to bar 1. The transport is instrumented, which gives the instant it
scheduled that layer and the offset it read into the buffer. Those two numbers must agree.

Also here: the responsive gates at 390 px and 360 px, and a no-JS-error check on the page.

Usage:
  MUSIC_APP_DATA_DIR=<disposable dir> streamlit run streamlit_music_practice_app.py \
      --server.port 8591
  python scripts/_accept_issue78a_app.py http://127.0.0.1:8591
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

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _probe_i78_recording_clock import (  # noqa: E402
    INSTRUMENT,
    click_text_button,
    collect,
    expand_layer,
    iframe_frame,
    upload_into_slot,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8591"
OUT = SCRIPTS / "evidence-issue78a"
OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="issue78a-app-"))

TRANSIENT_AT = 1.0
LAYER_SEC = 6.0
SR = 44100

GATES: dict[str, bool] = {}
NOTES: list[str] = []
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, s: float = 2.5) -> None:
    wait_idle(page, int(s * 1000))


def low(s: str) -> str:
    return (s or "").lower()


def make_layer(path: Path, *, freq: float, click_at: float) -> Path:
    n = int(SR * LAYER_SEC)
    body = bytearray()
    ci = int(SR * click_at)
    for i in range(n):
        v = 32000 if i == ci else int(3000 * math.sin(2 * math.pi * freq * i / SR))
        body += struct.pack("<h", v)
    head = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(body), b"WAVE",
                       b"fmt ", 16, 1, 1, SR, SR * 2, 2, 16, b"data", len(body))
    path.write_bytes(head + bytes(body))
    return path


def describe_wav(raw: bytes) -> dict:
    out: dict = {"bytes": len(raw)}
    try:
        with wave.open(io.BytesIO(raw), "rb") as wf:
            ch, sr, sw, n = (wf.getnchannels(), wf.getframerate(),
                             wf.getsampwidth(), wf.getnframes())
            frames = wf.readframes(n)
        out.update({"channels": ch, "sample_rate": sr, "duration_sec": round(n / sr, 4)})
        import array
        a = array.array("h")
        a.frombytes(frames[: (len(frames) // 2) * 2])
        if ch > 1:
            a = array.array("h", [a[i] for i in range(0, len(a) - ch + 1, ch)])
        peak = max((abs(v) for v in a), default=0)
        out["peak_abs"] = peak
        out["peak_sec"] = (max(range(len(a)), key=lambda i: abs(a[i])) / sr
                           if peak else None)
    except Exception as exc:
        out["parse_error"] = str(exc)
    return out


def fetch_audio_bytes(page: Page, selector: str, which: int = 0) -> bytes | None:
    """Fetch what one <audio> element is actually serving, chosen by CSS selector.

    Deliberately not "the last audio element on the page": Step 4 renders the mixed
    export first and then the export library, which renders more audio elements after
    it, so a page-wide last-match would read somebody else's file.
    """
    b64 = page.evaluate(
        """async ([sel, which]) => {
          const scope = document.querySelector(sel);
          if (!scope) return {err: 'scope-not-found'};
          const au = [...scope.querySelectorAll('audio')].filter((a) => a.src);
          if (!au.length) return {err: 'no-audio-in-scope'};
          if (which >= au.length) return {err: 'only-' + au.length + '-audio'};
          const node = which < 0 ? au[au.length - 1] : au[which];
          const r = await fetch(node.src);
          const buf = await r.arrayBuffer();
          let bin = '';
          const v = new Uint8Array(buf);
          for (let i = 0; i < v.length; i += 0x8000) {
            bin += String.fromCharCode.apply(null, v.subarray(i, i + 0x8000));
          }
          return {b64: btoa(bin), count: au.length};
        }""",
        [selector, which],
    )
    if not isinstance(b64, dict) or b64.get("err"):
        log(f"    fetch {selector}[{which}] -> {b64}")
        return None
    return base64.b64decode(b64["b64"])


def fetch_layer_audio(page: Page, slot: str) -> bytes | None:
    """The Original Take Preview for one layer, scoped by its own expander.

    The layer's audio element sits inside the "Layer controls" expander rather than a
    keyed container, so it is found by that expander's summary text.
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
          if (!el) return {err: 'layer-not-found'};
          const au = [...el.querySelectorAll('audio')].filter((a) => a.src);
          if (!au.length) return {err: 'no-audio-in-layer'};
          const r = await fetch(au[0].src);
          const buf = await r.arrayBuffer();
          let bin = '';
          const v = new Uint8Array(buf);
          for (let i = 0; i < v.length; i += 0x8000) {
            bin += String.fromCharCode.apply(null, v.subarray(i, i + 0x8000));
          }
          return {b64: btoa(bin), count: au.length};
        }""",
        slot,
    )
    if not isinstance(b64, dict) or b64.get("err"):
        log(f"    fetch layer audio for {slot} -> {b64}")
        return None
    return base64.b64decode(b64["b64"])


def slider_report(page: Page, slot: str) -> dict:
    """What the Align slider is actually made of, plus its current value.

    An earlier probe assumed ``[role="slider"]`` and found nothing, so the leg silently
    did not run. This reports the structure it finds, so a miss is visible in the log
    rather than looking like a passing test.
    """
    return page.evaluate(
        """(slot) => {
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          if (!el) return {err: 'layer-not-found'};
          const sliders = [...el.querySelectorAll('[data-testid="stSlider"]')];
          const sl = sliders.find((x) => (x.innerText || '').toLowerCase()
                                   .includes('align'));
          if (!sl) return {err: 'align-slider-not-found',
                           sliderTexts: sliders.map((x) => (x.innerText || '').slice(0, 40))};
          const role = sl.querySelector('[role="slider"]');
          const range = sl.querySelector('input[type="range"]');
          const thumb = sl.querySelector('[data-testid="stSliderThumbValue"]');
          return {
            found: true,
            hasRole: !!role, hasRange: !!range, hasThumbValue: !!thumb,
            roleNow: role ? role.getAttribute('aria-valuenow') : null,
            rangeNow: range ? range.value : null,
            thumbText: thumb ? (thumb.innerText || '').trim() : null,
            inner: (sl.innerText || '').replace(/\\n/g, ' | ').slice(0, 80),
          };
        }""",
        slot,
    )


ALIGN_MIN, ALIGN_MAX, ALIGN_STEP = -3.0, 3.0, 0.05


def align_value(page: Page, slot: str) -> float | None:
    rep = slider_report(page, slot)
    shown = rep.get("roleNow") or rep.get("rangeNow") or rep.get("thumbText")
    try:
        return float(str(shown))
    except Exception:
        return None


def set_align(page: Page, slot: str, target: float) -> dict:
    """Put the Align slider on ``target``, then read it back.

    A real mouse press on the track first, because this build renders no
    ``[role="slider"]`` thumb for keyboard focus to land on, and BaseWeb ignores
    synthetic events. Arrow keys then close the remaining gap a step at a time. The
    read-back is what decides whether it worked - never the setter's own return value,
    which is the trap that made an earlier probe report a control it had moved as
    unmoved.
    """
    box = page.evaluate(
        """(slot) => {
          const s = slot.toLowerCase();
          const all = [...document.querySelectorAll('details')];
          const el = all.find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          if (!el) return null;
          const sliders = [...el.querySelectorAll('[data-testid="stSlider"]')];
          const sl = sliders.find((x) => (x.innerText || '').toLowerCase()
                                   .includes('align'));
          if (!sl) return null;
          const track = sl.querySelector('div[data-baseweb="slider"]') || sl;
          track.scrollIntoView({block: 'center'});
          const r = track.getBoundingClientRect();
          return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""",
        slot,
    )
    if not box or not box.get("w"):
        return {"ok": False, "why": "align slider track not found", "box": box}
    frac = (target - ALIGN_MIN) / (ALIGN_MAX - ALIGN_MIN)
    px = box["x"] + box["w"] * frac
    py = box["y"] + box["h"] / 2
    page.mouse.move(px, py)
    page.mouse.down()
    page.mouse.move(px, py)
    page.mouse.up()
    settle(page, 8)
    got = align_value(page, slot)
    log(f"    mouse set Align to about {target:+.2f}, slider reads {got}")
    # Close the last step or two with the keyboard; the thumb has focus after a drag.
    for _ in range(40):
        if got is None or abs(got - target) < ALIGN_STEP / 2:
            break
        page.keyboard.press("ArrowRight" if got < target else "ArrowLeft")
        settle(page, 4)
        nxt = align_value(page, slot)
        if nxt is None or nxt == got:
            break
        got = nxt
    return {"ok": True, "value": got, "after": slider_report(page, slot)}


# ---------------------------------------------------------------------- app driving
def boot(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    waited = 0
    while waited < 150:
        b = page.inner_text("body") or ""
        if len(b.strip()) > 400 and "PAGES" in b.upper():
            return True
        settle(page, 3)
        waited += 3
    return False


def goto_multitrack(page: Page) -> bool:
    if "multitrack session workspace" in low(page.inner_text("body") or ""):
        return True
    click_nav(page, "Multitrack")
    settle(page, 6)
    return "multitrack session workspace" in low(page.inner_text("body") or "")


def play_transport(page: Page, wait_ms: int = 11000) -> dict:
    fr = iframe_frame(page)
    if fr is None:
        return {"err": "no-transport-iframe"}
    try:
        page.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
        fr.evaluate("() => { if (window.__i78) window.__i78.length = 0; }")
    except Exception:
        pass
    fr.evaluate("() => { const b = document.getElementById('mt-play'); if (b) b.click(); }")
    page.wait_for_timeout(wait_ms)
    ev = collect(page)
    srcs = [e for e in ev if e.get("kind") == "bufsrc_start" and e.get("_frame") == "iframe"]
    oscs = [e for e in ev if e.get("kind") == "osc_start" and e.get("_frame") == "iframe"]
    lbs = [float(e["late_by"]) for e in srcs if e.get("late_by") is not None]
    label = fr.evaluate(
        "() => (document.getElementById('mt-playback-label').textContent || '')")
    return {
        "sources": len(srcs), "clicks": len(oscs),
        "worst_late_sec": max(lbs) if lbs else 0.0,
        "smallest_margin_sec": -max(lbs) if lbs else 0.0,
        "whens": sorted({round(float(e["when"]), 5) for e in srcs
                         if e.get("when") is not None}),
        "offsets": sorted({round(float(e.get("offset") or 0), 5) for e in srcs}),
        "label": label,
        "raw": srcs,
    }


# ----------------------------------------------------------------------------- legs
def gate_setup(page: Page) -> bool:
    if not boot(page):
        mark("app boots", False)
        return False
    mark("app boots", True)
    expand_sidebar(page)
    try:
        pick_song(page, NOTES, "Let It Be", "Rock")
        settle(page, 4)
    except Exception as exc:
        log(f"  pick_song raised {exc}")
    if not goto_multitrack(page):
        mark("Multitrack page opens", False)
        return False
    mark("Multitrack page opens", True)
    log(f"  Prepare backing -> {click_text_button(page, 'prepare backing')}")
    settle(page, 14)
    return True


def gate_three_layers_start_together(page: Page, layers: dict) -> None:
    log("\n== three layers, one scheduled instant ==")
    staged = []
    for slot, path in layers.items():
        expand_layer(page, slot)
        settle(page, 2)
        if upload_into_slot(page, slot, path):
            staged.append(slot)
    log(f"  staged {staged}")
    mark("three layers staged", len(staged) == 3, str(staged))
    settle(page, 8)
    res = play_transport(page)
    MEASURED["three_layers"] = {k: v for k, v in res.items() if k != "raw"}
    log(f"  sources={res.get('sources')} clicks={res.get('clicks')} "
        f"margin={res.get('smallest_margin_sec', 0) * 1000:+.1f} ms "
        f"instants={res.get('whens')}")
    log(f"  transport says: {res.get('label')!r}")
    mark("no layer scheduled in the past",
         (res.get("worst_late_sec") or 0) <= 0.0005,
         f"worst {(res.get('worst_late_sec') or 0) * 1000:.1f} ms late")
    mark("every layer shares one scheduled instant",
         len(res.get("whens") or []) == 1, f"instants {res.get('whens')}")


def gate_preview_matches_export(page: Page, slot: str, expect_delay: float) -> None:
    """The Phase B measurement: one offset, two surfaces, same position."""
    log(f"\n== preview vs export at Align {expect_delay:+.2f}s on {slot} ==")
    expand_layer(page, slot)
    settle(page, 3)
    log(f"  slider before: {json.dumps(slider_report(page, slot))}")
    res = set_align(page, slot, expect_delay)
    if not res.get("ok"):
        mark(f"Align {expect_delay:+.2f} can be set", False, str(res))
        return
    log(f"  slider after:  {json.dumps(res.get('after'))}")
    actual = res.get("value")
    if actual is None:
        mark(f"Align {expect_delay:+.2f} can be read back", False, "unreadable")
        return
    mark(f"Align reads back as {expect_delay:+.2f}",
         abs(actual - expect_delay) < ALIGN_STEP / 2, f"slider shows {actual}")
    if abs(actual - expect_delay) >= ALIGN_STEP / 2:
        return
    expect_delay = round(float(actual), 4)

    play = play_transport(page)
    MEASURED[f"transport_at_{expect_delay}"] = {k: v for k, v in play.items()
                                                if k != "raw"}
    log(f"  transport buffer offsets = {play.get('offsets')}")
    want_offset = max(0.0, -expect_delay)
    mark(f"transport applies buffer offset {want_offset:.2f}s",
         any(abs(o - want_offset) < 1e-3 for o in (play.get("offsets") or [])),
         f"offsets {play.get('offsets')}")

    # Position of the transient relative to bar 1, as the transport scheduled it.
    #
    # The layer is identified by its buffer LENGTH, not by its buffer offset. At a
    # positive Align the layer's offset is 0 and so is the backing monitor's, and the
    # backing is scheduled first - so matching on offset picked the backing and reported
    # the transient at 1.0 s regardless of the Align setting. The layer is 6 s; the
    # backing is the whole song.
    preview_pos = None
    srcs = play.get("raw") or []
    if srcs and play.get("whens"):
        bar1 = min(play["whens"])
        layer = next(
            (e for e in srcs
             if e.get("when") is not None
             and abs(float(e.get("buffer_sec") or 0) - LAYER_SEC) < 0.25),
            None,
        )
        if layer is None:
            log("  no 6 s layer source found among "
                f"{[round(float(e.get('buffer_sec') or 0), 2) for e in srcs]}")
        else:
            off = float(layer.get("offset") or 0)
            preview_pos = (float(layer["when"]) - bar1) + (TRANSIENT_AT - off)
            log(f"  layer source: when-bar1={float(layer['when']) - bar1:+.4f}s, "
                f"buffer offset={off:.4f}s, buffer={layer.get('buffer_sec')}s")
    log(f"  preview puts the transient {preview_pos}s after bar 1"
        if preview_pos is not None else "  could not derive the preview position")

    log(f"  Create mixed WAV -> {click_text_button(page, 'create mixed wav')}")
    settle(page, 25)
    raw = fetch_audio_bytes(page, ".st-key-multitrack_export_panel", 0)
    if not raw:
        mark("exported mix can be read back", False)
        return
    (OUT / f"export-align{expect_delay:+.2f}.wav".replace("+", "p")).write_bytes(raw)
    desc = describe_wav(raw)
    MEASURED[f"export_at_{expect_delay}"] = desc
    log(f"  exported WAV: {desc.get('channels')}ch @ {desc.get('sample_rate')}Hz "
        f"{desc.get('duration_sec')}s, transient at {desc.get('peak_sec')}s")
    mark("exported mix can be read back", True)

    export_pos = desc.get("peak_sec")
    expected = TRANSIENT_AT + expect_delay
    if export_pos is None:
        mark("exported transient is locatable", False)
        return
    mark(f"exported transient is at {expected:.2f}s as the contract says",
         abs(export_pos - expected) < 0.06,
         f"measured {export_pos:.4f}s, expected {expected:.2f}s "
         f"(difference {abs(export_pos - expected) * 1000:.1f} ms)")
    if preview_pos is not None:
        diff_ms = abs(preview_pos - export_pos) * 1000
        MEASURED[f"agreement_ms_at_{expect_delay}"] = diff_ms
        mark("preview and export agree on the position", diff_ms < 60,
             f"preview {preview_pos:.4f}s vs export {export_pos:.4f}s "
             f"= {diff_ms:.1f} ms apart")


def gate_dry_take_is_unchanged(page: Page, slot: str, original: Path) -> None:
    log("\n== the stored recording is still the recording ==")
    expand_layer(page, slot)
    settle(page, 3)
    raw = fetch_layer_audio(page, slot)
    if not raw:
        mark("the layer's own audio can be read back", False)
        return
    mark("the layer's own audio can be read back", True)
    desc = describe_wav(raw)
    MEASURED["dry_take"] = desc
    log(f"  stored take: {desc.get('duration_sec')}s @ {desc.get('sample_rate')}Hz, "
        f"transient at {desc.get('peak_sec')}s")
    mark("the stored take still has its full length",
         abs((desc.get("duration_sec") or 0) - LAYER_SEC) < 0.05,
         f"{desc.get('duration_sec')}s vs {LAYER_SEC}s")
    mark("the stored take's transient is where it was recorded",
         abs((desc.get("peak_sec") or -9) - TRANSIENT_AT) < 0.02,
         f"at {desc.get('peak_sec')}s, recorded at {TRANSIENT_AT}s")
    body = page.inner_text("body") or ""
    mark("the panel names this the Original Take Preview",
         "Original Take Preview" in body)
    mark("the panel says the preview is never altered",
         "no alignment or mixing applied" in body)
    mark("the panel says playback and export match each other",
         "they match each other" in body)


def gate_responsive(page: Page, width: int) -> None:
    log(f"\n== {width}px ==")
    page.set_viewport_size({"width": width, "height": 860})
    settle(page, 6)
    info = page.evaluate(
        """() => ({
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth,
          body: (document.body.innerText || '').length,
        })""")
    log(f"  scrollWidth={info['scrollW']} clientWidth={info['clientW']} "
        f"text={info['body']} chars")
    mark(f"{width}px :: no horizontal page scroll",
         info["scrollW"] <= info["clientW"] + 2,
         f"{info['scrollW']} vs {info['clientW']}")
    mark(f"{width}px :: the page still renders", info["body"] > 500,
         f"{info['body']} chars")
    body = page.inner_text("body") or ""
    mark(f"{width}px :: the Align wording is present",
         "bar 1" in body or "original recording" in body)
    page.screenshot(path=str(OUT / f"app-{width}.png"), full_page=True)
    page.set_viewport_size({"width": 1400, "height": 900})
    settle(page, 4)


def main() -> int:
    layers = {
        "guitar": make_layer(WORK / "guitar.wav", freq=196.0, click_at=TRANSIENT_AT),
        "sax / winds": make_layer(WORK / "sax.wav", freq=311.0, click_at=TRANSIENT_AT),
        "extra layer": make_layer(WORK / "flute.wav", freq=587.0, click_at=TRANSIENT_AT),
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
            if not gate_setup(page):
                return 1
            gate_three_layers_start_together(page, layers)
            # Only the guitar keeps its layer in the mix, so the exported transient is
            # unambiguous; the backing is excluded for the same reason.
            for slot in ("sax / winds", "extra layer"):
                expand_layer(page, slot)
                settle(page, 2)
                page.evaluate(
                    """(slot) => {
                      const s = slot.toLowerCase();
                      const all = [...document.querySelectorAll('details')];
                      const el = all.find((d) => {
                        const sum = d.querySelector('summary');
                        const t = ((sum && sum.innerText) || '').toLowerCase();
                        return t.includes('layer controls') && t.includes(s);
                      });
                      if (!el) return;
                      const cbs = [...el.querySelectorAll('[data-testid="stCheckbox"]')];
                      const m = cbs.find((c) => (c.innerText || '').toLowerCase()
                                          .includes('mute'));
                      if (m) { const i = m.querySelector('input'); if (i) i.click(); }
                    }""",
                    slot,
                )
                settle(page, 6)
            log("  muted the other two layers so the exported transient is unambiguous")

            gate_preview_matches_export(page, "guitar", expect_delay=0.5)
            gate_preview_matches_export(page, "guitar", expect_delay=-0.5)
            gate_preview_matches_export(page, "guitar", expect_delay=0.0)
            gate_dry_take_is_unchanged(page, "guitar", layers["guitar"])
            for w in (390, 360):
                gate_responsive(page, w)
            mark("no uncaught JS errors on the page", not errs, str(errs)[:160])
        finally:
            try:
                page.screenshot(path=str(OUT / "app-final.png"), full_page=True)
                (OUT / "app-body.txt").write_text(
                    (page.inner_text("body") or "")[:40000], encoding="utf-8")
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
            (OUT / "app-report.json").write_text(
                json.dumps(report, indent=2, default=str), encoding="utf-8")
            (OUT / "app-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\n{report['passed']}/{report['total']} gates passed")
    if report["failed"]:
        log("FAILED: " + "\n         ".join(report["failed"]))
    log(f"evidence in {OUT}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

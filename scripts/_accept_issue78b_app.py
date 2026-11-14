"""Issue 78B acceptance in the real app: three layers recorded on the shared clock.

The component harness (``_accept_issue78b_recorder.py``) measures the recorder in isolation. This
one runs the whole workflow inside Streamlit, where the session, the media manager, the mixer and
the export all participate - the parts an isolated harness cannot speak for:

  * guitar, then a saxophone overdub, then a flute overdub, each recorded with one Record click,
  * every previously saved layer really being fetched and scheduled as a monitor,
  * Count-in None / 1 bar / 2 bars producing the count-in the setup panel promises,
  * discarding a take and recording it again, with the timing replaced rather than inherited,
  * saving and reloading the project, then mixing and exporting.

Every scheduling claim is measured by instrumenting ``AudioBufferSourceNode.start`` and
``OscillatorNode.start`` in every frame, so a gate compares what the recorder said with what the
AudioContext was really asked to do. This measures the scheduling clock and the captured file; it
is not a claim about acoustic latency. Physical microphone and listening acceptance are separate.

Usage:
  MUSIC_APP_DATA_DIR=<disposable copy> streamlit run streamlit_music_practice_app.py \
      --server.port 8592 --server.headless true
  python scripts/_accept_issue78b_app.py http://127.0.0.1:8592
"""

from __future__ import annotations

import base64
import io
import json
import struct
import sys
import wave
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _probe_i78_recording_clock import click_text_button, expand_layer  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8592"
OUT = SCRIPTS / "evidence-issue78b"
OUT.mkdir(parents=True, exist_ok=True)

SLOT_GUITAR = "guitar"
SLOT_SAX = "sax / winds"
SLOT_EXTRA = "extra layer"

GATES: dict[str, bool] = {}
NOTES: list[str] = []
MEASURED: dict[str, object] = {}

# Instrument every frame. The recorder component is served from the app's own origin, so the same
# init script covers the page, the transport iframe and each recorder iframe; `where` keeps them apart.
INSTRUMENT = """
window.__i78b = [];
(() => {
  const where = () => {
    try { return window.location.pathname + (window === window.parent ? "#top" : "#frame"); }
    catch (e) { return "?"; }
  };
  const B = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function (when, offset) {
    try {
      window.__i78b.push({ kind: "buffer", where: where(), when: Number(when),
                           offset: offset === undefined ? null : Number(offset),
                           now: this.context.currentTime, sr: this.context.sampleRate,
                           duration: this.buffer ? this.buffer.duration : null });
    } catch (e) {}
    return B.apply(this, arguments);
  };
  const O = OscillatorNode.prototype.start;
  OscillatorNode.prototype.start = function (when) {
    try {
      window.__i78b.push({ kind: "click", where: where(), when: Number(when),
                           freq: this.frequency.value, now: this.context.currentTime });
    } catch (e) {}
    return O.apply(this, arguments);
  };
})();
"""


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    # Never let formatting a detail end the run: a failing gate's detail is the most useful
    # thing in the output, and a crash here loses every gate after it as well.
    if not isinstance(detail, str):
        try:
            detail = json.dumps(detail, default=str)
        except Exception:
            detail = repr(detail)
    detail = (detail or '').replace(chr(10), ' | ')[:220]
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}{('  -> ' + detail) if detail else ''}")


def settle(page: Page, s: float = 2.5) -> None:
    page.wait_for_timeout(int(s * 1000))


def low(s: str) -> str:
    return (s or "").lower()


# ---------------------------------------------------------------- the recorder iframes
def tag_recorders(page: Page) -> list[dict]:
    """Mark every recorder iframe so one slot's recorder can be driven on its own.

    Identified by Streamlit's own title attribute (the declared component name) or the component
    src, with contentDocument only as a fallback: that document is not there the instant the element
    is, and depending on it made a present recorder look absent on a busy page.
    """
    return page.evaluate(
        """() => {
          const out = [];
          document.querySelectorAll('iframe').forEach((ifr) => {
            const title = ifr.getAttribute('title') || '';
            const src = ifr.getAttribute('src') || '';
            let isRec = title.indexOf('mission_recorder') >= 0 || src.indexOf('mission_recorder') >= 0;
            if (!isRec) {
              try { isRec = !!(ifr.contentDocument && ifr.contentDocument.getElementById('rec')); }
              catch (e) { isRec = false; }
            }
            if (!isRec) return;
            let ready = false;
            try { ready = !!(ifr.contentDocument && ifr.contentDocument.getElementById('rec')); }
            catch (e) { ready = false; }
            const det = ifr.closest('details');
            const sum = det && det.querySelector('summary');
            ifr.setAttribute('data-i78b', String(out.length));
            out.push({ idx: out.length, ready: ready,
                       summary: ((sum && sum.innerText) || '').trim().slice(0, 80) });
          });
          return out;
        }"""
    )


def recorder_selector(page: Page, slot: str, timeout_s: float = 25.0) -> str | None:
    """The selector for this slot's recorder, waiting for its document rather than assuming it."""
    want = slot.lower()
    waited = 0.0
    last: list[dict] = []
    while waited <= timeout_s:
        last = tag_recorders(page)
        for row in last:
            if want in low(row["summary"]) and row.get("ready"):
                return f'iframe[data-i78b="{row["idx"]}"]'
        page.wait_for_timeout(1000)
        waited += 1.0
    log(f"  no recorder for {slot!r} after {timeout_s:.0f}s; saw {json.dumps(last)[:300]}")
    return None


def recorder_status(page: Page, sel: str) -> str:
    try:
        return page.frame_locator(sel).locator("#status").inner_text()
    except Exception:
        return ""


def clear_probe(page: Page) -> None:
    for fr in page.frames:
        try:
            fr.evaluate("() => { if (window.__i78b) window.__i78b.length = 0; }")
        except Exception:
            pass


def collect_probe(page: Page) -> list[dict]:
    rows: list[dict] = []
    for fr in page.frames:
        try:
            got = fr.evaluate("() => window.__i78b || []")
        except Exception:
            continue
        if got:
            rows.extend(got)
    return rows


def record_in_slot(page: Page, slot: str, seconds: float = 2.0) -> dict:
    """Expand the layer, click Record, wait, click Stop. Returns what was scheduled."""
    expand_layer(page, slot)
    settle(page, 1.5)
    sel = recorder_selector(page, slot)
    if sel is None:
        return {"err": "no-recorder-iframe"}
    btn = page.frame_locator(sel).locator("#rec")
    try:
        if btn.is_disabled():
            return {"err": "record-disabled", "status": recorder_status(page, sel)}
    except Exception as exc:
        return {"err": f"record-unreadable: {exc}"}
    clear_probe(page)
    status_before = recorder_status(page, sel)
    btn.click()
    try:
        page.frame_locator(sel).locator("#rec").wait_for(state="visible", timeout=10000)
        page.wait_for_function(
            """(s) => { const f = document.querySelector(s);
                        const b = f && f.contentDocument && f.contentDocument.getElementById('rec');
                        return !!b && (b.textContent || '').includes('Stop'); }""",
            arg=sel, timeout=15000,
        )
    except Exception as exc:
        return {"err": f"never-started: {exc}", "status": recorder_status(page, sel)}
    page.wait_for_timeout(int(seconds * 1000))
    sched = collect_probe(page)
    page.frame_locator(sel).locator("#rec").click()
    # Stopping posts the take to Streamlit, which reruns the page.
    settle(page, 7)
    return {"sched": sched, "status_before": status_before}


# ---------------------------------------------------------------- app driving
def boot(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    waited = 0
    while waited < 180:
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
    settle(page, 6)
    return "multitrack session workspace" in low(page.inner_text("body") or "")


def count_in_value(page: Page) -> str:
    """The option the Count-in selectbox holds. Its container's text is the LABEL, not the value."""
    return page.evaluate(
        """() => {
          const inputs = [...document.querySelectorAll('input')];
          const box = inputs.find((i) => {
            const wrap = i.closest('[data-testid="stSelectbox"]');
            return wrap && (wrap.innerText || '').toLowerCase().includes('count-in');
          });
          return box ? (box.value || '') : 'gone';
        }"""
    )


def set_count_in(page: Page, label: str) -> str:
    """Set the Count-in selectbox with real mouse events and read the option back.

    BaseWeb's option list does not respond to a dispatched .click(), so a JS click silently left the
    control where it was - which is how two of these options went unverified in the first run.
    """
    for attempt in (1, 2, 3):
        if count_in_value(page) == label:
            return label
        try:
            box = page.locator('[data-testid="stSelectbox"]').filter(has_text="Count-in").first
            box.scroll_into_view_if_needed()
            box.click(timeout=8000)
            page.wait_for_timeout(800)
            opt = page.get_by_role("option", name=label, exact=True).first
            opt.wait_for(state="visible", timeout=6000)
            opt.click(timeout=6000)
        except Exception as exc:
            log(f"  set_count_in({label!r}) attempt {attempt}: {str(exc).splitlines()[0]}")
            # Close any half-open list before trying again, or the next click lands on an option.
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            page.wait_for_timeout(1200)
            continue
        settle(page, 6)
        if count_in_value(page) == label:
            return label
    return count_in_value(page)


def _unused_set_count_in(page: Page, label: str) -> str:
    got = page.evaluate(
        """(want) => {
          const inputs = [...document.querySelectorAll('input')];
          const box = inputs.find((i) => {
            const wrap = i.closest('[data-testid="stSelectbox"]');
            if (!wrap) return false;
            return (wrap.innerText || '').toLowerCase().includes('count-in');
          });
          if (!box) return 'no-selectbox';
          if ((box.value || '') === want) return 'already:' + box.value;
          box.scrollIntoView({block: 'center'});
          box.click();
          return 'opened:' + (box.value || '');
        }""",
        label,
    )
    if got.startswith("already"):
        return got.split(":", 1)[1]
    if got == "no-selectbox":
        return got
    settle(page, 1)
    page.evaluate(
        """(want) => {
          const opts = [...document.querySelectorAll('[role="option"], li')];
          const el = opts.find((o) => (o.innerText || '').trim() === want);
          if (el) el.click();
        }""",
        label,
    )
    settle(page, 5)
    return page.evaluate(
        """() => {
          const inputs = [...document.querySelectorAll('input')];
          const box = inputs.find((i) => {
            const wrap = i.closest('[data-testid="stSelectbox"]');
            return wrap && (wrap.innerText || '').toLowerCase().includes('count-in');
          });
          return box ? (box.value || '') : 'gone';
        }"""
    )


def read_bpm(page: Page) -> float:
    """The session tempo from the app's own slider, so a count-in's length is never assumed."""
    got = page.evaluate(
        """() => {
          const wrap = document.querySelector('.st-key-multitrack_bpm');
          if (!wrap) return null;
          const r = wrap.querySelector('input[type=range]');
          if (r && r.value) return Number(r.value);
          const t = wrap.querySelector('[data-testid="stSliderThumbValue"]');
          return t ? Number((t.innerText || '').replace(/[^0-9.]/g, '')) : null;
        }"""
    )
    try:
        value = float(got)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def count_in_ms(bpm: float, beats: int) -> float:
    """How long ``beats`` of click lasts at ``bpm`` - the number the recorder must reproduce."""
    return 0.0 if bpm <= 0 else beats * 60000.0 / bpm


def layer_has_audio(page: Page, slot: str) -> bool:
    """Whether this slot really holds a take.

    The EMPTY / HAS AUDIO badge is drawn ABOVE the expander, not inside it, so reading the details
    text for "has audio" finds nothing even when a take is there. The Original Take Preview caption
    is rendered only when the slot has audio, so that is the honest indicator.
    """
    return "original take preview" in layer_body(page, slot)


def click_in_layer(page: Page, slot: str, text: str) -> str:
    """Click a button inside ONE layer's controls.

    First-match-in-the-document is the guitar's button whatever slot was intended, which is how a
    discard aimed at the saxophone removed the guitar's take in the first run.
    """
    return page.evaluate(
        """(a) => {
          const s = a.slot.toLowerCase(), w = a.text.toLowerCase();
          const det = [...document.querySelectorAll('details')].find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          if (!det) return 'no-layer';
          const btn = [...det.querySelectorAll('button')]
            .find((b) => (b.innerText || '').toLowerCase().includes(w));
          if (!btn) return 'no-button';
          btn.scrollIntoView({block: 'center'});
          btn.click();
          return 'clicked';
        }""",
        {"slot": slot, "text": text},
    )


def layer_body(page: Page, slot: str) -> str:
    return low(page.evaluate(
        """(slot) => {
          const s = slot.toLowerCase();
          const det = [...document.querySelectorAll('details')].find((d) => {
            const sum = d.querySelector('summary');
            const t = ((sum && sum.innerText) || '').toLowerCase();
            return t.includes('layer controls') && t.includes(s);
          });
          return det ? (det.innerText || '') : '';
        }""",
        slot,
    ))


def export_bytes(page: Page) -> bytes | None:
    """Fetch the exported mix out of the export panel, scoped so it cannot be a layer preview."""
    b64 = page.evaluate(
        """async () => {
          const panel = document.querySelector('.st-key-multitrack_export_panel');
          if (!panel) return null;
          const a = panel.querySelector('audio');
          if (!a || !a.src) return null;
          const res = await fetch(a.src);
          const buf = await res.arrayBuffer();
          const u8 = new Uint8Array(buf);
          let bin = '';
          for (let i = 0; i < u8.length; i += 0x8000)
            bin += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
          return btoa(bin);
        }"""
    )
    return base64.b64decode(b64) if b64 else None


def wav_info(raw: bytes) -> dict:
    with wave.open(io.BytesIO(raw), "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        frames = w.readframes(n)
    vals = struct.unpack("<%dh" % (len(frames) // 2), frames) if frames else ()
    peak = max((abs(v) for v in vals), default=0) / 32768.0
    return {"sample_rate": sr, "frames": n, "channels": ch, "seconds": n / sr if sr else 0.0, "peak": peak}


def buffers(sched, where_frag: str = "#frame") -> list[dict]:
    return [e for e in sched if e["kind"] == "buffer" and where_frag in e.get("where", "")]


def clicks(sched, where_frag: str = "#frame") -> list[dict]:
    return [e for e in sched if e["kind"] == "click" and where_frag in e.get("where", "")]


# ---------------------------------------------------------------- the gates
def gate_setup(page: Page) -> bool:
    if not boot(page):
        mark("the app loads", False)
        return False
    mark("the app loads", True)
    try:
        pick_song(page, NOTES, "Let It Be", "Rock")
    except Exception as exc:
        log(f"  pick_song raised {exc} - continuing with whatever song is active")
    settle(page, 4)
    ok = goto_multitrack(page)
    mark("the Multitrack workspace opens", ok)
    if not ok:
        return False
    got = set_count_in(page, "1 bar")
    mark("Count-in can be set to 1 bar", got == "1 bar", f"reads {got!r}")
    return True


def gate_first_layer(page: Page) -> None:
    log("\n== the first layer: one Record, nothing to play along with ==")
    mark("the run starts with an empty guitar slot, so the counts below mean something",
         not layer_has_audio(page, SLOT_GUITAR),
         "a leftover take would make every monitor count wrong")
    r = record_in_slot(page, SLOT_GUITAR, 2.0)
    if r.get("err"):
        mark("the guitar layer records", False, str(r))
        return
    mark("the guitar layer records", True)
    cl = clicks(r["sched"])
    mark("a 1-bar count-in was heard", len(cl) == 4, f"{len(cl)} clicks scheduled")
    mark("nothing was played along with, there being no other layer",
         len(buffers(r["sched"])) == 0, f"{len(buffers(r['sched']))} sources")
    # The take arrives, the page reruns, and only then is the measurement drawn beside the take.
    # Wait for it rather than assuming one settle() was enough on a loaded machine.
    body = layer_body(page, SLOT_GUITAR)
    waited_line = 0.0
    while waited_line < 30.0 and "measured on the recording clock" not in body:
        page.wait_for_timeout(2000)
        waited_line += 2.0
        body = layer_body(page, SLOT_GUITAR)
    (OUT / "layer-body-guitar.txt").write_text(body, encoding="utf-8")
    mark("the take landed in the layer", layer_has_audio(page, SLOT_GUITAR),
         body[:200].replace("\n", " | "))
    mark("the measured timing is shown with the take", "measured on the recording clock" in body,
         f"after {waited_line:.0f}s: "
         + json.dumps([ln for ln in body.split("\n") if "measured on the recording" in ln][:1]))
    mark("the take is captured at a music rate, not a speech rate",
         "48.0 khz" in body or "44.1 khz" in body,
         [ln for ln in body.split("\n") if "khz" in ln][:1])


def gate_overdub(page: Page, slot: str, expect_monitors: int, label: str) -> dict:
    log(f"\n== {label}: the saved layers must really play while this one records ==")
    r = record_in_slot(page, slot, 2.0)
    if r.get("err"):
        mark(f"{label} records", False, str(r))
        return {}
    mark(f"{label} records", True)
    bufs = buffers(r["sched"])
    mark(f"{label} hears {expect_monitors} saved layer(s)", len(bufs) == expect_monitors,
         f"{len(bufs)} sources scheduled")
    cl = clicks(r["sched"])
    mark(f"{label} is counted in too", len(cl) == 4, f"{len(cl)} clicks")
    if bufs and cl:
        whens = [b["when"] for b in bufs]
        spread_ms = (max(whens) - min(whens)) * 1000.0
        mark(f"{label}'s monitors start at one instant", spread_ms <= 0.03,
             f"spread={spread_ms:.4f} ms")
        after_click_ms = (min(whens) - cl[0]["when"]) * 1000.0
        want_ms = count_in_ms(read_bpm(page), len(cl))
        mark(f"{label}'s monitors start exactly one bar after the first click",
             want_ms > 0 and abs(after_click_ms - want_ms) < 3.0,
             f"{after_click_ms:.2f} ms, one bar at this tempo is {want_ms:.2f} ms")
        leads = [(b["when"] - b["now"]) * 1000.0 for b in bufs]
        mark(f"{label} schedules nothing in the past", min(leads) > 0,
             f"min lead={min(leads):.1f} ms")
    body = layer_body(page, slot)
    mark(f"{label}'s take landed with its own measurement",
         "measured on the recording clock" in body,
         [ln for ln in body.split("\n") if "measured on the recording" in ln][:1])
    mark(f"{label}'s measurement names the parts that were playing",
         f"{expect_monitors} part" in body, f"expected '{expect_monitors} part(s)'")
    MEASURED[label] = {"monitors": len(bufs), "clicks": len(cl)}
    return r


def gate_count_in_choices(page: Page) -> None:
    log("\n== Count-in None / 1 bar / 2 bars ==")
    for label, want_clicks in (("None", 0), ("2 bars", 8), ("1 bar", 4)):
        got = set_count_in(page, label)
        if got != label:
            mark(f"Count-in can be set to {label}", False, f"reads {got!r}")
            continue
        mark(f"Count-in can be set to {label}", True)
        r = record_in_slot(page, SLOT_GUITAR, 1.0 if want_clicks < 8 else 1.0)
        if r.get("err"):
            mark(f"a take with Count-in {label} records", False, str(r))
            continue
        cl = clicks(r["sched"])
        mark(f"Count-in {label} schedules {want_clicks} clicks", len(cl) == want_clicks,
             f"{len(cl)} clicks")
        if want_clicks and len(cl) == want_clicks:
            bufs = buffers(r["sched"])
            if bufs:
                gap_ms = (min(b["when"] for b in bufs) - cl[0]["when"]) * 1000.0
                want_ms = count_in_ms(read_bpm(page), want_clicks)
                mark(f"Count-in {label} puts musical zero {want_ms:.0f} ms after the first click",
                     want_ms > 0 and abs(gap_ms - want_ms) < 3.0,
                     f"{gap_ms:.2f} ms, expected {want_ms:.2f} ms at this tempo")
        MEASURED[f"count-in {label}"] = len(cl)


def gate_one_record_control(page: Page) -> None:
    """One Record, named for what it does - and the old Record-then-Play pair not on offer."""
    log("\n== one Record control, named for what it does ==")
    expand_layer(page, SLOT_GUITAR)
    settle(page, 2)
    sel = recorder_selector(page, SLOT_GUITAR, timeout_s=25.0)
    if sel is None:
        mark("the synchronized recorder is the control the player is given", False, "no recorder iframe")
        return
    label = page.evaluate(
        """(s) => { const f = document.querySelector(s);
                    const b = f && f.contentDocument && f.contentDocument.getElementById('rec');
                    return b ? {text: b.textContent.trim(), aria: b.getAttribute('aria-label')} : null; }""",
        sel,
    )
    mark("the synchronized recorder is the control the player is given", bool(label), json.dumps(label))
    if label:
        says = "count-in" in low(label["text"])
        mark("Record names the count-in it will play", says, json.dumps(label))
        mark("and its accessible name says the same", "count-in" in low(label["aria"] or ""),
             json.dumps(label["aria"]))
    # The old route was: press Record on a plain microphone widget, then press Play. If that widget
    # is still rendered next to the real one, it is still the apparent recommended method.
    basic = page.locator('[data-testid="stAudioInput"]').count()
    mark("the old two-step microphone control is not offered as well", basic == 0,
         f"{basic} st.audio_input widgets on the page")
    body = low(page.locator("body").inner_text())
    mark("and nothing tells the player to use a compatibility recorder",
         "compatibility" not in body,
         f"occurrences of the word 'compatibility' in the page: {body.count('compatibility')}")


def transport_readout(page: Page) -> dict:
    """Position / bar / beat / cursor width from the Multitrack studio transport."""
    return page.evaluate(
        """() => {
            for (const f of document.querySelectorAll('iframe')) {
                let d = null; try { d = f.contentDocument; } catch (e) {}
                if (!d || !d.getElementById('mt-time')) continue;
                const cur = d.getElementById('mt-cursor');
                return {time: (d.getElementById('mt-time').textContent || '').trim(),
                        bar: (d.getElementById('mt-bar').textContent || '').trim(),
                        beat: (d.getElementById('mt-beat').textContent || '').trim(),
                        cursor: cur ? cur.style.width || '0%' : null};
            }
            return null;
        }"""
    )


def start_transport(page: Page) -> bool:
    return bool(page.evaluate(
        """() => {
            for (const f of document.querySelectorAll('iframe')) {
                let d = null; try { d = f.contentDocument; } catch (e) {}
                if (!d || !d.getElementById('mt-play')) continue;
                d.getElementById('mt-play').click();
                return true;
            }
            return false;
        }"""
    ))


def gate_discard_resets_the_transport(page: Page) -> None:
    """A discarded take must not leave the playhead and the chord cursor mid-song."""
    log("\n== discarding a take returns the transport to the beginning ==")
    before = transport_readout(page)
    if before is None:
        mark("the transport readout can be read", False, "no mt-studio transport found")
        return
    mark("the transport readout can be read", True, json.dumps(before))
    if not start_transport(page):
        mark("the transport can be started", False)
        return
    # Play begins with the transport's own count-in, during which the position legitimately stays
    # at zero. Poll until it moves rather than guessing how long that takes.
    running = None
    moved = False
    waited_play = 0.0
    while waited_play < 18.0:
        page.wait_for_timeout(1000)
        waited_play += 1.0
        running = transport_readout(page)
        if running and running["time"] not in ("0.0s", "0s", "", None):
            moved = True
            break
    mark("the transport really was running before the discard", moved,
         f"after {waited_play:.0f}s: {json.dumps(running)}")
    got = click_in_layer(page, SLOT_EXTRA, "discard")
    waited = 0.0
    while waited < 60.0 and layer_has_audio(page, SLOT_EXTRA):
        page.wait_for_timeout(1500)
        waited += 1.5
    settle(page, 3)
    after = transport_readout(page)
    mark("the take was discarded", got == "clicked" and not layer_has_audio(page, SLOT_EXTRA),
         f"click={got} after {waited:.1f}s")
    if after is None:
        mark("the transport is back at the beginning after a discard", False, "no readout")
        return
    at_start = (
        after["time"] in ("0.0s", "0s")
        and after["bar"] == "1"
        and after["beat"] == "1"
    )
    mark("the transport is back at the beginning after a discard", at_start, json.dumps(after))
    zeroed = after["cursor"] in ("0%", "", None) or str(after["cursor"]).startswith("0%")
    mark("and the chord cursor is back at the first bar", zeroed, json.dumps(after["cursor"]))
    # Put the layer back, so the gates after this one see the three-layer project they expect.
    again = record_in_slot(page, SLOT_EXTRA, 2.0)
    mark("the discarded layer can be recorded again", not again.get("err"),
         str(again.get("err") or ""))


def gate_discard_and_rerecord(page: Page) -> None:
    log("\n== discard one take and record it again ==")
    expand_layer(page, SLOT_SAX)
    settle(page, 1.5)
    before = layer_body(page, SLOT_SAX)
    had_timing = "measured on the recording clock" in before
    got = click_in_layer(page, SLOT_SAX, "discard")
    # Discarding reruns the page; wait for the slot to actually empty rather than for a fixed time.
    # Generously: under load this took 25.5 s where an unloaded machine needed 4.5 s.
    waited = 0.0
    while waited < 60.0 and layer_has_audio(page, SLOT_SAX):
        page.wait_for_timeout(1500)
        waited += 1.5
    log(f"  the slot emptied after {waited:.1f}s")
    after = layer_body(page, SLOT_SAX)
    mark("the take can be discarded", got == "clicked" and not layer_has_audio(page, SLOT_SAX),
         f"click={got}, emptied after {waited:.1f}s, still holds audio={layer_has_audio(page, SLOT_SAX)}")
    mark("discarding one layer leaves the others alone",
         layer_has_audio(page, SLOT_GUITAR) and layer_has_audio(page, SLOT_EXTRA),
         f"guitar={layer_has_audio(page, SLOT_GUITAR)} flute={layer_has_audio(page, SLOT_EXTRA)}")
    mark("discarding the take discards its measurement, so it cannot describe another take",
         had_timing and "measured on the recording clock" not in after,
         f"had={had_timing} still={'measured on the recording clock' in after}")
    r = record_in_slot(page, SLOT_SAX, 2.0)
    mark("the layer can be recorded again after a discard", not r.get("err"), str(r.get("err") or ""))
    again = layer_body(page, SLOT_SAX)
    mark("the re-recorded take carries a fresh measurement",
         "measured on the recording clock" in again)


def gate_save_reload_export(page: Page) -> None:
    log("\n== save the layers, reload, then mix and export ==")
    saved = 0
    held = []
    for slot in (SLOT_GUITAR, SLOT_SAX, SLOT_EXTRA):
        expand_layer(page, slot)
        settle(page, 1.5)
        if not layer_has_audio(page, slot):
            continue
        held.append(slot)
        if click_in_layer(page, slot, "save layer") == "clicked":
            settle(page, 7)
            saved += 1
    mark("every layer holding a take can be saved", saved == len(held) and saved >= 2,
         f"{saved} saved of {len(held)} holding audio: {held}")

    page.reload(wait_until="domcontentloaded")
    settle(page, 20)
    ok = goto_multitrack(page)
    mark("the workspace comes back after a reload", ok)
    if ok:
        kept = [s for s in (SLOT_GUITAR, SLOT_SAX, SLOT_EXTRA) if layer_has_audio(page, s)]
        mark("the saved layers survive the reload", len(kept) >= 2,
             f"{len(kept)} layers still hold audio: {kept}")
        # The audio coming back is not enough: a reloaded layer whose measurement was lost could
        # no longer be placed, and nothing on screen would say so.
        measured = []
        for slot in kept:
            expand_layer(page, slot)
            settle(page, 2)
            body = layer_body(page, slot)
            if "measured on the recording clock" in body:
                measured.append(slot)
        mark("the measured timing survives the save and the reload", len(measured) >= 1,
             f"{len(measured)} of {len(kept)} reloaded layers still show their measurement: {measured}")
        contradictory = [s for s in measured if "not time-aligned" in layer_body(page, s)]
        mark("and no reloaded layer claims a measurement it does not have",
             not contradictory,
             f"layers showing both a measurement and a not-aligned notice: {contradictory}")

    click_text_button(page, "Create mix")
    settle(page, 8)
    # Mixing three layers and rendering the panel takes as long as it takes.
    raw = export_bytes(page)
    waited_mix = 0.0
    while raw is None and waited_mix < 90.0:
        page.wait_for_timeout(3000)
        waited_mix += 3.0
        raw = export_bytes(page)
    if raw is None:
        mark("a mix can be exported", False, f"no audio in the export panel after {waited_mix:.0f}s")
        return
    info = wav_info(raw)
    info["waited_s"] = waited_mix
    MEASURED["export"] = info
    mark("a mix can be exported", True, json.dumps(info))
    mark("the exported mix is not silent", info["peak"] > 0.001, f"peak={info['peak']:.4f}")
    mark("the exported mix is as long as a take, not a fragment", info["seconds"] > 1.0,
         f"{info['seconds']:.2f}s")
    mark("the export keeps a music sample rate", info["sample_rate"] >= 44100,
         f"{info['sample_rate']} Hz")


def gate_responsive(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 780})
    settle(page, 4)
    expand_layer(page, SLOT_GUITAR)
    settle(page, 2)
    sel = recorder_selector(page, SLOT_GUITAR, timeout_s=12.0)
    if sel is None:
        mark(f"the recorder is present at {width} px", False)
        return
    box = page.evaluate(
        """(s) => { const f = document.querySelector(s);
                    const b = f && f.contentDocument && f.contentDocument.getElementById('rec');
                    if (!b) return null;
                    const r = b.getBoundingClientRect();
                    const fr = f.getBoundingClientRect();
                    return {w: r.width, h: r.height, right: r.right, frameW: fr.width}; }""",
        sel,
    )
    mark(f"the Record button is visible at {width} px", bool(box and box["w"] > 40 and box["h"] > 20),
         json.dumps(box))
    if box:
        mark(f"the Record button is not clipped at {width} px", box["right"] <= box["frameW"] + 1,
             f"right={box['right']:.0f} frame={box['frameW']:.0f}")
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    mark(f"no horizontal page scroll at {width} px", over <= 2, f"overflow={over}px")
    page.set_viewport_size({"width": 1400, "height": 900})
    settle(page, 3)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                  permissions=["microphone"])
        ctx.add_init_script(INSTRUMENT)
        page = ctx.new_page()
        page.set_default_timeout(45000)
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        report: dict = {}
        try:
            if not gate_setup(page):
                raise SystemExit(1)
            gate_first_layer(page)
            gate_overdub(page, SLOT_SAX, 1, "the saxophone overdub")
            gate_overdub(page, SLOT_EXTRA, 2, "the flute overdub")
            gate_count_in_choices(page)
            gate_one_record_control(page)
            gate_discard_resets_the_transport(page)
            gate_discard_and_rerecord(page)
            gate_save_reload_export(page)
            for w in (390, 360):
                gate_responsive(page, w)
            mark("no uncaught JS errors on the page", not errs, str(errs)[:200])
        finally:
            try:
                page.screenshot(path=str(OUT / "app-final.png"), full_page=True)
                (OUT / "app-body.txt").write_text((page.inner_text("body") or "")[:40000],
                                                  encoding="utf-8")
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
            (OUT / "app-report.json").write_text(json.dumps(report, indent=2, default=str),
                                                 encoding="utf-8")
            (OUT / "app-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    log(f"\n{report['passed']}/{report['total']} gates passed")
    for name in report["failed"]:
        log(f"  FAILED: {name}")
    log(f"evidence in {OUT}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

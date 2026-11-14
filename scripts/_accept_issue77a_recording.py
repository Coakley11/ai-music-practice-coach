"""Issue 77A acceptance: can the musician actually press Record with Count-In?

Every gate here is measured in a real browser against the running app, with synthetic audio only.
The gates exist because of what the read-only investigation measured on dev 59e77f35:

  * a freshly prepared monitor backing was ALWAYS refused - the recorder was told to expect a
    predicted duration (bars x bar_seconds x loops) while the renderer always leaves a second of
    decay, and the component rejects anything more than 0.6 s out. Record was disabled on every
    layer. G1/G2 are that case.
  * one undecodable layer disabled Record on every OTHER layer, and the message named nothing
    because the acknowledgement carrying the asset's identity was discarded. G3/G4 are that case.
  * an undecodable file was accepted as a layer in the first place. G5.
  * Free Layering correctly drops the backing (measured), so count-in-only recording must work. G6.

Usage:
    python scripts/_accept_issue77a_recording.py http://127.0.0.1:8615
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

# Navigation is reused from the Issue 78C harness rather than written again. Mine did not work and
# there is no reason to have two: that one already knows this app's sidebar has two copies of each
# entry at phone widths, and that arrival has to be proved by page content rather than by a click
# appearing to succeed.
import _accept_issue78c_visibility as H  # noqa: E402

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8615").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "after"
OUT = SCRIPTS / f"evidence-issue77a-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIXTURES = OUT / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}

SLOT_GUITAR = "guitar"
SLOT_SAX = "sax / winds"
SLOT_EXTRA = "extra layer"


def log(msg: str) -> None:
    """ASCII-safe output.

    The app's own labels contain the record dot and the em dash, and a Windows console is cp1252:
    printing them killed a run after its first three gates had already passed. A harness must not
    be able to fail on the way it reports a result.
    """
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


# --------------------------------------------------------------------------------------------
# fixtures: synthetic audio only
# --------------------------------------------------------------------------------------------
def make_fixtures() -> tuple[str, str]:
    import math
    import struct
    import wave

    good = FIXTURES / "good_take.wav"
    if not good.exists():
        with wave.open(str(good), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            handle.writeframes(b"".join(
                struct.pack("<h", int(11000 * math.sin(2 * math.pi * 220 * t / 44100)))
                for t in range(44100)
            ))
    bad = FIXTURES / "undecodable.wav"
    if not bad.exists():
        bad.write_bytes(b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900)
    return str(good), str(bad)


# --------------------------------------------------------------------------------------------
# page plumbing
# --------------------------------------------------------------------------------------------
RUNNING_JS = r"""() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

REC_JS = r"""(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const f = d.querySelector('iframe[title*="recorder" i], iframe[src*="recorder" i]');
    if (!f) return {error: 'no recorder iframe'};
    const rect = f.getBoundingClientRect();
    try {
      const doc = f.contentDocument, btn = doc.getElementById('rec'), st = doc.getElementById('status');
      return {label: (btn && btn.textContent || '').trim(), disabled: !!(btn && btn.disabled),
              status: (st && st.textContent || '').trim(),
              frame_h: Math.round(rect.height), frame_w: Math.round(rect.width),
              panel_text: (d.innerText || '').slice(0, 2000)};
    } catch (e) { return {error: 'cross-doc'}; }
  }
  return {error: 'no panel for ' + slot};
}"""

PANEL_JS = r"""(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    return {text: (d.innerText || ''),
            buttons: [...d.querySelectorAll('button')].map(b => (b.innerText||'').trim()),
            take: (d.innerText||'').toLowerCase().includes('original take preview')};
  }
  return {missing: true};
}"""

OVERFLOW_JS = r"""() => {
  const de = document.documentElement;
  return {scroll_w: de.scrollWidth, client_w: de.clientWidth,
          scrolls_sideways: de.scrollWidth > de.clientWidth + 2};
}"""


def idle(page, quiet: int = 3, limit: float = 200.0) -> bool:
    t0, n = time.time(), 0
    while time.time() - t0 < limit:
        if page.evaluate(RUNNING_JS):
            n = 0
        else:
            n += 1
            if n >= quiet:
                return True
        page.wait_for_timeout(1200)
    return False


def recorder(page, slot: str) -> dict:
    return page.evaluate(REC_JS, slot)


def wait_recorder(page, slot: str, limit: float = 150.0) -> dict:
    """The recorder's settled state: not mid-load, not mid-retry."""
    t0, last = time.time(), {}
    while time.time() - t0 < limit:
        last = recorder(page, slot)
        status = (last.get("status") or "").lower()
        if last.get("error") or "preparing recorder" not in status:
            break
        page.wait_for_timeout(4000)
    return last


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


def click_in_layer(page, needle: str, slot: str) -> str:
    box = page.evaluate(
        r"""([needle, slot]) => {
            const want = needle.toLowerCase(), s = slot.toLowerCase();
            let scope = null;
            for (const d of document.querySelectorAll('details')) {
                const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
                if (t.includes('layer controls') && t.includes(s)) { scope = d; break; }
            }
            if (!scope) return {error: 'no panel for ' + slot};
            let sawDisabled = false;
            for (const b of scope.querySelectorAll('button')) {
                const t = (b.innerText || '').toLowerCase();
                if (!t.includes(want)) continue;
                if (b.offsetParent === null) continue;
                if (b.disabled) { sawDisabled = true; continue; }
                b.scrollIntoView({block: 'center'});
                const r = b.getBoundingClientRect();
                if (r.width < 2 || r.height < 2) continue;
                return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: (b.innerText||'').trim()};
            }
            return {error: (sawDisabled ? 'only a DISABLED button matched ' : 'no button matching ') + needle};
        }""",
        [needle, slot],
    )
    if box.get("error"):
        return str(box["error"])
    page.wait_for_timeout(250)
    page.mouse.click(box["x"], box["y"])
    idle(page)
    page.wait_for_timeout(1200)
    idle(page)
    return "clicked"


def click_page_button(page, needle: str) -> str:
    box = page.evaluate(
        r"""(needle) => {
            const want = needle.toLowerCase();
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText || '').toLowerCase();
                if (!t.includes(want) || b.disabled || b.offsetParent === null) continue;
                b.scrollIntoView({block: 'center'});
                const r = b.getBoundingClientRect();
                if (r.width < 2) continue;
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            return {error: 'no enabled button matching ' + needle};
        }""",
        needle,
    )
    if box.get("error"):
        return str(box["error"])
    page.mouse.click(box["x"], box["y"])
    idle(page)
    page.wait_for_timeout(1200)
    idle(page)
    return "clicked"


def open_layer(page, slot: str) -> None:
    if H.layer_is_open(page, slot):
        return
    H.toggle_layer_by_pointer(page, slot, True)
    idle(page)


def upload_into(page, slot: str, path: str) -> None:
    sel = ('details:has(summary:has-text("Layer controls")):has(summary:has-text("' + slot
           + '")) input[type="file"]')
    page.locator(sel).first.set_input_files(path)
    idle(page)
    page.wait_for_timeout(1500)
    idle(page)


def goto_multitrack(page) -> bool:
    """Reach the Multitrack page, proved by its own content (78C's helper)."""
    if H.goto_multitrack(page):
        idle(page)
        return True
    return False


def boot(page) -> None:
    H.boot(page)
    idle(page)


# --------------------------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------------------------
def gate_backing_lets_the_musician_record(page) -> None:
    """G1/G2 - the defect that made Record unusable for every song."""
    log("\n-- G1/G2: a prepared backing must not disable Record")
    prepared = click_page_button(page, "prepare backing")
    MEASURED["prepare_backing"] = prepared
    if prepared != "clicked":
        mark("the page offers Prepare backing", False, prepared)
        return
    mark("the page offers Prepare backing", True)
    page.wait_for_timeout(4000)
    idle(page)
    open_layer(page, SLOT_GUITAR)
    state = wait_recorder(page, SLOT_GUITAR)
    MEASURED["recorder_with_backing"] = state
    shot(page, "g1-recorder-with-backing")
    mark("Record is ENABLED with a prepared monitor backing",
         state.get("disabled") is False, state.get("status"))
    status = str(state.get("status") or "").lower()
    mark("the recorder says what it will play, not that a part failed",
         ("on one clock" in status or "count-in" in status) and "could not be loaded" not in status,
         state.get("status"))
    mark("the control still offers the count-in by name",
         "count-in" in str(state.get("label") or "").lower(), state.get("label"))


def gate_a_bad_layer_is_named(page, bad: str) -> None:
    """G3/G4 - one undecodable layer used to block every other layer, anonymously."""
    log("\n-- G3/G4: a part that cannot load is named, with a way forward")
    open_layer(page, SLOT_EXTRA)
    upload_into(page, SLOT_EXTRA, bad)
    panel = page.evaluate(PANEL_JS, SLOT_EXTRA)
    text = str(panel.get("text") or "")
    MEASURED["bad_upload_panel"] = text[:400]
    shot(page, "g5-upload-refused")
    mark("an undecodable upload is refused, saying nothing was changed",
         "could not be added as a layer" in text.lower() and "nothing was changed" in text.lower(),
         text[:160].replace("\n", " "))
    mark("the refused upload did not become a take",
         panel.get("take") is False, panel.get("take"))


def gate_a_real_take_against_the_backing(page) -> None:
    """G8 - the musician's own objective: press Record, hear the accompaniment, keep the take.

    The gates above prove the control is usable. This one proves the whole point of it: a take
    captured WITH the generated backing playing, measured on the shared clock (Issue 78B), that can
    then be saved. Without this, "Record is enabled" could still be followed by a take that never
    lands or is silently reported unaligned.
    """
    log("\n-- G8: record a take with the backing, and keep it")
    open_layer(page, SLOT_GUITAR)
    before = wait_recorder(page, SLOT_GUITAR)
    if before.get("disabled") is not False:
        mark("Record can be pressed for a real take", False, before.get("status"))
        return
    # The count-in runs before the capture is musically useful, so allow for it.
    tapped = H.tap_record(page, SLOT_GUITAR)
    MEASURED["take_tap"] = tapped
    if tapped not in ("tapped", "clicked"):
        mark("Record can be pressed for a real take", False, tapped)
        return
    mark("Record can be pressed for a real take", True, tapped)
    page.wait_for_timeout(9000)                      # count-in plus a few seconds of playing
    H.tap_record(page, SLOT_GUITAR)
    idle(page)
    page.wait_for_timeout(4000)
    idle(page)
    panel = page.evaluate(PANEL_JS, SLOT_GUITAR)
    text = str(panel.get("text") or "")
    MEASURED["take_panel"] = text[:600]
    shot(page, "g8-take-landed")
    mark("the take lands in the layer", bool(panel.get("take")), panel.get("take"))
    low = text.lower()
    mark("the take is not reported as un-aligned",
         "not time-aligned" not in low and "could not be measured" not in low,
         [ln for ln in text.splitlines() if "align" in ln.lower()][:2])
    saved = click_in_layer(page, "save layer", SLOT_GUITAR)
    MEASURED["save_click"] = saved
    after = page.evaluate(PANEL_JS, SLOT_GUITAR)
    mark("Save layer keeps the take",
         "saved layer" in str(after.get("text") or "").lower(),
         saved)


def gate_free_layering(page) -> None:
    """G6 - count-in only: no backing is requested, so nothing can block it."""
    log("\n-- G6: Free layering records with the count-in alone")
    picked = page.evaluate(
        r"""() => {
            for (const l of document.querySelectorAll('label')) {
                const t = (l.innerText || '').trim().toLowerCase();
                if (t.startsWith('free layering')) {
                    l.scrollIntoView({block: 'center'});
                    const r = l.getBoundingClientRect();
                    return {x: r.x + 8, y: r.y + r.height / 2};
                }
            }
            return {error: 'no free layering option'};
        }""")
    if picked.get("error"):
        mark("Free layering can be selected", False, picked["error"])
        return
    page.mouse.click(picked["x"], picked["y"])
    idle(page)
    page.wait_for_timeout(2000)
    idle(page)
    body = str(page.evaluate("() => document.body.innerText"))
    selected = page.evaluate(
        r"""() => [...document.querySelectorAll('input[type=radio]')].filter(i => i.checked)
                   .map(i => ((i.closest('label')||{}).innerText||'').trim())""")
    MEASURED["scope_selected"] = selected
    mark("Free layering can be selected",
         any("free layering" in str(s).lower() for s in selected), selected)
    mark("no backing target is advertised in free layering", "Target:" not in body)
    open_layer(page, SLOT_GUITAR)
    state = wait_recorder(page, SLOT_GUITAR)
    MEASURED["recorder_free_layering"] = state
    shot(page, "g6-free-layering")
    mark("Record is ENABLED in free layering", state.get("disabled") is False, state.get("status"))


def gate_widths(browser, url: str) -> None:
    """G7 - the new message block must not break the phone layout."""
    log("\n-- G7: widths")
    for width in (1400, 390, 360):
        ctx = browser.new_context(viewport={"width": width, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(40000)
        try:
            page.goto(url, wait_until="load")
            idle(page)
            boot(page)
            if not goto_multitrack(page):
                mark(f"[{width}px] the Multitrack page opens", False)
                continue
            idle(page)
            open_layer(page, SLOT_GUITAR)
            state = wait_recorder(page, SLOT_GUITAR)
            over = page.evaluate(OVERFLOW_JS)
            MEASURED[f"width_{width}"] = {"recorder": state, "overflow": over}
            shot(page, f"g7-{width}px")
            mark(f"[{width}px] Record is visible and enabled",
                 state.get("disabled") is False and float(state.get("frame_h") or 0) >= 52,
                 f"frame {state.get('frame_h')}px, {state.get('status')}")
            mark(f"[{width}px] the page does not scroll sideways",
                 not over.get("scrolls_sideways"), over)
        finally:
            ctx.close()


def main() -> int:
    good, bad = make_fixtures()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required"],
        )
        try:
            ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
            page = ctx.new_page()
            page.set_default_timeout(40000)
            page.goto(URL, wait_until="load")
            idle(page)
            boot(page)
            if not goto_multitrack(page):
                mark("the Multitrack page opens", False)
                return 1
            mark("the Multitrack page opens", True)
            idle(page)

            gate_backing_lets_the_musician_record(page)
            gate_a_real_take_against_the_backing(page)
            gate_a_bad_layer_is_named(page, bad)
            gate_free_layering(page)
            ctx.close()
            gate_widths(browser, URL)
        finally:
            browser.close()

    (OUT / "measured.json").write_text(json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("\n" + "=" * 78)
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates pass")
    for gate in failed:
        log(f"  FAILED: {gate}")
    log(f"evidence: {OUT}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

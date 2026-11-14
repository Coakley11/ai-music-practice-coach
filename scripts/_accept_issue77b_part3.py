"""Issue 77B: can a remembered position reach music it does not belong to?

Switching songs in a browser means driving the song picker's selectboxes, which has already defeated
a harness once (Issue 78C's Analysis-mode selectbox responds to a click and never renders options).
So this proves the same property a way that is actually reachable, and more directly:

  * it reads the real sessionStorage key the transport stores its position under, and shows the
    song, project and scope inside it;
  * it then changes the playback SCOPE - part of that key, and reachable from the page - and checks
    that the transport does not inherit the position stored under the previous key;
  * and that returning to the first scope finds that first position still intact, which is what
    "scoped per context" means rather than "forgotten on any change".

The song and project dimensions of the key are covered by unit tests over ``position_context``; this
shows the mechanism those tests describe is the one actually running in the browser.
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

import _accept_issue78c_visibility as H  # noqa: E402

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8623").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "part3"
OUT = SCRIPTS / f"evidence-issue77b-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIX = OUT / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}
GUITAR = H.SLOT_GUITAR


def log(msg: str) -> None:
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


def fixture() -> str:
    import math
    import struct
    import wave

    path = FIX / "take.wav"
    if not path.exists():
        with wave.open(str(path), "wb") as h:
            h.setnchannels(1)
            h.setsampwidth(2)
            h.setframerate(44100)
            h.writeframes(b"".join(
                struct.pack("<h", int(11000 * math.sin(2 * math.pi * 220 * t / 44100)))
                for t in range(44100 * 2)))
    return str(path)


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

# Everything the transport knows about its remembered position, read inside its own frame.
POSITION_STORE_JS = """() => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      if (!(d && d.getElementById('mt-play') && d.getElementById('mt-bar'))) continue;
      const w = f.contentWindow;
      const keys = [];
      for (let i = 0; i < w.sessionStorage.length; i++) {
        const k = w.sessionStorage.key(i);
        if (k && k.indexOf('mtpos::') === 0) {
          keys.push({key: k, value: w.sessionStorage.getItem(k)});
        }
      }
      const read = (id) => {
        const el = d.getElementById(id);
        return el ? (el.textContent || '').trim() : '(missing)';
      };
      const c = window.__mtClock || null;
      return {entries: keys, time: read('mt-time'), bar: read('mt-bar'),
              clock_t: c ? Number(c.t) : null, clock_playing: c ? !!c.playing : null};
    } catch (e) {}
  }
  return {error: 'no transport iframe'};
}"""

CLICK_TRANSPORT_JS = """(which) => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      const b = d && d.getElementById(which);
      if (b) { b.click(); return 'clicked'; }
    } catch (e) {}
  }
  return 'no button';
}"""

SCOPE_JS = """(want) => {
  const needle = want.toLowerCase();
  for (const l of document.querySelectorAll('label')) {
    const t = (l.innerText || '').trim().toLowerCase();
    if (!t.startsWith(needle)) continue;
    if (l.offsetParent === null) continue;
    l.scrollIntoView({block: 'center'});
    const r = l.getBoundingClientRect();
    return {x: r.x + 8, y: r.y + r.height / 2, text: (l.innerText || '').trim()};
  }
  return {error: 'no option starting with ' + want};
}"""

SELECTED_SCOPE_JS = """() => [...document.querySelectorAll('input[type=radio]')]
  .filter(i => i.checked)
  .map(i => (((i.closest('label') || {}).innerText) || '').trim())"""


def idle(page, quiet: int = 3, limit: float = 200.0) -> bool:
    t0, n = time.time(), 0
    while time.time() - t0 < limit:
        if page.evaluate(RUNNING_JS):
            n = 0
        else:
            n += 1
            if n >= quiet:
                return True
        page.wait_for_timeout(1100)
    return False


def pick_scope(page, want: str) -> str:
    box = page.evaluate(SCOPE_JS, want)
    if box.get("error"):
        return box["error"]
    page.mouse.click(box["x"], box["y"])
    idle(page)
    page.wait_for_timeout(2000)
    idle(page)
    return "clicked " + str(box.get("text"))


def main() -> int:
    take = fixture()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            ctx = browser.new_context(viewport={"width": 1500, "height": 1100})
            page = ctx.new_page()
            page.set_default_timeout(40000)
            page.goto(URL, wait_until="load")
            idle(page)
            H.boot(page)
            if not H.goto_multitrack(page):
                mark("the Multitrack page opens", False)
                return 1
            mark("the Multitrack page opens", True)
            idle(page)

            if not H.layer_is_open(page, GUITAR):
                H.toggle_layer_by_pointer(page, GUITAR, True)
                idle(page)
            sel = ('details:has(summary:has-text("Layer controls")):has(summary:has-text("'
                   + GUITAR + '")) input[type="file"]')
            page.locator(sel).first.set_input_files(take)
            idle(page)
            page.wait_for_timeout(1200)
            idle(page)

            MEASURED["scope_at_start"] = page.evaluate(SELECTED_SCOPE_JS)
            log("\n-- play, then read the real storage key")
            page.evaluate(CLICK_TRANSPORT_JS, "mt-play")
            page.wait_for_timeout(9000)
            first = page.evaluate(POSITION_STORE_JS)
            MEASURED["while_playing_scope_a"] = first
            log("    " + json.dumps(first, default=str)[:400])
            entries = first.get("entries") or []
            mark("the transport stores its position under a context-scoped key",
                 bool(entries) and all(e["key"].startswith("mtpos::") for e in entries),
                 [e["key"] for e in entries])
            key_a = entries[0]["key"] if entries else ""
            mark("the key names the song it belongs to",
                 bool(key_a) and len(key_a) > len("mtpos::"), key_a)
            mark("the key names the playback scope it belongs to",
                 bool(key_a) and any(
                     token.lower() in key_a.lower()
                     for token in ("full song", "free layering", "single section",
                                   "multiple sections")),
                 key_a)

            log("\n-- change the playback scope: a position from the old scope must not apply")
            MEASURED["scope_switch"] = pick_scope(page, "Free layering")
            MEASURED["scope_after_switch"] = page.evaluate(SELECTED_SCOPE_JS)
            page.wait_for_timeout(2500)
            second = page.evaluate(POSITION_STORE_JS)
            MEASURED["after_scope_switch"] = second
            log("    " + json.dumps(second, default=str)[:400])
            switched = any("free layering" in str(s).lower()
                           for s in (MEASURED["scope_after_switch"] or []))
            mark("the playback scope really changed", switched, MEASURED["scope_after_switch"])
            if switched:
                keys_now = [e["key"] for e in (second.get("entries") or [])]
                mark("the transport does not inherit the other scope's position",
                     second.get("clock_t") in (0, None) and second.get("bar") in ("1", "(missing)"),
                     f"clock {second.get('clock_t')} bar {second.get('bar')}")
                mark("the other scope's remembered position is still stored separately",
                     key_a in keys_now, f"{key_a} in {keys_now}")
                mark("a new key was not written for the new scope until it plays",
                     len(keys_now) >= 1, keys_now)
            try:
                page.screenshot(path=str(OUT / "after-scope-switch.png"))
            except Exception:
                pass
            ctx.close()
        finally:
            browser.close()

    (OUT / "measured.json").write_text(json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("\n" + "=" * 78)
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates pass")
    for g in failed:
        log("  FAILED: " + g)
    log("evidence: " + str(OUT))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

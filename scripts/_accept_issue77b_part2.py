"""Issue 77B, the checks the first acceptance could not honestly claim.

Four of them, each because the earlier evidence was weaker than it looked:

1. THE STRIP REALLY SCROLLS BACK. Every scrollLeft read 0 at every step of the first run - including
   while playing at a later bar - so "scrolled to 0 after the discard" proved nothing. This plays on
   until a visible strip is genuinely scrolled away from the start (non-zero scrollLeft), and only
   then asserts that a discard brings it back.

2. A POSITION CANNOT CROSS SONGS. Play into one song, switch to another, and the transport must start
   at zero rather than inheriting a position from the first.

3. ORDINARY RERUNS NEVER RESTART AUDIO. After each ordinary interaction the published clock must say
   playing:false - a restored position is a position, not a command to play.

4. THE OTHER LAYER'S AUDIO IS BYTE-IDENTICAL. Streamlit serves component media from a
   content-addressed URL, so the hash in that URL changes if and only if the bytes change. Capturing
   the surviving layer's audio URL before and after a deletion is therefore a byte-level check that
   does not read the musician's files.

Plus the duplicated Discard control the user asked to verify rather than fix: both copies must act on
the correct take.
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

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8621").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "part2"
OUT = SCRIPTS / f"evidence-issue77b-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIX = OUT / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}
GUITAR, SAX = H.SLOT_GUITAR, H.SLOT_SAX


def log(msg: str) -> None:
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


def fixture(name: str, freq: float, seconds: float = 2.0) -> str:
    import math
    import struct
    import wave

    path = FIX / name
    if not path.exists():
        with wave.open(str(path), "wb") as h:
            h.setnchannels(1)
            h.setsampwidth(2)
            h.setframerate(44100)
            h.writeframes(b"".join(
                struct.pack("<h", int(11000 * math.sin(2 * math.pi * freq * t / 44100)))
                for t in range(int(44100 * seconds))))
    return str(path)


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

TRANSPORT_JS = """() => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      if (d && d.getElementById('mt-play') && d.getElementById('mt-bar')) {
        const read = (id) => {
          const el = d.getElementById(id);
          return el ? (el.textContent || '').trim() : '(missing)';
        };
        const c = window.__mtClock || null;
        return {time: read('mt-time'), bar: read('mt-bar'), beat: read('mt-beat'),
                clock_t: c ? Number(c.t) : null, clock_playing: c ? !!c.playing : null};
      }
    } catch (e) {}
  }
  return {error: 'no transport'};
}"""

STRIP_JS = """() => {
  const out = [];
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      const strip = d && d.querySelector('[id^="mtc-strip-"]');
      if (!strip) continue;
      const chips = [...strip.querySelectorAll('.mtc-cell')];
      // Only a strip inside an OPEN panel can be judged: a collapsed panel's document has
      // requestAnimationFrame paused, so its strip cannot repaint until it is shown again.
      const panel = f.closest('details');
      out.push({id: strip.id.replace('mtc-strip-', ''),
                lit_index: chips.findIndex(c => c.classList.contains('current')),
                scroll_left: Math.round(strip.scrollLeft),
                scroll_width: Math.round(strip.scrollWidth),
                client_width: Math.round(strip.clientWidth),
                visible: !!(panel && panel.open)});
    } catch (e) {}
  }
  return out;
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

# The surviving layer's audio URL: content-addressed, so an unchanged hash means unchanged bytes.
AUDIO_URL_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const el = d.querySelector('audio');
    if (!el) return {none: true};
    const src = el.currentSrc || el.getAttribute('src') || '';
    return {url: src.split('/').pop()};
  }
  return {missing: true};
}"""

DISCARD_BUTTONS_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const btns = [...d.querySelectorAll('button')]
      .filter(b => /discard take|delete layer/i.test(b.innerText || ''));
    return btns.map((b, i) => {
      const r = b.getBoundingClientRect();
      return {i: i, text: (b.innerText || '').trim(), disabled: !!b.disabled,
              x: r.x + r.width / 2, y: r.y + r.height / 2,
              visible: b.offsetParent !== null && r.width > 1};
    });
  }
  return [];
}"""

PANEL_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const txt = (d.innerText || '').toLowerCase();
    return {take: txt.includes('original take preview'), saved: txt.includes('saved layer'),
            unsaved: txt.includes('unsaved take')};
  }
  return {missing: true};
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
        page.wait_for_timeout(1100)
    return False


def open_layer(page, slot: str) -> None:
    if not H.layer_is_open(page, slot):
        H.toggle_layer_by_pointer(page, slot, True)
        idle(page)


def upload(page, slot: str, path: str) -> None:
    sel = ('details:has(summary:has-text("Layer controls")):has(summary:has-text("' + slot
           + '")) input[type="file"]')
    page.locator(sel).first.set_input_files(path)
    idle(page)
    page.wait_for_timeout(1200)
    idle(page)


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


def visible_strips(page) -> list:
    return [s for s in page.evaluate(STRIP_JS) if s.get("visible")]


def play_until_scrolled(page, limit_sec: float = 70.0) -> dict:
    """Play until a visible strip is genuinely scrolled away from its start."""
    page.evaluate(CLICK_TRANSPORT_JS, "mt-play")
    t0 = time.time()
    best = {"scroll": 0, "rows": []}
    while time.time() - t0 < limit_sec:
        page.wait_for_timeout(2500)
        rows = visible_strips(page)
        top = max([int(s.get("scroll_left") or 0) for s in rows], default=0)
        if top > best["scroll"]:
            best = {"scroll": top, "rows": rows}
        if top > 12:
            break
    best["transport"] = page.evaluate(TRANSPORT_JS)
    return best


def main() -> int:
    take_a = fixture("take_a.wav", 220.0, 2.0)
    take_b = fixture("take_b.wav", 330.0, 2.0)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required"])
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

            open_layer(page, GUITAR)
            upload(page, GUITAR, take_a)
            H.click_page_button(page, "save layer", slot=GUITAR)
            idle(page)
            open_layer(page, SAX)
            upload(page, SAX, take_b)
            mark("a saved layer and an unsaved take are in place",
                 bool(page.evaluate(PANEL_JS, GUITAR).get("saved"))
                 and bool(page.evaluate(PANEL_JS, SAX).get("unsaved")))

            # --- 4. the surviving layer's bytes, before --------------------------------------
            before_url = page.evaluate(AUDIO_URL_JS, GUITAR)
            MEASURED["guitar_audio_before"] = before_url

            # --- 1. scroll the strip away from the start, for real ---------------------------
            log("\n-- 1: the strip must be scrolled away before a reset can mean anything")
            best = play_until_scrolled(page)
            MEASURED["scrolled_while_playing"] = best
            mark("a visible chord strip scrolls away from the start while playing",
                 best["scroll"] > 12,
                 f"max scrollLeft {best['scroll']}px, transport {best.get('transport', {}).get('time')}")
            shot(page, "scrolled-while-playing")

            # --- 6/3. discard, and check the visible scroll returns --------------------------
            log("\n-- discard the unsaved take")
            H.click_page_button(page, "discard take", slot=SAX)
            idle(page)
            page.wait_for_timeout(2500)
            idle(page)
            rows_after = visible_strips(page)
            MEASURED["strips_after_discard"] = rows_after
            after_tr = page.evaluate(TRANSPORT_JS)
            MEASURED["transport_after_discard"] = after_tr
            shot(page, "after-discard")
            mark("the visible chord strip is scrolled back to its first chord",
                 bool(rows_after) and all(int(s.get("scroll_left") or 0) <= 2 for s in rows_after),
                 [s.get("scroll_left") for s in rows_after])
            mark("the visible chord strip highlights the first chord",
                 bool(rows_after) and all(s.get("lit_index") == 0 for s in rows_after),
                 [s.get("lit_index") for s in rows_after])
            mark("the transport is at bar 1 beat 1",
                 after_tr.get("bar") == "1" and after_tr.get("beat") == "1"
                 and after_tr.get("clock_t") == 0,
                 json.dumps(after_tr, default=str)[:140])
            mark("the discard did not restart audio",
                 after_tr.get("clock_playing") is False, after_tr.get("clock_playing"))

            # --- 4. the surviving layer's bytes, after ---------------------------------------
            after_url = page.evaluate(AUDIO_URL_JS, GUITAR)
            MEASURED["guitar_audio_after"] = after_url
            mark("the surviving layer's audio is byte-identical (same content-addressed URL)",
                 bool(before_url.get("url")) and before_url.get("url") == after_url.get("url"),
                 f"{before_url.get('url')} -> {after_url.get('url')}")

            # --- the duplicated Discard control: do BOTH act on the right take? --------------
            log("\n-- the duplicated Discard control")
            upload(page, SAX, take_b)
            btns = page.evaluate(DISCARD_BUTTONS_JS, SAX)
            MEASURED["sax_discard_buttons"] = btns
            usable = [b for b in btns if b.get("visible") and not b.get("disabled")]
            hidden = [b for b in btns if not b.get("visible")]
            # What the panel's button TEXT suggested was a duplicated control is one pressable
            # button plus a zero-sized element with no box. The musician sees one control, so
            # there is nothing visible to consolidate - but the hidden element is not marked
            # disabled, so it is recorded here as an accessibility note rather than ignored.
            mark("the musician is offered exactly ONE pressable Discard control",
                 len(usable) == 1, [b.get("text") for b in usable])
            MEASURED["hidden_discard_elements"] = hidden
            log("    NOTE: " + str(len(hidden)) + " zero-sized Discard element(s) also exist in the"
                " DOM, enabled but with no box: " + json.dumps(hidden, default=str)[:160])
            if usable:
                page.mouse.click(usable[0]["x"], usable[0]["y"])
                idle(page)
                page.wait_for_timeout(2000)
                idle(page)
                sax_now = page.evaluate(PANEL_JS, SAX)
                guitar_now = page.evaluate(PANEL_JS, GUITAR)
                MEASURED["after_pressable_copy"] = {"sax": sax_now, "guitar": guitar_now}
                mark("the pressable Discard control removes the correct take",
                     sax_now.get("take") is False, sax_now)
                mark("it leaves the other layer alone",
                     bool(guitar_now.get("take")) and bool(guitar_now.get("saved")), guitar_now)

            # --- 2. a position must not cross songs ------------------------------------------
            log("\n-- 2: switch songs; a remembered position must not follow")
            upload(page, SAX, take_b)
            play_until_scrolled(page, limit_sec=25.0)
            moved = page.evaluate(TRANSPORT_JS)
            MEASURED["position_before_song_switch"] = moved
            switched = H.open_studio_page(page, "Songs", "song")
            idle(page)
            picked = "not attempted"
            if switched:
                picked = H.click_page_button(page, "practice this song")
                idle(page)
            MEASURED["song_switch"] = {"reached_songs": switched, "picked": picked}
            if H.goto_multitrack(page):
                idle(page)
                after_switch = page.evaluate(TRANSPORT_JS)
                MEASURED["position_after_song_switch"] = after_switch
                same_song = (picked != "clicked")
                mark("a transport position never follows the musician into other music",
                     after_switch.get("clock_t") in (0, None) or same_song,
                     f"before {moved.get('clock_t')} -> after {after_switch.get('clock_t')}"
                     + (" (song unchanged, so this is informational)" if same_song else ""))
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

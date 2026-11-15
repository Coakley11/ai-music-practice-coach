"""Issue 77B acceptance: ordinary controls must not rewind the music; a discard must.

Measured in a real browser, in the order the musician described. Two things are read at every step,
because internal transport variables are not what the musician sees:

  * the TRANSPORT's own readout and the shared clock it publishes (seconds, bar, beat, playing);
  * the CHORD STRIP's visible state - which chip actually carries the "current" class, and the
     strip's real scrollLeft in pixels.

Why the position check is "preserved and shown as paused" rather than "still playing": a rerun that
changes the transport's arguments re-renders the component and its AudioContext goes with it, so
audio genuinely stops. The requirement accepted for this slice is that the POSITION survives and
nothing auto-resumes - never that sound continues through a Volume change.

Usage:
    python scripts/_accept_issue77b_position.py http://127.0.0.1:8619
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

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8619").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "after"
OUT = SCRIPTS / f"evidence-issue77b-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIXTURES = OUT / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}
GUITAR, SAX, FLUTE = H.SLOT_GUITAR, H.SLOT_SAX, H.SLOT_FLUTE


def log(msg: str) -> None:
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


def make_fixture(name: str, freq: float) -> str:
    import math
    import struct
    import wave

    path = FIXTURES / name
    if not path.exists():
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            handle.writeframes(b"".join(
                struct.pack("<h", int(11000 * math.sin(2 * math.pi * freq * t / 44100)))
                for t in range(int(44100 * 2.0))
            ))
    return str(path)


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

TRANSPORT_JS = """() => {
  let tf = null;
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      if (d && d.getElementById('mt-play') && d.getElementById('mt-bar')) { tf = f; break; }
    } catch (e) {}
  }
  if (!tf) return {error: 'no transport iframe'};
  const d = tf.contentDocument;
  const read = (id) => {
    const el = d.getElementById(id);
    return el ? (el.textContent || '').trim() : '(missing)';
  };
  const clock = window.__mtClock || null;
  return {time: read('mt-time'), bar: read('mt-bar'), beat: read('mt-beat'),
          label: read('mt-playback-label').slice(0, 70),
          clock_t: clock ? Number(clock.t) : null,
          clock_playing: clock ? !!clock.playing : null};
}"""

# The strip the musician looks at: which chip is lit, and where the strip is actually scrolled.
STRIP_JS = """() => {
  const out = [];
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      const strip = d && d.querySelector('[id^="mtc-strip-"]');
      if (!strip) continue;
      const chips = [...strip.querySelectorAll('.mtc-cell')];
      const lit = chips.findIndex(c => c.classList.contains('current'));
      const state = d.querySelector('[id^="mtc-state-"]');
      // Whether the musician can actually see this strip. A collapsed layer panel keeps its iframe
      // in the DOM but hidden, and a hidden document's requestAnimationFrame does not run - so a
      // hidden strip holds whatever it painted last and cannot be expected to repaint. Only the
      // visible ones can be judged.
      // Whether the musician can see this strip. A collapsed layer panel still gives its iframe a
      // box, so geometry says nothing; what decides it is the enclosing <details>. A collapsed
      // panel's document also has requestAnimationFrame paused, so its strip holds whatever it
      // last painted - which for a panel that was never opened is no highlight at all.
      const panel = f.closest('details');
      out.push({id: strip.id.replace('mtc-strip-', ''), chips: chips.length, lit_index: lit,
                scroll_left: Math.round(strip.scrollLeft),
                visible: !!(panel && panel.open),
                state: state ? (state.textContent || '').trim() : ''});
    } catch (e) {}
  }
  return out;
}"""

CLICK_TRANSPORT_JS = """(which) => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const d = f.contentDocument;
      const btn = d && d.getElementById(which);
      if (btn) { btn.click(); return 'clicked ' + which; }
    } catch (e) {}
  }
  return 'no button ' + which;
}"""

PANEL_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const txt = (d.innerText || '');
    return {take: txt.toLowerCase().includes('original take preview'),
            saved: txt.toLowerCase().includes('saved layer'),
            unsaved: txt.toLowerCase().includes('unsaved take'),
            controls: [...d.querySelectorAll('button')]
                        .map(b => (b.innerText || '').trim())
                        .filter(t2 => /discard take|delete layer|save layer/i.test(t2))};
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


def transport(page) -> dict:
    return page.evaluate(TRANSPORT_JS)


def strips(page) -> list:
    return page.evaluate(STRIP_JS)


def snapshot(page, label: str) -> dict:
    snap = {"transport": transport(page), "strips": strips(page)}
    MEASURED[label] = snap
    log("    " + label + ": " + json.dumps(snap, default=str)[:300])
    return snap


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


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


def press_in_layer(page, needle: str, slot: str) -> str:
    out = H.click_page_button(page, needle, slot=slot)
    idle(page)
    page.wait_for_timeout(1200)
    idle(page)
    return out


def play_to_a_later_bar(page, seconds: float = 7.0) -> dict:
    page.evaluate(CLICK_TRANSPORT_JS, "mt-play")
    page.wait_for_timeout(int(seconds * 1000))
    return transport(page)


def nudge_volume(page) -> str:
    try:
        vol = page.get_by_label("Volume", exact=False).first
        vol.scroll_into_view_if_needed()
        vol.click()
        page.keyboard.press("ArrowLeft")
        idle(page)
        page.wait_for_timeout(1200)
        idle(page)
        return "Volume nudged"
    except Exception as exc:
        return "failed: " + str(exc)[:110]


def toggle_mute(page) -> str:
    try:
        box = page.get_by_label("Mute", exact=False).first
        box.scroll_into_view_if_needed()
        box.click()
        idle(page)
        page.wait_for_timeout(1200)
        idle(page)
        return "Mute toggled"
    except Exception as exc:
        return "failed: " + str(exc)[:110]


def position_of(snap: dict) -> float:
    t = (snap.get("transport") or {}).get("clock_t")
    try:
        return float(t)
    except (TypeError, ValueError):
        return -1.0


def lit_indexes(snap: dict, visible_only: bool = False) -> list:
    rows = snap.get("strips") or []
    if visible_only:
        rows = [s for s in rows if s.get("visible")]
    return [s.get("lit_index") for s in rows]


def scrolls(snap: dict, visible_only: bool = False) -> list:
    rows = snap.get("strips") or []
    if visible_only:
        rows = [s for s in rows if s.get("visible")]
    return [s.get("scroll_left") for s in rows]


def main() -> int:
    good = make_fixture("take_a.wav", 220.0)
    other = make_fixture("take_b.wav", 330.0)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required"],
        )
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

            # --- 1. a project with a layer, playback moved to a later measure -----------------
            log("\n-- 1: move playback to a later measure")
            open_layer(page, GUITAR)
            upload(page, GUITAR, good)
            mark("a layer is in place to play", bool(page.evaluate(PANEL_JS, GUITAR).get("take")))
            played = play_to_a_later_bar(page, 7.0)
            MEASURED["while_playing"] = played
            log("    while playing: " + json.dumps(played, default=str)[:220])
            moved = position_of({"transport": played}) > 2.0
            mark("playback reaches a later measure", moved,
                 f"{played.get('time')} bar {played.get('bar')} clock {played.get('clock_t')}")
            before = snapshot(page, "before_volume")

            # --- 2. Volume -------------------------------------------------------------------
            log("\n-- 2: adjust Volume")
            MEASURED["volume_action"] = nudge_volume(page)
            after_vol = snapshot(page, "after_volume")
            kept = position_of(after_vol)
            mark("Volume does not rewind the position",
                 kept > 1.0, f"clock {kept} (was {position_of(before)})")
            mark("Volume does not auto-resume playback",
                 (after_vol.get("transport") or {}).get("clock_playing") is False,
                 (after_vol.get("transport") or {}).get("clock_playing"))
            mark("the chord strip stays where the music was",
                 any(i is not None and i > 0 for i in lit_indexes(after_vol)),
                 f"lit {lit_indexes(after_vol)} scroll {scrolls(after_vol)}")
            shot(page, "after-volume")

            # --- 3. Mute ---------------------------------------------------------------------
            log("\n-- 3: change Mute")
            MEASURED["mute_action"] = toggle_mute(page)
            after_mute = snapshot(page, "after_mute")
            mark("Mute does not rewind the position", position_of(after_mute) > 1.0,
                 f"clock {position_of(after_mute)}")

            # --- 4. Save a layer -------------------------------------------------------------
            log("\n-- 4: save the layer")
            MEASURED["save_click"] = press_in_layer(page, "save layer", GUITAR)
            after_save = snapshot(page, "after_save")
            mark("Save layer does not rewind the position", position_of(after_save) > 1.0,
                 f"clock {position_of(after_save)}")
            mark("the layer is saved", bool(page.evaluate(PANEL_JS, GUITAR).get("saved")))

            # --- 5. an additional instrument -------------------------------------------------
            log("\n-- 5: add another instrument")
            open_layer(page, SAX)
            upload(page, SAX, other)
            after_second = snapshot(page, "after_second_layer")
            sax = page.evaluate(PANEL_JS, SAX)
            mark("the second take lands unsaved", bool(sax.get("take")) and bool(sax.get("unsaved")),
                 sax.get("controls"))
            mark("adding a take does not rewind the position", position_of(after_second) > 1.0,
                 f"clock {position_of(after_second)}")

            # --- 6. discard the unsaved take -------------------------------------------------
            log("\n-- 6: discard the unsaved take")
            MEASURED["discard_click"] = press_in_layer(page, "discard take", SAX)
            after_discard = snapshot(page, "after_discard")
            shot(page, "after-discard")
            sax_after = page.evaluate(PANEL_JS, SAX)
            mark("the discarded take is gone", sax_after.get("take") is False, sax_after)
            mark("the transport returns to the beginning",
                 position_of(after_discard) == 0.0
                 and (after_discard.get("transport") or {}).get("bar") == "1"
                 and (after_discard.get("transport") or {}).get("beat") == "1",
                 json.dumps(after_discard.get("transport"), default=str)[:160])
            # Only the strips the musician can see: a collapsed panel's strip is hidden, and a
            # hidden document's requestAnimationFrame does not run, so it holds its last paint
            # until it is shown again - which the reopen check below covers.
            visible_lit = lit_indexes(after_discard, visible_only=True)
            mark("every visible chord strip highlights the first chord",
                 bool(visible_lit) and all(i == 0 for i in visible_lit),
                 f"visible {visible_lit} / all {lit_indexes(after_discard)}")
            mark("the chord strip is scrolled to its beginning",
                 all((s or 0) <= 2 for s in scrolls(after_discard, visible_only=True)),
                 f"scroll {scrolls(after_discard, visible_only=True)}")
            # And what the musician sees when they open that layer again.
            open_layer(page, SAX)
            page.wait_for_timeout(2500)
            reopened = snapshot(page, "after_discard_reopened")
            reopened_lit = lit_indexes(reopened, visible_only=True)
            mark("reopening the discarded layer shows it at the first chord",
                 bool(reopened_lit) and all(i == 0 for i in reopened_lit),
                 f"visible {reopened_lit}")
            guitar_now = page.evaluate(PANEL_JS, GUITAR)
            mark("the saved guitar layer is untouched by the discard",
                 bool(guitar_now.get("take")) and bool(guitar_now.get("saved")), guitar_now)

            # --- 7. record a replacement take ------------------------------------------------
            log("\n-- 7: a replacement take")
            upload(page, SAX, other)
            sax_again = page.evaluate(PANEL_JS, SAX)
            mark("a replacement take can be added", bool(sax_again.get("take")), sax_again)

            # --- 8. save it, then delete the layer -------------------------------------------
            log("\n-- 8: save it, then delete the layer")
            press_in_layer(page, "save layer", SAX)
            play_to_a_later_bar(page, 6.0)
            snapshot(page, "before_delete")
            MEASURED["delete_click"] = press_in_layer(page, "delete layer", SAX)
            after_delete = snapshot(page, "after_delete")
            shot(page, "after-delete")
            sax_deleted = page.evaluate(PANEL_JS, SAX)
            mark("Delete layer removes the saved layer", sax_deleted.get("take") is False,
                 sax_deleted)
            mark("Delete layer returns the transport to the beginning",
                 position_of(after_delete) == 0.0, position_of(after_delete))
            mark("Delete layer scrolls the chord strip back",
                 all((s or 0) <= 2 for s in scrolls(after_delete, visible_only=True)), f"scroll {scrolls(after_delete, visible_only=True)}")

            # --- 9. navigate away and back ---------------------------------------------------
            log("\n-- 9: navigate away and return")
            H.open_studio_page(page, "Practice", "practice")
            idle(page)
            H.goto_multitrack(page)
            idle(page)
            open_layer(page, SAX)
            open_layer(page, GUITAR)
            sax_back = page.evaluate(PANEL_JS, SAX)
            guitar_back = page.evaluate(PANEL_JS, GUITAR)
            MEASURED["after_navigation"] = {"sax": sax_back, "guitar": guitar_back}
            mark("the discarded/deleted audio does not reappear after navigation",
                 sax_back.get("take") is False, sax_back)
            mark("the other layer is still there after navigation",
                 bool(guitar_back.get("take")), guitar_back)

            # --- 10. reload the page (the persisted path) -------------------------------------
            log("\n-- 10: reload the app")
            page.reload(wait_until="load")
            idle(page)
            if H.goto_multitrack(page):
                idle(page)
                open_layer(page, SAX)
                open_layer(page, GUITAR)
                sax_reload = page.evaluate(PANEL_JS, SAX)
                guitar_reload = page.evaluate(PANEL_JS, GUITAR)
                MEASURED["after_reload"] = {"sax": sax_reload, "guitar": guitar_reload}
                mark("the deleted layer stays deleted after a reload",
                     sax_reload.get("take") is False, sax_reload)
                mark("the saved layer survives the reload",
                     bool(guitar_reload.get("take")), guitar_reload)
                shot(page, "after-reload")

                # --- the last remaining layer, which is where the defect lived ---------------
                log("\n-- last layer: the case the stale cache used to resurrect")
                press_in_layer(page, "delete layer", GUITAR)
                last = page.evaluate(PANEL_JS, GUITAR)
                mark("the last layer can be deleted", last.get("take") is False, last)
                page.reload(wait_until="load")
                idle(page)
                if H.goto_multitrack(page):
                    idle(page)
                    open_layer(page, GUITAR)
                    last_reload = page.evaluate(PANEL_JS, GUITAR)
                    MEASURED["last_layer_after_reload"] = last_reload
                    mark("the last deleted layer does not come back after a reload",
                         last_reload.get("take") is False, last_reload)
                    shot(page, "last-layer-after-reload")
            else:
                mark("the Multitrack page reopens after a reload", False)
            ctx.close()

            # --- widths -----------------------------------------------------------------------
            log("\n-- widths")
            for width in (1400, 390, 360):
                wctx = browser.new_context(viewport={"width": width, "height": 900})
                wpage = wctx.new_page()
                wpage.set_default_timeout(40000)
                try:
                    wpage.goto(URL, wait_until="load")
                    idle(wpage)
                    H.boot(wpage)
                    if not H.goto_multitrack(wpage):
                        mark(f"[{width}px] the Multitrack page opens", False)
                        continue
                    idle(wpage)
                    over = wpage.evaluate(
                        """() => { const de = document.documentElement;
                                   return {scroll_w: de.scrollWidth, client_w: de.clientWidth,
                                           sideways: de.scrollWidth > de.clientWidth + 2}; }""")
                    MEASURED[f"width_{width}"] = over
                    mark(f"[{width}px] the page does not scroll sideways", not over.get("sideways"),
                         over)
                    shot(wpage, f"width-{width}")
                finally:
                    wctx.close()
        finally:
            browser.close()

    (OUT / "measured.json").write_text(json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("\n" + "=" * 78)
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates pass")
    for gate in failed:
        log("  FAILED: " + gate)
    log("evidence: " + str(OUT))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

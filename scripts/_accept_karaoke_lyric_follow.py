"""Does the viewport actually come back to the lyric being sung?

The earlier run proved the hold and nothing about the following, because it measured Say's
instrumental Intro: one lyric line, a box that does not overflow, so nothing to scroll to. This
waits for a lyric-bearing section - several lines - and then walks the exact sequence:

  1. playback running, lyrics advancing with the music
  2. scroll away by hand
  3. automatic following suspended
  4. playback continues while the view stays where the singer put it
  5. after about six seconds the view returns to the CURRENT lyric
  6. following continues as later lines arrive

Everything is read as coordinates and as visible text: the page scroller's position, the
iframe's own scroll position, which lyric is active, and whether that lyric's box is inside the
window. ``suspended()`` is recorded too, but it is never the evidence on its own.

Run it twice, once with the Lead Sheet Off and once On:

  python -X utf8 scripts/_accept_karaoke_lyric_follow.py http://127.0.0.1:8614
  python -X utf8 scripts/_accept_karaoke_lyric_follow.py http://127.0.0.1:8614 --sheet-on
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8614"
SHEET_ON = "--sheet-on" in sys.argv
#: Phone widths are the same journey in a narrower window, so the measurements that already
#: proved the six-second hold and the return to the sung lyric are re-run there rather than
#: reimplemented. --width 390 (or 360) also turns on the layout gates below.
WIDTH = 1280
HEIGHT = 900
for _i, _a in enumerate(sys.argv):
    if _a == "--width" and _i + 1 < len(sys.argv):
        try:
            WIDTH = int(sys.argv[_i + 1])
            HEIGHT = 844 if WIDTH <= 400 else 900
        except ValueError:
            pass
PHONE = WIDTH <= 400

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    low,
    press_play,
    set_lead_sheet,
    settle,
    wait_for_app,
)
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-slice2"
OUT.mkdir(parents=True, exist_ok=True)
TAG = ("sheet-on" if SHEET_ON else "sheet-off") + (f"-{WIDTH}" if PHONE else "")
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []


def log(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def observe(msg: str) -> None:
    OBSERVED.append(msg)
    log(f"[OBS ] {msg}")


#: Coordinates and visible text together: where both scrollers are, which lyric is lit, and
#: whether that lyric is actually inside the window the singer is looking at.
READ = """
() => {
  const sc = document.scrollingElement || document.documentElement;
  const line = document.querySelector('.karaoke-lp-lyric-line.active');
  const lines = [...document.querySelectorAll('.karaoke-lp-lyric-line')];
  let onscreen = null, topInWindow = null;
  if (line) {
    try {
      const r = line.getBoundingClientRect();
      const fe = window.frameElement;
      const fr = fe ? fe.getBoundingClientRect() : {top: 0};
      topInWindow = Math.round(fr.top + r.top);
      const h = (window.top && window.top.innerHeight) || window.innerHeight;
      onscreen = topInWindow > 0 && topInWindow < h - 20;
    } catch (e) {}
  }
  let held = null;
  try { const c = window.top.__lsFollow; held = c && c.suspended ? !!c.suspended() : null; } catch (e) {}
  return {
    box_top: Math.round(sc ? sc.scrollTop : -1),
    box_scrollable: !!(sc && sc.scrollHeight > sc.clientHeight + 4),
    lines: lines.length,
    active: line ? (line.textContent || '').trim().slice(0, 46) : '',
    active_index: line ? lines.indexOf(line) : -1,
    active_top_in_window: topInWindow,
    active_onscreen: onscreen,
    playing: !![...document.querySelectorAll('audio')].find(a => !a.paused && !a.ended),
    held: held,
  };
}
"""

PAGE_Y = """
() => {
  const main = document.querySelector('[data-testid="stMain"]')
    || document.querySelector('[data-testid="stAppViewContainer"]')
    || document.scrollingElement;
  const own = main ? Math.round(main.scrollTop || 0) : 0;
  return own || Math.round(window.scrollY || 0);
}
"""


def page_y(page: Page) -> int:
    try:
        return int(page.evaluate(PAGE_Y))
    except Exception:
        return -1


def surface(page: Page) -> Frame | None:
    for f in page.frames:
        try:
            if f.evaluate("() => !!document.getElementById('live-chord')"):
                return f
        except Exception:
            continue
    return None


def main() -> int:
    report: dict = {"sheet_on": SHEET_ON}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT},
                                      has_touch=True, is_mobile=PHONE,
                                      device_scale_factor=3 if PHONE else 1)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark(f"L1 app renders [{TAG}]", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark(f"L2 performing [{TAG}]", "now singing" in low(page.inner_text("body") or ""))

            click_nav(page, "Backing")
            settle(page, 6)
            if SHEET_ON:
                set_lead_sheet(page, True)
                settle(page, 5)
            played = press_play(page)
            frame = None
            for _ in range(60):
                frame = surface(page)
                if frame:
                    break
                settle(page, 3)
            mark(f"L3 the surface mounts [{TAG}]", frame is not None, f"play={bool(played)}")
            if frame is None:
                return 2

            # Start the take; headless blocks autoplay, and the follower needs a running clock.
            log("    audio: " + str(frame.evaluate(
                """() => { const a = [...document.querySelectorAll('audio')]
                     .find(x => x.src || x.currentSrc);
                   if (!a) return 'none'; a.muted = true;
                   try { a.play(); } catch (e) { return 'threw'; } return 'started'; }""")))

            # Wait for a lyric-bearing section. Say's Intro is instrumental - one line - which
            # is why the first acceptance could not demonstrate following at all.
            lyric_state = {}
            for _ in range(80):
                lyric_state = frame.evaluate(READ)
                if int(lyric_state.get("lines") or 0) >= 3:
                    break
                page.wait_for_timeout(1000)
            log(f"    surface: {lyric_state}")
            mark(f"L4 a lyric-bearing section is on screen [{TAG}]",
                 int(lyric_state.get("lines") or 0) >= 3,
                 f"{lyric_state.get('lines')} lyric line(s), active {lyric_state.get('active')!r}")
            if int(lyric_state.get("lines") or 0) < 3:
                observe("never reached a section with several lyric lines; the sequence below "
                        "cannot be measured on an instrumental")
                return 2

            def snap(seconds: float, label: str) -> list[dict]:
                rows: list[dict] = []
                end = time.time() + seconds
                while time.time() < end:
                    try:
                        got = frame.evaluate(READ)
                    except Exception:
                        got = {}
                    got["page_y"] = page_y(page)
                    got["at"] = round(time.time(), 2)
                    got["phase"] = label
                    rows.append(got)
                    page.wait_for_timeout(250)
                return rows

            # 2. the lyrics advance with the music
            advancing = snap(12, "advancing")
            seen = [r.get("active") for r in advancing if r.get("active")]
            idx = [r.get("active_index") for r in advancing if r.get("active_index", -1) >= 0]
            mark(f"L5 the lyrics advance with the music [{TAG}]",
                 len(set(seen)) > 1 or len(set(idx)) > 1,
                 f"{len(set(seen))} distinct line(s): {sorted(set(seen))[:3]}")
            log(f"    page {[r['page_y'] for r in advancing][:10]}")
            log(f"    box  {[r.get('box_top') for r in advancing][:10]}")

            # 3. scroll away by hand
            box = None
            for el in page.locator("iframe").all():
                try:
                    b = el.bounding_box()
                except Exception:
                    b = None
                if b and b.get("height", 0) > 200:
                    box = b
                    break
            before = frame.evaluate(READ)
            before["page_y"] = page_y(page)
            # Aim inside the WINDOW, not at the iframe's absolute box: by this point the page is
            # scrolled down to the component, so box["y"] + 220 can fall below the fold and the
            # gesture lands nowhere - measured as "page 4020 -> 4020" with held=False. And
            # scroll UP, both because the page may already be at its maximum and because
            # scrolling up away from the lyrics is the musician's actual complaint.
            vp = page.viewport_size or {"width": 1280, "height": 900}
            page.mouse.move(vp["width"] / 2, vp["height"] / 2)
            page.mouse.wheel(0, -900)
            page.wait_for_timeout(300)
            if abs(page_y(page) - before["page_y"]) <= 80:
                observe(f"scrolling up did not move the page ({before['page_y']} -> "
                        f"{page_y(page)}); trying downward")
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(300)
            after_gesture = frame.evaluate(READ)
            after_gesture["page_y"] = page_y(page)
            moved_away = (abs(after_gesture["page_y"] - before["page_y"]) > 80
                          or abs(int(after_gesture.get("box_top") or 0) - int(before.get("box_top") or 0)) > 80)
            mark(f"L6 the musician can scroll away from the lyrics [{TAG}]", moved_away,
                 f"page {before['page_y']} -> {after_gesture['page_y']}, "
                 f"box {before.get('box_top')} -> {after_gesture.get('box_top')}, "
                 f"active lyric on screen: {after_gesture.get('active_onscreen')}")

            # 4 + 5. suspended, and the view stays put while the music runs on
            gesture_at = time.time()
            mark(f"L7 following is suspended by the gesture [{TAG}]",
                 after_gesture.get("held") is True, f"held={after_gesture.get('held')}")
            held_rows = snap(10, "after-gesture")
            early = [r for r in held_rows if r["at"] - gesture_at < 5.0]
            stayed = all(
                abs(r["page_y"] - after_gesture["page_y"]) <= 60
                and abs(int(r.get("box_top") or 0) - int(after_gesture.get("box_top") or 0)) <= 60
                for r in early
            )
            mark(f"L8 the view stays where the singer put it for the first five seconds [{TAG}]",
                 stayed and bool(early),
                 f"page {[r['page_y'] for r in early][:8]} box {[r.get('box_top') for r in early][:8]}")
            lines_held = [r.get("active") for r in held_rows if r.get("active")]
            mark(f"L9 playback and lyric highlighting continue while held [{TAG}]",
                 any(r.get("playing") for r in held_rows) and len(set(lines_held)) >= 1,
                 f"playing={sum(1 for r in held_rows if r.get('playing'))}/{len(held_rows)} "
                 f"samples, {len(set(lines_held))} distinct line(s)")

            # 6. the view returns to the CURRENT lyric
            returned = next(
                (r for r in held_rows
                 if r["at"] - gesture_at > 5.0 and r.get("active_onscreen") is True
                 and (abs(r["page_y"] - after_gesture["page_y"]) > 60
                      or abs(int(r.get("box_top") or 0) - int(after_gesture.get("box_top") or 0)) > 60)),
                None,
            )
            elapsed = round(returned["at"] - gesture_at, 2) if returned else None
            mark(f"L10 after about six seconds the view returns to the current lyric [{TAG}]",
                 returned is not None and 5.0 <= (elapsed or 0) <= 9.5,
                 f"returned after {elapsed}s to {(returned or {}).get('active')!r} "
                 f"(page {(returned or {}).get('page_y')}, box {(returned or {}).get('box_top')})")

            # 7. and keeps following afterwards
            later = snap(12, "after-return")
            later_lines = [r.get("active") for r in later if r.get("active")]
            onscreen_after = [r for r in later if r.get("active_onscreen") is True]
            mark(f"L11 following continues as later lyrics arrive [{TAG}]",
                 len(onscreen_after) >= len(later) // 2,
                 f"{len(onscreen_after)}/{len(later)} samples had the active lyric on screen, "
                 f"{len(set(later_lines))} distinct line(s)")
            report.update({"advancing": advancing, "before": before, "after_gesture": after_gesture,
                           "held": held_rows, "later": later, "returned_after_s": elapsed})
        finally:
            (OUT / f"lyric-follow-{TAG}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            try:
                page.screenshot(path=str(OUT / f"lyric-follow-{TAG}.png"), full_page=False)
            except Exception:
                pass
            context.close()
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / f"lyric-follow-gates-{TAG}.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

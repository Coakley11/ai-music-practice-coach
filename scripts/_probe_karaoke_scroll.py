"""Karaoke Parts 9 and 10: measure the scrolling before changing it.

The assignment is explicit that the viewport movement has to be measured rather than inferred
from timers or DOM state, so this probe watches three things while a karaoke take plays:

  1. how often the performance surface calls ``scrollIntoView`` / sets ``scrollTop``
  2. where the top-level page and the component's own scroller actually are, sampled over time
  3. what happens to those positions after a real manual gesture - wheel, keyboard and touch

The reason to measure first: there are two candidate mechanisms and they want opposite fixes.

  * the lyric follower (``highlightActiveLine``) calls
    ``activeLine.scrollIntoView({behavior:"smooth", block:"center"})`` on every tick of the
    follow loop - a requestAnimationFrame loop - and not only when the active line changes.
    ``scrollIntoView`` walks every scrollable ancestor, and this component is a same-origin
    srcdoc frame, so it can move the page itself.
  * the chart follower centres the current cell inside ``.live-follow-shell`` once per chord
    change, with no manual-scroll suspension at all.

Neither is fixed here. This only reports what is happening.

Usage:
  python -X utf8 scripts/_probe_karaoke_scroll.py http://127.0.0.1:8599
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8599"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    low,
    press_play,
    settle,
    wait_for_app,
    wait_for_live_strip,
)
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


# Counts the scrolling the surface performs, without changing what it does.
INSTRUMENT = """
() => {
  if (window.__scrollProbe) return true;
  const probe = {intoView: 0, topSet: 0, calls: [], start: Date.now()};
  window.__scrollProbe = probe;
  const realIntoView = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (...args) {
    probe.intoView += 1;
    if (probe.calls.length < 4000) {
      probe.calls.push({t: Date.now() - probe.start, kind: 'intoView',
                        cls: String(this.className || '').slice(0, 40)});
    }
    return realIntoView.apply(this, args);
  };
  const proto = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
  if (proto && proto.set) {
    Object.defineProperty(Element.prototype, 'scrollTop', {
      get: proto.get,
      set: function (v) {
        probe.topSet += 1;
        if (probe.calls.length < 4000) {
          probe.calls.push({t: Date.now() - probe.start, kind: 'scrollTop',
                            cls: String(this.className || '').slice(0, 40), v: Math.round(v)});
        }
        return proto.set.call(this, v);
      },
      configurable: true,
    });
  }
  return true;
}
"""

READ_PROBE = """
() => {
  const p = window.__scrollProbe || {intoView: 0, topSet: 0, calls: []};
  const shell = document.querySelector('.live-follow-shell');
  const panel = document.getElementById('karaoke-lyric-panel');
  const active = document.querySelector('.karaoke-lp-lyric-line.active');
  return {
    intoView: p.intoView,
    topSet: p.topSet,
    doc_top: Math.round((document.scrollingElement || document.body).scrollTop || 0),
    shell_top: shell ? Math.round(shell.scrollTop) : null,
    shell_scrollable: shell ? (shell.scrollHeight > shell.clientHeight + 4) : null,
    panel_present: !!panel,
    active_line: active ? (active.textContent || '').trim().slice(0, 40) : '',
    audio_playing: (() => {
      const a = [...document.querySelectorAll('audio')].find(x => !x.paused && !x.ended);
      return !!a;
    })(),
  };
}
"""


def perf_frame(page: Page) -> Frame | None:
    """The performance surface's own frame.

    Identified by ``#live-chord`` - the live chord strip - because that is the element the
    Issue 69 harness already waits for, so it is known to exist on this surface. An earlier
    version looked for the lyric panel or the chart root and reported "no performance frame
    appeared" while the performance was in fact running.
    """
    for frame in page.frames:
        try:
            got = frame.evaluate(
                """() => !!(document.getElementById('live-chord')
                            || document.getElementById('karaoke-lyric-panel')
                            || document.getElementById('live-chart-root'))"""
            )
        except Exception:
            continue
        if got:
            return frame
    return None


def describe_frames(page: Page) -> str:
    out = []
    for frame in page.frames:
        try:
            got = frame.evaluate(
                """() => ({ids: [...document.querySelectorAll('[id]')].map(e => e.id).slice(0, 12),
                            len: (document.body ? document.body.innerText.length : 0)})"""
            )
        except Exception as exc:
            got = {"error": type(exc).__name__}
        out.append(f"{frame.url[:40]!r} -> {got}")
    return "\n      ".join(out)


def page_scroll(page: Page) -> int:
    try:
        return int(page.evaluate("() => Math.round(window.scrollY || 0)"))
    except Exception:
        return -1


def sample(page: Page, frame: Frame, seconds: float, label: str) -> list[dict]:
    rows: list[dict] = []
    end = time.time() + seconds
    while time.time() < end:
        try:
            got = frame.evaluate(READ_PROBE)
        except Exception:
            got = {}
        got["page_y"] = page_scroll(page)
        got["at"] = round(time.time(), 2)
        got["phase"] = label
        rows.append(got)
        page.wait_for_timeout(250)
    return rows


def setup(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    settle(page, 5)
    if not wait_for_app(page):
        log("app never became ready")
        return False
    # Order matters: the instrument control has to be driven with a song already active, and
    # karaoke is voice-only - set on the landing page it did not take, so the Songs card had no
    # Add to Karaoke Set button and the run read "could not queue Say".
    if not pick_song(page, NOTES, "Say", "pop"):
        log("could not pick Say")
        return False
    expand_sidebar(page)
    set_baseweb_select(page, "Instrument", "Voice")
    settle(page, 6)
    click_nav(page, "Songs")
    settle(page, 4)
    if not (click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")):
        log("could not queue Say")
        return False
    settle(page, 3)
    click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 5)
    started = (click_text(page, "Start karaoke set") or click_text(page, "Start performance")
               or click_text(page, "Start"))
    settle(page, 8)
    body = page.inner_text("body") or ""
    log(f"performing={'now singing' in low(body)} (start helper {bool(started)})")
    return "now singing" in low(body)


def main() -> int:
    report: dict = {"url": URL}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 1000}, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            if not setup(page):
                log("BLOCKED: no performance to measure")
                return 2
            if not press_play(page):
                log("BLOCKED: Play was not available")
                return 2
            # The take has to be generated and installed before anything scrolls. The proven
            # detector is the live chord strip, so wait for that rather than a fixed settle.
            strip = wait_for_live_strip(page, 300)
            log(f"live strip: {strip}")
            frame = None
            for _ in range(40):
                frame = perf_frame(page)
                if frame:
                    break
                settle(page, 3)
            if frame is None:
                log("BLOCKED: no performance frame appeared. Frames seen:\n      "
                    + describe_frames(page))
                page.screenshot(path=str(OUT / "scroll-probe-noframe.png"), full_page=True)
                return 2
            log(f"performance frame: {frame.url[:60]!r}")
            frame.evaluate(INSTRUMENT)

            baseline = sample(page, frame, 8, "playing")
            first, last = baseline[0], baseline[-1]
            span = max(0.01, last["at"] - first["at"])
            rate = (last.get("intoView", 0) - first.get("intoView", 0)) / span
            top_rate = (last.get("topSet", 0) - first.get("topSet", 0)) / span
            log(f"while playing: scrollIntoView {rate:.1f}/s, scrollTop writes {top_rate:.1f}/s, "
                f"audio={last.get('audio_playing')}")
            report["playing"] = {"intoView_per_s": round(rate, 2),
                                 "scrollTop_per_s": round(top_rate, 2),
                                 "samples": baseline}

            # A real wheel gesture over the performance surface.
            box = None
            for el in page.locator("iframe").all():
                try:
                    b = el.bounding_box()
                except Exception:
                    b = None
                if b and b.get("height", 0) > 200:
                    box = b
                    break
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            before_y = page_scroll(page)
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(200)
            after_y = page_scroll(page)
            log(f"wheel: page scroll {before_y} -> {after_y}")
            wheel_rows = sample(page, frame, 10, "after-wheel")
            report["wheel"] = {"before": before_y, "after": after_y, "samples": wheel_rows}
            ys = [r.get("page_y") for r in wheel_rows]
            log(f"page scroll for 10 s after the wheel: {ys}")
            snapped = next(
                (r["at"] - wheel_rows[0]["at"] for r in wheel_rows
                 if abs((r.get("page_y") or 0) - before_y) < 30),
                None,
            )
            log(f"came back to where it was after {snapped}s" if snapped is not None
                else "did not come back to the pre-gesture position within 10 s")
            report["wheel"]["snap_back_seconds"] = snapped

            # Keyboard and touch, the other two gestures the assignment names.
            page.keyboard.press("PageDown")
            page.wait_for_timeout(400)
            report["keyboard_y"] = page_scroll(page)
            log(f"after PageDown: page scroll {report['keyboard_y']}")
            try:
                page.touchscreen.tap(box["x"] + 40, box["y"] + 40) if box else None
                report["touch_ok"] = True
            except Exception as exc:
                report["touch_ok"] = False
                log(f"touch gesture unavailable: {exc}")

            calls = frame.evaluate("() => (window.__scrollProbe || {}).calls || []")
            report["calls_tail"] = calls[-40:]
            kinds: dict[str, int] = {}
            for c in calls:
                kinds[c.get("kind", "?")] = kinds.get(c.get("kind", "?"), 0) + 1
            log(f"scroll calls by kind: {kinds}")
            report["calls_by_kind"] = kinds
        finally:
            page.screenshot(path=str(OUT / "scroll-probe.png"), full_page=True)
            context.close()
            browser.close()
    (OUT / "scroll-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "scroll-probe.log").write_text("\n".join(NOTES), encoding="utf-8")
    log(f"\nwrote {OUT / 'scroll-probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Karaoke Parts 9 and 10: measure the performance surface's scrolling, in a real browser.

All of the scrolling lives inside one component: ``live_follow_along_component_html``. So this
renders that component - the real function, with a real take and a real timeline - into a page
of its own and measures it directly. No setlist, no generation, no app: seconds per run instead
of ten minutes, and every variable under control.

What it measures:

  * how often the surface scrolls while a take plays, and by which call
  * where the page and the component's own scroller actually are, sampled over time
  * what happens after a real wheel, keyboard and touch gesture - and how long before the
    surface takes the viewport back
  * the same with the chord chart folded (Lead Sheet off) and open (Lead Sheet on)

The component is wrapped in a page that imitates the app's own frame: the HTML goes inside an
iframe of the same origin, because that is how Streamlit mounts it and because
``scrollIntoView`` inside a same-origin iframe can scroll the parent document - which is the
mechanism under suspicion.

Usage:
  python -X utf8 scripts/_probe_follow_component.py            # both cases
  python -X utf8 scripts/_probe_follow_component.py --headed   # watch it
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)

BPM = 76
BEAT = 60.0 / BPM
BAR = 4 * BEAT
SECTIONS = {
    "Verse 1": ["Bb:2|Eb:2p", "Gm:2|F:2p"] * 4,
    "Chorus 1": ["Bb:2|Eb:2p", "Gm:2|F:2p"] * 4,
}
LYRICS = {
    "Verse 1": [f"Verse line {i} - take all of your wasted honor" for i in range(1, 9)],
    "Chorus 1": [f"Chorus line {i} - say what you need to say" for i in range(1, 9)],
}

NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def build_timeline() -> list[dict]:
    """One event per sub-chord, with the same fields the app's own builder emits."""
    from chord_subdivisions import parse_subdivisions

    timeline: list[dict] = []
    t = 0.0
    index = 0
    for section, chart in SECTIONS.items():
        for bar_i, token in enumerate(chart):
            cursor = 0.0
            for sub in parse_subdivisions(token, beats_per_bar=4.0):
                start = t + cursor * BEAT
                dur = float(sub.weight) * BEAT
                timeline.append({
                    "event_index": index,
                    "absolute_bar": bar_i + 1,
                    "total_bars": len(chart),
                    "section": section,
                    "bar_in_section": bar_i,
                    "section_bars": len(chart),
                    "chord": sub.chord,
                    "start_time": start,
                    "duration": dur,
                    "end_time": start + dur,
                    "subdivision_index": 0,
                    "mood": "verse" if section.startswith("Verse") else "chorus",
                    "arrangement_intensity": 0.8 if section.startswith("Verse") else 1.2,
                    "is_final_chorus": False,
                })
                index += 1
                cursor += float(sub.weight)
            t += BAR
    return timeline


def build_component(*, hide_chart: bool) -> str:
    import streamlit_music_practice_app as app
    from backing_audio import generate_backing_track

    chords = [c for chart in SECTIONS.values() for c in chart]
    wav = generate_backing_track(
        chords, bpm=BPM, loops=1, style="Pop groove", level="Intermediate",
        song_title="Say", song_artist="John Mayer", time_signature="4/4",
    )
    chart_html = app.chart_html_for_sections(SECTIONS) if hasattr(app, "chart_html_for_sections") else ""
    if not chart_html:
        # The chart's own builder is not needed to measure scrolling: what matters is that
        # the cells carry the section/bar data attributes the follower looks for.
        cells = []
        for section, chart in SECTIONS.items():
            rows = "".join(
                f'<div class="live-chart-cell" data-section="{section}" data-bar="{i}" '
                f'data-chord="{c}"><span class="chord-symbol">{c}</span></div>'
                for i, c in enumerate(chart)
            )
            cells.append(
                f'<div class="section-card"><div class="section-head">'
                f'<span class="section-meta">{section}</span>'
                f'<span class="section-meta"></span></div>{rows}</div>'
            )
        chart_html = f'<div class="backing-chart-sheet">{"".join(cells)}</div>'

    panel = {
        name: {"lyrics": LYRICS[name], "chords": [str(c) for c in chart]}
        for name, chart in SECTIONS.items()
    }
    return app.live_follow_along_component_html(
        wav,
        build_timeline(),
        chart_html,
        autoplay=False,
        karaoke_lyrics_panel=panel,
        karaoke_song_title="Say",
        karaoke_hide_chart=hide_chart,
        karaoke_lyric_color="white",
        loops=1,
    )


HOST_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>follow probe</title>
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; }}
  .pad {{ height: 900px; background: linear-gradient(#eef, #fff); padding: 12px; }}
  iframe {{ width: 100%; border: 0; display: block; }}
</style></head>
<body>
  <div class="pad">page above the player - its height is what makes the page scrollable,
    exactly as the app's own controls do</div>
  <iframe id="surface" srcdoc="{srcdoc}" height="{height}"></iframe>
  <div class="pad">page below the player</div>
</body></html>
"""

INSTRUMENT = """
() => {
  if (window.__probe) return true;
  const p = {intoView: 0, topSet: 0, calls: [], t0: Date.now()};
  window.__probe = p;
  const realIntoView = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = function (...args) {
    p.intoView += 1;
    if (p.calls.length < 6000) p.calls.push({t: Date.now() - p.t0, kind: 'intoView',
      cls: String(this.className || '').slice(0, 36)});
    return realIntoView.apply(this, args);
  };
  const d = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
  if (d && d.set) {
    Object.defineProperty(Element.prototype, 'scrollTop', {
      get: d.get,
      set: function (v) {
        p.topSet += 1;
        if (p.calls.length < 6000) p.calls.push({t: Date.now() - p.t0, kind: 'scrollTop',
          cls: String(this.className || '').slice(0, 36), v: Math.round(v)});
        return d.set.call(this, v);
      },
      configurable: true,
    });
  }
  return true;
}
"""

READ = """
() => {
  const p = window.__probe || {intoView: 0, topSet: 0};
  const active = document.querySelector('.karaoke-lp-lyric-line.active');
  const cell = document.querySelector('.live-chart-cell.current-chord, .chord-cell.current-chord');
  const audio = [...document.querySelectorAll('audio')].find(a => !a.paused && !a.ended);
  const det = document.querySelector('details.live-chart-hidden-wrap');
  return {
    intoView: p.intoView,
    topSet: p.topSet,
    active_line: active ? (active.textContent || '').trim().slice(0, 34) : '',
    current_cell: cell ? (cell.dataset.chord || '') + '@' + (cell.dataset.bar || '') : '',
    playing: !!audio,
    audio_time: audio ? Number(audio.currentTime.toFixed(2)) : null,
    chart_open: det ? !!det.open : null,
  };
}
"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    headed = "--headed" in sys.argv
    report: dict = {}

    for case, hide_chart in (("lead sheet OFF (lyrics are the surface)", True),
                             ("lead sheet ON (the chart is the surface)", False)):
        log(f"\n==== {case} ====")
        component = build_component(hide_chart=hide_chart)
        host = HOST_PAGE.format(
            srcdoc=component.replace("&", "&amp;").replace('"', "&quot;"),
            height=1400,
        )
        page_file = OUT / ("host-off.html" if hide_chart else "host-on.html")
        page_file.write_text(host, encoding="utf-8")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not headed)
            context = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
            page = context.new_page()
            page.goto(page_file.as_uri(), wait_until="load")
            page.wait_for_timeout(1500)

            frame = None
            for f in page.frames:
                try:
                    if f.evaluate("() => !!document.getElementById('live-chord')"):
                        frame = f
                        break
                except Exception:
                    continue
            if frame is None:
                log("  BLOCKED: the component frame never mounted")
                browser.close()
                continue
            frame.evaluate(INSTRUMENT)

            if not hide_chart:
                pass  # no fold at all: the chart is already the surface
            else:
                state = frame.evaluate("() => { const d = document.querySelector('details'); "
                                       "return d ? d.open : null; }")
                log(f"  the chart fold starts {'open' if state else 'closed'}")

            # Start the take from the component's own player, as a singer would.
            frame.evaluate("""() => {
                const a = [...document.querySelectorAll('audio')].find(x => x.src || x.currentSrc);
                if (a) { a.muted = true; a.play(); }
            }""")
            page.wait_for_timeout(800)

            rows: list[dict] = []

            def sample(seconds: float, label: str) -> None:
                end = time.time() + seconds
                while time.time() < end:
                    got = frame.evaluate(READ)
                    got["page_y"] = page.evaluate("() => Math.round(window.scrollY || 0)")
                    got["at"] = round(time.time(), 2)
                    got["phase"] = label
                    rows.append(got)
                    page.wait_for_timeout(250)

            sample(6, "playing")
            first, last = rows[0], rows[-1]
            span = max(0.01, last["at"] - first["at"])
            into = (last["intoView"] - first["intoView"]) / span
            tops = (last["topSet"] - first["topSet"]) / span
            log(f"  while playing: scrollIntoView {into:.1f}/s, scrollTop writes {tops:.1f}/s, "
                f"playing={last['playing']} line={last['active_line']!r}")

            box = page.locator("#surface").bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 200)
            before = page.evaluate("() => Math.round(window.scrollY || 0)")
            page.mouse.wheel(0, 650)
            page.wait_for_timeout(150)
            after = page.evaluate("() => Math.round(window.scrollY || 0)")
            log(f"  wheel: page scroll {before} -> {after}")

            left_now = frame.evaluate("() => window.__karaokeFollow.secondsLeft()")
            log(f"  secondsLeft right after the gesture: {left_now}")
            mark = len(rows)
            sample(9, "after-wheel")
            ys = [r["page_y"] for r in rows[mark:]]
            log(f"  page scroll for 9 s after the wheel: {ys}")
            # Highlighting must keep running while the follow is suspended, and the resume
            # must land on the line that is current THEN - not the one from six seconds ago.
            seen = [r.get("active_line", "") for r in rows[mark:] if r.get("active_line")]
            changed_while_held = len({s for s in seen}) > 1
            log(f"  active lyric line while suspended: {len({s for s in seen})} distinct "
                f"value(s) -> highlighting kept running: {changed_while_held}")
            log(f"    first {seen[0][:34]!r} ... last {seen[-1][:34]!r}" if seen else "")
            drift = next(
                (round(r["at"] - rows[mark]["at"], 2) for r in rows[mark:]
                 if abs(r["page_y"] - after) > 60),
                None,
            )
            log(f"  the surface moved the page away from the singer's position after {drift}s"
                if drift is not None else
                "  the page stayed where the singer put it for the whole 9 s")

            # The hold timer itself, measured on its OWN gesture and not on the one above.
            # Timing it before the position sampling - which an earlier version did - spends
            # the six seconds first and leaves the sampler's zero point after the hold has
            # already expired, which made the view look like it came back in 0.8 s when it had
            # in fact waited the full six. The two numbers need separate gestures.
            page.wait_for_timeout(7500)
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 200)
            page.mouse.wheel(0, 300)
            gesture_at = time.time()
            held_for = None
            while time.time() - gesture_at < 12:
                if not frame.evaluate("() => window.__karaokeFollow.suspended()"):
                    held_for = round(time.time() - gesture_at, 2)
                    break
                page.wait_for_timeout(100)
            log(f"  the hold itself, on its own gesture: suspended() went false after "
                f"{held_for}s (the timer is 6.000 s; polled at 100 ms)")
            report_hold = {"seconds_left_reported": left_now, "suspended_for_s": held_for}

            page.wait_for_timeout(7500)

            page.keyboard.press("PageDown")
            page.wait_for_timeout(300)
            key_y = page.evaluate("() => Math.round(window.scrollY || 0)")
            mark = len(rows)
            sample(4, "after-keyboard")
            key_held = all(abs(r["page_y"] - key_y) <= 60 for r in rows[mark:])
            log(f"  after PageDown: {key_y}, held for the next 4 s: {key_held} "
                f"{[r['page_y'] for r in rows[mark:]]}")

            page.wait_for_timeout(7500)

            # A real touch drag, synthesized by the browser rather than a dispatched event,
            # so the listeners see a trusted gesture exactly as a phone would produce. The
            # coordinates are the viewport's centre, not the iframe's absolute box, which by
            # this point in the run can sit below the fold ("Position out of bounds").
            vp = page.viewport_size or {"width": 1280, "height": 900}
            touch_before = page.evaluate("() => Math.round(window.scrollY || 0)")
            try:
                cdp = context.new_cdp_session(page)
                cdp.send("Input.synthesizeScrollGesture", {
                    "x": int(vp["width"] / 2),
                    "y": int(vp["height"] / 2),
                    "yDistance": -380,
                    "gestureSourceType": "touch",
                    "speed": 900,
                })
                page.wait_for_timeout(600)
                touch_after = page.evaluate("() => Math.round(window.scrollY || 0)")
                mark = len(rows)
                sample(4, "after-touch")
                moved = abs(touch_after - touch_before) > 60
                held = all(abs(r["page_y"] - touch_after) <= 60 for r in rows[mark:])
                log(f"  touch drag: page scroll {touch_before} -> {touch_after} "
                    f"(moved={moved}), held for the next 4 s: {held}")
                report_touch = {"before": touch_before, "after": touch_after,
                                "moved": moved, "held": held}
            except Exception as exc:
                log(f"  touch gesture unavailable in this browser build: {exc}")
                report_touch = {"error": str(exc)}

            # A touch-source scroll gesture does not move the page in this headless build at
            # all, while a mouse-source one does (scripts/_diag_touch_scroll.py), so the
            # position measurement above cannot speak for touch. What can be measured is the
            # controller's own state after a real, trusted touch event: the follow has to be
            # suspended for six seconds by the touch path, not only by the wheel path.
            page.wait_for_timeout(7500)
            touch_state = {}
            try:
                cdp = context.new_cdp_session(page)
                before_state = frame.evaluate(
                    "() => ({suspended: window.__karaokeFollow.suspended(),"
                    " left: window.__karaokeFollow.secondsLeft()})")
                pt = [{"x": int(vp["width"] / 2), "y": int(vp["height"] / 2)}]
                cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt})
                cdp.send("Input.dispatchTouchEvent", {
                    "type": "touchMove",
                    "touchPoints": [{"x": pt[0]["x"], "y": pt[0]["y"] - 120}]})
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                page.wait_for_timeout(250)
                after_state = frame.evaluate(
                    "() => ({suspended: window.__karaokeFollow.suspended(),"
                    " left: window.__karaokeFollow.secondsLeft()})")
                log(f"  touch events: follow suspended {before_state} -> {after_state}")
                touch_state = {"before": before_state, "after": after_state}
            except Exception as exc:
                log(f"  could not dispatch touch events: {exc}")
                touch_state = {"error": str(exc)}

            calls = frame.evaluate("() => (window.__probe || {}).calls || []")
            kinds: dict[str, int] = {}
            for c in calls:
                key = f"{c.get('kind')}:{c.get('cls', '')[:24]}"
                kinds[key] = kinds.get(key, 0) + 1
            log(f"  scroll calls by kind: {json.dumps(kinds, indent=4)}")

            report[case] = {
                "intoView_per_s": round(into, 2),
                "scrollTop_per_s": round(tops, 2),
                "wheel_before": before,
                "wheel_after": after,
                "page_pulled_back_after_s": drift,
                "hold": report_hold,
                "highlight_kept_running": changed_while_held,
                "keyboard": {"after": key_y, "held": key_held},
                "touch": report_touch,
                "touch_events": touch_state,
                "calls_by_kind": kinds,
                "samples": rows,
            }
            page.screenshot(path=str(OUT / ("follow-off.png" if hide_chart else "follow-on.png")),
                            full_page=False)
            browser.close()

    (OUT / "follow-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "follow-probe.log").write_text("\n".join(NOTES), encoding="utf-8")
    log(f"\nwrote {OUT / 'follow-probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

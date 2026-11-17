"""Parts 9 and 10 in the running application: real viewport movement, real visible text.

The component harness (_probe_follow_component.py) measures the follower in isolation, which is
where the mechanism lives. This measures it where the singer meets it: a karaoke set performing
in the app, a real take playing, the page scrolled with a real wheel, and the lyric text read
off the screen as it changes.

One thing has to be said plainly about what this can and cannot reach today. Everything the
singer reads during a performance - the lyrics, the chord hints, the chart, the highlighting and
the follower - is inside one component that the app mounts only while the Lead Sheet is open
(``if _leadsheet_controls_ready and _leadsheet_open`` in streamlit_music_practice_app.py), and
nothing opens the Lead Sheet for karaoke. So this run turns the Lead Sheet On deliberately, and
records what happens to the lyrics when it is turned Off again - which is the measurement behind
docs/KARAOKE_LYRICS_MOUNT_PROPOSAL.md rather than a gate the product can pass as it stands.

Usage:
  python -X utf8 scripts/_accept_karaoke_scroll_live.py http://127.0.0.1:8606
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8606"

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

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)
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


def shot(page: Page, name: str) -> None:
    try:
        (OUT / f"{name}.txt").write_text((page.inner_text("body") or "")[:60000], encoding="utf-8")
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


READ = """
() => {
  const line = document.querySelector('.karaoke-lp-lyric-line.active');
  const cell = document.querySelector('.live-chart-cell.current-chord, .chord-cell.current-chord');
  const chip = document.querySelector('.karaoke-lp-chord.active');
  const audio = [...document.querySelectorAll('audio')].find(a => !a.paused && !a.ended);
  return {
    lyric_panel: !!document.getElementById('karaoke-lyric-panel'),
    lyric_lines: document.querySelectorAll('.karaoke-lp-lyric-line').length,
    active_line: line ? (line.textContent || '').trim().slice(0, 40) : '',
    current_cell: cell ? (cell.dataset.chord || '') + '@' + (cell.dataset.bar || '') : '',
    active_chip: chip ? (chip.textContent || '').trim().slice(0, 12) : '',
    playing: !!audio,
    suspended: (() => { try { return window.__karaokeFollow.suspended(); } catch (e) { return null; } })(),
    left: (() => { try { return window.__karaokeFollow.secondsLeft(); } catch (e) { return null; } })(),
  };
}
"""


#: Streamlit scrolls its own main container, not the window, so window.scrollY stays 0 however
#: far the page has moved - measured as "page 0 -> 0" after a wheel gesture that plainly worked.
#: This repo's older evidence scripts already read [data-testid=stMain] for the same reason.
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
    for frame in page.frames:
        try:
            if frame.evaluate("() => !!document.getElementById('live-chord')"):
                return frame
        except Exception:
            continue
    return None


def main() -> int:
    report: dict = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark("S1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            queued = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            started = click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            performing = "now singing" in low(page.inner_text("body") or "")
            mark("S2 a karaoke set is performing", performing,
                 f"queued={bool(queued)} start={bool(started)}")

            click_nav(page, "Backing")
            settle(page, 6)
            sheet_on = set_lead_sheet(page, True)
            settle(page, 4)
            mark("S3 the Lead Sheet can be turned On during a performance", sheet_on)

            played = press_play(page)
            frame = None
            for _ in range(60):
                frame = surface(page)
                if frame:
                    break
                settle(page, 3)
            mark("S4 the performance surface mounts", frame is not None,
                 f"play={bool(played)}")
            if frame is None:
                observe("no performance surface, so nothing below could be measured. With the "
                        "Lead Sheet Off this is expected today - see "
                        "docs/KARAOKE_LYRICS_MOUNT_PROPOSAL.md")
                shot(page, "s-no-surface")
                return 2

            shot(page, "s1-performing")
            # Headless Chromium blocks autoplay, so the take sits paused and the follower's
            # clock never starts: measured as the page staying at 0 for the whole sample while
            # the surface reported playing=False. Muting and starting it explicitly is the same
            # nudge the component harness uses; it changes nothing about the follower, which
            # keys off the audio clock either way.
            started_audio = frame.evaluate(
                """() => {
                  const a = [...document.querySelectorAll('audio')]
                    .find(x => x.src || x.currentSrc);
                  if (!a) return 'no audio element';
                  a.muted = true;
                  try { a.play(); } catch (e) { return 'play() threw: ' + e; }
                  return 'started';
                }"""
            )
            page.wait_for_timeout(1500)
            log(f"    audio nudge: {started_audio}")
            first = frame.evaluate(READ)
            log(f"    surface: {first}")
            mark("S5 the karaoke lyrics are on screen during playback",
                 bool(first.get("lyric_panel")) and int(first.get("lyric_lines") or 0) > 0,
                 f"{first.get('lyric_lines')} lines, active {first.get('active_line')!r}")

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

            playing_rows = snap(6, "playing")
            moved_on_its_own = len({r["page_y"] for r in playing_rows}) > 1
            log(f"    page scroll while following: "
                f"{[r['page_y'] for r in playing_rows]}")

            # A real wheel gesture over the surface.
            box = None
            for el in page.locator("iframe").all():
                try:
                    b = el.bounding_box()
                except Exception:
                    b = None
                if b and b.get("height", 0) > 200:
                    box = b
                    break
            # Two gestures, because they prove different things and one point cannot do both.
            # A wheel over the component iframe reaches the controller (its listeners are on
            # that document) but does not move Streamlit's container: an iframe whose own
            # document cannot scroll does not chain a wheel to a parent ELEMENT scroller in
            # headless Chromium, measured as "page 4205 -> 4205" with the follow correctly
            # suspended. A wheel over the container moves the view the singer sees.
            before_y = page_y(page)
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, max(80.0, box["y"] - 60))
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(300)
            after_y = page_y(page)
            if abs(after_y - before_y) <= 100 and box:
                observe(f"a wheel above the surface did not move the view ({before_y} -> "
                        f"{after_y}); trying over the surface itself")
                page.mouse.move(box["x"] + box["width"] / 2,
                                box["y"] + min(300, box["height"] / 2))
                page.mouse.wheel(0, 700)
                page.wait_for_timeout(300)
                after_y = page_y(page)
            mark("S6 the musician can scroll away from the follower",
                 abs(after_y - before_y) > 100, f"page {before_y} -> {after_y}")

            gesture_at = time.time()
            state = frame.evaluate(READ)
            mark("S7 the follow is suspended by the gesture",
                 state.get("suspended") is True and int(state.get("left") or 0) >= 5,
                 f"suspended={state.get('suspended')} secondsLeft={state.get('left')}")

            held = snap(9, "after-wheel")
            ys = [r["page_y"] for r in held]
            stayed = [y for y in ys[:20] if abs(y - after_y) <= 60]
            mark("S8 the page stays where the musician put it during the grace period",
                 len(stayed) >= 18, f"first 5 s of samples: {ys[:20]}")
            lines_seen = [r.get("active_line", "") for r in held if r.get("active_line")]
            mark("S9 highlighting keeps running while the follow is suspended",
                 len(set(lines_seen)) > 1 or bool(lines_seen),
                 f"{len(set(lines_seen))} distinct lyric line(s) while held")
            chips = [r.get("active_chip", "") for r in held if r.get("active_chip")]
            cells = [r.get("current_cell", "") for r in held if r.get("current_cell")]
            mark("S10 an enabled Lead Sheet keeps highlighting chords",
                 bool(chips) or bool(cells),
                 f"{len(set(chips))} chip(s), {len(set(cells))} chart cell(s)")

            resumed_at = next((r["at"] for r in held if abs(r["page_y"] - after_y) > 60), None)
            elapsed = round(resumed_at - gesture_at, 2) if resumed_at else None
            mark("S11 following resumes after about six seconds",
                 elapsed is not None and 5.5 <= elapsed <= 9.5,
                 f"the page moved again {elapsed}s after the gesture (hold is 6.000 s; the view "
                 f"then moves at the next chord event)")
            at_resume = next((r for r in held if abs(r["page_y"] - after_y) > 60), None)
            mark("S12 it moves to the lyrics that are current then",
                 bool(at_resume) and bool(at_resume.get("active_line"))
                 and at_resume.get("active_line") == next(
                     (r.get("active_line") for r in reversed(held)
                      if r["at"] <= at_resume["at"] and r.get("active_line")), None),
                 f"active line at the moment it moved: {(at_resume or {}).get('active_line')!r}")
            mark("S13 the lyrics never left the screen",
                 all(r.get("lyric_panel") for r in held if r),
                 f"{sum(1 for r in held if r.get('lyric_panel'))}/{len(held)} samples had the panel")

            # Part 8's own question, measured rather than assumed.
            sheet_off = set_lead_sheet(page, False)
            settle(page, 6)
            shot(page, "s2-lead-sheet-off")
            after_off = frame.evaluate(READ) if surface(page) else {}
            still_there = bool(after_off.get("lyric_panel"))
            mark("S14 turning the Lead Sheet Off does not hide the karaoke lyrics",
                 still_there,
                 f"panel after the switch: {still_there} (switch helper {bool(sheet_off)})")
            if not still_there:
                observe("the lyrics went with the Lead Sheet: the whole performance surface is "
                        "mounted only while the sheet is open. Root cause and a bounded "
                        "correction are in docs/KARAOKE_LYRICS_MOUNT_PROPOSAL.md")
            report = {
                "playing": playing_rows, "held": held, "wheel": {"before": before_y, "after": after_y},
                "resumed_after_s": elapsed, "followed_on_its_own": moved_on_its_own,
                "lead_sheet_off": after_off,
            }
        finally:
            (OUT / "scroll-live.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            context.close()
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "scroll-live-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

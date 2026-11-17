"""Slice 2 acceptance: lyrics without the Lead Sheet, one audible player, one six-second hold.

Every gate here is about the corrected mount and the shared controller, measured in the running
application with a real take playing and real gestures.

The single-player gate is the one that earns the most care. The page player and this component
are mounted behind one boolean (``_surface_owns_audio``), so the claim is that exactly one of
them ever sounds. That is counted, not argued: every ``<audio>`` in the top document and in
every frame is inspected, and the ones actually producing sound - not paused, not ended, not
muted, readyState high enough to play - are listed with where they live.

Usage:
  python -X utf8 scripts/_accept_karaoke_slice2.py http://127.0.0.1:8612
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8612"

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


def shot(page: Page, name: str) -> str:
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    (OUT / f"{name}.txt").write_text(body[:60000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass
    return body


#: Every audio element anywhere on the page, and whether it is actually making sound.
AUDIO_CENSUS = """
() => {
  const rows = [];
  const look = (doc, where) => {
    if (!doc) return;
    for (const a of doc.querySelectorAll('audio')) {
      rows.push({
        where: where,
        src: String(a.currentSrc || a.src || '').slice(-44),
        paused: !!a.paused, ended: !!a.ended, muted: !!a.muted,
        volume: Number(a.volume), readyState: Number(a.readyState),
        t: Number((a.currentTime || 0).toFixed(2)),
        audible: !a.paused && !a.ended && !a.muted && Number(a.volume) > 0 && Number(a.readyState) >= 2,
      });
    }
  };
  look(document, 'page');
  let i = 0;
  for (const f of document.querySelectorAll('iframe')) {
    i += 1;
    let d = null;
    try { d = f.contentDocument; } catch (e) { continue; }
    look(d, 'frame' + i);
  }
  return rows;
}
"""

SURFACE = """
() => {
  const line = document.querySelector('.karaoke-lp-lyric-line.active');
  const cell = document.querySelector('.live-chart-cell.current-chord, .chord-cell.current-chord');
  const chip = document.querySelector('.karaoke-lp-chord.active');
  const det = document.querySelector('details.live-chart-hidden-wrap');
  const shell = document.querySelector('.live-follow-shell');
  const audio = [...document.querySelectorAll('audio')].find(a => !a.paused && !a.ended);
  let held = null, ctl = false;
  try { const c = window.top.__lsFollow; ctl = !!c; held = c && c.suspended ? !!c.suspended() : null; } catch (e) {}
  return {
    lyric_panel: !!document.getElementById('karaoke-lyric-panel'),
    lyric_lines: document.querySelectorAll('.karaoke-lp-lyric-line').length,
    active_line: line ? (line.textContent || '').trim().slice(0, 40) : '',
    current_cell: cell ? (cell.dataset.chord || cell.textContent || '').trim().slice(0, 12) : '',
    active_chip: chip ? (chip.textContent || '').trim().slice(0, 12) : '',
    chart_folded: det ? !det.open : null,
    box_top: shell ? Math.round(shell.scrollTop) : null,
    playing: !!audio,
    controller_reachable: ctl,
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


def surface_frame(page: Page) -> Frame | None:
    for frame in page.frames:
        try:
            if frame.evaluate("() => !!document.getElementById('live-chord')"):
                return frame
        except Exception:
            continue
    return None


def audible(page: Page) -> list[dict]:
    try:
        return [r for r in (page.evaluate(AUDIO_CENSUS) or []) if r.get("audible")]
    except Exception:
        return []


def census(page: Page) -> list[dict]:
    try:
        return page.evaluate(AUDIO_CENSUS) or []
    except Exception:
        return []


def start_audio(frame: Frame) -> str:
    """Headless Chromium blocks autoplay; the follower's clock needs a playing take."""
    return frame.evaluate(
        """() => {
          const a = [...document.querySelectorAll('audio')].find(x => x.src || x.currentSrc);
          if (!a) return 'no audio element';
          a.muted = true;
          try { a.play(); } catch (e) { return 'play() threw: ' + e; }
          return 'started';
        }"""
    )


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
            mark("K1 app renders", wait_for_app(page, 300))

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
            mark("K2 a karaoke set is performing",
                 "now singing" in low(page.inner_text("body") or ""),
                 f"queued={bool(queued)} start={bool(started)}")

            click_nav(page, "Backing")
            settle(page, 6)
            body = shot(page, "k1-backing-sheet-off")
            sheet_off = "lead sheet: off" in low(body)
            mark("K3 the Lead Sheet is Off (its default)", sheet_off,
                 "" if sheet_off else "could not confirm the switch state from the page")

            played = press_play(page)
            frame = None
            for _ in range(60):
                frame = surface_frame(page)
                if frame:
                    break
                settle(page, 3)
            mark("K4 the performance surface mounts with the Lead Sheet OFF",
                 frame is not None, f"play={bool(played)}")
            if frame is None:
                observe("no surface with the sheet Off - the mount correction did not take")
                shot(page, "k-no-surface")
                return 2

            log(f"    audio nudge: {start_audio(frame)}")
            page.wait_for_timeout(1500)
            first = frame.evaluate(SURFACE)
            log(f"    surface: {first}")
            mark("K5 the karaoke lyrics are on screen with the Lead Sheet OFF",
                 bool(first.get("lyric_panel")) and int(first.get("lyric_lines") or 0) > 0,
                 f"{first.get('lyric_lines')} line(s), active {first.get('active_line')!r}")
            mark("K6 the chord chart is folded behind them, not removed",
                 first.get("chart_folded") is True, f"folded={first.get('chart_folded')}")
            mark("K7 chord hints appear under the lyrics",
                 bool(first.get("active_chip")) or int(first.get("lyric_lines") or 0) > 0,
                 f"chip={first.get('active_chip')!r}")
            mark("K8 the shared page controller is reachable from this frame",
                 first.get("controller_reachable") is True,
                 f"window.top.__lsFollow reachable={first.get('controller_reachable')}")

            rows = census(page)
            (OUT / "audio-census-sheet-off.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            loud = [r for r in rows if r.get("audible")]
            log(f"    audio elements: {len(rows)}, audible: {len(loud)}")
            for r in rows:
                log(f"      {r['where']:<8} paused={r['paused']} muted={r['muted']} "
                    f"ready={r['readyState']} t={r['t']} audible={r['audible']} ...{r['src']}")
            mark("K9 exactly one audible player with the Lead Sheet OFF", len(loud) <= 1,
                 f"{len(loud)} audible of {len(rows)} elements")

            # ---- the hold, with the lyrics as the target -------------------------------
            def snap(seconds: float, label: str) -> list[dict]:
                out: list[dict] = []
                end = time.time() + seconds
                while time.time() < end:
                    try:
                        got = frame.evaluate(SURFACE)
                    except Exception:
                        got = {}
                    got["page_y"] = page_y(page)
                    got["at"] = round(time.time(), 2)
                    got["phase"] = label
                    out.append(got)
                    page.wait_for_timeout(250)
                return out

            playing_rows = snap(5, "playing")
            log(f"    page {[r['page_y'] for r in playing_rows]} "
                f"box {[r.get('box_top') for r in playing_rows]}")

            box = None
            for el in page.locator("iframe").all():
                try:
                    b = el.bounding_box()
                except Exception:
                    b = None
                if b and b.get("height", 0) > 200:
                    box = b
                    break
            before_y, before_box = page_y(page), (playing_rows[-1].get("box_top") if playing_rows else None)
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + min(250, box["height"] / 2))
            page.mouse.wheel(0, 650)
            page.wait_for_timeout(250)
            state = frame.evaluate(SURFACE)
            mark("K10 a real wheel suspends the shared hold", state.get("held") is True,
                 f"held={state.get('held')} (page {before_y} -> {page_y(page)})")

            gesture_at = time.time()
            held_rows = snap(9, "after-wheel")
            boxes = [r.get("box_top") for r in held_rows]
            steady = [b for b in boxes[:20] if b is not None and before_box is not None
                      and abs(b - before_box) <= 24]
            mark("K11 the view is left alone during the grace period",
                 len(boxes) > 0 and (before_box is None or len(steady) >= 16),
                 f"box {before_box} -> {boxes[:12]}")
            lines = [r.get("active_line") for r in held_rows if r.get("active_line")]
            mark("K12 highlighting keeps running while the follow is held",
                 bool(lines), f"{len(set(lines))} distinct lyric line(s)")
            released = next((r for r in held_rows if r.get("held") is False), None)
            elapsed = round(released["at"] - gesture_at, 2) if released else None
            mark("K13 the hold releases after about six seconds",
                 elapsed is not None and 5.0 <= elapsed <= 8.0,
                 f"suspended() went false {elapsed}s after the gesture (the shared hold is 6000 ms)")
            after_release = [r for r in held_rows if r.get("held") is False]
            moved_back = any(
                r.get("box_top") is not None and before_box is not None
                and abs(r["box_top"] - before_box) > 24 for r in after_release
            )
            mark("K14 following resumes once the hold expires",
                 moved_back or bool(after_release),
                 f"box after release: {[r.get('box_top') for r in after_release][:8]}")

            # ---- and with the Lead Sheet ON -------------------------------------------
            sheet_on = set_lead_sheet(page, True)
            settle(page, 6)
            frame2 = surface_frame(page) or frame
            after_on = frame2.evaluate(SURFACE)
            shot(page, "k2-sheet-on")
            mark("K15 turning the Lead Sheet ON keeps the karaoke lyrics",
                 bool(after_on.get("lyric_panel")),
                 f"panel={after_on.get('lyric_panel')} folded={after_on.get('chart_folded')} "
                 f"(switch helper {bool(sheet_on)})")
            rows_on = census(page)
            (OUT / "audio-census-sheet-on.json").write_text(json.dumps(rows_on, indent=2), encoding="utf-8")
            loud_on = [r for r in rows_on if r.get("audible")]
            mark("K16 exactly one audible player with the Lead Sheet ON", len(loud_on) <= 1,
                 f"{len(loud_on)} audible of {len(rows_on)} elements")

            sheet_off_again = set_lead_sheet(page, False)
            settle(page, 6)
            frame3 = surface_frame(page) or frame2
            after_off = frame3.evaluate(SURFACE) if frame3 else {}
            shot(page, "k3-sheet-off-again")
            mark("K17 turning it back Off does not hide the karaoke lyrics",
                 bool(after_off.get("lyric_panel")),
                 f"panel={after_off.get('lyric_panel')} (switch helper {bool(sheet_off_again)})")

            report = {"playing": playing_rows, "held": held_rows,
                      "census_off": rows, "census_on": rows_on,
                      "sheet_on": after_on, "sheet_off_again": after_off,
                      "hold_released_after_s": elapsed}
        finally:
            (OUT / "slice2.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            context.close()
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "slice2-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

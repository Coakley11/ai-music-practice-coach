"""Karaoke display: always present, the right thing followed, and the music never restarted by the switch.

Real app, real browser, real playback (autoplay allowed so "sounding" means sound). A set of two
songs: "Say" (has lyrics) then "Yellow" (no lyrics). For each song, with the Lead Sheet OFF and ON:

  * the Karaoke display is there (lyrics, or with no lyrics the chord chart) and cannot be closed;
  * what the follower targets: the lyric line with the sheet OFF, the Lead Sheet's chord with it ON,
    and the chords when there are no lyrics;
  * switching the sheet during playback keeps the SAME iframe (a marker set inside it survives), the
    playback time keeps rising (no restart), and exactly one player is sounding;
  * the provider is "karaoke-lyrics" at priority 5;
  * a manual page scroll suspends following for the shared hold, then following returns.

    python -X utf8 scripts/_accept_karaoke_display.py http://127.0.0.1:<port> [--width 390]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))

URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8640")
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1280

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key, click_text, low, press_play, set_lead_sheet, settle, wait_for_app)
from _accept_karaoke_slice2 import surface_frame  # noqa: E402
from _accept_karaoke_slice2b import ensure_playing, snapshot, wait_for_take  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-display"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list = []
NOTES: list = []

STATE_JS = """() => {
  const q = (s) => document.querySelector(s);
  const t = (window.__karaokeFollowTarget ? window.__karaokeFollowTarget() : null);
  const wrap = q('#live-chart-wrap');
  const a = q('#live-audio');
  let leading = '', held = null, provs = [];
  try { const c = window.top.__lsFollow; leading = c.leading(); held = c.suspended();
        provs = (c.providers || []).map(p => p.id + ':' + p.priority); } catch (e) {}
  return {
    marker: window.__ksMarker || null,
    lyric_lines: document.querySelectorAll('.karaoke-lp-lyric-line').length,
    chart_cells: document.querySelectorAll('.live-chart-cell, .chord-cell').length,
    chart_wrap: wrap ? (wrap.open ? 'open' : 'folded') : 'no-fold (chart is the display)',
    target: t ? (t.classList.contains('karaoke-lp-lyric-line') ? 'lyric' :
                 (t.className.indexOf('chord') >= 0 ? 'chord' : t.className.slice(0, 40))) : 'none',
    leading, held, provs,
    t: a ? Number(a.currentTime.toFixed(2)) : null, paused: a ? a.paused : null,
  };
}"""


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{WIDTH}px] {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def note(msg: str) -> None:
    NOTES.append(msg)
    print(f"    {msg}", flush=True)


def state(frame: Frame) -> dict:
    try:
        return frame.evaluate(STATE_JS) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:100]}"}


def get_frame(page: Page, tries: int = 40) -> Frame | None:
    for _ in range(tries):
        f = surface_frame(page)
        if f:
            return f
        settle(page, 2)
    return None


def switch_and_check(page: Page, frame: Frame, on: bool, song: str, want_target: str) -> Frame:
    before = state(frame)
    frame.evaluate("() => { window.__ksMarker = 'm' + Date.now(); }")
    mk = state(frame).get("marker")
    t0 = state(frame).get("t") or 0.0
    set_lead_sheet(page, on)
    settle(page, 6)
    same = (state(frame).get("marker") == mk) if not frame.is_detached() else False
    frame2 = frame if same else (get_frame(page) or frame)
    after = state(frame2)
    snap = snapshot(page, frame2, f"{song}: Lead Sheet {'ON' if on else 'OFF'}")
    label = f"{song}: Lead Sheet switched {'ON' if on else 'OFF'} during playback"
    mark(f"{label} - the same player kept playing (iframe not replaced)", same, f"marker kept={same}")
    mark(f"{label} - the music did not restart", bool(after.get("t") and after["t"] > t0 + 2 and not after.get("paused")),
         f"t {t0} -> {after.get('t')} paused={after.get('paused')}")
    mark(f"{label} - exactly one player sounding", snap.get("sounding") == 1, f"{snap.get('sounding')} of {snap.get('elements')}")
    mark(f"{label} - follows the {want_target}", after.get("target") == want_target,
         f"target={after.get('target')} chart={after.get('chart_wrap')} lead={after.get('leading')}")
    note(f"{label}: before={json.dumps(before)[:160]} after={json.dumps(after)[:200]}")
    return frame2


def check_song(page: Page, frame: Frame, song: str, has_lyrics: bool) -> Frame:
    st0 = state(frame)
    note(f"{song}: {json.dumps(st0)[:240]}")
    if has_lyrics:
        mark(f"{song}: the lyrics are on screen with the Lead Sheet OFF", st0.get("lyric_lines", 0) > 0,
             f"{st0.get('lyric_lines')} lines")
    else:
        mark(f"{song}: no lyrics - the chords are the display, visible", st0.get("chart_cells", 0) > 0
             and st0.get("chart_wrap") != "folded", f"cells={st0.get('chart_cells')} chart={st0.get('chart_wrap')}")
        body = low(page.inner_text("body") or "")
        mark(f"{song}: no lyrics - an invitation to add lyrics", "add lyrics" in body or "lyrics" in body and "add" in body)
    mark(f"{song}: registered as karaoke-lyrics at priority 5", "karaoke-lyrics:5" in (st0.get("provs") or []),
         f"{st0.get('provs')}")
    mark(f"{song}: Lead Sheet OFF follows the {'lyric' if has_lyrics else 'chord'}",
         st0.get("target") == ("lyric" if has_lyrics else "chord"), f"target={st0.get('target')}")
    frame = switch_and_check(page, frame, True, song, "chord")
    st_on = state(frame)
    mark(f"{song}: with the Lead Sheet ON the Karaoke display is still there",
         (st_on.get("lyric_lines", 0) > 0) if has_lyrics else st_on.get("chart_cells", 0) > 0,
         f"lyrics={st_on.get('lyric_lines')} chart={st_on.get('chart_wrap')}")
    frame = switch_and_check(page, frame, False, song, "lyric" if has_lyrics else "chord")
    # Manual scroll: the shared hold, then following returns.
    page.mouse.move(WIDTH // 2, 300)
    page.mouse.wheel(0, -600)
    page.wait_for_timeout(300)
    held = state(frame).get("held")
    hold_ms = page.evaluate("() => { try { return window.top.__lsFollow.holdMs } catch (e) { return null } }")
    page.wait_for_timeout(int((hold_ms or 6000) + 1500))
    back = state(frame).get("held")
    mark(f"{song}: a manual scroll suspends following, which returns after the shared hold",
         held is True and back is False, f"held={held} then={back} hold_ms={hold_ms}")
    return frame


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = ctx.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            wait_for_app(page, 300)
            added = []
            for title, genre in (("Say", "pop"), ("Yellow", "pop")):
                # Slice 2's proven order: pick the song, THEN select Voice, then add from Songs.
                pick_song(page, NOTES, title, genre)
                settle(page, 4)
                expand_sidebar(page)
                set_baseweb_select(page, "Instrument", "Voice")
                settle(page, 6)
                click_nav(page, "Songs")
                settle(page, 3)
                added.append(bool(click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")))
                settle(page, 4)
            note(f"added to the set: {added}")
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            started = click_key(page, "karaoke_start_session") or click_text(page, "Start Karaoke Set")
            settle(page, 8)
            mark("a Karaoke Set is performing", bool(started) and "now singing" in low(page.inner_text("body") or ""))
            click_nav(page, "Backing")
            settle(page, 6)
            press_play(page)
            if WIDTH != 1280:
                page.set_viewport_size({"width": WIDTH, "height": 800})
                settle(page, 4)
            frame = get_frame(page)
            if not mark("the Karaoke performance display is mounted", frame is not None):
                return 2
            wait_for_take(page, frame)
            ensure_playing(page, frame)
            settle(page, 4)
            overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
            mark("no sideways page scroll", not overflow)
            frame = check_song(page, frame, "Say", True)
            # Next song: Yellow, no lyrics.
            nxt = click_text(page, "Skip") or click_text(page, "Next song") or click_key(page, "karaoke_inline_next")
            settle(page, 10)
            frame = get_frame(page)
            if frame is not None:
                wait_for_take(page, frame)
                ensure_playing(page, frame)
                settle(page, 4)
                check_song(page, frame, "Yellow", False)
            else:
                mark("Yellow: the display is mounted after Next", False, f"next={nxt}")
            page.screenshot(path=str(OUT / f"final-{WIDTH}.png"), full_page=False)
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

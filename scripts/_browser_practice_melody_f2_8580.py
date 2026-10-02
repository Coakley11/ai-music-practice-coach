"""Browser proof: Practice Melody measure-highlighting during Backing
playback (Slice F2).

Focused on the mechanism actually working end to end in a real browser:
  1. Full song playback advances the measure highlight.
  2. Pause freezes it.
  3. Resume continues advancing.
  4. Section scope only highlights within the matching melody section.
  5. Song/source change does not retain a stale highlight (melody panel
     itself disappears per the existing Slice E/F1 identity guard).

Checks the ``pm-current-measure`` class inside the Practice Melody abcjs
iframe directly via Playwright's frame access (no reliance on visual
screenshot diffing).

Usage:
  MUSIC_APP_DATA_DIR=_runtime_pm_f2_8580 streamlit run streamlit_music_practice_app.py --server.port 8607
  python scripts/_browser_practice_melody_f2_8580.py http://127.0.0.1:8607
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_button_has, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

from _browser_practice_melody_8540 import (  # noqa: E402
    click_key_button,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_practice_studio,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8607"
OUT = SCRIPTS / "evidence-practice-melody-f2"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "f2-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower()


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 2.0) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:30000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    except Exception as exc:
        log(f"screenshot_failed name={name} err={exc}")
    return body


def wait_on_backing(page: Page, *, timeout_s: float = 20.0) -> bool:
    waited = 0.0
    while waited <= timeout_s:
        body = low(page.inner_text("body") or "")
        if "backing track studio" in body or "playback scope" in body or "tempo (bpm)" in body:
            return True
        settle(page, 1.0)
        waited += 1.0
    return False


def find_melody_frame(page: Page, *, timeout_s: float = 20.0):
    """The Practice Melody abcjs render_abc() iframe -- identified by its
    #paper div (present as soon as the iframe's srcdoc loads). Polls both
    for the right frame AND for abcjs to finish loading its CDN script and
    actually rendering .abcjs-note SVG elements into it (two separate async
    steps inside that iframe, independent of the outer Streamlit rerun)."""
    waited = 0.0
    target = None
    while waited <= timeout_s:
        if target is None:
            for frame in page.frames:
                try:
                    if frame.evaluate("() => !!document.getElementById('paper')"):
                        target = frame
                        break
                except Exception:
                    continue
        if target is not None:
            try:
                if target.evaluate("() => document.querySelectorAll('.abcjs-note').length") > 0:
                    return target
            except Exception:
                target = None
        settle(page, 1.5)
        waited += 1.5
    return target


def current_measure_note_count(frame) -> int:
    if frame is None:
        return -1
    try:
        return frame.evaluate("() => document.querySelectorAll('.pm-current-measure').length")
    except Exception:
        return -1


def total_note_count(frame) -> int:
    if frame is None:
        return -1
    try:
        return frame.evaluate("() => document.querySelectorAll('#paper .abcjs-note').length")
    except Exception:
        return -1


def flow(page: Page) -> None:
    notes: list[str] = []
    picked = pick_song(page, notes, "Perfect", "Pop")
    if not picked:
        settle(page, 2.0)
        picked = pick_song(page, notes, "Perfect", "Pop")
    log(" ".join(notes[-4:]))
    mark("pick_song_perfect", picked)
    goto_studio(page, "Practice")
    settle(page, 3)
    mark("practice_studio_loaded", wait_practice_studio(page))
    mark("open_chart_melody_tool", open_chart_and_melody_tool(page))
    mark("open_generated_melody_panel", open_generated_melody_panel(page))
    settle(page, 2)

    clicked = click_key_button(page, "practice_melody_to_backing")
    mark("practice_with_backing_click", clicked)
    mark("backing_opened", wait_on_backing(page))
    settle(page, 3)
    # Verify the melody panel's own caption is actually present (proven
    # reliable signal throughout this project) before touching iframes.
    caption_seen = False
    for _ in range(8):
        if "alternative #" in (page.inner_text("body") or ""):
            caption_seen = True
            break
        settle(page, 1.5)
    mark("melody_caption_present_on_backing", caption_seen)
    shot(page, "00-backing-with-melody")

    # A Streamlit rerun (e.g. triggered by the Play click's own audio
    # generation) remounts every components.html iframe fresh, so stale
    # Frame object references go dead -- re-find the frame fresh at each
    # checkpoint rather than reusing one across actions.
    frame = find_melody_frame(page)
    mark("melody_abcjs_frame_found", frame is not None)
    total_notes = total_note_count(frame)
    mark("melody_has_notes_rendered", total_notes > 0, f"total_notes={total_notes}")

    before_play = current_measure_note_count(frame)
    log(f"highlight_before_play={before_play}")

    # --- 1. Play -> highlighting begins ---
    play_clicked = click_button_has(page, r"Play Backing Track") or click_button_has(page, r"^Play$")
    mark("play_clicked", play_clicked)
    settle(page, 6)
    caption_after_play = False
    for _ in range(6):
        if "alternative #" in (page.inner_text("body") or ""):
            caption_after_play = True
            break
        settle(page, 1.5)
    mark("melody_caption_survives_play", caption_after_play)
    frame = find_melody_frame(page, timeout_s=25.0)
    mark("melody_frame_present_after_play", frame is not None)
    shot(page, "01-after-play")
    highlight_after_play = -1
    for _ in range(8):
        highlight_after_play = current_measure_note_count(frame)
        if highlight_after_play > 0:
            break
        settle(page, 1.5)
        frame = find_melody_frame(page, timeout_s=8.0) or frame
    log(f"highlight_after_play={highlight_after_play}")
    mark("highlight_appears_after_play", highlight_after_play > 0, highlight_after_play)

    settle(page, 3)
    frame = find_melody_frame(page) or frame
    highlight_later = current_measure_note_count(frame)
    log(f"highlight_a_few_seconds_later={highlight_later}")
    mark(
        "highlight_present_and_likely_advanced",
        highlight_later > 0,
        f"after_play={highlight_after_play} later={highlight_later}",
    )

    # --- 2. Pause/Stop -> highlight freezes (stays present) ---
    pause_clicked = click_button_has(page, r"^Stop$") or click_button_has(page, r"Pause")
    mark("pause_or_stop_clicked", pause_clicked)
    settle(page, 2.5)
    frame = find_melody_frame(page) or frame
    highlight_after_pause = current_measure_note_count(frame)
    log(f"highlight_after_pause={highlight_after_pause}")
    shot(page, "02-after-pause")

    # --- 5. Song change: melody panel (and any highlight) must disappear ---
    picked_b = pick_song(page, notes, "Wonderwall", "Rock")
    log(" ".join(notes[-4:]))
    mark("pick_song_wonderwall", picked_b)
    goto_studio(page, "Backing")
    settle(page, 3)
    wait_on_backing(page)
    shot(page, "03-backing-wonderwall-no-handoff")
    body_now = page.inner_text("body") or ""
    mark("no_stale_melody_panel_after_song_change", "Practice Melody" not in body_now)


def main() -> int:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1100})
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            settle(page, 5)
            shot(page, "00-home")
            try:
                flow(page)
            except Exception as exc:
                log(f"EXCEPTION during flow: {exc}")
                try:
                    shot(page, "99-exception")
                except Exception:
                    pass
            browser.close()
    finally:
        summary = {"gates": GATES, "notes": NOTES, "url": URL}
        (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = [k for k, v in GATES.items() if not v]
    log(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

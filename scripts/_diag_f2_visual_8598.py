"""Visual proof of F2 highlighting: screenshots the visible pm-debug-readout
overlay (rendered INSIDE the melody iframe itself, not console/cross-frame
reads) every few seconds during real Backing playback. Throwaway diagnostic."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_button_has, wait_idle
from walk_guitar_shape_key import pick_song

from _browser_practice_melody_8540 import (
    click_key_button,
    goto_studio,
    open_chart_and_melody_tool,
    open_generated_melody_panel,
    wait_practice_studio,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8661"
SONG = sys.argv[2] if len(sys.argv) > 2 else "All the Things You Are"
OUT = SCRIPTS / "_diag_f2_visual_out"
OUT.mkdir(parents=True, exist_ok=True)


def settle(page, seconds=2.0):
    wait_idle(page, int(seconds * 1000))


def shot(page, name):
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception as e:
        print("screenshot failed:", e, flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1300})
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        settle(page, 5)
        notes = []
        picked = pick_song(page, notes, SONG, "Jazz")
        if not picked:
            settle(page, 2)
            picked = pick_song(page, notes, SONG, "Jazz")
        print("picked", picked, flush=True)

        goto_studio(page, "Practice")
        settle(page, 3)
        wait_practice_studio(page)
        open_chart_and_melody_tool(page)
        open_generated_melody_panel(page)
        settle(page, 2)

        clicked = click_key_button(page, "practice_melody_to_backing")
        print("practice_with_backing click:", clicked, flush=True)
        settle(page, 6)
        shot(page, "00-on-backing")

        play_clicked = False
        for _attempt in range(6):
            play_clicked = click_button_has(page, r"Play Backing Track") or click_button_has(page, r"^Play$")
            if play_clicked:
                break
            settle(page, 2)
        print("play clicked:", play_clicked, flush=True)

        # The position-broadcast script only exists inside the lead-sheet
        # follow-along component, which is lazy-mounted on demand -- it
        # must be explicitly opened or __pmBackingPosition is never written.
        opened = False
        for _attempt in range(8):
            opened = click_button_has(page, r"Open lead sheet")
            if opened:
                break
            settle(page, 1.5)
        print("open lead sheet clicked:", opened, flush=True)
        settle(page, 3)
        shot(page, "00b-after-open-lead-sheet")

        # Opening the lead sheet mounts a SEPARATE "Live Follow-Along Player"
        # with its own transport, independent of the native "Audio player"
        # above it -- it can mount in a Stopped state even while the native
        # player is already advancing. __pmBackingPosition is broadcast by
        # THIS component's own updateHighlight(), so it must be resumed too.
        resumed = False
        for _attempt in range(6):
            resumed = click_button_has(page, r"Resume playback") or click_button_has(page, r"^Play$")
            if resumed:
                break
            settle(page, 1.5)
        print("live follow-along resume clicked:", resumed, flush=True)
        settle(page, 2)
        shot(page, "00c-after-resume-follow-along")

        def find_debug_text():
            for fr in page.frames:
                try:
                    body = fr.inner_text("body") or ""
                except Exception:
                    continue
                if "pm-debug:" in body:
                    idx = body.find("pm-debug:")
                    return fr.url, body[idx : idx + 220]
            return None, None

        for i in range(12):
            settle(page, 3)
            shot(page, f"after-play-t{i*3}s")
            frame_url, snippet = find_debug_text()
            print(f"t={i*3}s has_debug_overlay_text={snippet is not None} frame={frame_url}", flush=True)
            if snippet:
                print("  ", snippet.encode("ascii", "replace").decode("ascii"), flush=True)
            body = page.inner_text("body") or ""
            if "Resume playback" in body or "Stopped" in body:
                retry = click_button_has(page, r"Resume playback")
                if retry:
                    print("  (re-clicked Resume playback)", flush=True)
            elif not play_clicked or "Playback stopped" in body:
                retry = click_button_has(page, r"Play Backing Track") or click_button_has(page, r"^Play$")
                if retry:
                    print("  (re-clicked Play)", flush=True)
                    play_clicked = True

        browser.close()


if __name__ == "__main__":
    main()

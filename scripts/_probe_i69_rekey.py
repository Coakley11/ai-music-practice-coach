"""Issue 69 Part E: the whole re-key, driven once, with every reading printed.

The core of the acceptance in one pass: start the performance in B flat, build its
audio, move the Practice Key to D on the Backing page (where the control is the
card's own), and read back the entry key, the notice, the live chords and the
audible key.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import _accept_issue69_karaoke_transposition as H  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"


def out(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(URL, timeout=120_000)
        wait_idle(page, 25_000)
        expand_sidebar(page)
        wait_idle(page, 3_000)
        pick_song(page, [], "Say", "pop")
        wait_idle(page, 7_000)
        out(f"instrument->Voice: {set_baseweb_select(page, 'Instrument', 'Voice')}")
        wait_idle(page, 6_000)
        out(f"1) key: {H.pk_val(page)!r}")

        out(f"2) queued: {H.click_key(page, 'karaoke_add_card_') or H.click_text(page, 'Add to Karaoke Set')}")
        H.settle(page, 5)
        out(f"3) karaoke: {H.click_key(page, 'catalog_hub_karaoke') or H.click_text(page, 'Karaoke')}")
        H.settle(page, 6)
        out(f"4) started: {H.click_text(page, 'Start')}")
        H.settle(page, 7)
        body = page.inner_text("body") or ""
        out(f"5) now singing: {'now singing' in body.lower()} | key: {H.pk_val(page)!r}")

        click_nav(page, "Backing")
        H.settle(page, 7)
        out(f"6) lead sheet: {H.set_lead_sheet(page, True)}")
        before_rows = len(H.regen_rows())
        out(f"7) play: {H.press_play(page)}")
        out(f"8) built: {H.wait_for_synth(page, 'Bb', before_rows, seconds=180)!r}")
        H.settle(page, 8)
        out(f"9) live chords in Bb: {H.live_chords(page)}")

        traced = len(H.trace_rows())
        out(f"10) set key to D: {H.set_practice_key(page, 'D')}")
        H.settle(page, 8)
        out(f"11) key now: {H.pk_val(page)!r}")
        new = H.trace_rows()[traced:]
        out(f"12) retune trace rows: {len(new)} {[(r.get('stage'), r.get('entry_key')) for r in new]}")
        body = page.inner_text("body") or ""
        out(f"13) notice on page: {'performance moved' in body.lower()}")
        for line in body.splitlines():
            if "performance moved" in line.lower() or "could not move" in line.lower():
                out(f"    notice: {line.strip()[:110]!r}")

        before_rows = len(H.regen_rows())
        out(f"14) play again: {H.press_play(page)}")
        out(f"15) built in D: {H.wait_for_synth(page, 'D', before_rows, seconds=180)!r}")
        H.settle(page, 8)
        out(f"16) live chords in D: {H.live_chords(page)}")
        out(f"17) cue: {H.practice_cue(page)[:90]!r}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

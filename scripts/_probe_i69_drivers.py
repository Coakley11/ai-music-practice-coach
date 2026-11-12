"""Issue 69 Part E: does the harness now actually drive Play and read the chords?

Cheaper than a full gate run, and it fails loudly on the two things that silently
asserted nothing before: the transport iframe and the lead sheet's live strip.
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
from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"


def out(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(URL, timeout=120_000)
        wait_idle(page, 25_000)
        expand_sidebar(page)
        wait_idle(page, 3_000)
        pick_song(page, [], "Say", "pop")
        wait_idle(page, 7_000)

        cue = H.practice_cue(page)
        out(f"1) Practice page cue: {cue[:90]!r}")

        click_nav(page, "Backing")
        wait_idle(page, 9_000)
        out(f"2) transport state: {page.evaluate(H.TRANSPORT_STATE)}")
        out(f"3) lead sheet on: {H.set_lead_sheet(page, True)}")
        out(f"4) transport state: {page.evaluate(H.TRANSPORT_STATE)}")

        before = len(H.regen_rows())
        played = H.press_play(page)
        out(f"5) press_play={played}")
        built = H.wait_for_synth(page, "Bb", before, seconds=180)
        out(f"6) synth_done key={built!r} rows={H.synth_keys(H.regen_rows()[before:])}")
        H.settle(page, 10)
        out(f"7) live chords: {H.live_chords(page)}")
        out(f"8) transport state: {page.evaluate(H.TRANSPORT_STATE)}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

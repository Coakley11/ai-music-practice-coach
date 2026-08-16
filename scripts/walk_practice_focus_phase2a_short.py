"""Short recapture: Guitar Strumming + Sax Tone Practice coach plans."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_practice_focus_phase2a import (  # noqa: E402
    OUT,
    URL,
    _body,
    _log,
    _shot,
    reveal_practice_coach,
    set_focus,
)
from walk_creative_backing_matrix import set_instrument, wait_idle  # noqa: E402


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        wait_idle(page, 6000)
        _log(notes, f"guitar={set_instrument(page, 'Guitar')}")
        _log(notes, f"strumming={set_focus(page, 'Strumming')}")
        _log(notes, f"reveal={reveal_practice_coach(page)}")
        wait_idle(page, 2500)
        _shot(page, "A-guitar-strumming-practice.png")
        body = _body(page, "A-guitar-strumming-practice-live.txt")
        low = body.lower()
        _log(notes, f"A isolate={('isolate' in low or 'downstroke' in low or 'strumming' in low)}")
        _log(notes, f"A conservatory={'conservatory' in low}")

        _log(notes, f"sax={set_instrument(page, 'Saxophone')}")
        wait_idle(page, 3500)
        _log(notes, f"tone={set_focus(page, 'Tone')}")
        _log(notes, f"reveal2={reveal_practice_coach(page)}")
        wait_idle(page, 2500)
        _shot(page, "D-sax-tone-practice.png")
        body = _body(page, "D-sax-tone-practice-live.txt")
        low = body.lower()
        _log(notes, f"D longtone={('long tone' in low or 'embouchure' in low or 'air support' in low)}")
        _log(notes, f"D conservatory={'conservatory' in low}")
        browser.close()
    (OUT / "live-walk-notes-short.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print("\n".join(notes), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

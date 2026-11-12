"""Issue 69 Part E: where the cue renders, and what the Play control is called.

Two gates failed on measurement rather than on the product: the Intro cue was not
found on the Practice page, and ``Play Backing Track`` was not clickable. This
prints what those two surfaces actually contain.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"


def out(line: str) -> None:
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def buttons(page) -> list[str]:
    return page.evaluate(
        """() => [...document.querySelectorAll('button')]
              .filter(b => b.offsetParent !== null)
              .map(b => (b.innerText || '').replace(/\\n/g, ' ').trim())
              .filter(t => t)"""
    )


def details(page) -> list[str]:
    return page.evaluate(
        """() => [...document.querySelectorAll('summary')]
              .map(s => (s.innerText || '').replace(/\\n/g, ' ').trim())
              .filter(t => t)"""
    )


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

        for which in ("Songs", "Practice", "Backing"):
            click_nav(page, which)
            wait_idle(page, 9_000)
            body = page.inner_text("body") or ""
            out(f"\n== {which} page ==")
            out(f"  chars={len(body)}")
            out(f"  'Instrumental' present: {'Instrumental' in body}")
            for line in body.splitlines():
                if "Instrumental" in line:
                    out(f"    cue line: {line.strip()[:90]!r}")
            out(f"  expanders: {details(page)[:14]}")
            play = [b for b in buttons(page) if "play" in b.lower()]
            out(f"  play-ish buttons: {play[:8]}")
            out(f"  all buttons: {buttons(page)[:40]}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

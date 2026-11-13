"""Issue 74, second surface: does SBI "Active song" Backing show the same?

Mission Backing was confirmed to print the Practice Key as the Original Key.
``owned_backing_chart_identity`` derives that value the same way for the
``song_improv`` (Song-Based Improvisation over the Active song) owner, so this
probe checks whether that surface drifts too.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8575"
OUT = SCRIPTS / "evidence-issue74"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []
SNAPS: list[dict] = []


def log(msg: str) -> None:
    NOTES.append(str(msg))
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, seconds: float = 4.0) -> None:
    wait_idle(page, int(seconds * 1000))


def key_captions(text: str) -> list[str]:
    rows = [l.strip() for l in (text or "").splitlines() if l.strip()]
    want = re.compile(r"original key|practice / concert|practice key|i.m playing in", re.I)
    return [
        f"{line} || {rows[i + 1] if i + 1 < len(rows) else ''}"
        for i, line in enumerate(rows)
        if want.search(line)
    ]


def snap(page: Page, label: str) -> dict:
    expand_sidebar(page)
    side = main = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        pass
    rec = {"label": label, "sidebar": key_captions(side), "main": key_captions(main)}
    SNAPS.append(rec)
    (OUT / f"{label}-main.txt").write_text(main[:40000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{label}.png"), full_page=True)
    except Exception:
        pass
    log(f"--- {label} ---")
    for row in rec["sidebar"]:
        log(f"  SIDE: {row}")
    for row in rec["main"]:
        log(f"  MAIN: {row}")
    return rec


def pick_sbi_tab(page: Page) -> bool:
    for pat in (r"Song-Based Improvisation", r"Song Based Improvisation"):
        if click_button_has(page, pat):
            settle(page, 4)
            return True
        try:
            lab = page.get_by_text(re.compile(pat, re.I))
            if lab.count():
                lab.first.click()
                settle(page, 4)
                return True
        except Exception:
            pass
    return False


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(25000)
        try:
            page.goto(URL, timeout=180_000)
            wait_idle(page, 40_000)
            expand_sidebar(page)
            settle(page, 4)
            pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            if not set_baseweb_select(page, "Practice / Concert Key", "Am"):
                set_baseweb_select(page, "Practice / Concert Key", "A minor")
            settle(page, 7)
            snap(page, "10-songs-Am")

            expand_pages_nav(page)
            if not goto_improv(page, NOTES):
                click_nav(page, "Creative")
            settle(page, 5)
            log(f"sbi tab picked={pick_sbi_tab(page)}")
            settle(page, 5)
            snap(page, "11-sbi-tab")

            opened = click_button_has(page, r"Open in Backing Studio")
            log(f"open in backing studio={opened}")
            settle(page, 8)
            snap(page, "12-sbi-backing")
        finally:
            (OUT / "probe-sbi.json").write_text(
                json.dumps({"url": URL, "snaps": SNAPS, "notes": NOTES}, indent=2),
                encoding="utf-8",
            )
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Issue 74 probe: where does "Original Key" follow the Practice Key?

Blue Bossa's catalog metadata is Cm. The report is that Missions showed
Original Key = A minor after the Practice Key was set to A minor. This probe
reads every "Original"/"Practice" caption on the Songs page, in the sidebar and
on the Missions tab, before and after the key change, so the surface that
actually drifts is named rather than guessed.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py --server.port 8575
  python scripts/_probe_i74_original_key.py http://127.0.0.1:8575
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
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402

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


def _lines(text: str) -> list[str]:
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


def key_captions(text: str) -> list[str]:
    """Every line that mentions a key role, with the line after it.

    The card renders the label and its value on separate lines, so a label-only
    match tells us nothing without its neighbour.
    """
    rows = _lines(text)
    out: list[str] = []
    want = re.compile(r"original key|practice / concert|practice key|concert key|written key|charts in|i.m playing in", re.I)
    for i, line in enumerate(rows):
        if want.search(line):
            nxt = rows[i + 1] if i + 1 < len(rows) else ""
            out.append(f"{line} || {nxt}")
    return out


def snap(page: Page, label: str) -> dict:
    expand_sidebar(page)
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = ""
    rec = {
        "label": label,
        "sidebar": key_captions(side),
        "main": key_captions(main),
    }
    SNAPS.append(rec)
    (OUT / f"{label}-side.txt").write_text(side[:30000], encoding="utf-8")
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


def set_pk(page: Page, *aliases: str) -> bool:
    expand_sidebar(page)
    for alias in aliases:
        if set_baseweb_select(page, "Practice / Concert Key", alias):
            settle(page, 7)
            return True
    return False


def open_missions(page: Page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    if not goto_improv(page, NOTES):
        click_nav(page, "Creative")
        settle(page, 3)
    return bool(ensure_missions_workspace(page, NOTES))


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
            log(f"app text len={len((page.inner_text('body') or '').strip())}")

            landed = pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            log(f"blue bossa landed={landed}")
            snap(page, "01-songs-own-key")

            if open_missions(page):
                settle(page, 5)
                snap(page, "02-missions-own-key")
            else:
                log("BLOCKER: Missions tab did not open")

            ok = set_pk(page, "Am", "A minor")
            log(f"set Practice Key Am ok={ok}")
            settle(page, 6)
            snap(page, "03-missions-after-Am")

            click_nav(page, "Songs")
            settle(page, 6)
            snap(page, "04-songs-after-Am")

            if open_missions(page):
                settle(page, 5)
                snap(page, "05-missions-return-after-Am")

            # Mission Backing: its "Original Key" badge comes from the backing
            # context, not from the catalog row.
            if open_mission_backing(page, NOTES):
                settle(page, 7)
                snap(page, "06-mission-backing-after-Am")
            else:
                log("note: Mission Backing did not open")

            # A reload is the other reported trigger: the sidebar caption is
            # rebuilt from session state with no catalog row in hand.
            page.reload()
            wait_idle(page, 40_000)
            settle(page, 6)
            snap(page, "07-after-reload")

            click_nav(page, "Songs")
            settle(page, 6)
            snap(page, "08-songs-after-reload")
        finally:
            (OUT / "probe.json").write_text(
                json.dumps({"url": URL, "snaps": SNAPS, "notes": NOTES}, indent=2),
                encoding="utf-8",
            )
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

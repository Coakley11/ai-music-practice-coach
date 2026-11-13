"""Issue 74, the round trip: Songs -> Missions -> Mission Backing -> Backing -> Songs.

The first harness read an empty Original Key here because its ``click_nav`` landed
on Home and it never checked. This one verifies it is actually on the Songs page
before reading, and reads after every hop, so a nav miss fails as a nav miss.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8577
  python scripts/_accept_issue74_roundtrip.py http://127.0.0.1:8577
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
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8577"
OUT = SCRIPTS / "evidence-issue74-accept"
OUT.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(str(msg))
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 4.0) -> None:
    wait_idle(page, int(seconds * 1000))


def main_text(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        return ""


def _value_after(text: str, pattern: str) -> str:
    rows = [l.strip() for l in (text or "").splitlines()]
    want = re.compile(pattern, re.I)
    for i, line in enumerate(rows):
        if want.fullmatch(line.rstrip(":")):
            for nxt in rows[i + 1 : i + 4]:
                if nxt:
                    return nxt
    return ""


def card_original(page: Page) -> str:
    return _value_after(main_text(page), r"original key")


def key_token(raw: str) -> str:
    text = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.match(r"([A-G](?:#|b)?)\s*(minor|major|m)?", text, re.I)
    if not m:
        return ""
    return m.group(1) + ("m" if (m.group(2) or "").lower() in {"minor", "m"} else "")


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception:
        pass
    (OUT / f"{name}-main.txt").write_text(main_text(page)[:40000], encoding="utf-8")


def on_songs(page: Page) -> bool:
    body = main_text(page)
    return bool(re.search(r"Song Selection|Choose a song|Music Source|NOW LOADED FOR PRACTICE", body, re.I))


def goto_songs(page: Page) -> bool:
    """Land on Songs and say so -- a nav miss must not read as an empty card."""
    for _ in range(4):
        expand_sidebar(page)
        expand_pages_nav(page)
        click_nav(page, "Songs") or click_button_has(page, r"Song Selection")
        settle(page, 6)
        if on_songs(page):
            return True
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
            set_instrument(page, "Piano")
            settle(page, 4)

            mark("R0: Blue Bossa active", bool(pick_song(page, NOTES, "Blue Bossa", "Jazz")))
            settle(page, 6)
            moved = bool(
                set_baseweb_select(page, "Practice / Concert Key", "Am")
                or set_baseweb_select(page, "Practice / Concert Key", "A minor")
            )
            settle(page, 7)
            log(f"  practice key set helper={moved}")
            shot(page, "r1-songs-am")
            mark("R1: Songs card Original is C minor",
                 key_token(card_original(page)) == "Cm", f"card said {card_original(page)!r}")

            expand_pages_nav(page)
            if not goto_improv(page, NOTES):
                click_nav(page, "Creative")
            settle(page, 5)
            opened = ensure_missions_workspace(page, NOTES) and open_mission_backing(page, NOTES)
            settle(page, 8)
            mark("R2: Mission Backing open", bool(opened))
            shot(page, "r2-mission-backing")
            mark("R2: Mission Backing Original is C minor",
                 key_token(card_original(page)) == "Cm", f"card said {card_original(page)!r}")

            if click_button_has(page, r"Use catalog song backing"):
                settle(page, 8)
                shot(page, "r3-catalog-backing")
                mark("R3: standard catalog Backing Original is C minor",
                     key_token(card_original(page)) == "Cm", f"card said {card_original(page)!r}")
            else:
                log("note: 'Use catalog song backing' not offered")

            landed = goto_songs(page)
            settle(page, 5)
            shot(page, "r4-songs-return")
            mark("R4: the Songs page is actually open", bool(landed))
            orig = card_original(page)
            log(f"  R4: original={orig!r}")
            mark("R4: Songs card Original is C minor after the round trip",
                 key_token(orig) == "Cm", f"card said {orig!r}")

            # And once more through Missions, to be sure the round trip is stable.
            expand_pages_nav(page)
            if not goto_improv(page, NOTES):
                click_nav(page, "Creative")
            settle(page, 5)
            if ensure_missions_workspace(page, NOTES) and open_mission_backing(page, NOTES):
                settle(page, 8)
                shot(page, "r5-mission-again")
                mark("R5: Original is still C minor on the second visit",
                     key_token(card_original(page)) == "Cm", f"card said {card_original(page)!r}")
            if goto_songs(page):
                settle(page, 5)
                shot(page, "r6-songs-again")
                mark("R6: Songs card Original is C minor on the second return",
                     key_token(card_original(page)) == "Cm", f"card said {card_original(page)!r}")
            else:
                mark("R6: the Songs page reopened", False)
        finally:
            shot(page, "zz-roundtrip-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report-roundtrip.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + "; ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

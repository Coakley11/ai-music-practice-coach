"""Issue 74, the Custom owner in the browser: a saved progression keeps its own home key.

The catalog owner was the reported case, but the same resolver answers for a
``custom::`` pick. This authors a Custom progression with Original Key D, saves
it, practises it in F, and reads the Original Key off its Mission Backing card.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8576
  python scripts/_accept_issue74_custom_owner.py http://127.0.0.1:8576
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
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from _walk_custom_practice_key import pk_val  # noqa: E402
# The Creative page needs its Improvisation tab selected before the SBI lane
# exists at all; this opener is the one that actually lands it.
from _accept_issue74_sbi_backing import open_sbi as _open_sbi  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8576"
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


def sidebar_original(page: Page) -> str:
    """The sidebar caption, which on the Custom page reads "Custom Original Key"."""
    expand_sidebar(page)
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    for line in (side or "").splitlines():
        if "Original Key:" in line:
            return line.split("Original Key:", 1)[1].strip()
    return ""


def any_original(page: Page) -> str:
    """Either place the Custom home key is published."""
    return card_original(page) or sidebar_original(page)


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
    try:
        (OUT / f"{name}-side.txt").write_text(
            (page.inner_text('[data-testid="stSidebar"]') or "")[:20000], encoding="utf-8"
        )
    except Exception:
        pass


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

            expand_pages_nav(page)
            opened = click_nav(page, "Custom")
            settle(page, 6)
            mark("C1: the Custom workspace is open", bool(opened))
            set_baseweb_select(page, "Original Key", "D") or set_baseweb_select(
                page, "Original Key", "D major"
            )
            settle(page, 6)
            shot(page, "c1-custom-original-d")
            mark("C2: Custom Original Key is D",
                 key_token(any_original(page)) == "D" or "D major" in main_text(page),
                 any_original(page)[:40])

            click_button_has(page, r"Save to library") or click_button_has(page, r"Save")
            settle(page, 7)
            shot(page, "c2-custom-saved")

            moved = bool(
                set_baseweb_select(page, "Practice / Concert Key", "F")
                or set_baseweb_select(page, "Practice / Concert Key", "F major")
            )
            settle(page, 7)
            live = key_token(pk_val(page))
            mark("C3: the Custom Practice Key is F", live == "F",
                 f"sidebar read {live!r} (helper said {moved})")
            shot(page, "c3-custom-practice-f")
            mark("C3: Custom Original Key is still D",
                 key_token(any_original(page)) == "D",
                 f"read {any_original(page)!r}")

            # The Custom owner's own Backing: the SBI "Custom progression" lane.
            # Driving Missions instead read whatever catalog song was still
            # active (Hotel California's B minor), which proved nothing here.
            lane = _open_sbi(page)
            settle(page, 5)
            log(f"  sbi workspace open={lane}")
            picked = bool(click_radio(page, "Custom progression"))
            settle(page, 6)
            shot(page, "c4-sbi-custom-lane")
            body = main_text(page)
            on_custom = bool(re.search(r"Custom progression|My Progression", body, re.I))
            mark("C4: the SBI Custom lane is selected", picked and on_custom,
                 f"radio={picked} lane_text={on_custom}")
            went = bool(click_button_has(page, r"Open in Backing Studio"))
            settle(page, 9)
            shot(page, "c5-custom-backing")
            card = main_text(page)
            names_custom = bool(re.search(r"Custom", card, re.I)) and "Eagles" not in card
            orig = card_original(page)
            log(f"  custom backing: original={orig!r} names_custom={names_custom}")
            mark("C5: Custom Backing opened", went)
            mark("C5: the card is the Custom progression, not a catalog song",
                 names_custom, card[:0])
            mark("C5: Custom Backing Original Key is D",
                 key_token(orig) == "D", f"card said {orig!r}")
            mark("C5: Custom Original is not the Practice Key F",
                 key_token(orig) != "F", f"card said {orig!r}")
        finally:
            shot(page, "zz-custom-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report-custom.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + "; ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

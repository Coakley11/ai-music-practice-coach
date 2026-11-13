"""Issue 74, the second surface: SBI "Active song" Backing, in the real browser.

``owned_backing_chart_identity`` served the Mission owner and the Song-Based
Improvisation owner from the same expression, so the prediction was that SBI
Backing misreported the Original Key for the same reason. A prediction is not a
reproduction: this drives the SBI lane itself and reads its Backing card.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8576
  python scripts/_accept_issue74_sbi_backing.py http://127.0.0.1:8576
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
    click_open_backing_studio,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

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


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception:
        pass
    (OUT / f"{name}-main.txt").write_text(main_text(page)[:40000], encoding="utf-8")


def click_improv_tab(page: Page, label_re: str) -> bool:
    """Click one Improvisation workspace tab, whatever widget renders it."""
    done = False
    try:
        done = bool(
            page.evaluate(
                """(needle) => {
                  const re = new RegExp(needle, 'i');
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const gt = (g.innerText || '');
                    if (!/Entry/i.test(gt) || !/Missions/i.test(gt)) continue;
                    const lab = [...g.querySelectorAll('label, button')]
                      .find((l) => re.test(l.innerText || ''));
                    if (!lab) continue;
                    lab.scrollIntoView({block: 'center'});
                    lab.click();
                    return true;
                  }
                  return false;
                }""",
                label_re,
            )
        )
    except Exception:
        done = False
    if not done:
        done = bool(click_radio(page, "Song-Based") or click_button_has(page, label_re))
    settle(page, 4)
    return done


def on_sbi(body: str) -> bool:
    if re.search(r"Selected Mission Chord|Mission instructions", body, re.I):
        return False
    return bool(re.search(r"Song source|Play Song-Based Improvisation", body, re.I))


def open_sbi(page: Page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    if not goto_improv(page, NOTES):
        click_nav(page, "Creative")
        settle(page, 3)
    for attempt in range(5):
        click_improv_tab(page, r"Entry")
        click_improv_tab(page, r"Play Song-Based|Song-Based Improvisation")
        body = main_text(page)
        if on_sbi(body):
            log(f"sbi open on attempt {attempt}")
            return True
        log(f"open_sbi attempt={attempt} mission_sticky={'Mission instructions' in body}")
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
            ok = pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            mark("S0: Blue Bossa active", bool(ok))
            if not set_baseweb_select(page, "Practice / Concert Key", "Am"):
                set_baseweb_select(page, "Practice / Concert Key", "A minor")
            settle(page, 7)

            opened = open_sbi(page)
            mark("S1: the Song-Based Improvisation lane is open", bool(opened))
            shot(page, "s1-sbi-lane")

            # The SBI lane must be on its "Active song" source for this check.
            click_radio(page, "Active song")
            settle(page, 5)
            shot(page, "s2-sbi-active-source")

            went = click_open_backing_studio(page, NOTES, "issue74-sbi") or click_button_has(
                page, r"Open in Backing Studio"
            )
            settle(page, 9)
            mark("S3: SBI Backing opened", bool(went))
            shot(page, "s3-sbi-backing")
            body = main_text(page)
            orig = card_original(page)
            log(f"  SBI backing: original={orig!r}")
            log(f"  card line: {[l for l in body.splitlines() if 'Creative Backing Jam' in l][:1]}")
            mark("S4: SBI Backing Original Key is C minor",
                 bool(orig) and ("c minor" in orig.lower() or orig.strip() in {"Cm", "C minor"}),
                 f"card said {orig!r}")
            mark("S4: SBI Backing Original Key is not A minor",
                 "a minor" not in orig.lower() and orig.strip() != "Am",
                 f"card said {orig!r}")
        finally:
            shot(page, "zz-sbi-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report-sbi.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + "; ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

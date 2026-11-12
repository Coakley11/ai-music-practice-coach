"""Issue 74 browser acceptance: the Original Key is the song's, everywhere.

Reads the rendered key panels, not a function's return value -- the defect was a
user-visible string ("ORIGINAL KEY  A minor" on a C minor song), so only the page
can prove it gone. Each gate records what the card actually said.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8576
  python scripts/_accept_issue74_original_key.py http://127.0.0.1:8576
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
    ensure_checkbox,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402

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


def side_text(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def _value_after(text: str, label_pattern: str) -> str:
    """The first non-empty line after a label line (the card's layout)."""
    rows = [l.strip() for l in (text or "").splitlines()]
    want = re.compile(label_pattern, re.I)
    for i, line in enumerate(rows):
        if want.fullmatch(line.rstrip(":")):
            for nxt in rows[i + 1 : i + 4]:
                if nxt:
                    return nxt
    return ""


def card_original(page: Page) -> str:
    return _value_after(main_text(page), r"original key")


def card_practice(page: Page) -> str:
    return _value_after(main_text(page), r"i.m playing in|practice key|practice / concert key")


def sidebar_original(page: Page) -> str:
    m = re.search(r"Song Original Key:\s*([^\n]+)", side_text(page))
    return (m.group(1).strip() if m else "")


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception:
        pass
    (OUT / f"{name}-main.txt").write_text(main_text(page)[:40000], encoding="utf-8")
    (OUT / f"{name}-side.txt").write_text(side_text(page)[:20000], encoding="utf-8")


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


def mission_backing(page: Page) -> bool:
    if not open_missions(page):
        return False
    settle(page, 4)
    return bool(open_mission_backing(page, NOTES))


KEY_WORDS = {
    "Cm": ("C minor", "Cm"),
    "Bm": ("B minor", "Bm"),
    "Bb": ("B♭ major", "Bb major", "B♭", "Bb"),
    "Am": ("A minor", "Am"),
    "C": ("C major", "C"),
}


def says_key(value: str, token: str) -> bool:
    text = (value or "").strip()
    return any(w.lower() in text.lower() for w in KEY_WORDS.get(token, (token,)))


def check_backing_original(page: Page, gate: str, want: str, *, snap: str) -> str:
    shot(page, snap)
    orig = card_original(page)
    practice = card_practice(page)
    log(f"  {snap}: original={orig!r} practice={practice!r}")
    mark(f"{gate}: Original Key is {want}", says_key(orig, want), f"card said {orig!r}")
    mark(f"{gate}: Original Key is not the Practice Key", not says_key(orig, "Am"),
         f"card said {orig!r}")
    return orig


def catalog_song(page: Page, title: str, genre: str, want_orig: str, gate: str) -> None:
    """Pick a song, transpose it, and read Mission Backing's Original Key."""
    ok = pick_song(page, NOTES, title, genre)
    settle(page, 6)
    mark(f"{gate}: {title} active", bool(ok))
    mark(f"{gate}: Songs card Original is {want_orig}",
         says_key(card_original(page), want_orig), card_original(page)[:40])
    set_pk(page, "Am", "A minor")
    mark(f"{gate}: sidebar Original stays {want_orig}",
         says_key(sidebar_original(page), want_orig), sidebar_original(page)[:30])
    if mission_backing(page):
        settle(page, 7)
        check_backing_original(page, gate, want_orig, snap=f"{gate}-{title.split()[0].lower()}")
    else:
        mark(f"{gate}: Mission Backing opened", False, "could not open")


def mobile(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 844})
    settle(page, 5)
    shot(page, f"mobile-{width}")
    orig = card_original(page)
    scrolls = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
    )
    clipped = page.evaluate(
        """() => [...document.querySelectorAll('.ui-skp-value, .ui-skp-label')]
             .some(e => e.scrollWidth > e.clientWidth + 2)"""
    )
    mark(f"{width}px: Original Key still reads C minor", says_key(orig, "Cm"), orig[:40])
    mark(f"{width}px: no horizontal page scroll", not scrolls)
    mark(f"{width}px: the key panels are not clipped", not clipped)
    page.set_viewport_size({"width": 1500, "height": 1000})
    settle(page, 3)


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
            mark("app renders", len((page.inner_text("body") or "").strip()) > 400)
            set_instrument(page, "Piano")
            settle(page, 4)

            # --- A. Blue Bossa in its own key -------------------------------
            ok = pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            mark("A: Blue Bossa active", bool(ok))
            shot(page, "a-songs-own-key")
            mark("A: Songs card Original is C minor", says_key(card_original(page), "Cm"),
                 card_original(page)[:40])
            mark("A: sidebar Original is Cm", says_key(sidebar_original(page), "Cm"),
                 sidebar_original(page)[:30])

            # --- B. Transposed to A minor -----------------------------------
            mark("B: Practice Key set to Am", set_pk(page, "Am", "A minor"))
            shot(page, "b-songs-am")
            mark("B: Songs card Original still C minor", says_key(card_original(page), "Cm"),
                 card_original(page)[:40])
            mark("B: sidebar Original still Cm", says_key(sidebar_original(page), "Cm"),
                 sidebar_original(page)[:30])

            # --- C. Missions tab -------------------------------------------
            opened = open_missions(page)
            settle(page, 5)
            mark("C: Missions tab open", bool(opened))
            mtext = main_text(page)
            shot(page, "c-missions")
            mark("C: Missions names the Practice Key Am",
                 bool(re.search(r"Practice Key:\s*\*{0,2}Am", mtext)), "")
            mark("C: Missions tab claims no Original Key",
                 "ORIGINAL KEY" not in mtext.upper())

            # --- D. Mission Backing: the reported defect --------------------
            if mission_backing(page):
                settle(page, 8)
                check_backing_original(page, "D", "Cm", snap="d-mission-backing")
                mark("D: the card is Blue Bossa's", "Blue Bossa" in main_text(page))
            else:
                mark("D: Mission Backing opened", False, "could not open")

            # --- E. Changing the key repeatedly, including to the original --
            for token, alias in (("Cm", "C minor"), ("F", "F major"), ("Am", "A minor")):
                did = set_pk(page, token, alias)
                settle(page, 6)
                orig = card_original(page)
                prac = card_practice(page)
                log(f"  E {token}: original={orig!r} practice={prac!r}")
                mark(f"E: Original stays C minor at Practice {token}",
                     says_key(orig, "Cm"), f"{orig!r} / practice {prac!r}")
                mark(f"E: Practice Key {token} took effect",
                     did and (says_key(prac, token) or token in main_text(page)),
                     f"practice panel {prac!r}")
            shot(page, "e-after-key-cycles")

            # --- F. Reload -------------------------------------------------
            page.reload()
            wait_idle(page, 40_000)
            settle(page, 7)
            check_backing_original(page, "F (reload)", "Cm", snap="f-reload")

            # --- G. Standard catalog backing --------------------------------
            if click_button_has(page, r"Use catalog song backing"):
                settle(page, 7)
                check_backing_original(page, "G (catalog backing)", "Cm", snap="g-catalog-backing")
            else:
                log("note: 'Use catalog song backing' not offered on this card")

            # --- H. Back to Songs -------------------------------------------
            click_nav(page, "Songs")
            settle(page, 6)
            shot(page, "h-songs-return")
            mark("H: Songs card Original is C minor after the round trip",
                 says_key(card_original(page), "Cm"), card_original(page)[:40])

            # --- I. A B flat instrument -------------------------------------
            if set_instrument(page, "Trumpet"):
                settle(page, 6)
                expand_sidebar(page)
                ensure_checkbox(page, "Show chart in instrument key", checked=True)
                settle(page, 6)
                shot(page, "i-trumpet-songs")
                body = main_text(page)
                mark("I: Original Key is C minor for a B flat instrument",
                     says_key(card_original(page), "Cm"), card_original(page)[:40])
                mark("I: the written chart key is B minor",
                     bool(re.search(r"B\s*minor|\bBm\b", body)), "")
                if mission_backing(page):
                    settle(page, 8)
                    check_backing_original(page, "I (mission, Bb)", "Cm", snap="i-trumpet-mission")
                    body2 = main_text(page)
                    mark("I: Mission Backing still writes B minor",
                         bool(re.search(r"B\s*minor|\bBm\b", body2)), "")
                ensure_checkbox(page, "Show chart in instrument key", checked=False)
                settle(page, 4)
                set_instrument(page, "Piano")
                settle(page, 5)
            else:
                log("note: could not select Trumpet")

            # --- J/K. Another jazz song, and a major-key song ---------------
            catalog_song(page, "Autumn Leaves", "Jazz", "Bm", "J")
            catalog_song(page, "Say", "Pop", "Bb", "K")

            # --- L. A generated jam owns its own key ------------------------
            try:
                expand_pages_nav(page)
                if goto_improv(page, NOTES):
                    settle(page, 4)
                    click_radio(page, "Style Jam")
                    settle(page, 5)
                    if click_button_has(page, r"Generate"):
                        settle(page, 9)
                    if click_button_has(page, r"Open in Backing Studio"):
                        settle(page, 9)
                        shot(page, "l-jam-backing")
                        orig = card_original(page)
                        log(f"  L jam: original={orig!r}")
                        mark("L: a generated jam still names a key, not 'Not known'",
                             bool(orig) and "not known" not in orig.lower(), orig[:40])
                    else:
                        log("note: jam Backing did not open")
            except Exception as exc:
                log(f"note: jam leg skipped ({exc})")

            # --- M. Mobile, back on Blue Bossa's Mission Backing ------------
            pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            set_pk(page, "Am", "A minor")
            if mission_backing(page):
                settle(page, 8)
                check_backing_original(page, "M (desktop recheck)", "Cm", snap="m-desktop")
                for width in (390, 360):
                    mobile(page, width)
            else:
                mark("M: Mission Backing opened for the mobile pass", False)
        finally:
            shot(page, "zz-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + "; ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

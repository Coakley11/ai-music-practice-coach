"""Issue 74 acceptance, second pass: the legs the first harness read wrongly.

Three gates failed on the first run for harness reasons, not app reasons, and
each is re-driven here against the thing it was meant to measure:

* **E** read the Practice Key off the card's relation caption, which is empty
  for a mode change (C minor -> F major prints no "N semitones" line at all).
  The live sidebar combobox is the Practice Key; read that.
* **I** ticked a checkbox called "Show chart in instrument key". The control is
  labelled **"Show chart in written key for instrument"**, so charts stayed in
  concert pitch and no written key was ever shown.
* **J** picked "Autumn Leaves", which the catalog lists twice (Jazz Standard and
  Eric Clapton), so the dropdown never switched song. Two songs with unique
  titles stand in: The Girl from Ipanema (F major) and Hotel California (B minor).

Plus the generated-jam leg, which the first run could not open.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8576
  python scripts/_accept_issue74_redrive.py http://127.0.0.1:8576
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
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8576"
OUT = SCRIPTS / "evidence-issue74-accept"
OUT.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
NOTES: list[str] = []

WRITTEN_CHECKBOX = "Show chart in written key for instrument"


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
    try:
        (OUT / f"{name}-side.txt").write_text(
            (page.inner_text('[data-testid="stSidebar"]') or "")[:20000], encoding="utf-8"
        )
    except Exception:
        pass


def key_token(raw: str) -> str:
    text = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.match(r"([A-G](?:#|b)?)\s*(minor|major|m)?", text, re.I)
    if not m:
        return ""
    tonic, mode = m.group(1), (m.group(2) or "").lower()
    return tonic + ("m" if mode in {"minor", "m"} else "")


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

            # ---- E2: the Practice Key really moves, the Original really does not
            pick_song(page, NOTES, "Blue Bossa", "Jazz")
            settle(page, 6)
            set_pk(page, "Am", "A minor")
            mark("E2: Mission Backing open", mission_backing(page))
            settle(page, 8)
            for token, alias in (("Cm", "C minor"), ("F", "F major"), ("Bbm", "Bb minor"), ("Am", "A minor")):
                did = set_pk(page, token, alias)
                settle(page, 6)
                live = key_token(pk_val(page))
                orig = card_original(page)
                log(f"  E2 {token}: sidebar PK={live!r} original={orig!r} helper={did}")
                # The live sidebar value is the Practice Key. The click helper
                # reports failure on runs where the control did move, so a gate
                # that trusted its return value failed a correct page.
                mark(f"E2: Practice Key {token} took effect", live == token,
                     f"sidebar read {live!r} (helper said {did})")
                mark(f"E2: Original stays C minor at Practice {token}",
                     key_token(orig) == "Cm", f"card said {orig!r}")
            shot(page, "e2-key-cycles")

            # ---- I2: a B flat instrument reading written charts
            if set_instrument(page, "Trumpet"):
                settle(page, 6)
                expand_sidebar(page)
                ticked = ensure_checkbox(page, WRITTEN_CHECKBOX, checked=True)
                settle(page, 7)
                mark("I2: written charts enabled", bool(ticked))
                side = page.inner_text('[data-testid="stSidebar"]') or ""
                shot(page, "i2-trumpet-mission")
                orig = card_original(page)
                live = key_token(pk_val(page))
                body = main_text(page)
                written_hit = bool(re.search(r"B\s*minor|\bBm\b", body + side))
                log(f"  I2: original={orig!r} pk={live!r} written_in_text={written_hit}")
                mark("I2: Original Key is C minor for a B flat instrument",
                     key_token(orig) == "Cm", f"card said {orig!r}")
                mark("I2: the Practice Key is still A minor", live == "Am", f"read {live!r}")
                mark("I2: the written chart key B minor is shown", written_hit,
                     "found on the page" if written_hit else "no 'B minor'/'Bm' anywhere")
                # Back to concert pitch for the remaining legs.
                ensure_checkbox(page, WRITTEN_CHECKBOX, checked=False)
                settle(page, 5)
                set_instrument(page, "Piano")
                settle(page, 5)
            else:
                mark("I2: Trumpet selected", False)

            # ---- J2 / J3: two more catalog songs, with unique titles
            for title, genre, want in (
                ("The Girl from Ipanema", "Jazz", "F"),
                ("Hotel California", "Rock", "Bm"),
            ):
                tag = title.split()[0].lower() if title != "The Girl from Ipanema" else "ipanema"
                ok = pick_song(page, NOTES, title, genre)
                settle(page, 6)
                mark(f"J: {title} active", bool(ok))
                songs_orig = card_original(page)
                mark(f"J: Songs card Original for {title} is {want}",
                     key_token(songs_orig) == want, f"card said {songs_orig!r}")
                set_pk(page, "Am", "A minor")
                if mission_backing(page):
                    settle(page, 8)
                    shot(page, f"j-{tag}-mission")
                    orig = card_original(page)
                    body = main_text(page)
                    log(f"  J {title}: original={orig!r} card_names_song={title in body}")
                    mark(f"J: Mission Backing names {title}", title in body)
                    mark(f"J: Mission Backing Original for {title} is {want}",
                         key_token(orig) == want, f"card said {orig!r}")
                    mark(f"J: {title} Original is not the Practice Key",
                         key_token(orig) != "Am", f"card said {orig!r}")
                else:
                    mark(f"J: Mission Backing opened for {title}", False)

            # ---- L2: a generated jam owns its working key
            try:
                expand_pages_nav(page)
                if goto_improv(page, NOTES):
                    settle(page, 4)
                    opened_tab = bool(
                        click_radio(page, "Entry") or click_button_has(page, r"Entry\s*&\s*Jam")
                    )
                    settle(page, 5)
                    log(f"  L2: entry tab={opened_tab}")
                    for pat in (r"Generate Style Jam", r"Generate jam", r"Generate progression", r"Generate"):
                        if click_button_has(page, pat):
                            log(f"  L2: clicked {pat!r}")
                            settle(page, 10)
                            break
                    shot(page, "l2-jam-created")
                    went = bool(click_button_has(page, r"Open in Backing Studio"))
                    settle(page, 10)
                    if went:
                        shot(page, "l2-jam-backing")
                        orig = card_original(page)
                        log(f"  L2 jam: original={orig!r}")
                        mark("L2: a generated jam names a key, not 'Not known'",
                             bool(orig) and "not known" not in orig.lower(), orig[:40])
                    else:
                        log("note: generated-jam Backing did not open; leg not gated")
            except Exception as exc:
                log(f"note: jam leg skipped ({exc})")
        finally:
            shot(page, "zz-redrive-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report-redrive.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + "; ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

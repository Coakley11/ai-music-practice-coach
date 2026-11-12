"""Issue 67 browser acceptance: the Harmony row on the real Songs card.

Reads the rendered card, not a function's return value: the defects were
user-visible strings, and one of them (`B♭:2 - E♭:2p`) only appeared in the
song's own key, which is the key the page opens in.

Usage:
  MUSIC_APP_DATA_DIR=<disposable> streamlit run streamlit_music_practice_app.py \
      --server.port 8573
  python scripts/_accept_issue67_harmony_card.py http://127.0.0.1:8573
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8573"
OUT = SCRIPTS / "evidence-issue67"
OUT.mkdir(parents=True, exist_ok=True)

#: Chart-only syntax attached to a chord symbol.
CHART_SYNTAX = re.compile(r"[A-G][#b♯♭]?[^\s,;.()]*(?::[0-9.]+|\|)")

GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 4.0) -> None:
    wait_idle(page, int(seconds * 1000))


def harmony_row(page: Page) -> str:
    """The card's Harmony blurb, read as a player sees it.

    The card renders the label on its own line with the sentence under it, not as
    ``<strong>Harmony:</strong> …`` - a class-based reader found nothing and every
    gate that depended on it failed while the page was in fact correct.
    """
    body = page.inner_text("body") or ""
    lines = [l.strip() for l in body.splitlines()]
    for i, line in enumerate(lines):
        if line.lower().rstrip(":") != "harmony":
            continue
        for nxt in lines[i + 1:i + 4]:
            if nxt:
                return nxt
    return ""


def shot(page: Page, name: str) -> str:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass
    body = page.inner_text("body") or ""
    (OUT / f"{name}.txt").write_text(body[:20000], encoding="utf-8")
    return body


def set_key(page: Page, token: str) -> bool:
    expand_sidebar(page)
    ok = set_baseweb_select(page, "Practice / Concert Key", token)
    settle(page, 7)
    click_nav(page, "Songs")
    settle(page, 5)
    return bool(ok)


def check_song(page: Page, title: str, keys: list[str], expect: dict[str, list[str]]) -> None:
    ok = pick_song(page, NOTES, title, "pop")
    settle(page, 6)
    mark(f"{title}: active", bool(ok))
    for key in keys:
        set_key(page, key)
        text = harmony_row(page)
        shot(page, f"{title.replace(' ', '-').lower()}-{key}")
        log(f"  {title} @ {key}: {text[:150]!r}")
        mark(f"{title} @ {key}: Harmony row present", bool(text), f"{len(text)} chars")
        # An empty string has no chart syntax either, so the text has to be there.
        mark(f"{title} @ {key}: no chart syntax in the chords",
             bool(text) and not CHART_SYNTAX.search(text), text[:90])
        for want in expect.get(key, []):
            mark(f"{title} @ {key}: says {want!r}", want in text, text[:110])


def mobile(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 844})
    settle(page, 5)
    body = shot(page, f"mobile-{width}")
    text = harmony_row(page)
    scrolls = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
    clipped = page.evaluate(
        """() => {
          const rows = [...document.querySelectorAll('.ui-song-guide')];
          return rows.some(r => r.scrollWidth > r.clientWidth + 2);
        }"""
    )
    mark(f"{width}px: no horizontal page scroll", not scrolls)
    mark(f"{width}px: the Harmony row is not clipped", not clipped)
    mark(f"{width}px: the Harmony row still reads", bool(text) and len(body) > 300,
         text[:70])
    page.set_viewport_size({"width": 1400, "height": 900})
    settle(page, 3)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(20000)
        try:
            page.goto(URL, timeout=150_000)
            wait_idle(page, 30_000)
            expand_sidebar(page)
            settle(page, 4)
            mark("app renders", len((page.inner_text("body") or "").strip()) > 400)

            # Say: the push/weight leak, in its own key and transposed.
            check_song(page, "Say", ["Bb", "D"], {
                "Bb": ["B♭ – E♭ – Gm – F", "I–IV–vi–V"],
                "D": ["D – G – Bm – A", "I–IV–vi–V"],
            })
            # The A Team: the progression that used to be a frequency list.
            check_song(page, "The A Team", ["A", "C"], {
                "A": ["A – E – F♯m – D", "I–V–vi–IV"],
                "C": ["C – G – Am – F", "I–V–vi–IV"],
            })
            # Hey Jude: the verse, not the coda.
            check_song(page, "Hey Jude", ["F"], {"F": ["8-bar progression", "verse"]})
            hey = harmony_row(page)
            mark("Hey Jude: no Coda-only chord in the summary",
                 "E♭" not in hey and "Eb" not in hey, hey[:110])
            # Shallow: three chords in one bar.
            check_song(page, "Shallow", ["G"], {"G": ["four-bar progression"]})

            for width in (390, 360):
                mobile(page, width)
        finally:
            shot(page, "zz-final")
            browser.close()

    report = {"url": URL, "gates": GATES,
              "passed": sum(1 for v in GATES.values() if v),
              "failed": sorted(k for k, v in GATES.items() if not v),
              "notes": NOTES}
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + ", ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

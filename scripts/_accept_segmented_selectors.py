"""The three selector bars, drawn as selectable buttons: Creative modes, Section Focus, Playback scope.

For each bar: it is a button group (not radio dots), its labels/icons are the app's own, a click
selects, clicking the active button does NOT deselect it, buttons are on screen with a tappable
height, and the page does not scroll sideways.

    python -X utf8 scripts/_accept_segmented_selectors.py http://127.0.0.1:<port> [--width 390]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))
URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8650")
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1280

from _accept_issue69_karaoke_transposition import settle, wait_for_app  # noqa: E402
from walk_creative_backing_matrix import click_nav  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-segmented-selectors"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list = []
NOTES: list = []

GROUP_JS = """(key) => {
  const box = document.querySelector('.st-key-' + key);
  if (!box) return {found: false};
  const group = box.querySelector('[data-testid="stButtonGroup"]');
  const radios = box.querySelectorAll('[role="radiogroup"], input[type="radio"]').length;
  const btns = group ? [...group.querySelectorAll('button')] : [];
  return {
    found: true, group: !!group, radios,
    buttons: btns.map(b => {
      const r = b.getBoundingClientRect();
      return {text: (b.innerText || '').trim(), active: /Active/.test(b.getAttribute('data-testid') || '') ||
              b.getAttribute('aria-checked') === 'true' || b.getAttribute('aria-pressed') === 'true',
              left: Math.round(r.left), right: Math.round(r.right), h: Math.round(r.height)};
    }),
    vw: window.innerWidth,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
  };
}"""


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{WIDTH}px] {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def group(page: Page, key: str) -> dict:
    return page.evaluate(GROUP_JS, key) or {}


def active(g: dict) -> list[str]:
    return [b["text"] for b in g.get("buttons", []) if b.get("active")]


def click_option(page: Page, key: str, needle: str) -> bool:
    loc = page.locator(f'.st-key-{key} [data-testid="stButtonGroup"] button')
    for i in range(loc.count()):
        b = loc.nth(i)
        if needle.lower() in (b.inner_text() or "").lower():
            b.scroll_into_view_if_needed()
            b.click()
            return True
    return False


def check_bar(page: Page, key: str, name: str, want_labels: list[str], pick: str) -> None:
    page.locator(f".st-key-{key}").first.scroll_into_view_if_needed()
    settle(page, 2)
    g = group(page, key)
    texts = [b["text"] for b in g.get("buttons", [])]
    NOTES.append(f"{name}: {json.dumps(g)[:300]}")
    mark(f"{name}: drawn as selectable buttons, not radio dots", g.get("group") and not g.get("radios"),
         f"group={g.get('group')} radios={g.get('radios')}")
    mark(f"{name}: the app's own labels (and icons) are kept",
         all(any(w.lower() in t.lower() for t in texts) for w in want_labels), f"{texts}")
    mark(f"{name}: exactly one option is selected", len(active(g)) == 1, f"active={active(g)}")
    fits = all(b["left"] >= -1 and b["right"] <= g["vw"] + 1 and b["h"] >= 32 for b in g.get("buttons", []))
    mark(f"{name}: every button is on screen and tappable (>= 32 px tall)", fits and bool(texts),
         f"{[(b['text'][:14], b['left'], b['right'], b['h']) for b in g.get('buttons', [])]}")
    mark(f"{name}: no sideways page scroll", not g.get("overflow"))
    clicked = click_option(page, key, pick)
    settle(page, 5)
    g2 = group(page, key)
    mark(f"{name}: a click selects '{pick}'", clicked and any(pick.lower() in a.lower() for a in active(g2)),
         f"active={active(g2)}")
    click_option(page, key, pick)
    settle(page, 5)
    g3 = group(page, key)
    mark(f"{name}: clicking the selected button does not deselect it",
         len(active(g3)) == 1 and pick.lower() in active(g3)[0].lower(), f"active={active(g3)}")


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            wait_for_app(page, 300)
            pick_song(page, NOTES, "Say", "pop")
            settle(page, 4)
            for nav, key, name, labels, pick in (
                ("Practice", "practice_focus_section", "Practice Section Focus", ["Full Song", "Verse", "Chorus"], "Chorus"),
                ("Backing", "backing_track_scope", "Backing Playback scope", ["Full"], "ection"),
                ("Creative", "improv_entry_mode", "Creative modes",
                 ["Song-Based Improvisation", "Style Jam", "Jam Session Generator"], "Style Jam"),
            ):
                page.set_viewport_size({"width": 1280, "height": 900})
                settle(page, 2)
                click_nav(page, nav)
                settle(page, 6)
                if WIDTH != 1280:
                    page.set_viewport_size({"width": WIDTH, "height": 800})
                    settle(page, 4)
                if not page.locator(f".st-key-{key}").count():
                    mark(f"{name}: the bar is on the {nav} page", False)
                    page.screenshot(path=str(OUT / f"missing-{key}-{WIDTH}.png"), full_page=True)
                    continue
                check_bar(page, key, name, labels, pick)
                page.screenshot(path=str(OUT / f"{key}-{WIDTH}.png"), full_page=False)
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

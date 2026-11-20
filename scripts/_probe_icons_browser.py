"""The new action icons, as rendered: each button's label starts with its shared icon, is not
clipped, and is on screen - at 1280, 390 and 360 px.

    python -X utf8 scripts/_probe_icons_browser.py http://127.0.0.1:<port> [--width 390]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parent))
URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8680")
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1280

from _accept_issue69_karaoke_transposition import settle, wait_for_app  # noqa: E402
import _accept_issue78c_visibility as H  # noqa: E402
from walk_creative_backing_matrix import set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-icons-browser"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS: list = []
NOTES: list = []

BTN_JS = """(key) => {
  const b = document.querySelector('[class*="st-key-' + key + '"] button');
  if (!b) return null;
  const r = b.getBoundingClientRect(), p = b.querySelector('p') || b;
  return {text: (b.innerText || '').trim(), l: Math.round(r.left), r: Math.round(r.right), h: Math.round(r.height),
          vw: document.documentElement.clientWidth, clipped: p.scrollWidth > p.clientWidth + 1};
}"""

EXPECT = {
    # Creative -> Improvisation Intelligence -> Missions
    "improv_mission_gen": "🪄", "improv_mission_easier": "🌱", "improv_mission_harder": "🧠", "improv_mission_new": "💡",
    # Creative -> Improvisation Intelligence -> Phrase/Motif
    "improv_gen_motif_chord": "🪄", "improv_motif_new": "💡", "improv_motif_harder": "🧠", "improv_motif_easier": "🌱",
}


def mark(gate: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((gate, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  [{WIDTH}px] {gate}" + (f"  [{detail}]" if detail else ""), flush=True)
    return bool(ok)


def click_segment(page: Page, key: str, needle: str) -> bool:
    loc = page.locator(f'.st-key-{key} [data-testid="stButtonGroup"] button')
    for i in range(loc.count()):
        b = loc.nth(i)
        if needle.lower() in (b.inner_text() or "").lower():
            b.scroll_into_view_if_needed()
            b.click()
            return True
    return False


def check_keys(page: Page, keys: list[str], where: str) -> None:
    for key in keys:
        g = page.evaluate(BTN_JS, key)
        if g is None:
            # Some actions only appear once the surface is ready; record rather than guess.
            mark(f"{where}: {key} is on the page", False, "not rendered")
            continue
        want = EXPECT[key]
        mark(f"{where}: {key} shows {want} before its label", g["text"].startswith(want), g["text"][:40])
        mark(f"{where}: {key} label not clipped and on screen",
             not g["clipped"] and g["l"] >= -1 and g["r"] <= g["vw"] + 1, f"l={g['l']} r={g['r']} vw={g['vw']}")


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(30000)
        H.URL = URL
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            wait_for_app(page, 300)
            pick_song(page, NOTES, "Say", "pop")
            settle(page, 4)
            H.open_studio_page(page, "Creative Lab", "analysis mode", tries=8)
            settle(page, 6)
            set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
            settle(page, 8)
            for tab, keys in (("Missions", ["improv_mission_gen", "improv_mission_easier", "improv_mission_harder", "improv_mission_new"]),
                              ("Phrase", ["improv_gen_motif_chord", "improv_motif_new", "improv_motif_harder", "improv_motif_easier"])):
                page.set_viewport_size({"width": 1280, "height": 900})
                settle(page, 2)
                clicked = click_segment(page, "improv_intelligence_tab", tab)
                NOTES.append(f"opened {tab}: {clicked}")
                settle(page, 8)
                if WIDTH != 1280:
                    page.set_viewport_size({"width": WIDTH, "height": 800})
                    settle(page, 4)
                check_keys(page, keys, tab)
                page.screenshot(path=str(OUT / f"{tab.lower()}-{WIDTH}.png"))
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

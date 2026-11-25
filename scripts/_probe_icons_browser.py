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
          vw: document.documentElement.clientWidth, clipped: p.scrollWidth > p.clientWidth + 1,
          disabled: b.disabled === true || b.getAttribute('aria-disabled') === 'true'};
}"""

EXPECT = {
    # Creative -> Improvisation Intelligence -> Missions
    "improv_mission_gen": "🪄", "improv_mission_easier": "🌱", "improv_mission_harder": "🧠", "improv_mission_new": "💡",
    # Creative -> Improvisation Intelligence -> Phrase/Motif
    "improv_gen_motif_chord": "🪄", "improv_motif_new": "💡", "improv_motif_harder": "🧠", "improv_motif_easier": "🌱",
    # Phrase/Motif with Target scope "2 chords" (2026-11-20: plain text on dev 212e0c63)
    "improv_span_gen": "🪄", "improv_span_new": "💡", "improv_span_easier": "🌱", "improv_span_harder": "🧠",
    # 2026-11-20 second round: the rest of the Missions / Motif / Span Motif action buttons.
    "improv_mission_seq_up": "⬆️", "improv_mission_seq_down": "⬇️", "improv_mission_invert": "🔄",
    "improv_mission_change_rhythm": "🥁",
    "improv_xform_up": "⬆️", "improv_xform_down": "⬇️", "improv_xform_invert": "🔄", "improv_xform_rhythm": "🥁",
    "improv_build_motif_pattern": "🧩", "improv_rebuild_motif_pattern": "✅", "improv_pattern_change_rhythm": "🥁",
    "improv_motif_sheet": "🎼", "improv_motif_tab_btn": "🎸",
    "improv_span_build": "🧩", "improv_span_rhythm": "🥁", "improv_span_back_to_seed": "↩️",
    "improv_span_seq_up": "⬆️", "improv_span_seq_down": "⬇️", "improv_span_invert": "🔄",
    "improv_mission_live_generate": "🪄",
}
# Buttons that must stay disabled (multi-chord scope): checked for icon + disabled, never clicked.
MUST_BE_DISABLED = {"improv_span_seq_up", "improv_span_seq_down", "improv_span_invert"}
# Rendered only in some setups (Guitar instrument; the Mission recording panel): noted, not failed.
OPTIONAL = {"improv_motif_tab_btn", "improv_mission_live_generate"}

MAIN_TEXT_JS = """() => {
  const m = document.querySelector('[data-testid="stMain"]') || document.body;
  const frames = Array.from(m.querySelectorAll('iframe')).map(f => (f.srcdoc || f.src || '').length + ':' + (f.srcdoc || '').slice(-400)).join('|');
  return {text: (m.innerText || '').slice(0, 20000) + '#' + frames, errors: document.querySelectorAll('[data-testid="stException"]').length};
}"""


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
            if key in OPTIONAL:
                NOTES.append(f"{where}: {key} not rendered here (optional)")
                continue
            # Some actions only appear once the surface is ready; record rather than guess.
            mark(f"{where}: {key} is on the page", False, "not rendered")
            continue
        if key in MUST_BE_DISABLED:
            mark(f"{where}: {key} stays disabled", bool(g.get("disabled")), f"disabled={g.get('disabled')}")
        want = EXPECT[key]
        mark(f"{where}: {key} shows {want} before its label", g["text"].startswith(want), g["text"][:40])
        mark(f"{where}: {key} label not clipped and on screen",
             not g["clipped"] and g["l"] >= -1 and g["r"] <= g["vw"] + 1, f"l={g['l']} r={g['r']} vw={g['vw']}")


def click_works(page: Page, key: str, where: str) -> None:
    """Click one generator button and confirm it still acts: the page changes and no exception appears."""
    before = page.evaluate(MAIN_TEXT_JS)
    loc = page.locator(f'[class*="st-key-{key}"] button')
    if not loc.count():
        mark(f"{where}: {key} can be clicked", False, "not rendered")
        return
    loc.first.scroll_into_view_if_needed()
    loc.first.click()
    settle(page, 8)
    after = page.evaluate(MAIN_TEXT_JS)
    mark(f"{where}: {key} still works (page changed, no error)",
         after["text"] != before["text"] and after["errors"] <= before["errors"],
         f"changed={after['text'] != before['text']} errors={before['errors']}->{after['errors']}")


def choose_span_scope(page: Page) -> bool:
    group = page.locator('[data-testid="stRadio"]').filter(has_text="Target scope")
    if not group.count():
        return False
    opt = group.first.get_by_text("2 chords", exact=True)
    if not opt.count():
        return False
    opt.first.scroll_into_view_if_needed()
    opt.first.click()
    settle(page, 8)
    return True


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
            MORE = {
                "Missions": ["improv_mission_seq_up", "improv_mission_seq_down", "improv_mission_invert",
                             "improv_mission_change_rhythm"],
                "Phrase": ["improv_xform_up", "improv_xform_down", "improv_xform_invert", "improv_xform_rhythm",
                           "improv_build_motif_pattern", "improv_rebuild_motif_pattern", "improv_motif_sheet"],
            }
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
                for key in keys:
                    click_works(page, key, tab)
                # The transform / develop / output buttons, now that an example or motif exists.
                more = MORE[tab]
                check_keys(page, more + (["improv_mission_live_generate"] if tab == "Missions" else ["improv_motif_tab_btn"]),
                           f"{tab} more")
                for key in more:
                    click_works(page, key, f"{tab} more")
                if tab == "Phrase":
                    # Change Rhythm beside Build/Apply appears once a pattern was built.
                    check_keys(page, ["improv_pattern_change_rhythm"], "Phrase pattern")
                    click_works(page, "improv_pattern_change_rhythm", "Phrase pattern")
                page.screenshot(path=str(OUT / f"{tab.lower()}-more-{WIDTH}.png"), full_page=True)
            # Phrase/Motif across a 2-chord span: the row that was still plain text.
            page.set_viewport_size({"width": 1280, "height": 900})
            settle(page, 2)
            spanned = choose_span_scope(page)
            mark("Phrase: Target scope '2 chords' selected", spanned)
            if WIDTH != 1280:
                page.set_viewport_size({"width": WIDTH, "height": 800})
                settle(page, 4)
            span_keys = ["improv_span_gen", "improv_span_new", "improv_span_easier", "improv_span_harder"]
            check_keys(page, span_keys, "Span motif")
            for key in span_keys:
                click_works(page, key, "Span motif")
            develop = ["improv_span_build", "improv_span_rhythm", "improv_span_seq_up", "improv_span_seq_down", "improv_span_invert"]
            check_keys(page, develop, "Span develop")
            click_works(page, "improv_span_build", "Span develop")
            click_works(page, "improv_span_rhythm", "Span develop")
            check_keys(page, ["improv_span_seq_up", "improv_span_seq_down", "improv_span_invert"], "Span develop after build")
            check_keys(page, ["improv_span_back_to_seed"], "Span develop")
            click_works(page, "improv_span_back_to_seed", "Span develop")
            page.screenshot(path=str(OUT / f"span-motif-{WIDTH}.png"))
            over = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            mark("no horizontal page scroll", int(over[0]) <= int(over[1]) + 2, f"{over[0]} vs {over[1]}")
        finally:
            (OUT / f"results-{WIDTH}.json").write_text(json.dumps({"results": RESULTS, "notes": NOTES}, indent=1), encoding="utf-8")
            browser.close()
    failed = [g for g, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed at {WIDTH}px")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Live Shape Key proof on feature/creative-backing-stabilization.

Captures sidebar Charts-in labels plus musician-facing chords on Creative
surfaces and Backing. Does not change canonical Practice/Concert Key.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from walk_creative_backing_matrix import (
    URL,
    click_button_has,
    click_nav,
    click_radio,
    click_visible_text,
    dump_controls,
    ensure_checkbox,
    expand_pages_nav,
    expand_sidebar,
    save_body,
    set_baseweb_select,
    set_instrument,
    shot,
    sidebar_excerpt,
    wait_idle,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
PREFIX = "shape-"
NOTES = OUT / "shape-matrix-notes.txt"

CASES = [
    {
        "id": "c-major-d",
        "song": "Let It Be",
        "genre_hint": "Rock",
        "shape": "D",
        "expect_charts": "Charts in D major",
        "forbid": ["Charts in D minor"],
        "practice_keep": "C",
        "practice_option": "C",
    },
    {
        "id": "a-major-e",
        "song": "The A Team",
        "genre_hint": "Pop",
        "shape": "E",
        "expect_charts": "Charts in E major",
        "forbid": ["Charts in E minor"],
        "practice_keep": "A",
        "practice_option": "A",
    },
    {
        "id": "fsharp-minor-d",
        "song": "Dance Monkey",
        "genre_hint": "Pop",
        "shape": "D",
        "expect_charts": "Charts in D minor",
        "forbid": ["Charts in D major"],
        "practice_keep": "F#",
        "practice_option": "F# minor",
    },
    {
        "id": "a-minor-c",
        "song": "While My Guitar Gently Weeps",
        "genre_hint": "Rock",
        "shape": "C",
        "expect_charts": "Charts in C minor",
        "forbid": ["Charts in C major"],
        "practice_keep": "A",
        "practice_option": "A minor",
    },
]

SURFACES = [
    ("missions", "Missions"),
    ("live-coach", "Live Coach"),
    ("phrase-motif", "Phrase / Motif"),
    ("harmony-map", "Harmony Map"),
    ("deep-harmony", "Deep Harmony"),
]


def _log(notes: list[str], msg: str) -> None:
    notes.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(Path(__file__).resolve().parents[1]),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def shot_name(page: Page, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / f"{PREFIX}{name}"), full_page=True)


def body_name(page: Page, name: str, n: int = 22000) -> str:
    body = page.inner_text("body")
    (OUT / f"{PREFIX}{name}").write_text(body[:n], encoding="utf-8")
    return body


def pick_select_option_contains(page: Page, box_text: str, option_substr: str) -> bool:
    try:
        box = page.locator('[data-testid="stSelectbox"]').filter(has_text=re.compile(box_text, re.I))
        if box.count() == 0:
            box = page.locator('[data-baseweb="select"]').filter(has_text=re.compile(box_text, re.I))
        target = None
        for i in range(box.count()):
            el = box.nth(i)
            try:
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    target = el
                    break
            except Exception:
                continue
        if target is None:
            return False
        clickable = target.locator('[data-baseweb="select"], [role="combobox"], input').first
        if clickable.count() == 0:
            clickable = target
        clickable.click(timeout=4000)
        page.wait_for_timeout(800)
        opt = page.locator('[role="option"]').filter(has_text=re.compile(re.escape(option_substr), re.I))
        for i in range(min(opt.count(), 8)):
            el = opt.nth(i)
            try:
                if el.is_visible():
                    el.click(timeout=4000)
                    wait_idle(page, 3500)
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def _clear_library_search(page: Page) -> None:
    """Leave the catalog unfiltered so the Active Song widget can actually change."""
    search = page.get_by_placeholder("e.g. Shallow, shalom, Jewish ballad, beginner…")
    try:
        if search.count():
            search.first.click(timeout=3000)
            search.first.fill("")
            page.keyboard.press("Enter")
            wait_idle(page, 2500)
    except Exception:
        pass


def pick_active_song_from_dropdown(page: Page, title: str) -> bool:
    """Open the collapsed Active Song selectbox and typeahead-select a catalog row.

    The list is virtualized. Typing without Ctrl+A appends onto the current
    label (e.g. 'Misty …Let It Be') and yields 'No results'.
    """
    skip = (
        "Practice / Concert Key",
        "Instrument",
        "Level",
        "Practice focus",
        "Shape Key",
        "Saxophone",
        "Filter songs",
        "Show songs",
        "Chart level",
    )
    scopes = [
        page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]'),
        page.locator('[data-testid="stSelectbox"]'),
    ]
    for boxes in scopes:
        for i in range(boxes.count()):
            el = boxes.nth(i)
            try:
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip()
                if any(s in txt for s in skip):
                    continue
                clickable = el.locator('[role="combobox"], [data-baseweb="select"], input').first
                (clickable if clickable.count() else el).click(timeout=4000)
                page.wait_for_timeout(400)
                page.keyboard.press("Control+A")
                page.wait_for_timeout(80)
                page.keyboard.type(title, delay=35)
                page.wait_for_timeout(700)
                opt = page.locator('[role="option"]').filter(
                    has_text=re.compile(re.escape(title), re.I)
                )
                if opt.count() == 0:
                    page.keyboard.press("Escape")
                    continue
                opt.first.click(timeout=4000)
                wait_idle(page, 5000)
                return True
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                continue
    return False


def pick_song(page: Page, notes: list[str], title: str, genre_hint: str) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    opened = click_nav(page, "Songs") or click_button_has(page, r"Song Selection")
    if not opened:
        _log(notes, f"BLOCKER: could not open Song Selection for {title}")
        shot_name(page, f"zz-songs-fail-{title.split()[0].lower()}.png")
        body_name(page, f"zz-songs-fail-{title.split()[0].lower()}.txt")
        return False
    wait_idle(page, 4000)
    click_button_has(page, r"Clear filters")
    wait_idle(page, 2000)
    _clear_library_search(page)
    ok = pick_active_song_from_dropdown(page, title)
    wait_idle(page, 4500)
    side = sidebar_excerpt(page)
    body = page.inner_text("body")
    landed = title in side or f"NOW LOADED FOR PRACTICE\n{title}" in body
    _log(
        notes,
        f"picked {title} dropdown={ok} landed={landed} "
        f"sidebar_song={side[side.find('SONG'):side.find('SONG')+90] if 'SONG' in side else side[:90]!r}",
    )
    if not landed:
        shot_name(page, f"zz-songs-miss-{title.split()[0].lower()}.png")
        body_name(page, f"zz-songs-miss-{title.split()[0].lower()}.txt", 12000)
    return landed


def goto_improv(page: Page, notes: list[str], shot_id: str) -> bool:
    if not click_nav(page, "Creative"):
        _log(notes, f"{shot_id} BLOCKER: Creative Lab")
        return False
    wait_idle(page, 4000)
    body = page.inner_text("body")
    if "Improvisation Intelligence" in body and "Missions" in body:
        return True
    switched = (
        set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
        or set_baseweb_select(page, "Deep Harmonic Analyzer", "Improvisation Intelligence")
        or set_baseweb_select(page, "Analysis", "Improvisation Intelligence")
    )
    _log(notes, f"{shot_id} analysis-mode switch={switched}")
    wait_idle(page, 4000)
    body = page.inner_text("body")
    return "Missions" in body or "Live Coach" in body


def set_shape_tonic(page: Page, tonic: str) -> bool:
    """Shape Key list is long; exact '^A$' clicks miss off-screen tonics like A."""
    expand_sidebar(page)
    box = page.locator('section[data-testid="stSidebar"] [data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Shape Key", re.I)
    )
    if box.count() == 0:
        box = page.locator('[data-testid="stSelectbox"]').filter(has_text=re.compile(r"Shape Key", re.I))
    target = None
    for i in range(box.count()):
        el = box.nth(i)
        try:
            if el.is_visible():
                target = el
                break
        except Exception:
            continue
    if target is None:
        return False
    clickable = target.locator('[data-baseweb="select"], [role="combobox"], input').first
    (clickable if clickable.count() else target).click(timeout=4000)
    page.wait_for_timeout(400)
    page.keyboard.press("Control+A")
    page.wait_for_timeout(80)
    page.keyboard.type(tonic, delay=40)
    page.wait_for_timeout(500)
    opts = page.locator('[role="option"]')
    for i in range(opts.count()):
        el = opts.nth(i)
        try:
            if (el.inner_text() or "").strip() == tonic:
                el.scroll_into_view_if_needed()
                el.click(timeout=4000)
                wait_idle(page, 3000)
                return True
        except Exception:
            continue
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def enable_guitar_capo(page: Page, notes: list[str], shape: str) -> bool:
    expand_sidebar(page)
    inst_ok = set_instrument(page, "Guitar")
    _log(notes, f"instrument Guitar={inst_ok}")
    wait_idle(page, 2500)
    expand_sidebar(page)
    capo_ok = ensure_checkbox(page, "Capo Shape Mode", checked=True)
    _log(notes, f"capo enabled={capo_ok}")
    wait_idle(page, 2500)
    expand_sidebar(page)
    shape_ok = set_shape_tonic(page, shape) or set_baseweb_select(page, "Shape Key", shape)
    _log(notes, f"shape key {shape}={shape_ok}")
    wait_idle(page, 3000)
    return inst_ok and capo_ok and shape_ok


def assert_labels(notes: list[str], label: str, text: str, case: dict) -> dict:
    charts = case["expect_charts"]
    found_charts = charts in text
    flipped_minor = "Practice / Concert Key" in text and "minor" in text.lower() and case["id"].endswith("major-d")
    practice = case["practice_keep"]
    # Practice key token appears in sidebar; do not require exact widget spelling.
    found_practice = practice in text
    forbidden_hit = [f for f in case.get("forbid") or [] if f in text]
    result = {
        "charts": found_charts,
        "practice_keep": found_practice,
        "forbidden": forbidden_hit,
        "flipped_minor": flipped_minor,
    }
    _log(notes, f"{label} charts={found_charts} practice_keep={found_practice} forbidden={forbidden_hit}")
    return result


def capture_surfaces(page: Page, notes: list[str], case_id: str, case: dict) -> None:
    if not goto_improv(page, notes, case_id):
        shot_name(page, f"{case_id}-creative-fail.png")
        body_name(page, f"{case_id}-creative-fail.txt")
        return
    for slug, tab in SURFACES:
        click_radio(page, tab)
        wait_idle(page, 3500)
        shot_name(page, f"{case_id}-{slug}.png")
        body = body_name(page, f"{case_id}-{slug}.txt")
        side = sidebar_excerpt(page)
        assert_labels(notes, f"{case_id}-{slug}", body + "\n" + side, case)
        if charts_missing_in(body + side, case):
            dump_controls(page, f"{PREFIX}{case_id}-{slug}-controls.json")
    if not click_nav(page, "Backing"):
        _log(notes, f"{case_id} BLOCKER: Backing")
        return
    wait_idle(page, 4500)
    shot_name(page, f"{case_id}-backing.png")
    body = body_name(page, f"{case_id}-backing.txt")
    side = sidebar_excerpt(page)
    assert_labels(notes, f"{case_id}-backing", body + "\n" + side, case)


def charts_missing_in(text: str, case: dict) -> bool:
    return case["expect_charts"] not in text


def leftover_am_case(page: Page, notes: list[str]) -> None:
    """Am song + capo stores shape tonic A; C major must chart A major, not A minor."""
    case = {
        "id": "leftover-am",
        "expect_charts": "Charts in A major",
        "forbid": ["Charts in A minor"],
        "practice_keep": "C",
    }
    pick_song(page, notes, "While My Guitar Gently Weeps", "Rock")
    set_baseweb_select(page, "Practice / Concert Key", "A minor")
    enable_guitar_capo(page, notes, "A")
    shot_name(page, "leftover-am-source.png")
    body_name(page, "leftover-am-source.txt")
    pick_song(page, notes, "Let It Be", "Rock")
    wait_idle(page, 4000)
    set_baseweb_select(page, "Practice / Concert Key", "C")
    wait_idle(page, 2500)
    expand_sidebar(page)
    shot_name(page, "leftover-am-sidebar.png")
    side = sidebar_excerpt(page)
    (OUT / f"{PREFIX}leftover-am-sidebar.txt").write_text(side, encoding="utf-8")
    body = page.inner_text("body")
    combined = body + "\n" + side
    assert_labels(notes, "leftover-am-sidebar", combined, case)
    has_shape_a = bool(re.search(r"Shape Key[\s\S]{0,80}\bA\b", combined)) and "Am" not in combined.split("Shape Key")[-1][:80]
    _log(notes, f"leftover-am shape-tonic-A={has_shape_a}")
    capture_surfaces(page, notes, "leftover-am", case)


def walk(page: Page, notes: list[str]) -> None:
    sha = git_sha()
    _log(notes, f"SHAPE SHA={sha}")
    page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    wait_idle(page, 8000)
    shot_name(page, "00-landing.png")
    expand_sidebar(page)

    for case in CASES:
        _log(notes, f"CASE {case['id']} {case['song']} + Shape {case['shape']}")
        if not pick_song(page, notes, case["song"], case["genre_hint"]):
            _log(notes, f"{case['id']} SKIP — song not landed")
            continue
        opt = str(case.get("practice_option") or "")
        if opt:
            pk_ok = set_baseweb_select(page, "Practice / Concert Key", opt)
            _log(notes, f"{case['id']} practice-key {opt}={pk_ok}")
            wait_idle(page, 2500)
        enable_guitar_capo(page, notes, case["shape"])
        expand_sidebar(page)
        shot_name(page, f"{case['id']}-sidebar.png")
        side = sidebar_excerpt(page)
        (OUT / f"{PREFIX}{case['id']}-sidebar.txt").write_text(side, encoding="utf-8")
        assert_labels(notes, f"{case['id']}-sidebar", side, case)
        capture_surfaces(page, notes, case["id"], case)

    leftover_am_case(page, notes)


def main() -> None:
    notes: list[str] = []
    OUT.mkdir(exist_ok=True)
    sha = git_sha()
    (OUT / "shape-sha.txt").write_text(sha + "\n", encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        try:
            import sys

            if "--leftover" in sys.argv:
                page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
                wait_idle(page, 8000)
                leftover_am_case(page, notes)
            else:
                walk(page, notes)
        except Exception as exc:
            _log(notes, f"EXCEPTION {type(exc).__name__}: {exc}")
            try:
                shot_name(page, "zz-exception.png")
                body_name(page, "zz-exception.txt")
            except Exception:
                pass
        finally:
            browser.close()
    if "--leftover" in __import__("sys").argv:
        prev = NOTES.read_text(encoding="utf-8") if NOTES.exists() else ""
        NOTES.write_text(prev.rstrip() + "\n" + "\n".join(notes) + "\n", encoding="utf-8")
    else:
        NOTES.write_text("\n".join(notes) + "\n", encoding="utf-8")
    print("wrote", NOTES)


if __name__ == "__main__":
    main()

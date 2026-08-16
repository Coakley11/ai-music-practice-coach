"""Live Practice page walk for Phase 2A (Guitar Strumming/Timing/Harmony, Sax Tone)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_pages_nav,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
    visible_open_indexes,
    wait_idle,
)

URL = "http://127.0.0.1:8511"
OUT = Path(__file__).resolve().parent / "evidence-practice-focus"
NOTES = OUT / "live-walk-notes.txt"


def _log(notes: list[str], msg: str) -> None:
    notes.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / name), full_page=True)


def _body(page: Page, name: str) -> str:
    text = page.inner_text("body")
    (OUT / name).write_text(text[:40000], encoding="utf-8")
    return text


def open_expander(page: Page, title: str) -> bool:
    loc = page.locator('[data-testid="stExpander"]').filter(has_text=re.compile(title, re.I))
    if loc.count() == 0:
        loc = page.get_by_text(title, exact=False)
    try:
        target = loc.first
        target.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        header = target.locator("summary, [data-testid='stExpanderToggleIcon'], details > summary, button").first
        if header.count():
            header.click(timeout=4000)
        else:
            target.click(timeout=4000)
        wait_idle(page, 2500)
        return True
    except Exception:
        try:
            page.get_by_text(title, exact=False).first.click(timeout=4000)
            wait_idle(page, 2500)
            return True
        except Exception:
            return False


def click_studio_page(page: Page, name: str) -> bool:
    """Click an exact sidebar page button (avoid 'Practice' matching Practice Log)."""
    expand_pages_nav(page)
    side = page.locator('section[data-testid="stSidebar"]')
    buttons = side.locator("button")
    needle = name.strip().lower()
    for i in range(buttons.count()):
        el = buttons.nth(i)
        try:
            text = " ".join((el.inner_text() or "").split()).strip().lower()
            if needle == "practice" and "log" in text:
                continue
            if text == needle or text.endswith(" " + needle):
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click(timeout=4000)
                    wait_idle(page, 4000)
                    return True
        except Exception:
            continue
    if name == "Practice":
        opens, vis = visible_open_indexes(page)
        if vis:
            try:
                opens.nth(vis[0]).click()
                wait_idle(page, 4000)
                return True
            except Exception:
                pass
    return False


def reveal_practice_coach(page: Page) -> bool:
    nav_ok = click_studio_page(page, "Practice")
    wait_idle(page, 3000)
    clicked_tool = False
    loc = page.locator("button").filter(has_text=re.compile(r"Chord & song coach", re.I))
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if el.is_visible():
                el.scroll_into_view_if_needed()
                el.click(timeout=4000)
                wait_idle(page, 4000)
                clicked_tool = True
                break
        except Exception:
            continue
    ok = open_expander(page, "Practice coach")
    open_expander(page, "Daily time breakdown")
    return bool(nav_ok or clicked_tool or ok)


def set_focus(page: Page, name: str) -> bool:
    expand_sidebar(page)
    side = page.locator('section[data-testid="stSidebar"]')
    box = side.locator('[data-testid="stSelectbox"]').filter(has_text=re.compile(r"Practice focus", re.I))
    try:
        target = box.first
        target.scroll_into_view_if_needed()
        clickable = target.locator("input, [role='combobox']").first
        clickable.click(timeout=4000)
        page.wait_for_timeout(400)
        if clickable.evaluate("el => el.tagName === 'INPUT'"):
            clickable.fill("")
            clickable.type(name, delay=40)
        opt = page.locator('[role="option"]').filter(has_text=re.compile(rf"^{re.escape(name)}$", re.I))
        if opt.count() == 0:
            opt = page.get_by_role("option", name=re.compile(name, re.I))
        opt.first.click(timeout=4000)
        wait_idle(page, 4000)
        return True
    except Exception:
        ok = set_baseweb_select(page, "Practice focus", name)
        if ok:
            wait_idle(page, 4000)
            return True
        return set_baseweb_select(page, "Focus", name)


def ask_ami(page: Page, question: str) -> bool:
    expand_sidebar(page)
    side = page.locator('section[data-testid="stSidebar"]')
    try:
        box = side.locator("textarea").first
        box.click(timeout=4000)
        box.fill(question)
        btn = side.get_by_role("button", name=re.compile(r"Ask the Music Coach", re.I))
        if btn.count():
            btn.first.click(timeout=4000)
        else:
            box.press("Control+Enter")
        wait_idle(page, 10000)
        return True
    except Exception:
        return False


def main() -> int:
    notes: list[str] = []
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        wait_idle(page, 8000)
        _log(notes, f"title={page.title()}")
        nav_ok = click_studio_page(page, "Practice")
        _log(notes, f"nav Practice={nav_ok}")
        wait_idle(page, 4000)

        inst_ok = set_instrument(page, "Guitar")
        _log(notes, f"instrument Guitar={inst_ok}")
        wait_idle(page, 3500)
        focus_ok = set_focus(page, "Strumming")
        _log(notes, f"focus Strumming={focus_ok}")
        coach_ok = reveal_practice_coach(page)
        _log(notes, f"open Practice coach expander={coach_ok}")
        wait_idle(page, 2500)
        _shot(page, "A-guitar-strumming-practice.png")
        body = _body(page, "A-guitar-strumming-practice-live.txt")
        _log(notes, f"A isolate/strum={'isolate' in body.lower() or 'downstroke' in body.lower() or 'strumming hand' in body.lower()}")

        focus_ok = set_focus(page, "Timing")
        _log(notes, f"focus Timing={focus_ok}")
        reveal_practice_coach(page)
        wait_idle(page, 2500)
        _shot(page, "B-guitar-timing-practice.png")
        body = _body(page, "B-guitar-timing-practice-live.txt")
        _log(notes, f"B metronome/subdivision={'metronome' in body.lower() or 'subdivision' in body.lower() or 'rush' in body.lower()}")

        focus_ok = set_focus(page, "Harmony")
        _log(notes, f"focus Harmony={focus_ok}")
        reveal_practice_coach(page)
        wait_idle(page, 2500)
        _shot(page, "C-guitar-harmony-practice.png")
        body = _body(page, "C-guitar-harmony-practice-live.txt")
        _log(notes, f"C chord/guide={'chord tone' in body.lower() or 'guide' in body.lower() or 'voice-lead' in body.lower() or 'voice leading' in body.lower()}")

        inst_ok = set_instrument(page, "Saxophone")
        _log(notes, f"instrument Saxophone={inst_ok}")
        wait_idle(page, 4000)
        focus_ok = set_focus(page, "Tone")
        _log(notes, f"focus Tone={focus_ok}")
        reveal_practice_coach(page)
        wait_idle(page, 2500)
        _shot(page, "D-sax-tone-practice.png")
        body = _body(page, "D-sax-tone-practice-live.txt")
        _log(notes, f"D long tone={'long tone' in body.lower() or 'embouchure' in body.lower() or 'air support' in body.lower()}")

        ami_ok = ask_ami(page, "What should I practice today?")
        _log(notes, f"AMI sax tone ask={ami_ok}")
        wait_idle(page, 6000)
        _shot(page, "H-ami-sax-tone-live.png")
        _body(page, "H-ami-sax-tone-live.txt")

        focus_ok = set_focus(page, "Articulation")
        _log(notes, f"focus Articulation={focus_ok}")
        ami_ok = ask_ami(page, "What should I practice today?")
        _log(notes, f"AMI sax articulation ask={ami_ok}")
        wait_idle(page, 6000)
        _shot(page, "H-ami-sax-articulation-live.png")
        _body(page, "H-ami-sax-articulation-live.txt")

        inst_ok = set_instrument(page, "Guitar")
        _log(notes, f"instrument Guitar again={inst_ok}")
        wait_idle(page, 3500)
        set_focus(page, "Strumming")
        ami_ok = ask_ami(page, "What should I practice today?")
        _log(notes, f"AMI guitar strumming ask={ami_ok}")
        wait_idle(page, 6000)
        _shot(page, "E-ami-guitar-strumming-live.png")
        _body(page, "E-ami-guitar-strumming-live.txt")

        set_focus(page, "Timing")
        ami_ok = ask_ami(page, "What should I practice today?")
        _log(notes, f"AMI guitar timing ask={ami_ok}")
        wait_idle(page, 6000)
        _shot(page, "F-ami-guitar-timing-live.png")
        _body(page, "F-ami-guitar-timing-live.txt")

        ami_ok = ask_ami(page, "What notes are in C major?")
        _log(notes, f"AMI C major ask={ami_ok}")
        wait_idle(page, 6000)
        _shot(page, "G-ami-c-major-live.png")
        body = _body(page, "G-ami-c-major-live.txt")
        _log(notes, f"G no strumming hijack={'strumming' not in body.lower()}")

        browser.close()
    NOTES.write_text("\n".join(notes) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

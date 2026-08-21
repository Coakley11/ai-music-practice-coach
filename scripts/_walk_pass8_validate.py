"""Pass 8 live validation against a freshly restarted local Streamlit.

Usage: python scripts/_walk_pass8_validate.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_creative_backing_matrix as matrix  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_label,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
)
import walk_guitar_shape_key as shape_walk  # noqa: E402
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 and not str(sys.argv[1]).startswith("--") else "http://127.0.0.1:8512"
A_ONLY = "--a-only" in sys.argv
B_ONLY = "--b-only" in sys.argv
C_ONLY = "--c-only" in sys.argv
E_ONLY = "--e-only" in sys.argv
E1_ONLY = "--e1-only" in sys.argv
E4_ONLY = "--e4-only" in sys.argv
E5_ONLY = "--e5-only" in sys.argv
E_MATRIX = E_ONLY or E1_ONLY or E4_ONLY or E5_ONLY


def _result_flags(row: str) -> dict[str, str]:
    """Parse `key=True` tokens from a walk result line."""
    return dict(re.findall(r"(\w+)=(True|False)", row))


def _backing_source_line(body: str) -> str:
    """First 'Backing source:' line — ignores sidebar ACTIVE SONG text."""
    for line in (body or "").splitlines():
        if "Backing source:" in line:
            return line.strip()
    return ""


def _practice_concert_key_from_body(body: str) -> str:
    """Parse PRACTICE / CONCERT KEY block value from regular catalog Backing card."""
    text = body or ""
    m = re.search(
        r"PRACTICE\s*/\s*CONCERT\s*KEY\s*\n\s*([A-G](?:#|b)?m?)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    # Sidebar Practice / Concert Key input is often not scraped; try Sounding Key / Original.
    m = re.search(r"Sounding Key:\s*([A-G](?:#|b)?m?)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"Song Original Key:\s*([A-G](?:#|b)?m?)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Banner form: Backing source: Catalog song · Title · D · 100 BPM
    line = _backing_source_line(text)
    parts = [p.strip() for p in re.split(r"[·•|]", line)]
    if len(parts) >= 3:
        cand = parts[2].split()[0] if parts[2] else ""
        if re.fullmatch(r"[A-G](?:#|b)?m?", cand):
            return cand
    return ""


def _e_matrix_failed(results: dict[str, str]) -> bool:
    e1 = _result_flags(results.get("E1", ""))
    if e1:
        if e1.get("opened") == "False":
            return True
        if e1.get("mission") == "False":
            return True
        if e1.get("catalog_bleed") == "True":
            return True
        if e1.get("sbi_not_mission") == "True":
            return True
        if e1.get("syncing") == "True":
            return True
        if e1.get("e1a_mission") == "False":
            return True
    e2 = _result_flags(results.get("E2", ""))
    if e2.get("mission_stuck") == "True" or e2.get("clocks_stuck") == "True":
        return True
    if e2.get("love_banner") == "False" or e2.get("pkC") == "False":
        return True
    e3 = _result_flags(results.get("E3", ""))
    if e3.get("jam_restored") == "False" or e3.get("love_regular") == "False" or e3.get("jam_stuck") == "True":
        return True
    e4 = _result_flags(results.get("E4", ""))
    if e4.get("mission_stuck") == "True" or e4.get("roads") == "False":
        return True
    if e4.get("roads_banner") == "False" or e4.get("pk_expected") == "False" or e4.get("love_stuck") == "True":
        return True
    e5 = _result_flags(results.get("E5", ""))
    if e5.get("custom_ok") == "False" or e5.get("trial") == "False":
        return True
    if e5.get("trial_banner") == "False" or e5.get("roads_stuck") == "True":
        return True
    if e5.get("catalog_stuck") == "True" or e5.get("refresh_ok") == "False":
        return True
    if e5.get("reverse_clocks") == "False" or e5.get("trial_leak") == "True":
        return True
    return False
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "pass8v-"
matrix.PREFIX = PREFIX
matrix.OUT = OUT


def wait(page: Page, ms: int = 900) -> None:
    page.wait_for_timeout(ms)
    try:
        page.locator('[data-testid="stSpinner"]').first.wait_for(state="hidden", timeout=6000)
    except Exception:
        pass


matrix.wait_idle = wait
shape_walk.wait_idle = wait


def wait_for(page: Page, needle: str, *, timeout_ms: int = 12000) -> bool:
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            body = page.inner_text("body") or ""
            if needle in body:
                return True
        except Exception:
            pass
        wait(page, 700)
        elapsed += 700
    return False


def _body_has_tempo_controls(body: str) -> bool:
    """Visible Tempo label may be CSS-upcased to TEMPO (BPM); widget aria is Quick BPM."""
    low = (body or "").lower()
    return "quick bpm" in low or "tempo (bpm)" in low or "tempo & playback" in low


def page_route_probe(page: Page) -> dict[str, object]:
    """Lightweight UI probe — route/source/BPM card (no server session access)."""
    body = page.inner_text("body") or ""
    on_backing = "Backing Track Studio" in body and (
        _body_has_tempo_controls(body) or ("Current" in body and "BPM" in body)
    )
    return {
        "on_backing": on_backing,
        "on_practice": (not on_backing)
        and (
            "Practice Page" in body
            or "Open Practice" in body
            or ("🎯" in body and "Practice length" in body and "Tempo & playback" not in body)
        ),
        "catalog": "Backing source: Catalog song" in body,
        "default_bpm": card_default(body),
        "current_bpm": card_current(body),
        "slider": slider_now(page),
        "blues": "Blues" in body,
        "meter_34": "3/4" in body,
        "chorus": "Chorus" in body,
    }


def wait_backing_ready(page: Page, *, timeout_ms: int = 20000) -> bool:
    """After reload/nav, wait until Backing is actually interactive (not welcome splash)."""
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            body = page.inner_text("body") or ""
            if (
                "Backing Track Studio" in body
                and _body_has_tempo_controls(body)
                and ("Current" in body and "BPM" in body)
            ):
                if slider(page) is not None:
                    return True
                # Number/slider may lag one tick; catalog banner + Current is enough.
                if "Backing source:" in body or "ACTIVE SONG · BACKING TRACK" in body:
                    return True
        except Exception:
            pass
        wait(page, 700)
        elapsed += 700
    return False


def leave_backing_to_practice(page: Page, notes: list[str]) -> bool:
    """TRUE leave: Backing → Practice. Refresh is not a leave."""
    before = page_route_probe(page)
    notes.append(f"leave_before={before}")
    for attempt in range(4):
        click_nav(page, "Practice")
        wait(page, 1800)
        body = page.inner_text("body") or ""
        left = "Backing Track Studio" not in body and not _body_has_tempo_controls(body)
        on_practice = left and (
            "Practice Page" in body
            or "Open Practice" in body
            or "Practice length" in body
        )
        notes.append(f"leave_attempt={attempt} left={left} on_practice={on_practice}")
        if left:
            after = page_route_probe(page)
            notes.append(f"leave_after={after}")
            return True
    notes.append("leave_FAILED_still_on_backing")
    return False


def goto_backing(page: Page) -> bool:
    """Open Catalog Backing the same way as dedicated pass8c (retry until ready)."""
    expand_sidebar(page)
    for attempt in range(8):
        click_button_has(page, r"Return to Catalog Song Backing") or click_nav(page, "Backing")
        wait(page, 2000)
        body = page.inner_text("body") or ""
        catalogish = "Backing source: Catalog song" in body or "ACTIVE SONG · BACKING TRACK" in body
        studio = "Backing Track Studio" in body
        if studio and catalogish and (
            _body_has_tempo_controls(body) or ("Current" in body and "BPM" in body)
        ):
            if wait_backing_ready(page, timeout_ms=8000):
                return True
            # Already on Catalog Backing — do not click Open cards (that leaves).
            return True
        # Only use Open-card fallback when not already on Backing Studio content.
        if not studio:
            try:
                opens = page.locator("button").filter(has_text=re.compile(r"^Open$"))
                if opens.count() >= 3:
                    opens.nth(2).click(timeout=4000)
                    wait(page, 2000)
            except Exception:
                pass
            if wait_backing_ready(page, timeout_ms=4000):
                return True
        # Last attempts: force sidebar Backing again.
        if attempt >= 4:
            click_nav(page, "Backing")
            wait(page, 2500)
    return wait_backing_ready(page, timeout_ms=6000)


def open_advanced_playback(page: Page) -> bool:
    """Open the Backing 'Advanced playback settings' expander (not a plain button)."""
    # Fast path: meter radios already visible.
    try:
        if page.locator('[role="radio"]').filter(has_text=re.compile(r"^(4/4|3/4)$")).count() > 0:
            return True
    except Exception:
        pass
    # Streamlit expander: click the details/summary header.
    opened = page.evaluate(
        """() => {
          const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
          const expanders = [...document.querySelectorAll('[data-testid="stExpander"]')];
          const target = expanders.find((el) => /advanced playback/i.test(el.innerText || ''));
          if (!target || !vis(target)) return false;
          const details = target.querySelector('details');
          if (details && !details.open) {
            const summary = details.querySelector('summary') || target;
            summary.scrollIntoView({block: 'center'});
            summary.click();
            return true;
          }
          // Fallback: click header text node / first clickable.
          const clickable = target.querySelector('summary, [data-testid="stExpanderToggleIcon"], button') || target;
          clickable.scrollIntoView({block: 'center'});
          clickable.click();
          return true;
        }"""
    )
    wait(page, 1200)
    try:
        if page.locator('[role="radio"]').filter(has_text=re.compile(r"^(4/4|3/4)$")).count() > 0:
            return True
    except Exception:
        pass
    # Text fallbacks.
    try:
        exp = page.locator('[data-testid="stExpander"]').filter(
            has_text=re.compile(r"Advanced playback", re.I)
        )
        if exp.count():
            exp.first.scroll_into_view_if_needed(timeout=4000)
            exp.first.click(timeout=4000)
            wait(page, 1000)
    except Exception:
        pass
    if not opened:
        click_button_has(page, r"Advanced playback")
        wait(page, 1000)
    try:
        return page.locator('[role="radio"]').filter(has_text=re.compile(r"^(4/4|3/4)$")).count() > 0
    except Exception:
        return bool(opened)


def set_groove_style(page: Page, option: str) -> bool:
    """Advanced 'Groove style' selectbox (label often collapsed). Prefer full GROOVE labels."""
    # Product choices are e.g. "Blues groove", not bare "Blues".
    aliases = {
        "Blues": "Blues groove",
        "Pop": "Pop groove",
        "Rock": "Rock groove",
        "Funk": "Funk groove",
        "Jazz": "Jazz swing",
    }
    target = aliases.get(option, option)
    candidates = [target]
    if option not in candidates:
        candidates.append(option)
    if not open_advanced_playback(page):
        open_advanced_playback(page)
    wait(page, 900)
    for want in candidates:
        for label in ("Groove style", "Pop groove", "Feel", "Groove", want, "Auto"):
            if set_baseweb_select(page, label, want):
                wait(page, 1400)
                return True
    try:
        boxes = page.locator('[data-testid="stSelectbox"]')
        for i in range(min(boxes.count(), 16)):
            el = boxes.nth(i)
            if not el.is_visible():
                continue
            txt = (el.inner_text() or "").lower()
            if not any(k in txt for k in ("groove", "pop", "blues", "auto", "feel", "jazz", "rock", "ballad")):
                continue
            el.click(timeout=3000)
            wait(page, 500)
            for want in candidates:
                opt = page.locator('[role="option"]').filter(
                    has_text=re.compile(rf"^{re.escape(want)}$", re.I)
                )
                if opt.count() == 0:
                    opt = page.locator('[role="option"]').filter(
                        has_text=re.compile(re.escape(want), re.I)
                    )
                if opt.count():
                    opt.first.click()
                    wait(page, 1400)
                    return True
            page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def set_meter(page: Page, meter: str) -> bool:
    """Advanced Meter radio (aria often 'Time signature' / bare '3/4')."""
    open_advanced_playback(page)
    wait(page, 800)
    try:
        page.get_by_text("Meter", exact=False).first.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    if click_radio(page, meter):
        wait(page, 1200)
        return True
    # Fallback: click any radio whose text equals meter.
    try:
        loc = page.locator('[role="radio"]').filter(has_text=re.compile(rf"^{re.escape(meter)}$"))
        for i in range(loc.count()):
            el = loc.nth(i)
            if el.is_visible():
                el.click(timeout=3000)
                wait(page, 1200)
                return True
    except Exception:
        pass
    return False


def _fast_idle(page: Page, ms: int = 800) -> None:
    wait(page, min(int(ms or 800), 1600))


matrix.wait_idle = _fast_idle
shape_walk.wait_idle = _fast_idle

ROOT = Path(__file__).resolve().parents[1]


def git_info() -> dict[str, str]:
    def run(cmd: list[str]) -> str:
        return subprocess.check_output(cmd, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:18000], encoding="utf-8")
    return body


def slider(page: Page):
    for aria in ("Quick BPM", "Tempo (BPM)", "Tempo"):
        loc = page.locator(f'input[type="range"][aria-label="{aria}"]')
        if loc.count():
            return loc.first
    loc = page.locator('input[type="range"]')
    # Prefer a BPM-looking range (20-180) over other page sliders.
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            mn = float(el.get_attribute("min") or 0)
            mx = float(el.get_attribute("max") or 0)
            if mn <= 20 and mx >= 160:
                return el
        except Exception:
            continue
    if loc.count():
        return loc.first
    for el in page.locator('[role="slider"]').all():
        try:
            if not el.is_visible():
                continue
            mn = float(el.get_attribute("aria-valuemin") or 0)
            mx = float(el.get_attribute("aria-valuemax") or 0)
            if mn <= 20 and mx >= 160:
                return el
        except Exception:
            continue
    return None


def slider_now(page: Page) -> int | None:
    el = slider(page)
    if el is None:
        return None
    try:
        raw = el.get_attribute("value") or el.get_attribute("aria-valuenow") or el.input_value()
        return int(float(raw or 0)) or None
    except Exception:
        return None


def set_bpm(page: Page, value: int) -> int | None:
    try:
        page.get_by_text("Tempo (BPM)", exact=False).first.scroll_into_view_if_needed(timeout=3000)
        wait(page, 300)
    except Exception:
        pass
    el = slider(page)
    if el is None:
        return None
    el.scroll_into_view_if_needed()
    wait(page, 200)
    box = el.bounding_box()
    if box:
        mn, mx = 20.0, 180.0
        try:
            mn = float(el.get_attribute("min") or el.get_attribute("aria-valuemin") or mn)
            mx = float(el.get_attribute("max") or el.get_attribute("aria-valuemax") or mx)
        except Exception:
            pass
        ratio = (value - mn) / max(1.0, (mx - mn))
        x = box["x"] + max(2, min(box["width"] - 2, box["width"] * ratio))
        y = box["y"] + box["height"] / 2
        page.mouse.click(x, y)
        wait(page, 1200)
    el.focus()
    now = slider_now(page)
    if now is None:
        return None
    if now < value:
        for _ in range(min(50, value - now)):
            page.keyboard.press("ArrowRight")
        wait(page, 1000)
    elif now > value:
        for _ in range(min(50, now - value)):
            page.keyboard.press("ArrowLeft")
        wait(page, 1000)
    return slider_now(page) or now


def card_current(text: str) -> str:
    m = re.search(r"Current\s+(\d{2,3})\s+BPM", text)
    if m:
        return m.group(1)
    m = re.search(r"BPM:\s*(\d{2,3})", text)
    if m:
        return m.group(1)
    m = re.search(r"⏱\s*BPM\s+(\d{2,3})", text)
    return m.group(1) if m else ""


def card_default(text: str) -> str:
    m = re.search(r"Default\s+(\d{2,3})\s+BPM", text)
    return m.group(1) if m else ""


def mission_bpm(text: str) -> str:
    m = re.search(r"⏱\s*BPM\s*·\s*(\d{2,3})", text)
    return m.group(1) if m else card_current(text)


def set_practice_key(page: Page, option: str) -> bool:
    expand_sidebar(page)
    return bool(set_baseweb_select(page, "Practice / Concert Key", option))


def click_chord(page: Page, label: str) -> bool:
    """Click a Missions chord tile so Streamlit ``on_click`` fires.

    Prefer unselected tiles in the main Missions panel. Avoid force clicks —
    they often skip Streamlit button callbacks (Return→first-click failure).
    """
    def _try_click(el) -> bool:
        try:
            if not el.is_visible():
                return False
            el.scroll_into_view_if_needed(timeout=3000)
            # Real pointer interaction — Streamlit on_click needs this.
            el.hover(timeout=2000)
            el.click(timeout=4000, force=False, no_wait_after=False)
            wait(page, 2500)
            return True
        except Exception:
            try:
                el.focus()
                page.keyboard.press("Enter")
                wait(page, 2500)
                return True
            except Exception:
                return False

    # Prefer tiles near the Missions chord picker (not sidebar / unrelated C#m).
    scopes = [
        page.locator('[data-testid="stMain"]'),
        page.locator("section.main"),
        page,
    ]
    for scope in scopes:
        try:
            role_btns = scope.get_by_role("button", name=label, exact=True)
            # Prefer secondary (unselected) first.
            for prefer_primary in (False, True):
                for i in range(min(role_btns.count(), 24)):
                    el = role_btns.nth(i)
                    try:
                        cls = (el.get_attribute("class") or "").lower()
                        is_primary = "primary" in cls
                        if prefer_primary != is_primary and role_btns.count() > 1:
                            continue
                        if _try_click(el):
                            return True
                    except Exception:
                        continue
        except Exception:
            continue
    try:
        btn = page.locator("button").filter(has_text=re.compile(rf"^{re.escape(label)}$"))
        for i in range(min(btn.count(), 24)):
            if _try_click(btn.nth(i)):
                return True
        return click_button_has(page, rf"^{re.escape(label)}$")
    except Exception:
        return False


def select_chorus_sections(page: Page) -> bool:
    clicked = click_radio(page, "Selected sections") or click_button_has(page, "Selected sections")
    wait(page, 800)
    try:
        box = page.locator('[data-testid="stMultiSelect"]').first
        if box.count() and box.is_visible():
            box.click()
            wait(page, 400)
            opt = page.locator('[role="option"]').filter(has_text=re.compile("Chorus", re.I))
            if opt.count():
                opt.first.click()
                wait(page, 1200)
                return True
    except Exception:
        pass
    return bool(clicked)


def ensure_missions_workspace(page: Page, notes: list[str]) -> bool:
    """Force Analysis mode → Missions until Generate example is visible."""
    for attempt in range(6):
        body = page.inner_text("body") or ""
        if "Generate example" in body or "Generate Example" in body:
            notes.append(f"missions_ready attempt={attempt}")
            return True
        # Prefer exact analysis-mode radio (emoji label).
        clicked = (
            click_radio(page, "🚩 Missions")
            or click_radio(page, "Missions")
            or click_button_has(page, r"🚩 Missions")
            or click_button_has(page, r"^Missions$")
            or click_label(page, "Missions")
        )
        notes.append(f"missions_click attempt={attempt} clicked={clicked}")
        wait(page, 2000)
        # Sometimes Entry & Jam stays; scroll to analysis radios and click via JS.
        page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
              const radios = [...document.querySelectorAll('[role="radio"]')].filter(vis);
              const m = radios.find((el) => /missions/i.test((el.getAttribute('aria-label')||'') + ' ' + (el.innerText||'')));
              if (m) { m.scrollIntoView({block:'center'}); m.click(); return true; }
              return false;
            }"""
        )
        wait(page, 2200)
    notes.append("missions_FAILED_no_generate_example")
    shot(page, "zz-missions-fail")
    return False


def open_mission_backing(page: Page, notes: list[str]) -> bool:
    """Open Mission Backing only (not Song-Based Improvisation Backing)."""
    # Mission-specific buttons only — never "Open in Backing Studio" (SBI/Jam entry).
    clicked = (
        click_button_has(page, r"Practice in Backing Jam")
        or click_button_has(page, r"Open Mission Backing")
        or click_button_has(page, r"▶ Practice in Backing")
        or click_button_has(page, r"Backing Jam")
    )
    notes.append(f"mission_backing_click={clicked}")
    if not clicked:
        # Dump visible button labels for diagnosis.
        try:
            labels = page.evaluate(
                """() => [...document.querySelectorAll('button')]
                  .filter(b => b.offsetParent)
                  .map(b => (b.innerText||'').trim().replace(/\\s+/g,' '))
                  .filter(t => /jam|backing|mission|generate/i.test(t))
                  .slice(0, 20)"""
            )
            notes.append(f"mission_backing_visible_btns={labels}")
        except Exception as exc:
            notes.append(f"mission_backing_btn_dump_err={exc}")
        notes.append("mission_backing_no_mission_button")
        shot(page, "zz-mission-open-fail")
        return False
    wait(page, 3500)

    def _is_mission_backing(body: str) -> bool:
        if "Backing Track Studio" not in body:
            return False
        if "Song-Based Improvisation" in body and "Creative Backing Jam · Mission" not in body:
            if "MISSION BACKING" not in body and "Return to Mission" not in body:
                return False
        return (
            "MISSION BACKING" in body
            or "Return to Mission" in body
            or "Creative Backing Jam · Mission" in body
        )

    for attempt in range(16):
        body = page.inner_text("body") or ""
        if _is_mission_backing(body) and (
            "Backing Track Studio" in body or _body_has_tempo_controls(body)
        ):
            notes.append(f"mission_backing_landed=True attempt={attempt}")
            return True
        # Still on Creative with sync caption — wait for deferred handoff consume.
        if "Mission context is still syncing" in body:
            notes.append(f"mission_backing_waiting_sync attempt={attempt}")
        wait(page, 1200)
    body = page.inner_text("body") or ""
    notes.append(
        f"mission_backing_FAILED syncing={'Mission context is still syncing' in body} "
        f"sbi={'Song-Based Improvisation' in body} "
        f"studio={'Backing Track Studio' in body}"
    )
    shot(page, "zz-mission-open-fail-final")
    return False


def return_to_mission(page: Page, notes: list[str]) -> bool:
    clicked = (
        click_button_has(page, r"Return to Mission")
        or click_button_has(page, r"← Return to Mission")
        or click_button_has(page, r"Open Creative Lab")
    )
    notes.append(f"return_to_mission_click={clicked}")
    wait(page, 2500)
    if not ensure_missions_workspace(page, notes):
        if goto_improv(page, notes):
            ensure_missions_workspace(page, notes)
    body = page.inner_text("body") or ""
    ok = "Generate example" in body or "Selected Mission Chord" in body
    notes.append(f"return_to_mission_ok={ok}")
    return ok


def open_jam_generator(page: Page, notes: list[str]) -> bool:
    if not goto_improv(page, notes):
        return False
    wait(page, 1200)
    # Creative Improvisation Intelligence: Entry / Analysis radios, then jam mode.
    for attempt in range(5):
        click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
            page, "Entry"
        )
        wait(page, 1200)
        page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
              const radios = [...document.querySelectorAll('[role="radio"]')].filter(vis);
              const entry = radios.find((el) => /entry/i.test((el.getAttribute('aria-label')||'') + ' ' + (el.innerText||'')));
              if (entry) { entry.scrollIntoView({block:'center'}); entry.click(); }
              return true;
            }"""
        )
        wait(page, 1500)
        ok = (
            click_radio(page, "Jam Session Generator")
            or click_radio(page, "Jam Session")
            or click_button_has(page, "Jam Session Generator")
            or click_button_has(page, "Jam Session")
            or click_button_has(page, "Generator")
        )
        if not ok:
            page.evaluate(
                """() => {
                  const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
                  const radios = [...document.querySelectorAll('[role="radio"]')].filter(vis);
                  const jam = radios.find((el) => /jam session/i.test((el.getAttribute('aria-label')||'') + ' ' + (el.innerText||'')));
                  if (jam) { jam.scrollIntoView({block:'center'}); jam.click(); return true; }
                  return false;
                }"""
            )
            wait(page, 1500)
        body = page.inner_text("body") or ""
        has_generate = (
            "Generate jam" in body
            or "Generate Jam" in body
            or "Generate jam session" in body
            or ("Generate" in body and "Jam Session" in body)
        )
        landed = "Jam Session" in body or "jam session" in body.lower()
        notes.append(
            f"jam_generator_attempt={attempt} ok={ok} has_generate={has_generate} landed={landed}"
        )
        if landed and has_generate:
            notes.append(f"jam_generator_open=True has_generate=True landed=True")
            return True
        wait(page, 1000)
    shot(page, "zz-jam-generator-fail")
    body = page.inner_text("body") or ""
    notes.append(f"jam_generator_FAILED body_snip={body[:400]!r}")
    return False


def main() -> int:
    info = git_info()
    notes: list[str] = []
    results: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 3500)
        try:
            reset = page.locator("button").filter(has_text="Reset to default")
            if reset.count() and reset.first.is_visible():
                reset.first.click(timeout=4000)
                wait(page, 4000)
                notes.append("reset=True")
        except Exception as exc:
            notes.append(f"reset_err={exc}")
        shot(page, "00-landing")

        landed_song = False
        if E_ONLY or E1_ONLY or E4_ONLY or E5_ONLY:
            notes.append(
                "e_only=True skip_shape_setup"
                if E_ONLY
                else (
                    "e5_only=True skip_shape_setup"
                    if E5_ONLY
                    else ("e4_only=True skip_shape_setup" if E4_ONLY else "e1_only=True skip_shape_setup")
                )
            )
            landed_song = True
        else:
            for attempt in range(3):
                landed_song = bool(pick_song(page, notes, "Shape of You", "Pop"))
                if landed_song:
                    break
                wait(page, 3000)
                click_nav(page, "Songs")
                wait(page, 2500)
            notes.append(f"shape_of_you_landed={landed_song}")
            if not landed_song:
                body = page.inner_text("body") or ""
                (OUT / f"{PREFIX}summary.txt").write_text(
                    "\n".join(notes) + "\nFAIL pick Shape of You\n" + body[:2500],
                    encoding="utf-8",
                )
                print("FAIL: could not pick Shape of You", flush=True)
                browser.close()
                return 2
            wait(page, 2500)
            wait_for(page, "Shape of You", timeout_ms=8000)
            set_instrument(page, "Guitar")
            wait(page, 1200)
            set_practice_key(page, "Dm") or set_practice_key(page, "D minor")
            wait(page, 1500)
            enable_guitar_capo(page, notes, "E") or set_shape_tonic(page, "E")
            wait(page, 1800)
            shot(page, "01-setup")

        if not B_ONLY and not C_ONLY and not E_ONLY and not E1_ONLY and not E4_ONLY and not E5_ONLY:
            # ---------- TEST A: catalog Backing ----------
            ok_backing = goto_backing(page)
            wait(page, 1500)
            notes.append(f"A0_probe={page_route_probe(page)}")
            a0 = shot(page, "A0")
            results["A0"] = (
                f"landed={ok_backing} slider={slider_now(page)} default={card_default(a0)} "
                f"current={card_current(a0)} catalog={'Catalog song' in a0}"
            )
            s110 = set_bpm(page, 110)
            # Same-run + at least one subsequent rerun (dedicated Case A contract).
            for _ in range(10):
                wait(page, 700)
                body_probe = page.inner_text("body") or ""
                if slider_now(page) == 110 and "Current 110 BPM" in body_probe:
                    break
            wait(page, 1200)
            a1 = shot(page, "A1-bpm110")
            results["A1"] = (
                f"slider={s110 or slider_now(page)} current={card_current(a1)} "
                f"default={card_default(a1)} banner110={'110 BPM' in a1}"
            )
            notes.append(f"A1_probe={page_route_probe(page)}")

            # BPM-only refresh first (must agree with dedicated Case A walk).
            page.reload(wait_until="domcontentloaded")
            wait(page, 2000)
            ready_a1r = wait_backing_ready(page, timeout_ms=22000)
            a1r = shot(page, "A1b-bpm-refresh")
            results["A1b"] = (
                f"ready={ready_a1r} slider={slider_now(page)} current={card_current(a1r)} "
                f"default={card_default(a1r)}"
            )
            notes.append(f"A1b_probe={page_route_probe(page)}")

            style_ok = set_groove_style(page, "Blues")
            wait(page, 1200)
            meter_ok = set_meter(page, "3/4")
            wait(page, 1200)
            sec_ok = select_chorus_sections(page)
            wait(page, 1500)
            a2 = shot(page, "A2-knobs")
            results["A2"] = (
                f"style={style_ok or ('Blues' in a2)} meter={meter_ok or ('3/4' in a2)} "
                f"sections={sec_ok or ('Chorus' in a2)} slider={slider_now(page)} current={card_current(a2)} "
                f"blues_groove={'Blues groove' in a2} meter_override={'3/4' in a2}"
            )
            notes.append(f"A2_probe={page_route_probe(page)}")

            page.reload(wait_until="domcontentloaded")
            wait(page, 2000)
            ready_a3 = wait_backing_ready(page, timeout_ms=22000)
            a3 = shot(page, "A3-refresh")
            results["A3"] = (
                f"ready={ready_a3} slider={slider_now(page)} current={card_current(a3)} "
                f"default={card_default(a3)} blues={'Blues' in a3} blues_groove={'Blues groove' in a3} "
                f"meter={'3/4' in a3} chorus={'Chorus' in a3}"
            )
            notes.append(f"A3_probe={page_route_probe(page)}")

            left = leave_backing_to_practice(page, notes)
            wait(page, 1500)
            a4 = shot(page, "A4-leave")
            results["A4"] = (
                f"left={left} still_backing={'Backing Track Studio' in a4 and _body_has_tempo_controls(a4)} "
                f"probe={page_route_probe(page)}"
            )

            ok_return = goto_backing(page)
            wait(page, 2000)
            wait_backing_ready(page, timeout_ms=12000)
            a5 = shot(page, "A5-return")
            results["A5"] = (
                f"landed={ok_return} left_ok={left} slider={slider_now(page)} "
                f"current={card_current(a5)} default={card_default(a5)} "
                f"(expect Current reset to catalog Default ~96 after TRUE leave)"
            )
            notes.append(f"A5_probe={page_route_probe(page)}")

            if A_ONLY:
                browser.close()
                text = "\n".join(
                    [
                        f"branch={info['branch']}",
                        f"sha={info['sha']}",
                        f"url={info['url']}",
                        f"streamlit=local 8512",
                        f"a_only=True",
                        "",
                        *[f"{k}: {v}" for k, v in results.items()],
                        "",
                        "NOTES",
                        *notes,
                    ]
                )
                (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
                (OUT / f"{PREFIX}summary.json").write_text(
                    json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                    encoding="utf-8",
                )
                print(text.encode("ascii", "replace").decode("ascii"), flush=True)
                return 0

        # ---------- TEST B: Mission Backing ----------
        if not C_ONLY and not E_ONLY and not E1_ONLY and not E4_ONLY and not E5_ONLY and goto_improv(page, notes):
            wait(page, 1200)
            if not ensure_missions_workspace(page, notes):
                results["B0"] = "BLOCKER: Missions workspace not reached"
                notes.append("B_BLOCKER_no_missions")
            else:
                set_practice_key(page, "Dm") or set_practice_key(page, "D minor")
                wait(page, 1200)
                enable_guitar_capo(page, notes, "E") or set_shape_tonic(page, "E")
                wait(page, 1500)
                click_chord(page, "Am")
                wait(page, 1000)
                click_button_has(page, "Generate example") or click_button_has(page, "Generate Example")
                wait(page, 2800)
                b0 = shot(page, "B0-missions")
                results["B0"] = (
                    f"selAm={'Selected Mission Chord: Am' in b0} "
                    f"selGm={'Selected Mission Chord: Gm' in b0} "
                    f"pkDm={'Practice Key: Dm' in b0 or 'Practice concert key: Dm' in b0 or 'Key Dm' in b0} "
                    f"has_generate={'Generate example' in b0}"
                )
                opened = open_mission_backing(page, notes)
                wait(page, 2000)
                wait_for(page, "Return to Mission", timeout_ms=10000) or wait_for(
                    page, "MISSION BACKING", timeout_ms=4000
                )
                wait(page, 1500)
                b1 = shot(page, "B1-mb")
                gm = "Chord Gm" in b1 or "— Gm" in b1 or "Mission Example — Gm" in b1
                results["B1"] = (
                    f"opened={opened} mission={'Return to Mission' in b1 or 'MISSION BACKING' in b1} "
                    f"sbi_leak={'Song-Based Improvisation' in b1 and 'Return to Mission' not in b1} "
                    f"progAm={'Progression: Am' in b1} chordGm={gm} "
                    f"notesAm={'C – E – A' in b1 or 'C - E - A' in b1} "
                    f"guitar={'Guitar' in b1} bpm={mission_bpm(b1)}"
                )
                s103 = set_bpm(page, 103)
                wait(page, 1600)
                b2 = shot(page, "B2-bpm103")
                results["B2"] = (
                    f"slider={s103 or slider_now(page)} card={mission_bpm(b2)} current={card_current(b2)}"
                )
                page.reload(wait_until="domcontentloaded")
                wait(page, 2000)
                wait_backing_ready(page, timeout_ms=22000)
                b3 = shot(page, "B3-refresh")
                results["B3"] = (
                    f"slider={slider_now(page)} card={mission_bpm(b3)} current={card_current(b3)}"
                )
                pk = set_practice_key(page, "Em") or set_practice_key(page, "E minor")
                # Pending Mission practice-key edit consumes on the next pre-widget run.
                for _ in range(8):
                    wait(page, 900)
                    body_pk = page.inner_text("body") or ""
                    if "Sounding Key: Em" in body_pk or "Practice concert key: E minor" in body_pk:
                        break
                    set_practice_key(page, "Em") or set_practice_key(page, "E minor")
                wait(page, 1200)
                b4 = shot(page, "B4-pk-em")
                results["B4"] = (
                    f"clicked={pk} concertEm={'Practice concert key: E minor' in b4 or 'Sounding Key: Em' in b4} "
                    f"soundingEm={'Sounding Key: Em' in b4} "
                    f"dm_stuck={'Practice concert key: D minor' in b4 and 'Sounding Key: Em' not in b4}"
                )
                before_notes = re.search(
                    r"(?:Notes|Motif)[:\s]+([A-G][#b♯♭]?(?:\s*[–-]\s*[A-G][#b♯♭]?){2,})",
                    b4,
                )
                notes.append(f"B4_notes_before_shape={before_notes.group(0) if before_notes else ''}")
                shape_ok = enable_guitar_capo(page, notes, "C#") or set_shape_tonic(page, "C#")
                wait(page, 2200)
                b5 = shot(page, "B5-shape")
                after_notes = re.search(
                    r"(?:Notes|Motif)[:\s]+([A-G][#b♯♭]?(?:\s*[–-]\s*[A-G][#b♯♭]?){2,})",
                    b5,
                )
                notes.append(f"B5_notes_after_shape={after_notes.group(0) if after_notes else ''}")
                results["B5"] = (
                    f"clicked={shape_ok} chartsC#={'Charts in C# minor' in b5 or 'C♯ minor' in b5} "
                    f"gm={'Chord Gm' in b5} fshm={'F#m' in b5 or 'F♯m' in b5} "
                    f"example_reproject={'T:Mission Example' in b5 or 'Mission Example' in b5} "
                    f"notes_changed={(after_notes.group(0) if after_notes else '') != (before_notes.group(0) if before_notes else '')}"
                )
                page.reload(wait_until="domcontentloaded")
                wait(page, 2000)
                wait_backing_ready(page, timeout_ms=22000)
                b6 = shot(page, "B6-shape-refresh")
                results["B6"] = (
                    f"chartsC#={'Charts in C# minor' in b6 or 'C♯ minor' in b6} "
                    f"capo1={'1st fret' in b6 or 'Capo Fret: 1' in b6} "
                    f"shapeC#={'Shape Key' in b6 and ('C#' in b6 or 'C♯' in b6)}"
                )
                returned = return_to_mission(page, notes)
                wait(page, 1800)
                b7 = shot(page, "B7-return")
                before_sel = re.search(r"Selected Mission Chord: (\S+)", b7)
                before_chord = before_sel.group(1) if before_sel else ""
                notes.append(f"B7_selected_before={before_sel.group(0) if before_sel else ''}")
                # Click a DIFFERENT visible tile than the current selection.
                candidates = ["F#m", "C#m", "A", "B", "Dm", "Am", "G", "C", "Em", "F♯m", "C♯m"]
                # Normalize unicode sharps in before_chord for compare.
                before_norm = (before_chord or "").replace("♯", "#").replace("♭", "b")
                click_target = next(
                    (c for c in candidates if c.replace("♯", "#") != before_norm),
                    "C#m",
                )
                clicked = False
                after_chord = before_chord
                for attempt in range(4):
                    target = click_target if attempt == 0 else next(
                        (c for c in candidates if c.replace("♯", "#") != before_norm and c != click_target),
                        click_target,
                    )
                    if click_chord(page, target):
                        clicked = True
                        click_target = target
                    wait(page, 1500)
                    body_try = page.inner_text("body") or ""
                    m_try = re.search(r"Selected Mission Chord: (\S+)", body_try)
                    after_chord = m_try.group(1) if m_try else after_chord
                    after_norm = (after_chord or "").replace("♯", "#").replace("♭", "b")
                    if after_norm and after_norm != before_norm:
                        break
                wait(page, 800)
                b8 = shot(page, "B8-chord-click")
                after_sel = re.search(r"Selected Mission Chord: (\S+)", b8)
                after_chord = after_sel.group(1) if after_sel else after_chord
                after_norm = (after_chord or "").replace("♯", "#").replace("♭", "b")
                notes.append(
                    f"B8_clicked_target={click_target} selected_after={after_sel.group(0) if after_sel else after_chord}"
                )
                results["B7"] = (
                    f"returned={returned} before={before_sel.group(0) if before_sel else ''} "
                    f"return_page={'Generate example' in b8 or 'Missions' in b8}"
                )
                results["B8"] = (
                    f"clicked={clicked} target={click_target} after={after_sel.group(0) if after_sel else after_chord} "
                    f"changed={bool(after_norm) and after_norm != before_norm}"
                )

            if B_ONLY:
                browser.close()
                text = "\n".join(
                    [
                        f"branch={info['branch']}",
                        f"sha={info['sha']}",
                        f"url={info['url']}",
                        f"streamlit=local 8512",
                        f"b_only=True",
                        "",
                        *[f"{k}: {v}" for k, v in results.items()],
                        "",
                        "NOTES",
                        *notes,
                    ]
                )
                (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
                (OUT / f"{PREFIX}summary.json").write_text(
                    json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                    encoding="utf-8",
                )
                print(text.encode("ascii", "replace").decode("ascii"), flush=True)
                return 0

        # ---------- TEST C: Jam Generator leak ----------
        if E_ONLY or E1_ONLY or E4_ONLY or E5_ONLY:
            notes.append(
                "e_only skip_test_C"
                if E_ONLY
                else (
                    "e5_only skip_test_C"
                    if E5_ONLY
                    else ("e4_only skip_test_C" if E4_ONLY else "e1_only skip_test_C")
                )
            )
        elif open_jam_generator(page, notes):
            set_baseweb_select(page, "Concert Key", "F#") or set_baseweb_select(
                page, "Concert Key", "F# major"
            )
            wait(page, 900)
            # Distinctive BPM for Jam play-session init (Pass 8 §11).
            set_baseweb_select(page, "BPM", "98") or set_bpm(page, 98)
            wait(page, 600)
            click_button_has(page, "Generate jam session") or click_button_has(
                page, "Generate jam"
            ) or click_button_has(page, r"^Generate$")
            wait(page, 3500)
            wait_for(page, "Open in Backing Studio", timeout_ms=8000)
            c0 = shot(page, "C0-jam")
            results["C0"] = (
                f"generator={'Jam Session' in c0} F#={'F#' in c0} "
                f"still_mission={'Selected Mission Chord' in c0}"
            )
            opened = click_open_backing_studio(page, notes, "jam")
            wait(page, 2000)
            wait_for(page, "Backing Track Studio", timeout_ms=10000)
            wait(page, 1500)
            c1 = shot(page, "C1-jam-backing")
            results["C1"] = (
                f"opened={opened} jam_src={'Jam Session Generator' in c1} "
                f"mission_stuck={'MISSION BACKING' in c1} F#={'F#' in c1} "
                f"default={card_default(c1)} current={card_current(c1) or mission_bpm(c1)} "
                f"slider={slider_now(page)} catalog96bleed={card_default(c1) == '96' or slider_now(page) == 96}"
            )
            # Jam BPM edit → refresh persist
            set_bpm(page, 111)
            for _ in range(8):
                wait(page, 700)
                if slider_now(page) == 111:
                    break
            c1b = shot(page, "C1b-jam-bpm111")
            results["C1b"] = (
                f"slider={slider_now(page)} current={card_current(c1b)} "
                f"banner111={'111' in c1b}"
            )
            page.reload(wait_until="domcontentloaded")
            wait(page, 2000)
            wait_backing_ready(page, timeout_ms=22000)
            c1c = shot(page, "C1c-jam-bpm-refresh")
            results["C1c"] = (
                f"slider={slider_now(page)} current={card_current(c1c)} default={card_default(c1c)} "
                f"still111={slider_now(page) == 111}"
            )
            # True leave → second generated Jam with distinctive BPM 127.
            leave_backing_to_practice(page, notes)
            wait(page, 1200)
            if open_jam_generator(page, notes):
                set_baseweb_select(page, "Concert Key", "A") or set_baseweb_select(
                    page, "Concert Key", "A major"
                )
                wait(page, 700)
                set_baseweb_select(page, "BPM", "127") or set_bpm(page, 127)
                wait(page, 600)
                click_button_has(page, "Generate jam session") or click_button_has(
                    page, "Generate jam"
                ) or click_button_has(page, r"^Generate$")
                wait(page, 3500)
                wait_for(page, "Open in Backing Studio", timeout_ms=8000)
                click_open_backing_studio(page, notes, "jam-127")
                wait(page, 2000)
                wait_for(page, "Backing Track Studio", timeout_ms=10000)
                wait_backing_ready(page, timeout_ms=16000)
                c1d = shot(page, "C1d-jam-127")
                results["C1d"] = (
                    f"default={card_default(c1d)} current={card_current(c1d) or mission_bpm(c1d)} "
                    f"slider={slider_now(page)} stale111={slider_now(page) == 111 or card_current(c1d) == '111'} "
                    f"fresh127={slider_now(page) == 127 or card_current(c1d) == '127' or card_default(c1d) == '127'}"
                )
                leave_backing_to_practice(page, notes)
            # Entry Style Jam same source-BPM contract.
            # Product button is "Generate progression" (not "Generate style jam").
            if goto_improv(page, notes):
                click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
                    page, "Entry"
                )
                wait(page, 1200)
                click_radio(page, "Style Jam Mode") or click_radio(page, "Style Jam") or click_button_has(
                    page, "Style Jam"
                )
                wait(page, 1500)
                set_baseweb_select(page, "Concert Key", "G") or set_baseweb_select(
                    page, "Concert Key", "G major"
                )
                wait(page, 500)
                set_baseweb_select(page, "BPM", "130") or set_baseweb_select(
                    page, "Tempo (BPM)", "130"
                ) or set_bpm(page, 130)
                wait(page, 600)
                gen_style = (
                    click_button_has(page, r"Generate progression")
                    or click_button_has(page, "Generate style jam")
                    or click_button_has(page, r"Generate Style")
                )
                notes.append(f"style_jam_generate={gen_style}")
                wait(page, 3500)
                has_open = wait_for(page, "Open in Backing Studio", timeout_ms=12000)
                notes.append(f"style_jam_open_visible={has_open}")
                opened_style = bool(has_open) and click_open_backing_studio(page, notes, "style-jam")
                wait(page, 2000)
                wait_for(page, "Backing Track Studio", timeout_ms=10000)
                wait_backing_ready(page, timeout_ms=16000)
                c1e = shot(page, "C1e-style-jam-130")
                on_backing = "Backing Track Studio" in c1e
                style_src = "Style Jam" in c1e or "Entry & Jam" in c1e
                results["C1e"] = (
                    f"opened={opened_style} on_backing={on_backing} jamish={style_src} "
                    f"default={card_default(c1e)} "
                    f"current={card_current(c1e) or mission_bpm(c1e)} slider={slider_now(page)} "
                    f"fresh130={on_backing and (slider_now(page) == 130 or card_current(c1e) == '130' or card_default(c1e) == '130')} "
                    f"catalogBleed={card_default(c1e) == '96' or ('Catalog song' in c1e and slider_now(page) == 96)}"
                )
                if opened_style and on_backing and (style_src or slider_now(page) == 130):
                    set_bpm(page, 115)
                    for _ in range(8):
                        wait(page, 700)
                        if slider_now(page) == 115:
                            break
                    page.reload(wait_until="domcontentloaded")
                    wait(page, 2000)
                    wait_backing_ready(page, timeout_ms=22000)
                    c1f = shot(page, "C1f-style-jam-refresh")
                    results["C1f"] = (
                        f"slider={slider_now(page)} current={card_current(c1f)} "
                        f"still115={slider_now(page) == 115}"
                    )
                    leave_backing_to_practice(page, notes)
                else:
                    results["C1f"] = "skipped_style_jam_not_opened"
            # Leave Jam Backing → Creative Missions without re-picking the catalog
            # song (pick_song reseals Practice Key to catalog original Bm and masks
            # whether jam leaked F# into the song-owned Dm slot).
            if not goto_improv(page, notes):
                click_nav(page, "Songs")
                wait(page, 1200)
                pick_song(page, notes, "Shape of You", "Pop")
                wait(page, 1600)
                goto_improv(page, notes)
            wait(page, 1000)
            click_radio(page, "Missions") or click_button_has(page, "Missions")
            wait(page, 2200)
            c2 = shot(page, "C2-missions-after-jam")
            leak = (
                "Practice Key: F#" in c2
                or ("F# major" in c2 and "Practice Key: Dm" not in c2 and "Practice Key: Bm" not in c2)
            )
            results["C2"] = (
                f"leak={leak} practiceDm={'Practice Key: Dm' in c2 or 'D minor' in c2 or 'Sounding Key: Dm' in c2} "
                f"practiceBm={'Practice Key: Bm' in c2 and 'Sounding Key: Dm' not in c2} "
                f"F#major={'F# major' in c2 or 'Practice Key: F#' in c2 or 'Sounding Key: F#' in c2} "
                f"reconciled={'stale jam data removed' in c2}"
            )
            click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
            wait(page, 2200)
            c3 = shot(page, "C3-sbi-after-jam")
            results["C3"] = f"Dm={'Practice Key: Dm' in c3 or 'D minor' in c3} F#major={'F# major' in c3}"
        else:
            results["C0"] = "FAIL jam_generator_not_opened"
            notes.append("C_FAIL jam_generator_not_opened")

        if C_ONLY:
            browser.close()
            text = "\n".join(
                [
                    f"branch={info['branch']}",
                    f"sha={info['sha']}",
                    f"url={info['url']}",
                    f"streamlit=local 8512",
                    f"c_only=True",
                    "",
                    *[f"{k}: {v}" for k, v in results.items()],
                    "",
                    "NOTES",
                    *notes,
                ]
            )
            (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
            (OUT / f"{PREFIX}summary.json").write_text(
                json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                encoding="utf-8",
            )
            print(text.encode("ascii", "replace").decode("ascii"), flush=True)
            failed = (
                "FAIL" in results.get("C0", "")
                or "catalog96bleed=True" in results.get("C1", "")
                or "still111=False" in results.get("C1c", "")
                or "fresh127=False" in results.get("C1d", "")
                or "opened=False" in results.get("C1e", "")
                or "fresh130=False" in results.get("C1e", "")
                or "catalogBleed=True" in results.get("C1e", "")
                or "still115=False" in results.get("C1f", "")
                or "skipped_style_jam" in results.get("C1f", "")
                or "leak=True" in results.get("C2", "")
            )
            return 2 if failed else 0

        # ---------- TEST E: active-source restore epoch ----------
        def _open_mission_backing_for_song(
            page: Page, notes: list[str], title: str, genre: str
        ) -> bool:
            click_nav(page, "Songs")
            wait(page, 1500)
            # Clocks lives under Pop in catalog; callers may pass Rock — try both.
            genre_tries = [genre]
            for alt in ("Pop", "Rock", "Country"):
                if alt not in genre_tries:
                    genre_tries.append(alt)
            picked = False
            for g in genre_tries:
                if pick_song(page, notes, title, g):
                    picked = True
                    notes.append(f"E_pick_ok title={title} genre={g}")
                    break
                wait(page, 800)
                click_nav(page, "Songs")
                wait(page, 1200)
            if not picked:
                notes.append(f"E_pick_fail title={title}")
                return False
            wait(page, 1800)
            if not goto_improv(page, notes):
                return False
            wait(page, 1200)
            if not ensure_missions_workspace(page, notes):
                notes.append("E_missions_workspace_fail")
                return False
            # Establish valid Mission context before Open (chord + example).
            click_chord(page, "Eb") or click_chord(page, "Abm") or click_chord(page, "Bb")
            wait(page, 1000)
            gen = click_button_has(page, "Generate example") or click_button_has(
                page, "Generate Example"
            )
            notes.append(f"E_generate_example={gen}")
            wait(page, 2800)
            body = page.inner_text("body") or ""
            if "Mission context is still syncing" in body:
                notes.append("E_mission_still_syncing_before_open")
                wait(page, 2000)
                click_button_has(page, "Generate example") or click_button_has(
                    page, "Generate Example"
                )
                wait(page, 2500)
                body = page.inner_text("body") or ""
            if "Practice in Backing Jam" not in body and "Backing Jam" not in body:
                # Ensure example exists so mission-specific button is visible.
                click_button_has(page, "Generate example") or click_button_has(
                    page, "Generate Example"
                )
                wait(page, 3000)
            return open_mission_backing(page, notes)

        def _open_jam_backing_for_song(
            page: Page, notes: list[str], title: str, genre: str, bpm: int = 98
        ) -> bool:
            click_nav(page, "Songs")
            wait(page, 1500)
            if not pick_song(page, notes, title, genre):
                return False
            wait(page, 1800)
            if not open_jam_generator(page, notes):
                return False
            set_baseweb_select(page, "BPM", str(bpm)) or set_bpm(page, bpm)
            wait(page, 600)
            click_button_has(page, "Generate jam session") or click_button_has(
                page, "Generate jam"
            ) or click_button_has(page, r"^Generate$")
            wait(page, 3500)
            wait_for(page, "Open in Backing Studio", timeout_ms=8000)
            return click_open_backing_studio(page, notes, f"e-jam-{title}")

        def _goto_upload(page: Page, notes: list[str]) -> bool:
            ok = click_nav(page, "Upload") or click_nav(page, "Upload & Analyze")
            wait(page, 2000)
            body = page.inner_text("body") or ""
            landed = "Upload" in body and "Backing Track Studio" not in body
            notes.append(f"upload_nav={ok} landed={landed}")
            return bool(ok or landed)

        def _fill_cpl_song_title(page: Page, title: str = "Trial Song") -> bool:
            """Fill CPL 'Song title' (Streamlit key cpl_title_input)."""
            candidates = [
                page.get_by_label(re.compile(r"^Song title$", re.I)),
                page.locator('input[placeholder*="Ballad"]'),
                page.locator('input[aria-label*="Song title" i]'),
                page.locator('[data-testid="stTextInput"]').filter(
                    has_text=re.compile(r"Song title", re.I)
                ).locator("input"),
            ]
            for loc in candidates:
                try:
                    if loc.count() == 0:
                        continue
                    el = loc.first
                    if not el.is_visible():
                        continue
                    el.scroll_into_view_if_needed()
                    el.click(timeout=2500)
                    el.fill("")
                    el.fill(title)
                    el.press("Tab")
                    wait(page, 800)
                    return True
                except Exception:
                    continue
            # Last resort: first visible text input inside custom builder panel
            try:
                panel = page.locator('[class*="cpl-title"], [data-testid="stVerticalBlock"]').first
                inputs = page.locator('input[type="text"]:visible')
                for i in range(min(inputs.count(), 8)):
                    el = inputs.nth(i)
                    ph = (el.get_attribute("placeholder") or "").lower()
                    val = (el.input_value() or "").lower()
                    if "artist" in ph or "your name" in ph:
                        continue
                    if "ballad" in ph or "my progression" in val or i == 0:
                        el.click(timeout=2000)
                        el.fill("")
                        el.fill(title)
                        el.press("Tab")
                        wait(page, 800)
                        return True
            except Exception:
                pass
            return False

        def _activate_trial_song_custom(page: Page, notes: list[str]) -> bool:
            """Custom Progression Lab → Trial Song → Set as Active Song."""
            clicked = (
                click_nav(page, "Custom")
                or click_nav(page, "Custom Progression")
                or click_button_has(page, r"Custom Progression")
            )
            wait(page, 2500)
            wait_for(page, "Song title", timeout_ms=8000) or wait_for(
                page, "Set as Active Song", timeout_ms=6000
            )
            notes.append(f"custom_nav={clicked}")
            loaded = False
            # Prefer loading an existing Trial Song if library already has it.
            try:
                if click_button_has(page, r"Load saved") or click_label(page, "Load saved"):
                    wait(page, 800)
                if set_baseweb_select(page, "Saved songs", "Trial Song"):
                    wait(page, 800)
                    if click_button_has(page, r"Load selected"):
                        wait(page, 2500)
                        body_load = page.inner_text("body") or ""
                        # Require the builder to actually show Trial Song (not My Progression).
                        title_ok = (
                            "Editing Trial Song" in body_load
                            or 'value="Trial Song"' in (page.content() or "")
                        )
                        try:
                            title_val = page.locator('input[aria-label="Song title"]').input_value(
                                timeout=2000
                            )
                            title_ok = title_ok or str(title_val or "").strip() == "Trial Song"
                        except Exception:
                            pass
                        loaded = bool(title_ok)
                        notes.append(f"custom_loaded_saved_trial={loaded} title_ok={title_ok}")
            except Exception as exc:
                notes.append(f"custom_load_err={exc}")
            if not loaded:
                filled = _fill_cpl_song_title(page, "Trial Song")
                notes.append(f"custom_title_filled={filled}")
                click_button_has(page, r"^C$") or click_button_has(page, r"\bC\b")
                wait(page, 500)
                click_button_has(page, r"^1 bar$") or click_button_has(page, r"1 bar") or click_button_has(
                    page, r"^4 bars$"
                )
                wait(page, 800)
                click_button_has(page, r"Save to library")
                wait(page, 1200)
                if "Trial Song" not in (page.inner_text("body") or ""):
                    filled2 = _fill_cpl_song_title(page, "Trial Song")
                    notes.append(f"custom_title_refill={filled2}")
                    wait(page, 600)
            # Final title gate before Set as Active — never promote My Progression as Trial.
            try:
                title_val = page.locator('input[aria-label="Song title"]').input_value(timeout=2000)
            except Exception:
                title_val = ""
            if str(title_val or "").strip() != "Trial Song":
                filled3 = _fill_cpl_song_title(page, "Trial Song")
                notes.append(f"custom_title_force={filled3} was={title_val!r}")
                wait(page, 800)
                try:
                    title_val = page.locator('input[aria-label="Song title"]').input_value(
                        timeout=2000
                    )
                except Exception:
                    title_val = ""
            if str(title_val or "").strip() != "Trial Song":
                notes.append(f"custom_bind_fail title={title_val!r} abort_activate")
                return False
            activated = False
            for attempt in range(1, 4):
                activated = (
                    click_button_has(page, r"Set as Active Song")
                    or click_button_has(page, r"Save & Activate")
                    or click_button_has(page, r"Activate")
                )
                notes.append(f"custom_activate_attempt={attempt} clicked={activated}")
                wait(page, 4000)
                # Prefer verifying on Custom page first — Songs nav can race a stale
                # catalog reclaim before custom persist lands (E5 run2 flake).
                body_custom = page.inner_text("body") or ""
                side_custom = _sidebar_custom_active(body_custom) and "Trial Song" in (
                    body_custom[
                        body_custom.find("ACTIVE SONG") : body_custom.find("ACTIVE SONG") + 320
                    ]
                    if "ACTIVE SONG" in body_custom
                    else ""
                )
                notes.append(f"custom_side_on_cpl={side_custom}")
                if side_custom:
                    # Settle persist: Custom→Songs once more before hard refresh (E5).
                    click_nav(page, "Songs")
                    wait(page, 2500)
                    body_settle = page.inner_text("body") or ""
                    if not (
                        _sidebar_custom_active(body_settle)
                        and "Trial Song"
                        in (
                            body_settle[
                                body_settle.find("ACTIVE SONG") : body_settle.find("ACTIVE SONG")
                                + 320
                            ]
                            if "ACTIVE SONG" in body_settle
                            else ""
                        )
                    ):
                        notes.append("custom_settle_lost=True")
                        click_nav(page, "Custom") or click_nav(page, "Custom Progression")
                        wait(page, 2000)
                        continue
                    notes.append("custom_active_ok=True")
                    return True
                click_nav(page, "Songs")
                wait(page, 2800)
                body = page.inner_text("body") or ""
                side_ok = _sidebar_custom_active(body) and "Trial Song" in (
                    body[body.find("ACTIVE SONG") : body.find("ACTIVE SONG") + 320]
                    if "ACTIVE SONG" in body
                    else body
                )
                notes.append(f"custom_side_ok_attempt={attempt} side_ok={side_ok}")
                if side_ok:
                    # Do NOT bounce Custom→Songs here — that nav was reclaiming
                    # Country Roads after a green Trial sidebar (E5 flake).
                    notes.append("custom_active_ok=True")
                    return True
                # Retry from Custom page — reload Trial into builder each attempt.
                click_nav(page, "Custom") or click_nav(page, "Custom Progression")
                wait(page, 2000)
                _fill_cpl_song_title(page, "Trial Song")
                wait(page, 600)
            # Last resort: reload then verify sidebar
            page.reload(wait_until="domcontentloaded")
            wait(page, 4500)
            body = page.inner_text("body") or ""
            ok = _sidebar_custom_active(body) and "Trial Song" in body
            notes.append(f"custom_active_ok={ok} after_reload")
            return bool(ok)

        def _sidebar_custom_active(body: str) -> bool:
            """True when ACTIVE SONG block owns Custom (ignore library title mentions)."""
            text = body or ""
            if "ACTIVE SONG" not in text:
                return "CUSTOM PROGRESSION" in text and (
                    "Trial Song" in text or "My Progression" in text
                )
            side = text[text.find("ACTIVE SONG") : text.find("ACTIVE SONG") + 280]
            return "CUSTOM PROGRESSION" in side

        def _ensure_catalog_music_source(page: Page, notes: list[str], *, tag: str) -> bool:
            """Songs page: leave Custom hub and land Catalog as ACTIVE SONG."""
            click_nav(page, "Songs") or click_nav(page, "Song Selection")
            wait(page, 2200)
            body0 = page.inner_text("body") or ""
            if not _sidebar_custom_active(body0) and "ACTIVE SONG" in body0:
                notes.append(f"{tag}_already_catalogish=True")
                return True
            # After Trial Backing, Custom hub ("Use catalog song instead") often is not
            # in the DOM until a fresh Songs render — reload first when Custom is active.
            if _sidebar_custom_active(body0) and "Use catalog song instead" not in body0:
                page.reload(wait_until="domcontentloaded")
                wait(page, 4500)
                click_nav(page, "Songs") or click_nav(page, "Song Selection")
                wait(page, 2500)
                notes.append(f"{tag}_songs_reload_for_hub=True")
            flipped = False
            # 1) Custom hub button (authoritative product path)
            try:
                if click_button_has(page, r"Use catalog song instead"):
                    flipped = True
                    wait(page, 3000)
                    notes.append(f"{tag}_flip=hub_button")
            except Exception as exc:
                notes.append(f"{tag}_catalog_btn_err={exc}")
            # 2) Music source radiogroup text
            if _sidebar_custom_active(page.inner_text("body") or ""):
                try:
                    group = page.get_by_role("radiogroup", name="Music source")
                    if group.count():
                        group.first.scroll_into_view_if_needed()
                        txt = group.get_by_text("Song Selection (catalog song)", exact=True)
                        if txt.count():
                            txt.first.click(timeout=4000, force=True)
                            flipped = True
                            notes.append(f"{tag}_flip=radiogroup_text")
                            wait(page, 3500)
                except Exception as exc:
                    notes.append(f"{tag}_radiogroup_err={exc}")
            if _sidebar_custom_active(page.inner_text("body") or ""):
                if click_radio(page, "Song Selection (catalog song)") or click_radio(
                    page, "catalog song"
                ):
                    flipped = True
                    notes.append(f"{tag}_flip=click_radio")
                    wait(page, 3500)
            # Persist + clear stale custom sidebar after switch
            if flipped or _sidebar_custom_active(page.inner_text("body") or ""):
                page.reload(wait_until="domcontentloaded")
                wait(page, 4000)
                click_nav(page, "Songs")
                wait(page, 2000)
                if _sidebar_custom_active(page.inner_text("body") or ""):
                    if click_button_has(page, r"Use catalog song instead"):
                        flipped = True
                        notes.append(f"{tag}_flip=hub_after_reload")
                        wait(page, 3000)
                        page.reload(wait_until="domcontentloaded")
                        wait(page, 4000)
                        click_nav(page, "Songs")
                        wait(page, 2000)
            for _ in range(4):
                body = page.inner_text("body") or ""
                if not _sidebar_custom_active(body):
                    break
                wait(page, 1500)
            body = page.inner_text("body") or ""
            side_custom = _sidebar_custom_active(body)
            ok = not side_custom
            notes.append(f"{tag}_catalog_radio={flipped} {tag}_catalog_ok={ok}")
            return bool(ok)

        if E_ONLY or not C_ONLY:
            if not E4_ONLY and not E5_ONLY:
                # Cold / residue: prior Trial Custom must not block E1 catalog picks.
                _ensure_catalog_music_source(page, notes, tag="e_matrix_start")
                # E1: same source — Mission Backing survives Upload → Backing
                e1_ok = _open_mission_backing_for_song(page, notes, "Clocks", "Pop")
                wait(page, 2000)
                wait_backing_ready(page, timeout_ms=16000)
                e1a = shot(page, "E1a-mission-clocks")
                _goto_upload(page, notes)
                wait(page, 1500)
                click_nav(page, "Backing")
                wait(page, 2500)
                wait_backing_ready(page, timeout_ms=16000)
                e1 = shot(page, "E1-restore-mission")
                results["E1"] = (
                    f"opened={e1_ok} mission={'MISSION BACKING' in e1 or 'Return to Mission' in e1 or 'Creative Backing Jam · Mission' in e1} "
                    f"clocks={'Clocks' in e1} catalog_bleed={'Catalog song' in e1 and 'MISSION' not in e1 and 'Mission' not in e1} "
                    f"sbi_not_mission={'Song-Based Improvisation' in e1 and 'Mission' not in e1 and 'Creative Backing Jam · Mission' not in e1} "
                    f"syncing={'Mission context is still syncing' in e1a} "
                    f"e1a_mission={'MISSION BACKING' in e1a or 'Return to Mission' in e1a or 'Creative Backing Jam · Mission' in e1a} "
                    f"pkEb={'Practice Key: Eb' in e1 or 'Sounding Key: Eb' in e1 or 'Eb' in e1}"
                )

                if E1_ONLY:
                    browser.close()
                    text = "\n".join(
                        [
                            f"branch={info['branch']}",
                            f"sha={info['sha']}",
                            f"url={info['url']}",
                            f"streamlit=local 8512",
                            f"e1_only=True",
                            "",
                            *[f"{k}: {v}" for k, v in results.items()],
                            "",
                            "NOTES",
                            *notes,
                        ]
                    )
                    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
                    (OUT / f"{PREFIX}summary.json").write_text(
                        json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                        encoding="utf-8",
                    )
                    print(text.encode("ascii", "replace").decode("ascii"), flush=True)
                    e1f = _result_flags(results.get("E1", ""))
                    failed = (
                        not e1_ok
                        or e1f.get("syncing") == "True"
                        or e1f.get("e1a_mission") == "False"
                        or e1f.get("opened") == "False"
                        or e1f.get("mission") == "False"
                        or e1f.get("sbi_not_mission") == "True"
                        or e1f.get("catalog_bleed") == "True"
                    )
                    return 2 if failed else 0

                # E2: different song — Love Story must be regular, zero Clocks Mission restore
                e2_ok = _open_mission_backing_for_song(page, notes, "Clocks", "Rock")
                wait(page, 2000)
                click_nav(page, "Songs")
                wait(page, 1500)
                pick_song(page, notes, "Love Story", "Country") or pick_song(
                    page, notes, "Love Story", "Pop"
                )
                wait(page, 2000)
                click_nav(page, "Backing")
                wait(page, 2500)
                wait_backing_ready(page, timeout_ms=16000)
                e2 = shot(page, "E2-love-story-regular")
                e2_banner = _backing_source_line(e2)
                e2_pk = _practice_concert_key_from_body(e2)
                results["E2"] = (
                    f"prior_mission={e2_ok} catalog={'Catalog song' in e2_banner} "
                    f"love={'Love Story' in e2} love_banner={'Love Story' in e2_banner} "
                    f"mission_stuck={'MISSION BACKING' in e2 or 'Return to Mission' in e2} "
                    f"clocks_stuck={'Clocks' in e2_banner} "
                    f"pkC={e2_pk == 'C' or 'Practice Key: C' in e2 or 'Sounding Key: C' in e2}"
                )

                # E3: Jam restore on same source, then Love Story invalidates
                e3_jam = _open_jam_backing_for_song(page, notes, "Clocks", "Rock", bpm=98)
                wait(page, 2000)
                wait_backing_ready(page, timeout_ms=16000)
                _goto_upload(page, notes)
                wait(page, 1500)
                click_nav(page, "Backing")
                wait(page, 2500)
                wait_backing_ready(page, timeout_ms=16000)
                e3a = shot(page, "E3a-jam-restore")
                click_nav(page, "Songs")
                wait(page, 1500)
                pick_song(page, notes, "Love Story", "Country") or pick_song(
                    page, notes, "Love Story", "Pop"
                )
                wait(page, 2000)
                click_nav(page, "Backing")
                wait(page, 2500)
                wait_backing_ready(page, timeout_ms=16000)
                e3 = shot(page, "E3-love-after-jam")
                results["E3"] = (
                    f"jam_opened={e3_jam} jam_restored={'Jam' in e3a and 'Love Story' not in e3a} "
                    f"love_regular={'Catalog song' in e3 and 'Love Story' in e3} "
                    f"jam_stuck={'Jam Session' in e3 or ('Jam' in e3 and 'Love Story' not in e3)}"
                )

            # E4: Love Story Mission → Country Roads regular D
            if not E5_ONLY:
                if E4_ONLY:
                    _ensure_catalog_music_source(page, notes, tag="e4_pre")
                e4_ok = _open_mission_backing_for_song(page, notes, "Love Story", "Country") or _open_mission_backing_for_song(
                    page, notes, "Love Story", "Pop"
                )
                wait(page, 2000)
                click_nav(page, "Songs")
                wait(page, 1500)
                pick_song(page, notes, "Take Me Home, Country Roads", "Country") or pick_song(
                    page, notes, "Country Roads", "Country"
                )
                wait(page, 2000)
                click_nav(page, "Backing")
                wait(page, 2500)
                wait_backing_ready(page, timeout_ms=16000)
                e4 = shot(page, "E4-country-roads")
                e4_banner = _backing_source_line(e4)
                e4_pk = _practice_concert_key_from_body(e4)
                roads_catalog_key = "A"
                pk_ok = (
                    e4_pk == roads_catalog_key
                    or f"Practice Key: {roads_catalog_key}" in e4
                    or f"Sounding Key: {roads_catalog_key}" in e4
                )
                results["E4"] = (
                    f"prior_mission={e4_ok} roads={'Country Roads' in e4 or 'Take Me Home' in e4} "
                    f"roads_banner={'Country Roads' in e4_banner or 'Take Me Home' in e4_banner} "
                    f"catalog={'Catalog song' in e4_banner} "
                    f"mission_stuck={'MISSION BACKING' in e4 or 'Return to Mission' in e4} "
                    f"love_stuck={'Love Story' in e4_banner} "
                    f"pk_expected={pk_ok} "
                    f"pk_actual={e4_pk or 'missing'} "
                    f"pk_authoritative={roads_catalog_key}"
                )

                if E4_ONLY:
                    browser.close()
                    text = "\n".join(
                        [
                            f"branch={info['branch']}",
                            f"sha={info['sha']}",
                            f"url={info['url']}",
                            f"streamlit=local 8512",
                            f"e4_only=True",
                            "",
                            *[f"{k}: {v}" for k, v in results.items()],
                            "",
                            "NOTES",
                            *notes,
                        ]
                    )
                    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
                    (OUT / f"{PREFIX}summary.json").write_text(
                        json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                        encoding="utf-8",
                    )
                    print(text.encode("ascii", "replace").decode("ascii"), flush=True)
                    e4f = _result_flags(results.get("E4", ""))
                    failed = (
                        e4f.get("roads_banner") == "False"
                        or e4f.get("catalog") == "False"
                        or e4f.get("mission_stuck") == "True"
                        or e4f.get("love_stuck") == "True"
                        or e4f.get("pk_expected") == "False"
                    )
                    return 2 if failed else 0

            # E5: Catalog Country Roads → Custom Trial Song regular (+ refresh + reverse)
            click_nav(page, "Songs")
            wait(page, 1500)
            # Ensure we are on catalog before picking Roads (stale Trial hub blocks pick).
            _ensure_catalog_music_source(page, notes, tag="e5_prior")
            wait(page, 1500)
            pick_song(page, notes, "Take Me Home, Country Roads", "Country") or pick_song(
                page, notes, "Country Roads", "Country"
            )
            wait(page, 1500)
            click_nav(page, "Backing")
            wait(page, 2000)
            wait_backing_ready(page, timeout_ms=12000)
            e5_prior = shot(page, "E5-prior-roads")
            e5_prior_banner = _backing_source_line(e5_prior)
            notes.append(f"e5_previous_source={e5_prior_banner or 'missing'}")

            custom_ok = _activate_trial_song_custom(page, notes)
            wait(page, 1500)
            # Confirm Custom Trial Song is active BEFORE Backing (ACTIVE SONG ownership)
            pre_body = page.inner_text("body") or ""
            pre_trial = _sidebar_custom_active(pre_body) and "Trial Song" in (
                pre_body[pre_body.find("ACTIVE SONG") : pre_body.find("ACTIVE SONG") + 320]
                if "ACTIVE SONG" in pre_body
                else ""
            )
            pre_roads = (not _sidebar_custom_active(pre_body)) and "Country Roads" in (
                pre_body[pre_body.find("ACTIVE SONG") : pre_body.find("ACTIVE SONG") + 280]
                if "ACTIVE SONG" in pre_body
                else pre_body
            )
            notes.append(f"e5_pre_backing_trial={pre_trial} e5_pre_backing_roads={pre_roads}")

            # Ordinary rerun: Enter on a text field / soft reload of current page
            try:
                page.keyboard.press("Enter")
                wait(page, 2000)
            except Exception:
                pass
            rerun_body = page.inner_text("body") or ""
            rerun_ok = _sidebar_custom_active(rerun_body) and "Trial Song" in (
                rerun_body[rerun_body.find("ACTIVE SONG") : rerun_body.find("ACTIVE SONG") + 320]
                if "ACTIVE SONG" in rerun_body
                else ""
            )
            notes.append(f"e5_rerun_trial={rerun_ok}")

            # Browser refresh must keep Trial Song Custom
            page.reload(wait_until="domcontentloaded")
            wait(page, 4000)
            wait_for(page, "ACTIVE SONG", timeout_ms=12000) or wait_for(
                page, "Trial Song", timeout_ms=8000
            )
            refresh_body = page.inner_text("body") or ""
            refresh_ok = _sidebar_custom_active(refresh_body) and "Trial Song" in (
                refresh_body[
                    refresh_body.find("ACTIVE SONG") : refresh_body.find("ACTIVE SONG") + 320
                ]
                if "ACTIVE SONG" in refresh_body
                else ""
            )
            refresh_shot = shot(page, "E5-refresh-trial")
            notes.append(f"e5_refresh_trial={refresh_ok}")

            click_nav(page, "Backing")
            wait(page, 2500)
            wait_backing_ready(page, timeout_ms=16000)
            e5 = shot(page, "E5-trial-song")
            e5_banner = _backing_source_line(e5)
            e5_pk = _practice_concert_key_from_body(e5)
            trial_banner = "Trial Song" in e5_banner
            custom_src = (
                "Custom" in e5_banner
                or "custom progression" in e5_banner.lower()
                or "Custom progression" in e5
            )
            roads_stuck = "Country Roads" in e5_banner
            catalog_stuck = "Catalog song" in e5_banner and "Trial Song" not in e5_banner
            # Practice Key should belong to Trial Song (not Country Roads A leak as sole owner)
            pk_ok = bool(e5_pk) and e5_pk != "" and not (
                roads_stuck and e5_pk == "A" and "Trial Song" not in e5
            )

            # Custom → Catalog reverse: Clocks
            catalog_ok = _ensure_catalog_music_source(page, notes, tag="e5")
            clocks_ok = False
            if catalog_ok:
                clocks_ok = pick_song(page, notes, "Clocks", "Pop") or pick_song(
                    page, notes, "Clocks", "Rock"
                )
            wait(page, 2500)
            click_nav(page, "Backing")
            wait(page, 3500)
            wait_backing_ready(page, timeout_ms=20000)
            wait(page, 1500)
            e5r = shot(page, "E5-reverse-clocks")
            e5r_banner = _backing_source_line(e5r)
            if not e5r_banner:
                # Unicode/dash variants — fall back to raw line scan
                for line in (e5r or "").splitlines():
                    if "Backing source:" in line:
                        e5r_banner = line.strip()
                        break
            reverse_clocks = "Clocks" in e5r_banner and (
                "Catalog song" in e5r_banner or "Catalog" in e5r_banner
            )
            trial_leak = "Trial Song" in e5r_banner
            notes.append(
                f"e5_reverse_banner={e5r_banner or 'missing'} "
                f"reverse_clocks={reverse_clocks} trial_leak={trial_leak}"
            )

            results["E5"] = (
                f"custom_ok={custom_ok} trial={'Trial Song' in e5} "
                f"trial_banner={trial_banner} "
                f"custom_src={custom_src} "
                f"roads_stuck={roads_stuck} "
                f"catalog_stuck={catalog_stuck} "
                f"rerun_ok={rerun_ok} "
                f"refresh_ok={refresh_ok} "
                f"pk_ok={pk_ok} pk_actual={e5_pk or 'missing'} "
                f"pre_trial={pre_trial} "
                f"clocks_pick={bool(clocks_ok)} "
                f"reverse_clocks={reverse_clocks} "
                f"trial_leak={trial_leak}"
            )

            if E5_ONLY:
                browser.close()
                text = "\n".join(
                    [
                        f"branch={info['branch']}",
                        f"sha={info['sha']}",
                        f"url={info['url']}",
                        f"streamlit=local 8512",
                        f"e5_only=True",
                        "",
                        *[f"{k}: {v}" for k, v in results.items()],
                        "",
                        "NOTES",
                        *notes,
                    ]
                )
                (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
                (OUT / f"{PREFIX}summary.json").write_text(
                    json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                    encoding="utf-8",
                )
                print(text.encode("ascii", "replace").decode("ascii"), flush=True)
                e5f = _result_flags(results.get("E5", ""))
                failed = (
                    e5f.get("custom_ok") == "False"
                    or e5f.get("trial") == "False"
                    or e5f.get("trial_banner") == "False"
                    or e5f.get("roads_stuck") == "True"
                    or e5f.get("catalog_stuck") == "True"
                    or e5f.get("refresh_ok") == "False"
                    or e5f.get("reverse_clocks") == "False"
                    or e5f.get("trial_leak") == "True"
                )
                return 2 if failed else 0

        if E_ONLY or E1_ONLY:
            browser.close()
            text = "\n".join(
                [
                    f"branch={info['branch']}",
                    f"sha={info['sha']}",
                    f"url={info['url']}",
                    f"streamlit=local 8512",
                    f"e_only={E_ONLY}",
                    f"e1_only={E1_ONLY}",
                    "",
                    *[f"{k}: {v}" for k, v in results.items()],
                    "",
                    "NOTES",
                    *notes,
                ]
            )
            (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
            (OUT / f"{PREFIX}summary.json").write_text(
                json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
                encoding="utf-8",
            )
            print(text.encode("ascii", "replace").decode("ascii"), flush=True)
            return 2 if _e_matrix_failed(results) else 0

        # ---------- TEST D: source transitions ----------
        def _matrix_row(page: Page, tag: str) -> str:
            body = page.inner_text("body") or ""
            return (
                f"route={'backing' if 'Backing Track Studio' in body else 'other'} "
                f"jam={'Jam Session' in body} style={'Style Jam' in body} "
                f"mission={'MISSION BACKING' in body} catalog={'Catalog song' in body} "
                f"default={card_default(body)} current={card_current(body)} slider={slider_now(page)} "
                f"pkDm={'Practice Key: Dm' in body or 'Sounding Key: Dm' in body} "
                f"F#={'F#' in body}"
            )

        click_nav(page, "Backing")
        wait(page, 2500)
        wait_backing_ready(page, timeout_ms=16000)
        d1 = shot(page, "D1-catalog")
        results["D1"] = _matrix_row(page, "catalog") + f" catalog={'Catalog song' in d1}"
        if goto_improv(page, notes):
            click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
            wait(page, 1800)
            click_open_backing_studio(page, notes, "sbi")
            wait(page, 2200)
            wait_backing_ready(page, timeout_ms=16000)
            d2 = shot(page, "D2-sbi")
            results["D2"] = _matrix_row(page, "sbi") + f" sbi={'Song-Based' in d2 or 'song-based' in d2.lower()}"
            if goto_improv(page, notes):
                click_radio(page, "Missions") or click_button_has(page, "Missions")
                wait(page, 1800)
                click_open_backing_studio(page, notes, "mission-d")
                wait(page, 2200)
                wait_backing_ready(page, timeout_ms=16000)
                d3 = shot(page, "D3-mission")
                results["D3"] = _matrix_row(page, "mission") + f" mission={'MISSION BACKING' in d3 or 'Mission' in d3}"
            if goto_improv(page, notes):
                click_radio(page, "Entry") or click_radio(page, "Entry & Jam")
                wait(page, 1000)
                click_radio(page, "Style Jam") or click_button_has(page, "Style Jam")
                wait(page, 1500)
                click_open_backing_studio(page, notes, "style-d")
                wait(page, 2200)
                wait_backing_ready(page, timeout_ms=16000)
                d4 = shot(page, "D4-style-jam")
                results["D4"] = _matrix_row(page, "style")
            if open_jam_generator(page, notes):
                click_open_backing_studio(page, notes, "jam-d")
                wait(page, 2200)
                wait_backing_ready(page, timeout_ms=16000)
                d5 = shot(page, "D5-jam-gen")
                results["D5"] = _matrix_row(page, "jam")
                leave_backing_to_practice(page, notes)
            if goto_improv(page, notes):
                click_radio(page, "Missions") or click_button_has(page, "Missions")
                wait(page, 1800)
                d6 = shot(page, "D6-missions-after")
                results["D6"] = (
                    f"pkDm={'Practice Key: Dm' in d6 or 'Sounding Key: Dm' in d6} "
                    f"F#leak={'Practice Key: F#' in d6 or 'Sounding Key: F#' in d6}"
                )
                click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
                wait(page, 1800)
                d7 = shot(page, "D7-sbi-after")
                results["D7"] = f"pkDm={'Practice Key: Dm' in d7 or 'D minor' in d7} F#={'F#' in d7}"
            click_nav(page, "Backing")
            wait(page, 2500)
            wait_backing_ready(page, timeout_ms=16000)
            d8 = shot(page, "D8-catalog-return")
            results["D8"] = _matrix_row(page, "catalog-return")

        browser.close()

    lines = [
        f"branch={info['branch']}",
        f"sha={info['sha']}",
        f"url={info['url']}",
        "streamlit=restarted local 8512 from feature/creative-backing-stabilization working tree",
        "cloud_dev=NOT_USED",
        "",
    ]
    for k, v in results.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("NOTES")
    lines.extend(notes)
    (OUT / "pass8v-summary.txt").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "pass8v-summary.json").write_text(
        json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
        encoding="utf-8",
    )
    print("\n".join(lines).encode("ascii", "replace").decode("ascii"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

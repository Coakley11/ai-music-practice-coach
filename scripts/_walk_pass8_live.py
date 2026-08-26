"""Pass 8 live Streamlit walk — Tests A–D against a local instance.

Usage: python scripts/_walk_pass8_live.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "pass8-"


def git_info() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    def _run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()
    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:18000], encoding="utf-8")
    return body


def _quick_bpm_input(page: Page):
    """Streamlit 1.4x+ uses React-Aria range inputs (no role=slider)."""
    for label in ("Quick BPM", "TEMPO (BPM)", "Tempo", "BPM"):
        loc = page.locator(f'input[type="range"][aria-label="{label}"]')
        if loc.count():
            try:
                el = loc.first
                if el.count():
                    return el
            except Exception:
                continue
    # Fallback: any visible BPM-range input (20–180-ish).
    for cand in page.locator('input[type="range"]').all():
        try:
            mn = float(cand.get_attribute("min") or 0)
            mx = float(cand.get_attribute("max") or 0)
            aria = str(cand.get_attribute("aria-label") or "")
            if mn <= 40 and mx >= 140 and re.search(r"BPM|TEMPO|Tempo", aria, re.I):
                return cand
            if mn <= 40 and mx >= 140:
                return cand
        except Exception:
            continue
    return None


def _slider(page: Page):
    # Legacy role=slider (older Streamlit).
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
    return _quick_bpm_input(page)


def slider_bpm(page: Page) -> int | None:
    # Prefer card text (authoritative applied BPM) then widget value.
    card = current_card_bpm(page.inner_text("body") or "")
    if card is not None:
        return card
    el = _slider(page)
    if el is None:
        for cand in page.locator('[role="slider"]').all():
            try:
                if not cand.is_visible():
                    continue
                mn = float(cand.get_attribute("aria-valuemin") or 0)
                mx = float(cand.get_attribute("aria-valuemax") or 0)
                if mn <= 60 and mx >= 140:
                    el = cand
                    break
            except Exception:
                continue
    if el is None:
        return None
    try:
        now = el.get_attribute("aria-valuenow") or el.input_value() or el.get_attribute("value")
        return int(float(now or 0)) or None
    except Exception:
        return None


def set_slider_bpm(page: Page, value: int) -> int | None:
    """Set Backing BPM via Quick BPM range input (Home + ArrowRight)."""
    open_advanced(page)
    page.wait_for_timeout(400)
    # Primary path: Quick BPM / TEMPO range input (current Streamlit).
    inp = _quick_bpm_input(page)
    if inp is not None:
        try:
            inp.scroll_into_view_if_needed()
            inp.focus()
            page.keyboard.press("Home")
            page.wait_for_timeout(150)
            mn = 20
            try:
                mn = int(float(inp.get_attribute("min") or 20))
            except Exception:
                mn = 20
            steps = max(0, int(value) - mn)
            for _ in range(steps):
                page.keyboard.press("ArrowRight")
            wait_idle(page, 2000)
            now = current_card_bpm(page.inner_text("body") or "") or slider_bpm(page)
            if now == value or (now is not None and abs(int(now) - int(value)) <= 1):
                return now
            # Click track at fractional position as backup.
            block = page.locator("[data-testid=stSlider]").filter(has_text=re.compile(r"Quick BPM|TEMPO|BPM", re.I))
            if block.count():
                track = block.first.locator("[data-orientation=horizontal]").first
                box = track.bounding_box()
                if box:
                    mx = 180
                    try:
                        mx = int(float(inp.get_attribute("max") or 180))
                    except Exception:
                        mx = 180
                    frac = max(0.0, min(1.0, (float(value) - mn) / max(1.0, float(mx - mn))))
                    page.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] / 2)
                    wait_idle(page, 2000)
                    now = current_card_bpm(page.inner_text("body") or "") or slider_bpm(page)
                    if now is not None:
                        return now
            return now
        except Exception:
            pass
    el = _slider(page)
    if el is None:
        for cand in page.locator('[role="slider"]').all():
            try:
                if not cand.is_visible():
                    continue
                mn = float(cand.get_attribute("aria-valuemin") or 0)
                mx = float(cand.get_attribute("aria-valuemax") or 0)
                if mn <= 60 and mx >= 140:
                    el = cand
                    break
            except Exception:
                continue
    if el is None:
        # Number-input fallback labeled TEMPO
        try:
            root = page.locator('[data-testid="stNumberInput"]')
            for i in range(min(root.count(), 8)):
                block = root.nth(i)
                label = (block.inner_text() or "") + (block.get_attribute("aria-label") or "")
                parent_txt = ""
                try:
                    parent_txt = block.locator("xpath=ancestor::div[contains(@class,'element-container')]").inner_text()
                except Exception:
                    parent_txt = label
                if not re.search(r"TEMPO|BPM", parent_txt, re.I):
                    continue
                num = block.locator("input").first
                if not num.count():
                    continue
                num.click(timeout=2000)
                num.fill("")
                num.type(str(value), delay=30)
                num.press("Enter")
                wait_idle(page, 2000)
                now = current_card_bpm(page.inner_text("body") or "") or slider_bpm(page)
                return now or value
        except Exception:
            pass
        return current_card_bpm(page.inner_text("body") or "")
    try:
        el.scroll_into_view_if_needed()
        el.focus()
        page.keyboard.press("Home")
        page.wait_for_timeout(200)
        mn = int(float(el.get_attribute("aria-valuemin") or el.get_attribute("min") or 20))
        steps = max(0, int(value) - mn)
        for _ in range(steps):
            page.keyboard.press("ArrowRight")
        wait_idle(page, 1800)
        return current_card_bpm(page.inner_text("body") or "") or slider_bpm(page)
    except Exception:
        return slider_bpm(page)


def body_bpms(text: str) -> list[int]:
    found = re.findall(r"(?:BPM[:\s·]+(\d{2,3})|(\d{2,3})\s*BPM)", text, flags=re.I)
    out: list[int] = []
    for a, b in found:
        try:
            out.append(int(a or b))
        except ValueError:
            pass
    return out


def current_card_bpm(text: str) -> int | None:
    m = re.search(r"Current\s+(\d{2,3})\s*BPM", text, flags=re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"Current BPM[:\s·]+(\d{2,3})", text, flags=re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"⏱\s*BPM\s*·\s*(\d{2,3})", text)
    if m:
        return int(m.group(1))
    m = re.search(r"BPM\s*·\s*(\d{2,3})", text)
    if m:
        return int(m.group(1))
    return None


def open_advanced(page: Page) -> bool:
    return bool(
        click_button_has(page, r"Advanced playback")
        or click_button_has(page, r"Advanced")
    )


def set_practice_key(page: Page, token: str) -> bool:
    """Set sidebar Practice / Concert Key to ``token`` only (no silent fallbacks)."""
    expand_sidebar(page)
    want = str(token or "").strip()
    if not want:
        return False
    aliases = [want]
    low = want.lower().replace(" ", "")
    # Sidebar options use short tokens (Cm, C#m, D) — not "C minor".
    if low in {"c#minor", "c#m", "dbminor", "dbm"}:
        aliases = ["C#m", "Dbm", "C# minor", "Db minor"]
    elif low in {"cminor", "cm"}:
        aliases = ["Cm", "C minor"]
    elif low in {"dmajor", "d"}:
        aliases = ["D", "D major"]
    elif low in {"dminor", "dm"}:
        aliases = ["Dm", "D minor"]
    elif low in {"f#major", "f#", "gb"}:
        aliases = ["F#", "Gb", "F# major"]
    elif low in {"gmajor", "g"}:
        aliases = ["G", "G major"]
    elif low in {"emajor", "e"}:
        aliases = ["E", "E major"]
    elif low in {"ebmajor", "eb", "d#"}:
        aliases = ["Eb", "D#", "Eb major"]

    def _concert_label() -> str:
        try:
            body = page.inner_text("body") or ""
            m = re.search(r"Practice concert key:\s*([^\n·]+)", body, re.I)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        try:
            from _walk_custom_practice_key import pk_val

            return str(pk_val(page) or "").strip()
        except Exception:
            return ""

    def _norm_key(s: str) -> str:
        t = (s or "").lower().replace(" ", "").replace("♯", "#").replace("♭", "b")
        if t.endswith("minor"):
            return t[: -len("minor")] + "m"
        if t.endswith("major"):
            return t[: -len("major")]
        return t

    def _landed_ok(landed: str, opt: str) -> bool:
        # Exact normalized match only — "Cm" must not accept "C# minor".
        L = _norm_key(landed)
        O = _norm_key(opt)
        return bool(L) and bool(O) and L == O

    for opt in aliases:
        if set_baseweb_select(page, "Practice / Concert Key", opt):
            wait_idle(page, 2000)
            landed = _concert_label()
            if _landed_ok(landed, opt):
                return True
            continue
    # Typeahead into the combobox (Streamlit filters long / virtualized option lists).
    try:
        side = page.locator('section[data-testid="stSidebar"]')
        box = side.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
        )
        if box.count() == 0:
            box = page.locator('[data-testid="stSelectbox"]').filter(
                has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
            )
        for opt in aliases:
            try:
                target = box.first
                target.scroll_into_view_if_needed()
                inp = target.locator("input").first
                if inp.count() == 0:
                    target.locator('[data-baseweb="select"], [role="combobox"]').first.click(timeout=4000)
                    page.wait_for_timeout(200)
                    inp = target.locator("input").first
                else:
                    inp.click(timeout=4000)
                page.wait_for_timeout(150)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(opt, delay=40)
                page.wait_for_timeout(700)
                hit = page.locator(
                    '[role="listbox"] [role="option"], [data-baseweb="menu"] [role="option"]'
                ).filter(has_text=re.compile(rf"^{re.escape(opt)}$", re.I))
                if not hit.count():
                    # Virtualized: arrow through filtered results.
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(200)
                    hit = page.locator(
                        '[role="listbox"] [role="option"], [role="option"]'
                    ).filter(has_text=re.compile(rf"^{re.escape(opt)}$", re.I))
                if not hit.count():
                    page.keyboard.press("Escape")
                    continue
                hit.first.click(timeout=4000, force=False)
                wait_idle(page, 3500)
                # Prefer on-page concert key label over widget scrape.
                body = page.inner_text("body") or ""
                m = re.search(r"Practice concert key:\s*([^\n·]+)", body, re.I)
                landed = (m.group(1).strip() if m else "")
                if not landed:
                    try:
                        from _walk_custom_practice_key import pk_val

                        landed = str(pk_val(page) or "").strip()
                    except Exception:
                        landed = ""
                if _landed_ok(landed, opt):
                    return True
                if opt.lower() == "cm" and landed.lower() in {"c", "c major"}:
                    continue
                continue
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                continue
    except Exception:
        pass
    return False


def click_chord_tile(page: Page, label: str) -> bool:
    try:
        btn = page.locator("button").filter(has_text=re.compile(rf"^{re.escape(label)}$"))
        for i in range(min(btn.count(), 12)):
            el = btn.nth(i)
            try:
                if el.is_visible():
                    el.click(timeout=3000)
                    wait_idle(page, 2500)
                    return True
            except Exception:
                continue
        return click_button_has(page, rf"^{re.escape(label)}$")
    except Exception:
        return False


def select_sections_chorus(page: Page) -> bool:
    try:
        if click_button_has(page, r"Selected sections") or click_radio(page, "Selected sections"):
            wait_idle(page, 1500)
        # Streamlit multiselect
        box = page.locator('[data-testid="stMultiSelect"]').first
        if box.count() and box.is_visible():
            box.click()
            page.wait_for_timeout(500)
            opt = page.locator('[role="option"]').filter(has_text=re.compile("Chorus", re.I))
            if opt.count():
                opt.first.click()
                wait_idle(page, 2500)
                return True
        return set_baseweb_select(page, "section", "Chorus") or click_button_has(page, "Chorus")
    except Exception:
        return False


def matrix_row(page: Page, owner: str) -> dict[str, str]:
    body = page.inner_text("body") or ""
    side = ""
    try:
        side = page.evaluate(
            """() => {
              const s = document.querySelector('section[data-testid="stSidebar"]');
              return s ? (s.innerText || '') : '';
            }"""
        )
    except Exception:
        side = ""
    bpm = current_card_bpm(body)
    slider = slider_bpm(page)
    return {
        "owner": owner,
        "song": "Shape of You" if "Shape of You" in body else "",
        "practice_key": (
            "Dm" if re.search(r"Practice Key:\s*Dm", body) or "D minor" in side else
            "F#" if "F#" in (body + side) else
            "Em" if "E minor" in (body + side) or re.search(r"Practice Key:\s*Em", body) else
            ""
        ),
        "instrument": "Guitar" if "Guitar" in (body + side) else "",
        "shape": (
            "C#" if "C#" in (body + side) or "C♯" in (body + side) else
            "E" if "E minor" in (body + side) or "Shape Key" in side else ""
        ),
        "default_bpm": str(body_bpms(body)[:4]),
        "current_bpm": str(bpm or slider or ""),
        "sections": "Chorus" if "Chorus" in body else "",
        "source": (
            "Mission" if "Mission Backing" in body or "Creative Backing Jam · Mission" in body else
            "Jam Generator" if "Jam Session Generator" in body else
            "Style Jam" if "Style Jam" in body else
            "SBI" if "Song-Based" in body else
            "Catalog" if "Backing source: Catalog" in body or "Backing Track Studio" in body else
            ""
        ),
    }


def main() -> int:
    info = git_info()
    notes: list[str] = [f"branch={info['branch']}", f"sha={info['sha']}", f"url={info['url']}"]
    results: dict[str, str] = {}
    matrix: list[dict[str, str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait_idle(page, 5000)
        shot(page, "00-landing")

        pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page, 4000)
        set_instrument(page, "Guitar")
        wait_idle(page, 2000)
        expand_sidebar(page)
        set_practice_key(page, "Dm")
        wait_idle(page, 2500)
        enable_guitar_capo(page, notes, "E") or set_shape_tonic(page, "E")
        wait_idle(page, 2500)
        shot(page, "01-shape-of-you-setup")

        # ---------- TEST A: Regular catalog Backing ----------
        expand_sidebar(page)
        click_nav(page, "Backing")
        wait_idle(page, 5000)
        a0 = shot(page, "A0-catalog-enter")
        matrix.append(matrix_row(page, "Catalog Backing enter"))
        bpm0 = slider_bpm(page)
        notes.append(f"A enter slider={bpm0} card={current_card_bpm(a0)}")
        set_ok = set_slider_bpm(page, 96)
        wait_idle(page, 2500)
        a1 = shot(page, "A1-bpm-96-same-rerun")
        card1 = current_card_bpm(a1)
        slider1 = slider_bpm(page)
        results["A_bpm_same_rerun"] = f"slider={slider1} card={card1} set={set_ok}"
        open_advanced(page)
        wait_idle(page, 1500)
        style_ok = set_baseweb_select(page, "Groove", "Blues") or set_baseweb_select(page, "style", "Blues")
        wait_idle(page, 2000)
        meter_ok = click_radio(page, "3/4") or click_button_has(page, r"3/4")
        wait_idle(page, 2000)
        sec_ok = select_sections_chorus(page)
        wait_idle(page, 2500)
        a2 = shot(page, "A2-style-meter-sections")
        results["A_knobs_same_rerun"] = (
            f"style={style_ok or ('Blues' in a2)} meter={meter_ok or ('3/4' in a2)} "
            f"sections={sec_ok or ('Chorus' in a2)}"
        )
        page.reload(wait_until="domcontentloaded")
        wait_idle(page, 6000)
        a3 = shot(page, "A3-refresh")
        slider3 = slider_bpm(page)
        card3 = current_card_bpm(a3)
        results["A_refresh"] = (
            f"slider={slider3} card={card3} blues={'Blues' in a3} "
            f"meter={'3/4' in a3} chorus={'Chorus' in a3}"
        )
        click_nav(page, "Practice")
        wait_idle(page, 3500)
        shot(page, "A4-leave-backing")
        click_nav(page, "Backing")
        wait_idle(page, 5000)
        a5 = shot(page, "A5-return-later")
        slider5 = slider_bpm(page)
        results["A_leave_return"] = f"slider={slider5} card={current_card_bpm(a5)} (expect ~source 82)"
        matrix.append(matrix_row(page, "Catalog Backing after leave/return"))

        # ---------- TEST B: Mission Backing ----------
        if goto_improv(page, notes):
            click_radio(page, "Missions") or click_button_has(page, "Missions")
            wait_idle(page, 4000)
            expand_sidebar(page)
            set_practice_key(page, "Dm")
            wait_idle(page, 2000)
            enable_guitar_capo(page, notes, "E") or set_shape_tonic(page, "E")
            wait_idle(page, 2500)
            click_chord_tile(page, "Am") or click_button_has(page, "Am")
            wait_idle(page, 2000)
            gen = click_button_has(page, "Generate example") or click_button_has(page, "Generate Example")
            wait_idle(page, 5000)
            b0 = shot(page, "B0-missions-am-generate")
            results["B_missions_pre"] = (
                f"gen={gen} Am={'Am' in b0} Gm_stale={'Gm' in b0 and 'Selected Mission Chord: Gm' in b0} "
                f"practice={'Practice Key: Dm' in b0} charts_E={'E minor' in b0}"
            )
            opened = click_open_backing_studio(page, notes, "mission")
            wait_idle(page, 5000)
            b1 = shot(page, "B1-mission-backing")
            matrix.append(matrix_row(page, "Mission Backing"))
            gm_label = bool(re.search(r"Selected Mission Chord:\s*Gm|· Gm\b|G minor", b1))
            results["B_chord_label"] = (
                f"opened={opened} Gm_stale={gm_label} Am={'Am' in b1} "
                f"guitar={'Guitar' in b1} E={'E minor' in b1}"
            )
            set_slider_bpm(page, 103)
            wait_idle(page, 2500)
            b2 = shot(page, "B2-bpm-103")
            results["B_bpm_same_rerun"] = f"slider={slider_bpm(page)} card={current_card_bpm(b2)}"
            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 6000)
            b3 = shot(page, "B3-refresh-bpm")
            results["B_bpm_refresh"] = f"slider={slider_bpm(page)} card={current_card_bpm(b3)}"
            pk = set_practice_key(page, "Em")
            wait_idle(page, 3000)
            b4 = shot(page, "B4-practice-em")
            results["B_practice_key"] = f"clicked={pk} Em={'Em' in b4 or 'E minor' in b4} Dm_stuck={'Practice Key: Dm' in b4}"
            shape_ok = enable_guitar_capo(page, notes, "C#") or set_shape_tonic(page, "C#")
            wait_idle(page, 3500)
            b5 = shot(page, "B5-shape-csharp")
            results["B_shape_reproject"] = (
                f"clicked={shape_ok} csharp={'C#' in b5 or 'C♯' in b5} "
                f"example_am={'Am' in b5}"
            )
            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 6000)
            b6 = shot(page, "B6-shape-refresh")
            results["B_shape_refresh"] = f"csharp={'C#' in b6 or 'C♯' in b6}"
            ret = (
                click_button_has(page, "Return to Mission")
                or click_button_has(page, "Missions")
                or click_nav(page, "Creative")
            )
            wait_idle(page, 4000)
            click_radio(page, "Missions") or click_button_has(page, "Missions")
            wait_idle(page, 3000)
            b7 = shot(page, "B7-return-missions")
            clicked_other = click_chord_tile(page, "Dm") or click_button_has(page, "Dm") or click_chord_tile(page, "G")
            wait_idle(page, 2500)
            b8 = shot(page, "B8-chord-first-click")
            results["B_return_chord"] = f"return={ret} clicked={clicked_other} selected_change={b8 != b7}"
            gen2 = click_button_has(page, "Generate example")
            wait_idle(page, 4500)
            shot(page, "B9-generate-after-chord")
            results["B_generate_after"] = f"clicked={gen2}"

        # ---------- TEST C: Jam Generator + leak ----------
        if goto_improv(page, notes):
            click_radio(page, "Entry") or click_button_has(page, "Entry") or click_button_has(page, "Jam")
            wait_idle(page, 2500)
            click_button_has(page, "Jam Session") or click_button_has(page, "Generator")
            wait_idle(page, 2500)
            set_baseweb_select(page, "Key", "F#") or set_baseweb_select(page, "Jam", "F#")
            wait_idle(page, 1500)
            click_button_has(page, "Generate")
            wait_idle(page, 6000)
            c0 = shot(page, "C0-jam-generated")
            opened = click_open_backing_studio(page, notes, "jam")
            wait_idle(page, 5000)
            c1 = shot(page, "C1-jam-backing")
            matrix.append(matrix_row(page, "Jam Generator Backing"))
            results["C_jam_init"] = (
                f"opened={opened} slider={slider_bpm(page)} card={current_card_bpm(c1)} "
                f"F#={'F#' in c1} bpms={body_bpms(c1)[:6]}"
            )
            set_slider_bpm(page, 110)
            wait_idle(page, 2000)
            page.reload(wait_until="domcontentloaded")
            wait_idle(page, 6000)
            c2 = shot(page, "C2-jam-bpm-refresh")
            results["C_jam_bpm_refresh"] = f"slider={slider_bpm(page)} card={current_card_bpm(c2)}"
            pk = set_practice_key(page, "G")
            wait_idle(page, 2500)
            c3 = shot(page, "C3-jam-practice-key")
            results["C_jam_pk"] = f"clicked={pk} body_has_G={' G' in c3 or 'G major' in c3}"
            # Navigate to Shape of You Missions — F# must not leak
            click_nav(page, "Songs") or click_nav(page, "Practice")
            wait_idle(page, 3000)
            pick_song(page, notes, "Shape of You", "Pop")
            wait_idle(page, 3500)
            if goto_improv(page, notes):
                click_radio(page, "Missions") or click_button_has(page, "Missions")
                wait_idle(page, 4000)
            c4 = shot(page, "C4-missions-after-jam")
            matrix.append(matrix_row(page, "Missions after Jam"))
            leak = bool(re.search(r"Practice Key:\s*F#", c4)) or (
                "F# major" in c4 and "Practice Key: Dm" not in c4
            )
            results["C_jam_no_leak"] = (
                f"leak={leak} practice_Dm={'Practice Key: Dm' in c4 or 'D minor' in c4} "
                f"F#_major={'F# major' in c4}"
            )
            click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
            wait_idle(page, 3500)
            c5 = shot(page, "C5-sbi-after-jam")
            results["C_sbi_no_leak"] = f"Dm={'Dm' in c5} F#={'F# major' in c5}"

        # ---------- TEST D: source transition matrix ----------
        expand_sidebar(page)
        click_nav(page, "Backing")
        wait_idle(page, 4000)
        shot(page, "D1-catalog")
        matrix.append(matrix_row(page, "D Catalog"))
        if goto_improv(page, notes):
            click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
            wait_idle(page, 3000)
            click_open_backing_studio(page, notes, "sbi")
            wait_idle(page, 4000)
            shot(page, "D2-sbi")
            matrix.append(matrix_row(page, "D SBI Backing"))
            if goto_improv(page, notes):
                click_radio(page, "Missions") or click_button_has(page, "Missions")
                wait_idle(page, 3000)
                click_open_backing_studio(page, notes, "mission")
                wait_idle(page, 4000)
                shot(page, "D3-mission")
                matrix.append(matrix_row(page, "D Mission Backing"))
            if goto_improv(page, notes):
                click_radio(page, "Entry") or click_button_has(page, "Entry")
                wait_idle(page, 2000)
                click_button_has(page, "Style Jam")
                wait_idle(page, 2000)
                click_button_has(page, "Generate")
                wait_idle(page, 4000)
                click_open_backing_studio(page, notes, "style")
                wait_idle(page, 4000)
                shot(page, "D4-style-jam")
                matrix.append(matrix_row(page, "D Style Jam Backing"))
            if goto_improv(page, notes):
                click_radio(page, "Entry") or click_button_has(page, "Jam")
                wait_idle(page, 2000)
                click_button_has(page, "Jam Session") or click_button_has(page, "Generator")
                wait_idle(page, 2000)
                click_button_has(page, "Generate")
                wait_idle(page, 4000)
                click_open_backing_studio(page, notes, "jamgen")
                wait_idle(page, 4000)
                shot(page, "D5-jam-gen")
                matrix.append(matrix_row(page, "D Jam Generator Backing"))
            if goto_improv(page, notes):
                click_radio(page, "Missions") or click_button_has(page, "Missions")
                wait_idle(page, 3500)
                shot(page, "D6-missions")
                matrix.append(matrix_row(page, "D Missions"))
                click_radio(page, "Song-Based") or click_button_has(page, "Song-Based")
                wait_idle(page, 3000)
                shot(page, "D7-sbi")
                matrix.append(matrix_row(page, "D SBI"))
        click_nav(page, "Backing")
        wait_idle(page, 4000)
        shot(page, "D8-catalog")
        matrix.append(matrix_row(page, "D Catalog return"))

        browser.close()

    payload = {"info": info, "notes": notes, "results": results, "matrix": matrix}
    (OUT / "pass8-live-summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        f"branch={info['branch']}",
        f"sha={info['sha']}",
        f"url={info['url']}",
        "streamlit=fresh local 8512 (Pass 8 working tree)",
        "",
        "RESULTS",
    ]
    for k, v in results.items():
        lines.append(f"{k}: {v}")
    lines.append("")
    lines.append("MATRIX")
    for row in matrix:
        lines.append(json.dumps(row))
    lines.append("")
    lines.append("NOTES")
    lines.extend(notes)
    (OUT / "pass8-live-summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:80]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

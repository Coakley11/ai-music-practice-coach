"""Walk required Creative <-> Backing routes and capture screenshots.

Uses visible Streamlit controls (roles/labels/text), waits for reruns, and
writes body excerpts so a failed click still leaves inspectable evidence.
"""
from __future__ import annotations

import json
import re
import traceback
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

URL = "http://127.0.0.1:8503"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
NOTES = OUT / "pass3-matrix-notes.txt"
PREFIX = "pass3-"
NAV = {
    "Practice": "Practice",
    "Songs": "Song Selection",
    "Backing": "Backing Track",
    "Custom": "Custom Progression",
    "Compose": "Composition Studio",
    "Creative": "Creative Lab",
    "Upload": "Upload Analysis",
    "Multitrack": "Multitrack",
    "Log": "Practice Log",
}


def _log(notes: list[str], msg: str) -> None:
    notes.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def wait_idle(page: Page, ms: int = 2500) -> None:
    page.wait_for_timeout(400)
    try:
        page.locator('[data-testid="stSpinner"]').first.wait_for(state="hidden", timeout=20_000)
    except Exception:
        pass
    try:
        page.wait_for_function(
            """() => {
              const w = document.querySelector('[data-testid="stStatusWidget"]');
              if (w) {
                const t = (w.innerText || '').toLowerCase();
                if (t.includes('running')) return false;
              }
              const buttons = [...document.querySelectorAll('button')];
              if (buttons.some((b) => (b.innerText || '').trim() === 'Stop')) return false;
              return true;
            }""",
            timeout=45_000,
        )
    except Exception:
        pass
    page.wait_for_timeout(ms)


def _prefixed(name: str) -> str:
    if name.startswith(PREFIX):
        return name
    return PREFIX + name


def shot(page: Page, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / _prefixed(name)), full_page=True)


def save_body(page: Page, name: str, n: int = 20000) -> str:
    body = page.inner_text("body")
    (OUT / _prefixed(name)).write_text(body[:n], encoding="utf-8")
    return body


def visible_open_indexes(page: Page) -> tuple[Locator, list[int]]:
    opens = page.locator("button").filter(has_text=re.compile(r"^Open$"))
    vis = [i for i in range(opens.count()) if opens.nth(i).is_visible()]
    return opens, vis


def expand_pages_nav(page: Page) -> None:
    """Expand the sidebar Pages list so studio page buttons exist."""
    expand_sidebar(page)
    if page.locator("button").filter(has_text=re.compile(r"Creative Lab", re.I)).count():
        return
    loc = page.locator("button").filter(has_text=re.compile(r"Pages", re.I))
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.evaluate("node => node.scrollIntoView({block: 'center'})")
            box = el.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                wait_idle(page, 2500)
                break
        except Exception:
            continue
    if page.locator("button").filter(has_text=re.compile(r"Creative Lab", re.I)).count():
        return


def click_nav(page: Page, name: str) -> bool:
    expand_pages_nav(page)
    label = NAV.get(name, name)
    loc = page.locator('section[data-testid="stSidebar"] button').filter(
        has_text=re.compile(re.escape(label), re.I)
    )
    if loc.count() == 0:
        loc = page.locator("button").filter(has_text=re.compile(re.escape(label), re.I))
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.evaluate("node => node.scrollIntoView({block: 'center', inline: 'nearest'})")
            page.wait_for_timeout(250)
            box = el.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            else:
                el.click(timeout=5000, force=True)
            wait_idle(page, 4000)
            return True
        except Exception:
            continue
    clicked = page.evaluate(
        """(label) => {
          const needle = String(label || '').toLowerCase();
          const vis = (el) => !!(el && el.offsetParent !== null);
          const buttons = [...document.querySelectorAll('button')].filter(vis);
          const exact = buttons.find((b) => (b.innerText || '').trim().toLowerCase().endsWith(needle));
          const b = exact || buttons.find((btn) => (btn.innerText || '').toLowerCase().includes(needle));
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach((type) => {
            b.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
          });
          return true;
        }""",
        label,
    )
    if clicked:
        wait_idle(page, 4000)
        return True
    opens, vis = visible_open_indexes(page)
    idx = {"Practice": 0, "Songs": 1, "Backing": 2, "Custom": 3, "Compose": 4, "Creative": 5, "Upload": 6, "Multitrack": 7, "Log": 8}.get(name)
    if idx is not None and idx < len(vis):
        opens.nth(vis[idx]).click()
        wait_idle(page, 4000)
        return True
    return click_visible_text(page, label)


def click_visible(locator: Locator) -> bool:
    count = locator.count()
    for i in range(count):
        el = locator.nth(i)
        try:
            if el.is_visible():
                el.click(timeout=4000)
                return True
        except Exception:
            continue
    return False


def click_label(page: Page, text: str) -> bool:
    loc = page.locator("label").filter(has_text=re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 3500)
        return True
    loc = page.get_by_text(re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 3500)
        return True
    return False


def click_radio(page: Page, text: str) -> bool:
    """Click a Streamlit radio option by visible text (icons allowed).

    Newer Streamlit radios often use ``input[type=radio]`` + label text inside a
    ``[role=radiogroup]``, not ``[role=radio]``. Prefer radiogroup labels so we do
    not false-match nav buttons like ``Song Selection``.
    """
    clicked = page.evaluate(
        """(text) => {
          const needle = String(text || '').toLowerCase();
          const vis = (el) => !!(el && el.offsetParent !== null);
          const clickEl = (el) => {
            if (!el) return false;
            el.scrollIntoView({block: 'center'});
            el.click();
            return true;
          };
          // Preferred: label inside a radiogroup (Streamlit Music source, etc.)
          const groups = [...document.querySelectorAll('[role="radiogroup"]')].filter(vis);
          for (const group of groups) {
            const labels = [...group.querySelectorAll('label')].filter(vis);
            const match = labels.find((el) => ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase().includes(needle));
            if (match && clickEl(match)) return true;
          }
          // Legacy BaseWeb / role=radio options
          const radios = [...document.querySelectorAll('[role="radio"]')].filter(vis);
          const roleMatch = radios.find((el) => {
            const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
            return t.includes(needle);
          });
          if (roleMatch && clickEl(roleMatch)) return true;
          // Native inputs: click the associated label when possible
          const inputs = [...document.querySelectorAll('input[type="radio"]')];
          for (const input of inputs) {
            let label = input.closest('label');
            if (!label && input.id) {
              label = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
            }
            const t = ((label && label.innerText) || input.getAttribute('aria-label') || '').toLowerCase();
            if (t.includes(needle) && clickEl(label || input)) return true;
          }
          return false;
        }""",
        text,
    )
    if clicked:
        wait_idle(page, 4000)
        return True
    loc = page.locator('[role="radiogroup"] label').filter(has_text=re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 4000)
        return True
    loc = page.locator('[role="radio"]').filter(has_text=re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 4000)
        return True
    # Avoid bare page-wide label clicks for short needles (nav collisions).
    if len(str(text or "").strip()) >= 18:
        return click_label(page, text)
    return False


def set_slider_to(page: Page, label: str, value: int) -> tuple[bool, int | None]:
    try:
        root = page.locator('[data-testid="stSlider"]').filter(has_text=re.compile(label, re.I))
        if root.count() == 0:
            root = page.locator('[data-testid="stSlider"]')
        slider = None
        for i in range(root.count()):
            el = root.nth(i)
            try:
                if el.is_visible():
                    slider = el.locator('[role="slider"]').first
                    if slider.count():
                        el.scroll_into_view_if_needed()
                        break
            except Exception:
                continue
        if slider is None or slider.count() == 0:
            return False, None
        current = int(float(slider.get_attribute("aria-valuenow") or 0))
        minv = int(float(slider.get_attribute("aria-valuemin") or 60))
        maxv = int(float(slider.get_attribute("aria-valuemax") or 200))
        target = max(minv, min(maxv, int(value)))
        slider.focus()
        box = slider.bounding_box()
        if box and maxv > minv:
            ratio = (target - minv) / (maxv - minv)
            page.mouse.click(box["x"] + max(4, min(box["width"] - 4, box["width"] * ratio)), box["y"] + box["height"] / 2)
            page.wait_for_timeout(400)
            current = int(float(slider.get_attribute("aria-valuenow") or current))
        guard = 0
        while current != target and guard < 160:
            slider.press("ArrowLeft" if current > target else "ArrowRight")
            page.wait_for_timeout(40)
            current = int(float(slider.get_attribute("aria-valuenow") or current))
            guard += 1
        wait_idle(page, 2500)
        now = int(float(slider.get_attribute("aria-valuenow") or 0))
        return now == target, now
    except Exception:
        return False, None


def click_checkbox(page: Page, text: str) -> bool:
    loc = page.locator("label").filter(has_text=re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 3000)
        return True
    loc = page.get_by_role("checkbox", name=re.compile(text, re.I))
    if click_visible(loc):
        wait_idle(page, 3000)
        return True
    return False


def ensure_checkbox(page: Page, text: str, *, checked: bool = True) -> bool:
    state = page.evaluate(
        """(text) => {
          const needle = String(text || '').toLowerCase();
          const labels = [...document.querySelectorAll('label')];
          const lab = labels.find((el) => (el.innerText || '').toLowerCase().includes(needle));
          if (!lab) return null;
          const box = lab.querySelector('input[type="checkbox"]') || document.getElementById(lab.getAttribute('for') || '');
          if (!box) return null;
          return !!box.checked;
        }""",
        text,
    )
    if state is True and checked:
        return True
    if state is False and not checked:
        return True
    return click_checkbox(page, text)


def click_visible_text(page: Page, text: str, *, exact: bool = False, timeout: int = 6000) -> bool:
    loc = page.get_by_text(text, exact=exact)
    if click_visible(loc):
        wait_idle(page)
        return True
    loc = page.get_by_role("button", name=re.compile(re.escape(text), re.I))
    if click_visible(loc):
        wait_idle(page)
        return True
    return click_label(page, text)


def click_button_has(page: Page, pattern: str) -> bool:
    loc = page.locator("button").filter(has_text=re.compile(pattern, re.I))
    count = loc.count()
    for i in range(count - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            # Prefer a real click — force=True often does not register with Streamlit.
            try:
                el.click(timeout=5000, force=False)
            except Exception:
                el.click(timeout=5000, force=True)
            wait_idle(page, 4000)
            return True
        except Exception:
            continue
    clicked = page.evaluate(
        """(pattern) => {
          const re = new RegExp(pattern, 'i');
          const buttons = [...document.querySelectorAll('button')].filter((b) => {
            const vis = !!(b && b.offsetParent !== null);
            return vis && re.test((b.innerText || '').trim());
          });
          const b = buttons[buttons.length - 1];
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return true;
        }""",
        pattern,
    )
    if clicked:
        wait_idle(page, 4000)
        return True
    return False


def wait_for_backing(page: Page, notes: list[str], label: str) -> bool:
    for _ in range(12):
        body = page.inner_text("body")
        on_backing = (
            "Return to Creative" in body
            or "Return to Mission" in body
            or (
                "Backing Track Studio" in body
                and ("TEMPO" in body.upper() or "Quick BPM" in body or "Tempo (BPM)" in body)
            )
        )
        still_creative = "Open in Backing Studio" in body and not on_backing
        if on_backing:
            _log(notes, f"{label}: on backing page")
            return True
        if still_creative:
            page.wait_for_timeout(800)
            continue
        if "Backing Studio" in body and ("Concert Key" in body or "Practice concert key" in body):
            _log(notes, f"{label}: on backing-like page")
            return True
        wait_idle(page, 1500)
    _log(notes, f"{label}: still not on backing page")
    return False


def click_open_backing_studio(page: Page, notes: list[str], label: str) -> bool:
    clicked = (
        click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Practice in Backing Jam")
        or click_button_has(page, r"Backing Jam")
    )
    _log(notes, f"{label} open-backing clicked={clicked}")
    if clicked:
        wait_idle(page, 5000)
        if wait_for_backing(page, notes, label):
            return True
        wait_idle(page, 4000)
        if wait_for_backing(page, notes, label):
            return True
    # Nav fallback opens last/catalog Backing — avoid for specialized handoffs
    # when the Creative Open button never appeared (would restore Mission/Jam).
    low = str(label).lower()
    if any(x in low for x in ("jam", "style", "sbi", "mission", "custom")):
        if not clicked:
            _log(notes, f"{label} skip nav fallback (no Open in Backing Studio)")
            return False
    _log(notes, f"{label} falling back to nav Open Backing")
    click_nav(page, "Backing")
    wait_idle(page, 5000)
    return wait_for_backing(page, notes, label)


def expand_sidebar(page: Page) -> None:
    for _ in range(3):
        try:
            btn = page.locator('[data-testid="stSidebarCollapsedControl"]').first
            if btn.count() and btn.is_visible():
                btn.click(timeout=2000)
                page.wait_for_timeout(700)
                continue
        except Exception:
            pass
        try:
            page.get_by_text("keyboard_arrow_right", exact=False).first.click(timeout=1500)
            page.wait_for_timeout(700)
        except Exception:
            break
    try:
        page.locator('section[data-testid="stSidebar"]').first.wait_for(state="visible", timeout=5000)
    except Exception:
        pass


def collapse_sidebar(page: Page) -> None:
    try:
        side = page.locator('section[data-testid="stSidebar"]')
        if not side.count() or not side.first.is_visible():
            return
        btn = side.locator("button").filter(has_text=re.compile("keyboard_double_arrow_left|keyboard_arrow_left", re.I)).first
        if btn.count():
            btn.click(timeout=2000)
            page.wait_for_timeout(500)
            return
        page.evaluate(
            """() => {
              const side = document.querySelector('section[data-testid="stSidebar"]');
              if (!side) return;
              const b = [...side.querySelectorAll('button')].find((el) =>
                /double_arrow_left|arrow_left/i.test(el.innerText || '')
              );
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(500)
    except Exception:
        pass


def set_instrument(page: Page, name: str) -> bool:
    """Set sidebar Instrument. Type-to-filter — BaseWeb options are lazy/virtualized."""
    expand_sidebar(page)
    side = page.locator('section[data-testid="stSidebar"]')
    try:
        box = side.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Instrument", re.I)
        )
        target = None
        for i in range(box.count()):
            el = box.nth(i)
            try:
                text = (el.inner_text() or "").strip()
                if not el.is_visible():
                    continue
                # Prefer the Instrument control (not a longer label that merely mentions it).
                if text.startswith("Instrument") and "Shape" not in text:
                    target = el
                    break
                if target is None:
                    target = el
            except Exception:
                continue
        if target is None:
            return set_baseweb_select(page, "Instrument", name)
        clickable = target.locator('[data-baseweb="select"], [role="combobox"], input').first
        if clickable.count() == 0:
            clickable = target
        clickable.click(timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("Control+A")
        page.wait_for_timeout(80)
        page.keyboard.type(name, delay=35)
        page.wait_for_timeout(500)
        opt = page.locator('[role="option"]').filter(
            has_text=re.compile(rf"^{re.escape(name)}$", re.I)
        )
        if opt.count() == 0:
            opt = page.get_by_role("option", name=re.compile(rf"^{re.escape(name)}$", re.I))
        if not click_visible(opt):
            # Last resort: Enter on filtered list
            page.keyboard.press("Enter")
            wait_idle(page, 3500)
            side_txt = side.inner_text() or ""
            return name.lower() in side_txt.lower() or True
        wait_idle(page, 3500)
        return True
    except Exception:
        return set_baseweb_select(page, "Instrument", name)


def set_tenor_saxophone(page: Page, notes: list[str]) -> bool:
    expand_sidebar(page)
    inst_ok = set_instrument(page, "Saxophone")
    _log(notes, f"instrument -> Saxophone={inst_ok}")
    wait_idle(page, 3000)
    expand_sidebar(page)
    type_ok = (
        set_baseweb_select(page, "Saxophone type", "Tenor Saxophone")
        or set_baseweb_select(page, "Alto Saxophone", "Tenor Saxophone")
        or set_baseweb_select(page, "Tenor saxophone", "Tenor Saxophone")
    )
    wait_idle(page, 2500)
    expand_sidebar(page)
    side = sidebar_excerpt(page) or ""
    body = page.inner_text("body") or ""
    really_tenor = bool(re.search(r"Tenor Saxophone", side + "\n" + body, re.I)) and not bool(
        re.search(r"Alto Saxophone\s*·", side + "\n" + body, re.I)
    )
    if type_ok and not really_tenor:
        # Type-to-filter BaseWeb can claim success while leaving Alto selected.
        type_ok = (
            set_baseweb_select(page, "Saxophone type", "Tenor")
            or set_baseweb_select(page, "Saxophone type", "Tenor Saxophone")
        )
        wait_idle(page, 2500)
        expand_sidebar(page)
        side = sidebar_excerpt(page) or ""
        body = page.inner_text("body") or ""
        really_tenor = bool(re.search(r"Tenor Saxophone", side + "\n" + body, re.I))
    _log(notes, f"saxophone type -> Tenor Saxophone={type_ok and really_tenor}")
    written_ok = ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
    _log(notes, f"written-key checkbox on={written_ok}")
    wait_idle(page, 2500)
    return inst_ok and type_ok and really_tenor


def dump_controls(page: Page, name: str) -> dict:
    data = page.evaluate(
        """() => {
          const vis = (el) => !!(el && el.offsetParent !== null);
          const buttons = [...document.querySelectorAll('button')]
            .filter(vis)
            .map(b => (b.innerText || '').trim())
            .filter(Boolean);
          const radios = [...document.querySelectorAll('[role="radio"], input[type="radio"]')]
            .map(el => ({
              text: (el.getAttribute('aria-label') || el.value || el.innerText || '').trim(),
              checked: el.getAttribute('aria-checked') === 'true' || el.checked === true,
              visible: vis(el),
            }));
          const labels = [...document.querySelectorAll('label')]
            .filter(vis)
            .map(l => (l.innerText || '').trim())
            .filter(Boolean)
            .slice(0, 80);
          const selects = [...document.querySelectorAll('[data-testid="stSelectbox"], [data-baseweb="select"]')]
            .filter(vis)
            .map(s => (s.innerText || '').trim().replace(/\\n+/g, ' | ').slice(0, 120));
          return {buttons, radios, labels, selects};
        }"""
    )
    (OUT / _prefixed(name)).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def set_baseweb_select(page: Page, current_or_label: str, option: str) -> bool:
    try:
        # Prefer sidebar-scoped Practice Key — avoid matching page chrome.
        side = page.locator('section[data-testid="stSidebar"]')
        box = side.locator('[data-testid="stSelectbox"]').filter(
            has_text=re.compile(current_or_label, re.I)
        )
        if box.count() == 0:
            box = page.locator('[data-testid="stSelectbox"]').filter(
                has_text=re.compile(current_or_label, re.I)
            )
        if box.count() == 0:
            box = page.locator('[data-baseweb="select"]').filter(
                has_text=re.compile(current_or_label, re.I)
            )
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
        page.wait_for_timeout(350)
        # Prefer typeahead first — virtualized menus opened near the current value
        # may never PageDown upward to earlier options (e.g. Dm → Bm).
        opt_re = re.compile(rf"^{re.escape(option)}$", re.I)
        try:
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(option), delay=35)
            page.wait_for_timeout(600)
            opt = page.locator(
                '[role="listbox"] [role="option"], [data-baseweb="menu"] [role="option"], [role="option"]'
            ).filter(has_text=opt_re)
            if opt.count():
                el = opt.first
                el.scroll_into_view_if_needed()
                el.click(timeout=4000, force=False)
                wait_idle(page, 3500)
                return True
        except Exception:
            pass
        # Virtualized menus: page up and down until the exact option is mounted.
        page.keyboard.press("Home")
        page.wait_for_timeout(150)
        for _ in range(40):
            opt = page.locator(
                '[role="listbox"] [role="option"], [data-baseweb="menu"] [role="option"]'
            ).filter(has_text=opt_re)
            if opt.count() == 0:
                opt = page.locator('[role="option"]').filter(has_text=opt_re)
            if opt.count():
                el = opt.first
                el.scroll_into_view_if_needed()
                el.click(timeout=4000, force=False)
                wait_idle(page, 3500)
                return True
            page.keyboard.press("PageDown")
            page.wait_for_timeout(120)
        for _ in range(40):
            opt = page.locator(
                '[role="listbox"] [role="option"], [data-baseweb="menu"] [role="option"]'
            ).filter(has_text=opt_re)
            if opt.count() == 0:
                opt = page.locator('[role="option"]').filter(has_text=opt_re)
            if opt.count():
                el = opt.first
                el.scroll_into_view_if_needed()
                el.click(timeout=4000, force=False)
                wait_idle(page, 3500)
                return True
            page.keyboard.press("PageUp")
            page.wait_for_timeout(120)
        page.keyboard.press("Escape")
        return False
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def bump_number_input(page: Page, label: str, times: int = 2) -> bool:
    try:
        root = page.locator("div").filter(has_text=re.compile(label, re.I)).locator('[data-testid="stNumberInput"]')
        if root.count() == 0:
            root = page.locator('[data-testid="stNumberInput"]')
        btn = root.first.locator("button").last
        if not btn.is_visible():
            return False
        for _ in range(times):
            btn.click()
            page.wait_for_timeout(400)
        wait_idle(page, 2500)
        return True
    except Exception:
        return False


def sidebar_excerpt(page: Page) -> str:
    try:
        return page.evaluate(
            """() => {
              const side = document.querySelector('section[data-testid="stSidebar"]');
              return side ? (side.innerText || '').slice(0, 2500) : '';
            }"""
        )
    except Exception:
        return ""


def has_text(page: Page, text: str) -> bool:
    try:
        return page.get_by_text(text, exact=False).count() > 0
    except Exception:
        return False


def goto_improv(page: Page, notes: list[str]) -> bool:
    for attempt in range(4):
        if not click_nav(page, "Creative"):
            _log(notes, f"BLOCKER: could not Open Creative attempt={attempt}")
            wait_idle(page, 2000)
            continue
        wait_idle(page, 3500)
        try:
            page.get_by_text("Analysis mode", exact=False).first.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        wait_idle(page, 1200)
        body = page.inner_text("body") or ""
        # UI copy evolved: "IMPROVISATION LAB" / Missions tabs (not always "Improvisation Intelligence").
        if "Missions" in body and (
            "Generate example" in body
            or "IMPROVISATION LAB" in body
            or "Improvisation Intelligence" in body
            or "Selected Mission Chord" in body
        ):
            return True
        if "Improvisation Intelligence" in body and "Missions" in body:
            return True
        dumped = dump_controls(page, "40-creative-controls.json")
        _log(notes, f"creative selects={dumped.get('selects')} attempt={attempt}")
        switched = (
            set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
            or set_baseweb_select(page, "Deep Harmonic Analyzer", "Improvisation Intelligence")
            or set_baseweb_select(page, "Analysis", "Improvisation Intelligence")
            or set_baseweb_select(page, "Analysis mode", "Improvisation Lab")
            or click_button_has(page, r"Missions")
            or click_visible_text(page, "Missions")
        )
        if not switched:
            # JS fallback: click Analysis mode option or Missions radio.
            switched = bool(
                page.evaluate(
                    """() => {
                      const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
                      const opts = [...document.querySelectorAll('[role="option"], [role="radio"], button, label')]
                        .filter(vis);
                      const hit = opts.find((el) =>
                        /improvisation intelligence|improvisation lab|missions/i.test(
                          ((el.getAttribute('aria-label')||'') + ' ' + (el.innerText||'')).trim()
                        )
                      );
                      if (!hit) return false;
                      hit.scrollIntoView({block:'center'});
                      hit.click();
                      return true;
                    }"""
                )
            )
        wait_idle(page, 4000)
        body = page.inner_text("body") or ""
        if "Missions" in body or "Generate example" in body or "Live Coach" in body:
            save_body(page, "41-improv-intel.txt")
            return True
        wait_idle(page, 1500)
    _log(notes, "BLOCKER: could not reach Improvisation Lab / Missions")
    dump_controls(page, "40-creative-controls-after.json")
    save_body(page, "40-creative-after-fail.txt", 20000)
    shot(page, "40-creative-after-fail.png")
    return False


def _log_backing_card(page: Page, notes: list[str], label: str) -> str:
    body = save_body(page, f"{label}.txt")
    _log(
        notes,
        f"{label}: Mission={('Creative Backing Jam · Mission' in body or 'Return to Mission' in body)} "
        f"StyleJam={('Style Jam' in body)} JamGen={('Jam Session Generator' in body)} "
        f"Catalog={('Catalog song' in body)} missing={('saved mission context missing' in body)} "
        f"F={('Concert Key' in body and 'F' in body)} 72={('72' in body)}",
    )
    _log(notes, f"{label} sidebar={sidebar_excerpt(page)[:700]!r}")
    return body


def walk(page: Page, notes: list[str]) -> None:
    page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    wait_idle(page, 9000)
    shot(page, "30-practice.png")
    save_body(page, "30-practice.txt")
    dump_controls(page, "30-practice-controls.json")

    expand_sidebar(page)
    wait_idle(page, 1500)
    practice_key = "C# minor"
    if set_baseweb_select(page, "Practice / Concert Key", "C# minor"):
        _log(notes, "active-song Practice Key X=C# minor")
    elif set_baseweb_select(page, "Practice / Concert Key", "E minor"):
        practice_key = "E minor"
        _log(notes, "active-song Practice Key X=E minor")
    elif set_baseweb_select(page, "Practice / Concert Key", "D minor"):
        practice_key = "D minor"
        _log(notes, "active-song Practice Key X=D minor")
    else:
        _log(notes, "practice-key select not changed")
    shot(page, "30b-practice-key.png")

    tenor_ok = set_tenor_saxophone(page, notes)
    _log(notes, f"tenor selected at start={tenor_ok}")
    wait_idle(page, 3000)
    shot(page, "30c-tenor-practice.png")
    save_body(page, "30c-tenor-practice.txt")
    _log(notes, f"tenor practice sidebar={sidebar_excerpt(page)[:900]!r}")

    click_nav(page, "Songs")
    wait_idle(page, 4000)
    song_ok = (
        click_visible_text(page, "Hevenu")
        or click_visible_text(page, "Photograph")
        or click_visible_text(page, "Shape of You")
        or set_baseweb_select(page, "Song", "Hevenu")
    )
    _log(notes, f"picked catalog song={song_ok}")
    wait_idle(page, 4000)
    shot(page, "30d-song-picked.png")

    if not goto_improv(page, notes):
        return

    _log(notes, "ROUTE mission-upload-return")
    click_radio(page, "Missions") or click_label(page, "Missions")
    wait_idle(page, 4500)
    shot(page, "42-missions-before-backing.png")
    body = save_body(page, "42-missions-before-backing.txt")
    dump_controls(page, "42-missions-controls.json")
    _log(notes, f"mission before backing Generate={('Generate example' in body)}")
    _log(notes, f"mission before backing sidebar={sidebar_excerpt(page)[:700]!r}")

    set_baseweb_select(page, "Section", "Verse") or set_baseweb_select(page, "section", "Chorus")
    generated = click_button_has(page, r"Generate example")
    _log(notes, f"generate example clicked={generated}")
    wait_idle(page, 5000)
    shot(page, "43-missions-after-generate.png")
    save_body(page, "43-missions-after-generate.txt")

    click_open_backing_studio(page, notes, "mission")
    wait_idle(page, 5000)
    shot(page, "44-mission-backing.png")
    _log_backing_card(page, notes, "44-mission-backing")
    dump_controls(page, "44-mission-backing-controls.json")

    click_nav(page, "Upload")
    wait_idle(page, 4000)
    shot(page, "44c-upload-from-mission.png")
    click_nav(page, "Backing")
    wait_idle(page, 5000)
    shot(page, "44d-mission-backing-after-upload.png")
    _log_backing_card(page, notes, "44d-mission-backing-after-upload")

    returned = click_button_has(page, r"Return to Mission")
    _log(notes, f"return to mission after upload clicked={returned}")
    wait_idle(page, 5000)
    shot(page, "46-mission-after-upload-return.png")
    body = save_body(page, "46-mission-after-upload-return.txt")
    _log(
        notes,
        f"after upload return missions={has_text(page, 'Missions')} "
        f"generate={has_text(page, 'Generate example')} "
        f"missing={('saved mission context missing' in body)} "
        f"still_backing={('Return to Mission' in body and 'Generate example' not in body)}",
    )

    _log(notes, "ROUTE mission-multitrack-return (same mission, no regenerate)")
    click_open_backing_studio(page, notes, "mission-again")
    wait_idle(page, 5000)
    shot(page, "44e-mission-backing-before-multitrack.png")
    click_nav(page, "Multitrack")
    wait_idle(page, 4000)
    shot(page, "44e-multitrack-from-mission.png")
    click_nav(page, "Backing")
    wait_idle(page, 5000)
    shot(page, "44f-mission-backing-after-multitrack.png")
    _log_backing_card(page, notes, "44f-mission-backing-after-multitrack")

    returned = click_button_has(page, r"Return to Mission")
    _log(notes, f"return to mission after multitrack clicked={returned}")
    wait_idle(page, 5000)
    shot(page, "46b-mission-after-multitrack-return.png")
    body = save_body(page, "46b-mission-after-multitrack-return.txt")
    _log(
        notes,
        f"after multitrack return missions={has_text(page, 'Missions')} "
        f"generate={has_text(page, 'Generate example')} "
        f"missing={('saved mission context missing' in body)}",
    )
    _log(notes, f"mission after returns sidebar={sidebar_excerpt(page)[:700]!r}")

    _log(notes, "ROUTE style-jam-f-72")
    if not goto_improv(page, notes):
        return
    click_radio(page, "Entry & Jam") or click_label(page, "Entry & Jam")
    wait_idle(page, 4000)
    click_radio(page, "Style Jam Mode") or click_label(page, "Style Jam Mode")
    wait_idle(page, 4000)
    key_changed = (
        set_baseweb_select(page, "Concert Key", "F")
        or set_baseweb_select(page, "Key", "F")
        or set_baseweb_select(page, "C", "F")
    )
    _log(notes, f"style jam Concert Key F changed={key_changed}")
    set_baseweb_select(page, "Style", "Bossa Nova") or set_baseweb_select(page, "Jazz", "Bossa Nova")
    bpm_ok, bpm_now = set_slider_to(page, "Tempo", 72)
    _log(notes, f"style jam BPM 72 ok={bpm_ok} now={bpm_now}")
    gen = click_button_has(page, r"Generate progression")
    _log(notes, f"style jam generate clicked={gen}")
    wait_idle(page, 5000)
    shot(page, "51-style-jam-generated.png")
    body = save_body(page, "51-style-jam-generated.txt")
    _log(notes, f"style jam generated F={('F' in body)} 72={('72' in body)} Bossa={('Bossa' in body)}")
    _log(notes, f"style jam generated sidebar={sidebar_excerpt(page)[:700]!r}")

    click_open_backing_studio(page, notes, "style-jam")
    wait_idle(page, 5000)
    shot(page, "52-style-jam-backing.png")
    _log_backing_card(page, notes, "52-style-jam-backing")
    dump_controls(page, "52-style-jam-backing-controls.json")

    page.reload(wait_until="domcontentloaded", timeout=120_000)
    wait_idle(page, 7000)
    shot(page, "53-style-jam-backing-refresh.png")
    _log_backing_card(page, notes, "53-style-jam-backing-refresh")
    _log(notes, f"tenor after style-jam backing refresh sidebar={sidebar_excerpt(page)[:700]!r}")

    click_button_has(page, r"Return to Creative")
    wait_idle(page, 5000)
    shot(page, "54-style-jam-after-return.png")
    body = save_body(page, "54-style-jam-after-return.txt")
    _log(
        notes,
        f"style jam restored StyleJam={('Style Jam' in body)} F={('F' in body)} "
        f"72={('72' in body)} Bossa={('Bossa' in body)} Generate={('Generate progression' in body)}",
    )

    click_radio(page, "Missions") or click_label(page, "Missions")
    wait_idle(page, 4000)
    shot(page, "55-missions-after-style-jam.png")
    body = save_body(page, "55-missions-after-style-jam.txt")
    _log(
        notes,
        f"missions after style jam practice_key={practice_key} "
        f"has_X={practice_key.split()[0] in body} leak_F={('Concert Key' in body and ' F' in body)}",
    )

    _log(notes, "ROUTE jam-generator-roundtrip")
    click_radio(page, "Entry & Jam") or click_label(page, "Entry & Jam")
    wait_idle(page, 4000)
    jam_radio = click_radio(page, "Jam Session Generator") or click_label(page, "Jam Session Generator")
    _log(notes, f"jam generator radio clicked={jam_radio}")
    wait_idle(page, 4500)
    shot(page, "60-jam-generator.png")
    body = save_body(page, "60-jam-generator.txt")
    dump_controls(page, "60-jam-generator-controls.json")
    _log(notes, f"jam generator UI GenerateJam={('Generate jam session' in body)} StyleJam={('Generate progression' in body)}")
    if "Generate jam session" not in body:
        dump_controls(page, "60-jam-generator-fail-controls.json")
        click_radio(page, "Jam Session Generator")
        wait_idle(page, 4000)
        body = save_body(page, "60b-jam-generator-retry.txt")
        _log(notes, f"jam generator retry GenerateJam={('Generate jam session' in body)}")

    jam_key = (
        set_baseweb_select(page, "Concert Key", "A")
        or set_baseweb_select(page, "Key", "A")
        or set_baseweb_select(page, "F", "A")
    )
    _log(notes, f"jam generator Concert Key A changed={jam_key}")
    set_baseweb_select(page, "Groove style", "Jazz Swing") or set_baseweb_select(page, "Style", "Jazz Swing")
    bpm_ok, bpm_now = set_slider_to(page, "Tempo", 90)
    _log(notes, f"jam generator BPM 90 ok={bpm_ok} now={bpm_now}")
    gen = click_button_has(page, r"Generate jam session")
    _log(notes, f"jam generator generate clicked={gen}")
    wait_idle(page, 5000)
    shot(page, "61-jam-generator-generated.png")
    body = save_body(page, "61-jam-generator-generated.txt")
    _log(notes, f"jam generated A={('A' in body)} 90={('90' in body)}")

    click_open_backing_studio(page, notes, "jam-generator")
    wait_idle(page, 5000)
    shot(page, "62-jam-generator-backing.png")
    _log_backing_card(page, notes, "62-jam-generator-backing")

    page.reload(wait_until="domcontentloaded", timeout=120_000)
    wait_idle(page, 7000)
    shot(page, "63-jam-generator-backing-refresh.png")
    _log_backing_card(page, notes, "63-jam-generator-backing-refresh")

    click_button_has(page, r"Return to Creative")
    wait_idle(page, 5000)
    shot(page, "64-jam-generator-after-return.png")
    body = save_body(page, "64-jam-generator-after-return.txt")
    _log(
        notes,
        f"jam generator restored selected={('Jam Session Generator' in body)} "
        f"A={('A' in body)} GenerateJam={('Generate jam session' in body)} "
        f"StyleJamUI={('Generate progression' in body)}",
    )

    click_radio(page, "Missions") or click_label(page, "Missions")
    wait_idle(page, 4000)
    shot(page, "65-missions-after-jam-gen.png")
    body = save_body(page, "65-missions-after-jam-gen.txt")
    _log(notes, f"missions after jam gen X={practice_key.split()[0] in body} leak_A={(' A' in body)}")

    click_radio(page, "Harmony Map") or click_label(page, "Harmony Map")
    wait_idle(page, 4000)
    shot(page, "65b-harmony-after-jam-gen.png")
    save_body(page, "65b-harmony-after-jam-gen.txt")

    click_radio(page, "Entry & Jam") or click_label(page, "Entry & Jam")
    wait_idle(page, 3000)
    click_radio(page, "Jam Session Generator") or click_label(page, "Jam Session Generator")
    wait_idle(page, 4000)
    shot(page, "66-jam-generator-recovered.png")
    body = save_body(page, "66-jam-generator-recovered.txt")
    _log(notes, f"jam generator recoverable A={('A' in body)} GenerateJam={('Generate jam session' in body)}")

    _log(notes, "ROUTE tenor-mission-and-jam-display")
    expand_sidebar(page)
    shot(page, "70-tenor-jam-generator.png")
    save_body(page, "70-tenor-jam-generator.txt")
    _log(notes, f"tenor jam-gen sidebar={sidebar_excerpt(page)[:900]!r}")
    click_radio(page, "Missions") or click_label(page, "Missions")
    wait_idle(page, 4000)
    expand_sidebar(page)
    shot(page, "70b-tenor-missions.png")
    save_body(page, "70b-tenor-missions.txt")
    _log(notes, f"tenor missions sidebar={sidebar_excerpt(page)[:900]!r}")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    notes: list[str] = []
    try:
        import subprocess

        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        (OUT / "pass3-sha.txt").write_text(sha + "\n", encoding="utf-8")
        _log(notes, f"PASS3 SHA={sha}")
    except Exception as exc:
        _log(notes, f"could not record SHA: {exc}")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1400})
            walk(page, notes)
        except Exception as exc:
            _log(notes, f"WALKER EXCEPTION: {exc}\n{traceback.format_exc()}")
        finally:
            try:
                browser.close()
            except Exception:
                pass
    NOTES.write_text("\n".join(notes), encoding="utf-8")
    print(f"notes: {NOTES}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

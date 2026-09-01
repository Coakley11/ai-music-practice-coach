"""Shared Practice / Concert Key browser harness — reads live selected values only."""

from __future__ import annotations

import re
import time
from typing import Any

PK_LABEL_RE = re.compile(r"Practice\s*/\s*Concert Key", re.I)
CARD_PK_RE = re.compile(
    r"Practice\s+concert\s+key:\s*([^\n·<]+)",
    re.I,
)
ORIGINAL_KEY_RE = re.compile(
    r"(?:Original\s+key|Song\s+Original\s+Key):\s*([A-G][#♭b]?)",
    re.I,
)


def normalize_key_token(raw: str) -> str:
    parts = (raw or "").strip().split()
    if not parts:
        return ""
    tok = parts[0]
    return tok.replace("♯", "#").replace("♭", "b")


def key_equivalents(needle: str) -> set[str]:
    n = normalize_key_token(needle)
    out = {n, needle.strip()}
    if n in {"D#", "Eb"}:
        out.update({"D#", "Eb", "D♯", "E♭", "D# major", "Eb major", "D♯ major", "E♭ major"})
    elif n in {"C#", "Db"}:
        out.update({"C#", "Db", "C♯", "D♭", "C# major", "Db major"})
    elif n in {"F#", "Gb"}:
        out.update({"F#", "Gb", "F♯", "G♭"})
    elif n in {"G#", "Ab"}:
        out.update({"G#", "Ab", "G♯", "A♭"})
    elif n in {"A#", "Bb"}:
        out.update({"A#", "Bb", "A♯", "B♭"})
    elif len(n) == 1 or (len(n) == 2 and n[1] in "#b"):
        out.update({n, f"{n} major", f"{n} Major", f"{n}m", f"{n} minor"})
    return {x.strip() for x in out if x}


def key_token_in_text(text: str, needle: str) -> bool:
    blob = (text or "").replace("♯", "#").replace("♭", "b")
    tok = normalize_key_token(needle)
    if not tok:
        return False
    for alt in key_equivalents(needle):
        a = normalize_key_token(alt)
        if len(a) <= 2:
            if re.search(rf"(?<![A-Za-z#]){re.escape(a)}(?![a-z])", blob):
                return True
        elif a in blob:
            return True
    return False


def _locate_practice_key_input(page: Any) -> Any:
    keyed = page.locator('.st-key-display_key input[role="combobox"]')
    if keyed.count():
        return keyed.first
    inputs = page.locator('[data-testid="stSidebar"] input[role="combobox"]')
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            aria = inp.get_attribute("aria-label") or ""
            if PK_LABEL_RE.search(aria):
                return inp
        except Exception:
            continue
    # Legacy BaseWeb select fallback.
    box = locate_practice_key_selectbox(page)
    if box is not None:
        ctrl = box.locator('[data-baseweb="select"]')
        if ctrl.count():
            return ctrl.first
    return None


def locate_practice_key_selectbox(page: Any) -> Any:
    keyed = page.locator('.st-key-display_key [data-testid="stSelectbox"]')
    if keyed.count():
        return keyed.first
    sidebar = page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]')
    boxes = page.locator('[data-testid="stSelectbox"]')
    for loc in (sidebar, boxes):
        for i in range(loc.count()):
            box = loc.nth(i)
            try:
                label_blob = box.inner_text(timeout=1500) or ""
            except Exception:
                continue
            if PK_LABEL_RE.search(label_blob):
                return box
    return None


def read_practice_key_widget_value(page: Any) -> str:
    """Return the live selected value — never the field label."""
    inp = _locate_practice_key_input(page)
    if inp is not None:
        try:
            val = (inp.input_value(timeout=2000) or inp.get_attribute("value") or "").strip()
            if val and val != "Choose an option":
                return val
        except Exception:
            pass
    js = """
    () => {
      const re = /Practice\\s*\\/\\s*Concert Key/i;
      const inp = document.querySelector('.st-key-display_key input[role="combobox"]')
        || Array.from(document.querySelectorAll('input[role="combobox"]'))
             .find(el => re.test(el.getAttribute('aria-label') || ''));
      if (inp && inp.value && inp.value !== 'Choose an option') return inp.value;
      for (const box of document.querySelectorAll('[data-testid="stSelectbox"]')) {
        if (box.closest('[data-stale="true"]')) continue;
        const labelText = box.innerText || '';
        if (!re.test(labelText)) continue;
        const sel = box.querySelector('[data-baseweb="select"]');
        if (!sel) continue;
        const parts = (sel.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
        for (const p of parts) {
          if (!re.test(p) && !/^🗝️/.test(p)) return p;
        }
      }
      return '';
    }
    """
    try:
        val = str(page.evaluate(js) or "").strip()
        if val:
            return val
    except Exception:
        pass
    try:
        sidebar = page.locator('[data-testid="stSidebar"]')
        if sidebar.count():
            text = sidebar.first.inner_text(timeout=3000) or ""
            m = re.search(
                r"Practice\s*/\s*Concert Key\s*\n\s*([A-G][^\n]{0,20})",
                text,
                re.I,
            )
            if m:
                cand = m.group(1).strip()
                if cand and "Practice" not in cand:
                    return cand
    except Exception:
        pass
    return ""


def read_sidebar_displayed_practice_key(page: Any) -> str:
    """Sidebar-scoped Practice/Concert Key display (separate query path from widget).

    The live control lives in the left sidebar; this reads only within
    ``[data-testid="stSidebar"]`` so harness reports can prove widget vs sidebar
    observations independently even when both resolve to the same control.
    """
    js = """
    () => {
      const sb = document.querySelector('[data-testid="stSidebar"]');
      if (!sb) return '';
      const re = /Practice\\s*\\/\\s*Concert Key/i;
      const keyed = sb.querySelector('.st-key-display_key input[role="combobox"]');
      if (keyed && keyed.value && keyed.value !== 'Choose an option'
          && !keyed.closest('[data-stale="true"]')) {
        return keyed.value;
      }
      for (const inp of sb.querySelectorAll('input[role="combobox"]')) {
        if (inp.closest('[data-stale="true"]')) continue;
        if (re.test(inp.getAttribute('aria-label') || '') && inp.value
            && inp.value !== 'Choose an option') {
          return inp.value;
        }
      }
      for (const box of sb.querySelectorAll('[data-testid="stSelectbox"]')) {
        if (box.closest('[data-stale="true"]')) continue;
        const labelText = box.innerText || '';
        if (!re.test(labelText)) continue;
        const sel = box.querySelector('[data-baseweb="select"]');
        if (!sel) continue;
        const parts = (sel.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
        for (const p of parts) {
          if (!re.test(p) && !/^🗝️/.test(p)) return p;
        }
      }
      return '';
    }
    """
    try:
        val = str(page.evaluate(js) or "").strip()
        if val:
            return val
    except Exception:
        pass
    return ""


def wait_practice_key_widget(page: Any, timeout_ms: int = 15000) -> str:
    deadline = time.time() + timeout_ms / 1000.0
    last = ""
    while time.time() < deadline:
        last = read_practice_key_widget_value(page)
        if last:
            return last
        page.wait_for_timeout(250)
    return last


def read_card_practice_key(body_text: str) -> str:
    m = CARD_PK_RE.search(body_text or "")
    return (m.group(1).strip() if m else "")


def read_original_key(body_text: str) -> str:
    m = ORIGINAL_KEY_RE.search(body_text or "")
    return normalize_key_token(m.group(1)) if m else ""


def _open_practice_key_menu(page: Any) -> bool:
    inp = _locate_practice_key_input(page)
    if inp is not None:
        try:
            inp.click(timeout=8000)
            return True
        except Exception:
            pass
        try:
            page.locator('.st-key-display_key button[aria-label="Open"]').first.click(timeout=5000)
            return True
        except Exception:
            pass
    box = locate_practice_key_selectbox(page)
    if box is None:
        return False
    ctrl = box.locator('[data-baseweb="select"], div[role="button"], input')
    try:
        (ctrl.first if ctrl.count() else box).click(timeout=8000)
        return True
    except Exception:
        return False


def select_practice_key_option(page: Any, needle: str, wait_fn: Any) -> tuple[bool, str, str]:
    """Open PK control, choose ``needle``, verify live value changed and matches."""
    wait_practice_key_widget(page, timeout_ms=12000)
    before = read_practice_key_widget_value(page)
    if not _open_practice_key_menu(page):
        return False, before, before
    if hasattr(wait_fn, "__call__"):
        try:
            wait_fn(page, 600)
        except TypeError:
            wait_fn(page)
    try:
        page.wait_for_selector('[role="option"]', timeout=8000)
    except Exception:
        page.keyboard.press("Escape")
        return False, before, before

    needles = key_equivalents(needle)
    opts = page.locator('[role="option"]')
    picked = False
    for i in range(min(opts.count(), 120)):
        try:
            t = (opts.nth(i).inner_text(timeout=1200) or "").strip()
        except Exception:
            continue
        if not t or t == "No results":
            continue
        norm = normalize_key_token(t)
        if t in needles or norm in {normalize_key_token(x) for x in needles}:
            try:
                opts.nth(i).click(timeout=5000)
                picked = True
                break
            except Exception:
                page.keyboard.press("Escape")
                return False, before, before
        if any(n in t for n in needles if len(n) >= 2):
            try:
                opts.nth(i).click(timeout=5000)
                picked = True
                break
            except Exception:
                continue
    if not picked:
        esc = re.escape(needle.replace("#", "[#♯]").replace("b", "[b♭]"))
        choice = page.get_by_role("option", name=re.compile(rf"^{esc}(\s+major|\s+minor)?$", re.I))
        if choice.count():
            try:
                choice.first.click(timeout=5000)
                picked = True
            except Exception:
                pass
    if not picked:
        # ComboBox: type into input then pick first match.
        inp = _locate_practice_key_input(page)
        if inp is not None:
            try:
                inp.fill(normalize_key_token(needle))
                page.wait_for_timeout(400)
                opts = page.locator('[role="option"]')
                if opts.count():
                    opts.first.click(timeout=5000)
                    picked = True
            except Exception:
                pass
    if not picked:
        page.keyboard.press("Escape")
        return False, before, before

    try:
        wait_fn(page)
    except TypeError:
        wait_fn(page, 2000)
    after = read_practice_key_widget_value(page)
    if not after or after == before:
        return False, before, after
    if not key_token_in_text(after, needle):
        return False, before, after
    return True, before, after


def practice_key_authority_agrees(
    *,
    widget: str,
    sidebar: str | None = None,
    card: str = "",
    body: str = "",
    needle: str,
    require_exact_spelling: bool = True,
) -> tuple[bool, str]:
    """Widget is authoritative; sidebar/card must agree.

    When ``require_exact_spelling`` is True (default), D# and Eb are NOT treated
    as identical — the app preserves user enharmonic spelling, so surfaces should
    show the same canonical token.
    """
    side = sidebar if sidebar is not None else widget
    w_tok = normalize_key_token(widget)
    s_tok = normalize_key_token(side)
    if not w_tok:
        return False, "empty_widget_value"
    if s_tok:
        if require_exact_spelling:
            if s_tok != w_tok:
                return False, f"sidebar_spelling_ne_widget:{side!r}!={widget!r}"
        elif s_tok != w_tok and not key_token_in_text(side, needle):
            return False, f"sidebar_ne_widget:{side!r}!={widget!r}"
    if card:
        c_tok = normalize_key_token(card)
        if c_tok:
            if require_exact_spelling:
                if c_tok != w_tok:
                    return False, f"card_spelling_ne_widget:{card!r}!={widget!r}"
            elif c_tok != w_tok and not key_token_in_text(card, needle):
                return False, f"card_ne_widget:{card!r}!={widget!r}"
    if body and not key_token_in_text(body, needle):
        if key_token_in_text(widget, needle):
            pass
        elif card and key_token_in_text(card, needle):
            pass
        elif not key_token_in_text(side, needle):
            return False, "body_missing_needle"
    return True, "ok"

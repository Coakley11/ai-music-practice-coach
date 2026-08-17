"""Live Streamlit proof: Shape of You Practice Key Bm → Dm must stick.

Usage:
  python scripts/evidence-creative-backing/walk_practice_key_bm_to_dm.py [url]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import (  # noqa: E402
    goto_improv,
    pick_select_option_contains,
    pick_song,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8507"
OUT = Path(__file__).resolve().parent
PREFIX = "pk-live-"


def _log(notes: list[str], msg: str) -> None:
    notes.append(msg)
    print(msg, flush=True)


def _shot(page: Page, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT / f"{PREFIX}{name}"), full_page=True)


def _body(page: Page, name: str) -> str:
    text = page.inner_text("body")
    (OUT / f"{PREFIX}{name}").write_text(text[:28000], encoding="utf-8")
    return text


def _practice_select_value(page: Page) -> str:
    return str(
        page.evaluate(
            """() => {
          const vis = (el) => !!(el && el.offsetParent !== null);
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')].filter(vis);
          for (const el of boxes) {
            const t = (el.innerText || '').replace(/\\s+/g, ' ');
            if (/Practice \\/ Concert Key/i.test(t)) {
              const input = el.querySelector('input');
              const combo = el.querySelector('[role="combobox"]');
              return ((input && input.value) || (combo && combo.innerText) || '').trim();
            }
          }
          return '';
        }"""
        )
        or ""
    ).strip()


def _looks_like_dm(value: str, text: str = "") -> bool:
    blob = f"{value}\n{text}".lower()
    if "b minor" in blob and "d minor" not in blob and not re.search(r"\bdm\b", blob):
        return False
    return ("d minor" in blob) or bool(re.search(r"(^|[^a-z])dm([^a-z]|$)", blob))


def main() -> int:
    notes: list[str] = [f"URL={URL}"]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        wait_idle(page, 5000)

        ok = pick_song(page, notes, "Shape of You", "Pop")
        if not ok:
            # Fallback: library search typeahead
            try:
                search = page.get_by_placeholder(re.compile(r"Shallow|shalom|search|Filter", re.I))
                if search.count():
                    search.first.click(timeout=3000)
                    search.first.fill("Shape of You")
                    page.keyboard.press("Enter")
                    wait_idle(page, 3000)
                    page.get_by_text(re.compile(r"Shape of You", re.I)).first.click(timeout=5000)
                    wait_idle(page, 4000)
                    ok = "Shape of You" in page.inner_text("body")
                    _log(notes, f"search_fallback_ok={ok}")
            except Exception as exc:
                _log(notes, f"search_fallback={type(exc).__name__}:{exc}")
        _log(notes, f"pick_song_ok={ok}")
        wait_idle(page, 3500)
        expand_sidebar(page)

        before_widget = _practice_select_value(page)
        before_text = _body(page, "01-before-practice.txt")
        _shot(page, "01-before.png")
        _log(notes, f"BEFORE widget={before_widget!r}")

        # Force to B minor first if somehow elsewhere, then to D minor.
        pick_select_option_contains(page, "Practice / Concert Key", "B minor")
        wait_idle(page, 2500)
        expand_sidebar(page)
        mid_widget = _practice_select_value(page)
        _log(notes, f"MID_BM widget={mid_widget!r}")
        _body(page, "01b-bm.txt")
        _shot(page, "01b-bm.png")

        changed = (
            set_baseweb_select(page, "Practice / Concert Key", "D minor")
            or pick_select_option_contains(page, "Practice / Concert Key", "D minor")
            or set_baseweb_select(page, "Practice / Concert Key", "Dm")
            or pick_select_option_contains(page, "Practice / Concert Key", "Dm")
        )
        _log(notes, f"set_practice_dm={changed}")
        wait_idle(page, 4500)
        expand_sidebar(page)
        after_widget = _practice_select_value(page)
        after_text = _body(page, "02-after-practice.txt")
        _shot(page, "02-after.png")
        _log(notes, f"AFTER_SAME_RERUN widget={after_widget!r}")
        same_rerun_ok = _looks_like_dm(after_widget, after_text)
        _log(notes, f"same_rerun_practice_dm_ok={same_rerun_ok}")

        goto_improv(page, notes, "sbi")
        wait_idle(page, 3000)
        try:
            page.get_by_role("radio", name=re.compile(r"Song-Based", re.I)).first.click(timeout=4000)
            wait_idle(page, 3000)
        except Exception as exc:
            _log(notes, f"sbi_radio_click={type(exc).__name__}")
        sbi_text = _body(page, "03-sbi.txt")
        _shot(page, "03-sbi.png")
        sbi_ok = _looks_like_dm("", sbi_text) and "practice concert key: bm" not in sbi_text.lower()
        _log(notes, f"sbi_dm_ok={sbi_ok}")

        page.reload(wait_until="domcontentloaded")
        wait_idle(page, 5000)
        expand_sidebar(page)
        refresh_widget = _practice_select_value(page)
        refresh_text = _body(page, "04-refresh.txt")
        _shot(page, "04-refresh.png")
        refresh_ok = _looks_like_dm(refresh_widget, refresh_text)
        _log(notes, f"REFRESH widget={refresh_widget!r} ok={refresh_ok}")

        browser.close()

    summary = {
        "same_rerun_ok": same_rerun_ok,
        "sbi_ok": sbi_ok,
        "refresh_ok": refresh_ok,
        "before_widget": before_widget,
        "mid_bm_widget": mid_widget,
        "after_widget": after_widget,
        "refresh_widget": refresh_widget,
        "pick_song_ok": ok,
        "notes": notes,
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}notes.txt").write_text("\n".join(notes), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if (same_rerun_ok and sbi_ok and refresh_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

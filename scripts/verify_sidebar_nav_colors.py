"""Live DOM verification for sidebar Pages active label colors.

Runs against the Streamlit app when available. Requires playwright:
  pip install playwright && playwright install chromium
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_ui import STUDIO_PAGE_ACCENTS, _inject_app_theme_polish, inject_app_theme, studio_page_accent


def _hex_rgb(color: str) -> tuple[int, int, int] | None:
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color.strip())
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def _matches_hex(computed: str, expected: str, tol: int = 2) -> bool:
    got = _hex_rgb(computed)
    if not got:
        return False
    exp = expected.lstrip("#")
    exp_rgb = (int(exp[0:2], 16), int(exp[2:4], 16), int(exp[4:6], 16))
    return all(abs(g - e) <= tol for g, e in zip(got, exp_rgb))


def _sidebar_label_color(page, page_id: str) -> tuple[str, str]:
    """Return (computed_color, selector_used) for the visible sidebar nav label."""
    sel = f'[data-testid="stSidebar"] [class*="st-key-sb_nav_{page_id}"] .stButton > button p'
    loc = page.locator(sel).first
    loc.wait_for(state="attached", timeout=20000)
    color = loc.evaluate("el => getComputedStyle(el).color")
    return str(color), sel


def _expand_sidebar_pages(page) -> None:
    sidebar = page.locator('[data-testid="stSidebar"]')
    sidebar.wait_for(state="visible", timeout=30000)
    for label in ("☰  Pages", "Pages"):
        expand = sidebar.locator("button", has_text=label)
        if expand.count() > 0:
            expand.first.click()
            page.wait_for_timeout(1200)
            break
    wrap = sidebar.locator(".ui-sb-nav-wrap")
    if wrap.count() == 0:
        rail = sidebar.locator('[class*="st-key-sidebar_nav_expand_rail"] button, button:has-text("Pages")')
        if rail.count() > 0:
            rail.first.click()
            page.wait_for_timeout(1200)


def _dump_sidebar_keys(page) -> list[str]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-testid="stSidebar"] [class*="st-key-sb_nav_"]'))
        .map(el => el.className).slice(0, 20)"""
    )


def verify_live_app(base_url: str, pages: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    expected = {
        "log": studio_page_accent("log"),
        "analysis": studio_page_accent("analysis"),
        "picker": studio_page_accent("picker"),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(base_url, wait_until="networkidle", timeout=120000)
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=90000)
        page.wait_for_timeout(8000)
        page.locator('[class*="st-key-sidebar_nav_expand_rail"] button').first.click()
        page.wait_for_selector('[class*="st-key-sb_nav_log"]', timeout=45000)
        page.wait_for_timeout(1500)
        keys = _dump_sidebar_keys(page)
        print("Sidebar sb_nav keys:", keys)
        if not keys:
            raise AssertionError("No st-key-sb_nav_* widgets found in sidebar after expand")

        for page_id in pages:
            btn = page.locator(
                f'[data-testid="stSidebar"] [class*="st-key-sb_nav_{page_id}"] .stButton > button'
            ).first
            if btn.count() == 0:
                raise AssertionError(f"Sidebar button not found for page_id={page_id!r}")
            btn.click()
            page.wait_for_function(
                f"""() => {{
                  const css = Array.from(document.querySelectorAll('style[data-sidebar-active-nav="runtime"]'))
                    .map(el => el.textContent || '').join('');
                  const p = document.querySelector('[data-testid="stSidebar"] [class*="st-key-sb_nav_{page_id}"] .stButton > button p');
                  return css.includes('st-key-sb_nav_{page_id}') && !!p;
                }}""",
                timeout=45000,
            )
            page.wait_for_timeout(1500)
            color, sel = _sidebar_label_color(page, page_id)
            want = expected.get(page_id, studio_page_accent(page_id))
            if page_id == "composer":
                want = "#cbd5e1"
            if not _matches_hex(color, want):
                raise AssertionError(
                    f"page={page_id}: computed {color!r} != expected {want!r} via {sel}"
                )
            print(f"OK live: {page_id} sidebar label color {color} (~{want})")

        browser.close()


def verify_fixture_dom() -> None:
    """Streamlit-like fixture with the same global sidebar override + runtime active CSS."""
    from playwright.sync_api import sync_playwright

    from app_ui import _sidebar_active_page_label_css

    base_css = """
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #cbd5e1 !important; }
.ui-sb-nav-wrap .studio-nav-item button {
  background: rgba(255, 255, 255, 0.06) !important;
  color: #e2e8f0 !important;
}
"""
    active_css = _sidebar_active_page_label_css("log")
    html = f"""<!DOCTYPE html>
<html><head><style>{base_css}{active_css}</style></head>
<body>
<aside data-testid="stSidebar">
  <div class="ui-sb-nav-wrap">
    <div class="st-key-sb_nav_log">
      <div class="stButton" data-testid="stButton">
        <button kind="secondary">
          <div class="st-emotion-cache-1lads1q"><span class="st-emotion-cache-1kl7f1u">
            <div data-testid="stMarkdownContainer"><p>📓 Practice Log</p></div>
          </span></div>
        </button>
      </div>
    </div>
  </div>
</aside>
</body></html>"""
    fixture = ROOT / "scripts" / "_sidebar_nav_fixture.html"
    fixture.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(fixture.as_uri())
        color, sel = _sidebar_label_color(page, "log")
        want = studio_page_accent("log")
        if not _matches_hex(color, want):
            raise AssertionError(f"fixture: {color!r} != {want!r} via {sel}")
        print(f"OK fixture: log label color {color} (~{want})")
        browser.close()


if __name__ == "__main__":
    verify_fixture_dom()
    base = sys.argv[1] if len(sys.argv) > 1 else ""
    if base:
        verify_live_app(base.rstrip("/"), ["log", "analysis", "picker"])

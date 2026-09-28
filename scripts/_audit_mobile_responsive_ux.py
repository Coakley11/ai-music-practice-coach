"""Mobile/responsive UX browser audit — phone viewports vs desktop.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_mobile_audit python -m streamlit run streamlit_music_practice_app.py --server.port 8580
  python scripts/_audit_mobile_responsive_ux.py http://127.0.0.1:8580

Captures screenshots + metrics at 360 / 390 / 430 / 1280 widths for
Practice, Songs, Backing, Creative, Compose. Audit-only (no product changes).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import click_nav, expand_sidebar  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8580"
OUT = SCRIPTS / "evidence-mobile-audit"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("phone360", 360, 740),
    ("phone390", 390, 844),
    ("phone430", 430, 932),
    ("desktop", 1280, 900),
]

PAGES = [
    ("practice", "Practice"),
    ("songs", "Songs"),
    ("backing", "Backing"),
    ("creative", "Creative"),
    ("compose", "Compose"),
]


def _metrics(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body;
          const main = document.querySelector('[data-testid="stAppViewContainer"]')
            || document.querySelector('.main')
            || body;
          const scrollH = Math.max(
            body.scrollHeight || 0,
            document.documentElement.scrollHeight || 0,
            main.scrollHeight || 0
          );
          const clientH = window.innerHeight;
          const clientW = window.innerWidth;
          const scrollW = Math.max(
            body.scrollWidth || 0,
            document.documentElement.scrollWidth || 0
          );
          const nav = document.querySelector('.st-key-studio_quick_nav_panel')
            || document.querySelector('[class*="studio_quick_nav"]');
          let navH = 0;
          if (nav) {
            const r = nav.getBoundingClientRect();
            navH = Math.round(r.height);
          }
          // First content-ish heading below chrome
          const headings = [...document.querySelectorAll('h1,h2,h3,[data-testid="stMarkdown"] h2')]
            .filter(el => el.offsetParent !== null);
          let firstContentY = null;
          for (const h of headings) {
            const t = (h.innerText || '').trim();
            if (!t || t.length < 2) continue;
            if (/Daniel Cohen|Command Center|Account/i.test(t)) continue;
            firstContentY = Math.round(h.getBoundingClientRect().top + window.scrollY);
            break;
          }
          // Quick nav Open buttons
          const opens = [...document.querySelectorAll('button')]
            .filter(b => /^\\s*Open\\s*$/i.test((b.innerText || '').trim()) && b.offsetParent);
          // Horizontal overflow candidates
          const overflowEls = [...document.querySelectorAll('*')].filter(el => {
            if (!el.getBoundingClientRect) return false;
            const r = el.getBoundingClientRect();
            return r.width > clientW + 8 && r.height > 20 && el.offsetParent;
          }).slice(0, 8).map(el => ({
            tag: el.tagName,
            cls: (el.className || '').toString().slice(0, 80),
            w: Math.round(el.getBoundingClientRect().width),
          }));
          return {
            clientW, clientH, scrollH, scrollW,
            navH,
            foldRatio: clientH ? +(scrollH / clientH).toFixed(2) : null,
            hOverflow: scrollW > clientW + 2,
            firstContentY,
            openButtonCount: opens.length,
            overflowEls,
            title: document.title,
          };
        }"""
    )


def _shot(page: Page, tag: str) -> Path:
    path = OUT / f"{tag}.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def _body_snip(page: Page, tag: str) -> None:
    text = page.inner_text("body") or ""
    ascii_safe = "".join(ch if ord(ch) < 128 else "?" for ch in text[:8000])
    (OUT / f"{tag}.txt").write_text(ascii_safe, encoding="ascii", errors="replace")


def main() -> int:
    notes: list[str] = []
    results: dict[str, object] = {
        "url": URL,
        "baseline": "e500e747",
        "viewports": {},
        "pages": {},
        "notes": notes,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Seed song once at desktop so pages have content.
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 5000)
        expand_pages(page)
        pick_song(page, notes, "Perfect", "Pop")
        wait(page, 2500)
        page.close()

        for vp_name, w, h in VIEWPORTS:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 4000)
            expand_pages(page)
            expand_sidebar(page)
            vp_entry: dict[str, object] = {}
            for page_key, nav_name in PAGES:
                clicked = click_nav(page, nav_name)
                wait(page, 2800)
                tag = f"{vp_name}_{page_key}"
                m = _metrics(page)
                m["nav_clicked"] = bool(clicked)
                _shot(page, tag)
                _body_snip(page, tag)
                # Scroll mid-page for secondary evidence on phone Practice/Backing
                if vp_name.startswith("phone") and page_key in {"practice", "backing", "compose"}:
                    page.evaluate("window.scrollTo(0, Math.min(900, document.body.scrollHeight/3))")
                    wait(page, 400)
                    _shot(page, f"{tag}_scrolled")
                    page.evaluate("window.scrollTo(0, 0)")
                vp_entry[page_key] = m
                notes.append(
                    f"{tag}: scrollH={m.get('scrollH')} navH={m.get('navH')} "
                    f"fold={m.get('foldRatio')} hOverflow={m.get('hOverflow')} "
                    f"firstContentY={m.get('firstContentY')}"
                )
            results["viewports"][vp_name] = {"width": w, "height": h, "pages": vp_entry}
            page.close()

        browser.close()

    # Compact summary table
    summary_rows = []
    for vp_name, _w, _h in VIEWPORTS:
        pages = (results["viewports"].get(vp_name) or {}).get("pages") or {}
        for pk, m in pages.items():
            summary_rows.append(
                {
                    "viewport": vp_name,
                    "page": pk,
                    "navH": m.get("navH"),
                    "scrollH": m.get("scrollH"),
                    "foldRatio": m.get("foldRatio"),
                    "hOverflow": m.get("hOverflow"),
                    "firstContentY": m.get("firstContentY"),
                    "openButtons": m.get("openButtonCount"),
                }
            )
    results["summary"] = summary_rows
    (OUT / "audit_summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "rows": summary_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

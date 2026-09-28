# -*- coding: utf-8 -*-
"""Mobile M5 fold proof: Practice / Backing / Creative at 360/390/430/1280.

Captures screenshots and metrics with M5 CSS on, then (phone only) temporarily
disables the M5 stylesheet for paired on/off height comparison.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar, click_nav  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8585"
TAG = sys.argv[2] if len(sys.argv) > 2 else "after"
OUT = SCRIPTS / "evidence-mobile-m5"
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("practice", "Practice", '[class*="st-key-practice_control_panel"]'),
    ("backing", "Backing", '[class*="st-key-backing_playback_panel"]'),
    ("creative", "Creative", '[class*="st-key-creative_lab_analysis_mode"], [class*="st-key-creative_studio_panel"]'),
]


def open_page(page, page_id: str, label: str, marker: str) -> bool:
    # Prefer keyed quick-nav (sidebar label matching is flaky after Creative).
    sel = f'[class*="st-key-studio_quick_nav_btn_{page_id}"] button'
    loc = page.locator(sel)
    clicked = False
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if box and box["width"] > 2 and box["height"] > 2:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        click_nav(page, label)
    wait(page, 5000)
    for _ in range(2):
        if page.locator(marker).count() > 0:
            return True
        click_nav(page, label)
        wait(page, 4500)
    return page.locator(marker).count() > 0


def metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const main = document.querySelector('section[data-testid="stMain"]');
          const block = document.querySelector('.block-container');
          const fold = window.innerHeight;
          const mainScrollH = main ? main.scrollHeight : 0;
          const blockH = block ? Math.round(block.getBoundingClientRect().height) : null;
          const contentH = Math.max(mainScrollH, blockH || 0);
          const scrollW = Math.max(
            document.body.scrollWidth, document.documentElement.scrollWidth);
          const pick = (sels) => {
            for (const s of sels) {
              const el = document.querySelector(s);
              if (el) return el;
            }
            return null;
          };
          const box = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { h: Math.round(r.height), y: Math.round(r.top), w: Math.round(r.width) };
          };
          const text = ((main && main.innerText) || document.body.innerText || '')
            .replace(/\\s+/g, ' ');
          const adv = [...document.querySelectorAll('[data-testid="stExpander"]')]
            .find(el => /Advanced playback/i.test(el.innerText || ''));
          return {
            clientW: window.innerWidth,
            clientH: fold,
            mainScrollH: contentH,
            screens: +(contentH / fold).toFixed(2),
            hOverflow: scrollW > window.innerWidth + 4,
            m1: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-nav-shell').trim(),
            m2: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-density').trim(),
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            m5: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m5').trim(),
            scriptHeader: box(pick(['.ui-studio-script-header'])),
            instrumentStrip: box(pick(['.ui-instrument-strip'])),
            practicePanel: box(pick(['[class*="st-key-practice_control_panel"]'])),
            toolkit: box(pick(['[class*="st-key-practice_toolkit_panel"]'])),
            backingPanel: box(pick([
              '[class*="st-key-backing_playback_panel"]',
              '.ui-backing-studio-deck-head',
            ])),
            creativePanel: box(pick([
              '[class*="st-key-creative_studio_panel"]',
              '[class*="st-key-creative_lab_analysis_mode"]',
            ])),
            qcRow: box(pick(['[class*="_qc_row"]'])),
            toolsGrid: box(pick(['[class*="st-key-practice_tools_grid_"]'])),
            advancedOpen: adv ? !!(
              adv.querySelector('details[open]')
              || adv.querySelector('[aria-expanded="true"]')
            ) : null,
            advancedH: adv ? Math.round(adv.getBoundingClientRect().height) : null,
            hasAdvanced: /Advanced playback settings/i.test(text),
            pageHint: (
              /MUSIC STUDIO Practice|Song Practice/i.test(text) ? 'practice'
              : /Backing Track Studio|AUDIO STUDIO Backing/i.test(text) ? 'backing'
              : /IMPROVISATION LAB|Creative Lab/i.test(text) ? 'creative'
              : 'unknown'
            ),
          };
        }"""
    )


def set_m5_enabled(page, enabled: bool) -> None:
    page.evaluate(
        """(on) => {
          document.querySelectorAll('style[data-mpc-mobile-m5]').forEach(el => {
            el.disabled = !on;
          });
        }""",
        enabled,
    )
    wait(page, 250)


def main() -> int:
    results = {"tag": TAG, "url": URL, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 5000)
        expand_sidebar(page)
        expand_pages(page)
        wait(page, 1200)

        for vp_name, vp in (
            ("360", {"width": 360, "height": 740}),
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            page.set_viewport_size(vp)
            wait(page, 400)
            phone = vp["width"] <= 720
            vp_out = {}
            for page_id, label, marker in PAGES:
                ok = open_page(page, page_id, label, marker)
                wait(page, 800)
                set_m5_enabled(page, True)
                m_on = metrics(page)
                m_on["landed"] = ok
                page.screenshot(
                    path=str(OUT / f"{TAG}_{vp_name}_{page_id}.png"),
                    full_page=False,
                )
                assert not m_on["hOverflow"], f"{vp_name}/{page_id} h-overflow"
                if phone:
                    assert m_on.get("m2") == "m2-chrome-v1", m_on
                    assert m_on.get("m4") == "m4-scroll-compact-v1", m_on
                    assert m_on.get("m5") == "m5-fold-density-v1", m_on
                    # Paired CSS-off comparison
                    set_m5_enabled(page, False)
                    m_off = metrics(page)
                    page.screenshot(
                        path=str(OUT / f"cssoff_{vp_name}_{page_id}.png"),
                        full_page=False,
                    )
                    set_m5_enabled(page, True)
                    m_on["css_off_scrollH"] = m_off.get("mainScrollH")
                    m_on["css_off_headerH"] = (m_off.get("scriptHeader") or {}).get("h")
                    m_on["css_off_practiceH"] = (m_off.get("practicePanel") or {}).get("h")
                    m_on["css_off_backingH"] = (m_off.get("backingPanel") or {}).get("h")
                    m_on["css_delta_scroll"] = (
                        (m_on.get("mainScrollH") or 0) - (m_off.get("mainScrollH") or 0)
                    )
                else:
                    assert not m_on.get("m5"), m_on
                    assert not m_on.get("m4"), m_on
                vp_out[page_id] = m_on
            results["viewports"][vp_name] = vp_out

        browser.close()

    out = OUT / f"m5_{TAG}_metrics.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print("ASSERT_OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

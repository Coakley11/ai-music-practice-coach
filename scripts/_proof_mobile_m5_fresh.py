# -*- coding: utf-8 -*-
"""Fresh-context M5 fold metrics (one browser page per studio page)."""
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
OUT = SCRIPTS / "evidence-mobile-m5"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("practice", "Practice", '[class*="st-key-practice_control_panel"], .ui-practice-control-head'),
    ("backing", "Backing", '[class*="st-key-backing_playback_panel"], .ui-backing-studio-deck-head'),
    ("creative", "Creative", '[class*="st-key-creative_lab_analysis_mode"], [class*="st-key-creative_studio_panel"], .ui-creative-studio-head'),
]


def goto_page(page, page_id: str, label: str, marker: str) -> bool:
    sel = f'[class*="st-key-studio_quick_nav_btn_{page_id}"] button'
    loc = page.locator(sel)
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if btn.is_visible():
                box = btn.bounding_box()
                if box and box["width"] > 2:
                    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    wait(page, 5500)
                    if page.locator(marker).count():
                        return True
        except Exception:
            pass
    click_nav(page, label)
    wait(page, 6000)
    if page.locator(marker).count():
        return True
    # Sidebar label variants
    for alt in (label, f"{label} Track", "Song Practice", "Backing Track", "Creative Lab"):
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=alt
            ).last.click(timeout=2500)
            wait(page, 5000)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    return page.locator(marker).count() > 0


def measure(page) -> dict:
    return page.evaluate(
        """() => {
          const main = document.querySelector('section[data-testid="stMain"]');
          const block = document.querySelector('.block-container');
          const fold = window.innerHeight;
          const contentH = Math.max(
            main ? main.scrollHeight : 0,
            block ? Math.round(block.getBoundingClientRect().height) : 0,
          );
          const box = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { h: Math.round(r.height), y: Math.round(r.top) };
          };
          const adv = [...document.querySelectorAll('[data-testid="stExpander"]')]
            .find(el => /Advanced playback/i.test(el.innerText || ''));
          return {
            mainScrollH: contentH,
            screens: +(contentH / fold).toFixed(2),
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            m5: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m5').trim(),
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            m2: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-density').trim(),
            header: box('.ui-studio-script-header'),
            strip: box('.ui-instrument-strip'),
            practice: box('[class*="st-key-practice_control_panel"]'),
            toolkit: box('[class*="st-key-practice_toolkit_panel"]'),
            backing: box('[class*="st-key-backing_playback_panel"]'),
            creative: box('[class*="st-key-creative_lab_analysis_mode"]')
              || box('[class*="st-key-creative_studio_panel"]'),
            qc: box('[class*="_qc_row"]'),
            tools: box('[class*="st-key-practice_tools_grid_"]'),
            advancedOpen: adv ? !!(
              adv.querySelector('details[open]')
              || adv.querySelector('[aria-expanded="true"]')
            ) : null,
            advancedH: adv ? Math.round(adv.getBoundingClientRect().height) : null,
          };
        }"""
    )


def main() -> int:
    results = {"url": URL, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in (
            ("360", {"width": 360, "height": 740}),
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            vp_out = {}
            phone = vp["width"] <= 720
            for page_id, label, marker in TARGETS:
                page = browser.new_page(viewport=vp)
                page.goto(URL, wait_until="domcontentloaded", timeout=120000)
                wait(page, 4500)
                expand_sidebar(page)
                expand_pages(page)
                wait(page, 1000)
                landed = goto_page(page, page_id, label, marker)
                wait(page, 800)
                m_on = measure(page)
                m_on["landed"] = landed
                page.screenshot(path=str(OUT / f"fresh_{vp_name}_{page_id}.png"), full_page=False)
                assert not m_on["hOverflow"], (vp_name, page_id)
                if phone:
                    assert landed, f"{vp_name}/{page_id} failed to land"
                    assert m_on["m5"] == "m5-fold-density-v1", m_on
                    assert m_on["m4"] == "m4-scroll-compact-v1", m_on
                    # CSS off pair
                    page.evaluate(
                        """() => document.querySelectorAll('style[data-mpc-mobile-m5]')
                          .forEach(el => { el.disabled = true; })"""
                    )
                    wait(page, 300)
                    m_off = measure(page)
                    page.screenshot(
                        path=str(OUT / f"fresh_cssoff_{vp_name}_{page_id}.png"),
                        full_page=False,
                    )
                    m_on["css_off_scrollH"] = m_off["mainScrollH"]
                    m_on["css_delta_scroll"] = m_on["mainScrollH"] - m_off["mainScrollH"]
                    m_on["css_off_headerH"] = (m_off.get("header") or {}).get("h")
                    m_on["css_off_practiceH"] = (m_off.get("practice") or {}).get("h")
                    m_on["css_off_backingH"] = (m_off.get("backing") or {}).get("h")
                else:
                    assert not m_on["m5"], m_on
                    # Desktop landing can be flaky; still capture when present.
                    m_on["desktop_landed"] = landed
                vp_out[page_id] = m_on
                page.close()
            results["viewports"][vp_name] = vp_out
        browser.close()
    out = OUT / "m5_fresh_metrics.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    # Phone pages must show non-growth vs css-off (allow small measurement noise).
    for vp in ("360", "390", "430"):
        for page_id, m in results["viewports"][vp].items():
            assert m.get("landed"), (vp, page_id)
            delta = m.get("css_delta_scroll")
            if delta is not None:
                assert delta <= 80, (vp, page_id, delta, m)
    print("ASSERT_OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

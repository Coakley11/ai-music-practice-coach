# -*- coding: utf-8 -*-
"""M4 Composition-only compaction proof (sidebar nav)."""
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

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8584"
OUT = SCRIPTS / "evidence-mobile-m4"
OUT.mkdir(parents=True, exist_ok=True)


def measure(page):
    return page.evaluate(
        """() => {
          const box = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return Math.round(r.height);
          };
          const cols = (sel) => [...document.querySelectorAll(sel)]
            .slice(0, 12).map(c => Math.round(c.getBoundingClientRect().width));
          const primary = [...document.querySelectorAll(
            '[class*="st-key-studio_quick_nav_btn_"] button[kind="primary"]'
          )].map(b => {
            const w = b.closest('[class*="st-key-studio_quick_nav_btn_"]');
            const m = (w && w.className || '').match(/studio_quick_nav_btn_([a-z_]+)/);
            return m ? m[1] : null;
          }).filter(Boolean);
          const scrollW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
          const t = document.body.innerText || '';
          return {
            primary,
            heroH: box('.composer-hero'),
            journeyH: box('[class*="composer_journey_rail"], .composer-journey-wrap'),
            identityH: box('.composer-identity-header'),
            utilityH: box('[class*="composer_utility_panel"]'),
            journeyCols: cols(
              '[class*="composer_journey_rail"] [data-testid="stColumn"],'
              + '[class*="composer_journey_rail"] .stColumn,'
              + '[class*="composer_utility_panel"] [data-testid="stColumn"],'
              + '[class*="composer_utility_panel"] .stColumn'),
            hOverflow: scrollW > window.innerWidth + 4,
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            hasComposer: primary.includes('composer')
              || !!document.querySelector('.composer-hero')
              || !!document.querySelector('[class*="composer_journey_rail"], .composer-journey-wrap')
              || !!document.querySelector('.composer-identity-header')
              || t.includes('Composition Studio')
              || t.includes('Guided path')
              || t.includes('What kind of song'),
          };
        }"""
    )


def main() -> int:
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in (
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            page = browser.new_page(viewport=vp)
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 4000)
            expand_sidebar(page)
            expand_pages(page)
            wait(page, 1200)
            click_nav(page, "Compose")  # → Composition Studio
            wait(page, 5000)
            page.evaluate(
                """() => {
                  const el = document.querySelector('.composer-hero')
                    || document.querySelector('[class*="composer_journey_rail"]')
                    || document.querySelector('.composer-journey-wrap')
                    || document.querySelector('[class*="composer_utility_panel"]')
                    || document.querySelector('.composer-identity-header');
                  if (el) el.scrollIntoView({block:'start'});
                }"""
            )
            wait(page, 400)
            after = measure(page)
            page.screenshot(path=str(OUT / f"{vp_name}_composer_only_after.png"), full_page=False)
            before = after
            if vp["width"] <= 720:
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m4]')
                      .forEach(el => { el.disabled = true; })"""
                )
                wait(page, 200)
                before = measure(page)
                page.screenshot(path=str(OUT / f"{vp_name}_composer_only_before.png"), full_page=False)
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m4]')
                      .forEach(el => { el.disabled = false; })"""
                )
                wait(page, 200)
                after = measure(page)
            j_a, j_b = after.get("journeyH"), before.get("journeyH")
            h_a, h_b = after.get("heroH"), before.get("heroH")
            results[vp_name] = {
                "landed": bool(after.get("hasComposer")),
                "primary": after.get("primary"),
                "before_journey_h": j_b,
                "after_journey_h": j_a,
                "before_hero_h": h_b,
                "after_hero_h": h_a,
                "journey_cols": after.get("journeyCols"),
                "hOverflow": after.get("hOverflow"),
                "m4": after.get("m4"),
                "journey_reduction_pct": (
                    round(100 * (1 - j_a / j_b), 1) if j_a and j_b else None
                ),
                "hero_reduction_pct": (
                    round(100 * (1 - h_a / h_b), 1) if h_a and h_b else None
                ),
            }
            page.close()
        browser.close()
    path = OUT / "m4_composer_only_metrics.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    for vp, d in results.items():
        assert d["landed"], f"{vp} composer not landed: {d}"
        assert not d["hOverflow"], f"{vp} overflow"
    print("ASSERT_OK", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

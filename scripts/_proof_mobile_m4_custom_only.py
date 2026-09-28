# -*- coding: utf-8 -*-
"""M4 Custom-only compaction proof (reliable)."""
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
            .slice(0, 10).map(c => Math.round(c.getBoundingClientRect().width));
          const scrollW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
          return {
            chordH: box('[class*="cpl_chord_pick_grid"]'),
            barH: box('[class*="cpl_bar_duration_row"]'),
            headH: box('.ui-custom-builder-head'),
            chordCols: cols('[class*="cpl_chord_pick_grid"] [data-testid="stColumn"], [class*="cpl_chord_pick_grid"] .stColumn'),
            barCols: cols('[class*="cpl_bar_duration_row"] [data-testid="stColumn"], [class*="cpl_bar_duration_row"] .stColumn'),
            hOverflow: scrollW > window.innerWidth + 4,
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            hasCreate: (document.body.innerText || '').includes('Create Your Own Song'),
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
            click_nav(page, "Custom")
            wait(page, 4000)
            page.evaluate(
                """() => {
                  const el = document.querySelector('[class*="cpl_chord_pick_grid"]');
                  if (el) el.scrollIntoView({block:'center'});
                }"""
            )
            wait(page, 400)
            after = measure(page)
            page.screenshot(path=str(OUT / f"{vp_name}_custom_only_after.png"), full_page=False)
            before = after
            if vp["width"] <= 720:
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m4]')
                      .forEach(el => { el.disabled = true; })"""
                )
                wait(page, 200)
                before = measure(page)
                page.screenshot(path=str(OUT / f"{vp_name}_custom_only_before.png"), full_page=False)
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m4]')
                      .forEach(el => { el.disabled = false; })"""
                )
                wait(page, 200)
                after = measure(page)
            ch_a, ch_b = after.get("chordH"), before.get("chordH")
            results[vp_name] = {
                "landed": bool(after.get("hasCreate") or after.get("chordH")),
                "before_chord_h": ch_b,
                "after_chord_h": ch_a,
                "chord_cols": after.get("chordCols"),
                "bar_cols": after.get("barCols"),
                "hOverflow": after.get("hOverflow"),
                "m4": after.get("m4"),
                "reduction_pct": round(100 * (1 - ch_a / ch_b), 1) if ch_a and ch_b else None,
            }
            page.close()
        browser.close()
    path = OUT / "m4_custom_only_metrics.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    for vp, d in results.items():
        assert d["landed"], f"{vp} custom not landed"
        assert not d["hOverflow"], f"{vp} overflow"
        if vp != "1280":
            assert d["after_chord_h"] and d["after_chord_h"] < d["before_chord_h"], d
    print("ASSERT_OK", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Focused M4 evidence for Composition + Custom compaction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar, click_nav  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8584"
OUT = SCRIPTS / "evidence-mobile-m4"
OUT.mkdir(parents=True, exist_ok=True)


def _open_page(page: Page, page_id: str, label: str) -> None:
    """Open a studio page. Prefer sidebar label for Compose (more reliable)."""
    page.evaluate("window.scrollTo(0,0)")
    wait(page, 200)
    # Composition Studio: quick-nav Open is flaky after Custom; sidebar is reliable.
    if page_id == "composer":
        click_nav(page, "Compose")
        wait(page, 4500)
        # Confirm; if still not composer, try quick-nav once.
        primary = page.evaluate(
            """() => [...document.querySelectorAll(
              '[class*="st-key-studio_quick_nav_btn_"] button[kind="primary"]'
            )].map(b => {
              const w = b.closest('[class*="st-key-studio_quick_nav_btn_"]');
              const m = (w && w.className || '').match(/studio_quick_nav_btn_([a-z_]+)/);
              return m ? m[1] : null;
            }).filter(Boolean)"""
        )
        if "composer" in (primary or []):
            return
    sel = f'[class*="st-key-studio_quick_nav_btn_{page_id}"] button'
    loc = page.locator(sel)
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if box and box["width"] > 2:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                wait(page, 4000)
                return
        except Exception:
            continue
    click_nav(page, label)
    wait(page, 4000)


def _disable_m4(page: Page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('style[data-mpc-mobile-m4]').forEach(el => {
            el.disabled = true;
            el.setAttribute('data-mpc-m4-disabled','1');
          });
        }"""
    )
    wait(page, 200)


def _enable_m4(page: Page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('style[data-mpc-m4-disabled]').forEach(el => {
            el.disabled = false;
            el.removeAttribute('data-mpc-m4-disabled');
          });
        }"""
    )
    wait(page, 200)


def _measure(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const box = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {h: Math.round(r.height), w: Math.round(r.width)};
          };
          const cols = (sel) => [...document.querySelectorAll(sel)]
            .slice(0, 12)
            .map(c => Math.round(c.getBoundingClientRect().width));
          const t = document.body.innerText || '';
          const scrollH = Math.max(
            document.body.scrollHeight, document.documentElement.scrollHeight);
          const scrollW = Math.max(
            document.body.scrollWidth, document.documentElement.scrollWidth);
          const m4 = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-m4').trim();
          // Prefer primary-looking nav button as page identity when data attr missing
          const primaryNav = [...document.querySelectorAll(
            '[class*="st-key-studio_quick_nav_btn_"] button[kind="primary"]'
          )].map(b => {
            const wrap = b.closest('[class*="st-key-studio_quick_nav_btn_"]');
            const m = (wrap && wrap.className || '').match(/studio_quick_nav_btn_([a-z_]+)/);
            return m ? m[1] : null;
          }).filter(Boolean);
          return {
            m4,
            primaryNav,
            pageAttr: document.body.getAttribute('data-studio-page'),
            scrollH,
            hOverflow: scrollW > window.innerWidth + 4,
            // Composition surfaces
            composerHero: box('.composer-hero'),
            composerJourney: box('[class*="composer_journey_rail"], .composer-journey-wrap'),
            composerIdentity: box('.composer-identity-header'),
            composerPhase: box('.composer-phase-card'),
            composerUtility: box('[class*="composer_utility_panel"]'),
            hasGuidedText: t.includes('Guided path'),
            hasWelcome: t.includes('What kind of song'),
            // Custom surfaces
            customHead: box('.ui-custom-builder-head'),
            customStep: box('.ui-custom-step-card'),
            cplChord: box('[class*="cpl_chord_pick_grid"]'),
            cplBar: box('[class*="cpl_bar_duration_row"]'),
            cplLaunch: box('[class*="cpl_launch_actions"]'),
            chordCols: cols(
              '[class*="cpl_chord_pick_grid"] [data-testid="stColumn"],'
              + '[class*="cpl_chord_pick_grid"] .stColumn'),
            barCols: cols(
              '[class*="cpl_bar_duration_row"] [data-testid="stColumn"],'
              + '[class*="cpl_bar_duration_row"] .stColumn'),
            journeyCols: cols(
              '[class*="composer_journey_rail"] [data-testid="stColumn"],'
              + '[class*="composer_journey_rail"] .stColumn'),
            hasCreateOwn: t.includes('Create Your Own Song'),
            hasClickChord: t.includes('Click a chord'),
          };
        }"""
    )


def main() -> int:
    results: dict = {"url": URL, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 4500)
        expand_sidebar(page)
        expand_pages(page)
        wait(page, 1500)

        for vp_name, vp in (
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            page.set_viewport_size(vp)
            wait(page, 400)
            phone = vp["width"] <= 720
            out: dict = {}

            # —— Custom ——
            _open_page(page, "custom", "Custom")
            wait(page, 1500)
            # Scroll into builder (below hero)
            page.evaluate(
                """() => {
                  const el = document.querySelector('[class*="cpl_chord_pick_grid"]')
                    || document.querySelector('.ui-custom-builder-head')
                    || document.querySelector('[class*="custom_song_builder_panel"]');
                  if (el) el.scrollIntoView({block:'start'});
                  // Also try text
                  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                  while (walker.nextNode()) {
                    if ((walker.currentNode.nodeValue || '').includes('Click a chord')) {
                      walker.currentNode.parentElement?.scrollIntoView({block:'center'});
                      break;
                    }
                  }
                }"""
            )
            wait(page, 500)
            after = _measure(page)
            page.screenshot(path=str(OUT / f"{vp_name}_custom_builder_after.png"), full_page=False)
            before = after
            if phone:
                _disable_m4(page)
                before = _measure(page)
                page.screenshot(path=str(OUT / f"{vp_name}_custom_builder_before.png"), full_page=False)
                _enable_m4(page)
                after = _measure(page)
            ch_a = (after.get("cplChord") or {}).get("h")
            ch_b = (before.get("cplChord") or {}).get("h")
            head_a = (after.get("customHead") or {}).get("h")
            head_b = (before.get("customHead") or {}).get("h")
            out["custom"] = {
                "landed": bool(after.get("hasCreateOwn") or after.get("customHead") or after.get("primaryNav") == ["custom"] or (after.get("primaryNav") or [None])[0] == "custom"),
                "primaryNav": after.get("primaryNav"),
                "before_chord_h": ch_b,
                "after_chord_h": ch_a,
                "chord_cols": after.get("chordCols"),
                "bar_cols": after.get("barCols"),
                "before_head_h": head_b,
                "after_head_h": head_a,
                "before_scroll_h": before.get("scrollH"),
                "after_scroll_h": after.get("scrollH"),
                "hOverflow": after.get("hOverflow"),
                "chord_reduction_pct": (
                    round(100 * (1 - ch_a / ch_b), 1) if ch_a and ch_b else None
                ),
                "scroll_reduction_pct": (
                    round(100 * (1 - after["scrollH"] / before["scrollH"]), 1)
                    if after.get("scrollH") and before.get("scrollH")
                    else None
                ),
            }

            # —— Composition ——
            _open_page(page, "composer", "Compose")
            wait(page, 2500)
            # Prefer welcome hero or journey
            page.evaluate(
                """() => {
                  const el = document.querySelector('.composer-hero')
                    || document.querySelector('[class*="composer_journey_rail"]')
                    || document.querySelector('.composer-journey-wrap')
                    || document.querySelector('.composer-identity-header')
                    || document.querySelector('[class*="composer_utility_panel"]');
                  if (el) el.scrollIntoView({block:'start'});
                }"""
            )
            wait(page, 500)
            after_c = _measure(page)
            page.screenshot(path=str(OUT / f"{vp_name}_composer_builder_after.png"), full_page=False)
            before_c = after_c
            if phone:
                _disable_m4(page)
                before_c = _measure(page)
                page.screenshot(path=str(OUT / f"{vp_name}_composer_builder_before.png"), full_page=False)
                _enable_m4(page)
                after_c = _measure(page)
            hero_a = (after_c.get("composerHero") or {}).get("h")
            hero_b = (before_c.get("composerHero") or {}).get("h")
            journey_a = (after_c.get("composerJourney") or {}).get("h")
            journey_b = (before_c.get("composerJourney") or {}).get("h")
            out["composer"] = {
                "landed": bool(
                    after_c.get("hasWelcome")
                    or after_c.get("hasGuidedText")
                    or after_c.get("composerHero")
                    or after_c.get("composerJourney")
                    or after_c.get("composerIdentity")
                    or (after_c.get("primaryNav") or [None])[0] == "composer"
                ),
                "primaryNav": after_c.get("primaryNav"),
                "before_hero_h": hero_b,
                "after_hero_h": hero_a,
                "before_journey_h": journey_b,
                "after_journey_h": journey_a,
                "journey_cols": after_c.get("journeyCols"),
                "before_scroll_h": before_c.get("scrollH"),
                "after_scroll_h": after_c.get("scrollH"),
                "hOverflow": after_c.get("hOverflow"),
                "hero_reduction_pct": (
                    round(100 * (1 - hero_a / hero_b), 1) if hero_a and hero_b else None
                ),
                "journey_reduction_pct": (
                    round(100 * (1 - journey_a / journey_b), 1)
                    if journey_a and journey_b
                    else None
                ),
                "scroll_reduction_pct": (
                    round(100 * (1 - after_c["scrollH"] / before_c["scrollH"]), 1)
                    if after_c.get("scrollH") and before_c.get("scrollH")
                    else None
                ),
            }

            results["viewports"][vp_name] = out

        browser.close()

    path = OUT / "m4_comp_custom_metrics.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print("Wrote", path)
    # Soft asserts
    for vp, data in results["viewports"].items():
        assert data["custom"]["landed"], f"{vp} did not land on Custom"
        assert not data["custom"]["hOverflow"], f"{vp} custom h-overflow"
        assert data["composer"]["landed"], f"{vp} did not land on Compose"
        assert not data["composer"]["hOverflow"], f"{vp} composer h-overflow"
    print("ASSERT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Mobile M6 Composition before/after proof at 360/390/430/1280."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar, click_nav  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8587"
OUT = SCRIPTS / "evidence-mobile-m6"
OUT.mkdir(parents=True, exist_ok=True)


def wait_ready(page, timeout_ms: int = 45000) -> None:
    elapsed = 0
    while elapsed < timeout_ms:
        ready = page.evaluate(
            """() => !!(
              document.querySelector('[class*="st-key-studio_quick_nav_btn_"]')
              || document.querySelector('.ui-studio-script-header')
            )"""
        )
        if ready:
            return
        wait(page, 1500)
        elapsed += 1500
        expand_sidebar(page)


def click_quick_nav_open(page, page_id: str) -> bool:
    wrap = page.locator(f'[class*="st-key-studio_quick_nav_btn_{page_id}"]')
    if wrap.count() == 0:
        return False
    try:
        wrap.first.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        pass
    wait(page, 300)
    btns = wrap.first.locator("button")
    for i in range(btns.count()):
        btn = btns.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if not box or box["width"] < 2:
                continue
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            wait(page, 5500)
            return True
        except Exception:
            continue
    return False


def open_composer(page) -> bool:
    marker = (
        '[class*="st-key-composer_journey_rail"], '
        '[class*="st-key-composer_utility_panel"], '
        '.composer-hero, .composer-journey-title'
    )
    if click_quick_nav_open(page, "composer") and page.locator(marker).count():
        return True
    click_nav(page, "Compose")
    wait(page, 5000)
    for alt in ("Composition Studio", "Composition", "Compose"):
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=re.compile(re.escape(alt), re.I)
            ).last.click(timeout=2500)
            wait(page, 5000)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    click_quick_nav_open(page, "composer")
    wait(page, 2000)
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
            return {
              h: Math.round(r.height),
              w: Math.round(r.width),
              x: Math.round(r.left),
              y: Math.round(r.top),
              right: Math.round(r.right),
            };
          };
          const anyClip = (() => {
            const vw = window.innerWidth;
            const nodes = [...document.querySelectorAll(
              '.st-key-composer_utility_panel, .st-key-composer_journey_rail, .composer-beside-panel, .composer-score-wrap, .composer-hero, [class*="st-key-composer_"]'
            )];
            for (const el of nodes) {
              const r = el.getBoundingClientRect();
              if (r.width < 2) continue;
              if (r.right > vw + 6 || r.left < -6) return true;
            }
            return false;
          })();
          return {
            mainScrollH: contentH,
            screens: +(contentH / fold).toFixed(2),
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            clipOffscreen: anyClip,
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            m5: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m5').trim(),
            m6: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m6').trim(),
            panel: box('[class*="st-key-composer_utility_panel"]')
              || box('[class*="st-key-composer_journey_rail"]'),
            journey: box('[class*="st-key-composer_journey_rail"]'),
            partner: box('.composer-beside-panel'),
            partnerLead: box('.composer-partner-lead') || box('.composer-beside-body'),
            score: box('.composer-score-wrap'),
            hero: box('.composer-hero'),
            library: box('[class*="st-key-composer_library_actions"]'),
            crossNav: box('[class*="st-key-composer_cross_nav"]'),
            split: box('[class*="st-key-composer_desktop_split"]'),
            padBottom: block ? getComputedStyle(block).paddingBottom : '',
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
            phone = vp["width"] <= 720
            page = browser.new_page(viewport=vp)
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 6500)
            expand_sidebar(page)
            expand_pages(page)
            wait_ready(page)
            expand_sidebar(page)
            landed = open_composer(page)
            wait(page, 1200)

            # Structural before: force desktop nowrap (pre-M6 clip condition)
            structural_before = None
            if phone:
                page.evaluate(
                    """() => {
                      let s = document.getElementById('mpc-m6-struct-before');
                      if (!s) {
                        s = document.createElement('style');
                        s.id = 'mpc-m6-struct-before';
                        document.head.appendChild(s);
                      }
                      s.textContent = `
                        [class*="st-key-composer_desktop_split"] [data-testid="stHorizontalBlock"] {
                          flex-wrap: nowrap !important;
                          flex-direction: row !important;
                        }
                        [class*="st-key-composer_desktop_split"] [data-testid="column"]:last-child {
                          flex: 1 1 280px !important;
                          max-width: 340px !important;
                          min-width: 280px !important;
                        }
                      `;
                    }"""
                )
                wait(page, 350)
                structural_before = measure(page)
                page.screenshot(
                    path=str(OUT / f"struct_before_{vp_name}_composer.png"),
                    full_page=False,
                )
                page.evaluate(
                    """() => {
                      const s = document.getElementById('mpc-m6-struct-before');
                      if (s) s.remove();
                    }"""
                )
                wait(page, 250)

                # Density before = M6 stylesheet disabled
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m6]')
                      .forEach(el => { el.disabled = true; })"""
                )
                wait(page, 350)
                before = measure(page)
                page.screenshot(path=str(OUT / f"before_{vp_name}_composer.png"), full_page=False)
                page.evaluate(
                    """() => document.querySelectorAll('style[data-mpc-mobile-m6]')
                      .forEach(el => { el.disabled = false; })"""
                )
                wait(page, 350)
            else:
                before = None

            after = measure(page)
            after["landed"] = landed
            if structural_before:
                after["struct_before_hOverflow"] = structural_before.get("hOverflow")
                after["struct_before_clip"] = structural_before.get("clipOffscreen")
                after["struct_before_panelW"] = (structural_before.get("panel") or {}).get("w")
                after["struct_before_splitW"] = (structural_before.get("split") or {}).get("w")
            if before:
                after["before_scrollH"] = before["mainScrollH"]
                after["before_screens"] = before["screens"]
                after["delta_scroll"] = after["mainScrollH"] - before["mainScrollH"]
                after["before_panelW"] = (before.get("panel") or {}).get("w")
                after["after_panelW"] = (after.get("panel") or {}).get("w")
                after["before_partnerH"] = (before.get("partner") or {}).get("h")
                after["after_partnerH"] = (after.get("partner") or {}).get("h")
                after["before_clip"] = before.get("clipOffscreen")
                after["before_hOverflow"] = before.get("hOverflow")
                after["before_padBottom"] = before.get("padBottom")
                after["after_padBottom"] = after.get("padBottom")
                after["before_partnerClamp"] = page.evaluate(
                    """() => {
                      const el = document.querySelector('.composer-partner-lead');
                      return el ? getComputedStyle(el).webkitLineClamp : '';
                    }"""
                )
            page.screenshot(path=str(OUT / f"after_{vp_name}_composer.png"), full_page=False)
            assert not after["hOverflow"], (vp_name, after)
            assert not after.get("clipOffscreen"), (vp_name, after)
            if phone:
                assert after["m6"] == "m6-tool-density-v1", after
                if after.get("panel"):
                    assert after["panel"]["w"] <= vp["width"] + 2, after["panel"]
            else:
                assert not after.get("m6"), after
            results["viewports"][vp_name] = after
            page.close()
        browser.close()

    out = OUT / "m6_composer_metrics.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print("ASSERT_OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

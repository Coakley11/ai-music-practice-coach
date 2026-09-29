# -*- coding: utf-8 -*-
"""Mobile M6 before/after proof: Creative / Upload / Practice at 360/390/430/1280."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    click_nav,
    set_baseweb_select,
    click_radio,
    click_label,
)
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8587"
TAG = sys.argv[2] if len(sys.argv) > 2 else "after"
OUT = SCRIPTS / "evidence-mobile-m6"
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    (
        "creative",
        "Creative",
        '[class*="st-key-creative_studio_panel"], .ui-creative-studio-head, [class*="st-key-creative_lab"]',
    ),
    (
        "analysis",
        "Upload",
        '.ui-upload-studio-head, [class*="st-key-upload_studio_panel"], body.upload-studio-page',
    ),
    (
        "practice",
        "Practice",
        '[class*="st-key-practice_control_panel"], .ui-practice-control-head',
    ),
]


def wait_ready(page, timeout_ms: int = 45000) -> None:
    deadline = timeout_ms
    step = 1500
    elapsed = 0
    while elapsed < deadline:
        ready = page.evaluate(
            """() => {
              const nav = document.querySelector('[class*="st-key-studio_quick_nav_btn_"]');
              const side = document.querySelector('section[data-testid="stSidebar"]');
              const header = document.querySelector('.ui-studio-script-header');
              return !!(nav || header || (side && side.offsetWidth > 40));
            }"""
        )
        if ready:
            return
        wait(page, step)
        elapsed += step
        expand_sidebar(page)


def click_quick_nav_open(page, page_id: str) -> bool:
    wrap = page.locator(f'[class*="st-key-studio_quick_nav_btn_{page_id}"]')
    if wrap.count() == 0:
        return False
    try:
        wrap.first.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        pass
    wait(page, 350)
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
    try:
        wrap.first.click(force=True, timeout=4000)
        wait(page, 5500)
        return True
    except Exception:
        return False


def ensure_improv_lab(page) -> bool:
    """Creative may open in DHA mode — switch to Improvisation Lab for M6 surfaces."""
    if page.locator('[class*="st-key-creative_studio_panel"]').count():
        return True
    switched = (
        set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
        or set_baseweb_select(page, "Analysis mode", "Improvisation Lab")
        or set_baseweb_select(page, "Deep Harmonic Analyzer", "Improvisation Intelligence")
    )
    wait(page, 4500)
    if page.locator('[class*="st-key-creative_studio_panel"]').count():
        return True
    if not switched:
        try:
            page.locator('[class*="st-key-creative_lab_analysis_mode"]').first.click(timeout=2500)
            wait(page, 700)
            page.get_by_text("Improvisation Intelligence", exact=False).last.click(timeout=3000)
            wait(page, 4500)
        except Exception:
            pass
    return page.locator('[class*="st-key-creative_studio_panel"]').count() > 0


def open_creative_submode(page, name: str) -> None:
    click_radio(page, name) or click_label(page, name)
    wait(page, 3500)


def open_page(page, page_id: str, label: str, marker: str) -> bool:
    if click_quick_nav_open(page, page_id) and page.locator(marker).count():
        if page_id == "creative":
            ensure_improv_lab(page)
        return page.locator(marker).count() > 0
    # Sidebar / Pages labels
    if click_nav(page, label):
        wait(page, 2000)
        if page_id == "creative":
            ensure_improv_lab(page)
        if page.locator(marker).count():
            return True
    alts = {
        "creative": ["Creative Lab", "Creative"],
        "analysis": ["Upload Analysis", "Upload", "Analysis"],
        "practice": ["Practice", "Song Practice"],
    }
    for alt in alts.get(page_id, [label]):
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=re.compile(re.escape(alt), re.I)
            ).last.click(timeout=2500)
            wait(page, 5000)
            if page_id == "creative":
                ensure_improv_lab(page)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    # Retry quick-nav after sidebar attempts
    if click_quick_nav_open(page, page_id):
        wait(page, 2000)
        if page_id == "creative":
            ensure_improv_lab(page)
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
          const any = (sels) => {
            for (const s of sels) {
              const b = box(s);
              if (b) return b;
            }
            return null;
          };
          return {
            mainScrollH: contentH,
            screens: +(contentH / fold).toFixed(2),
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            m1: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-nav-shell').trim(),
            m2: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-density').trim(),
            m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
            m5: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m5').trim(),
            m6: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m6').trim(),
            header: box('.ui-studio-script-header'),
            creative: any([
              '[class*="st-key-creative_studio_panel"]',
              '.ui-creative-studio-head',
            ]),
            uploadHead: box('.ui-upload-studio-head'),
            uploadPanel: box('[class*="st-key-upload_studio_panel"]'),
            karaokePanel: box('.karaoke-lyric-panel'),
            motifActions: any([
              '[class*="st-key-improv_motif_gen_actions"]',
              '[class*="st-key-improv_mission_gen_actions"]',
              '[class*="st-key-improv_style_jam_controls"]',
              '[class*="st-key-improv_jam_gen_controls"]',
            ]),
            liveCoachQc: box('[class*="st-key-improv_live_coach_qc_row"]'),
          };
        }"""
    )


def main() -> int:
    results = {"tag": TAG, "url": URL, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in (
            ("360", {"width": 360, "height": 740}),
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            phone = vp["width"] <= 720
            vp_out = {}
            for page_id, label, marker in TARGETS:
                page = browser.new_page(viewport=vp)
                page.goto(URL, wait_until="domcontentloaded", timeout=120000)
                wait(page, 6000)
                expand_sidebar(page)
                expand_pages(page)
                wait_ready(page)
                expand_sidebar(page)
                wait(page, 800)
                landed = open_page(page, page_id, label, marker)
                if page_id == "creative" and landed:
                    # Prefer Style Jam controls for compact 3-up density signal
                    open_creative_submode(page, "Entry & Jam")
                    open_creative_submode(page, "Style Jam Mode")
                wait(page, 1000)

                m_before = None
                if TAG == "after" and phone:
                    page.evaluate(
                        """() => document.querySelectorAll('style[data-mpc-mobile-m6]')
                          .forEach(el => { el.disabled = true; })"""
                    )
                    wait(page, 350)
                    m_before = measure(page)
                    page.screenshot(
                        path=str(OUT / f"before_{vp_name}_{page_id}.png"),
                        full_page=False,
                    )
                    page.evaluate(
                        """() => document.querySelectorAll('style[data-mpc-mobile-m6]')
                          .forEach(el => { el.disabled = false; })"""
                    )
                    wait(page, 350)

                m_on = measure(page)
                m_on["landed"] = landed
                page.screenshot(path=str(OUT / f"{TAG}_{vp_name}_{page_id}.png"), full_page=False)
                assert not m_on["hOverflow"], (vp_name, page_id, m_on)
                if phone:
                    assert m_on["m2"] == "m2-chrome-v1", m_on
                    assert m_on["m4"] == "m4-scroll-compact-v1", m_on
                    assert m_on["m5"] == "m5-fold-density-v1", m_on
                    if TAG == "after":
                        assert m_on["m6"] == "m6-tool-density-v1", m_on
                        assert m_before is not None
                        m_on["before_scrollH"] = m_before["mainScrollH"]
                        m_on["before_screens"] = m_before["screens"]
                        m_on["delta_scroll"] = m_on["mainScrollH"] - m_before["mainScrollH"]
                        m_on["before_creativeH"] = (m_before.get("creative") or {}).get("h")
                        m_on["after_creativeH"] = (m_on.get("creative") or {}).get("h")
                        m_on["before_uploadH"] = (m_before.get("uploadHead") or {}).get("h")
                        m_on["after_uploadH"] = (m_on.get("uploadHead") or {}).get("h")
                        m_on["before_motifH"] = (m_before.get("motifActions") or {}).get("h")
                        m_on["after_motifH"] = (m_on.get("motifActions") or {}).get("h")
                else:
                    assert not m_on.get("m6"), m_on
                    assert not m_on.get("m5"), m_on
                vp_out[page_id] = m_on
                page.close()
            results["viewports"][vp_name] = vp_out
        browser.close()

    out = OUT / f"m6_{TAG}_metrics.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    if TAG == "after":
        for vp in ("360", "390", "430"):
            for page_id, m in results["viewports"][vp].items():
                delta = m.get("delta_scroll")
                if delta is not None:
                    assert delta <= 120, (vp, page_id, delta)
    print("ASSERT_OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

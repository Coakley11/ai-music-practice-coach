# -*- coding: utf-8 -*-
"""Quick check that genre pill colors apply after CSS fix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8584"
OUT = SCRIPTS / "evidence-mobile-m4"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, vp in (
            ("390", {"width": 390, "height": 844}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            page = browser.new_page(viewport=vp)
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 3500)
            expand_sidebar(page)
            expand_pages(page)
            wait(page, 1200)
            loc = page.locator('[class*="st-key-studio_quick_nav_btn_picker"] button')
            for i in range(loc.count()):
                btn = loc.nth(i)
                if btn.is_visible():
                    box = btn.bounding_box()
                    if box:
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        break
            wait(page, 4000)
            page.evaluate(
                """() => {
                  const el = document.querySelector('[class*="genre_filter_pill_grid"]');
                  if (el) el.scrollIntoView({block:'start'});
                }"""
            )
            wait(page, 300)
            info = page.evaluate(
                """() => {
                  const style = document.querySelector('style[data-mpc-genre-filter-pills]');
                  const txt = style ? style.textContent : '';
                  const hasCommaBug = txt.includes(
                    'st-key-genre_pill_Pop"], [class*="st-key-genre_more_Pop"]'
                  );
                  const btns = [...document.querySelectorAll(
                    '[class*="genre_filter_pill_grid"] button'
                  )].slice(0, 9).map(b => {
                    const cs = getComputedStyle(b);
                    return {
                      text: (b.innerText || '').trim(),
                      kind: b.getAttribute('kind'),
                      bg: cs.backgroundColor,
                      bgImg: cs.backgroundImage.slice(0, 80),
                      color: cs.color,
                      border: cs.borderColor,
                      h: Math.round(b.getBoundingClientRect().height),
                    };
                  });
                  const cols = [...document.querySelectorAll(
                    '[class*="genre_filter_pill_grid"] [data-testid="stColumn"],'
                    + '[class*="genre_filter_pill_grid"] .stColumn'
                  )].slice(0, 9).map(c => Math.round(c.getBoundingClientRect().width));
                  const grid = document.querySelector('[class*="genre_filter_pill_grid"]');
                  const gr = grid ? grid.getBoundingClientRect() : null;
                  // select first secondary then check primary after click
                  return {
                    hasCommaBug,
                    m4: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m4').trim(),
                    genreCss: !!style,
                    gridH: gr ? Math.round(gr.height) : null,
                    cols,
                    btns,
                    hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
                      > window.innerWidth + 4,
                  };
                }"""
            )
            # Click Pop to verify selected state
            pop = page.locator('[class*="st-key-genre_pill_Pop"] button').first
            if pop.count():
                pop.evaluate("node => node.scrollIntoView({block:'center'})")
                wait(page, 200)
                try:
                    pop.click(timeout=8000)
                except Exception:
                    pop.click(force=True)
                wait(page, 2800)
                selected = page.evaluate(
                    """() => {
                      const b = document.querySelector('[class*="st-key-genre_pill_Pop"] button');
                      if (!b) return null;
                      const cs = getComputedStyle(b);
                      const style = document.querySelector('style[data-mpc-genre-filter-pills]');
                      const txt = style ? style.textContent : '';
                      const hasPrimaryGradient = txt.includes('genre_pill_Pop')
                        && txt.includes('button[kind="primary"]')
                        && txt.includes('linear-gradient');
                      return {
                        text: (b.innerText || '').trim(),
                        kind: b.getAttribute('kind'),
                        bg: cs.backgroundColor,
                        bgImg: cs.backgroundImage.slice(0, 100),
                        color: cs.color,
                        hasPrimaryGradient,
                      };
                    }"""
                )
                info["selectedPop"] = selected
            page.screenshot(path=str(OUT / f"songs_genre_{vp_name}.png"), full_page=False)
            results[vp_name] = info
            page.close()
        browser.close()
    out = OUT / "songs_genre_visual.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    # Basic assertions
    for vp, info in results.items():
        assert not info.get("hasCommaBug"), f"{vp} still has CSS comma bug"
        assert info.get("genreCss"), f"{vp} missing genre CSS"
        btns = info.get("btns") or []
        assert btns, f"{vp} no genre buttons"
        # Distinct soft fills (not uniform white)
        soft_ok = any(
            b.get("bg") not in {"rgb(255, 255, 255)", "rgba(0, 0, 0, 0)", "transparent"}
            for b in btns
            if b.get("kind") == "secondary"
        )
        assert soft_ok, f"{vp} unselected pills still white: {btns[:3]}"
        # Distinct colors across genres
        bgs = {b.get("bg") for b in btns}
        assert len(bgs) >= 5, f"{vp} expected many genre colors, got {bgs}"
        # Icons present in labels
        assert any("Pop" in (b.get("text") or "") for b in btns)
        assert any("🎤" in (b.get("text") or "") for b in btns), f"{vp} missing Pop mic icon"
        assert any("🤘" in (b.get("text") or "") for b in btns), f"{vp} missing Rock icon"
        assert any("🎷" in (b.get("text") or "") for b in btns), f"{vp} missing Jazz icon"
        sel = info.get("selectedPop") or {}
        # Either live toggle to primary, or primary gradient CSS is ready for selected state
        if sel.get("kind") == "primary":
            assert "255, 255, 255" in str(sel.get("color")), f"{vp} selected text not white: {sel}"
            assert (
                "gradient" in str(sel.get("bgImg") or "").lower()
                or sel.get("bg") not in {"rgb(255, 255, 255)", "rgb(238, 242, 255)"}
            ), f"{vp} selected fill not gradient: {sel}"
        else:
            assert sel.get("hasPrimaryGradient"), f"{vp} missing selected primary CSS: {sel}"
        assert not info.get("hOverflow"), f"{vp} horizontal overflow"
    print("ASSERT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

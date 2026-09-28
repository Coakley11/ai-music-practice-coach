"""Mobile M4 browser proof — vertical-scroll compaction before/after.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_mobile_m4 python -m streamlit run streamlit_music_practice_app.py --server.port 8584
  python scripts/_proof_mobile_m4_compaction.py http://127.0.0.1:8584
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8584"
OUT = SCRIPTS / "evidence-mobile-m4"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("360", {"width": 360, "height": 740}),
    ("390", {"width": 390, "height": 844}),
    ("430", {"width": 430, "height": 932}),
    ("1280", {"width": 1280, "height": 900}),
]


def click_quick_nav(page: Page, page_id: str) -> None:
    from walk_creative_backing_matrix import click_nav

    id_to_name = {
        "practice": "Practice",
        "picker": "Songs",
        "backing": "Backing",
        "creative": "Creative",
        "composer": "Compose",
        "custom": "Custom",
    }
    page.evaluate("window.scrollTo(0,0)")
    wait(page, 250)
    for _ in range(20):
        if page.locator('[class*="st-key-studio_quick_nav_panel"]').count() > 0:
            break
        wait(page, 400)
    sel = f'[class*="st-key-studio_quick_nav_btn_{page_id}"] button'
    loc = page.locator(sel)
    # Prefer a visible instance (Streamlit can keep a hidden duplicate in DOM).
    for i in range(loc.count()):
        btn = loc.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if box and box.get("width", 0) > 2 and box.get("height", 0) > 2:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                wait(page, 2500)
                return
            btn.click(timeout=8000, force=True)
            wait(page, 2500)
            return
        except Exception:
            continue
    click_nav(page, id_to_name.get(page_id, page_id))
    wait(page, 2500)


def _page_metrics(page: Page) -> dict:
    return page.evaluate(
        """() => {
          function box(sel) {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {
              h: Math.round(r.height),
              w: Math.round(r.width),
              top: Math.round(r.top + window.scrollY),
            };
          }
          function colWidths(sel) {
            return [...document.querySelectorAll(sel)]
              .slice(0, 12)
              .map(c => Math.round(c.getBoundingClientRect().width));
          }
          const m4 = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-m4').trim();
          const density = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-density').trim();
          const scrollW = Math.max(
            document.body.scrollWidth, document.documentElement.scrollWidth);
          const scrollH = Math.max(
            document.body.scrollHeight, document.documentElement.scrollHeight);
          const clientW = window.innerWidth;
          const clientH = window.innerHeight;
          const genreCols = colWidths(
            '[class*="genre_filter_pill_grid"] [data-testid="stColumn"],'
            + '[class*="genre_filter_pill_grid"] .stColumn');
          const chordCols = colWidths(
            '[class*="cpl_chord_pick_grid"] [data-testid="stColumn"],'
            + '[class*="cpl_chord_pick_grid"] .stColumn');
          const genreBtns = [...document.querySelectorAll(
            '[class*="genre_filter_pill_grid"] button'
          )].slice(0, 12).map(b => {
            const cs = getComputedStyle(b);
            return {
              text: (b.innerText || '').trim(),
              kind: b.getAttribute('kind') || b.getAttribute('data-testid') || '',
              bg: (cs.backgroundImage && cs.backgroundImage !== 'none')
                ? cs.backgroundImage.slice(0, 80)
                : cs.backgroundColor,
              color: cs.color,
            };
          });
          return {
            clientW, clientH, scrollH,
            hOverflow: scrollW > clientW + 4,
            m4, density,
            genrePillsStyle: !!document.querySelector('style[data-mpc-genre-filter-pills]'),
            genreBtns,
            genreGrid: box('[class*="genre_filter_pill_grid"]'),
            genreCols,
            songLibrary: box('[class*="song_library_panel"]'),
            composerHero: box('.composer-hero'),
            composerJourney: box('[class*="composer_journey_rail"], .composer-journey-wrap'),
            composerDocH: scrollH,
            customHead: box('.ui-custom-builder-head'),
            cplChordGrid: box('[class*="cpl_chord_pick_grid"]'),
            chordCols,
            cplBarRow: box('[class*="cpl_bar_duration_row"]'),
            customBuilder: box('[class*="custom_song_builder_panel"]'),
          };
        }"""
    )


def _disable_m4(page: Page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('style[data-mpc-mobile-m4]').forEach(el => {
            el.setAttribute('data-mpc-m4-disabled', '1');
            el.disabled = true;
          });
          document.body.style.removeProperty('--mpc-mobile-m4');
        }"""
    )


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


def _shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def main() -> int:
    results: dict = {"url": URL, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 4500)
        expand_sidebar(page)
        expand_pages(page)
        wait(page, 1500)
        # Ensure quick-nav is present before measuring.
        for _ in range(25):
            if page.locator('[class*="st-key-studio_quick_nav_panel"]').count() > 0:
                break
            wait(page, 400)

        for vp_name, vp in VIEWPORTS:
            page.set_viewport_size(vp)
            wait(page, 500)
            phone = vp["width"] <= 720
            vp_out: dict = {}

            # —— Songs genre filters ——
            click_quick_nav(page, "picker")
            wait(page, 1500)
            page.evaluate("window.scrollTo(0,0)")
            wait(page, 300)
            # Scroll genre grid into view if needed
            page.evaluate(
                """() => {
                  const el = document.querySelector('[class*="genre_filter_pill_grid"]')
                    || document.querySelector('[class*="song_library_panel"]');
                  if (el) el.scrollIntoView({block:'start'});
                }"""
            )
            wait(page, 400)
            after = _page_metrics(page)
            _shot(page, f"{vp_name}_songs_after")
            before = after
            if phone:
                _disable_m4(page)
                wait(page, 250)
                before = _page_metrics(page)
                _shot(page, f"{vp_name}_songs_before")
                _enable_m4(page)
                wait(page, 250)
                after = _page_metrics(page)
            genre_after_h = (after.get("genreGrid") or {}).get("h")
            genre_before_h = (before.get("genreGrid") or {}).get("h")
            vp_out["songs"] = {
                "before_genre_h": genre_before_h,
                "after_genre_h": genre_after_h,
                "genre_cols_after": after.get("genreCols"),
                "genre_pills_style": after.get("genrePillsStyle"),
                "genre_btns": after.get("genreBtns"),
                "hOverflow": after.get("hOverflow"),
                "m4": after.get("m4"),
                "reduction_pct": (
                    round(100 * (1 - genre_after_h / genre_before_h), 1)
                    if genre_before_h and genre_after_h
                    else None
                ),
            }

            # —— Composition ——
            click_quick_nav(page, "composer")
            wait(page, 1800)
            page.evaluate("window.scrollTo(0,0)")
            wait(page, 300)
            after_c = _page_metrics(page)
            _shot(page, f"{vp_name}_composer_after")
            before_c = after_c
            if phone:
                _disable_m4(page)
                wait(page, 250)
                before_c = _page_metrics(page)
                _shot(page, f"{vp_name}_composer_before")
                _enable_m4(page)
                wait(page, 250)
                after_c = _page_metrics(page)
            hero_a = (after_c.get("composerHero") or {}).get("h")
            hero_b = (before_c.get("composerHero") or {}).get("h")
            scroll_a = after_c.get("scrollH")
            scroll_b = before_c.get("scrollH")
            vp_out["composer"] = {
                "before_hero_h": hero_b,
                "after_hero_h": hero_a,
                "before_scroll_h": scroll_b,
                "after_scroll_h": scroll_a,
                "hOverflow": after_c.get("hOverflow"),
                "scroll_reduction_pct": (
                    round(100 * (1 - scroll_a / scroll_b), 1)
                    if scroll_b and scroll_a
                    else None
                ),
            }

            # —— Custom ——
            click_quick_nav(page, "custom")
            wait(page, 2000)
            page.evaluate("window.scrollTo(0,0)")
            wait(page, 400)
            page.evaluate(
                """() => {
                  const el = document.querySelector('[class*="cpl_chord_pick_grid"]')
                    || document.querySelector('[class*="custom_song_builder_panel"]');
                  if (el) el.scrollIntoView({block:'center'});
                }"""
            )
            wait(page, 400)
            after_u = _page_metrics(page)
            _shot(page, f"{vp_name}_custom_after")
            before_u = after_u
            if phone:
                _disable_m4(page)
                wait(page, 250)
                before_u = _page_metrics(page)
                _shot(page, f"{vp_name}_custom_before")
                _enable_m4(page)
                wait(page, 250)
                after_u = _page_metrics(page)
            chord_a = (after_u.get("cplChordGrid") or {}).get("h")
            chord_b = (before_u.get("cplChordGrid") or {}).get("h")
            vp_out["custom"] = {
                "before_chord_h": chord_b,
                "after_chord_h": chord_a,
                "chord_cols_after": after_u.get("chordCols"),
                "before_scroll_h": before_u.get("scrollH"),
                "after_scroll_h": after_u.get("scrollH"),
                "hOverflow": after_u.get("hOverflow"),
                "chord_reduction_pct": (
                    round(100 * (1 - chord_a / chord_b), 1)
                    if chord_b and chord_a
                    else None
                ),
            }

            # Desktop: m4 marker should be empty / unused at 1280
            if not phone:
                vp_out["desktop_m4_marker"] = after.get("m4") or ""
                vp_out["desktop_h_overflow"] = after.get("hOverflow")

            results["viewports"][vp_name] = vp_out

        browser.close()

    out_json = OUT / "m4_metrics.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

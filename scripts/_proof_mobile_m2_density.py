"""Mobile M2 browser proof — shared density chrome on representative pages.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_mobile_m2 python -m streamlit run streamlit_music_practice_app.py --server.port 8582
  python scripts/_proof_mobile_m2_density.py http://127.0.0.1:8582
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
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8582"
OUT = SCRIPTS / "evidence-mobile-m2"
OUT.mkdir(parents=True, exist_ok=True)

# page_id for studio_quick_nav_btn_* keys
PAGES = [
    ("practice", "practice"),
    ("picker", "picker"),
    ("backing", "backing"),
    ("creative", "creative"),
    ("composer", "composer"),
]


def click_quick_nav(page: Page, page_id: str) -> None:
    """Prefer keyed quick-nav Opens (avoids sidebar 'Practice'→'Practice Log')."""
    from walk_creative_backing_matrix import click_nav

    id_to_name = {
        "practice": "Practice",
        "picker": "Songs",
        "backing": "Backing",
        "creative": "Creative",
        "composer": "Compose",
    }
    page.evaluate("window.scrollTo(0,0)")
    wait(page, 300)
    sel = f'[class*="st-key-studio_quick_nav_btn_{page_id}"] button'
    loc = page.locator(sel)
    if loc.count() > 0:
        btn = loc.first
        try:
            btn.evaluate("node => node.scrollIntoView({block:'center'})")
            wait(page, 200)
            btn.click(timeout=8000, force=True)
            wait(page, 2200)
            return
        except Exception:
            pass
    click_nav(page, id_to_name.get(page_id, page_id))
    wait(page, 2200)


def _metrics(page: Page) -> dict:
    return page.evaluate(
        """() => {
          function box(sel) {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            if (r.height < 1 && r.width < 1) return null;
            return { h: Math.round(r.height), top: Math.round(r.top) };
          }
          const density = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-density').trim();
          const shell = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-nav-shell').trim();
          const scrollW = Math.max(
            document.body.scrollWidth, document.documentElement.scrollWidth);
          const clientW = window.innerWidth;
          const nav = document.querySelector('[class*="studio_quick_nav_panel"]');
          let contentY = null;
          if (nav) contentY = Math.round(nav.getBoundingClientRect().bottom + window.scrollY);
          const fieldsEl = document.querySelector('.ui-backing-setup-fields-row');
          return {
            clientW, clientH: window.innerHeight,
            density, shell,
            hOverflow: scrollW > clientW + 4,
            contentY,
            pageHead: box('.ui-page-head, [class*="ui-studio-script-header"]'),
            metaBadges: box('.ui-studio-meta-badges'),
            backingCtx: box('.ui-backing-setup-context'),
            practiceMeta: box('.ui-practice-meta-row'),
            practiceHead: box('.ui-practice-control-head'),
            creativeMeta: box('.ui-creative-song-meta'),
            hubActions: box('[class*="_hub_nav_actions"]'),
            softCard: box('.ui-card'),
            fieldsRow: fieldsEl ? {
              cols: getComputedStyle(fieldsEl).gridTemplateColumns,
              h: Math.round(fieldsEl.getBoundingClientRect().height),
            } : null,
            hubColW: [...document.querySelectorAll(
              '[class*="_hub_nav_actions"] [data-testid="stColumn"]'
            )].slice(0, 5).map(c => Math.round(c.getBoundingClientRect().width)),
          };
        }"""
    )


def _density_toggle_compare(page: Page) -> dict:
    """Measure key chrome with density on, then disable M2 style and remeasure."""
    before = page.evaluate(
        """() => {
          const sels = {
            pageHead: '.ui-page-head',
            scriptHead: '[class*="ui-studio-script-header"]',
            metaBadges: '.ui-studio-meta-badges',
            hubActions: '[class*="_hub_nav_actions"]',
            practiceHead: '.ui-practice-control-head',
            backingCtx: '.ui-backing-setup-context',
            card: '.ui-card',
          };
          const out = {};
          for (const [k, sel] of Object.entries(sels)) {
            const el = document.querySelector(sel);
            out[k] = el ? Math.round(el.getBoundingClientRect().height) : null;
          }
          out.density = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-density').trim();
          return out;
        }"""
    )
    page.evaluate(
        """() => {
          document.querySelectorAll('style[data-mpc-mobile-density]').forEach(s => s.remove());
        }"""
    )
    wait(page, 200)
    after_off = page.evaluate(
        """() => {
          const sels = {
            pageHead: '.ui-page-head',
            scriptHead: '[class*="ui-studio-script-header"]',
            metaBadges: '.ui-studio-meta-badges',
            hubActions: '[class*="_hub_nav_actions"]',
            practiceHead: '.ui-practice-control-head',
            backingCtx: '.ui-backing-setup-context',
            card: '.ui-card',
          };
          const out = {};
          for (const [k, sel] of Object.entries(sels)) {
            const el = document.querySelector(sel);
            out[k] = el ? Math.round(el.getBoundingClientRect().height) : null;
          }
          out.density = getComputedStyle(document.body)
            .getPropertyValue('--mpc-mobile-density').trim();
          return out;
        }"""
    )
    return {"with_density": before, "density_disabled": after_off}


def main() -> int:
    notes: list[str] = []
    result: dict[str, object] = {"ok": False, "viewports": {}, "compare390": None, "notes": notes}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        seed = browser.new_page(viewport={"width": 1280, "height": 900})
        seed.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(seed, 4500)
        expand_pages(seed)
        pick_song(seed, notes, "Perfect", "Pop")
        wait(seed, 2000)
        seed.close()

        for name, w, h in [
            ("phone360", 360, 740),
            ("phone390", 390, 844),
            ("phone430", 430, 932),
            ("desktop", 1280, 900),
        ]:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 4000)
            expand_pages(page)
            expand_sidebar(page)
            phone = w <= 720
            page_metrics: dict[str, object] = {}
            for file_stub, page_id in PAGES:
                click_quick_nav(page, page_id)
                page.evaluate("window.scrollTo(0,0)")
                wait(page, 500)
                m = _metrics(page)
                page.screenshot(path=str(OUT / f"{name}_{file_stub}.png"), full_page=False)
                page_metrics[file_stub] = m
                if name == "phone390" and page_id == "picker":
                    result["compare390"] = {
                        "page": "picker",
                        **_density_toggle_compare(page),
                    }
                    # Reload to restore density CSS for remaining pages
                    page.reload(wait_until="domcontentloaded", timeout=120000)
                    wait(page, 3500)
                    expand_pages(page)
                    expand_sidebar(page)
                    click_quick_nav(page, "picker")
            checks = {
                "density_shell": (not phone)
                or (page_metrics["practice"].get("density") == "m2-chrome-v1"),
                "desktop_no_density": (phone)
                or (not page_metrics["practice"].get("density")),
                "no_hoverflow": all(
                    not bool((page_metrics[k] or {}).get("hOverflow")) for k in page_metrics
                ),
                "m1_shell_still": (not phone)
                or (page_metrics["practice"].get("shell") == "m1-compact-3col"),
            }
            hub_w = (page_metrics.get("picker") or {}).get("hubColW") or []
            if phone and hub_w:
                checks["hub_wrap"] = all(cw < w * 0.62 for cw in hub_w if cw > 0)
            fields = (page_metrics.get("backing") or {}).get("fieldsRow")
            if phone and fields and fields.get("cols"):
                col_s = str(fields["cols"])
                checks["fields_2col"] = col_s.count("fr") >= 2 and "100%" not in col_s
            result["viewports"][name] = {"pages": page_metrics, "checks": checks}
            notes.append(f"{name}: checks={checks}")
            page.close()
        browser.close()

    all_checks = []
    for vp in result["viewports"].values():
        all_checks.extend((vp.get("checks") or {}).values())
    result["ok"] = bool(all_checks) and all(bool(c) for c in all_checks)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

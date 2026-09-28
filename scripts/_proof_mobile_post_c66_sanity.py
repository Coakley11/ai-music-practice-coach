"""Post-c66 / M1+M2 browser sanity — density + nav shells at phone + desktop.

Usage:
  python scripts/_proof_mobile_post_c66_sanity.py http://127.0.0.1:8583
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import click_nav, expand_sidebar  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8583"
OUT = SCRIPTS / "evidence-mobile-post-c66"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    notes: list[str] = []
    result: dict[str, object] = {"ok": False, "viewports": {}, "notes": notes}
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
            click_nav(page, "Songs")
            wait(page, 2200)
            page.evaluate("window.scrollTo(0,0)")
            wait(page, 400)
            m = page.evaluate(
                """() => {
                  const scrollW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
                  return {
                    density: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-density').trim(),
                    shell: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-nav-shell').trim(),
                    hOverflow: scrollW > window.innerWidth + 4,
                    hubColW: [...document.querySelectorAll('[class*="_hub_nav_actions"] [data-testid="stColumn"]')]
                      .slice(0,4).map(c => Math.round(c.getBoundingClientRect().width)),
                    navH: (() => {
                      const nav = document.querySelector('[class*="studio_quick_nav_panel"]');
                      return nav ? Math.round(nav.getBoundingClientRect().height) : null;
                    })(),
                  };
                }"""
            )
            page.screenshot(path=str(OUT / f"{name}_songs.png"), full_page=False)
            phone = w <= 720
            checks = {
                "density": (not phone) or (m.get("density") == "m2-chrome-v1"),
                "shell": (not phone) or (m.get("shell") == "m1-compact-3col"),
                "desktop_clean": (phone)
                or ((not m.get("density")) and (not m.get("shell"))),
                "no_hoverflow": not bool(m.get("hOverflow")),
                "nav_compact": (not phone) or (int(m.get("navH") or 999) < 400),
            }
            if phone and m.get("hubColW"):
                checks["hub_wrap"] = all(cw < w * 0.62 for cw in m["hubColW"] if cw > 0)
            result["viewports"][name] = {"metrics": m, "checks": checks}
            notes.append(f"{name}: {checks} metrics={m}")
            page.close()
        browser.close()

    all_c = [c for vp in result["viewports"].values() for c in (vp.get("checks") or {}).values()]
    result["ok"] = bool(all_c) and all(bool(x) for x in all_c)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

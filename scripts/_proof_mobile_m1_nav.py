"""Mobile M1 browser proof — compact nav height + BF dock + desktop regression.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_mobile_m1 python -m streamlit run streamlit_music_practice_app.py --server.port 8581
  python scripts/_proof_mobile_m1_nav.py http://127.0.0.1:8581
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import click_nav, expand_sidebar  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8581"
OUT = SCRIPTS / "evidence-mobile-m1"
OUT.mkdir(parents=True, exist_ok=True)

BEFORE_NAV_H = 828  # audit baseline


def _metrics(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const nav = document.querySelector('.st-key-studio_quick_nav_panel')
            || document.querySelector('[class*="studio_quick_nav_panel"]');
          let navH = 0, navTop = null, navBottom = null;
          if (nav) {
            const r = nav.getBoundingClientRect();
            navH = Math.round(r.height);
            navTop = Math.round(r.top);
            navBottom = Math.round(r.bottom);
          }
          const back = document.querySelector('[class*="st-key-studio_nav_back_btn"] .stButton');
          const fwd = document.querySelector('[class*="st-key-studio_nav_forward_btn"] .stButton');
          function box(el) {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { top: Math.round(r.top), bottom: Math.round(r.bottom),
                     left: Math.round(r.left), right: Math.round(r.right) };
          }
          const backB = box(back);
          const fwdB = box(fwd);
          const opens = [...document.querySelectorAll('[class*="st-key-studio_quick_nav_btn_"] button')]
            .filter(b => b.offsetParent);
          let overlapOpen = false;
          for (const b of opens) {
            const r = b.getBoundingClientRect();
            for (const hb of [backB, fwdB]) {
              if (!hb) continue;
              const hit = !(r.right < hb.left || r.left > hb.right || r.bottom < hb.top || r.top > hb.bottom);
              if (hit) overlapOpen = true;
            }
          }
          const shell = getComputedStyle(document.body).getPropertyValue('--mpc-mobile-nav-shell').trim();
          const scrollW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth);
          const clientW = window.innerWidth;
          // First non-nav main heading / deck after nav
          let contentY = null;
          const main = document.querySelector('section[data-testid="stMain"]');
          if (main && nav) {
            contentY = Math.round(nav.getBoundingClientRect().bottom + window.scrollY);
          }
          return {
            clientW, clientH: window.innerHeight,
            navH, navTop, navBottom, contentY,
            shell, overlapOpen,
            hOverflow: scrollW > clientW + 4,
            backB, fwdB,
            openCount: opens.length,
          };
        }"""
    )


def main() -> int:
    notes: list[str] = []
    result: dict[str, object] = {"ok": False, "before_navH": BEFORE_NAV_H, "viewports": {}, "notes": notes}
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
            click_nav(page, "Practice")
            wait(page, 2500)
            m = _metrics(page)
            page.screenshot(path=str(OUT / f"{name}_practice.png"), full_page=False)
            # Visit another page to exercise nav
            click_nav(page, "Backing")
            wait(page, 2200)
            m2 = _metrics(page)
            page.screenshot(path=str(OUT / f"{name}_backing.png"), full_page=False)
            click_nav(page, "Practice")
            wait(page, 1800)
            phone = w <= 720
            checks = {
                "nav_reduced": (not phone) or (int(m.get("navH") or 0) < 400),
                "shell": (not phone) or (m.get("shell") == "m1-compact-3col"),
                "no_overlap": not bool(m.get("overlapOpen")),
                "no_hoverflow": not bool(m.get("hOverflow")),
                "opens_present": int(m.get("openCount") or 0) >= 8,
                "desktop_no_shell": (phone) or (not m.get("shell")),
            }
            # Desktop: mid-height BF. Phone: bottom dock, or mid-side fallback when
            # compact nav still occupies the lower viewport (short phones).
            if phone and m.get("backB"):
                top = int(m["backB"]["top"])
                checks["bf_clear_zone"] = (top > int(h) * 0.55) or (0.25 * h < top < 0.5 * h)
            if not phone and m.get("backB"):
                checks["bf_mid"] = abs(int(m["backB"]["top"]) - int(h) * 0.5) < 120
            result["viewports"][name] = {
                "metrics_practice": m,
                "metrics_backing": m2,
                "checks": checks,
                "reduction_pct": round(
                    100 * (1 - (int(m.get("navH") or 0) / BEFORE_NAV_H)), 1
                )
                if phone
                else None,
            }
            notes.append(
                f"{name}: navH={m.get('navH')} shell={m.get('shell')!r} "
                f"overlap={m.get('overlapOpen')} checks={checks}"
            )
            page.close()
        browser.close()

    all_checks = []
    for vp in result["viewports"].values():
        all_checks.extend((vp.get("checks") or {}).values())
    result["ok"] = all(bool(c) for c in all_checks)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

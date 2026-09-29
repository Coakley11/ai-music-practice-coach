# -*- coding: utf-8 -*-
"""Mobile M7 focused proof: Creative/Karaoke/Practice + seeded score (360/390/430/1280)."""
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

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8597"
OUT = SCRIPTS / "evidence-mobile-m7"
OUT.mkdir(parents=True, exist_ok=True)

print("M7 proof start", URL, flush=True)


def wait_ready(page, timeout_ms: int = 40000) -> None:
    elapsed = 0
    while elapsed < timeout_ms:
        ready = page.evaluate(
            """() => !!(
              document.querySelector('[class*="st-key-studio_quick_nav_btn_"]')
              || document.querySelector('.ui-studio-script-header')
              || (document.querySelector('section[data-testid="stSidebar"]')
                  && document.querySelector('section[data-testid="stSidebar"]').offsetWidth > 40)
            )"""
        )
        if ready:
            return
        wait(page, 1200)
        elapsed += 1200
        expand_sidebar(page)


def click_quick_nav_open(page, page_id: str) -> bool:
    wrap = page.locator(f'[class*="st-key-studio_quick_nav_btn_{page_id}"]')
    if wrap.count() == 0:
        return False
    try:
        wrap.first.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    wait(page, 250)
    btns = wrap.first.locator("button")
    for i in range(min(btns.count(), 4)):
        btn = btns.nth(i)
        try:
            if not btn.is_visible():
                continue
            box = btn.bounding_box()
            if not box or box["width"] < 2:
                continue
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            wait(page, 4500)
            return True
        except Exception:
            continue
    return False


def ensure_improv_lab(page) -> bool:
    if page.locator('[class*="st-key-creative_studio_panel"]').count():
        return True
    set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence") or set_baseweb_select(
        page, "Analysis mode", "Improvisation Lab"
    )
    wait(page, 3500)
    return page.locator('[class*="st-key-creative_studio_panel"]').count() > 0


def open_page(page, page_id: str, label: str, marker: str) -> bool:
    if click_quick_nav_open(page, page_id) and page.locator(marker).count():
        if page_id == "creative":
            ensure_improv_lab(page)
        return page.locator(marker).count() > 0
    click_nav(page, label)
    wait(page, 3500)
    if page_id == "creative":
        ensure_improv_lab(page)
    if page.locator(marker).count():
        return True
    for alt in {
        "creative": ["Creative Lab", "Creative"],
        "karaoke": ["Karaoke"],
        "practice": ["Practice"],
        "composer": ["Composition Studio", "Compose"],
    }.get(page_id, [label]):
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=re.compile(re.escape(alt), re.I)
            ).last.click(timeout=2000)
            wait(page, 4000)
            if page_id == "creative":
                ensure_improv_lab(page)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    return page.locator(marker).count() > 0


def disable_m7(page) -> None:
    page.evaluate(
        """() => {
          document.querySelectorAll('style[data-mpc-mobile-m7]').forEach((s) => s.remove());
          document.body.style.removeProperty('--mpc-mobile-m7');
        }"""
    )


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
            return { h: Math.round(r.height), w: Math.round(r.width) };
          };
          return {
            mainScrollH: contentH,
            screens: +(contentH / fold).toFixed(2),
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            m6: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m6').trim(),
            m7: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m7').trim(),
            creative: box('[class*="st-key-creative_studio_panel"]'),
            motifSetupQc: box('[class*="st-key-improv_motif_setup_qc_row"]'),
            missionQc: box('[class*="st-key-improv_mission_qc_row"]'),
            liveCoachQc: box('[class*="st-key-improv_live_coach_qc_row"]'),
            liveInsight: box('[class*="st-key-improv_live_coach_insight_row"]'),
            jamControls: box('[class*="st-key-improv_style_jam_controls"]'),
            karaokePanel: box('.karaoke-lyric-panel'),
            karaokeStage: box('[class*="st-key-karaoke_stage"]'),
            practiceSub: (document.querySelector('.ui-practice-control-sub') || {}).textContent || '',
            score: box('.composer-score-wrap'),
          };
        }"""
    )


def proof_seeded_score(browser, vp_name: str, vp: dict) -> dict:
    from composition_melody_notation import build_abc_from_melody_events, render_abc_html

    events = [
        {"pitch": p, "duration_beats": d, "is_rest": False}
        for p, d in [
            ("C4", 1), ("E4", 1), ("G4", 1), ("C5", 1),
            ("D4", 1), ("F4", 1), ("A4", 1), ("G4", 1),
            ("E4", 2), ("C4", 2),
            ("G4", 1), ("A4", 1), ("B4", 1), ("C5", 1),
            ("A4", 2), ("G4", 2),
        ]
    ]
    abc = build_abc_from_melody_events(events, key="C", meter="4/4", bpm=100, title="M7 Live Score")
    inner = render_abc_html(abc, height=260)
    html_path = OUT / f"seeded_score_{vp_name}.html"
    html_path.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html,body{{margin:0;padding:0;overflow-x:hidden;background:#f8fafc}}
.composer-score-wrap{{padding:.32rem;margin:.5rem;max-width:100%;overflow-x:auto;
box-sizing:border-box;border:1px solid #cbd5e1;border-radius:10px;background:#fff}}
.composer-score-wrap iframe{{max-width:100%;width:100%;border:0}}
</style></head><body>
<div class="composer-score-wrap"><iframe id="f" height="280" style="width:100%;max-width:100%;border:0"></iframe></div>
<script>
const f=document.getElementById('f');
f.srcdoc = {json.dumps(inner)};
</script></body></html>""",
        encoding="utf-8",
    )
    page = browser.new_page(viewport=vp)
    page.goto(html_path.as_uri(), wait_until="domcontentloaded", timeout=60000)
    wait(page, 1600)
    metrics = page.evaluate(
        """() => {
          const wrap = document.querySelector('.composer-score-wrap');
          const r = wrap.getBoundingClientRect();
          return {
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            clipOffscreen: r.right > window.innerWidth + 6 || r.left < -6,
            wrapW: Math.round(r.width),
            vw: window.innerWidth,
            hasSvg: !!document.querySelector('#f') ,
          };
        }"""
    )
    # Check iframe SVG width vs viewport via frame
    try:
        frame = page.frame_locator("#f")
        svg_w = page.evaluate(
            """() => {
              const f = document.getElementById('f');
              try {
                const svg = f.contentDocument && f.contentDocument.querySelector('svg');
                if (!svg) return null;
                const r = svg.getBoundingClientRect();
                return { w: Math.round(r.width), overflow:
                  Math.max(f.contentDocument.body.scrollWidth, f.contentDocument.documentElement.scrollWidth)
                  > f.contentWindow.innerWidth + 4 };
              } catch (e) { return { err: String(e) }; }
            }"""
        )
        metrics["iframeSvg"] = svg_w
    except Exception as exc:
        metrics["iframeSvg"] = {"err": str(exc)}
    page.screenshot(path=str(OUT / f"after_{vp_name}_seeded_score.png"), full_page=True)
    page.close()
    print(f"  seeded_score {vp_name}: {metrics}", flush=True)
    return metrics


TARGETS = [
    ("creative", "Creative", '[class*="st-key-creative_studio_panel"], [class*="st-key-creative_lab"]'),
    ("karaoke", "Karaoke", '[class*="st-key-karaoke_stage"], .karaoke-lyric-panel, [class*="st-key-karaoke"]'),
    ("practice", "Practice", '[class*="st-key-practice_control_panel"], .ui-practice-control-head'),
]


def main() -> int:
    results = {"url": URL, "viewports": {}, "seeded_score": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp_name, vp in (
            ("360", {"width": 360, "height": 740}),
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            print(f"== viewport {vp_name} ==", flush=True)
            phone = vp["width"] <= 720
            results["seeded_score"][vp_name] = proof_seeded_score(browser, vp_name, vp)
            assert results["seeded_score"][vp_name]["hOverflow"] is False
            assert results["seeded_score"][vp_name]["clipOffscreen"] is False

            vp_out = {}
            for page_id, label, marker in TARGETS:
                print(f"  open {page_id}…", flush=True)
                page = browser.new_page(viewport=vp)
                page.goto(URL, wait_until="domcontentloaded", timeout=120000)
                wait(page, 4500)
                expand_sidebar(page)
                expand_pages(page)
                wait_ready(page)
                landed = open_page(page, page_id, label, marker)
                wait(page, 800)

                before = None
                if phone:
                    disable_m7(page)
                    wait(page, 150)
                    before = measure(page)
                    page.screenshot(path=str(OUT / f"before_{vp_name}_{page_id}.png"), full_page=True)
                    page.reload(wait_until="domcontentloaded", timeout=120000)
                    wait(page, 4000)
                    expand_sidebar(page)
                    expand_pages(page)
                    wait_ready(page)
                    open_page(page, page_id, label, marker)
                    wait(page, 800)

                if page_id == "creative" and landed:
                    for sub in ("Entry & Jam", "Missions", "Phrase / Motif", "Live Coach"):
                        try:
                            click_radio(page, sub) or click_label(page, sub)
                            wait(page, 2200)
                            page.screenshot(
                                path=str(OUT / f"after_{vp_name}_creative_{sub.split()[0].lower()}.png"),
                                full_page=True,
                            )
                        except Exception as exc:
                            print(f"    sub {sub} skip: {exc}", flush=True)

                after = measure(page)
                page.screenshot(path=str(OUT / f"after_{vp_name}_{page_id}.png"), full_page=True)
                entry = {"landed": landed, "after": after}
                if before is not None:
                    entry["before"] = before
                    entry["deltaScrollH"] = (before.get("mainScrollH") or 0) - (after.get("mainScrollH") or 0)
                print(
                    f"  {page_id}: landed={landed} scroll={after.get('mainScrollH')} "
                    f"m7={after.get('m7')!r} hOverflow={after.get('hOverflow')} "
                    f"delta={entry.get('deltaScrollH')}",
                    flush=True,
                )
                if phone:
                    assert after.get("hOverflow") is False, (vp_name, page_id, after)
                    assert after.get("m7") == "m7-finish-density-v1", after
                if page_id == "practice" and landed:
                    sub = (after.get("practiceSub") or "").strip()
                    assert "Session goal, key behavior, and section focus" in sub, sub
                    assert "Groove and length" not in sub, sub
                vp_out[page_id] = entry
                page.close()

            results["viewports"][vp_name] = vp_out

        browser.close()

    out_path = OUT / "m7_after_metrics.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"seeded_score": results["seeded_score"], "summary": {
        vp: {pid: {"landed": e["landed"], "deltaScrollH": e.get("deltaScrollH"),
                   "screens": e["after"].get("screens"), "m7": e["after"].get("m7")}
             for pid, e in pages.items()}
        for vp, pages in results["viewports"].items()
    }}, indent=2), flush=True)
    print(f"Wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

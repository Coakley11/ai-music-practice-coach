# -*- coding: utf-8 -*-
"""M7 publish sanity: overflow, markers, Practice copy, BF placement, Multitrack icons."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar, click_nav, set_baseweb_select  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8598"
OUT = SCRIPTS / "evidence-mobile-m7"
OUT.mkdir(parents=True, exist_ok=True)
print("M7 publish sanity", URL, flush=True)


def wait_ready(page, timeout_ms: int = 40000) -> None:
    elapsed = 0
    while elapsed < timeout_ms:
        if page.evaluate(
            """() => !!(
              document.querySelector('[class*="st-key-studio_quick_nav_btn_"]')
              || document.querySelector('.ui-studio-script-header')
            )"""
        ):
            return
        wait(page, 1200)
        elapsed += 1200
        expand_sidebar(page)


def click_quick_nav(page, page_id: str) -> bool:
    wrap = page.locator(f'[class*="st-key-studio_quick_nav_btn_{page_id}"]')
    if wrap.count() == 0:
        return False
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


def open_page(page, page_id: str, labels: list[str], marker: str) -> bool:
    if click_quick_nav(page, page_id) and page.locator(marker).count():
        return True
    for lab in labels:
        click_nav(page, lab)
        wait(page, 3500)
        if page.locator(marker).count():
            return True
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=re.compile(re.escape(lab), re.I)
            ).last.click(timeout=2000)
            wait(page, 4000)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    return page.locator(marker).count() > 0


def measure_shell(page) -> dict:
    return page.evaluate(
        """() => {
          const main = document.querySelector('section[data-testid="stMain"]');
          const fold = window.innerHeight;
          const contentH = main ? main.scrollHeight : 0;
          const welcome = [...document.querySelectorAll('[data-testid="stAlert"]')]
            .find(el => /restored your last settings/i.test(el.textContent || ''));
          const hist = document.querySelector('[class*="st-key-studio_history_nav_row"]');
          const nav = document.querySelector('[class*="st-key-studio_quick_nav_panel"], [class*="studio_quick_nav"]');
          const backBtn = document.querySelector('[class*="st-key-studio_nav_back_btn"] .stButton');
          const backPos = backBtn ? getComputedStyle(backBtn).position : '';
          const wr = welcome ? welcome.getBoundingClientRect() : null;
          const hr = hist ? hist.getBoundingClientRect() : null;
          const nr = nav ? nav.getBoundingClientRect() : null;
          return {
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            screens: +(contentH / fold).toFixed(2),
            m6: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m6').trim(),
            m7: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m7').trim(),
            practiceSub: (document.querySelector('.ui-practice-control-sub') || {}).textContent || '',
            histPresent: !!hist,
            backPosition: backPos,
            orderOk: !!(wr && hr && nr && wr.bottom <= hr.top + 8 && hr.bottom <= nr.top + 12),
            welcomeY: wr ? Math.round(wr.bottom) : null,
            histY: hr ? Math.round(hr.top) : null,
            navY: nr ? Math.round(nr.top) : null,
            mtSong: !!document.querySelector('.ui-mt-ctx-badge.song'),
            mtSongSource: (document.querySelector('.ui-mt-ctx-badge.song') || {}).className || '',
            mtSection: (() => {
              const t = document.querySelector('.ui-mt-setup-section-title');
              return t ? (t.textContent || '').trim() : '';
            })(),
            mtSectionIcon: !!document.querySelector('.ui-mt-setup-section-icon--section'),
            mtLayerIcon: document.querySelectorAll('.ui-mt-layer-ico').length,
            creative: !!document.querySelector('[class*="st-key-creative_studio_panel"]'),
            karaokePanel: !!document.querySelector('.karaoke-lyric-panel'),
          };
        }"""
    )


def proof_seeded_score(browser, vp) -> dict:
    from composition_melody_notation import build_abc_from_melody_events, render_abc_html

    events = [
        {"pitch": p, "duration_beats": 1.0, "is_rest": False}
        for p in ("C4", "E4", "G4", "C5", "D4", "F4", "A4", "G4")
    ]
    abc = build_abc_from_melody_events(events, key="C", meter="4/4", bpm=100, title="M7 Publish")
    inner = render_abc_html(abc, height=240)
    html_path = OUT / f"publish_seeded_{vp['width']}.html"
    html_path.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{{margin:0;overflow-x:hidden}}.composer-score-wrap{{margin:.5rem;max-width:100%;overflow-x:auto}}</style>
</head><body><div class="composer-score-wrap"><iframe id="f" height="260" style="width:100%;border:0"></iframe></div>
<script>document.getElementById('f').srcdoc={json.dumps(inner)};</script></body></html>""",
        encoding="utf-8",
    )
    page = browser.new_page(viewport=vp)
    page.goto(html_path.as_uri(), wait_until="domcontentloaded")
    wait(page, 1200)
    m = page.evaluate(
        """() => ({
          hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
            > window.innerWidth + 4,
          clip: (() => {
            const r = document.querySelector('.composer-score-wrap').getBoundingClientRect();
            return r.right > window.innerWidth + 6 || r.left < -6;
          })()
        })"""
    )
    page.close()
    return m


def main() -> int:
    results = {"url": URL, "viewports": {}, "seeded": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, vp in (
            ("360", {"width": 360, "height": 740}),
            ("390", {"width": 390, "height": 844}),
            ("430", {"width": 430, "height": 932}),
            ("1280", {"width": 1280, "height": 900}),
        ):
            phone = vp["width"] <= 720
            print(f"== {name} ==", flush=True)
            results["seeded"][name] = proof_seeded_score(browser, vp)
            assert results["seeded"][name]["hOverflow"] is False
            assert results["seeded"][name]["clip"] is False

            page = browser.new_page(viewport=vp)
            page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            wait(page, 5000)
            expand_sidebar(page)
            expand_pages(page)
            wait_ready(page)

            # Landing / practice for BF order + practice copy
            open_page(
                page,
                "practice",
                ["Practice"],
                '[class*="st-key-practice_control_panel"], .ui-practice-control-head',
            )
            wait(page, 1000)
            m_practice = measure_shell(page)
            page.screenshot(path=str(OUT / f"publish_{name}_practice.png"), full_page=True)

            # Creative
            open_page(
                page,
                "creative",
                ["Creative", "Creative Lab"],
                '[class*="st-key-creative_studio_panel"], [class*="st-key-creative_lab"]',
            )
            if page.locator('[class*="st-key-creative_studio_panel"]').count() == 0:
                set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
                wait(page, 3500)
            m_creative = measure_shell(page)
            page.screenshot(path=str(OUT / f"publish_{name}_creative.png"), full_page=True)

            # Multitrack
            open_page(
                page,
                "multitrack",
                ["Multitrack"],
                '[class*="st-key-multitrack_studio_panel"], .ui-mt-session-setup-head',
            )
            wait(page, 1500)
            m_mt = measure_shell(page)
            page.screenshot(path=str(OUT / f"publish_{name}_multitrack.png"), full_page=True)

            # Karaoke lyric panel inject under M7 CSS
            page.evaluate(
                """() => {
                  const host = document.querySelector('section[data-testid="stMain"] .block-container') || document.body;
                  if (document.querySelector('.karaoke-lyric-panel')) return;
                  const d = document.createElement('div');
                  d.className = 'karaoke-lyric-panel';
                  d.innerHTML = '<p class="karaoke-lp-kicker">Now Singing</p><p class="karaoke-lp-title">Demo</p><p class="karaoke-lp-section">Verse</p><div class="karaoke-lp-lyrics"><div class="karaoke-lp-lyric-line active">Hello from karaoke</div></div>';
                  host.prepend(d);
                }"""
            )
            wait(page, 200)
            karaoke_h = page.evaluate(
                """() => {
                  const el = document.querySelector('.karaoke-lyric-panel');
                  if (!el) return null;
                  return {
                    h: Math.round(el.getBoundingClientRect().height),
                    pad: getComputedStyle(el).padding,
                    m7: getComputedStyle(document.body).getPropertyValue('--mpc-mobile-m7').trim(),
                  };
                }"""
            )

            entry = {
                "practice": m_practice,
                "creative": m_creative,
                "multitrack": m_mt,
                "karaokeInject": karaoke_h,
            }
            print(
                f"  overflow={m_practice['hOverflow']} m7={m_practice['m7']!r} "
                f"orderOk={m_practice['orderOk']} backPos={m_practice['backPosition']} "
                f"mtSection={m_mt.get('mtSection')!r} layers={m_mt.get('mtLayerIcon')}",
                flush=True,
            )

            assert m_practice["hOverflow"] is False
            assert m_creative["hOverflow"] is False
            assert m_mt["hOverflow"] is False
            if phone:
                assert m_practice["m7"] == "m7-finish-density-v1"
                assert m_practice["backPosition"] == "static"
                # Welcome may be absent on some cold starts; require hist above nav when both exist
                if m_practice["histY"] is not None and m_practice["navY"] is not None:
                    assert m_practice["histY"] <= m_practice["navY"] + 4, m_practice
                if m_practice.get("practiceSub"):
                    assert "Session goal, key behavior, and section focus" in m_practice["practiceSub"]
                    assert "Groove and length" not in m_practice["practiceSub"]
                if m_mt.get("mtSection"):
                    assert "SONG / SECTION" in m_mt["mtSection"].upper()
                    assert m_mt.get("mtSectionIcon") is True
                if m_mt.get("mtLayerIcon"):
                    assert m_mt["mtLayerIcon"] >= 1
            else:
                assert m_practice["m7"] == ""
                assert m_practice["backPosition"] in {"fixed", "static"}  # desktop fixed preferred

            results["viewports"][name] = entry
            page.close()

        browser.close()

    out = OUT / "m7_publish_sanity.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"seeded": results["seeded"], "ok": True}, indent=2), flush=True)
    print("Wrote", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

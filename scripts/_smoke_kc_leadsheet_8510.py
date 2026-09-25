"""Smoke: cycle ON audio + real lead sheet, no raw grid. Leave Off."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS"):
    os.environ.pop(k, None)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "leadsheet_smoke_report.json"


def main() -> int:
    out: dict = {}
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(800)
        for _ in range(8):
            goto_studio(page, "Backing")
            page.wait_for_timeout(1500)
            if "Play Backing Track" in (page.inner_text("body") or ""):
                break
        out["on_backing"] = "Play Backing Track" in (page.inner_text("body") or "")
        set_cycle_mode(page, True)
        click_play(page)
        audio = wait_kc_audio(page, 180)
        if not audio.get("ok"):
            click_play(page)
            audio = wait_kc_audio(page, 120)
        out["audio"] = audio
        try:
            page.get_by_role("button", name="Open lead sheet").click(timeout=4000)
            page.wait_for_timeout(1200)
        except Exception:
            pass
        chart = page.evaluate(
            """() => {
              const sheet = document.querySelector('.backing-chart-sheet, .lead-sheet');
              const raw = !!document.querySelector(
                '.kc-chart-full, #kc-full-chart-host, #kc-chart-live, .kc-chord-cell'
              );
              const cells = sheet
                ? [...sheet.querySelectorAll('.live-chart-cell, .chord-cell')]
                : [];
              return {
                has_lead_sheet: !!sheet,
                cell_count: cells.length,
                has_raw_grid: raw,
                sample: cells.slice(0, 8).map(
                  (c) => (c.textContent || '').replace(/\\s+/g, ' ').trim()
                ),
              };
            }"""
        )
        out["chart"] = chart
        out["sounding"] = cycle_ui(page).get("sounding")
        out["duration"] = audio.get("duration")
        set_cycle_mode(page, False)
        page.wait_for_timeout(900)
        out["left_off"] = not bool(cycle_ui(page).get("playbar"))
        b.close()
    out["ok"] = bool(
        out.get("on_backing")
        and (out.get("audio") or {}).get("ok")
        and (out.get("chart") or {}).get("has_lead_sheet")
        and not (out.get("chart") or {}).get("has_raw_grid")
        and float(out.get("duration") or 0) > 20
        and out.get("left_off")
    )
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("SMOKE_OK", out["ok"])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

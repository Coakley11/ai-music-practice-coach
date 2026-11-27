# -*- coding: utf-8 -*-
"""Why did the guided path reach Melody without chords? Print what each step actually offers."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from _browser_composition_recorder_accept import (  # noqa: E402
    body_text,
    click_key,
    click_text,
    fill_key,
    open_composer,
    settle,
    wait_ready,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8611"


def keys(page, pattern: str) -> list[str]:
    found = page.evaluate(
        """() => Array.from(document.querySelectorAll('[class*="st-key-"]'))
              .flatMap(e => Array.from(e.classList))
              .filter(c => c.startsWith('st-key-'))"""
    )
    uniq = sorted(set(found))
    return [k for k in uniq if re.search(pattern, k)]


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(20000)
        page.goto(URL, wait_until="domcontentloaded")
        wait_ready(page)
        settle(page, 4.0)
        print("composer opens:", open_composer(page))

        fill_key(page, "composer_welcome_idea", "A short flute line over a D major vamp.")
        fill_key(page, "composer_welcome_bpm", "96")
        print("begin clicked:", click_text(page, r"Begin your song", settle_s=5.0))
        print("  phase keys:", keys(page, r"composer_(vision|structure|journey)")[:12])

        print("vision continue:", click_key(page, "composer_vision_continue", settle_s=5.0))
        print("  keys now:", keys(page, r"composer_(tpl|structure)")[:12])

        print("template simple:", click_key(page, "composer_tpl_simple", settle_s=5.0))
        print("structure continue:", click_key(page, "composer_structure_continue", settle_s=6.0))

        print("\n--- after Continue to Chords ---")
        print("  paste keys   :", keys(page, r"composer_paste"))
        print("  chord keys   :", keys(page, r"composer_ch_")[:14])
        print("  section keys :", keys(page, r"composer_(section|align)")[:10])
        print("  journey keys :", keys(page, r"composer_journey"))
        txt = body_text(page)
        print("  body head    :", " | ".join(t.strip() for t in txt.splitlines()[:14] if t.strip()))

        print("\n--- via the journey rail to Chords ---")
        print("journey chords:", click_key(page, "composer_journey_chords", settle_s=6.0))
        print("  paste keys :", keys(page, r"composer_paste"))
        print("  chord keys :", keys(page, r"composer_ch_")[:16])
        print("  all keys   :", keys(page, r"composer_")[:40])
        t2 = body_text(page)
        print("  body       :", " | ".join(x.strip() for x in t2.splitlines()[:20] if x.strip()))

        page.screenshot(path=str(SCRIPTS / "evidence-composition-recorder" / "probe-chords-step.png"))
        ctx.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

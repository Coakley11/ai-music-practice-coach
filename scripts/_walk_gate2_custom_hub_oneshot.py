"""Dedicated Gate-2 one-shot: Trial GA C / Custom hub → Use catalog → Shape once.

Usage:
  python scripts/_walk_gate2_custom_hub_oneshot.py http://127.0.0.1:8916
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8916"


def main() -> int:
    from walk_creative_backing_matrix import click_button_has, click_nav
    from _walk_core_key_coherence import set_songs_practice_key
    from _walk_ownership_audit_full import build_trial_song
    from _walk_owner_key_tuple import (
        custom_hub_to_catalog_song,
        log,
        settle,
        songs_hub_state,
        wait_trial_custom_ga,
    )

    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)
        from _walk_owner_key_tuple import wait_for_studio_ready

        init = wait_for_studio_ready(page)
        print(f"init={json.dumps(init)}", flush=True)
        if not init.get("ok"):
            print("OVERALL=FAIL init", flush=True)
            browser.close()
            return 1
        ok = build_trial_song(page, notes)
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        trial_ga = wait_trial_custom_ga(page)
        click_nav(page, "Songs")
        settle(page, 3)
        set_songs_practice_key(page, "C")
        settle(page, 2)
        before = songs_hub_state(page)
        print(f"seed_ok={ok} trial_ga={trial_ga} before={json.dumps(before, default=str)}", flush=True)
        print("notes=" + " | ".join(notes[-8:]), flush=True)
        g2 = custom_hub_to_catalog_song(page, notes, "Shape of You")
        after = songs_hub_state(page)
        print(f"g2={json.dumps(g2, default=str)}", flush=True)
        print(f"after={json.dumps(after, default=str)}", flush=True)
        case_b = False
        if g2.get("ok"):
            from _walk_owner_key_tuple import click_sbi_song_source, land_sbi, wait_sbi_tuple
            from _walk_ownership_audit_full import rendered_em_em_d_d

            landed = land_sbi(page, notes)
            clicked = click_sbi_song_source(page, "custom") if landed else False
            case_b = bool(
                landed
                and clicked
                and wait_sbi_tuple(page, source="custom", title="Trial Song", d_major=True, em_d_prog=True)
            )
            print(f"case_b={case_b} landed={landed} clicked={clicked}", flush=True)
        browser.close()
        ok_all = bool(g2.get("ok") and after.get("ga_shape") and not after.get("ga_trial") and case_b)
        print("OVERALL=" + ("PASS" if ok_all else "FAIL"), flush=True)
        return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused live proof: Creative → Entry & Jam → Song-Based → Custom progression survives reboot."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    click_nav,
    creative_tab,
    disk_creative_slice,
    disk_studio_page,
    has_any,
    open_fresh,
    open_sbi_custom_source,
    page_family,
    pick_song,
    reboot_server,
    seed_trial_song_last_custom,
    settle,
    shot,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def wait_sbi_custom_disk(timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = disk_creative_slice()
        src = str(last.get("sbi_preview_source") or last.get("improv_song_source") or "")
        if last.get("studio_page") == "creative" and "Custom" in src:
            return last
        time.sleep(0.5)
    return last


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)

        seed_trial_song_last_custom(page, notes)
        pick_song(page, notes, "Shape of You", "Pop")
        assert open_sbi_custom_source(page, notes), f"open failed notes={notes}"
        settle(page, 4)
        click_nav(page, "Creative")
        settle(page, 3)
        pre_disk = wait_sbi_custom_disk()
        body_pre = shot(page, "nested-sbi-custom-pre")
        fam_pre = page_family(body_pre)
        assert fam_pre == "creative", f"left Creative before reboot: {fam_pre}"

        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, "nested-sbi-custom-post")
        fam = page_family(body)
        tab = creative_tab(body)
        disk = disk_studio_page()
        post_disk = disk_creative_slice()
        src = str(post_disk.get("sbi_preview_source") or post_disk.get("improv_song_source") or "")
        trial = has_any(body, "Trial Song")
        top_custom = has_any(body, "custom progression lab", "create your own song")
        ok = (
            fam == "creative"
            and disk == "creative"
            and tab == "sbi"
            and trial
            and not top_custom
            and "Custom" in src
        )
        report = {
            "ok": ok,
            "family": fam,
            "tab": tab,
            "disk": disk,
            "src": src,
            "trial": trial,
            "top_custom": top_custom,
            "pre_disk": pre_disk,
            "post_disk": post_disk,
            "notes": notes,
            "snippet": " ".join(body.split())[:500],
        }
        (OUT / "nested-sbi-custom-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        browser.close()
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

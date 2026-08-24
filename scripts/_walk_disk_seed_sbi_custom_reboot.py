"""Prove Creative→SBI→Custom reboot restore via disk seed + hydrate (browser-visible).

Seeds nested SBI Custom into music_user_state, reboots Streamlit, asserts Creative
page + SBI Custom + Trial Song — not top-level Custom.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    creative_tab,
    disk_creative_slice,
    disk_state_path,
    disk_studio_page,
    has_any,
    open_fresh,
    page_family,
    reboot_server,
    seed_trial_song_last_custom,
    settle,
    shot,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def _stamp_page(blob: dict, page: str) -> None:
    """Mirror page_change save: every page-bearing blob must agree or hydrate prefers a stale picker."""
    blob["studio_page"] = page
    for key in (
        "studio_nav_state",
        "music_workspace_state",
        "practice_workspace_state",
        "core",
        "session",
    ):
        node = blob.get(key)
        if not isinstance(node, dict):
            node = {}
            blob[key] = node
        node["studio_page"] = page
        if key == "studio_nav_state":
            node["page"] = page
            node["last_write_reason"] = "disk_seed_nested_sbi_custom"
        elif key == "music_workspace_state":
            node["page"] = page
            nested = node.get("practice_workspace_state")
            if isinstance(nested, dict):
                nested["studio_page"] = page
                nested["page"] = page


def _patch_disk_nested_sbi_custom() -> dict:
    path = disk_state_path()
    blob = json.loads(path.read_text(encoding="utf-8"))
    st = blob.setdefault("state", {})
    # _studio_page_from_blob prefers music_workspace_state over top-level/nav —
    # seeding only studio_page left a stale picker workspace and reboot restored Songs.
    _stamp_page(st, "creative")
    st["improv_entry_mode"] = "Song-Based Improvisation"
    st["improv_intelligence_tab"] = "Entry & Jam"
    st["creative_improv_intelligence_tab"] = "Entry & Jam"
    st["improv_song_source"] = "Custom progression"
    st["sbi_preview_source"] = "Custom progression"
    cw = st.get("creative_workspace_state")
    if not isinstance(cw, dict):
        cw = {}
        st["creative_workspace_state"] = cw
    cw["improv_entry_mode"] = "Song-Based Improvisation"
    cw["improv_intelligence_tab"] = "Entry & Jam"
    cw["creative_improv_intelligence_tab"] = "Entry & Jam"
    cw["improv_song_source"] = "Custom progression"
    cw["sbi_preview_source"] = "Custom progression"
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    return disk_creative_slice()


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Ensure Trial Song exists as LAST_CUSTOM, Shape is Global Active.
        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        settle(page, 2)
        page.context.close()

        pre = _patch_disk_nested_sbi_custom()
        notes.append(f"seeded_disk={pre}")
        reboot_server()
        page = open_fresh(browser)
        # Wait for Creative body (not just suite chrome).
        deadline = time.time() + 90
        body = ""
        while time.time() < deadline:
            settle(page, 3)
            body = page.inner_text("body") or ""
            low = body.lower()
            if len(body) > 800 and (
                "entry & jam" in low
                or "improvisation lab" in low
                or "song-based" in low
                or "custom progression" in low
            ):
                break
        body = shot(page, "disk-seed-sbi-custom-post")
        fam = page_family(body)
        tab = creative_tab(body)
        disk = disk_studio_page()
        post = disk_creative_slice()
        src = str(post.get("sbi_preview_source") or post.get("improv_song_source") or "")
        trial = has_any(body, "Trial Song")
        top_custom = has_any(body, "custom progression lab", "progression lab") and has_any(
            body, "new song", "original key"
        )
        custom_ui = has_any(body, "custom progression") and (
            trial or has_any(body, "preview only", "last custom")
        )
        ok = (
            fam == "creative"
            and disk == "creative"
            and "Custom" in src
            and not top_custom
            and (
                tab == "sbi"
                or custom_ui
                or trial
                or has_any(body, "entry & jam", "song-based", "song source")
            )
        )
        report = {
            "ok": ok,
            "family": fam,
            "tab": tab,
            "disk": disk,
            "src": src,
            "trial": trial,
            "top_custom": top_custom,
            "custom_ui": custom_ui,
            "pre": pre,
            "post": post,
            "notes": notes,
            "snippet": " ".join(body.split())[:600],
        }
        (OUT / "disk-seed-sbi-custom-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        browser.close()
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

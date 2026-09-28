"""Deterministic Monetization M2.5 browser acceptance.

Run this against a fresh local Streamlit runtime configured with:

    MUSIC_ENTITLEMENT_DEV_CONTROLS=1
    MUSIC_ENTITLEMENT_RUNTIME=test
    MUSIC_ENTITLEMENT_DEV_PLAN=free
    MUSIC_BILLING_ROLLOUT=preview

The script writes no evidence files.  Its JSON stdout is the acceptance record.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from playwright.sync_api import Page, sync_playwright


URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8602"
READY = '#music-startup-ready-marker[data-music-startup-ready="true"]'
STATE_ATTRS = (
    "data-song-title",
    "data-pick-key",
    "data-music-source",
    "data-practice-key",
    "data-studio-page",
    "data-entitlement-plan",
    "data-entitlement-status",
    "data-entitlement-source",
)


def ready_state(page: Page, *, timeout_ms: int = 90_000) -> dict[str, str]:
    page.wait_for_selector(READY, state="attached", timeout=timeout_ms)
    marker = page.locator("#music-startup-ready-marker").last
    return {
        name.removeprefix("data-"): str(marker.get_attribute(name) or "")
        for name in STATE_ATTRS
    }


def wait_for_state(page: Page, attribute: str, expected: str, *, timeout_ms: int = 60_000) -> None:
    page.wait_for_function(
        """([name, expected]) => {
          const markers = [...document.querySelectorAll('#music-startup-ready-marker')];
          const marker = markers.length ? markers[markers.length - 1] : null;
          return marker && marker.getAttribute(name) === expected;
        }""",
        arg=[attribute, expected],
        timeout=timeout_ms,
    )


def _expand_sidebar(page: Page) -> None:
    collapsed = page.locator('[data-testid="stSidebarCollapsedControl"] button')
    if collapsed.count() and collapsed.first.is_visible():
        collapsed.first.click()


def navigate(page: Page, *, page_id: str, key_suffix: str) -> None:
    if ready_state(page)["studio-page"] == page_id:
        return
    _expand_sidebar(page)
    target = page.locator(f".st-key-sb_nav_{key_suffix} button")
    if not (target.count() and target.first.is_visible()):
        pages = page.get_by_role("button", name=re.compile(r"Pages", re.I))
        for index in range(pages.count()):
            if pages.nth(index).is_visible():
                pages.nth(index).click()
                break
    target.wait_for(state="visible", timeout=20_000)
    target.click()
    wait_for_state(page, "data-studio-page", page_id)


def same_music_state(left: dict[str, str], right: dict[str, str]) -> bool:
    return all(
        left[key] == right[key]
        for key in ("song-title", "pick-key", "music-source", "practice-key")
    )


def run() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    states: dict[str, dict[str, str]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30_000)

        initial = ready_state(page)
        states["initial_free_practice"] = initial
        initial_body = page.locator("body").inner_text()
        checks["clean_first_song_ready"] = bool(initial["song-title"] and initial["pick-key"])
        checks["free_practice"] = (
            initial["studio-page"] == "practice"
            and initial["entitlement-plan"] == "free"
            and "Song Practice" in initial_body
        )

        navigate(page, page_id="composer", key_suffix="composer")
        page.wait_for_selector(
            '[data-monetization-locked-feature="composition_studio"]',
            timeout=60_000,
        )
        locked = ready_state(page)
        states["free_composition"] = locked
        checks["free_composition_gated"] = locked["entitlement-plan"] == "free"
        checks["music_state_into_gate"] = same_music_state(initial, locked)

        page.get_by_role("button", name=re.compile(r"Compare Free and Pro", re.I)).click()
        page.wait_for_selector('[data-monetization-pricing="m2"]', timeout=60_000)
        pricing = ready_state(page)
        states["m2_pricing"] = pricing
        pricing_body = page.locator("body").inner_text()
        checks["m2_pricing_surface"] = "Practice freely. Go Pro" in pricing_body
        checks["checkout_safely_disabled"] = (
            "Checkout not enabled" in pricing_body
            and "Billing enforcement and checkout are not enabled" in pricing_body
        )
        checks["music_state_in_pricing"] = same_music_state(initial, pricing)

        page.get_by_role(
            "button", name=re.compile(r"Return to Composition Studio", re.I)
        ).click()
        page.wait_for_selector(
            '[data-monetization-locked-feature="composition_studio"]',
            timeout=60_000,
        )
        page.get_by_text("Entitlement preview (dev)", exact=True).click()
        entitlement = page.get_by_role("combobox", name="Entitlement preview")
        entitlement.wait_for(state="visible", timeout=10_000)
        entitlement.click()
        entitlement.fill("Pro")
        page.get_by_role("option", name="Pro", exact=True).click(timeout=10_000)
        wait_for_state(page, "data-entitlement-plan", "pro")
        page.wait_for_selector(
            '[data-monetization-locked-feature="composition_studio"]',
            state="detached",
            timeout=60_000,
        )
        pro = ready_state(page)
        states["development_pro"] = pro
        checks["development_pro_unlocks_composition"] = (
            pro["entitlement-plan"] == "pro"
            and "Composition Studio" in page.locator("body").inner_text()
        )
        checks["music_state_free_to_pro"] = same_music_state(initial, pro)

        page.reload(wait_until="domcontentloaded", timeout=30_000)
        refreshed = ready_state(page)
        states["refresh"] = refreshed
        # The dropdown is deliberately session-only test tooling. A browser reload
        # reconstructs the server-owned test default instead of trusting stale
        # client/session Pro state.
        checks["refresh_reconstructs_server_entitlement"] = (
            refreshed["entitlement-plan"] == "free"
            and refreshed["entitlement-status"] == "development"
            and refreshed["entitlement-source"] == "development_override"
        )
        checks["refresh_preserves_music_state"] = same_music_state(initial, refreshed)
        checks["refresh_renders_reconstructed_access"] = (
            page.locator('[data-monetization-locked-feature="composition_studio"]').count()
            == 1
        )

        fresh_context = browser.new_context()
        fresh_page = fresh_context.new_page()
        fresh_page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
        fresh = ready_state(fresh_page)
        states["fresh_session"] = fresh
        checks["fresh_session_reconstructs_server_default"] = (
            fresh["entitlement-plan"] == "free"
            and fresh["entitlement-status"] == "development"
            and fresh["entitlement-source"] == "development_override"
        )
        checks["fresh_session_does_not_inherit_stale_pro"] = (
            fresh["entitlement-plan"] != "pro"
        )
        checks["fresh_session_reconstructs_music_state"] = same_music_state(initial, fresh)

        fresh_context.close()
        context.close()
        browser.close()

    return {"all_pass": all(checks.values()), "checks": checks, "states": states}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["all_pass"] else 1)

"""Focused gates: cold-start Custom select + first Composition hub→Backing click.

Uses an isolated suite_workspace per run. No reload / second-click recovery.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

import _gate_workspace as gw  # noqa: E402
import _source_identity_browser_verify as v  # noqa: E402

OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)


def _snap(page, label: str) -> dict:
    snap = {
        "label": label,
        "page": "",
        "radio": {"catalog": False, "custom": False, "composition": False},
        "marker": {},
        "composition_hub_backing_live": 0,
        "card_owner": "",
        "has_mode_composition": False,
        "has_mode_custom": False,
        "title_hint": "",
    }
    try:
        snap["page"] = v._studio_page_id(page)
    except Exception:
        pass
    try:
        snap["marker"] = (
            v.read_composition_hub_marker(page)
            if hasattr(v, "read_composition_hub_marker")
            else {}
        )
    except Exception:
        pass
    try:
        snap["radio"] = {
            "catalog": v.assert_radio_selected(page, "Catalog"),
            "custom": v.assert_radio_selected(page, "Custom Progression"),
            "composition": v.assert_radio_selected(page, "Composition"),
        }
    except Exception:
        pass
    try:
        loc = page.locator(".st-key-composition_hub_backing button")
        for i in range(loc.count()):
            btn = loc.nth(i)
            if btn.is_visible() and v._marker_is_live(btn):
                snap["composition_hub_backing_live"] += 1
    except Exception:
        pass
    if snap["page"] == "backing":
        try:
            snap["card_owner"] = v.read_live_backing_card_owner(page) or ""
        except Exception:
            pass
    # Avoid page.content()/inner_text("body") during Streamlit navigations — they can hang.
    try:
        modes = page.evaluate(
            """() => {
              const html = document.documentElement ? document.documentElement.innerHTML : '';
              return {
                composition: html.includes('mode-composition-song-backing'),
                custom: html.includes('mode-custom-progression-backing'),
              };
            }"""
        )
        snap["has_mode_composition"] = bool(modes.get("composition"))
        snap["has_mode_custom"] = bool(modes.get("custom"))
    except Exception:
        pass
    try:
        title = page.evaluate(
            """() => {
              const nodes = Array.from(document.querySelectorAll('p, [data-testid=\"stMarkdownContainer\"]'));
              for (const el of nodes) {
                if (el.closest('[data-stale=\"true\"]')) continue;
                const t = (el.innerText || '').trim();
                if (!t) continue;
                if (t.includes('My Composition') || t.includes('My Progression') || t.includes('Say')) {
                  return t.slice(0, 120);
                }
              }
              return '';
            }"""
        )
        snap["title_hint"] = str(title or "")
    except Exception:
        pass
    print(f"[SNAP] {label}: {json.dumps(snap, ensure_ascii=True)}", flush=True)
    return snap


def _reach_songs(page) -> bool:
    """Navigate to Songs once as setup (not mid-assertion recovery)."""
    for _ in range(6):
        if v._studio_page_id(page) == "picker":
            # Require a live Music Source radio before declaring ready.
            try:
                radios = page.locator("[data-testid='stRadio']")
                for i in range(radios.count()):
                    block = radios.nth(i)
                    if not v._marker_is_live(block):
                        continue
                    if not block.is_visible():
                        continue
                    txt = block.inner_text(timeout=1500)
                    if "Composition" in txt and ("Custom" in txt or "catalog" in txt.lower()):
                        return True
            except Exception:
                pass
            # Marker says picker but radio still remounting — brief idle then retry.
            v.wait_streamlit_idle(page, timeout_ms=3000)
            try:
                radios = page.locator("[data-testid='stRadio']")
                for i in range(radios.count()):
                    block = radios.nth(i)
                    if v._marker_is_live(block) and block.is_visible():
                        return True
            except Exception:
                pass
        try:
            nav = page.locator(".ui-nav-art-cell.nav-picker button")
            if nav.count() and nav.first.is_visible():
                nav.first.click(timeout=5000, no_wait_after=True)
                v.wait_streamlit(page, 3000)
                continue
        except Exception:
            pass
        try:
            v.click_nav(page, "Songs")
            v.wait_streamlit(page, 3000)
        except Exception:
            page.wait_for_timeout(500)
    return v._studio_page_id(page) == "picker"


def run_cold_start_custom(page, workspace_id: str) -> int:
    """Catalog disk restore → one Custom radio select must stick (first attempt)."""
    fails = 0
    url = gw.workspace_url(v.URL, workspace_id)
    page.goto(url, wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 10000)
    if not _reach_songs(page):
        print(
            f"[FAIL] cold_reach_songs: page={v._studio_page_id(page)!r}",
            flush=True,
        )
        return fails + 1
    v.wait_streamlit_idle(page)
    # Precondition: Catalog from disk
    if not (v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(page, "Song Selection")):
        print("[FAIL] cold_precondition_catalog: expected Catalog after disk restore", flush=True)
        fails += 1
    else:
        print("[PASS] cold_precondition_catalog", flush=True)
    try:
        v.select_music_source(page, "Custom Progression")
    except Exception as exc:
        print(f"[FAIL] cold_custom_select: {exc}", flush=True)
        return fails + 1
    ok = v.assert_radio_selected(page, "Custom Progression")
    print(f"[{'PASS' if ok else 'FAIL'}] cold_custom_radio_stuck: radio={ok}", flush=True)
    if not ok:
        fails += 1
        v.dump_debug(page, "cold_custom_select")
    # Hub live without second click
    live = 0
    loc = page.locator(".st-key-custom_hub_backing button")
    for i in range(loc.count()):
        try:
            el = loc.nth(i)
            if el.is_visible() and v._marker_is_live(el):
                live += 1
        except Exception:
            continue
    hub_ok = live > 0
    print(f"[{'PASS' if hub_ok else 'FAIL'}] cold_custom_hub_live: n={live}", flush=True)
    if not hub_ok:
        fails += 1
    return fails


def run_first_comp_backing_click(browser, workspace_id: str, *, cycles: int = 1) -> int:
    """Custom → Composition → one hub Backing click. No reload/second click.

    Each cycle uses a fresh browser context so Streamlit remount residue from prior
    cycles cannot poison the first-click evidence (still one Streamlit process).
    """
    fails = 0
    url = gw.workspace_url(v.URL, workspace_id)

    for i in range(1, cycles + 1):
        label = f"cycle_{i}"
        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1500, "height": 1200})
        try:
            print(f"[cycle] {i}/{cycles} fresh_context goto…", flush=True)
            page.goto(url, wait_until="domcontentloaded", timeout=180_000)
            v.wait_streamlit(page, 10000)
            print(f"[cycle] {i}/{cycles} reach_songs…", flush=True)
            if not _reach_songs(page):
                print(f"[FAIL] {label}_songs: page={v._studio_page_id(page)!r}", flush=True)
                fails += 1
                continue
            v.wait_streamlit_idle(page, timeout_ms=10000)
            print(f"[cycle] {i}/{cycles} select Custom…", flush=True)
            v.select_music_source(page, "Custom Progression")
            v.wait_streamlit_idle(page)
            try:
                v.wait_custom_hub_ready(page, timeout_ms=15000)
            except Exception:
                pass
            print(f"[cycle] {i}/{cycles} select Composition…", flush=True)
            v.select_music_source(page, "Composition")
            print(f"[cycle] {i}/{cycles} wait hub ready…", flush=True)
            marker = v.wait_composition_hub_ready(page, timeout_ms=35000)
            print(f"[cycle] {i}/{cycles} hub ready pick={marker.get('pick')!r}", flush=True)
            before = _snap(page, f"{label}_pre_click")
            print(f"[cycle] {i}/{cycles} click hub Backing…", flush=True)
            loc = page.locator(".st-key-composition_hub_backing button")
            clicked = False
            try:
                n = loc.count()
            except Exception:
                n = 0
            for j in range(n):
                btn = loc.nth(j)
                try:
                    if not btn.is_visible() or not v._marker_is_live(btn):
                        continue
                    btn.scroll_into_view_if_needed(timeout=2000)
                    btn.click(timeout=5000, no_wait_after=True)
                    clicked = True
                    break
                except Exception as exc:
                    print(f"[cycle] {i}/{cycles} click try {j} err={exc!r}", flush=True)
                    continue
            if not clicked:
                clicked = bool(
                    page.evaluate(
                        """() => {
                          const btns = Array.from(
                            document.querySelectorAll('.st-key-composition_hub_backing button')
                          );
                          for (const btn of btns) {
                            if (btn.closest('[data-stale=\"true\"]')) continue;
                            if (btn.offsetParent === null) continue;
                            btn.click();
                            return true;
                          }
                          return false;
                        }"""
                    )
                )
                print(f"[cycle] {i}/{cycles} js_click={clicked}", flush=True)
            if not clicked:
                print(f"[FAIL] {label}_click: no live composition_hub_backing", flush=True)
                fails += 1
                continue
            print(f"[cycle] {i}/{cycles} clicked — snap t0…", flush=True)
            immediate = _snap(page, f"{label}_t0")
            landed = False
            deadline = time.time() + 30
            after = immediate
            last_page = immediate.get("page")
            while time.time() < deadline:
                page_id = v._studio_page_id(page)
                if page_id != last_page or page_id == "backing":
                    after = _snap(page, f"{label}_poll")
                    last_page = page_id
                if page_id == "backing":
                    landed = True
                    break
                page.wait_for_timeout(250)
            owner = after.get("card_owner") or ""
            if landed and not owner and after.get("has_mode_composition"):
                owner = "composition"
            ok = landed and owner == "composition" and after.get("has_mode_composition")
            detail = (
                f"landed={landed} page={after.get('page')!r} owner={owner!r} "
                f"t0_page={immediate.get('page')!r} "
                f"pre_hub_click={before.get('marker', {}).get('hub_click')!r} "
                f"pre_last={before.get('marker', {}).get('last_event')!r} "
                f"t0_hub_click={immediate.get('marker', {}).get('hub_click')!r} "
                f"t0_last={immediate.get('marker', {}).get('last_event')!r}"
            )
            print(f"[{'PASS' if ok else 'FAIL'}] {label}_first_comp_backing: {detail}", flush=True)
            if not ok:
                fails += 1
                v.dump_debug(page, f"{label}_comp_open_fail")
        except Exception as exc:
            print(f"[FAIL] {label}_exception: {exc}", flush=True)
            fails += 1
        finally:
            try:
                context.close()
            except Exception:
                pass
    return fails


def run_comp_after_custom_refresh(page, workspace_id: str) -> int:
    """Mirror verify section 1→2: Custom Backing + refresh, then first Comp Backing click."""
    fails = 0
    url = gw.workspace_url(v.URL, workspace_id)
    page.goto(url, wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 10000)
    if not _reach_songs(page):
        print(f"[FAIL] refresh_path_songs: page={v._studio_page_id(page)!r}", flush=True)
        return 1
    try:
        v.select_music_source(page, "Custom Progression")
        v.open_custom_backing_from_hub(page)
        print("[PASS] refresh_path_custom_backing", flush=True)
    except Exception as exc:
        print(f"[FAIL] refresh_path_custom_backing: {exc}", flush=True)
        return 1
    page.wait_for_timeout(2500)
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    page.wait_for_timeout(10000)
    v.wait_streamlit(page, 4000)
    if not _reach_songs(page):
        print(f"[FAIL] refresh_path_songs_after_reload: page={v._studio_page_id(page)!r}", flush=True)
        return 1
    if not v.assert_radio_selected(page, "Custom Progression"):
        v.select_music_source(page, "Custom Progression")
    try:
        v.open_custom_backing_from_hub(page)
        print("[PASS] refresh_path_custom_reopen", flush=True)
    except Exception as exc:
        print(f"[FAIL] refresh_path_custom_reopen: {exc}", flush=True)
        return 1
    if not _reach_songs(page):
        print(f"[FAIL] refresh_path_songs_before_comp: page={v._studio_page_id(page)!r}", flush=True)
        return 1
    try:
        v.select_music_source(page, "Composition")
        marker = v.wait_composition_hub_ready(page, timeout_ms=25000)
        before = _snap(page, "refresh_path_pre_click")
        # Use the SAME inline one-click as the original verify (not helper).
        loc = page.locator(".st-key-composition_hub_backing button")
        clicked = False
        for i in range(loc.count()):
            btn = loc.nth(i)
            try:
                if not btn.is_visible() or not v._marker_is_live(btn):
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=8000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            print("[FAIL] refresh_path_comp_click: no live button", flush=True)
            return 1
        t0 = _snap(page, "refresh_path_t0")
        ok = False
        after = t0
        deadline = time.time() + 25
        while time.time() < deadline:
            after = _snap(page, "refresh_path_poll")
            if after["page"] == "backing" and (
                after.get("card_owner") == "composition" or after.get("has_mode_composition")
            ):
                ok = True
                break
            page.wait_for_timeout(250)
        detail = (
            f"ok={ok} page={after.get('page')!r} owner={after.get('card_owner')!r} "
            f"t0={t0.get('page')!r} pre_last={before.get('marker', {}).get('last_event')!r} "
            f"ready_marker={marker}"
        )
        print(f"[{'PASS' if ok else 'FAIL'}] refresh_path_comp_open: {detail}", flush=True)
        if not ok:
            fails += 1
            v.dump_debug(page, "refresh_path_comp_open_fail")
    except Exception as exc:
        print(f"[FAIL] refresh_path_comp_open: {exc}", flush=True)
        fails += 1
    return fails


def main() -> int:
    mode = (os.environ.get("FOCUSED_GATE") or "both").strip().lower()
    cycles = int(os.environ.get("FOCUSED_COMP_CYCLES") or "1")
    ws = os.environ.get("FOCUSED_WORKSPACE") or gw.unique_workspace_id("gate_focused")
    print(f"[workspace] id={ws} mode={mode} cycles={cycles}", flush=True)

    if mode in {"cold", "both"}:
        gw.seed_catalog_disk_state(ws)
    else:
        gw.ensure_empty_workspace(ws)
    gw.point_active_workspace_file(ws)

    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1500, "height": 1200})
        if mode in {"cold", "both"}:
            fails += run_cold_start_custom(page, ws)
        if mode in {"comp", "both"}:
            context.close()
            ws2 = gw.unique_workspace_id("gate_comp_click")
            gw.ensure_empty_workspace(ws2)
            gw.point_active_workspace_file(ws2)
            print(f"[workspace] comp_click id={ws2}", flush=True)
            fails += run_first_comp_backing_click(browser, ws2, cycles=cycles)
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1500, "height": 1200})
        if mode in {"refresh_path", "both"}:
            context.close()
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1500, "height": 1200})
            ws3 = gw.unique_workspace_id("gate_refresh_path")
            gw.ensure_empty_workspace(ws3)
            gw.point_active_workspace_file(ws3)
            print(f"[workspace] refresh_path id={ws3}", flush=True)
            fails += run_comp_after_custom_refresh(page, ws3)
        context.close()
        browser.close()

    print(f"Failures: {fails}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

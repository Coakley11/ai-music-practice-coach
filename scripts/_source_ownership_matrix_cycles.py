"""Ownership matrix — 10× Custom persistence + source switches + nav refresh.

Hang root cause (diagnosed): after Composition hub-ready, stale radio label
locators swallowed Custom clicks so the radio never flipped; the old wait loop
looked hung under buffered Tee output. Fix lives in select_music_source
(re-query labels before each click). This runner adds flush + timeouts.

EXTRA beyond test-required refresh (documented for embargo review):
- `_fresh_session`: clear_cookies + goto at the start of each A/B cycle and
  each C case (harness isolation, not an app refresh assertion).
- Composition→Custom remount: one `page.reload` AFTER selecting Composition
  and BEFORE selecting Custom (cycles A and B). This is NOT part of the
  product refresh contract; it was added to work around Streamlit radio
  widget desync observed when Comp→Custom clicks were no-ops without remount.
Test-required refreshes remain the explicit Custom persistence reloads in A
and the land-page reloads in C.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _source_identity_browser_verify as v  # noqa: E402

CYCLES = 10
MATRIX_OUT = v.OUT / "ownership_matrix_results.json"
SNAPSHOTS: list[dict] = []


def _log(msg: str) -> None:
    print(msg, flush=True)


def _snap(page, label: str) -> dict:
    html = v.body_html(page)
    radio = {
        "custom": v.assert_radio_selected(page, "Custom Progression"),
        "composition": v.assert_radio_selected(page, "Composition"),
        "catalog": v.assert_radio_selected(page, "Catalog")
        or v.assert_radio_selected(page, "Song Selection"),
    }
    cards = {
        "backing_custom": v._live_mode_card(page, "mode-custom-progression-backing"),
        "backing_composition": v._live_mode_card(page, "mode-composition-song-backing"),
        "source_custom_art": "source-custom" in html,
        "source_composition_art": "source-composition" in html,
    }
    row = {
        "label": label,
        "radio": radio,
        "cards": cards,
        "page": v._studio_page_id(page),
    }
    SNAPSHOTS.append(row)
    return row


def _expect_custom_songs(page) -> bool:
    return v.assert_radio_selected(page, "Custom Progression") and not v.assert_radio_selected(
        page, "Composition"
    )


def _expect_composition_songs(page) -> bool:
    return v.assert_radio_selected(page, "Composition") and not v.assert_radio_selected(
        page, "Custom Progression"
    )


def _expect_catalog_songs(page) -> bool:
    return (
        v.assert_radio_selected(page, "Catalog")
        or v.assert_radio_selected(page, "Song Selection")
    ) and not v.assert_radio_selected(page, "Composition")


def _expect_custom_backing(page) -> bool:
    return v._live_mode_card(page, "mode-custom-progression-backing") and not v._live_mode_card(
        page, "mode-composition-song-backing"
    )


def _expect_composition_backing(page) -> bool:
    return v._live_mode_card(page, "mode-composition-song-backing") and not v._live_mode_card(
        page, "mode-custom-progression-backing"
    )


def _expect_catalog_backing(page) -> bool:
    return not v._live_mode_card(
        page, "mode-composition-song-backing"
    ) and not v._live_mode_card(page, "mode-custom-progression-backing")


def _recover(page) -> None:
    try:
        _fresh_session(page)
        v.ensure_songs(page)
    except Exception as exc:
        _log(f"  recover failed: {exc}")


def _fresh_session(page) -> None:
    """Drop Streamlit cookies so goto starts a new server session."""
    try:
        page.context.clear_cookies()
    except Exception:
        pass
    page.goto(f"{v.URL}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4500)


def cycle_a_custom_persistence(page, n: int) -> list[str]:
    fails: list[str] = []
    _fresh_session(page)
    v.ensure_songs(page)
    v.select_music_source(page, "Composition")
    _snap(page, f"A{n}_before_custom")
    # Remount Songs after Composition so the Streamlit radio widget value matches
    # the visible selection (disk workspace restore otherwise desyncs Comp→Custom).
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 3500)
    v.ensure_songs(page)
    if not v.assert_radio_selected(page, "Composition"):
        v.select_music_source(page, "Composition")
    v.select_music_source(page, "Custom Progression")
    _snap(page, f"A{n}_after_custom")
    if not _expect_custom_songs(page):
        fails.append(f"A{n}: radio not Custom after Composition→Custom")
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4000)
    v.ensure_songs(page)
    _snap(page, f"A{n}_after_refresh1")
    if not _expect_custom_songs(page):
        fails.append(f"A{n}: Custom lost after refresh #1")
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4000)
    v.ensure_songs(page)
    _snap(page, f"A{n}_after_refresh2")
    if not _expect_custom_songs(page):
        fails.append(f"A{n}: Custom lost after refresh #2")
    html = v.body_html(page)
    text = v.body_text(page)
    if "📀" not in html and "Source" not in text:
        fails.append(f"A{n}: Source badge missing after Custom refresh")
    return fails


def cycle_b_switch_matrix(page, n: int) -> list[str]:
    fails: list[str] = []
    transitions = [
        ("Composition", "Custom Progression", "custom"),
        ("Custom Progression", "Composition", "composition"),
        ("Composition", "Catalog", "catalog"),
        ("Catalog", "Composition", "composition"),
    ]
    _fresh_session(page)
    v.ensure_songs(page)
    for src, dst, expect in transitions:
        v.ensure_songs(page)
        v.select_music_source(page, src)
        _snap(page, f"B{n}_{src}_songs")
        if src == "Composition" and dst == "Custom Progression":
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            v.wait_streamlit(page, 3500)
            v.ensure_songs(page)
            if not v.assert_radio_selected(page, "Composition"):
                v.select_music_source(page, "Composition")
        v.select_music_source(page, dst)
        _snap(page, f"B{n}_{src}_to_{dst}_songs")
        if expect == "custom" and not _expect_custom_songs(page):
            fails.append(f"B{n}: Songs radio not Custom after {src}→{dst}")
        if expect == "composition" and not _expect_composition_songs(page):
            fails.append(f"B{n}: Songs radio not Composition after {src}→{dst}")
        if expect == "catalog" and not _expect_catalog_songs(page):
            fails.append(f"B{n}: Songs radio not Catalog after {src}→{dst}")
        prefer = "catalog" if expect == "catalog" else expect
        try:
            v.open_backing(page, prefer=prefer)
        except Exception as exc:
            fails.append(f"B{n}: open_backing after {src}→{dst}: {exc}")
            v.ensure_songs(page)
            continue
        _snap(page, f"B{n}_{src}_to_{dst}_backing")
        if expect == "custom" and not _expect_custom_backing(page):
            fails.append(f"B{n}: Backing not Custom after {src}→{dst}")
        if expect == "composition" and not _expect_composition_backing(page):
            fails.append(f"B{n}: Backing not Composition after {src}→{dst}")
        if expect == "catalog" and not _expect_catalog_backing(page):
            fails.append(f"B{n}: Backing not Catalog after {src}→{dst}")
        v.ensure_songs(page)
    return fails


def cycle_c_nav_refresh(page, n: int) -> list[str]:
    fails: list[str] = []
    cases = [
        ("Custom Progression", "custom", "Backing"),
        ("Custom Progression", "custom", "Songs"),
        ("Composition", "composition", "Backing"),
        ("Composition", "composition", "Songs"),
    ]
    for source, expect, land in cases:
        _fresh_session(page)
        v.ensure_songs(page)
        v.select_music_source(page, source)
        if land == "Backing":
            try:
                v.open_backing(page, prefer=expect)
            except Exception as exc:
                fails.append(f"C{n}: open_backing {source}: {exc}")
                continue
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 4000)
        if land == "Backing":
            try:
                v.ensure_songs(page)
                v.select_music_source(page, source)
                v.open_backing(page, prefer=expect)
            except Exception:
                pass
        else:
            v.ensure_songs(page)
            try:
                v.select_music_source(page, source)
            except Exception:
                pass
        _snap(page, f"C{n}_{expect}_{land}_refresh")
        if expect == "custom":
            ok = (
                _expect_custom_backing(page)
                if land == "Backing"
                else _expect_custom_songs(page)
            )
        else:
            ok = (
                _expect_composition_backing(page)
                if land == "Backing"
                else _expect_composition_songs(page)
            )
        if not ok:
            fails.append(f"C{n}: {source} lost after {land} refresh")
        if land == "Backing":
            v.ensure_songs(page)
            try:
                v.select_music_source(page, source)
                v.open_backing(page, prefer=expect)
            except Exception as exc:
                fails.append(f"C{n}: Backing→Songs→Backing {source}: {exc}")
                continue
            if expect == "custom" and not _expect_custom_backing(page):
                fails.append(f"C{n}: Custom lost on Backing→Songs→Backing")
            if expect == "composition" and not _expect_composition_backing(page):
                fails.append(f"C{n}: Composition lost on Backing→Songs→Backing")
    return fails


def main() -> int:
    all_fails: list[str] = []
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.set_default_navigation_timeout(180_000)
        _log(f"matrix start url={v.URL}")
        page.goto(f"{v.URL}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        v.shot(page, "matrix_start")

        _log(f"\n=== A: Custom persistence x{CYCLES} ===")
        for i in range(1, CYCLES + 1):
            t = time.time()
            try:
                fails = cycle_a_custom_persistence(page, i)
            except Exception as exc:
                fails = [f"A{i}: exception {exc}"]
                _recover(page)
            all_fails.extend(fails)
            v.log(f"matrix_A_cycle_{i}", not fails, "; ".join(fails) or "ok")
            _log(f"  A{i}: {'FAIL ' + fails[0] if fails else 'PASS'} ({time.time()-t:.0f}s)")

        _log(f"\n=== B: switch matrix x{CYCLES} ===")
        for i in range(1, CYCLES + 1):
            t = time.time()
            try:
                fails = cycle_b_switch_matrix(page, i)
            except Exception as exc:
                fails = [f"B{i}: exception {exc}"]
                _recover(page)
            all_fails.extend(fails)
            v.log(f"matrix_B_cycle_{i}", not fails, "; ".join(fails) or "ok")
            _log(f"  B{i}: {'FAIL ' + fails[0] if fails else 'PASS'} ({time.time()-t:.0f}s)")

        _log(f"\n=== C: nav/refresh x{CYCLES} ===")
        for i in range(1, CYCLES + 1):
            t = time.time()
            try:
                fails = cycle_c_nav_refresh(page, i)
            except Exception as exc:
                fails = [f"C{i}: exception {exc}"]
                _recover(page)
            all_fails.extend(fails)
            v.log(f"matrix_C_cycle_{i}", not fails, "; ".join(fails) or "ok")
            _log(f"  C{i}: {'FAIL ' + fails[0] if fails else 'PASS'} ({time.time()-t:.0f}s)")

        browser.close()

    payload = {
        "cycles": CYCLES,
        "fail_count": len(all_fails),
        "fails": all_fails,
        "elapsed_s": round(time.time() - t0, 1),
        "snapshots": SNAPSHOTS[-80:],
    }
    MATRIX_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _log(f"\nMatrix evidence: {MATRIX_OUT}")
    _log(f"Total fails: {len(all_fails)} elapsed={payload['elapsed_s']}s")
    for f in all_fails[:40]:
        _log(f" - {f}")
    return 1 if all_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Evidence for ensure_songs reload + Comp→Custom without matrix remount.

Does not change product code. Writes JSON under _source_identity_browser_evidence/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _source_identity_browser_verify as v  # noqa: E402

OUT = v.OUT / "nav_recovery_evidence.json"


def _nav_snapshot(page) -> dict:
    keyed = page.locator(".ui-nav-art-cell.nav-picker button")
    sb = page.locator("[class*='st-key-sb_nav_picker'] button")
    try:
        keyed_n = keyed.count()
        keyed_vis = sum(1 for i in range(keyed_n) if keyed.nth(i).is_visible())
    except Exception:
        keyed_n, keyed_vis = -1, -1
    try:
        sb_n = sb.count()
        sb_vis = sum(1 for i in range(sb_n) if sb.nth(i).is_visible())
    except Exception:
        sb_n, sb_vis = -1, -1
    return {
        "page_id": v._studio_page_id(page),
        "body_studio_page": page.evaluate(
            "() => (document.body && document.body.dataset.studioPage) || ''"
        ),
        "keyed_picker_buttons": keyed_n,
        "keyed_picker_visible": keyed_vis,
        "sb_nav_picker_buttons": sb_n,
        "sb_nav_picker_visible": sb_vis,
        "source_radio_visible": bool(
            page.locator("[data-testid='stRadio'] label").filter(
                has_text="Composition"
            ).count()
        ),
        "radio": {
            "composition": v.assert_radio_selected(page, "Composition"),
            "custom": v.assert_radio_selected(page, "Custom Progression"),
        },
    }


def _hub_cycle(page, i: int) -> dict:
    t0 = time.time()
    try:
        v.ensure_songs(page)
        v.select_music_source(page, "Custom Progression")
        v.select_music_source(page, "Composition")
        marker = v.wait_composition_hub_ready(page, timeout_ms=30000)
        loc = page.locator(".st-key-composition_hub_backing button")
        clicked = False
        for j in range(loc.count()):
            btn = loc.nth(j)
            if not btn.is_visible() or not v._marker_is_live(btn):
                continue
            btn.scroll_into_view_if_needed(timeout=3000)
            btn.click(timeout=8000)
            clicked = True
            break
        if not clicked:
            raise RuntimeError("no live hub button")
        if not v._await_backing_studio(page, timeout_ms=45000, prefer="composition"):
            raise RuntimeError("backing not open page=%r" % (v._studio_page_id(page),))
        after_backing = _nav_snapshot(page)
        v.ensure_songs(page)
        after_songs = _nav_snapshot(page)
        return {
            "cycle": i,
            "ok": True,
            "dt": round(time.time() - t0, 1),
            "pick": marker.get("pick"),
            "after_backing": after_backing,
            "after_songs": after_songs,
        }
    except Exception as exc:
        return {
            "cycle": i,
            "ok": False,
            "error": str(exc)[:400],
            "dt": round(time.time() - t0, 1),
            "snap": _nav_snapshot(page),
        }


def run_hub(cycles: int, allow_reload: bool) -> dict:
    os.environ["ENSURE_SONGS_ALLOW_RELOAD"] = "1" if allow_reload else "0"
    v.reset_ensure_songs_stats()
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        for i in range(1, cycles + 1):
            row = _hub_cycle(page, i)
            rows.append(row)
            print(row, flush=True)
            if not row.get("ok") and allow_reload:
                try:
                    page.goto(
                        v.URL + "/?dev=1",
                        wait_until="domcontentloaded",
                        timeout=120_000,
                    )
                    v.wait_streamlit(page, 3000)
                except Exception:
                    pass
        browser.close()
    okn = sum(1 for r in rows if r.get("ok"))
    return {
        "allow_reload": allow_reload,
        "ok": okn,
        "cycles": cycles,
        "rows": rows,
        "ensure_songs_stats": dict(v.ENSURE_SONGS_STATS),
    }


def run_comp_to_custom_no_remount(trials: int = 5) -> dict:
    """Composition → Custom with NO page.reload / fresh_session between."""
    os.environ["ENSURE_SONGS_ALLOW_RELOAD"] = "0"
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 4500)
        v.ensure_songs(page)
        for i in range(1, trials + 1):
            before = _nav_snapshot(page)
            try:
                v.select_music_source(page, "Composition")
                mid = _nav_snapshot(page)
                v.select_music_source(page, "Custom Progression")
                after = _nav_snapshot(page)
                ok = after["radio"]["custom"] and not after["radio"]["composition"]
                results.append(
                    {
                        "trial": i,
                        "ok": ok,
                        "before": before,
                        "after_comp": mid,
                        "after_custom": after,
                    }
                )
                print(
                    f"comp_to_custom_no_remount {i} ok={ok} "
                    f"page={after['page_id']} custom={after['radio']['custom']}",
                    flush=True,
                )
            except Exception as exc:
                results.append(
                    {
                        "trial": i,
                        "ok": False,
                        "error": str(exc)[:400],
                        "snap": _nav_snapshot(page),
                    }
                )
                print(f"comp_to_custom_no_remount {i} FAIL {exc}", flush=True)
                # Stay on same session — no remount recovery.
                try:
                    v.ensure_songs(page)
                except Exception:
                    pass
        browser.close()
    return {
        "trials": trials,
        "ok": sum(1 for r in results if r.get("ok")),
        "results": results,
    }


def main() -> int:
    payload: dict = {
        "product_note": "app code not modified; harness evidence only",
        "hub_with_reload": None,
        "hub_no_reload": None,
        "comp_to_custom_no_remount": None,
    }
    print("=== hub 20 WITH reload fallback ===", flush=True)
    payload["hub_with_reload"] = run_hub(20, allow_reload=True)
    print(
        "ENSURE_SONGS_STATS",
        json.dumps(payload["hub_with_reload"]["ensure_songs_stats"]),
        flush=True,
    )

    reload_n = int(
        payload["hub_with_reload"]["ensure_songs_stats"].get("reload_fallback") or 0
    )
    if reload_n > 0:
        print(
            f"=== hub 20 WITHOUT reload fallback (prior recovery={reload_n}) ===",
            flush=True,
        )
        payload["hub_no_reload"] = run_hub(20, allow_reload=False)
    else:
        print(
            "=== reload fallback never invoked; skipping no-reload hub re-run ===",
            flush=True,
        )
        # Still run a short Songs-after-Backing check with reload disabled.
        print("=== hub 5 WITHOUT reload (sanity) ===", flush=True)
        payload["hub_no_reload"] = run_hub(5, allow_reload=False)

    print("=== Comp→Custom without matrix remount ===", flush=True)
    payload["comp_to_custom_no_remount"] = run_comp_to_custom_no_remount(5)

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}", flush=True)
    hub_ok = payload["hub_with_reload"]["ok"] == 20
    no_reload_ok = (
        payload["hub_no_reload"] is None
        or payload["hub_no_reload"]["ok"] == payload["hub_no_reload"]["cycles"]
    )
    c2c_ok = payload["comp_to_custom_no_remount"]["ok"] == 5
    return 0 if hub_ok and no_reload_ok and c2c_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

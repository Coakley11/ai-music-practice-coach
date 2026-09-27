"""Slice 5C browser visual check — instrument / Shape icons.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_slice5c python -m streamlit run streamlit_music_practice_app.py --server.port 8572
  python scripts/_proof_slice5c_instrument_icons.py http://127.0.0.1:8572
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from music_feature_icons import instrument_icon, semantic_field_icon  # noqa: E402
from walk_creative_backing_matrix import expand_sidebar, set_instrument  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import click_sidebar_once, expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8572"
OUT = SCRIPTS / "evidence-slice5c-icons"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    clarinet = instrument_icon("Clarinet")
    sax = instrument_icon("Saxophone")
    guitar = instrument_icon("Guitar")
    shape = semantic_field_icon("shape_key")
    result: dict[str, object] = {
        "clarinet_icon": clarinet,
        "sax_icon": sax,
        "guitar_icon": guitar,
        "shape_icon": shape,
        "ok": False,
    }
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 4000)
        expand_pages(page)
        pick_song(page, notes, "Perfect", "Pop")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2000)
        set_instrument(page, "Clarinet")
        wait(page, 2000)
        expand_sidebar(page)
        body = page.inner_text("body") or ""
        html = page.content()
        (OUT / "clarinet.txt").write_text(body[:12000], encoding="utf-8")
        page.screenshot(path=str(OUT / "clarinet.png"), full_page=False)

        clarinet_ok = clarinet in html and sax not in (body.split("Instrument")[1][:200] if "Instrument" in body else "")
        # Clarinet glyph present; sax not used as the Clarinet instrument identity.
        clarinet_present = clarinet in html
        sax_as_clarinet = False
        if "Clarinet" in body:
            # Nearby Clarinet mentions should not be prefixed by sax glyph in status strip.
            sax_as_clarinet = f"{sax} Instrument" in html or f"{sax}</span> Clarinet" in html

        set_instrument(page, "Saxophone")
        wait(page, 2000)
        expand_sidebar(page)
        html_sax = page.content()
        page.screenshot(path=str(OUT / "sax.png"), full_page=False)
        sax_present = sax in html_sax

        set_instrument(page, "Guitar")
        wait(page, 2000)
        expand_sidebar(page)
        html_g = page.content()
        page.screenshot(path=str(OUT / "guitar.png"), full_page=False)
        guitar_present = guitar in html_g
        shape_ok = shape == guitar

        checks = {
            "clarinet_present": clarinet_present,
            "clarinet_not_sax_identity": not sax_as_clarinet,
            "sax_present": sax_present,
            "guitar_present": guitar_present,
            "shape_is_guitar": shape_ok,
            "clarinet_neq_sax": clarinet != sax,
        }
        result["checks"] = checks
        result["ok"] = all(checks.values())
        browser.close()
    (OUT / "slice5c_icons_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

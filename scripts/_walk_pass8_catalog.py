"""Clean catalog Backing BPM probe after Reset to default. URL: http://127.0.0.1:8512"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import walk_creative_backing_matrix as matrix
import walk_guitar_shape_key as shape_walk
from walk_creative_backing_matrix import click_button_has, click_nav, expand_sidebar, set_baseweb_select, set_instrument
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
PREFIX = "pass8c-"
matrix.PREFIX = PREFIX
matrix.OUT = OUT


def wait(page, ms=1000):
    page.wait_for_timeout(ms)
    try:
        page.locator('[data-testid="stSpinner"]').first.wait_for(state="hidden", timeout=6000)
    except Exception:
        pass


matrix.wait_idle = wait
shape_walk.wait_idle = wait


def dump_sliders(page):
    return page.evaluate(
        """() => {
          const vis = (el) => !!(el && el.offsetWidth && el.offsetHeight);
          const sliders = [...document.querySelectorAll('[role="slider"], input[type="range"]')].map((s) => ({
            tag: s.tagName,
            role: s.getAttribute('role'),
            min: s.getAttribute('aria-valuemin') || s.getAttribute('min'),
            max: s.getAttribute('aria-valuemax') || s.getAttribute('max'),
            now: s.getAttribute('aria-valuenow') || s.value,
            label: (s.getAttribute('aria-label') || '').slice(0, 80),
            vis: vis(s),
          }));
          return sliders;
        }"""
    )


def main() -> int:
    notes = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 8000)
        # Contract: Reset → Shape of You → Catalog Backing. Do not Reset after pick.
        try:
            reset = page.locator("button").filter(has_text="Reset to default")
            if reset.count() and reset.first.is_visible():
                reset.first.click(timeout=4000)
                wait(page, 5000)
                notes.append("start_reset=True")
        except Exception as exc:
            notes.append(f"start_reset_err={exc}")
        landed = False
        for attempt in range(3):
            landed = bool(pick_song(page, notes, "Shape of You", "Pop"))
            if landed:
                break
            wait(page, 3000)
            click_nav(page, "Songs")
            wait(page, 2500)
        notes.append(f"landed={landed}")
        if not landed:
            body = page.inner_text("body") or ""
            (OUT / f"{PREFIX}summary.txt").write_text("\n".join(notes) + "\nFAIL pick Shape of You\n" + body[:2000], encoding="utf-8")
            browser.close()
            print("\n".join(notes), flush=True)
            return 1
        wait(page, 2500)
        set_instrument(page, "Guitar")
        wait(page, 1200)
        expand_sidebar(page)
        set_baseweb_select(page, "Practice / Concert Key", "Dm") or set_baseweb_select(
            page, "Practice / Concert Key", "D minor"
        )
        wait(page, 1500)
        enable_guitar_capo(page, notes, "E") or set_shape_tonic(page, "E")
        wait(page, 1800)
        click_button_has(page, "Return to Catalog Song Backing") or click_nav(page, "Backing")
        wait(page, 3500)
        for _ in range(8):
            body = page.inner_text("body") or ""
            if "Backing source: Catalog song" in body:
                break
            click_button_has(page, "Return to Catalog Song Backing") or click_nav(page, "Backing")
            wait(page, 2000)
        body = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / f"{PREFIX}A0.png"), full_page=True)
        (OUT / f"{PREFIX}A0.txt").write_text(body[:16000], encoding="utf-8")
        sliders = dump_sliders(page)
        (OUT / f"{PREFIX}sliders.json").write_text(json.dumps(sliders, indent=2), encoding="utf-8")
        notes.append(f"sliders={sliders}")
        notes.append(f"catalog={'Backing source: Catalog song' in body}")
        notes.append(f"default96={'Default 96 BPM' in body}")
        notes.append(f"current96={'Current 96 BPM' in body}")
        notes.append(f"pkDm={'PRACTICE / CONCERT KEY' in body and 'Dm' in body}")
        notes.append(f"fshm={'F#m' in body}")
        if "Backing Track Studio" not in body and "Quick BPM" not in body:
            notes.append("FAIL not on backing page")
            (OUT / f"{PREFIX}summary.txt").write_text("\n".join(notes), encoding="utf-8")
            print("\n".join(notes), flush=True)
            browser.close()
            return 1
        # Drive Quick BPM input[type=range] (Streamlit does not use role=slider here).
        bpm_input = page.locator('input[type="range"][aria-label="Quick BPM"]').first
        if bpm_input.count() == 0:
            bpm_input = page.locator('input[type="range"]').first
        if bpm_input.count() == 0:
            notes.append("FAIL no BPM slider")
            (OUT / f"{PREFIX}summary.txt").write_text("\n".join(notes), encoding="utf-8")
            print("\n".join(notes), flush=True)
            browser.close()
            return 1
        bpm_input.scroll_into_view_if_needed()
        wait(page, 300)
        box = bpm_input.bounding_box()
        if box:
            # Click near 110 on the track, then nudge with arrows.
            ratio = (110 - 20) / 160
            page.mouse.click(box["x"] + box["width"] * ratio, box["y"] + box["height"] / 2)
            wait(page, 1200)
        bpm_input.focus()
        now = int(float(bpm_input.get_attribute("value") or bpm_input.input_value() or 0) or 0)
        if now < 110:
            for _ in range(min(40, 110 - now)):
                page.keyboard.press("ArrowRight")
            wait(page, 1500)
        elif now > 110:
            for _ in range(min(40, now - 110)):
                page.keyboard.press("ArrowLeft")
            wait(page, 1500)
        # Allow same-run fill + at least one subsequent full rerun.
        for _ in range(12):
            wait(page, 800)
            try:
                now = int(float(bpm_input.input_value() or 0) or 0)
            except Exception:
                now = 0
            body_probe = page.inner_text("body") or ""
            if now == 110 and "Current 110 BPM" in body_probe:
                break
        wait(page, 2000)
        body2 = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / f"{PREFIX}A1.png"), full_page=True)
        (OUT / f"{PREFIX}A1.txt").write_text(body2[:16000], encoding="utf-8")
        notes.append(
            f"after_slider={bpm_input.input_value()} current110={('Current 110 BPM' in body2)} "
            f"current96={('Current 96 BPM' in body2)} banner110={('110 BPM' in body2)} "
            f"changed={('Playback settings changed' in body2)}"
        )
        page.reload(wait_until="domcontentloaded")
        wait(page, 4500)
        body3 = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / f"{PREFIX}A3.png"), full_page=True)
        (OUT / f"{PREFIX}A3.txt").write_text(body3[:16000], encoding="utf-8")
        notes.append(f"refresh_current110={'Current 110 BPM' in body3} refresh96={'Current 96 BPM' in body3}")
        click_nav(page, "Practice")
        wait(page, 2500)
        click_nav(page, "Backing")
        wait(page, 3500)
        body4 = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / f"{PREFIX}A5.png"), full_page=True)
        (OUT / f"{PREFIX}A5.txt").write_text(body4[:16000], encoding="utf-8")
        notes.append(f"return_current={('Current 96 BPM' in body4)} return110={('Current 110 BPM' in body4)}")
        browser.close()
    text = "\n".join(notes)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    print(text.encode("ascii", "replace").decode("ascii"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

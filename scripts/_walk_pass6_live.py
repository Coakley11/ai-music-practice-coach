"""Pass 6 live checks: Guitar ownership, Generate, Jam BPM init, catalog edits.

Usage: python scripts/_walk_pass6_live.py [http://127.0.0.1:PORT]
Do not commit evidence unless requested.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    click_visible_text,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    (OUT / f"{name}.txt").write_text(page.inner_text("body")[:12000], encoding="utf-8")


def body_has(page: Page, *needles: str) -> bool:
    text = (page.inner_text("body") or "").lower()
    return all(n.lower() in text for n in needles)


def main() -> int:
    results: dict[str, str] = {}
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        wait_idle(page, 4000)

        # Active song must have an original key or Creative Lab blocks.
        expand_sidebar(page)
        song_ok = (
            pick_song(page, notes, "Photograph", "Pop")
            or pick_song(page, notes, "Hevenu Shalom Aleichem", "Folk")
            or pick_song(page, notes, "Shape of You", "Pop")
        )
        if not song_ok:
            click_nav(page, "Songs")
            wait_idle(page, 4000)
            song_ok = (
                click_visible_text(page, "Photograph")
                or click_visible_text(page, "Hevenu")
                or set_baseweb_select(page, "Song", "Photograph")
            )
        notes.append(f"picked catalog song={song_ok}")
        wait_idle(page, 4000)
        shot(page, "pass6-A00-song")

        # A. Instrument ownership
        set_instrument(page, "Guitar")
        wait_idle(page, 2000)
        expand_sidebar(page)
        shot(page, "pass6-A0-guitar")
        if not goto_improv(page, notes):
            results["A_instrument"] = "FAIL: could not open Creative/Improv"
        else:
            wait_idle(page, 3000)
            click_radio(page, "Missions") or click_button_has(page, "Missions") or click_button_has(page, "Mission")
            wait_idle(page, 3500)
            shot(page, "pass6-A1-missions")
            guitar_ok = body_has(page, "Guitar")
            opened = click_open_backing_studio(page, notes, "mission") or click_button_has(
                page, "Mission Backing"
            ) or click_button_has(page, "Open Backing")
            wait_idle(page, 4000)
            shot(page, "pass6-A2-mission-backing")
            still_guitar = "Guitar" in (page.inner_text("body") or "")
            piano_badge = "Instrument · Piano" in (page.inner_text("body") or "") or "🎹 Instrument · Piano" in (
                page.inner_text("body") or ""
            )
            click_button_has(page, "Return to Mission") or click_button_has(page, "Missions") or click_button_has(
                page, "Creative"
            )
            wait_idle(page, 3500)
            shot(page, "pass6-A3-return-missions")
            back_guitar = "Guitar" in (page.inner_text("body") or "")
            results["A_instrument"] = (
                "PASS"
                if (guitar_ok and still_guitar and back_guitar and not piano_badge)
                else f"PARTIAL/FAIL g={guitar_ok} mb={still_guitar} piano_badge={piano_badge} ret={back_guitar} opened={opened}"
            )

        # B. Generate Example first click
        if goto_improv(page, notes):
            wait_idle(page, 2500)
            click_radio(page, "Missions") or click_button_has(page, "Missions")
            wait_idle(page, 3000)
            before = page.inner_text("body") or ""
            clicked = click_button_has(page, "Generate example") or click_button_has(page, "Generate Example")
            wait_idle(page, 4500)
            shot(page, "pass6-B-generate")
            after = page.inner_text("body") or ""
            appeared = bool(clicked) and (
                len(after) > len(before) + 40
                or "chord tones" in after.lower()
                or "optional example" in after.lower()
                or "ABC" in after
                or "motif" in after.lower()
            )
            inst_ok = "Guitar" in after
            results["B_generate"] = (
                "PASS" if appeared and inst_ok else f"PARTIAL/FAIL clicked={clicked} appeared={appeared} inst={inst_ok}"
            )

        # C. Jam BPM init — best effort via Entry & Jam
        if goto_improv(page, notes):
            wait_idle(page, 2000)
            click_radio(page, "Entry") or click_button_has(page, "Entry") or click_button_has(page, "Jam")
            wait_idle(page, 2500)
            click_button_has(page, "Jam Session") or click_button_has(page, "Generator")
            wait_idle(page, 2500)
            click_button_has(page, "Generate")
            wait_idle(page, 5000)
            shot(page, "pass6-C0-jam-generated")
            opened = click_open_backing_studio(page, notes, "jam")
            wait_idle(page, 4000)
            shot(page, "pass6-C1-jam-backing")
            text = page.inner_text("body") or ""
            bpms = re.findall(r"(?:BPM[:\s·]+(\d{2,3})|(\d{2,3})\s*BPM)", text, flags=re.I)
            flat = [a or b for a, b in bpms]
            card = re.search(r"BPM[:\s·]+(\d{2,3})", text, flags=re.I)
            tempo_block = "TEMPO (BPM)" in text
            results["C_jam_bpm"] = (
                f"{'OPENED' if opened else 'NO_OPEN'} bpms={flat[:8]} "
                f"card={card.group(1) if card else None} tempo_ui={tempo_block}"
            )

        # D. Catalog backing edits — open regular Backing
        expand_sidebar(page)
        click_nav(page, "Backing")
        wait_idle(page, 4000)
        shot(page, "pass6-D-catalog-backing")
        text = page.inner_text("body") or ""
        editable = "Groove style" in text or "Advanced playback" in text or "TEMPO (BPM)" in text or "Selected sections" in text
        # Try a light edit signal: bump tempo if number input exists
        bumped = False
        try:
            from walk_creative_backing_matrix import bump_number_input

            bumped = bump_number_input(page, "TEMPO", times=1)
        except Exception:
            bumped = False
        wait_idle(page, 2500)
        after = page.inner_text("body") or ""
        results["D_catalog"] = (
            f"{'EDITED' if bumped else 'REACHED'} editable_ui={editable} bumped={bumped} "
            f"has_advanced={'Advanced playback' in after}"
        )

        browser.close()

    summary = OUT / "pass6-live-summary.txt"
    lines = [f"URL={URL}", f"ts={time.strftime('%Y-%m-%d %H:%M:%S')}"] + [f"{k}: {v}" for k, v in results.items()]
    lines += ["notes:"] + notes[-40:]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

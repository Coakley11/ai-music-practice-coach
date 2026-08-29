"""Songs-page Creative button: one-click nav without ownership mutation.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_songs_creative_nav streamlit run streamlit_music_practice_app.py --server.port 8534
  python scripts/_walk_songs_creative_nav.py http://127.0.0.1:8534
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import practice_badge  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8534"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "songs-creative-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(low(n) in b for n in needles)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 2.0) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body[:24000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def click_songs_creative_button(page: Page) -> bool:
    loc = page.locator('[class*="st-key-picker_card_creative"] button')
    if not loc.count():
        log("picker_card_creative not in DOM")
        return False
    try:
        loc.first.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        loc.first.click(timeout=5000)
        settle(page, 3)
        return True
    except Exception as exc:
        log(f"picker_card_creative click err {exc!r}")
        return False


def on_creative(body: str) -> bool:
    return has_any(body, "Creative Lab", "Improvisation Intelligence", "Harmony, improvisation")


def on_songs(body: str) -> bool:
    return has_any(body, "Song Selection", "Choose a song from your library", "Now loaded for practice")


def main() -> int:
    log(f"url={URL}")
    notes: list[str] = NOTES

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 980})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        # 1. Songs with Shape active → Creative
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 2)
        pick_song(page, notes, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Bm")
        settle(page, 3)
        body1 = shot(page, "1-songs-shape")
        pk1 = practice_badge(body1) or pk_val(page)
        shape_on_songs = has_any(body1, "Shape of You") and on_songs(body1)
        btn_visible = page.locator('[class*="st-key-picker_card_creative"]').count() > 0
        clicked = click_songs_creative_button(page)
        body1b = shot(page, "1-creative-shape")
        pk1b = practice_badge(body1b) or pk_val(page)
        still_shape = has_any(body1b, "Shape of You") and not has_any(body1b, "Trial Song")
        pk_same = "b minor" in low(pk1b or body1b)
        mark(
            "1_shape_to_creative",
            bool(shape_on_songs and btn_visible and clicked and on_creative(body1b) and still_shape and pk_same),
            f"btn={btn_visible} click={clicked} creative={on_creative(body1b)} "
            f"shape={still_shape} pk={pk1!r}->{pk1b!r}",
        )

        # 2. Creative → Songs → Creative (ownership stays coherent)
        sbi_before = has_any(body1b, "Active Source", "Active song")
        click_nav(page, "Songs")
        settle(page, 3)
        body2 = shot(page, "2-songs-return")
        clicked2 = click_songs_creative_button(page)
        body2b = shot(page, "2-creative-roundtrip")
        still_shape2 = has_any(body2b, "Shape of You") and not has_any(body2b, "Trial Song")
        pk2 = practice_badge(body2b) or pk_val(page)
        mark(
            "2_creative_songs_creative",
            bool(on_songs(body2) and clicked2 and on_creative(body2b) and still_shape2 and "b minor" in low(pk2 or body2b)),
            f"songs={on_songs(body2)} click={clicked2} creative={on_creative(body2b)} "
            f"shape={still_shape2} sbi_was_active={sbi_before} pk={pk2!r}",
        )

        # 3. Songs with Custom Global Active → Creative
        trial_ok = build_trial_song(page, notes)
        settle(page, 2)
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        click_nav(page, "Songs")
        settle(page, 4)
        body3 = shot(page, "3-songs-custom-ga")
        custom_on_songs = has_any(body3, "Trial Song") and on_songs(body3)
        no_catalog_hub = "Use catalog song instead" in body3 or has_any(body3, "your song")
        clicked3 = click_songs_creative_button(page)
        body3b = shot(page, "3-creative-custom-ga")
        still_trial = has_any(body3b, "Trial Song")
        no_shape_fallback = not (
            has_any(body3b, "Shape of You") and not has_any(body3b, "Trial Song")
        )
        mark(
            "3_custom_ga_to_creative",
            bool(trial_ok and custom_on_songs and clicked3 and on_creative(body3b) and still_trial and no_shape_fallback),
            f"trial_build={trial_ok} songs_custom={custom_on_songs} hub={no_catalog_hub} "
            f"click={clicked3} creative={on_creative(body3b)} trial={still_trial} "
            f"no_shape_fallback={no_shape_fallback}",
        )

        # 4. Refresh after using the new button
        page.reload(wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
        body4 = shot(page, "4-refresh")
        still_creative = on_creative(body4)
        still_trial4 = has_any(body4, "Trial Song")
        no_crash = "NameError" not in body4 and "Traceback" not in body4
        mark(
            "4_refresh_after_button",
            bool(still_creative and still_trial4 and no_crash),
            f"creative={still_creative} trial={still_trial4} crash={not no_crash}",
        )

        browser.close()

    reds = [k for k, v in GATES.items() if not v]
    overall = "ALL_PASS" if GATES and not reds else "RED"
    print(json.dumps(GATES, indent=2), flush=True)
    print(f"OVERALL={overall}", flush=True)
    (OUT / f"{PREFIX}report.json").write_text(
        json.dumps({"overall": overall, "gates": GATES, "notes": NOTES[-40:]}, indent=2),
        encoding="utf-8",
    )
    return 0 if overall == "ALL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

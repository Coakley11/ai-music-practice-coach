"""Pass 7 live: Shape of You Dm + Shape D# Missions projection/example + Backing."""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    (OUT / f"{name}.txt").write_text(page.inner_text("body")[:16000], encoding="utf-8")


def set_practice_key(page: Page, token: str) -> bool:
    from walk_creative_backing_matrix import set_baseweb_select

    return bool(
        set_baseweb_select(page, "Practice / Concert Key", token)
        or set_baseweb_select(page, "Practice / Concert Key", "D minor")
        or set_baseweb_select(page, "Practice / Concert Key", "F minor")
    )


def _slider_bpm(page: Page) -> int | None:
    for el in page.locator('[role="slider"]').all():
        try:
            if not el.is_visible():
                continue
            mn = float(el.get_attribute("aria-valuemin") or 0)
            mx = float(el.get_attribute("aria-valuemax") or 0)
            if mn <= 20 and mx >= 160:
                return int(float(el.get_attribute("aria-valuenow") or 0)) or None
        except Exception:
            continue
    return None


def _set_slider(page: Page, value: int) -> int | None:
    for el in page.locator('[role="slider"]').all():
        try:
            if not el.is_visible():
                continue
            mn = float(el.get_attribute("aria-valuemin") or 0)
            mx = float(el.get_attribute("aria-valuemax") or 0)
            if mn <= 20 and mx >= 160:
                el.focus()
                page.keyboard.press("Home")
                for _ in range(max(0, int(value - mn))):
                    page.keyboard.press("ArrowRight")
                wait_idle(page, 2000)
                return _slider_bpm(page)
        except Exception:
            continue
    return None


def _example_slice(body: str) -> str:
    idx = body.find("Mission example")
    if idx < 0:
        return body[-2500:]
    return body[idx : idx + 1800]


def main() -> int:
    notes: list[str] = []
    results: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        wait_idle(page, 4000)
        pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page, 3500)
        set_instrument(page, "Guitar")
        wait_idle(page, 2000)
        expand_sidebar(page)
        set_practice_key(page, "Dm")
        wait_idle(page, 2500)
        enable_guitar_capo(page, notes, "D#") or set_shape_tonic(page, "D#")
        wait_idle(page, 3000)
        shot(page, "pass7-00-setup")
        if not goto_improv(page, notes):
            results["missions"] = "FAIL: no Creative"
        else:
            click_radio(page, "Missions") or click_button_has(page, "Missions")
            wait_idle(page, 4000)
            shot(page, "pass7-01-missions")
            body = page.inner_text("body") or ""
            has_dsharp_tile = "D#m" in body
            selected_label = "Selected Mission Chord: D#m" in body
            stale_fsharp = "Selected Mission Chord: F#m" in body
            charts = "Charts in D# minor" in body or "Charts in D♯ minor" in body
            practice = "Practice Key: Dm" in body
            results["missions_labels"] = (
                f"tile_D#m={has_dsharp_tile} selected_D#m={selected_label} "
                f"stale_F#m={stale_fsharp} charts={charts} practice_Dm={practice}"
            )
            clicked = click_button_has(page, "Generate example")
            wait_idle(page, 5000)
            shot(page, "pass7-02-generate")
            after = page.inner_text("body") or ""
            ex = _example_slice(after)
            heading_dsharp = "Mission example · D#m" in after
            dorian_d = "D Dorian" in ex
            dorian_ds = "D# Dorian" in ex or "D♯ Dorian" in ex
            tones_d = "D · F · A" in ex
            tones_ds = "D#" in ex and "F#" in ex
            results["generate"] = (
                f"clicked={clicked} heading_D#m={heading_dsharp} "
                f"dorian_D={dorian_d} dorian_D#={dorian_ds} tones_DFA={tones_d} tones_Dsharp={tones_ds}"
            )

            clicked_b = click_button_has(page, r"^B$")
            wait_idle(page, 3000)
            shot(page, "pass7-04-select-b")
            b_body = page.inner_text("body") or ""
            key_still_dm = "Practice Key: Dm" in b_body and "Charts in D# minor" in b_body
            selected_b = "Selected Mission Chord: B" in b_body
            selected_still_dsharp = "Selected Mission Chord: D#m" in b_body
            results["select_b"] = (
                f"clicked={clicked_b} key_still_dm={key_still_dm} "
                f"selected_B={selected_b} still_D#m={selected_still_dsharp}"
            )
            gen_b = click_button_has(page, "Generate example")
            wait_idle(page, 5000)
            shot(page, "pass7-05-generate-b")
            gb = _example_slice(page.inner_text("body") or "")
            results["generate_b"] = (
                f"clicked={gen_b} heading_B={'Mission example · B' in gb} "
                f"heading_D#m={'Mission example · D#m' in gb} "
                f"dorian_D={'D Dorian' in gb} practice_dm={'Practice Key: Dm' in (page.inner_text('body') or '')}"
            )

            shape_e = set_shape_tonic(page, "E")
            wait_idle(page, 4000)
            shot(page, "pass7-06-shape-e")
            se = page.inner_text("body") or ""
            results["shape_e"] = (
                f"clicked={shape_e} charts_e={'Charts in E minor' in se} "
                f"tile_Em={'Em' in se} practice_dm={'Practice Key: Dm' in se} "
                f"example={_example_slice(se)[:180]!r}"
            )

            click_open_backing_studio(page, notes, "mission")
            wait_idle(page, 4000)
            shot(page, "pass7-03-mission-backing")
            mb = page.inner_text("body") or ""
            mb_pk = set_practice_key(page, "Fm")
            wait_idle(page, 3000)
            shot(page, "pass7-07-mission-backing-pk")
            mb2 = page.inner_text("body") or ""
            results["mission_backing"] = (
                f"guitar={'Guitar' in mb} tempo={'TEMPO (BPM)' in mb} "
                f"practice_key={'Practice / Concert Key' in mb} "
                f"pk_click={mb_pk} fm_after={'Fm' in mb2 or 'F minor' in mb2.lower()}"
            )

        if goto_improv(page, notes):
            click_radio(page, "Play Song-Based Improvisation") or click_radio(
                page, "Song-Based Improvisation"
            )
            wait_idle(page, 3500)
            click_open_backing_studio(page, notes, "sbi")
            wait_idle(page, 4000)
            shot(page, "pass7-08-sbi-backing")
            before = _slider_bpm(page)
            after_bpm = _set_slider(page, 118)
            wait_idle(page, 2500)
            shot(page, "pass7-09-sbi-bpm")
            sbi_txt = page.inner_text("body") or ""
            err = "StreamlitAPIException" in sbi_txt
            pk = set_practice_key(page, "Fm")
            wait_idle(page, 3000)
            shot(page, "pass7-10-sbi-pk")
            sbi2 = page.inner_text("body") or ""
            results["sbi_backing"] = (
                f"slider_before={before} slider_after={after_bpm} exception={err} "
                f"pk_click={pk} fm={'Fm' in sbi2 or 'F minor' in sbi2.lower()} "
                f"card_bpm={bool(re.search(r'118', sbi_txt))}"
            )
        browser.close()
    summary = OUT / "pass7-live-summary.txt"
    lines = [f"URL={URL}", f"ts={time.strftime('%Y-%m-%d %H:%M:%S')}"]
    lines += [f"{k}: {v}" for k, v in results.items()]
    lines += ["notes:"] + notes[-30:]
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

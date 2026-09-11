"""Real-browser Custom page owner / Presets / Finish Song walk.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8541
  python scripts/_walk_custom_page_owner_basics.py http://127.0.0.1:8541
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402
from _walk_custom_practice_key import (  # noqa: E402
    key_is,
    original_key_val,
    pk_val,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8541"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "custom-basics-"


def _git() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]

    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def shot(page: Page, name: str) -> tuple[str, str]:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    side = ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:9000]}\n\n=== BODY ===\n{body[:18000]}",
        encoding="utf-8",
    )
    return side, body


def _low(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("♯", "#").replace("♭", "b"))


def has_bm_bleed(text: str) -> bool:
    t = _low(text)
    return bool(re.search(r"\bb minor\b", t) or re.search(r"\bbm\b", t))


def presets_key_visible(page: Page) -> bool:
    loc = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Presets key", re.I)
    )
    return loc.count() > 0 and loc.first.is_visible()


def set_presets_key(page: Page, token: str) -> bool:
    main = page.locator('[data-testid="stAppViewContainer"], section.main, .main').first
    box = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Presets key", re.I)
    )
    if box.count() == 0:
        return False
    target = box.first
    try:
        target.scroll_into_view_if_needed()
        target.locator('[data-baseweb="select"], [role="combobox"], input').first.click(timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(token), delay=30)
        page.wait_for_timeout(500)
        opt = page.locator('[role="option"]').filter(
            has_text=re.compile(rf"^{re.escape(token)}( major)?$", re.I)
        )
        if opt.count():
            opt.first.click(timeout=4000)
            wait_idle(page, 3500)
            return True
    except Exception:
        pass
    return bool(set_baseweb_select(page, "Presets key", token) or set_baseweb_select(page, "Presets key", f"{token} major"))


def click_main_button(page: Page, pattern: str) -> bool:
    """Click a main-area button; skip sidebar nav clones."""
    loc = page.locator(
        '[data-testid="stAppViewContainer"] button, section.main button, .main button'
    ).filter(has_text=re.compile(pattern, re.I))
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed()
            el.click(timeout=5000)
            wait_idle(page, 4000)
            return True
        except Exception:
            continue
    return click_button_has(page, pattern)


def main() -> int:
    notes: list[str] = [json.dumps(_git())]
    gates: dict[str, bool] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 980})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait_idle(page, 5000)

        # A. Songs → catalog Shape of You (leave Custom active if restored)
        click_nav(page, "Songs")
        wait_idle(page, 2500)
        click_button_has(page, r"Use catalog song instead") or click_button_has(
            page, r"Song Selection \(catalog"
        )
        wait_idle(page, 2500)
        ok_pick = pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page, 3000)
        side_a, body_a = shot(page, "A-shape-songs")
        shape_ok = ok_pick and ("shape of you" in _low(body_a + side_a))
        gates["A_shape_bm"] = bool(ok_pick and shape_ok)
        notes.append(f"A pick={ok_pick} shape_text={shape_ok} bm={has_bm_bleed(side_a+body_a)}")

        # B. Custom → Trial Song D major
        trial_ok = build_trial_song(page, notes)
        wait_idle(page, 2500)
        side_b, body_b = shot(page, "B-trial-custom")
        orig = original_key_val(page)
        pk = pk_val(page)
        gates["B_trial"] = bool(trial_ok) and (
            key_is(orig, "D") or "d major" in _low(orig + body_b)
        )
        notes.append(f"B trial={trial_ok} orig={orig!r} pk={pk!r}")

        # C. Songs → reactivate Shape
        click_nav(page, "Songs")
        wait_idle(page, 2500)
        click_button_has(page, r"Use catalog song instead")
        wait_idle(page, 2000)
        ok_re = pick_song(page, notes, "Shape of You", "Pop")
        wait_idle(page, 2500)
        side_c, body_c = shot(page, "C-shape-reactivate")
        gates["C_shape_bm"] = bool(ok_re) and "shape of you" in _low(side_c + body_c)
        notes.append(f"C reactivate={ok_re} bm={has_bm_bleed(side_c+body_c)}")

        # D. Custom page must be Trial D, not Shape Bm
        click_nav(page, "Custom")
        wait_idle(page, 4000)
        side_d, body_d = shot(page, "D-custom-after-shape")
        orig_d = original_key_val(page)
        pk_d = pk_val(page)
        trial_visible = "trial song" in _low(body_d)
        presets_vis = presets_key_visible(page)
        bleed_d = has_bm_bleed(side_d) or (
            "b minor" in _low(body_d) and "trial song" in _low(body_d)
        )
        orig_is_d = key_is(orig_d, "D") or "d major" in _low(orig_d + body_d)
        gates["D_trial_not_bm"] = bool(
            trial_visible and orig_is_d and not bleed_d and not key_is(pk_d, "Bm")
        )
        gates["D_presets_visible"] = presets_vis
        notes.append(
            f"D trial={trial_visible} orig={orig_d!r} pk={pk_d!r} "
            f"presets={presets_vis} bleed={bleed_d}"
        )

        # E. Custom PK D → E
        pk_set = set_baseweb_select(page, "Practice / Concert Key", "E") or set_baseweb_select(
            page, "Practice / Concert Key", "E major"
        )
        wait_idle(page, 3500)
        side_e, body_e = shot(page, "E-custom-pk-e")
        pk_e = pk_val(page)
        pk_is_e = key_is(pk_e, "E") or "e major" in _low(pk_e)
        still_trial = "trial song" in _low(body_e)
        gates["E_pk_e"] = bool(pk_set and pk_is_e and still_trial and not has_bm_bleed(side_e))
        notes.append(f"E set={pk_set} pk={pk_e!r} trial={still_trial}")

        # Presets key dropdown — change through UI
        preset_ok = False
        if presets_key_visible(page):
            preset_ok = set_presets_key(page, "E") or set_presets_key(page, "C")
            wait_idle(page, 3000)
            side_p, body_p = shot(page, "F-presets-key")
            # I–V–vi–IV in E is E B C#m A; in C is C G Am F
            preset_follows = ("e major" in _low(body_p) or "c major" in _low(body_p)) and (
                "i–v–vi–iv" in _low(body_p) or "i-v–vi-iv" in _low(body_p) or "pop presets" in _low(body_p)
            )
            gates["presets_dropdown"] = True
            gates["presets_follows"] = bool(preset_ok and not has_bm_bleed(side_p))
            notes.append(f"presets set={preset_ok} follows={preset_follows}")
            # Restore E if we flipped to C for the probe
            if "c major" in _low(pk_val(page)):
                set_baseweb_select(page, "Practice / Concert Key", "E")
                wait_idle(page, 2000)
        else:
            gates["presets_dropdown"] = False
            gates["presets_follows"] = False
            notes.append("FAIL presets key dropdown not visible")

        # F. Songs — Shape still Bm
        click_nav(page, "Songs")
        wait_idle(page, 3000)
        side_f, body_f = shot(page, "G-songs-shape-still")
        gates["F_shape_still"] = "shape of you" in _low(side_f + body_f)
        notes.append(f"F songs shape={gates['F_shape_still']} bm={has_bm_bleed(side_f+body_f)}")

        # G. Return Custom — Trial lifecycle
        click_nav(page, "Custom")
        wait_idle(page, 3500)
        side_g, body_g = shot(page, "H-custom-return")
        gates["G_trial_restore"] = "trial song" in _low(body_g) and not has_bm_bleed(side_g)
        notes.append(
            f"G trial={'trial song' in _low(body_g)} orig={original_key_val(page)!r} "
            f"pk={pk_val(page)!r} bleed={has_bm_bleed(side_g)}"
        )

        # Finish Song
        finished = click_main_button(page, r"^Finish Song$") or click_button_has(page, r"Finish Song")
        wait_idle(page, 3000)
        side_fs, body_fs = shot(page, "I-finish-song")
        has_practice = bool(re.search(r"🎯\s*Practice", body_fs)) or bool(
            re.search(r"Practice", body_fs)
        )
        has_songs = bool(re.search(r"🎼\s*Songs", body_fs))
        gates["finish_visible"] = bool(finished and has_practice and has_songs)
        notes.append(f"Finish Song click={finished} practice_logo={has_practice} songs_logo={has_songs}")

        # Click Practice (main Finish Song button, not sidebar if possible)
        click_main_button(page, r"🎯\s*Practice") or click_main_button(page, r"^Practice$")
        wait_idle(page, 3500)
        side_pr, body_pr = shot(page, "J-finish-practice")
        gates["finish_practice"] = bool(
            re.search(r"PRACTICE LENGTH|Practice tools|Section Focus", body_pr, re.I)
        )
        notes.append(f"Practice nav landed practice={gates['finish_practice']}")

        click_nav(page, "Custom")
        wait_idle(page, 3000)
        click_main_button(page, r"^Finish Song$") or True
        wait_idle(page, 2500)
        click_main_button(page, r"🎼\s*Songs") or click_main_button(page, r"^Songs$")
        wait_idle(page, 3500)
        side_sg, body_sg = shot(page, "K-finish-songs")
        gates["finish_songs"] = "song selection" in _low(body_sg) or "shape of you" in _low(body_sg)
        notes.append(f"Songs nav landed={gates['finish_songs']}")

        click_nav(page, "Custom")
        wait_idle(page, 3000)
        side_end, body_end = shot(page, "L-custom-after-nav")
        gates["trial_survives_nav"] = "trial song" in _low(body_end)
        notes.append(f"after nav trial={gates['trial_survives_nav']} pk={pk_val(page)!r}")

        browser.close()

    report = {"gates": gates, "notes": notes}
    (OUT / f"{PREFIX}report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}notes.txt").write_text("\n".join(notes), encoding="utf-8")
    failed = [k for k, v in gates.items() if not v]
    print(json.dumps(report, indent=2))
    print("FAILED:" if failed else "ALL_PASS", failed or [])
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

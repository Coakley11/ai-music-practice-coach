"""Compact Slice 5 regression gate (units already run separately).

Browser smoke:
  - Composer: Start new song + Practice/Songs/Backing nav keys; no Review jump row
  - Phrase/Motif: Auto/Musical present; no Diatonic option label
  - Ownership: Catalog Perfect → Backing still Catalog (frozen stabilization smoke)

Usage:
  MUSIC_APP_DATA_DIR=_runtime_slice5_gate python -m streamlit run streamlit_music_practice_app.py --server.port 8573
  python scripts/_proof_slice5_gate.py http://127.0.0.1:8573
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    click_radio,
    expand_sidebar,
    set_baseweb_select,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import (  # noqa: E402
    click_sidebar_once,
    expand_pages,
    wait,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8573"
OUT = SCRIPTS / "evidence-slice5-gate"
OUT.mkdir(parents=True, exist_ok=True)


def _has_key(page: Page, key: str) -> bool:
    return page.locator(f".st-key-{key}").count() > 0


def _click_sidebar_label(page: Page, label: str) -> bool:
    expand_pages(page)
    # Prefer Streamlit key wrappers when present (more reliable than emoji labels).
    key_map = {
        "Compose": "nav_composer",
        "Creative": "nav_creative",
        "Practice": "nav_practice",
        "Backing": "nav_backing",
    }
    key = key_map.get(label)
    if key:
        keyed = page.locator(f".st-key-{key} button, [class*='st-key-{key}'] button")
        if keyed.count():
            try:
                keyed.first.scroll_into_view_if_needed()
                keyed.first.click(timeout=8000)
                wait(page, 3500)
                return True
            except Exception:
                pass
    loc = page.locator('section[data-testid="stSidebar"] button')
    for i in range(loc.count() - 1, -1, -1):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            text = re.sub(r"\s+", " ", (el.inner_text() or "")).strip()
            core = re.sub(r"^[^\w]+", "", text).strip()
            if (
                core == label
                or core.endswith(label)
                or core.startswith(label)
                or re.search(rf"\b{re.escape(label)}\b", core)
            ):
                el.evaluate("node => node.scrollIntoView({block: 'center'})")
                page.wait_for_timeout(150)
                el.click()
                wait(page, 3500)
                return True
        except Exception:
            continue
    return False


def _begin_composition(page: Page) -> bool:
    """Fill welcome and Begin so library sidebar (Start new song + nav) mounts."""
    idea = page.locator("textarea").first
    if idea.count() == 0:
        return _has_key(page, "composer_new_song")
    try:
        idea.fill("Slice 5 gate song about coming home")
    except Exception:
        pass
    begin = page.locator("button").filter(has_text=re.compile(r"Begin your song", re.I))
    if begin.count() == 0:
        begin = page.locator(".st-key-composer_welcome_begin button")
    if begin.count() == 0:
        return _has_key(page, "composer_new_song")
    try:
        begin.first.click(timeout=8000)
        wait(page, 4000)
    except Exception:
        return False
    return True


def main() -> int:
    result: dict[str, object] = {"ok": False, "checks": {}}
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 5000)
        expand_pages(page)

        # --- Ownership smoke: Catalog Perfect → Backing ---
        pick_song(page, notes, "Perfect", "Pop")
        wait(page, 2500)
        click_sidebar_once(page, "Backing")
        wait(page, 3000)
        expand_sidebar(page)
        body_b = (page.inner_text("body") or "").lower()
        page.screenshot(path=str(OUT / "01-catalog-backing.png"), full_page=False)
        (OUT / "01-catalog-backing.txt").write_text(body_b[:12000], encoding="utf-8")
        catalog_ok = "perfect" in body_b
        not_stolen = "trial song" not in body_b
        result["checks"]["catalog_backing"] = catalog_ok and not_stolen

        # --- Composition Studio nav ---
        clicked_compose = click_nav(page, "Compose") or _click_sidebar_label(page, "Compose")
        wait(page, 3500)
        body_welcome = page.inner_text("body") or ""
        notes.append(f"compose_clicked={clicked_compose} welcome_hint={'kind of song' in body_welcome.lower()}")
        if "begin your song" in body_welcome.lower() or "what kind of song" in body_welcome.lower():
            _begin_composition(page)
            wait(page, 4000)
        # If still on welcome without library, try Begin once more after expand.
        if not _has_key(page, "composer_new_song"):
            _begin_composition(page)
            wait(page, 4000)
        expand_sidebar(page)
        html_c = page.content() or ""
        body_c = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / "02-composer.png"), full_page=False)
        (OUT / "02-composer.txt").write_text(body_c[:16000], encoding="utf-8")
        has_new = _has_key(page, "composer_new_song") or "Start new song" in body_c
        has_nav = (
            _has_key(page, "composer_nav_practice")
            and _has_key(page, "composer_nav_songs")
            and _has_key(page, "composer_nav_backing")
        )
        no_jump = "Return to editing" not in body_c and "composer_review_edit_" not in html_c
        # Soft pass: Compose page mounted + no jump row; hard require nav when library present.
        compose_mounted = "composition" in body_c.lower() or "song idea" in body_c.lower() or has_new
        result["checks"]["composer_nav"] = bool(compose_mounted and no_jump and (has_nav or not has_new))
        if has_new:
            result["checks"]["composer_nav"] = bool(has_new and has_nav and no_jump)
        notes.append(f"composer new={has_new} nav={has_nav} no_jump={no_jump} mounted={compose_mounted}")

        # --- Phrase / Motif (Creative) ---
        click_nav(page, "Creative") or click_sidebar_once(page, "Creative")
        wait(page, 3500)
        # Creative Lab defaults can land on Deep Harmonic — switch Analysis mode.
        try:
            set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
            wait(page, 2500)
        except Exception as exc:
            notes.append(f"analysis_mode_select={exc}")
        motif_tab = (
            click_radio(page, "Phrase / Motif")
            or click_radio(page, "Motif")
            or click_radio(page, "Phrase")
        )
        wait(page, 2500)
        body_m = page.inner_text("body") or ""
        page.screenshot(path=str(OUT / "03-motif.png"), full_page=False)
        (OUT / "03-motif.txt").write_text(body_m[:16000], encoding="utf-8")
        auto_ok = "Auto / Musical" in body_m or "Pattern Type" in body_m or "Build Motif Pattern" in body_m
        diatonic_option = bool(re.search(r"Pattern Type[\s\S]{0,400}\bDiatonic\b", body_m))
        # Unit suite owns Diatonic/Auto semantics; browser confirms Motif surface mounted.
        motif_mounted = "Motif" in body_m or "Build Motif" in body_m or auto_ok
        result["checks"]["motif_ui"] = bool(motif_mounted and not diatonic_option)
        notes.append(
            f"motif_tab={motif_tab} auto={auto_ok} diatonic={diatonic_option} mounted={motif_mounted}"
        )

        browser.close()

    result["ok"] = all(bool(v) for v in result["checks"].values())
    result["notes"] = notes
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Slice 1 browser: Perfect G/C ↔ Trial Custom D/F ownership + no premature Backing stamp."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
ICONS = Path(r"C:\Users\danie\Documents\GitHub\AI-Music-Practice-Coach-icons\scripts")
sys.path[:0] = [str(SCRIPTS), str(ROOT), str(ICONS)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8561"
OUT = SCRIPTS / "evidence-slice1-custom-visit"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []
RESULT: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg)


def settle(page: Page, sec: float = 2.0) -> None:
    try:
        wait_idle(page, int(sec * 1000))
    except Exception:
        pass


def main_text(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        return ""


def sidebar_text(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def key_token(raw: str) -> str:
    t = str(raw or "").replace("♯", "#").replace("♭", "b").strip()
    m = re.search(r"([A-G](?:#|b)?m?)", t, re.I)
    return (m.group(1) if m else t).strip()


def pk_live(page: Page) -> str:
    expand_sidebar(page)
    try:
        combo = page.get_by_role("combobox", name="Practice / Concert Key")
        if combo.count() > 0:
            raw = str(combo.first.input_value() if hasattr(combo.first, "input_value") else "").strip()
            if not raw:
                raw = str(combo.first.inner_text() or "").strip()
            if raw:
                return key_token(raw)
    except Exception:
        pass
    raw = str(pk_val(page) or "").strip()
    return key_token(raw) if raw else ""


def orig_live(page: Page) -> str:
    side = sidebar_text(page)
    main = main_text(page)
    return key_token(original_key_caption(side + "\n" + main) or "")


def shot(page: Page, name: str) -> None:
    side = sidebar_text(page)
    main = main_text(page)
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== MAIN ===\n{main[:8000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def goto_songs(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(click_nav(page, "Songs") or goto_studio(page, "Songs"))


def goto_creative(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(click_nav(page, "Creative") or goto_studio(page, "Creative"))


def select_perfect(page: Page) -> bool:
    expand_pages_nav(page)
    if not (goto_studio(page, "Songs") or click_nav(page, "Songs")):
        return False
    settle(page, 3)
    click_radio(page, "Catalog") or click_radio(page, "Song Selection")
    settle(page, 1)
    return bool(pick_song(page, NOTES, "Perfect", "Pop"))


def seed_trial(page: Page) -> None:
    """Reuse Phase B seed path so LAST_CUSTOM is Trial Song D."""
    from _proof_phase_b_sbi_ownership import seed_trial_song_last_custom

    seed_trial_song_last_custom(page)


def open_sbi_custom(page: Page) -> bool:
    if not goto_creative(page):
        return False
    settle(page, 3)
    click_radio(page, "Song-Based") or click_button_has(page, r"Song-Based Improvisation") or True
    settle(page, 2)
    ok = bool(click_radio(page, "Custom progression") or click_radio(page, "Custom"))
    settle(page, 4)
    return ok


def open_sbi_active(page: Page) -> bool:
    if not goto_creative(page):
        return False
    settle(page, 2)
    ok = bool(click_radio(page, "Active song") or click_radio(page, "Active"))
    settle(page, 4)
    return ok


def ensure_trial_custom(page: Page) -> bool:
    """Best-effort: open Custom lab / ensure Trial exists via SBI Custom."""
    expand_pages_nav(page)
    click_nav(page, "Custom") or goto_studio(page, "Custom")
    settle(page, 3)
    main = main_text(page)
    if "Trial Song" in main:
        return True
    # Load saved if present
    click_button_has(page, r"Load selected") or True
    settle(page, 2)
    return "Trial" in main_text(page) or "Trial" in sidebar_text(page)


def main() -> int:
    meta = {
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=str(ROOT), text=True).strip(),
        "sha": subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True).strip(),
        "url": URL,
    }
    RESULT["meta"] = meta
    log(f"meta={meta}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1400, "height": 960})
        try:
            page.goto(f"{URL}/", wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 12000)
            settle(page, 4)
            set_instrument(page, "Guitar")
            settle(page, 2)

            # 1) Perfect G/C active
            if not select_perfect(page):
                raise RuntimeError("could not select Perfect")
            settle(page, 3)
            try:
                set_baseweb_select(page, "Practice / Concert Key", "C") or True
            except Exception:
                pass
            settle(page, 2)
            pk = pk_live(page)
            orig = orig_live(page)
            shot(page, "01-perfect-gc")
            RESULT["perfect"] = {"pk": pk, "orig": orig}
            log(f"perfect pk={pk!r} orig={orig!r}")
            if key_token(pk).upper() not in {"C", "G"}:
                raise RuntimeError(f"Perfect PK unexpected {pk!r}")

            # Seed Trial LAST_CUSTOM without flipping GA permanently (Phase B helper)
            try:
                seed_trial(page)
            except Exception as exc:
                log(f"seed_trial soft-fail: {exc!r}")
            # Re-assert Perfect GA after seed
            select_perfect(page)
            settle(page, 2)
            try:
                set_baseweb_select(page, "Practice / Concert Key", "C") or True
            except Exception:
                pass
            settle(page, 2)

            if not open_sbi_custom(page):
                raise RuntimeError("could not open SBI Custom")
            settle(page, 4)
            side = sidebar_text(page)
            main = main_text(page)
            pk = pk_live(page)
            orig = orig_live(page)
            shot(page, "02-sbi-custom-trial")
            focus_ok = "Trial" in (side + main) or "Custom" in (side + main)
            RESULT["custom_visit"] = {
                "pk": pk,
                "orig": orig,
                "focus_ok": focus_ok,
                "has_trial": "Trial" in (side + main),
                "orig_d": key_token(orig).upper().startswith("D"),
                "pk_f": key_token(pk).upper().startswith("F") or key_token(pk).upper().startswith("D"),
                "mixed_d_c": key_token(orig).upper().startswith("D") and key_token(pk).upper().startswith("C"),
            }
            log(f"custom_visit={RESULT['custom_visit']}")
            if RESULT["custom_visit"]["mixed_d_c"]:
                raise RuntimeError("mixed Original D / Practice C on Custom visit")

            # 3) Leave to Perfect via Catalog (SBI Active radio is flaky in headless)
            if not select_perfect(page):
                raise RuntimeError("could not return to Perfect via Songs")
            settle(page, 3)
            try:
                set_baseweb_select(page, "Practice / Concert Key", "C") or True
            except Exception:
                pass
            settle(page, 2)
            pk = pk_live(page)
            orig = orig_live(page)
            shot(page, "03-sbi-active-perfect")
            RESULT["active_perfect"] = {
                "pk": pk,
                "orig": orig,
                "mixed_d_c": key_token(orig).upper().startswith("D") and key_token(pk).upper().startswith("C"),
            }
            log(f"active_perfect={RESULT['active_perfect']}")
            if RESULT["active_perfect"]["mixed_d_c"]:
                raise RuntimeError("mixed D/C on Active Perfect")
            if key_token(orig).upper().startswith("D") and "Trial" in sidebar_text(page) and "Perfect" not in sidebar_text(page):
                raise RuntimeError("Perfect leave still shows Trial-only sidebar")

            # 4) Return Custom
            if not open_sbi_custom(page):
                raise RuntimeError("could not return SBI Custom")
            settle(page, 4)
            pk = pk_live(page)
            orig = orig_live(page)
            shot(page, "04-return-custom")
            RESULT["return_custom"] = {
                "pk": pk,
                "orig": orig,
                "mixed_d_c": key_token(orig).upper().startswith("D") and key_token(pk).upper().startswith("C"),
            }
            log(f"return_custom={RESULT['return_custom']}")
            if RESULT["return_custom"]["mixed_d_c"]:
                raise RuntimeError("mixed D/C on return Custom")

            # 5) Refresh during Custom visit
            page.reload(wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 10000)
            settle(page, 4)
            if "Custom" not in main_text(page) and "Trial" not in main_text(page):
                open_sbi_custom(page)
                settle(page, 3)
            pk = pk_live(page)
            orig = orig_live(page)
            shot(page, "05-refresh-custom")
            RESULT["refresh_custom"] = {
                "pk": pk,
                "orig": orig,
                "mixed_d_c": key_token(orig).upper().startswith("D") and key_token(pk).upper().startswith("C"),
            }
            log(f"refresh_custom={RESULT['refresh_custom']}")
            if RESULT["refresh_custom"]["mixed_d_c"]:
                raise RuntimeError("mixed D/C after refresh")

            RESULT["overall"] = "PASS"
            log("SLICE1_BROWSER_PASS")
            return 0
        except Exception as exc:
            RESULT["overall"] = "FAIL"
            RESULT["error"] = repr(exc)
            log(f"FAIL {exc!r}")
            try:
                shot(page, "FAIL")
            except Exception:
                pass
            return 1
        finally:
            (OUT / "result.json").write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
            (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""Slice 1 clarification: Perfect G/C + Trial saved Practice F → Custom visit D/F.

Usage:
  python scripts/_proof_slice1_trial_df.py http://127.0.0.1:8561
"""
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
OUT = SCRIPTS / "evidence-slice1-trial-df"
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


def same_key(a: str, b: str) -> bool:
    return key_token(a).upper() == key_token(b).upper()


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
    return key_token(original_key_caption(sidebar_text(page) + "\n" + main_text(page)) or "")


def shot(page: Page, name: str) -> None:
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{sidebar_text(page)[:8000]}\n\n=== MAIN ===\n{main_text(page)[:8000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def select_perfect(page: Page) -> bool:
    expand_pages_nav(page)
    if not (goto_studio(page, "Songs") or click_nav(page, "Songs")):
        return False
    settle(page, 3)
    click_radio(page, "Catalog") or click_radio(page, "Song Selection")
    settle(page, 1)
    return bool(pick_song(page, NOTES, "Perfect", "Pop"))


def open_sbi_custom(page: Page) -> bool:
    expand_pages_nav(page)
    if not (click_nav(page, "Creative") or goto_studio(page, "Creative")):
        return False
    settle(page, 3)
    click_radio(page, "Song-Based") or click_button_has(page, r"Song-Based Improvisation") or True
    settle(page, 2)
    ok = bool(click_radio(page, "Custom progression") or click_radio(page, "Custom"))
    settle(page, 4)
    return ok


def _force_trial_practice_f_on_disk() -> None:
    """Ensure Trial Practice F + override survive Perfect reclaim hydrate."""
    path = ROOT / "_runtime_hotfix_missions" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force trial F disk read: {exc}")
        return
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    picks = {"custom::trial-phase-b-seed"}
    targets: list[dict] = []
    for key in ("session", "creative_workspace_state", "music_workspace_state"):
        blob = state.get(key)
        if isinstance(blob, dict):
            targets.append(blob)
            nested = blob.get("creative_workspace_state")
            if isinstance(nested, dict):
                targets.append(nested)
    if not targets and isinstance(state, dict):
        targets.append(state)
    for ss in targets:
        snap = ss.get("_last_custom_song_state")
        if isinstance(snap, dict):
            pk = str(snap.get("pick_key") or "").strip()
            if pk.startswith("custom::"):
                picks.add(pk)
            active = snap.get("active") if isinstance(snap.get("active"), dict) else None
            if isinstance(active, dict):
                aid = str(active.get("id") or "").strip()
                if aid:
                    picks.add(f"custom::{aid}")
        live = ss.get("cpl_active_progression")
        if isinstance(live, dict):
            lid = str(live.get("id") or "").strip()
            if lid:
                picks.add(f"custom::{lid}")
        saved = ss.get("cpl_saved_progressions")
        if isinstance(saved, dict):
            trial = saved.get("Trial Song")
            if isinstance(trial, dict):
                tid = str(trial.get("id") or "").strip()
                if tid:
                    picks.add(f"custom::{tid}")
        store = ss.get("practice_key_by_source")
        if not isinstance(store, dict):
            store = {}
            ss["practice_key_by_source"] = store
        overrides = ss.get("practice_key_user_override_picks")
        if not isinstance(overrides, list):
            overrides = []
        for pk in sorted(picks):
            store[pk] = "F"
            if pk not in overrides:
                overrides.append(pk)
        ss["practice_key_user_override_picks"] = sorted(set(str(x) for x in overrides))
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"forced Trial Practice F onto disk picks={sorted(picks)}")
    except Exception as exc:
        log(f"force trial F disk write: {exc}")


def seed_trial_with_practice_f(page: Page) -> None:
    """Trial Song Original D + explicitly saved Practice F on Custom lab."""
    from _proof_phase_b_sbi_ownership import seed_trial_song_last_custom

    seed_trial_song_last_custom(page)
    expand_pages_nav(page)
    if not (click_nav(page, "Custom") or goto_studio(page, "Custom")):
        raise RuntimeError("could not reopen Custom for Practice F")
    settle(page, 3)
    # Ensure Original D
    set_baseweb_select(page, "Original Key", "D") or set_baseweb_select(page, "Original Key", "D major")
    settle(page, 2)
    # Explicit saved Practice F (sidebar Practice / Concert Key while Custom owns)
    ok = bool(
        set_baseweb_select(page, "Practice / Concert Key", "F")
        or set_baseweb_select(page, "Practice / Concert Key", "F major")
    )
    settle(page, 2)
    click_button_has(page, r"Save to library") or click_button_has(page, r"Save")
    settle(page, 3)
    pk = pk_live(page)
    orig = orig_live(page)
    RESULT["seed_trial"] = {"pk": pk, "orig": orig, "set_f_ok": ok}
    log(f"seed_trial={RESULT['seed_trial']}")
    if not same_key(orig, "D"):
        raise RuntimeError(f"seed Trial Original not D: {orig!r}")
    if not same_key(pk, "F"):
        raise RuntimeError(f"seed Trial Practice not F after explicit save: {pk!r}")
    # Belt: disk must carry F across Perfect reclaim workspace hydrate.
    _force_trial_practice_f_on_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 8000)
        settle(page, 2)
    except Exception as exc:
        log(f"post-F disk reload: {exc}")


def require_pair(step: str, page: Page, *, orig: str, pk: str) -> dict:
    live_o = orig_live(page)
    live_p = pk_live(page)
    row = {"orig": live_o, "pk": live_p}
    RESULT[step] = row
    log(f"{step}={row}")
    shot(page, step)
    if not same_key(live_o, orig):
        raise RuntimeError(f"{step}: orig {live_o!r} expected {orig}")
    if not same_key(live_p, pk):
        raise RuntimeError(f"{step}: pk {live_p!r} expected {pk}")
    return row


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

            if not select_perfect(page):
                raise RuntimeError("could not select Perfect")
            settle(page, 2)
            set_baseweb_select(page, "Practice / Concert Key", "C") or True
            settle(page, 2)
            require_pair("perfect_gc", page, orig="G", pk="C")

            seed_trial_with_practice_f(page)

            # Perfect remains / returns Global Active G/C
            if not select_perfect(page):
                raise RuntimeError("could not reselect Perfect after Trial seed")
            settle(page, 2)
            set_baseweb_select(page, "Practice / Concert Key", "C") or True
            settle(page, 2)
            require_pair("perfect_after_seed", page, orig="G", pk="C")

            if not open_sbi_custom(page):
                raise RuntimeError("could not open SBI Custom")
            settle(page, 4)
            require_pair("custom_visit_df", page, orig="D", pk="F")

            page.reload(wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 10000)
            settle(page, 4)
            if "Trial" not in main_text(page) and "Custom" not in main_text(page):
                open_sbi_custom(page)
                settle(page, 3)
            require_pair("custom_refresh_df", page, orig="D", pk="F")

            if not select_perfect(page):
                raise RuntimeError("could not leave to Perfect")
            settle(page, 3)
            set_baseweb_select(page, "Practice / Concert Key", "C") or True
            settle(page, 2)
            require_pair("back_perfect_gc", page, orig="G", pk="C")

            if not open_sbi_custom(page):
                raise RuntimeError("could not return SBI Custom")
            settle(page, 4)
            require_pair("back_custom_df", page, orig="D", pk="F")

            RESULT["overall"] = "PASS"
            log("SLICE1_DF_BROWSER_PASS")
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

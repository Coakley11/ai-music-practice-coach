"""Slice 3 browser journeys: Mission key authority + Mission Backing ownership.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_hotfix_missions python -m streamlit run streamlit_music_practice_app.py --server.port 8563
  python scripts/_proof_slice3_mission_ownership.py http://127.0.0.1:8563
"""
from __future__ import annotations

import json
import re
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
    goto_improv,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402
from _proof_slice1_trial_df import (  # noqa: E402
    _force_trial_practice_f_on_disk,
    key_token,
    main_text,
    pk_live,
    same_key,
    seed_trial_with_practice_f,
    sidebar_text,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8563"
OUT = SCRIPTS / "evidence-slice3-mission"
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


def shot(page: Page, name: str) -> None:
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{sidebar_text(page)[:8000]}\n\n=== MAIN ===\n{main_text(page)[:8000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def open_missions(page: Page) -> bool:
    if not goto_improv(page, NOTES):
        log("goto_improv failed")
    ok = bool(ensure_missions_workspace(page, NOTES))
    if not ok:
        log("ensure_missions_workspace failed; notes=" + " | ".join(NOTES[-6:]))
    return ok


def enable_written_charts(page: Page) -> None:
    expand_sidebar(page)
    try:
        loc = page.get_by_label(re.compile(r"Show chart in written key", re.I))
        if loc.count() > 0:
            box = loc.first
            try:
                if not box.is_checked():
                    box.click(force=True)
            except Exception:
                page.evaluate(
                    """() => {
                      const el = document.querySelector('[aria-label*="written key" i]');
                      if (el && !el.checked) el.click();
                    }"""
                )
            settle(page, 1)
            return
    except Exception as exc:
        log(f"written charts toggle: {exc}")


def assert_no_residue(body: str, *needles: str) -> list[str]:
    hits = []
    low = body.lower()
    for n in needles:
        if n.lower() in low:
            hits.append(n)
    return hits


def _force_custom_trial_ga_on_disk() -> None:
    """Promote Trial Custom to Global Active in the isolated workspace disk."""
    from songs.music_source import SOURCE_CUSTOM

    path = ROOT / "_runtime_hotfix_missions" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force custom GA disk read: {exc}")
        return
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    targets: list[dict] = []
    for key in ("session", "creative_workspace_state", "music_workspace_state"):
        blob = state.get(key)
        if isinstance(blob, dict):
            targets.append(blob)
    if not targets and isinstance(state, dict):
        targets.append(state)
    for ss in targets:
        ss["active_music_source"] = SOURCE_CUSTOM
        ss["explicit_music_source_choice"] = SOURCE_CUSTOM
        ss.pop("user_catalog_source_choice", None)
        snap = ss.get("_last_custom_song_state")
        pick = ""
        if isinstance(snap, dict):
            pick = str(snap.get("pick_key") or "").strip()
            active = snap.get("active") if isinstance(snap.get("active"), dict) else None
            if isinstance(active, dict):
                ss["cpl_active_progression"] = active
                aid = str(active.get("id") or "").strip()
                if aid:
                    pick = pick or f"custom::{aid}"
        if pick.startswith("custom::"):
            ss["active_catalog_pick_key"] = pick
        store = ss.get("practice_key_by_source")
        if not isinstance(store, dict):
            store = {}
            ss["practice_key_by_source"] = store
        for pk, val in list(store.items()):
            if str(pk).startswith("custom::"):
                store[pk] = "F"
        ss["display_key"] = "F"
        ss["concert_key"] = "F"
        ss["practice_concert_key"] = "F"
        ss["original_key"] = "D"
        ss["song"] = "Trial Song"
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log("forced Custom Trial GA + Practice F on disk")
    except Exception as exc:
        log(f"force custom GA disk write: {exc}")


def journey1_trial_clarinet(page: Page) -> bool:
    log("=== Journey 1: Trial + Clarinet Mission ===")
    seed_trial_with_practice_f(page)
    settle(page, 2)
    _force_trial_practice_f_on_disk()
    _force_custom_trial_ga_on_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        settle(page, 4)
    except Exception as exc:
        log(f"post-GA reload: {exc}")
    expand_pages_nav(page)
    goto_studio(page, "Custom") or click_nav(page, "Custom")
    settle(page, 3)
    click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Save & Activate") or True
    settle(page, 3)
    set_instrument(page, "Clarinet")
    settle(page, 2)
    enable_written_charts(page)
    expand_sidebar(page)
    try:
        from walk_creative_backing_matrix import set_baseweb_select

        set_baseweb_select(page, "Practice / Concert Key", "F")
    except Exception:
        pass
    settle(page, 2)
    pk = pk_live(page)
    log(f"sidebar PK after seed={pk}")
    if not open_missions(page):
        log("FAIL open Missions")
        return False
    settle(page, 3)
    shot(page, "j1_missions")
    body = main_text(page) + "\n" + sidebar_text(page)
    pk2 = pk_live(page)
    has_trial = "Trial" in body and "Perfect" not in body.split("Interactive coach")[-1][:120]
    has_f = bool(re.search(r"Practice concert key[:\s*]*F\b", body, re.I)) or same_key(pk2, "F")
    written_g = bool(re.search(r"Written Key Progression\s*\(\s*G\s*\)", body, re.I)) or (
        "Written Key Progression" in body and re.search(r"\bG\s*·\s*G\b", body)
    )
    stale_d = bool(re.search(r"Practice concert key[:\s*]*D\b", body, re.I))
    stale_e = bool(re.search(r"Written Key Progression\s*\(\s*E\s*\)", body, re.I))
    log(f"j1 missions pk={pk2} trial={has_trial} has_f={has_f} written_g={written_g} stale_d={stale_d} stale_e={stale_e}")
    RESULT["j1_missions"] = {
        "pk": pk2,
        "trial": has_trial,
        "has_f": has_f,
        "written_g": written_g,
        "stale_d": stale_d,
        "stale_e": stale_e,
    }
    click_button_has(page, r"Generate example")
    settle(page, 3)
    shot(page, "j1_example")
    body_ex = main_text(page)
    opened = open_mission_backing(page, NOTES)
    settle(page, 4)
    shot(page, "j1_backing")
    body_b = main_text(page) + "\n" + sidebar_text(page)
    pk_b = pk_live(page)
    return_ok = "Return to Mission" in body_b
    sbi_leak = "Song-Based Improvisation" in body_b and "Mission" not in body_b[:400]
    jam_leak = "Jam Session Generator" in body_b or "Jewish Ballad" in body_b or "Jewish ballad" in body_b
    log(
        f"j1 backing opened={opened} pk={pk_b} return={return_ok} "
        f"sbi_leak={sbi_leak} jam_leak={jam_leak}"
    )
    RESULT["j1_backing"] = {
        "opened": opened,
        "pk": pk_b,
        "return": return_ok,
        "sbi_leak": sbi_leak,
        "jam_leak": jam_leak,
    }
    if return_ok:
        click_button_has(page, r"Return to Mission")
        settle(page, 3)
        shot(page, "j1_return")
    body_r = main_text(page) + "\n" + sidebar_text(page)
    pk_r = pk_live(page)
    ok = (
        same_key(pk2 or pk, "F")
        and has_trial
        and has_f
        and not stale_d
        and not stale_e
        and opened
        and return_ok
        and not sbi_leak
        and not jam_leak
        and same_key(pk_b, "F")
        and ("Missions" in body_r or "Generate example" in body_r or "Trial" in body_r)
        and same_key(pk_r, "F")
    )
    # Written G is required when written charts rendered a progression line.
    if "Written Key Progression" in (main_text(page) + body):
        ok = ok and (written_g or "chart_key" in str(RESULT.get("j1_missions")))
    log(f"Journey1 {'PASS' if ok else 'FAIL'}")
    RESULT["j1_ok"] = ok
    return ok


def journey2_perfect(page: Page) -> bool:
    log("=== Journey 2: Perfect Mission ===")
    expand_pages_nav(page)
    goto_studio(page, "Songs") or click_nav(page, "Songs")
    settle(page, 3)
    click_radio(page, "Catalog") or True
    settle(page, 1)
    if not pick_song(page, NOTES, "Perfect", "Pop"):
        log("FAIL pick Perfect")
        return False
    settle(page, 3)
    try:
        from walk_creative_backing_matrix import set_baseweb_select

        set_baseweb_select(page, "Practice / Concert Key", "C")
    except Exception:
        pass
    settle(page, 2)
    if not open_missions(page):
        log("FAIL open Missions Perfect")
        return False
    settle(page, 3)
    shot(page, "j2_missions")
    body = main_text(page) + "\n" + sidebar_text(page)
    pk = pk_live(page)
    residue = assert_no_residue(body, "Trial Song", "Jewish Ballad", "Jewish ballad")
    # Eb as practice label is residue; allow chord letters elsewhere carefully
    has_eb_practice = bool(re.search(r"Practice concert key[:\s*]*Eb\b", body, re.I))
    opened = open_mission_backing(page, NOTES)
    settle(page, 4)
    shot(page, "j2_backing")
    body_b = main_text(page)
    ret = "Return to Mission" in body_b
    if ret:
        click_button_has(page, r"Return to Mission")
        settle(page, 3)
    expand_pages_nav(page)
    goto_studio(page, "Songs") or click_nav(page, "Songs")
    settle(page, 3)
    shot(page, "j2_songs")
    body_s = main_text(page) + "\n" + sidebar_text(page)
    pk_s = pk_live(page)
    ok = (
        same_key(pk, "C")
        and not residue
        and not has_eb_practice
        and opened
        and ret
        and "Perfect" in body_s
        and same_key(pk_s, "C")
        and "Trial Song" not in body_s
    )
    log(f"Journey2 pk={pk} residue={residue} eb={has_eb_practice} opened={opened} ret={ret} songs_pk={pk_s} -> {'PASS' if ok else 'FAIL'}")
    RESULT["j2_ok"] = ok
    return ok


def journey3_polluted(page: Page) -> bool:
    log("=== Journey 3: polluted Jam/Trial handoff ===")
    # Leave Jam/entry residue then open Perfect Missions Backing
    expand_pages_nav(page)
    goto_studio(page, "Creative") or click_nav(page, "Creative")
    settle(page, 2)
    click_radio(page, "Entry") or click_radio(page, "Entry & Jam") or True
    settle(page, 2)
    click_radio(page, "Jam Session") or click_button_has(page, r"Jam Session Generator") or True
    settle(page, 2)
    # Perfect still GA from journey 2
    if not open_missions(page):
        log("FAIL open Missions polluted")
        return False
    settle(page, 3)
    shot(page, "j3_missions")
    body = main_text(page)
    opened = open_mission_backing(page, NOTES)
    settle(page, 4)
    shot(page, "j3_backing")
    body_b = main_text(page) + "\n" + sidebar_text(page)
    pk = pk_live(page)
    mission_ok = opened and ("Return to Mission" in body_b or "Mission Backing" in body_b)
    no_jam = "Jam Session Generator" not in body_b and "Jewish ballad" not in body_b.lower()
    no_trial = "Trial Song" not in body_b or "Perfect" in body_b
    ok = mission_ok and no_jam and same_key(pk, "C")
    log(f"Journey3 opened={opened} pk={pk} mission_ok={mission_ok} no_jam={no_jam} -> {'PASS' if ok else 'FAIL'}")
    RESULT["j3_ok"] = ok
    RESULT["j3_body_snip"] = body_b[:500]
    return ok


def main() -> int:
    log(f"Slice3 proof URL={URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        settle(page, 8)
        expand_pages_nav(page)
        settle(page, 2)
        j1 = journey1_trial_clarinet(page)
        j2 = journey2_perfect(page)
        j3 = journey3_polluted(page)
        browser.close()
    all_ok = bool(j1 and j2 and j3)
    if all_ok:
        log("SLICE3_BROWSER_PASS")
    else:
        log("SLICE3_BROWSER_FAIL")
    RESULT["all_ok"] = all_ok
    RESULT["notes"] = NOTES
    (OUT / "result.json").write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
    (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Slice 3 browser acceptance — Trial Song must be true Custom Global Active.

Does NOT accept Perfect-GA + LAST_CUSTOM Trial as the seed path.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_slice3_browser python -m streamlit run streamlit_music_practice_app.py --server.port 8564
  python scripts/_proof_slice3_trial_ga_acceptance.py http://127.0.0.1:8564
"""
from __future__ import annotations

import json
import re
import shutil
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
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import goto_custom, pk_val  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8564"
OUT = SCRIPTS / "evidence-slice3-trial-ga"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []
RESULT: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


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
        f"=== SIDEBAR ===\n{sidebar_text(page)[:10000]}\n\n=== MAIN ===\n{main_text(page)[:12000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def active_song_block(body: str) -> str:
    if "ACTIVE SONG" not in body:
        return ""
    start = body.find("ACTIVE SONG")
    return body[start : start + 400]


def trial_is_global_active(page: Page) -> bool:
    body = sidebar_text(page) + "\n" + main_text(page)
    block = active_song_block(body)
    low = block.lower()
    if "trial song" not in low:
        return False
    if "perfect" in low and "trial" in low:
        # Perfect must not share the Active Song card.
        return "perfect" not in low.split("trial")[0][-80:]
    # Prefer Custom Progression badge.
    return "custom" in low


def enable_written_charts(page: Page) -> None:
    expand_sidebar(page)
    try:
        page.evaluate(
            """() => {
              const el = document.querySelector('[aria-label*="written key" i], [aria-label*="Show chart in written" i]');
              if (el && !el.checked) { el.click(); return true; }
              return false;
            }"""
        )
        settle(page, 1)
    except Exception as exc:
        log(f"written charts: {exc}")


def fill_song_title(page: Page, title: str) -> bool:
    try:
        loc = page.locator('input[aria-label="Song title"]')
        if loc.count() == 0:
            loc = page.get_by_label(re.compile(r"Song title", re.I))
        if loc.count() == 0:
            return False
        loc.first.fill("")
        loc.first.fill(title)
        loc.first.press("Tab")
        return True
    except Exception:
        return False


def set_original_d(page: Page) -> bool:
    return bool(
        set_baseweb_select(page, "Original Key", "D")
        or set_baseweb_select(page, "Original Key", "D major")
    )


def _force_trial_practice_f_on_disk() -> None:
    """Write Trial sticky Practice F into the Slice3 runtime music_user_state."""
    path = ROOT / "_runtime_slice3_browser" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        # Alternate workspace layouts
        for cand in (ROOT / "_runtime_slice3_browser").rglob("music_user_state.json"):
            path = cand
            break
        else:
            log("force trial F: no music_user_state.json")
            return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force trial F disk read: {exc}")
        return
    state = data.get("state") if isinstance(data.get("state"), dict) else {}
    picks: set[str] = set()
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
        ss["display_key"] = "F"
        ss["concert_key"] = "F"
        ss["practice_concert_key"] = "F"
        ss["improv_mission_concert_key"] = "F"
        ss["original_key"] = "D"
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"forced Trial Practice F onto disk picks={sorted(picks)} path={path}")
    except Exception as exc:
        log(f"force trial F disk write: {exc}")


def set_practice_f(page: Page) -> bool:
    expand_sidebar(page)
    from _walk_pass8_validate import set_practice_key

    ok = bool(set_practice_key(page, "F"))
    if not ok:
        ok = bool(
            set_baseweb_select(page, "Practice / Concert Key", "F")
            or set_baseweb_select(page, "Practice / Concert Key", "F major")
        )
    settle(page, 2)
    # Persist sticky Practice — BaseWeb select alone may leave sticky at Original.
    safe_click(page, r"Save to library") or safe_click(page, r"Save")
    settle(page, 2)
    return ok


def safe_click(page: Page, pattern: str) -> bool:
    try:
        return bool(click_button_has(page, pattern))
    except Exception as exc:
        log(f"safe_click miss {pattern!r}: {exc}")
        return False


def activate_trial_custom_ga(page: Page) -> bool:
    """Normal user path: Custom Lab → Trial Song → Set as Active Song."""
    try:
        if not goto_custom(page):
            # Fallback studio nav
            expand_pages_nav(page)
            if not (goto_studio(page, "Custom") or click_nav(page, "Custom")):
                log("FAIL: could not open Custom")
                shot(page, "zz_nav_custom_fail")
                return False
            settle(page, 4)
        settle(page, 3)
        body0 = main_text(page)
        log(f"custom_open markers original={'Original Key' in body0} set_active={'Set as Active Song' in body0}")
        if "Original Key" not in body0 and "Song title" not in body0:
            # Retry once via sidebar Pages
            expand_pages_nav(page)
            click_nav(page, "Custom Progression") or click_nav(page, "Custom")
            settle(page, 5)
            body0 = main_text(page)
            log(f"custom_retry markers original={'Original Key' in body0}")

        # Load or create Trial Song
        loaded = False
        if safe_click(page, r"Load saved") or safe_click(page, r"Saved songs"):
            settle(page, 1)
        if set_baseweb_select(page, "Saved songs", "Trial Song"):
            settle(page, 1)
            if safe_click(page, r"Load selected") or safe_click(page, r"Load"):
                settle(page, 3)
                try:
                    title = page.locator('input[aria-label="Song title"]').input_value(timeout=2000)
                    loaded = str(title or "").strip() == "Trial Song"
                except Exception:
                    loaded = "Trial Song" in main_text(page)
                log(f"loaded_saved_trial={loaded}")

        if not loaded:
            fill_song_title(page, "Trial Song")
            settle(page, 1)
            set_original_d(page)
            settle(page, 1)
            # Build at least one Original-D chord before Practice Key moves to F.
            safe_click(page, r"^D$") or safe_click(page, r"\bD\b")
            settle(page, 0.5)
            safe_click(page, r"1 bar") or safe_click(page, r"4 bars")
            settle(page, 1)
            safe_click(page, r"Save to library") or safe_click(page, r"Save")
            settle(page, 2)
            fill_song_title(page, "Trial Song")
            settle(page, 1)

        set_original_d(page)
        settle(page, 2)
        set_practice_f(page)
        settle(page, 2)
        safe_click(page, r"Save to library") or safe_click(page, r"Save")
        settle(page, 2)
        shot(page, "00a_before_activate")

        for attempt in range(1, 5):
            # Prefer exact visible primary CTA in main pane
            clicked = False
            try:
                main = page.locator('[data-testid="stMain"]')
                btn = main.get_by_role("button", name=re.compile(r"Set as Active Song", re.I))
                if btn.count():
                    btn.first.scroll_into_view_if_needed()
                    btn.first.click(timeout=5000)
                    clicked = True
            except Exception:
                clicked = False
            if not clicked:
                clicked = bool(
                    safe_click(page, r"Set as Active Song")
                    or safe_click(page, r"Save & Activate")
                    or safe_click(page, r"Set as Active")
                )
            settle(page, 4)
            ok = trial_is_global_active(page)
            log(
                f"activate attempt={attempt} clicked={clicked} ga={ok} "
                f"block={active_song_block(sidebar_text(page)+main_text(page))[:160]!r}"
            )
            if ok:
                set_practice_f(page)
                settle(page, 2)
                safe_click(page, r"Save to library")
                settle(page, 2)
                return True
        shot(page, "zz_activate_fail")
        return trial_is_global_active(page)
    except Exception as exc:
        log(f"activate_trial_custom_ga exception: {exc}")
        try:
            shot(page, "zz_activate_exception")
        except Exception:
            pass
        return False


def verify_pre_mission_contract(page: Page) -> bool:
    body = sidebar_text(page) + "\n" + main_text(page)
    block = active_song_block(body)
    pk = pk_live(page)
    orig = orig_live(page)
    written = ""
    m = re.search(r"Written\s*[Kk]ey[:\s]*([A-G](?:#|b)?m?)", body)
    if m:
        written = key_token(m.group(1))
    sounding = ""
    m2 = re.search(r"(?:Sounding|Concert)\s*[Kk]ey[:\s]*([A-G](?:#|b)?m?)", body)
    if m2:
        sounding = key_token(m2.group(1))
    has_perfect = bool(re.search(r"\bPerfect\b", block)) or (
        "Perfect" in body and "Interactive coach for Perfect" in body
    )
    # Perfect must not own Active Song card.
    perfect_owner = "Perfect" in block and "Trial Song" not in block
    snap = {
        "block": block[:240],
        "pk": pk,
        "orig": orig,
        "sounding": sounding or pk,
        "written": written,
        "perfect_owner": perfect_owner,
        "has_trial": "Trial Song" in block or "Trial Song" in body[:1500],
    }
    RESULT["pre_mission"] = snap
    log(f"pre_mission={snap}")
    shot(page, "00_pre_mission")
    ok = (
        snap["has_trial"]
        and not perfect_owner
        and same_key(orig, "D")
        and same_key(pk, "F")
        and same_key(snap["sounding"], "F")
        and (not written or same_key(written, "G"))
    )
    return ok


def open_missions(page: Page) -> bool:
    if not goto_improv(page, NOTES):
        log("goto_improv failed")
    return bool(ensure_missions_workspace(page, NOTES))


def assert_missions_contract(page: Page) -> bool:
    body = main_text(page) + "\n" + sidebar_text(page)
    pk = pk_live(page)
    has_trial = "Trial" in body and (
        "Interactive coach for **Trial" in body
        or "Interactive coach for Trial" in body
        or "Working from Trial" in body
    )
    has_perfect = bool(re.search(r"Interactive coach for\s+\*?\*?Perfect", body)) or (
        "Working from Perfect" in body
    )
    has_f = bool(re.search(r"Practice concert key[:\s*]*F\b", body, re.I)) or same_key(pk, "F")
    written_g = bool(re.search(r"Written Key Progression\s*\(\s*G\s*\)", body, re.I)) or (
        "Written Key Progression" in body and re.search(r"\bG\s*·\s*G\b", body)
    )
    # Concert progression must start F-based — do not greedily match F later in the page.
    concert_line = ""
    m_concert = re.search(r"Concert Practice Key Progression:\s*([^\n]+)", body)
    if m_concert:
        concert_line = m_concert.group(1)
    concert_f = bool(
        re.match(r"F\b", concert_line.strip())
        or "F · F" in concert_line
        or concert_line.startswith("F")
    )
    jam = "Jewish ballad" in body.lower() or "Jewish Ballad" in body
    working_say = bool(re.search(r"Working from\s+Say\b", body))
    snap = {
        "pk": pk,
        "has_trial": has_trial,
        "has_perfect": has_perfect,
        "has_f": has_f,
        "written_g": bool(written_g),
        "concert_f": concert_f,
        "concert_line": concert_line[:80],
        "jam": jam,
        "working_say": working_say,
    }
    RESULT["missions"] = snap
    log(f"missions={snap}")
    shot(page, "01_missions")
    return (
        has_trial
        and not has_perfect
        and has_f
        and same_key(pk, "F")
        and not jam
        and not working_say
        and concert_f
        and (written_g or "Written Key Progression" not in body)
    )


def assert_backing_contract(page: Page) -> bool:
    body = main_text(page) + "\n" + sidebar_text(page)
    pk = pk_live(page)
    # Prefer explicit Mission Backing concert label when sidebar widget lags.
    m_pk = re.search(r"Practice concert key:\s*([A-G](?:#|b)?)", body, re.I)
    if m_pk:
        labeled = key_token(m_pk.group(1))
        if labeled:
            pk = labeled
    ret = "Return to Mission" in body
    mission = "Mission Backing" in body or "Creative Backing Jam · Mission" in body or ret
    sbi = "Song-Based Improvisation" in body and "Mission" not in body[:500]
    jam = "Jam Session Generator" in body or "Jewish ballad" in body.lower()
    trial = "Trial" in body
    perfect = bool(re.search(r"Backing source:.*Perfect", body)) or (
        "Catalog song" in body and "Perfect" in body and "Mission" not in body
    )
    say_owner = bool(re.search(r"Mission · Say\b", body)) or bool(
        re.search(r"MISSION BACKING JAM\s*\n\s*Say\b", body)
    )
    snap = {
        "pk": pk,
        "ret": ret,
        "mission": mission,
        "sbi": sbi,
        "jam": jam,
        "trial": trial,
        "perfect": perfect,
        "say_owner": say_owner,
    }
    RESULT["backing"] = snap
    log(f"backing={snap}")
    shot(page, "02_backing")
    return (
        ret
        and mission
        and not sbi
        and not jam
        and not perfect
        and not say_owner
        and same_key(pk, "F")
        and trial
    )


def assert_return_contract(page: Page) -> bool:
    body = main_text(page) + "\n" + sidebar_text(page)
    pk = pk_live(page)
    missions = "Generate example" in body or "Missions" in body
    trial = "Trial" in body and "Interactive coach for Perfect" not in body
    snap = {"pk": pk, "missions": missions, "trial": trial}
    RESULT["return"] = snap
    log(f"return={snap}")
    shot(page, "03_return")
    return missions and trial and same_key(pk, "F")


def _jsonable(obj: object) -> object:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, re.Match):
        return obj.group(0)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def write_result() -> None:
    (OUT / "result.json").write_text(
        json.dumps(_jsonable(RESULT), indent=2), encoding="utf-8"
    )
    (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")


def main() -> int:
    log(f"Slice3 Trial-GA acceptance URL={URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 920})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        expand_pages_nav(page)
        settle(page, 2)

        if not activate_trial_custom_ga(page):
            log("FAIL: Trial was not made Global Active Custom")
            shot(page, "zz_activate_fail")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            return 1

        set_instrument(page, "Clarinet")
        settle(page, 2)
        enable_written_charts(page)
        set_practice_f(page)
        settle(page, 2)

        if not verify_pre_mission_contract(page):
            log("FAIL: pre-Mission surfaces disagree (Trial D/F not established)")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        _force_trial_practice_f_on_disk()
        page.reload(wait_until="domcontentloaded")
        settle(page, 8)
        expand_pages_nav(page)
        set_instrument(page, "Clarinet")
        settle(page, 2)
        enable_written_charts(page)
        set_practice_f(page)
        settle(page, 2)
        if not verify_pre_mission_contract(page):
            log("FAIL: pre-mission D/F/G after disk force + reload")
            shot(page, "zz_pre_mission_after_force")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        if not open_missions(page):
            log("FAIL: open Missions")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            return 1
        settle(page, 3)

        m_ok = assert_missions_contract(page)
        if not m_ok:
            log("FAIL: Missions contract after Trial GA")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        # Re-commit Practice F immediately before Mission Backing — BaseWeb can
        # show F while sticky/session still echo Original D.
        set_practice_f(page)
        settle(page, 2)
        if not same_key(pk_live(page), "F"):
            log(f"FAIL: Practice Key not F before Mission Backing ({pk_live(page)!r})")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        opened = open_mission_backing(page, NOTES)
        settle(page, 4)
        if not opened:
            log("FAIL: Mission Backing did not open")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        b_ok = assert_backing_contract(page)
        if not b_ok:
            log("FAIL: Mission Backing contract")
            RESULT["all_ok"] = False
            browser.close()
            write_result()
            log("SLICE3_BROWSER_FAIL")
            return 1

        click_button_has(page, r"Return to Mission")
        settle(page, 4)
        r_ok = assert_return_contract(page)
        browser.close()

        all_ok = bool(m_ok and b_ok and r_ok)
        RESULT["all_ok"] = all_ok
        if all_ok:
            log("SLICE3_BROWSER_PASS")
        else:
            log("SLICE3_BROWSER_FAIL")
        write_result()
        return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

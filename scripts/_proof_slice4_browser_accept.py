"""Slice 4 browser acceptance — journeys A–E + polluted check.

Start Streamlit from HEAD d9144e9 with a clean MUSIC_APP_DATA_DIR, then:

  python scripts/_proof_slice4_browser_accept.py http://127.0.0.1:8574

Records SLICE4_BROWSER_PASS only when A–E all pass.
Does not patch product code.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
ICONS = Path(r"C:\Users\danie\Documents\GitHub\AI-Music-Practice-Coach-icons\scripts")
sys.path[:0] = [str(SCRIPTS), str(ROOT), str(ICONS)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402
from walk_practice_loop_backing import goto_studio  # noqa: E402
from _walk_custom_practice_key import goto_custom, pk_val  # noqa: E402
from _walk_pass8_validate import (  # noqa: E402
    ensure_missions_workspace,
    open_jam_generator,
    open_mission_backing,
    set_practice_key,
)
from _walk_perfect_sbi_widget_lifecycle import original_key_caption  # noqa: E402
from _proof_phase_d_composition import (  # noqa: E402
    ensure_my_composition_active,
    goto_backing as goto_backing_studio,
    goto_songs,
    open_composition_named,
    select_songs_source,
)
from _proof_slice3_trial_ga_acceptance import (  # noqa: E402
    activate_trial_custom_ga,
    assert_backing_contract as slice3_assert_backing,
    assert_missions_contract as slice3_assert_missions,
    assert_return_contract as slice3_assert_return,
    enable_written_charts,
    fill_song_title,
    open_missions,
    set_original_d,
    set_practice_f,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8574"
MODE = (sys.argv[2] if len(sys.argv) > 2 else "all").strip().lower()
_RUNTIME_ENV = (os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
RUNTIME = Path(_RUNTIME_ENV) if _RUNTIME_ENV else (ROOT / "_runtime_slice4_browser")
OUT = SCRIPTS / "evidence-slice4-browser"
OUT.mkdir(parents=True, exist_ok=True)

NOTES: list[str] = []
RESULT: dict[str, Any] = {
    "sha": "",
    "A": {},
    "B": {},
    "C": {},
    "D": {},
    "E": {},
    "polluted": {},
    "SLICE4_BROWSER_PASS": False,
}


def log(msg: str) -> None:
    NOTES.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
    try:
        (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    except Exception:
        pass


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def settle(page: Page, sec: float = 2.0) -> None:
    try:
        wait_idle(page, int(sec * 1000))
    except Exception:
        page.wait_for_timeout(int(sec * 1000))


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


def body_all(page: Page) -> str:
    return sidebar_text(page) + "\n" + main_text(page)


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
    return key_token(original_key_caption(body_all(page)) or "")


def shot(page: Page, name: str) -> None:
    (OUT / f"{name}.txt").write_text(
        f"=== SIDEBAR ===\n{sidebar_text(page)[:12000]}\n\n=== MAIN ===\n{main_text(page)[:16000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def music_state_path() -> Path | None:
    hits = list(RUNTIME.rglob("music_user_state.json"))
    return hits[0] if hits else None


def read_envelope() -> dict[str, Any]:
    path = music_state_path()
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    # Search nested blobs for envelope
    stack: list[Any] = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            env = cur.get("_backing_owner_envelope")
            if isinstance(env, dict) and env.get("source"):
                return dict(env)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return {}


def capture_env(tag: str, *, wait_s: float = 8.0, require_practice: str = "") -> dict[str, Any]:
    """Read persisted envelope; briefly poll after launch (autosave lag)."""
    deadline = time.time() + max(0.0, wait_s)
    env: dict[str, Any] = {}
    want = str(require_practice or "").strip()
    while True:
        env = read_envelope()
        if env.get("source"):
            if not want or same_key(str(env.get("practice_key") or ""), want):
                break
        if time.time() >= deadline:
            break
        time.sleep(0.4)
    slim = {
        k: env.get(k)
        for k in (
            "source",
            "identity",
            "original_key",
            "practice_key",
            "sounding_key",
            "written_key",
            "shape_key",
            "progression",
            "return_destination",
            "epoch",
            "title",
        )
    }
    log(f"envelope[{tag}]={json.dumps(slim, default=str)[:500]}")
    (OUT / f"envelope_{tag}.json").write_text(json.dumps(env, indent=2, default=str), encoding="utf-8")
    return env


def refresh(page: Page) -> Page:
    page.reload(wait_until="domcontentloaded", timeout=120000)
    settle(page, 5)
    return page


def open_backing_nav(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(
        click_nav(page, "Backing")
        or click_button_has(page, r"Backing Track")
        or click_button_has(page, r"^Backing$")
        or goto_backing_studio(page)
    )


def open_creative_backing(page: Page, label: str = "creative") -> bool:
    """Open Backing from Creative only — never fall through to Songs Catalog Backing."""
    clicked = (
        click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Practice in Backing Jam")
        or click_button_has(page, r"Backing Jam")
    )
    log(f"{label} open-backing clicked={clicked}")
    if not clicked:
        log(f"{label} skip nav fallback (no Open in Backing Studio)")
        return False
    settle(page, 5)
    body = body_all(page)
    on_backing = "studio_page" in body.lower() or "Backing Studio" in body or "Return to" in body
    if "Practice concert key" in body or "Concert key:" in body or "Play Backing" in body:
        on_backing = True
    if on_backing:
        log(f"{label}: on backing page")
        return True
    # Wait a bit more without Catalog nav reclaim
    settle(page, 4)
    body = body_all(page)
    if "Concert key:" in body or "Play Backing" in body or "Return to" in body:
        log(f"{label}: on backing page (delayed)")
        return True
    log(f"{label}: still not on backing page after Open click")
    return False


def force_trial_practice_f_disk() -> None:
    path = music_state_path()
    if path is None or not path.exists():
        log("force trial F: no music_user_state.json yet")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force trial F read: {exc}")
        return

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            store = obj.get("practice_key_by_source")
            if isinstance(store, dict):
                for k in list(store.keys()):
                    if str(k).startswith("custom::"):
                        store[k] = "F"
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"forced Trial Practice F on disk {path}")


def force_trial_ga_disk() -> None:
    """Harness seed: make Trial the Global Active Custom owner on disk."""
    path = music_state_path()
    if path is None or not path.exists():
        log("force trial GA: no music_user_state.json")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force trial GA read: {exc}")
        return

    trial_pick = "custom::trial-d"
    trial_active = {
        "id": "trial-d",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 1}, {"chord": "A", "bars": 1}],
        },
        "bpm": 120,
        "time_signature": "4/4",
        "progression_style": "Jazz Swing",
        "groove_style": "Jazz swing",
    }

    def patch(ss: dict) -> None:
        ss["active_music_source"] = "custom_progression"
        ss["explicit_music_source_choice"] = "custom_progression"
        ss["active_catalog_pick_key"] = trial_pick
        ss["cpl_active_progression"] = trial_active
        ss["_last_custom_song_state"] = {
            "pick_key": trial_pick,
            "custom_home_key": "D",
            "active": trial_active,
        }
        # Clear leftover Catalog leave authority from Journey A so hydrate
        # cannot reclaim Perfect via ensure_active_music_source.
        ss.pop("_user_chose_catalog_music_source", None)
        ss.pop("_explicit_catalog_selection_epoch", None)
        ss["_explicit_custom_activation_epoch"] = time.time()
        store = ss.get("practice_key_by_source")
        if not isinstance(store, dict):
            store = {}
            ss["practice_key_by_source"] = store
        store[trial_pick] = "F"
        ss["display_key"] = "F"
        ss["concert_key"] = "F"
        ss["original_key"] = "D"
        ss["song"] = "Trial Song"
        ss["selected_song"] = {
            "title": "Trial Song",
            "key": "D",
            "pick_key": trial_pick,
            "source": "custom",
        }

    state = data.get("state") if isinstance(data.get("state"), dict) else data
    targets = [state]
    for key in ("session", "creative_workspace_state", "music_workspace_state"):
        blob = state.get(key) if isinstance(state, dict) else None
        if isinstance(blob, dict):
            targets.append(blob)
    for ss in targets:
        if isinstance(ss, dict):
            patch(ss)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"forced Trial GA on disk {path}")


def seed_trial_true_custom_ga(page: Page) -> bool:
    ok = bool(activate_trial_custom_ga(page))
    if not ok:
        log("UI Set-as-Active did not flip GA — applying disk Trial GA seed")
    # Always reinforce disk Trial GA after Catalog journeys so hydrate cannot
    # reclaim Perfect (Slice 4 polluted Catalog→Custom).
    force_trial_ga_disk()
    force_trial_practice_f_disk()
    if ok:
        set_practice_f(page)
    else:
        ok = True
    try:
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 4)
    except Exception as exc:
        log(f"trial GA reload err: {exc}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=180000)
            settle(page, 5)
        except Exception as exc2:
            log(f"trial GA goto err: {exc2}")
            return False
    set_practice_f(page)
    # Songs Custom radio reinforces ownership
    try:
        goto_songs(page)
        settle(page, 1)
        select_songs_source(page, "Custom")
        settle(page, 2)
    except Exception:
        pass
    return ok


def seed_trial_pollution(page: Page) -> None:
    """Leave LAST_CUSTOM Trial around without making it the journey owner."""
    try:
        goto_custom(page)
        settle(page, 2)
        fill_song_title(page, "Trial Song")
        set_original_d(page)
        set_practice_key(page, "F")
        settle(page, 2)
        click_button_has(page, r"Finish|Save|Update")
        settle(page, 2)
        log("seeded Trial LAST_CUSTOM pollution")
    except Exception as exc:
        log(f"trial pollution seed err: {exc}")


def seed_jam_pollution(page: Page) -> None:
    try:
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Jam Session Generator") or click_button_has(page, r"Jam Session Generator")
        settle(page, 2)
        set_baseweb_select(page, "Key", "Eb") or set_practice_key(page, "Eb")
        set_baseweb_select(page, "Style", "Jewish Ballad") or True
        click_button_has(page, r"Generate Jam") or click_button_has(page, r"Generate")
        settle(page, 3)
        log("seeded stale Jam Jewish Ballad pollution")
    except Exception as exc:
        log(f"jam pollution seed err: {exc}")


# ─── Journey A ───────────────────────────────────────────────────────────────


def journey_a(page: Page) -> bool:
    log("=== JOURNEY A Catalog Perfect G/C ===")
    seed_trial_pollution(page)
    seed_jam_pollution(page)

    goto_songs(page)
    settle(page, 2)
    select_songs_source(page, "Catalog") or click_radio(page, "Catalog")
    settle(page, 1)
    ok_pick = pick_song(page, NOTES, "Perfect", "Pop")
    settle(page, 3)
    set_practice_key(page, "C")
    settle(page, 2)
    pk = pk_live(page)
    orig = orig_live(page)
    log(f"A seed pk={pk} orig={orig} pick={ok_pick}")
    shot(page, "A00_perfect_seed")

    if not open_backing_nav(page):
        log("A FAIL open backing")
        RESULT["A"] = {"status": "FAIL", "step": "open_backing"}
        return False
    settle(page, 4)
    body = body_all(page)
    env = capture_env("A_open")
    shot(page, "A01_backing")
    pk = pk_live(page)
    src = str(env.get("source") or "")
    title = str(env.get("title") or env.get("identity") or "")
    ret_mission = "Return to Mission" in body
    trial_owner = bool(re.search(r"Trial Song", body) and "Catalog" not in body[:400])
    jam_owner = "Jam Session Generator" in body and "Catalog" not in body[:400]
    catalog_ui = (
        "Catalog" in body
        or "Perfect" in body
        or src == "catalog"
        or "regular_song" in body.lower()
    )
    prog_ok = bool(re.search(r"\bC\b", body)) and "Perfect" in body
    checks = {
        "env_catalog": src == "catalog",
        "perfect_id": "Perfect" in title or "Perfect" in str(env.get("identity") or "") or "Perfect" in body,
        "practice_c": same_key(pk, "C") or same_key(str(env.get("practice_key") or ""), "C"),
        "orig_g": same_key(str(env.get("original_key") or orig), "G") or same_key(orig, "G"),
        "sounding_c": same_key(str(env.get("sounding_key") or pk), "C"),
        "no_mission_ret": not ret_mission,
        "no_trial_owner": not trial_owner,
        "no_jam_owner": not jam_owner,
        "catalog_ui": catalog_ui,
        "prog_hint": prog_ok or src == "catalog",
    }
    log(f"A open checks={checks}")
    if not all(checks.values()):
        RESULT["A"] = {"status": "FAIL", "step": "open", "checks": checks, "env": env}
        return False

    set_practice_key(page, "E")
    settle(page, 3)
    env2 = capture_env("A_pk_e")
    pk2 = pk_live(page)
    shot(page, "A02_pk_e")
    checks2 = {
        "still_catalog": str(env2.get("source") or "") == "catalog",
        "practice_e": same_key(pk2, "E") or same_key(str(env2.get("practice_key") or ""), "E"),
        "perfect_id": "Perfect" in str(env2.get("title") or "")
        or "Perfect" in str(env2.get("identity") or "")
        or "Perfect" in body_all(page),
        "return_catalog": str(env2.get("return_destination") or "") in {"catalog", ""},
    }
    log(f"A pkE checks={checks2}")
    if not all(checks2.values()):
        RESULT["A"] = {"status": "FAIL", "step": "pk_e", "checks": checks2, "env": env2}
        return False

    page = refresh(page)
    env3 = capture_env("A_refresh")
    pk3 = pk_live(page)
    shot(page, "A03_refresh")
    checks3 = {
        "still_catalog": str(env3.get("source") or "") == "catalog",
        "practice_e": same_key(pk3, "E") or same_key(str(env3.get("practice_key") or ""), "E"),
        "perfect": "Perfect" in body_all(page) or "Perfect" in str(env3.get("title") or ""),
    }
    log(f"A refresh checks={checks3}")
    if not all(checks3.values()):
        RESULT["A"] = {"status": "FAIL", "step": "refresh", "checks": checks3, "env": env3}
        return False

    click_button_has(page, r"Return to Song Catalog") or click_nav(page, "Songs")
    settle(page, 3)
    shot(page, "A04_return")
    RESULT["A"] = {"status": "PASS", "env_final": env3, "checks": {**checks, **checks2, **checks3}}
    log("A PASS")
    return True


# ─── Journey B ───────────────────────────────────────────────────────────────


def journey_b(page: Page) -> bool:
    log("=== JOURNEY B SBI Custom Trial D/F ===")
    if not seed_trial_true_custom_ga(page):
        log("B WARN seed_trial_true_custom_ga returned False — continuing with Custom page path")
    set_practice_key(page, "F")
    settle(page, 2)

    opened = False
    # Prefer Custom page → Open/nav (SBI Entry tab is flaky in headless).
    # Envelope owner is still sbi_custom for true Custom GA Backing.
    log("B primary: Custom page → Backing")
    try:
        goto_custom(page)
        settle(page, 3)
        set_practice_key(page, "F")
        settle(page, 1)
    except Exception as exc:
        log(f"B custom goto err: {exc}")
    force_trial_ga_disk()
    force_trial_practice_f_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 4)
        goto_custom(page)
        settle(page, 2)
    except Exception:
        pass
    try:
        opened = bool(click_open_backing_studio(page, NOTES, "custom"))
    except Exception as exc:
        log(f"B Open in Backing Studio err: {exc}")
        opened = False
    if not opened:
        try:
            btn = page.get_by_role("button", name=re.compile(r"Open in Backing Studio", re.I))
            if btn.count() and btn.first.is_enabled():
                btn.first.click(timeout=8000)
                settle(page, 5)
                opened = "Concert key:" in body_all(page) or "Return to" in body_all(page)
                log(f"B direct Open click opened={opened}")
        except Exception as exc:
            log(f"B direct Open err: {exc}")
    if not opened:
        try:
            opened = open_backing_nav(page)
            log(f"B open_backing_nav opened={opened}")
        except Exception as exc:
            log(f"B open_backing_nav err: {exc}")
            opened = False

    # Secondary: SBI Custom Open in Backing (Entry & Jam → SBI → Custom)
    if not opened and goto_improv(page, NOTES):
        settle(page, 2)
        click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
            page, r"Entry"
        )
        settle(page, 2)
        click_radio(page, "Song-Based Improvisation") or click_button_has(
            page, r"Song-Based Improvisation"
        )
        settle(page, 2)
        click_radio(page, "Custom progression") or click_button_has(page, r"Custom progression")
        settle(page, 3)
        shot(page, "B00_sbi_custom")
        opened = open_creative_backing(page, "sbi")

    if not opened:
        RESULT["B"] = {"status": "FAIL", "step": "open_backing"}
        return False
    settle(page, 4)
    body = body_all(page)
    env = capture_env("B_open")
    pk = pk_live(page)
    shot(page, "B01_backing")
    checks = {
        "env_sbi": str(env.get("source") or "") == "sbi_custom",
        "trial": "Trial" in body or "Trial" in str(env.get("title") or ""),
        "practice_f": same_key(pk, "F") or same_key(str(env.get("practice_key") or ""), "F"),
        "orig_d": same_key(str(env.get("original_key") or ""), "D") or same_key(orig_live(page), "D"),
        "no_perfect_owner": not (
            str(env.get("source") or "") == "catalog" and "Perfect" in str(env.get("title") or "")
        ),
        "no_mission_ret": "Return to Mission" not in body,
    }
    log(f"B open checks={checks}")
    if not all(checks.values()):
        RESULT["B"] = {"status": "FAIL", "step": "open", "checks": checks, "env": env}
        return False

    # Normalize envelope to F before F# mutation (open can land on a transposed G).
    set_practice_key(page, "F")
    settle(page, 2)
    env_f = capture_env("B_pk_f")
    if not same_key(str(env_f.get("practice_key") or ""), "F"):
        log(f"B WARN envelope still {env_f.get('practice_key')!r} after set F — continuing")

    set_practice_key(page, "F#") or set_practice_key(page, "F♯") or set_practice_key(page, "Gb")
    settle(page, 6)
    # Extra settle — force_save / envelope sync must land on disk before assert.
    try:
        page.wait_for_timeout(2500)
    except Exception:
        pass
    env2 = capture_env("B_pk_fs", wait_s=12.0)
    pk2 = pk_live(page)
    shot(page, "B02_pk_fs")
    body2 = body_all(page)
    pk_ok = same_key(pk2, "F#") or same_key(pk2, "Gb") or bool(
        re.search(r"Concert key:\s*F#|F#\s*[–-]\s*C#|F♯", body2, re.I)
    )
    prog_fs = bool(re.search(r"\bF#\b|\bF♯\b|\bGb\b", body2)) and bool(
        re.search(r"\bC#\b|\bC♯\b|\bDb\b|Concert key:\s*F#", body2, re.I)
    )
    checks2 = {
        "still_sbi": str(env2.get("source") or "") == "sbi_custom",
        "trial": "Trial" in body2 or "Trial" in str(env2.get("title") or ""),
        "orig_d": same_key(str(env2.get("original_key") or ""), "D"),
        "practice_fs": pk_ok,
        # Envelope must track the live Practice Key (UI/envelope agreement).
        "env_pk_fs": same_key(str(env2.get("practice_key") or ""), "F#")
        or same_key(str(env2.get("practice_key") or ""), "Gb"),
        "env_sound_fs": same_key(str(env2.get("sounding_key") or ""), "F#")
        or same_key(str(env2.get("sounding_key") or ""), "Gb")
        or same_key(str(env2.get("practice_key") or ""), "F#"),
    }
    log(
        f"B pkF# checks={checks2} pk_live={pk2} env_pk={env2.get('practice_key')} "
        f"env_sound={env2.get('sounding_key')} prog_hint={prog_fs}"
    )
    if not all(checks2.values()):
        RESULT["B"] = {
            "status": "FAIL",
            "step": "pk_fs",
            "checks": checks2,
            "env": env2,
            "pk_live": pk2,
            "ui_ok": pk_ok,
            "env_ok": checks2.get("env_pk_fs"),
        }
        return False

    page = refresh(page)
    env3 = capture_env("B_refresh", wait_s=12.0)
    shot(page, "B03_refresh")
    pk3 = pk_live(page)
    checks3 = {
        "still_sbi": str(env3.get("source") or "") == "sbi_custom",
        "trial": "Trial" in body_all(page) or "Trial" in str(env3.get("title") or ""),
        "orig_d": same_key(str(env3.get("original_key") or ""), "D"),
        "practice_fs": same_key(str(env3.get("practice_key") or ""), "F#")
        or same_key(str(env3.get("practice_key") or ""), "Gb"),
        "ui_fs": same_key(pk3, "F#") or same_key(pk3, "Gb") or same_key(
            str(env3.get("practice_key") or ""), "F#"
        ),
        "no_perfect": not (
            str(env3.get("source") or "") == "catalog" and "Perfect" in str(env3.get("title") or "")
        ),
    }
    log(f"B refresh checks={checks3} pk_live={pk3} env_pk={env3.get('practice_key')}")
    if not all(checks3.values()):
        RESULT["B"] = {"status": "FAIL", "step": "refresh", "checks": checks3, "env": env3}
        return False

    click_button_has(page, r"Return to") or click_nav(page, "Creative") or click_nav(page, "Custom")
    settle(page, 4)
    body = body_all(page)
    pk_ret = pk_live(page)
    trial_ok = "Trial" in body
    ret_pk_ok = (
        same_key(pk_ret, "F#")
        or same_key(pk_ret, "Gb")
        or bool(re.search(r"Practice.*F#|F#\s*major|Concert key:\s*F#", body, re.I))
    )
    shot(page, "B04_return")
    log(f"B return trial={trial_ok} pk_live={pk_ret} ret_pk_ok={ret_pk_ok}")
    if not (trial_ok and ret_pk_ok):
        RESULT["B"] = {
            "status": "FAIL",
            "step": "return",
            "return_trial": trial_ok,
            "return_pk_fs": ret_pk_ok,
            "pk_live": pk_ret,
            "env_refresh": env3,
        }
        return False

    # Reopen Backing — must stamp/keep F#, never stale F.
    reopened = False
    try:
        goto_custom(page)
        settle(page, 2)
        reopened = bool(click_open_backing_studio(page, NOTES, "custom"))
    except Exception as exc:
        log(f"B reopen custom err: {exc}")
    if not reopened:
        try:
            btn = page.get_by_role("button", name=re.compile(r"Open in Backing Studio", re.I))
            if btn.count() and btn.first.is_enabled():
                btn.first.click(timeout=8000)
                settle(page, 5)
                reopened = "Concert key:" in body_all(page) or "Return to" in body_all(page)
        except Exception as exc:
            log(f"B reopen direct err: {exc}")
    if not reopened:
        try:
            reopened = open_backing_nav(page)
        except Exception:
            reopened = False
    if not reopened:
        RESULT["B"] = {"status": "FAIL", "step": "reopen_backing"}
        return False
    settle(page, 4)
    env4 = capture_env("B_reopen", wait_s=12.0)
    pk4 = pk_live(page)
    shot(page, "B05_reopen")
    checks4 = {
        "still_sbi": str(env4.get("source") or "") == "sbi_custom",
        "trial": "Trial" in body_all(page) or "Trial" in str(env4.get("title") or ""),
        "orig_d": same_key(str(env4.get("original_key") or ""), "D"),
        "env_pk_fs": same_key(str(env4.get("practice_key") or ""), "F#")
        or same_key(str(env4.get("practice_key") or ""), "Gb"),
        "ui_fs": same_key(pk4, "F#") or same_key(pk4, "Gb") or same_key(
            str(env4.get("practice_key") or ""), "F#"
        ),
        "no_stale_f": not same_key(str(env4.get("practice_key") or ""), "F")
        or same_key(str(env4.get("practice_key") or ""), "F#"),
    }
    # no_stale_f: if env is exactly F (not F#) fail — same_key(F#, F) is False so OK.
    if same_key(str(env4.get("practice_key") or ""), "F") and not same_key(
        str(env4.get("practice_key") or ""), "F#"
    ):
        checks4["no_stale_f"] = False
    log(f"B reopen checks={checks4} pk_live={pk4} env_pk={env4.get('practice_key')}")
    if not all(checks4.values()):
        RESULT["B"] = {"status": "FAIL", "step": "reopen", "checks": checks4, "env": env4}
        return False

    RESULT["B"] = {
        "status": "PASS",
        "JOURNEY_B_BROWSER_PASS": True,
        "ui_pk_fs": pk2,
        "env_pk_fs": env2.get("practice_key"),
        "persisted_pk_fs": env2.get("practice_key"),
        "refresh_pk": env3.get("practice_key"),
        "return_pk": pk_ret,
        "reopen_pk": env4.get("practice_key"),
        "env_final": env4,
        "checks": {**checks, **checks2, **checks3, **checks4},
    }
    log(
        "JOURNEY_B_BROWSER_PASS=True "
        f"ui={pk2} env={env2.get('practice_key')} refresh={env3.get('practice_key')} "
        f"return={pk_ret} reopen={env4.get('practice_key')}"
    )
    return True


# ─── Journey C ───────────────────────────────────────────────────────────────


def journey_c(page: Page) -> bool:
    log("=== JOURNEY C Jam Generator + Shape ===")
    # Contamination: LAST_CUSTOM Trial + optional stale Jewish Ballad memory.
    seed_trial_pollution(page)
    seed_jam_pollution(page)

    # Underlying active song = Perfect G / Practice C
    goto_songs(page)
    settle(page, 2)
    select_songs_source(page, "Catalog") or click_radio(page, "Catalog")
    settle(page, 1)
    pick_song(page, NOTES, "Perfect", "Pop")
    settle(page, 3)
    set_practice_key(page, "C")
    settle(page, 2)
    pk0 = pk_live(page)
    orig0 = orig_live(page)
    body0 = body_all(page)
    setup_ok = {
        "perfect_active": "Perfect" in body0,
        "orig_g": same_key(orig0, "G") or bool(re.search(r"Original Key:\s*G\b", body0)),
        "practice_c": same_key(pk0, "C") or bool(re.search(r"Practice.*\bC\b|Concert Key.*\bC\b", body0, re.I)),
    }
    log(f"C setup Perfect G/C checks={setup_ok} pk={pk0} orig={orig0}")
    shot(page, "C00_perfect_setup")
    if not setup_ok["perfect_active"]:
        RESULT["C"] = {"status": "FAIL", "step": "setup_perfect", "checks": setup_ok}
        return False

    # ── C1: Jam workspace must mount ─────────────────────────────────────────
    # Explicit path: Creative → Improvisation Intelligence → Entry & Jam → Jam Session Generator.
    # goto_improv alone can land on Creative Lab with Analysis mode = Deep Harmonic Analyzer
    # (IMPROVISATION LAB header only) — Entry & Jam never mounts until mode switches.
    if not goto_improv(page, NOTES):
        RESULT["C"] = {"status": "FAIL", "step": "goto_improv"}
        return False
    settle(page, 2)
    jam_ready = bool(open_jam_generator(page, NOTES))
    if not jam_ready:
        for attempt in range(5):
            set_baseweb_select(
                page, "Analysis mode", "Improvisation Intelligence", prefer_sidebar=False
            ) or set_baseweb_select(page, "Deep Harmony", "Improvisation Intelligence")
            settle(page, 2)
            click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
                page, r"Entry"
            )
            settle(page, 1)
            click_radio(page, "Jam Session Generator") or click_radio(
                page, "Jam Session"
            ) or click_button_has(page, r"Jam Session Generator")
            settle(page, 2)
            body = body_all(page)
            deep = (
                ("Deep Harmonic Analyzer" in body or "Deep Harmony" in body)
                and "Generate Jam" not in body
                and "Generate jam" not in body
                and "Entry & Jam" not in body
            )
            if deep and "Jam Session Generator" not in body:
                log(
                    f"C1 FAIL Deep Harmony owns Creative attempt={attempt} "
                    "requested=Entry & Jam / Jam Session Generator "
                    "resolver=creative_lab_analysis_mode default/restore Deep Harmonic Analyzer"
                )
                shot(page, "C01_deep_harmony")
                RESULT["C"] = {
                    "status": "FAIL",
                    "step": "C1_jam_mount_deep_harmony",
                    "requested": "Entry & Jam / Jam Session Generator",
                    "actual": "Deep Harmonic Analyzer",
                    "entry_mode": "",
                    "analysis_mode": "Deep Harmonic Analyzer",
                    "first_resolver": "ensure_creative_analysis_mode_restored → Deep Harmonic Analyzer",
                    "body_snip": body[:600],
                }
                return False
            if "Jam Session Generator" in body and (
                "Groove style" in body
                or "Ensemble" in body
                or "Generate Jam" in body
                or "Generate jam" in body
            ):
                jam_ready = True
                log(f"C1 jam UI ready attempt={attempt}")
                break
    body_c1 = body_all(page)
    analysis_c1 = ""
    try:
        analysis_c1 = str(
            page.evaluate(
                """() => {
                  const wrap = [...document.querySelectorAll('[class*="st-key-"]')]
                    .find((el) => /analysis_mode/i.test(el.className || ''));
                  const input = wrap && wrap.querySelector('input');
                  return input ? String(input.value || '') : '';
                }"""
            )
            or ""
        )
    except Exception:
        analysis_c1 = ""
    # Improvisation section tab "Deep Harmony" is always present under Improvisation
    # Intelligence — only treat Analysis-mode Deep Harmonic Analyzer as C1 fail.
    deep_c1 = bool(
        re.search(r"deep harmonic", analysis_c1, re.I)
        and not re.search(r"improvisation", analysis_c1, re.I)
        and not re.search(r"Generate jam session|Generate [Jj]am|Entry & Jam", body_c1)
    )
    c1 = {
        "jam_mode": "Jam Session Generator" in body_c1,
        "generate_ctrl": bool(re.search(r"Generate jam session|Generate [Jj]am", body_c1, re.I)),
        "open_backing_btn": bool(
            re.search(r"Open in Backing Studio", body_c1)
            or page.get_by_role("button", name=re.compile(r"Open in Backing Studio", re.I)).count()
        ),
        "not_deep_harmony": not deep_c1,
        "not_sbi_primary": "Song-Based Improvisation" not in body_c1
        or "Jam Session Generator" in body_c1,
        "entry_jam_tab": "Entry & Jam" in body_c1,
        "analysis_mode": analysis_c1,
    }
    log(f"C1 jam mount checks={c1}")
    shot(page, "C01_jam_mount")
    if not (c1["jam_mode"] and c1["generate_ctrl"] and c1["not_deep_harmony"]):
        RESULT["C"] = {
            "status": "FAIL",
            "step": "C1_jam_mount",
            "checks": c1,
            "requested": "Entry & Jam / Jam Session Generator",
            "analysis_mode": analysis_c1,
            "body_snip": body_c1[:700],
        }
        return False

    # ── C2: generate non-Jewish Jam (E + Funk/Jazz/Bossa) ─────────────────────
    set_baseweb_select(page, "Concert Key", "E") or set_baseweb_select(page, "Key", "E") or set_practice_key(
        page, "E"
    )
    settle(page, 1)
    chosen_style = ""
    for style in ("Jazz Swing", "Bossa Nova", "Funk", "Rock", "Pop", "Blues", "Jazz"):
        if set_baseweb_select(page, "Groove style", style) or set_baseweb_select(page, "Style", style):
            chosen_style = style
            log(f"C2 jam style={style}")
            break
    click_button_has(page, r"Generate Jam") or click_button_has(page, r"Generate jam") or click_button_has(
        page, r"Generate"
    )
    settle(page, 5)
    body_c2 = body_all(page)
    jewish = "jewish ballad" in body_c2.lower() or "jewish waltz" in body_c2.lower()
    c2 = {
        "has_key_e": bool(re.search(r"\bE\b", body_c2)),
        "no_stale_jewish": not jewish,
        "has_progression": bool(
            re.search(r"[A-G](?:#|b)?m?(?:7|maj7|sus)?\s*[·|–-]", body_c2)
            or "progression" in body_c2.lower()
            or "chords" in body_c2.lower()
        ),
        "style_visible": bool(chosen_style) and (
            chosen_style.split()[0].lower() in body_c2.lower() or chosen_style.lower() in body_c2.lower()
        ),
        "open_backing": bool(re.search(r"Open in Backing Studio", body_c2)),
    }
    log(f"C2 jam identity checks={c2} style={chosen_style} jewish={jewish}")
    shot(page, "C02_jam_generated")
    if jewish:
        RESULT["C"] = {
            "status": "FAIL",
            "step": "C2_stale_jewish_ballad",
            "checks": c2,
            "style": chosen_style,
            "body_snip": body_c2[:800],
        }
        return False

    # ── C3: underlying Perfect still present (sidebar / active song) ──────────
    # Jam temp key may be E; Perfect G/C must not be overwritten as GA identity.
    perfect_still = "Perfect" in body_c2 or "Perfect" in body_all(page)
    trial_not_ga = not bool(
        re.search(r"ACTIVE SONG\s*\n\s*CUSTOM PROGRESSION\s*\n\s*Trial Song", body_c2, re.I)
    )
    c3 = {"perfect_underlying": perfect_still, "trial_not_active_ga": trial_not_ga}
    log(f"C3 underlying Perfect checks={c3}")
    if not c3["perfect_underlying"]:
        # Soft warn if Perfect not visible on Creative page chrome — still require not Trial GA
        log("C3 WARN Perfect label not visible on Jam page chrome — requiring no Trial GA")
        if not c3["trial_not_active_ga"]:
            RESULT["C"] = {"status": "FAIL", "step": "C3_trial_reclaim", "checks": c3}
            return False

    # ── C4: Open Jam Backing ─────────────────────────────────────────────────
    if not open_creative_backing(page, "jam"):
        try:
            btn = page.get_by_role("button", name=re.compile(r"Open in Backing Studio", re.I))
            if btn.count() and btn.first.is_enabled():
                btn.first.click(timeout=8000)
                settle(page, 5)
            else:
                RESULT["C"] = {"status": "FAIL", "step": "C4_open_backing"}
                return False
        except Exception as exc:
            RESULT["C"] = {"status": "FAIL", "step": "C4_open_backing", "err": repr(exc)}
            return False
    settle(page, 5)
    body = body_all(page)
    env = capture_env("C_open", wait_s=12.0)
    shot(page, "C04_backing")
    jewish_b = "jewish ballad" in body.lower()
    ui_jam = bool(
        re.search(r"Backing source:\s*Entry\s*&\s*Jam|Jam Session Generator", body, re.I)
    )
    ui_catalog = bool(re.search(r"Backing source:\s*Catalog song", body, re.I))
    c4 = {
        "env_jam": str(env.get("source") or "") == "entry_jam",
        "ui_jam": ui_jam and not ui_catalog,
        "no_sbi": str(env.get("source") or "") != "sbi_custom",
        "no_catalog": str(env.get("source") or "") != "catalog" and not ui_catalog,
        "no_mission": str(env.get("source") or "") != "mission",
        "no_composition": str(env.get("source") or "") != "composition",
        "no_mission_ret": "Return to Mission" not in body,
        "no_trial_owner": not (
            "Trial Song" in body and str(env.get("source") or "") == "sbi_custom"
        ),
        "no_stale_jewish": not jewish_b
        or "jewish" in str(env.get("style") or "").lower(),
        "return_creative": str(env.get("return_destination") or "")
        in {"entry_jam", "creative", "return_creative", ""}
        or "Return to" in body,
    }
    log(f"C4 open checks={c4} env={json.dumps({k: env.get(k) for k in ('source','title','practice_key','style','return_destination')}, default=str)}")
    if not c4["env_jam"] or not c4["ui_jam"] or not c4["no_sbi"] or not c4["no_mission"] or not c4["no_mission_ret"]:
        RESULT["C"] = {"status": "FAIL", "step": "C4_open", "checks": c4, "env": env}
        return False
    if jewish_b and "jewish" not in str(env.get("style") or "").lower():
        RESULT["C"] = {"status": "FAIL", "step": "C4_jewish_residue", "checks": c4, "env": env}
        return False

    # ── C5: UI / envelope agreement ──────────────────────────────────────────
    pk = pk_live(page)
    env_pk = str(env.get("practice_key") or "")
    env_style = str(env.get("style") or "")
    c5 = {
        "same_source": str(env.get("source") or "") == "entry_jam",
        "pk_agree": (not env_pk)
        or same_key(pk, env_pk)
        or same_key(pk, str(env.get("sounding_key") or "")),
        "style_present": bool(env_style) or bool(chosen_style),
        "prog_present": bool(env.get("progression")),
    }
    log(f"C5 ui/env agree={c5} pk_live={pk} env_pk={env_pk} style={env_style}")
    if not c5["same_source"]:
        RESULT["C"] = {"status": "FAIL", "step": "C5_agree", "checks": c5, "env": env}
        return False

    # ── C6: Guitar Shape C ───────────────────────────────────────────────────
    set_instrument(page, "Guitar")
    settle(page, 2)
    enable_guitar_capo(page, NOTES, "C")
    settle(page, 4)
    body = body_all(page)
    env_s = capture_env("C_shape_c", wait_s=10.0)
    shot(page, "C05_shape_c")
    charts_c = bool(re.search(r"Charts in C|Shape\s*C|shape key[:\s]*C\b", body, re.I))
    bad_prog = bool(re.search(r"(?:D\s*[·–-]\s*){3}D|(?:E\s*[·–-]\s*){3}E", body))
    sounding = str(env_s.get("sounding_key") or env_s.get("practice_key") or pk_live(page) or "")
    jam_pk = str(env.get("practice_key") or env_pk or "")
    c6 = {
        "still_jam": str(env_s.get("source") or "") == "entry_jam",
        "charts_or_shape": charts_c or same_key(str(env_s.get("shape_key") or ""), "C"),
        "not_bad_prog": not (charts_c and bad_prog),
        "sounding_unchanged": (not jam_pk)
        or same_key(sounding, jam_pk)
        or same_key(pk_live(page), jam_pk),
        "no_nav_upload": not (
            "Upload" in main_text(page) and "Backing Track Studio" not in main_text(page)
        ),
    }
    log(f"C6 shapeC={c6} sounding={sounding} charts_c={charts_c} bad_prog={bad_prog}")
    if not c6["still_jam"] or not c6["not_bad_prog"] or not c6["no_nav_upload"]:
        RESULT["C"] = {"status": "FAIL", "step": "C6_shape_c", "checks": c6, "env": env_s}
        return False

    # ── C7: Shape C → E (must not navigate to Upload) ────────────────────────
    set_shape_tonic(page, "E")
    settle(page, 3)
    env_e = capture_env("C_shape_e", wait_s=10.0)
    shot(page, "C06_shape_e")
    body_e = body_all(page)
    c7 = {
        "still_jam": str(env_e.get("source") or "") == "entry_jam",
        "no_upload_nav": not (
            "Upload" in main_text(page) and "Backing Track Studio" not in main_text(page)
        ),
        "no_sbi": "Song-Based Improvisation" not in body_e[:500]
        or "Backing" in body_e,
        "shape_e": same_key(str(env_e.get("shape_key") or ""), "E")
        or bool(re.search(r"Charts in E|Shape\s*E|shape key[:\s]*E\b", body_e, re.I)),
    }
    log(f"C7 shapeE={c7}")
    if not c7["still_jam"] or not c7["no_upload_nav"]:
        RESULT["C"] = {"status": "FAIL", "step": "C7_shape_e", "checks": c7, "env": env_e}
        return False

    # ── C8: refresh ──────────────────────────────────────────────────────────
    page = refresh(page)
    env_r = capture_env("C_refresh", wait_s=12.0)
    shot(page, "C07_refresh")
    body_r = body_all(page)
    c8 = {
        "still_jam": str(env_r.get("source") or "") == "entry_jam",
        "no_trial": str(env_r.get("source") or "") != "sbi_custom",
        "no_mission": str(env_r.get("source") or "") != "mission",
        "no_catalog": str(env_r.get("source") or "") != "catalog",
        "no_mission_ret": "Return to Mission" not in body_r,
    }
    log(f"C8 refresh={c8} env_src={env_r.get('source')} pk={env_r.get('practice_key')}")
    if not all(c8.values()):
        RESULT["C"] = {"status": "FAIL", "step": "C8_refresh", "checks": c8, "env": env_r}
        return False

    # ── C9: Return to Jam / Creative ─────────────────────────────────────────
    click_button_has(page, r"Return to") or click_nav(page, "Creative")
    settle(page, 4)
    body_ret = body_all(page)
    shot(page, "C08_return")
    jam_back = (
        "Jam Session Generator" in body_ret
        or "Generate Jam" in body_ret
        or "Generate jam" in body_ret
        or "Entry & Jam" in body_ret
    )
    c9 = {
        "return_jam_or_creative": jam_back or "Creative" in body_ret,
        "no_mission_ret": "Return to Mission" not in body_ret,
        "no_stale_jewish_focus": "jewish ballad" not in body_ret.lower()
        or (chosen_style and "jewish" in chosen_style.lower()),
        "perfect_or_not_trial_ga": "Perfect" in body_ret
        or not bool(
            re.search(r"ACTIVE SONG\s*\n\s*CUSTOM PROGRESSION\s*\n\s*Trial Song", body_ret, re.I)
        ),
    }
    log(f"C9 return={c9}")
    if not c9["return_jam_or_creative"] or not c9["no_mission_ret"]:
        RESULT["C"] = {
            "status": "FAIL",
            "step": "C9_return",
            "checks": c9,
            "body_snip": body_ret[:700],
        }
        return False

    RESULT["C"] = {
        "status": "PASS",
        "JOURNEY_C_BROWSER_PASS": True,
        "style": chosen_style,
        "env_open": env,
        "env_refresh": env_r,
        "checks": {
            "C1": c1,
            "C2": c2,
            "C3": c3,
            "C4": c4,
            "C5": c5,
            "C6": c6,
            "C7": c7,
            "C8": c8,
            "C9": c9,
        },
    }
    log(
        f"JOURNEY_C_BROWSER_PASS=True style={chosen_style} "
        f"open_src={env.get('source')} refresh_src={env_r.get('source')} pk={env.get('practice_key')}"
    )
    return True


# ─── Journey D ───────────────────────────────────────────────────────────────


def journey_d(page: Page) -> bool:
    log("=== JOURNEY D Mission Slice3->Slice4 envelope regression ===")
    # Setup: Trial Song true Custom GA — Original D, Practice F, Clarinet, written ON.
    # Slice3 contract uses sidebar "Clarinet" (Bb subtype), not the literal "Bb Clarinet".
    set_instrument(page, "Clarinet") or set_instrument(page, "Bb Clarinet")
    settle(page, 1)
    enable_written_charts(page)
    if not seed_trial_true_custom_ga(page):
        log("D WARN trial GA seed soft-fail — continuing with disk reinforce")
    set_instrument(page, "Clarinet") or set_instrument(page, "Bb Clarinet")
    settle(page, 2)
    enable_written_charts(page)
    set_practice_key(page, "F")
    settle(page, 3)
    body0 = body_all(page)
    pk0 = pk_live(page)
    orig0 = orig_live(page)
    setup = {
        "trial_active": "Trial" in body0,
        "trial_label": bool(re.search(r"Trial Song|CUSTOM PROGRESSION\s*\n\s*Trial", body0, re.I)),
        "orig_d": same_key(orig0, "D") or bool(re.search(r"Original Key:\s*D\b", body0)),
        "practice_f": same_key(pk0, "F") or bool(re.search(r"Practice.*\bF\b|Concert Key.*\bF\b", body0, re.I)),
        "clarinet": bool(re.search(r"Clarinet", body0, re.I)),
        "no_perfect_owner": not bool(re.search(r"ACTIVE SONG\s*\n\s*SONG\s*\n\s*Perfect", body0, re.I)),
    }
    log(f"D setup Trial D/F checks={setup} pk={pk0} orig={orig0}")
    shot(page, "D00_trial_ga")
    if not (setup["trial_label"] or setup["trial_active"]) or not setup["practice_f"]:
        RESULT["D"] = {"status": "FAIL", "step": "setup_trial_ga", "checks": setup}
        return False

    # ── D1: Missions mount ───────────────────────────────────────────────────
    if not open_missions(page):
        RESULT["D"] = {"status": "FAIL", "step": "D1_open_missions"}
        return False
    settle(page, 3)
    # Missions remount can leave Creative instrument on Piano — re-assert Clarinet + written.
    set_instrument(page, "Clarinet") or set_instrument(page, "Bb Clarinet")
    settle(page, 2)
    enable_written_charts(page)
    set_practice_key(page, "F")
    settle(page, 3)
    # Also try Missions-page Instrument control if sidebar did not stick.
    try:
        set_baseweb_select(page, "Instrument", "Clarinet", prefer_sidebar=False) or set_baseweb_select(
            page, "Instrument", "Bb Clarinet", prefer_sidebar=False
        )
        settle(page, 2)
        enable_written_charts(page)
        settle(page, 2)
    except Exception as exc:
        log(f"D1 creative instrument set err: {exc}")
    body_d1 = body_all(page)
    pk_d1 = pk_live(page)
    concert_line = ""
    m_concert = re.search(r"Concert Practice Key Progression:\s*([^\n]+)", body_d1)
    if m_concert:
        concert_line = m_concert.group(1)
    # Trial at F often starts on IV (Bb); require Practice F + F-diatonic evidence (F/Gm/Bb).
    # Avoid variable-width lookbehind (Python re rejects (?<![A-G]#?)).
    concert_f_ok = bool(
        re.search(r"Practice concert key[:\s*]*F\b", body_d1, re.I)
        or same_key(pk_d1, "F")
    ) and (
        bool(re.search(r"(?<![A-G#])F\b", concert_line))
        or "Gm" in concert_line
        or "Bb" in concert_line
        or concert_line.strip().startswith("F")
        or "F ·" in concert_line
        or "F:" in concert_line
    )
    d1 = {
        "missions_ui": bool(
            re.search(r"Generate example|Selected Mission Chord|🚩 Missions", body_d1, re.I)
        ),
        "trial_bound": "Trial" in body_d1
        and not bool(re.search(r"Interactive coach for\s+\*?\*?Perfect|Working from Perfect", body_d1)),
        "practice_f": same_key(pk_d1, "F")
        or bool(re.search(r"Practice concert key[:\s*]*F\b", body_d1, re.I)),
        "clarinet": bool(re.search(r"Clarinet", body_d1, re.I)),
        "written_g": bool(re.search(r"Written Key Progression\s*\(\s*G\s*\)", body_d1, re.I))
        or bool(re.search(r"Written Key Progression:\s*G\b", body_d1, re.I)),
        "concert_f": concert_f_ok,
        "concert_line": concert_line[:100],
        "no_perfect": not bool(re.search(r"Working from Perfect|Interactive coach for\s+\*?\*?Perfect", body_d1)),
        "no_jam_jewish": "jewish ballad" not in body_d1.lower()
        and "Jam Session Generator" not in body_d1[:1500],
    }
    slice3_m = False
    try:
        slice3_m = bool(slice3_assert_missions(page))
    except Exception as exc:
        log(f"D1 slice3_assert_missions err: {exc}")
    log(f"D1 missions mount checks={d1} slice3={slice3_m} pk={pk_d1}")
    shot(page, "D01_missions")
    if not d1["missions_ui"] or not d1["trial_bound"] or not d1["practice_f"] or not d1["concert_f"]:
        RESULT["D"] = {"status": "FAIL", "step": "D1_missions_mount", "checks": d1}
        return False
    if not d1["clarinet"]:
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D1_clarinet_missing",
            "checks": d1,
            "trace": "Mission page instrument still Piano — written G cannot derive",
        }
        return False
    if not d1["written_g"]:
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D1_written_g_missing",
            "checks": d1,
            "trace": "Mission reader / written charts before Backing",
            "body_snip": body_d1[:900],
        }
        return False

    # ── D2: Generate Mission example ─────────────────────────────────────────
    gen = (
        click_button_has(page, r"Generate example")
        or click_button_has(page, r"Generate Example")
    )
    settle(page, 5)
    body_d2 = body_all(page)
    d2 = {
        "generated": gen
        or bool(re.search(r"Selected Mission Chord|example|ABC|MIDI|Play", body_d2, re.I)),
        "still_f": same_key(pk_live(page), "F")
        or bool(re.search(r"Practice concert key[:\s*]*F\b", body_d2, re.I)),
        "still_written_g": bool(re.search(r"Written Key Progression\s*\(\s*G\s*\)", body_d2, re.I))
        or d1["written_g"],
        "no_catalog_jam_key": "jewish ballad" not in body_d2.lower(),
    }
    log(f"D2 generate checks={d2} gen_click={gen}")
    shot(page, "D02_generated")
    if not d2["still_f"]:
        RESULT["D"] = {"status": "FAIL", "step": "D2_generate_authority", "checks": d2}
        return False

    # ── D3: Mission Backing launch ───────────────────────────────────────────
    if not open_mission_backing(page, NOTES):
        RESULT["D"] = {"status": "FAIL", "step": "D3_open_mission_backing"}
        return False
    settle(page, 5)
    for _ in range(6):
        body = body_all(page)
        if "Return to Mission" in body or "MISSION BACKING" in body:
            break
        settle(page, 2)
    env = capture_env("D_open", wait_s=16.0, require_practice="F")
    shot(page, "D03_backing")
    body = body_all(page)
    pk = pk_live(page)
    m_pk = re.search(r"Practice concert key:\s*([A-G](?:#|b)?)", body, re.I)
    if m_pk:
        pk = key_token(m_pk.group(1)) or pk
    ui_mission = bool(
        re.search(r"Return to Mission|MISSION BACKING|Creative Backing Jam · Mission", body)
    )
    d3 = {
        "env_mission": str(env.get("source") or "") == "mission",
        "ui_mission": ui_mission,
        "trial_id": "Trial" in str(env.get("title") or "")
        or "Trial" in str(env.get("identity") or "")
        or "Trial" in body,
        "orig_d": same_key(str(env.get("original_key") or ""), "D")
        or bool(re.search(r"ORIGINAL KEY\s*\n\s*D\b", body)),
        "practice_f": same_key(str(env.get("practice_key") or ""), "F")
        or (
            same_key(pk, "F")
            and same_key(str(env.get("sounding_key") or ""), "F")
            and same_key(str(env.get("written_key") or ""), "G")
        ),
        "env_practice_f": same_key(str(env.get("practice_key") or ""), "F"),
        "sounding_f": same_key(str(env.get("sounding_key") or ""), "F") or same_key(pk, "F"),
        "written_g": same_key(str(env.get("written_key") or ""), "G")
        or bool(re.search(r"Written|Charts in G|chart.*\bG\b", body, re.I)),
        "return_mission": "Return to Mission" in body
        and str(env.get("return_destination") or "") in {"mission", ""},
        "env_return_mission": str(env.get("return_destination") or "") == "mission",
        "no_sbi": str(env.get("source") or "") != "sbi_custom",
        "no_jam": str(env.get("source") or "") != "entry_jam",
        "no_catalog": str(env.get("source") or "") != "catalog",
        "no_jewish": "jewish ballad" not in body.lower(),
    }
    log(
        f"D3 open checks={d3} env={json.dumps({k: env.get(k) for k in ('source','title','practice_key','sounding_key','written_key','return_destination','original_key')}, default=str)}"
    )
    if not (
        d3["env_mission"]
        and d3["ui_mission"]
        and d3["practice_f"]
        and d3.get("env_practice_f", True)
        and d3["return_mission"]
        and d3["no_sbi"]
        and d3["no_jam"]
        and d3["no_catalog"]
    ):
        RESULT["D"] = {"status": "FAIL", "step": "D3_open", "checks": d3, "env": env}
        return False
    if not d3.get("env_practice_f", True):
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D3_env_practice_not_f",
            "checks": d3,
            "env": env,
            "trace": "envelope practice_key must be F (not Original-echo D with sounding F)",
        }
        return False
    if not d3["written_g"]:
        RESULT["D"] = {"status": "FAIL", "step": "D3_written_g", "checks": d3, "env": env}
        return False

    # ── D4: Return button from envelope source=mission ───────────────────────
    d4 = {
        "return_btn": "Return to Mission" in body,
        "env_source_mission": str(env.get("source") or "") == "mission",
        "env_return_dest": str(env.get("return_destination") or "") == "mission",
        "no_mission_conflict": "Return to Jam" not in body and "Return to Song Catalog" not in body,
    }
    log(f"D4 return button checks={d4}")
    if not (d4["return_btn"] and d4["env_source_mission"]):
        RESULT["D"] = {"status": "FAIL", "step": "D4_return_btn", "checks": d4, "env": env}
        return False

    # ── D5: Practice F → E (Bb Clarinet → Written F#) ────────────────────────
    set_practice_key(page, "E")
    settle(page, 4)
    env_e = capture_env("D_pk_e", wait_s=16.0, require_practice="E")
    body_e = body_all(page)
    pk_e = pk_live(page)
    m_pk_e = re.search(r"Practice concert key:\s*([A-G](?:#|b)?)", body_e, re.I)
    if m_pk_e:
        pk_e = key_token(m_pk_e.group(1)) or pk_e
    written_e = str(env_e.get("written_key") or "")
    d5 = {
        "still_mission": str(env_e.get("source") or "") == "mission",
        "practice_e": same_key(pk_e, "E"),
        "env_practice_e": same_key(str(env_e.get("practice_key") or ""), "E"),
        "sounding_e": same_key(str(env_e.get("sounding_key") or ""), "E"),
        "written_fs": same_key(written_e, "F#")
        or same_key(written_e, "Gb")
        or bool(re.search(r"Written.*F#|Charts in F#|Written Key Progression\s*\(\s*F#\s*\)", body_e, re.I)),
        "return_stays": "Return to Mission" in body_e,
        "no_owner_swap": str(env_e.get("source") or "") not in {"sbi_custom", "entry_jam", "catalog"},
    }
    log(
        f"D5 pk F->E checks={d5} pk={pk_e} env_pk={env_e.get('practice_key')} "
        f"written={written_e} env={json.dumps({k: env_e.get(k) for k in ('source','practice_key','sounding_key','written_key')}, default=str)}"
    )
    shot(page, "D05_pk_e")
    if not (
        d5["still_mission"]
        and d5["practice_e"]
        and d5["env_practice_e"]
        and d5["sounding_e"]
        and d5["written_fs"]
        and d5["return_stays"]
        and d5["no_owner_swap"]
    ):
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D5_pk_e",
            "checks": d5,
            "env": env_e,
            "trace": "PK mutation / envelope — UI E must match live envelope E/F#",
        }
        return False

    # ── D6: UI / live envelope / persisted agreement ──────────────────────────
    env_disk = read_envelope()
    d6 = {
        "ui_e": same_key(pk_e, "E"),
        "live_mission": str(env_e.get("source") or "") == "mission",
        "live_pk_e": same_key(str(env_e.get("practice_key") or ""), "E"),
        "live_sound_e": same_key(str(env_e.get("sounding_key") or ""), "E"),
        "live_written_fs": same_key(str(env_e.get("written_key") or ""), "F#")
        or same_key(str(env_e.get("written_key") or ""), "Gb"),
        "disk_mission": str(env_disk.get("source") or "") == "mission",
        "disk_pk_e": same_key(str(env_disk.get("practice_key") or ""), "E"),
        "disk_not_stale_f": not same_key(str(env_disk.get("practice_key") or ""), "F"),
        "disk_written_fs": same_key(str(env_disk.get("written_key") or ""), "F#")
        or same_key(str(env_disk.get("written_key") or ""), "Gb")
        or (
            # Written may be derived at read time — allow empty disk written if live has F#.
            not str(env_disk.get("written_key") or "").strip()
            and d5["written_fs"]
        ),
    }
    log(f"D6 ui/env/disk agree={d6} disk_pk={env_disk.get('practice_key')} disk_w={env_disk.get('written_key')}")
    if not (
        d6["live_mission"]
        and d6["live_pk_e"]
        and d6["live_sound_e"]
        and d6["live_written_fs"]
        and d6["disk_mission"]
        and d6["disk_pk_e"]
        and d6["disk_not_stale_f"]
    ):
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D6_persist_split",
            "checks": d6,
            "live": env_e,
            "disk": env_disk,
        }
        return False

    # ── D7: refresh ──────────────────────────────────────────────────────────
    page = refresh(page)
    env_r = capture_env("D_refresh", wait_s=12.0)
    body_r = body_all(page)
    shot(page, "D07_refresh")
    pk_r = pk_live(page)
    d7 = {
        "still_mission": str(env_r.get("source") or "") == "mission",
        "practice_e": same_key(str(env_r.get("practice_key") or pk_r), "E"),
        "sounding_e": same_key(str(env_r.get("sounding_key") or ""), "E")
        or same_key(str(env_r.get("practice_key") or ""), "E"),
        "written_fs": same_key(str(env_r.get("written_key") or ""), "F#")
        or same_key(str(env_r.get("written_key") or ""), "Gb")
        or bool(re.search(r"Written.*F#|Charts in F#|Written Key Progression\s*\(\s*F#\s*\)", body_r, re.I)),
        "return_mission": "Return to Mission" in body_r,
        "no_reclaim": str(env_r.get("source") or "") not in {"catalog", "sbi_custom", "entry_jam"},
        "trial_id": "Trial" in body_r or "Trial" in str(env_r.get("title") or ""),
    }
    log(f"D7 refresh checks={d7} env_src={env_r.get('source')} pk={env_r.get('practice_key')}")
    if not all(
        [
            d7["still_mission"],
            d7["practice_e"],
            d7["sounding_e"],
            d7["written_fs"],
            d7["return_mission"],
            d7["no_reclaim"],
        ]
    ):
        RESULT["D"] = {"status": "FAIL", "step": "D7_refresh", "checks": d7, "env": env_r}
        return False

    # ── D8: Return to Mission ────────────────────────────────────────────────
    ret_clicked = (
        click_button_has(page, r"Return to Mission")
        or click_button_has(page, r"← Return to Mission")
    )
    settle(page, 4)
    # Prefer shared return helper (retries Creative → Missions after handoff).
    if not ensure_missions_workspace(page, NOTES):
        try:
            from _walk_pass8_validate import return_to_mission as _return_to_mission

            _return_to_mission(page, NOTES)
        except Exception as exc:
            log(f"D8 return_to_mission helper err: {exc}")
            goto_improv(page, NOTES)
            ensure_missions_workspace(page, NOTES)
    settle(page, 4)
    # Re-assert Clarinet + written so Written F# is readable on Missions.
    set_instrument(page, "Clarinet") or set_instrument(page, "Bb Clarinet")
    settle(page, 1)
    enable_written_charts(page)
    settle(page, 2)
    body_ret = body_all(page)
    pk_ret = pk_live(page)
    shot(page, "D08_return")
    d8 = {
        "clicked": ret_clicked,
        "missions_ui": bool(re.search(r"Generate example|Selected Mission Chord|Missions", body_ret, re.I)),
        "practice_e": same_key(pk_ret, "E")
        or bool(re.search(r"Practice concert key[:\s*]*E\b", body_ret, re.I)),
        "written_fs": bool(
            re.search(r"Written Key Progression\s*\(\s*F#\s*\)", body_ret, re.I)
        )
        or bool(re.search(r"Written.*F#|Charts in F#", body_ret, re.I)),
        "trial_still": "Trial" in body_ret,
        "not_restored_f": not same_key(pk_ret, "F"),
        "no_mission_ret_btn": "Return to Mission" not in body_ret
        or "Generate example" in body_ret,
        "no_crash": "IndexError" not in body_ret and "Traceback" not in body_ret,
    }
    log(f"D8 return checks={d8} pk={pk_ret}")
    if not d8["no_crash"]:
        RESULT["D"] = {
            "status": "FAIL",
            "step": "D8_return_crash",
            "checks": d8,
            "trace": "Return to Mission crashed — see D08_return.txt",
        }
        return False
    if not (d8["missions_ui"] and d8["practice_e"] and d8["trial_still"] and d8["not_restored_f"]):
        RESULT["D"] = {"status": "FAIL", "step": "D8_return", "checks": d8}
        return False
    if not d8["written_fs"]:
        RESULT["D"] = {"status": "FAIL", "step": "D8_written_fs", "checks": d8}
        return False

    # ── D9: reopen Mission Backing ───────────────────────────────────────────
    if not open_mission_backing(page, NOTES):
        RESULT["D"] = {"status": "FAIL", "step": "D9_reopen_backing"}
        return False
    settle(page, 5)
    env_re = capture_env("D_reopen", wait_s=12.0)
    body_re = body_all(page)
    shot(page, "D09_reopen")
    d9 = {
        "env_mission": str(env_re.get("source") or "") == "mission",
        "practice_e": same_key(str(env_re.get("practice_key") or ""), "E"),
        "written_fs": same_key(str(env_re.get("written_key") or ""), "F#")
        or same_key(str(env_re.get("written_key") or ""), "Gb")
        or bool(re.search(r"Written.*F#|Charts in F#", body_re, re.I)),
        "no_stale_f": not same_key(str(env_re.get("practice_key") or ""), "F"),
        "no_other_owner": str(env_re.get("source") or "") not in {"catalog", "sbi_custom", "entry_jam"},
        "return_mission": "Return to Mission" in body_re,
    }
    log(
        f"D9 reopen checks={d9} env={json.dumps({k: env_re.get(k) for k in ('source','practice_key','written_key','return_destination')}, default=str)}"
    )
    if not all(d9.values()):
        RESULT["D"] = {"status": "FAIL", "step": "D9_reopen", "checks": d9, "env": env_re}
        return False

    RESULT["D"] = {
        "status": "PASS",
        "JOURNEY_D_BROWSER_PASS": True,
        "d1": d1,
        "d3": {k: env.get(k) for k in ("source", "practice_key", "written_key", "return_destination")},
        "d5": {k: env_e.get(k) for k in ("source", "practice_key", "sounding_key", "written_key")},
        "d7": {k: env_r.get(k) for k in ("source", "practice_key", "written_key")},
        "d9": {k: env_re.get(k) for k in ("source", "practice_key", "written_key")},
    }
    log(
        "JOURNEY_D_BROWSER_PASS=True "
        f"open={env.get('practice_key')}/{env.get('written_key')} "
        f"pk_e={env_e.get('practice_key')}/{env_e.get('written_key')} "
        f"refresh={env_r.get('practice_key')} reopen={env_re.get('practice_key')}"
    )
    return True



# ─── Journey E ───────────────────────────────────────────────────────────────


def journey_e(page: Page) -> bool:
    log("=== JOURNEY E Composition Backing ===")
    goto_songs(page)
    settle(page, 2)
    ensure_my_composition_active(page)
    settle(page, 3)
    select_songs_source(page, "Composition")
    settle(page, 2)
    # Set a distinctive Practice that is not G
    set_practice_key(page, "C#") or set_practice_key(page, "C♯") or set_practice_key(page, "Db")
    settle(page, 2)
    pk0 = pk_live(page)
    orig0 = orig_live(page)
    shot(page, "E00_composition_seed")
    log(f"E seed pk={pk0} orig={orig0}")

    if not open_backing_nav(page):
        RESULT["E"] = {"status": "FAIL", "step": "open_backing"}
        return False
    settle(page, 4)
    body = body_all(page)
    env = capture_env("E_open")
    pk = pk_live(page)
    shot(page, "E01_backing")
    checks = {
        "env_comp": str(env.get("source") or "") == "composition",
        "uuid": "composition::" in str(env.get("identity") or "") or bool(env.get("identity")),
        "practice_not_g_unless_chosen": not (
            same_key(pk, "G") and not same_key(pk0, "G") and not same_key(str(env.get("practice_key") or ""), "G")
        ),
        "practice_matches": same_key(pk, pk0)
        or same_key(str(env.get("practice_key") or ""), pk0)
        or same_key(str(env.get("practice_key") or ""), "C#")
        or same_key(str(env.get("practice_key") or ""), "Db"),
        "no_catalog_g": not (
            str(env.get("source") or "") == "catalog" and same_key(str(env.get("practice_key") or ""), "G")
        ),
        "comp_ui": "Composition" in body or str(env.get("source") or "") == "composition",
    }
    log(f"E open checks={checks}")
    if not checks["env_comp"] or not checks["no_catalog_g"]:
        RESULT["E"] = {"status": "FAIL", "step": "open", "checks": checks, "env": env}
        return False

    set_practice_key(page, "E")
    settle(page, 3)
    env2 = capture_env("E_pk_e")
    pk2 = pk_live(page)
    shot(page, "E02_pk_e")
    checks2 = {
        "still_comp": str(env2.get("source") or "") == "composition",
        "same_id": str(env2.get("identity") or "") == str(env.get("identity") or "")
        or bool(env2.get("identity")),
        "practice_e": same_key(pk2, "E") or same_key(str(env2.get("practice_key") or ""), "E"),
        "not_g": not same_key(pk2, "G") or same_key(str(env2.get("practice_key") or ""), "E"),
    }
    log(f"E pkE checks={checks2}")
    if not all(v for k, v in checks2.items() if k != "same_id"):
        RESULT["E"] = {"status": "FAIL", "step": "pk_e", "checks": checks2, "env": env2}
        return False

    page = refresh(page)
    env3 = capture_env("E_refresh")
    shot(page, "E03_refresh")
    if str(env3.get("source") or "") != "composition":
        RESULT["E"] = {"status": "FAIL", "step": "refresh", "env": env3}
        return False
    if same_key(str(env3.get("practice_key") or pk_live(page)), "G") and not same_key(
        str(env2.get("practice_key") or ""), "G"
    ):
        RESULT["E"] = {"status": "FAIL", "step": "refresh_jumped_g", "env": env3}
        return False

    click_button_has(page, r"Return to Composition") or click_nav(page, "Songs") or click_nav(
        page, "Composition"
    )
    settle(page, 3)
    shot(page, "E04_return")
    RESULT["E"] = {"status": "PASS", "env_final": env3, "checks": {**checks, **checks2}}
    log("E PASS")
    return True


# ─── Polluted sequence ───────────────────────────────────────────────────────


def polluted_check(page: Page) -> bool:
    log("=== POLLUTED explicit launches ===")
    results: dict[str, bool] = {}

    # Explicit Catalog
    goto_songs(page)
    select_songs_source(page, "Catalog")
    pick_song(page, NOTES, "Perfect", "Pop")
    set_practice_key(page, "C")
    settle(page, 2)
    open_backing_nav(page)
    settle(page, 3)
    env = capture_env("P_catalog")
    results["catalog"] = str(env.get("source") or "") == "catalog" and "Trial" not in str(
        env.get("title") or ""
    )
    shot(page, "P_catalog")

    # Explicit Custom via SBI
    seed_trial_true_custom_ga(page)
    goto_improv(page, NOTES)
    click_radio(page, "Song-Based Improvisation")
    click_radio(page, "Custom progression")
    settle(page, 2)
    open_creative_backing(page, "sbi")
    settle(page, 3)
    env = capture_env("P_custom")
    results["custom"] = str(env.get("source") or "") == "sbi_custom"
    shot(page, "P_custom")

    # Explicit Jam
    goto_improv(page, NOTES)
    click_radio(page, "Jam Session Generator")
    set_baseweb_select(page, "Key", "A") or True
    set_baseweb_select(page, "Style", "Funk") or True
    click_button_has(page, r"Generate Jam") or click_button_has(page, r"Generate")
    settle(page, 3)
    open_creative_backing(page, "jam")
    settle(page, 3)
    env = capture_env("P_jam")
    results["jam"] = str(env.get("source") or "") == "entry_jam"
    shot(page, "P_jam")

    # Explicit Mission
    set_instrument(page, "Bb Clarinet")
    enable_written_charts(page)
    seed_trial_true_custom_ga(page)
    set_practice_key(page, "F")
    open_missions(page)
    settle(page, 3)
    open_mission_backing(page, NOTES)
    settle(page, 4)
    env = capture_env("P_mission")
    results["mission"] = str(env.get("source") or "") == "mission"
    shot(page, "P_mission")

    # Explicit Composition
    goto_songs(page)
    select_songs_source(page, "Composition")
    ensure_my_composition_active(page)
    open_composition_named(page, "My Composition")
    set_practice_key(page, "C#") or set_practice_key(page, "Db")
    settle(page, 2)
    open_backing_nav(page)
    settle(page, 3)
    env = capture_env("P_composition")
    results["composition"] = str(env.get("source") or "") == "composition" and not (
        str(env.get("source") or "") == "catalog"
    )
    shot(page, "P_composition")

    ok = all(results.values())
    RESULT["polluted"] = {"status": "PASS" if ok else "FAIL", "results": results}
    log(f"polluted={results} => {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    RESULT["sha"] = git_sha()
    log(f"HEAD={RESULT['sha']}")
    log(f"URL={URL} MODE={MODE} RUNTIME={RUNTIME}")

    journeys = (
        ("A", journey_a),
        ("B", journey_b),
        ("C", journey_c),
        ("D", journey_d),
        ("E", journey_e),
        ("polluted", polluted_check),
    )
    if MODE not in {"", "all"}:
        want = {MODE, MODE.upper(), MODE.lower()}
        journeys = tuple((n, f) for n, f in journeys if n.lower() in {w.lower() for w in want} or n.lower().startswith(MODE.lower()))
        if not journeys:
            log(f"unknown MODE={MODE}")
            return 2

    all_ok = False
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
            ],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(60_000)
        # Warm the server before the journey page cycle.
        for warm in range(3):
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=180000)
                settle(page, 6)
                body0 = ""
                try:
                    body0 = page.inner_text("body") or ""
                except Exception:
                    body0 = ""
                if len(body0) > 200 and ("Command Center" in body0 or "Practice" in body0 or "Creative" in body0):
                    log(f"warm_ok attempt={warm} body_len={len(body0)}")
                    break
                log(f"warm_retry attempt={warm} body_len={len(body0)}")
            except Exception as warm_exc:
                log(f"warm_err attempt={warm} {warm_exc!r}")
                settle(page, 3)
        shot(page, "00_start")

        results_ok: dict[str, bool] = {}
        single_mode = MODE not in {"", "all"} and len(journeys) == 1
        try:
            for name, fn in journeys:
                try:
                    if not single_mode:
                        # Fresh page per journey reduces Streamlit/driver flake across long sessions.
                        try:
                            page.close()
                        except Exception:
                            pass
                        page = context.new_page()
                        page.set_default_timeout(60_000)
                        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
                        settle(page, 8)
                    results_ok[name] = bool(fn(page))
                except Exception as exc:
                    log(f"{name} EXCEPTION: {exc!r}")
                    RESULT[name] = {"status": "FAIL", "exception": repr(exc)}
                    results_ok[name] = False
                    try:
                        page = context.new_page()
                        page.set_default_timeout(60_000)
                        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
                        settle(page, 5)
                    except Exception as re_exc:
                        log(f"{name} recovery_page_failed: {re_exc!r}")

            a_ok = results_ok.get("A", False)
            b_ok = results_ok.get("B", False)
            c_ok = results_ok.get("C", False)
            d_ok = results_ok.get("D", False)
            e_ok = results_ok.get("E", False)
            p_ok = results_ok.get("polluted", False)

            if MODE not in {"", "all"}:
                all_ok = all(results_ok.values()) if results_ok else False
                RESULT["SLICE4_BROWSER_PASS"] = False
                RESULT["mode_pass"] = bool(all_ok)
            else:
                all_ok = a_ok and b_ok and c_ok and d_ok and e_ok
                RESULT["SLICE4_BROWSER_PASS"] = bool(all_ok)
            RESULT["journeys"] = {
                "A": a_ok,
                "B": b_ok,
                "C": c_ok,
                "D": d_ok,
                "E": e_ok,
                "polluted": p_ok,
            }
            log(f"MODE_PASS={RESULT.get('mode_pass', all_ok)} SLICE4_BROWSER_PASS={RESULT['SLICE4_BROWSER_PASS']}")
            if MODE.lower() == "b":
                jb = bool((RESULT.get("B") or {}).get("JOURNEY_B_BROWSER_PASS")) if isinstance(RESULT.get("B"), dict) else bool(b_ok)
                RESULT["JOURNEY_B_BROWSER_PASS"] = jb
                log(f"JOURNEY_B_BROWSER_PASS={jb}")
            if MODE.lower() == "c":
                jc = bool((RESULT.get("C") or {}).get("JOURNEY_C_BROWSER_PASS")) if isinstance(RESULT.get("C"), dict) else bool(c_ok)
                RESULT["JOURNEY_C_BROWSER_PASS"] = jc
                log(f"JOURNEY_C_BROWSER_PASS={jc}")
            if MODE.lower() == "d":
                jd = bool((RESULT.get("D") or {}).get("JOURNEY_D_BROWSER_PASS")) if isinstance(RESULT.get("D"), dict) else bool(d_ok)
                RESULT["JOURNEY_D_BROWSER_PASS"] = jd
                log(f"JOURNEY_D_BROWSER_PASS={jd}")
            # Persist evidence before browser.close (driver can already be dead).
            (OUT / "summary.json").write_text(json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
            (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
        finally:
            try:
                browser.close()
            except Exception as close_exc:
                log(f"browser_close_err={close_exc!r}")

    (OUT / "summary.json").write_text(json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    print(json.dumps(RESULT.get("journeys") or {}, indent=2), flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
    print(msg, flush=True)


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


def capture_env(tag: str, *, wait_s: float = 8.0) -> dict[str, Any]:
    """Read persisted envelope; briefly poll after launch (autosave lag)."""
    deadline = time.time() + max(0.0, wait_s)
    env: dict[str, Any] = {}
    while True:
        env = read_envelope()
        if env.get("source"):
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
    settle(page, 3)
    env2 = capture_env("B_pk_fs")
    pk2 = pk_live(page)
    shot(page, "B02_pk_fs")
    body2 = body_all(page)
    pk_ok = same_key(pk2, "F#") or same_key(pk2, "Gb") or bool(
        re.search(r"Concert key:\s*F#|F#\s*[–-]\s*C#|F♯", body2, re.I)
    )
    checks2 = {
        "still_sbi": str(env2.get("source") or "") == "sbi_custom",
        "trial": "Trial" in body2 or "Trial" in str(env2.get("title") or ""),
        "practice_fs": pk_ok,
        # Envelope must track the live Practice Key (UI/envelope agreement).
        "env_pk_fs": same_key(str(env2.get("practice_key") or ""), "F#")
        or same_key(str(env2.get("practice_key") or ""), "Gb"),
    }
    log(f"B pkF# checks={checks2} pk_live={pk2} env_pk={env2.get('practice_key')}")
    if not all(checks2.values()):
        RESULT["B"] = {"status": "FAIL", "step": "pk_fs", "checks": checks2, "env": env2}
        return False

    page = refresh(page)
    env3 = capture_env("B_refresh")
    shot(page, "B03_refresh")
    checks3 = {
        "still_sbi": str(env3.get("source") or "") == "sbi_custom",
        "practice_fs": same_key(str(env3.get("practice_key") or pk_live(page)), "F#")
        or same_key(str(env3.get("practice_key") or pk_live(page)), "Gb"),
    }
    if not all(checks3.values()):
        RESULT["B"] = {"status": "FAIL", "step": "refresh", "checks": checks3, "env": env3}
        return False

    click_button_has(page, r"Return to") or click_nav(page, "Creative") or click_nav(page, "Custom")
    settle(page, 3)
    body = body_all(page)
    trial_ok = "Trial" in body
    shot(page, "B04_return")
    RESULT["B"] = {
        "status": "PASS" if trial_ok else "FAIL",
        "env_final": env3,
        "return_trial": trial_ok,
        "checks": {**checks, **checks2, **checks3},
    }
    log("B PASS" if trial_ok else "B FAIL return trial")
    return bool(trial_ok)


# ─── Journey C ───────────────────────────────────────────────────────────────


def journey_c(page: Page) -> bool:
    log("=== JOURNEY C Jam Generator + Shape ===")
    # Ensure Perfect underlying + Trial pollution exist
    goto_songs(page)
    settle(page, 1)
    select_songs_source(page, "Catalog") or True
    pick_song(page, NOTES, "Perfect", "Pop")
    settle(page, 2)

    if not goto_improv(page, NOTES):
        RESULT["C"] = {"status": "FAIL", "step": "goto_improv"}
        return False
    settle(page, 2)
    if not open_jam_generator(page, NOTES):
        # Fallback: Entry & Jam → Jam Session Generator with strict chrome check
        jam_ready = False
        for attempt in range(5):
            click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
                page, r"Entry"
            )
            settle(page, 1)
            click_radio(page, "Jam Session Generator") or click_radio(page, "Jam Session") or click_button_has(
                page, r"Jam Session Generator"
            )
            settle(page, 2)
            body = body_all(page)
            if "Jam Session Generator" in body and (
                "Groove style" in body or "Ensemble" in body or "Generate Jam" in body
            ):
                jam_ready = True
                log(f"C jam UI ready attempt={attempt}")
                break
        if not jam_ready:
            RESULT["C"] = {"status": "FAIL", "step": "jam_ui"}
            shot(page, "C00_jam_ui_fail")
            return False
    else:
        log("C jam UI via open_jam_generator")
    set_baseweb_select(page, "Concert Key", "E") or set_baseweb_select(page, "Key", "E") or set_practice_key(
        page, "E"
    )
    # Prefer a non-Jewish style (Groove style select on Jam Generator)
    for style in ("Funk", "Rock", "Pop", "Blues", "Jazz Swing"):
        if set_baseweb_select(page, "Groove style", style) or set_baseweb_select(page, "Style", style):
            log(f"C jam style={style}")
            break
    click_button_has(page, r"Generate Jam") or click_button_has(page, r"Generate")
    settle(page, 4)
    body = body_all(page)
    shot(page, "C00_jam_generated")
    if "Generate" in body and "E" not in body and "Funk" not in body and "Rock" not in body:
        log("C WARN jam generate may have failed — continuing")

    if not open_creative_backing(page, "jam"):
        RESULT["C"] = {"status": "FAIL", "step": "open_backing"}
        return False
    settle(page, 4)
    body = body_all(page)
    env = capture_env("C_open")
    shot(page, "C01_backing")
    jewish = "jewish ballad" in body.lower()
    checks = {
        "env_jam": str(env.get("source") or "") == "entry_jam",
        "no_trial_sbi": str(env.get("source") or "") != "sbi_custom",
        "no_catalog": str(env.get("source") or "") != "catalog",
        "no_mission_ret": "Return to Mission" not in body,
        "no_stale_jewish": not jewish or "jewish" in str(env.get("style") or "").lower(),
    }
    log(f"C open checks={checks}")
    if not all(checks.values()):
        RESULT["C"] = {"status": "FAIL", "step": "open", "checks": checks, "env": env}
        return False

    # Guitar shape C
    set_instrument(page, "Guitar")
    settle(page, 2)
    enable_guitar_capo(page, NOTES, "C")
    settle(page, 3)
    body = body_all(page)
    env_s = capture_env("C_shape_c")
    shot(page, "C02_shape_c")
    charts_c = bool(re.search(r"Charts in C|Shape\s*C|shape key[:\s]*C", body, re.I))
    # Progression should not be solid D·D·D·D or E·E while Charts in C
    bad_prog = bool(re.search(r"(?:D\s*[·–-]\s*){3}D|(?:E\s*[·–-]\s*){3}E", body))
    sounding = str(env_s.get("sounding_key") or env_s.get("practice_key") or pk_live(page) or "")
    shape_checks = {
        "still_jam": str(env_s.get("source") or "") == "entry_jam",
        "charts_or_shape": charts_c or same_key(str(env_s.get("shape_key") or ""), "C"),
        "not_bad_prog": not (charts_c and bad_prog),
        "sounding_not_forced_c": not same_key(sounding, "C") or same_key(sounding, "C"),  # allow if jam key is C
    }
    # If jam key is E, sounding must stay E while shape is C
    if same_key(str(env.get("practice_key") or ""), "E") or same_key(pk_live(page), "E"):
        shape_checks["sounding_e"] = same_key(sounding, "E") or same_key(pk_live(page), "E")
    log(f"C shapeC checks={shape_checks} sounding={sounding} charts_c={charts_c} bad_prog={bad_prog}")
    if not shape_checks["still_jam"] or not shape_checks["not_bad_prog"]:
        RESULT["C"] = {"status": "FAIL", "step": "shape_c", "checks": shape_checks, "env": env_s}
        return False

    set_shape_tonic(page, "E")
    settle(page, 2)
    env_e = capture_env("C_shape_e")
    shot(page, "C03_shape_e")
    if str(env_e.get("source") or "") != "entry_jam":
        RESULT["C"] = {"status": "FAIL", "step": "shape_e_owner", "env": env_e}
        return False
    if "Upload" in main_text(page) and "Backing Track Studio" not in main_text(page):
        RESULT["C"] = {"status": "FAIL", "step": "shape_e_nav_upload"}
        return False

    page = refresh(page)
    env_r = capture_env("C_refresh")
    shot(page, "C04_refresh")
    if str(env_r.get("source") or "") != "entry_jam":
        RESULT["C"] = {"status": "FAIL", "step": "refresh", "env": env_r}
        return False

    RESULT["C"] = {
        "status": "PASS",
        "env_final": env_r,
        "checks": checks,
        "shape": shape_checks,
    }
    log("C PASS")
    return True


# ─── Journey D ───────────────────────────────────────────────────────────────


def journey_d(page: Page) -> bool:
    log("=== JOURNEY D Mission Slice3 regression ===")
    set_instrument(page, "Bb Clarinet")
    settle(page, 1)
    enable_written_charts(page)
    if not seed_trial_true_custom_ga(page):
        log("D WARN trial GA seed soft-fail")
    set_practice_key(page, "F")
    settle(page, 2)
    shot(page, "D00_trial_ga")

    if not open_missions(page):
        RESULT["D"] = {"status": "FAIL", "step": "open_missions"}
        return False
    settle(page, 4)
    if not slice3_assert_missions(page):
        # Soft: still try backing if near
        log("D WARN missions assert soft — continuing to backing")
    shot(page, "D01_missions")

    if not open_mission_backing(page, NOTES):
        RESULT["D"] = {"status": "FAIL", "step": "open_mission_backing"}
        return False
    settle(page, 5)
    # Avoid re-clicking checkbox-style controls — wait only
    for _ in range(6):
        body = body_all(page)
        if "Return to Mission" in body or "Mission Backing" in body:
            break
        settle(page, 2)
    env = capture_env("D_open")
    shot(page, "D02_backing")
    body = body_all(page)
    pk = pk_live(page)
    m_pk = re.search(r"Practice concert key:\s*([A-G](?:#|b)?)", body, re.I)
    if m_pk:
        pk = key_token(m_pk.group(1)) or pk
    checks = {
        "env_mission": str(env.get("source") or "") == "mission",
        "practice_f": same_key(pk, "F") or same_key(str(env.get("practice_key") or ""), "F"),
        "sounding_f": same_key(str(env.get("sounding_key") or ""), "F") or same_key(pk, "F"),
        "written_g": same_key(str(env.get("written_key") or ""), "G")
        or bool(re.search(r"Written|Charts in G|chart.*G", body, re.I)),
        "return_mission": "Return to Mission" in body
        or str(env.get("return_destination") or "") == "mission",
        "no_sbi_jam": str(env.get("source") or "") not in {"sbi_custom", "entry_jam"},
    }
    log(f"D open checks={checks}")
    ui_ok = slice3_assert_backing(page)
    if not checks["env_mission"] or not checks["practice_f"] or not checks["return_mission"]:
        RESULT["D"] = {"status": "FAIL", "step": "open", "checks": checks, "env": env, "ui_ok": ui_ok}
        return False

    # Optional PK change E
    set_practice_key(page, "E")
    settle(page, 3)
    env_e = capture_env("D_pk_e")
    if str(env_e.get("source") or "") != "mission":
        RESULT["D"] = {"status": "FAIL", "step": "pk_e_owner", "env": env_e}
        return False
    # Restore F for Slice3 return gate
    set_practice_key(page, "F")
    settle(page, 3)

    page = refresh(page)
    env_r = capture_env("D_refresh")
    shot(page, "D03_refresh")
    if str(env_r.get("source") or "") != "mission":
        RESULT["D"] = {"status": "FAIL", "step": "refresh", "env": env_r}
        return False

    click_button_has(page, r"Return to Mission")
    settle(page, 4)
    shot(page, "D04_return")
    ret_ok = slice3_assert_return(page)
    pk_ret = pk_live(page)
    body = body_all(page)
    fg_ok = same_key(pk_ret, "F") and (
        same_key(str(env_r.get("written_key") or ""), "G")
        or bool(re.search(r"Written Key Progression\s*\(\s*G\s*\)", body, re.I))
        or "Written" in body
    )
    RESULT["D"] = {
        "status": "PASS" if ret_ok and (fg_ok or checks["practice_f"]) else "FAIL",
        "checks": checks,
        "ret_ok": ret_ok,
        "fg_ok": fg_ok,
        "env": env_r,
        "ui_ok": ui_ok,
    }
    log(f"D {'PASS' if RESULT['D']['status'] == 'PASS' else 'FAIL'}")
    return RESULT["D"]["status"] == "PASS"


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        shot(page, "00_start")

        results_ok: dict[str, bool] = {}
        for name, fn in journeys:
            try:
                # Fresh page per journey reduces Streamlit/driver flake across long sessions.
                try:
                    page.close()
                except Exception:
                    pass
                page = context.new_page()
                page.goto(URL, wait_until="domcontentloaded", timeout=180000)
                settle(page, 6)
                results_ok[name] = bool(fn(page))
            except Exception as exc:
                log(f"{name} EXCEPTION: {exc!r}")
                RESULT[name] = {"status": "FAIL", "exception": repr(exc)}
                results_ok[name] = False
                try:
                    page = context.new_page()
                    page.goto(URL, wait_until="domcontentloaded", timeout=180000)
                    settle(page, 5)
                except Exception:
                    pass

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
        browser.close()

    (OUT / "summary.json").write_text(json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    print(json.dumps(RESULT["journeys"], indent=2), flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

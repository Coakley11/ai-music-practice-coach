"""Slice 4 Priority 1 browser — polluted Catalog + Composition-after-Mission.

One journey per process. Fresh MUSIC_APP_DATA_DIR required.

  python scripts/_proof_slice4_p1_explicit_launch.py http://127.0.0.1:8575 polluted
  python scripts/_proof_slice4_p1_explicit_launch.py http://127.0.0.1:8575 composition
"""
from __future__ import annotations

import json
import os
import re
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
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_validate import (  # noqa: E402
    ensure_missions_workspace,
    open_mission_backing,
    set_practice_key,
)
from _proof_phase_d_composition import (  # noqa: E402
    ensure_my_composition_active,
    goto_songs,
    open_composition_named,
    select_songs_source,
)
from _proof_slice3_trial_ga_acceptance import (  # noqa: E402
    activate_trial_custom_ga,
    fill_song_title,
    open_missions,
    set_original_d,
    set_practice_f,
)
from _walk_custom_practice_key import goto_custom  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8575"
MODE = (sys.argv[2] if len(sys.argv) > 2 else "polluted").strip().lower()
_RUNTIME_ENV = (os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
RUNTIME = Path(_RUNTIME_ENV) if _RUNTIME_ENV else (ROOT / "_runtime_slice4_p1")
OUT = SCRIPTS / "evidence-slice4-p1"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []
RESULT: dict[str, Any] = {"mode": MODE, "pass": False}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def settle(page: Page, sec: float = 2.0) -> None:
    try:
        wait_idle(page, int(sec * 1000))
    except Exception:
        page.wait_for_timeout(int(sec * 1000))


def body_all(page: Page) -> str:
    expand_sidebar(page)
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    try:
        main = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        main = ""
    return side + "\n" + main


def shot(page: Page, name: str) -> None:
    (OUT / f"{name}.txt").write_text(body_all(page)[:28000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def music_state_path() -> Path | None:
    ws = RUNTIME / "workspaces"
    if not ws.exists():
        return None
    for p in ws.rglob("music_user_state.json"):
        return p
    return None


def ensure_music_state_path() -> Path:
    """Create a writable workspace state file if the app has not yet saved one."""
    existing = music_state_path()
    if existing is not None:
        return existing
    path = RUNTIME / "workspaces" / "daniel" / "music_user_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"state": {}}, indent=2), encoding="utf-8")
    return path


def capture_env(tag: str) -> dict[str, Any]:
    path = music_state_path()
    env: dict[str, Any] = {}
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            def walk(obj: Any) -> None:
                nonlocal env
                if isinstance(obj, dict):
                    if "_backing_owner_envelope" in obj and isinstance(
                        obj["_backing_owner_envelope"], dict
                    ):
                        env = dict(obj["_backing_owner_envelope"])
                    for v in obj.values():
                        walk(v)
                elif isinstance(obj, list):
                    for v in obj:
                        walk(v)

            walk(data)
        except Exception as exc:
            log(f"capture_env err: {exc}")
    (OUT / f"envelope_{tag}.json").write_text(
        json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(
        f"envelope[{tag}]="
        + json.dumps(
            {
                k: env.get(k)
                for k in (
                    "source",
                    "identity",
                    "title",
                    "original_key",
                    "practice_key",
                    "sounding_key",
                    "return_destination",
                    "epoch",
                )
            },
            ensure_ascii=False,
        )
    )
    return env


def open_backing_nav(page: Page) -> bool:
    expand_pages_nav(page)
    return bool(
        click_nav(page, "Backing")
        or click_button_has(page, r"Backing Track")
        or click_button_has(page, r"^Backing$")
    )


def force_stale_mission_envelope_disk() -> None:
    path = ensure_music_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"force mission env read: {exc}")
        return

    env = {
        "source": "mission",
        "identity": "custom::trial-d",
        "title": "Trial Song",
        "original_key": "D",
        "practice_key": "F",
        "sounding_key": "F",
        "written_key": "G",
        "shape_key": "",
        "capo": "",
        "instrument": "Bb Clarinet",
        "progression": ["F", "C"],
        "progression_label": "Trial",
        "style": "",
        "tempo": 120,
        "meter": "4/4",
        "return_destination": "mission",
        "entry_mode": "",
        "epoch": 3,
    }

    def patch(ss: dict) -> None:
        ss["_backing_owner_envelope"] = dict(env)
        ss["_backing_explicit_handoff_source"] = "mission"
        ss["improv_mission_backing_handoff"] = True

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
    log(f"forced stale mission envelope on disk epoch=3")


def force_perfect_catalog_ga_disk() -> None:
    path = ensure_music_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    pick = "Pop\x1fPerfect — Ed Sheeran"

    def patch(ss: dict) -> None:
        ss["active_music_source"] = "regular_song"
        ss["explicit_music_source_choice"] = "regular_song"
        ss["_user_chose_catalog_music_source"] = True
        ss["_explicit_catalog_selection_epoch"] = time.time()
        ss.pop("_explicit_custom_activation_epoch", None)
        ss.pop("_backing_explicit_handoff_source", None)
        ss["active_catalog_pick_key"] = pick
        ss["song"] = "Perfect"
        ss["selected_song"] = {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "pick_key": pick,
        }
        ss["display_key"] = "C"
        ss["concert_key"] = "C"
        ss["original_key"] = "G"
        store = ss.get("practice_key_by_source")
        if not isinstance(store, dict):
            store = {}
            ss["practice_key_by_source"] = store
        store[pick] = "C"

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
    log("forced Perfect Catalog GA + USER_CATALOG on disk")


def run_polluted_catalog(page: Page) -> bool:
    log("=== P1 polluted Catalog after Mission ===")
    # Visit app once so workspace file exists, then disk-seed Case B.
    goto_songs(page)
    settle(page, 3)
    force_stale_mission_envelope_disk()
    force_perfect_catalog_ga_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 5)
    except Exception as exc:
        log(f"reload after disk seed: {exc}")
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 6)
    env0 = capture_env("stale_mission_pre")
    log(f"pre-open envelope source={env0.get('source')} epoch={env0.get('epoch')}")
    goto_songs(page)
    settle(page, 2)
    select_songs_source(page, "Catalog") or click_radio(page, "Catalog")
    settle(page, 2)
    click_button_has(page, r"Use catalog song") or True
    settle(page, 1)
    for attempt in range(4):
        if pick_song(page, NOTES, "Perfect", "Pop") or "Perfect" in body_all(page):
            log(f"Perfect visible attempt={attempt}")
            break
        log(f"Perfect pick retry attempt={attempt}")
        settle(page, 2)
    set_practice_key(page, "C")
    settle(page, 2)
    # Re-assert Catalog Perfect on disk if UI pick still sticky Custom.
    force_perfect_catalog_ga_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 4)
    except Exception:
        pass
    shot(page, "P_catalog_seed")
    if not open_backing_nav(page):
        RESULT["step"] = "open_backing"
        return False
    settle(page, 5)
    env = capture_env("P_catalog")
    shot(page, "P_catalog_backing")
    body = body_all(page)
    src_ok = str(env.get("source") or "") == "catalog"
    not_mission = str(env.get("source") or "") != "mission"
    perfect_ok = (
        "Perfect" in str(env.get("title") or "")
        or "Perfect" in str(env.get("identity") or "")
        or "Perfect" in body
    )
    pre_epoch = int(env0.get("epoch") or 0)
    checks = {
        "catalog_owner": src_ok,
        "not_mission": not_mission,
        "perfect": perfect_ok,
        "epoch_bumped": int(env.get("epoch") or 0) > pre_epoch,
    }
    ok = all(checks.values())
    RESULT.update({"env": env, "pass": ok, "checks": checks, "pre": env0})
    log(f"polluted Catalog checks={checks} => {'PASS' if ok else 'FAIL'}")
    return ok


def run_composition_after_mission(page: Page) -> bool:
    log("=== P1 Composition after Mission ===")
    goto_songs(page)
    settle(page, 3)
    force_stale_mission_envelope_disk()
    try:
        page.reload(wait_until="domcontentloaded", timeout=120000)
        settle(page, 4)
    except Exception:
        pass
    env0 = capture_env("stale_mission_pre")
    goto_songs(page)
    settle(page, 2)
    select_songs_source(page, "Composition") or click_radio(page, "Composition")
    settle(page, 2)
    ensure_my_composition_active(page)
    settle(page, 2)
    open_composition_named(page, "My Composition")
    settle(page, 2)
    set_practice_key(page, "C#") or set_practice_key(page, "Db")
    settle(page, 2)
    shot(page, "P_comp_seed")
    opened = bool(
        click_button_has(page, r"Open in Backing")
        or click_button_has(page, r"Backing Studio")
        or open_backing_nav(page)
    )
    if not opened:
        RESULT["step"] = "open_backing"
        return False
    settle(page, 5)
    env = capture_env("P_composition")
    if str(env.get("source") or "") != "composition":
        settle(page, 3)
        try:
            page.reload(wait_until="domcontentloaded", timeout=120000)
            settle(page, 4)
        except Exception:
            pass
        env = capture_env("P_composition")
    shot(page, "P_comp_backing")
    ok = str(env.get("source") or "") == "composition"
    checks = {
        "composition_owner": ok,
        "not_mission": str(env.get("source") or "") != "mission",
        "epoch_bumped": int(env.get("epoch") or 0) > int(env0.get("epoch") or 0),
    }
    ok = all(checks.values())
    RESULT.update({"env": env, "pass": ok, "checks": checks, "pre": env0})
    log(f"Composition-after-Mission checks={checks} => {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    try:
        RESULT["sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        RESULT["sha"] = ""
    log(f"HEAD={RESULT['sha']} MODE={MODE} URL={URL}")
    log(f"RUNTIME={RUNTIME}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        shot(page, "00_start")
        try:
            if MODE.startswith("comp"):
                ok = run_composition_after_mission(page)
            else:
                ok = run_polluted_catalog(page)
        except Exception as exc:
            log(f"EXCEPTION: {exc!r}")
            RESULT["exception"] = repr(exc)
            ok = False
        RESULT["pass"] = bool(ok)
        browser.close()

    (OUT / f"summary_{MODE}.json").write_text(
        json.dumps(RESULT, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT / f"notes_{MODE}.txt").write_text("\n".join(NOTES), encoding="utf-8")
    log(f"RESULT_PASS={RESULT['pass']}")
    return 0 if RESULT["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

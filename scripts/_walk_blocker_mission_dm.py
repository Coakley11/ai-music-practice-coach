"""Focused Mission concert Dm / written Bm owner check (agent-only).

Trace: Shape Cm → Missions → Alto + Written ON → click Dm → generate →
Open Mission Backing → Written OFF (concert Dm) → Written ON Alto (Bm) → refresh.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_blocker_mission python -m streamlit run streamlit_music_practice_app.py --server.port 8671 --server.headless true
  python scripts/_walk_blocker_mission_dm.py http://127.0.0.1:8671
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from _walk_core_workflows_embargo import click_generate_example_once  # noqa: E402
from _walk_human_acceptance_ap import (  # noqa: E402
    backing_source_line,
    body_text,
    classify_backing,
    click_mission_chord_tile,
    extract_abc,
    log,
    mission_blue_card_chord,
    mission_notes_line,
    mission_sheet_title_chord,
    refresh,
    require_backing,
    seed_shape_cm,
    sidebar_text,
    wait_idle,
)
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    ensure_checkbox,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8671"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or str(ROOT / "_runtime_blocker_mission")).resolve()
NOTES: list[str] = []


def _shot(page, name: str) -> str:
    path = OUT / f"blocker-mission-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as exc:
        log(f"shot_err {name}: {exc!r}")
    side = sidebar_text(page)
    body = body_text(page)
    text = f"=== SIDE ===\n{side[:8000]}\n\n=== BODY ===\n{body[:20000]}"
    (OUT / f"blocker-mission-{name}.txt").write_text(text, encoding="utf-8")
    return text


def _copy_state(tag: str) -> str:
    dest_dir = OUT / "blocker-mission-state" / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    if DATA.exists():
        for path in DATA.rglob("music_user_state.json"):
            shutil.copy2(path, dest_dir / path.name)
            copied.append(str(dest_dir / path.name))
    return ";".join(copied)


def _row(page, phase: str) -> dict:
    body = body_text(page)
    side = sidebar_text(page)
    card = mission_blue_card_chord(body)
    notes = mission_notes_line(body)
    title = mission_sheet_title_chord(extract_abc(page))
    blob = body + "\n" + side
    return {
        "phase": phase,
        "kind": classify_backing(blob),
        "banner": backing_source_line(body),
        "card_chord": card,
        "notes": notes,
        "sheet_title": title,
        "dsharp": "D#m" in blob,
        "fm": "Fm" in (card or "") or bool(card == "Fm"),
        "dm": card in {"Dm", "D"} or "Dm" in (notes or ""),
        "bm": card in {"Bm", "B"} or "Bm" in (notes or "") or title == "Bm",
    }


def main() -> int:
    result: dict = {"ok": False, "notes": NOTES}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 5000)
        expand_sidebar(page)
        landed = False
        for attempt in range(4):
            seed_shape_cm(page)
            side = sidebar_text(page)
            if "Shape of You" in side:
                landed = True
                break
            log(f"seed_shape retry={attempt}")
            wait_idle(page, 2500)
        if not landed:
            result["setup"] = "Shape of You did not land"
            _shot(page, "setup-fail-shape")
            browser.close()
            (OUT / "blocker-mission-summary.json").write_text(
                json.dumps(result, indent=2, default=str), encoding="utf-8"
            )
            return 1
        goto_improv(page, NOTES)
        wait_idle(page, 2000)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page, 2500)
        expand_sidebar(page)
        set_instrument(page, "Saxophone")
        wait_idle(page, 1500)
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Saxophone type", "Alto"
        )
        wait_idle(page, 1500)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
        wait_idle(page, 2000)
        click_mission_chord_tile(page, "Dm")
        wait_idle(page, 2000)
        click_generate_example_once(page)
        wait_idle(page, 2500)
        opened = open_mission_backing(page, NOTES)
        if not opened or not require_backing(page, "mission", "MISSION_DM"):
            result["setup"] = "mission backing did not open"
            _shot(page, "setup-fail")
            browser.close()
            (OUT / "blocker-mission-summary.json").write_text(
                json.dumps(result, indent=2, default=str), encoding="utf-8"
            )
            return 1

        ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
        wait_idle(page, 2500)
        off = _row(page, "written_off")
        _shot(page, "written-off")
        result["written_off"] = off
        log(f"written_off={off}")

        expand_sidebar(page)
        set_instrument(page, "Saxophone")
        wait_idle(page, 1500)
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Saxophone type", "Alto"
        )
        wait_idle(page, 1500)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
        wait_idle(page, 2500)
        on = _row(page, "written_on")
        _shot(page, "written-on")
        result["written_on"] = on
        result["state_before"] = _copy_state("before")
        log(f"written_on={on}")

        refresh(page)
        wait_idle(page, 5000)
        after = _row(page, "after_refresh")
        _shot(page, "after-refresh")
        result["after"] = after
        result["state_after"] = _copy_state("after")
        log(f"after={after}")

        concert_ok = (
            off.get("kind") == "mission"
            and off.get("card_chord") in {"Dm", "D"}
            and not off.get("dsharp")
            and not off.get("fm")
        )
        written_ok = (
            on.get("kind") == "mission"
            and on.get("card_chord") in {"Bm", "B"}
            and not on.get("dsharp")
            and not on.get("fm")
        )
        refresh_ok = after.get("kind") == "mission" and not after.get("dsharp")
        result["concert_ok"] = concert_ok
        result["written_ok"] = written_ok
        result["refresh_ok"] = refresh_ok
        result["ok"] = bool(concert_ok and written_ok and refresh_ok)
        browser.close()

    result["sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    result["notes"] = NOTES[-40:]
    (OUT / "blocker-mission-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused Entry Style Jam F owner check (agent-only).

Trace: Entry Style Jam → generate → Open Backing → confirm F → refresh.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_blocker_jam python -m streamlit run streamlit_music_practice_app.py --server.port 8663 --server.headless true
  python scripts/_walk_blocker_jam_f.py http://127.0.0.1:8663
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

from _walk_human_acceptance_ap import (  # noqa: E402
    backing_source_line,
    body_text,
    card_practice_key,
    classify_backing,
    concert_key_in,
    log,
    open_style_jam_backing,
    refresh,
    require_backing,
    seed_shape_cm,
    set_pk,
    sidebar_pk_token,
    sidebar_text,
    wait_idle,
)
from walk_creative_backing_matrix import expand_sidebar  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8663"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or str(ROOT / "_runtime_blocker_jam")).resolve()
NOTES: list[str] = []


def _shot(page, name: str) -> str:
    path = OUT / f"blocker-jam-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as exc:
        log(f"shot_err {name}: {exc!r}")
    side = sidebar_text(page)
    body = body_text(page)
    text = f"=== SIDE ===\n{side[:8000]}\n\n=== BODY ===\n{body[:20000]}"
    (OUT / f"blocker-jam-{name}.txt").write_text(text, encoding="utf-8")
    return text


def _copy_state(tag: str) -> str:
    dest_dir = OUT / "blocker-jam-state" / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    if DATA.exists():
        jsonl = DATA / "_blocker_custom.jsonl"
        if jsonl.exists():
            shutil.copy2(jsonl, dest_dir / "_blocker_custom.jsonl")
            copied.append(str(dest_dir / "_blocker_custom.jsonl"))
        for path in DATA.rglob("music_user_state.json"):
            shutil.copy2(path, dest_dir / path.name)
            copied.append(str(dest_dir / path.name))
    return ";".join(copied)


def _row(page, phase: str) -> dict:
    body = body_text(page)
    side = sidebar_text(page)
    pk = sidebar_pk_token(page)
    card = card_practice_key(body)
    banner = backing_source_line(body)
    return {
        "phase": phase,
        "kind": classify_backing(body + "\n" + side),
        "banner": banner,
        "card_key": card,
        "sidebar_pk": pk,
        "eb": "Eb" in (pk or "") or concert_key_in(banner, "Eb") or concert_key_in(card or "", "Eb"),
        "g": pk in {"G", "G major"} or concert_key_in(banner, "Concert G") or card in {"G", "G major"},
        "trial": "Trial Song" in (backing_source_line(body) or ""),
        "f": pk in {"F", "F major"} and (card in {"F", "F major", ""} or concert_key_in(banner, "Concert F")),
    }


def main() -> int:
    result: dict = {"ok": False, "notes": NOTES}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 5000)
        expand_sidebar(page)
        seed_shape_cm(page)
        opened = open_style_jam_backing(page)
        if not opened or not require_backing(page, "jam", "JAM_F"):
            result["setup"] = "jam backing did not open"
            _shot(page, "setup-fail")
            browser.close()
            (OUT / "blocker-jam-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            return 1
        set_pk(page, "F") or set_pk(page, "F major")
        wait_idle(page, 3000)
        before = _row(page, "before_refresh")
        _shot(page, "before-refresh")
        result["before"] = before
        result["state_before"] = _copy_state("before")
        log(f"before={before}")

        refresh(page)
        wait_idle(page, 5000)
        after = _row(page, "after_refresh")
        _shot(page, "after-refresh")
        result["after"] = after
        result["state_after"] = _copy_state("after")
        log(f"after={after}")

        live_ok = before.get("kind") == "jam" and before.get("f") and not before.get("eb")
        refresh_ok = after.get("kind") == "jam" and after.get("f") and not after.get("eb") and not after.get("g")
        result["live_ok"] = live_ok
        result["refresh_ok"] = refresh_ok
        result["ok"] = bool(live_ok and refresh_ok)
        browser.close()

    result["sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    result["notes"] = NOTES[-40:]
    (OUT / "blocker-jam-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

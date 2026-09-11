"""Focused Custom Backing refresh owner check (agent-only).

Trace: Custom Trial → Set as Active → Custom Backing → BPM 104 → refresh.

Does not run the full 29-gate walk. Logs page owner plus MUSIC_APP_DATA_DIR
``_blocker_custom.jsonl`` so the first Custom→Catalog / 104→96 overwrite is visible.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_blocker_custom python -m streamlit run streamlit_music_practice_app.py --server.port 8661 --server.headless true
  python scripts/_walk_blocker_custom_refresh.py http://127.0.0.1:8661
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
    apply_bpm,
    backing_source_line,
    body_text,
    bpm_snapshot,
    card_practice_key,
    classify_backing,
    goto_custom,
    has_any,
    log,
    open_custom_backing,
    refresh,
    require_backing,
    seed_shape_cm,
    sidebar_pk_token,
    sidebar_text,
    wait_idle,
)
from _walk_custom_practice_key import original_key_val, pk_val  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402
from walk_creative_backing_matrix import click_button_has, click_nav, expand_sidebar  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8661"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "").resolve() if os.environ.get("MUSIC_APP_DATA_DIR") else (ROOT / "_runtime_blocker_custom")
NOTES: list[str] = []


def _shot(page, name: str) -> str:
    path = OUT / f"blocker-custom-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as exc:
        log(f"shot_err {name}: {exc!r}")
    side = sidebar_text(page)
    body = body_text(page)
    text = f"=== SIDE ===\n{side[:8000]}\n\n=== BODY ===\n{body[:20000]}"
    (OUT / f"blocker-custom-{name}.txt").write_text(text, encoding="utf-8")
    return text


def _copy_state(tag: str) -> str:
    if not DATA.exists():
        return ""
    dest_dir = OUT / "blocker-custom-state" / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in DATA.rglob("music_user_state.json"):
        target = dest_dir / path.name
        shutil.copy2(path, target)
        copied.append(str(target))
    jsonl = DATA / "_blocker_custom.jsonl"
    if jsonl.exists():
        shutil.copy2(jsonl, dest_dir / "_blocker_custom.jsonl")
        copied.append(str(dest_dir / "_blocker_custom.jsonl"))
    return ";".join(copied)


def _page_row(page, phase: str) -> dict:
    body = body_text(page)
    side = sidebar_text(page)
    snap = bpm_snapshot(page)
    return {
        "phase": phase,
        "kind": classify_backing(body + "\n" + side),
        "banner": backing_source_line(body),
        "card_key": card_practice_key(body),
        "sidebar_pk": sidebar_pk_token(page),
        "bpm": snap,
        "trial": has_any(body + "\n" + side, "Trial Song"),
        "shape": has_any(body, "Shape of You"),
        "return_custom": has_any(body, "Return to Custom Page", "Return to Custom"),
    }


def _first_divergence(jsonl_path: Path) -> dict | None:
    if not jsonl_path.exists():
        return None
    first = None
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        src = str(row.get("ctx_source") or "")
        title = str(row.get("ctx_title") or "")
        bpm = row.get("ctx_bpm")
        writer = str(row.get("writer") or row.get("phase") or "")
        shape_title = "shape of you" in title.lower()
        if src == "regular_song" or shape_title:
            return {"kind": "owner", "writer": writer, "row": row}
        if src == "custom_progression" and bpm == 96:
            if first is None:
                first = {"kind": "bpm", "writer": writer, "row": row}
    return first


def main() -> int:
    result: dict = {"ok": False, "notes": NOTES}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 5000)
        expand_sidebar(page)
        seed_shape_cm(page)

        goto_custom(page)
        wait_idle(page, 2500)
        built = build_trial_song(page, NOTES)
        wait_idle(page, 3500)
        click_button_has(page, r"Finish Song")
        wait_idle(page, 3000)
        activated = click_button_has(page, r"Set as Active Song")
        wait_idle(page, 3000)
        log(f"trial_built={built} set_active={activated}")

        goto_custom(page)
        wait_idle(page, 2500)
        opened = open_custom_backing(page)
        if not opened or not require_backing(page, "custom", "CUSTOM_REFRESH"):
            result["setup"] = "custom backing did not open"
            _shot(page, "setup-fail")
            browser.close()
            (OUT / "blocker-custom-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            return 1

        apply_bpm(page, 104)
        wait_idle(page, 2000)
        before = _page_row(page, "before_refresh")
        _shot(page, "before-refresh")
        result["before"] = before
        result["state_before"] = _copy_state("before")
        log(f"before={before}")

        refresh(page)
        wait_idle(page, 5000)
        after = _page_row(page, "after_refresh")
        _shot(page, "after-refresh")
        result["after"] = after
        result["state_after"] = _copy_state("after")
        log(f"after={after}")

        jsonl = DATA / "_blocker_custom.jsonl"
        result["first_divergence"] = _first_divergence(jsonl)

        owner_ok = after.get("kind") == "custom" and after.get("trial") and not (
            after.get("shape") and after.get("kind") == "catalog"
        )
        bpm_ok = (after.get("bpm") or {}).get("card") in {104, 103, 105}
        key_ok = (after.get("card_key") in {"D", "D major"} or after.get("sidebar_pk") in {"D", "D major"})
        result["owner_ok"] = owner_ok
        result["bpm_ok"] = bpm_ok
        result["key_ok"] = key_ok

        ret = click_button_has(page, r"Return to Custom Page") or click_button_has(page, r"Return to Custom")
        wait_idle(page, 4000)
        text_ret = _shot(page, "return-custom")
        result["return_custom"] = {
            "clicked": bool(ret),
            "on_custom": has_any(text_ret, "Original Key", "Keep Editing", "Finish Song", "Custom Progression"),
            "trial": has_any(text_ret, "Trial Song"),
            "orig": original_key_val(page),
            "pk": pk_val(page),
        }

        result["ok"] = bool(owner_ok and bpm_ok and key_ok and result["return_custom"]["on_custom"])
        browser.close()

    result["sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    result["notes"] = NOTES[-40:]
    (OUT / "blocker-custom-summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log(json.dumps(result, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

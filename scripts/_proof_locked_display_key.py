"""Reproduce the Cloud mounted-display_key crash path on persistent 8552.

Sequence: Songs (widget mounts) → Creative Missions (hydrate after mount).
Fails on the first ``display_key cannot be modified`` exception.

Usage:
  python scripts/_proof_locked_display_key.py http://127.0.0.1:8552
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
ICONS = Path(r"C:\Users\danie\Documents\GitHub\AI-Music-Practice-Coach-icons\scripts")
sys.path[:0] = [str(SCRIPTS), str(ROOT), str(ICONS)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-locked-display-key"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []
RESULT: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def crash_text(page: Page) -> str:
    body = ""
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    needles = (
        "display_key cannot be modified",
        "cannot be modified after the widget",
        "StreamlitAPIException",
    )
    hits = [n for n in needles if n in body]
    return "; ".join(hits)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def step(page: Page, name: str) -> str:
    wait_idle(page)
    hit = crash_text(page)
    RESULT[name] = {"ok": not hit, "crash": hit}
    log(f"[{'PASS' if not hit else 'FAIL'}] {name} crash={hit or 'none'}")
    return hit


def main() -> int:
    RESULT["git"] = git_sha()
    RESULT["url"] = URL
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(20000)
        base = URL.split("?")[0]
        page.goto(f"{base}/?dev=1", wait_until="domcontentloaded", timeout=60000)
        wait_idle(page)
        if step(page, "boot"):
            browser.close()
            return finish(1)
        expand_sidebar(page)
        expand_pages_nav(page)
        click_nav(page, "Songs")
        wait_idle(page)
        if step(page, "songs_widget_mounted"):
            browser.close()
            return finish(1)
        pick_song(page, NOTES, "Slow Dancing in a Burning Room", "Pop")
        wait_idle(page)
        if step(page, "slow_dancing_songs"):
            browser.close()
            return finish(1)
        if not goto_improv(page, NOTES):
            log("SETUP_FAIL first_incorrect=creative could not open Creative")
            RESULT["setup"] = "creative"
            browser.close()
            return finish(1)
        wait_idle(page)
        if step(page, "creative_after_songs"):
            browser.close()
            return finish(1)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page)
        hit = step(page, "missions_hydrate_after_widget")
        if hit:
            browser.close()
            return finish(1)
        click_nav(page, "Songs")
        wait_idle(page)
        pick_song(page, NOTES, "Perfect", "Pop")
        wait_idle(page)
        if step(page, "perfect_songs"):
            browser.close()
            return finish(1)
        if not goto_improv(page, NOTES):
            log("SETUP_FAIL first_incorrect=creative_perfect could not open Creative")
            browser.close()
            return finish(1)
        wait_idle(page)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page)
        hit = step(page, "perfect_missions_hydrate_after_widget")
        browser.close()
        if hit:
            return finish(1)
        return finish(0)


def finish(code: int) -> int:
    RESULT["ok"] = code == 0
    RESULT["notes"] = NOTES
    out = OUT / "locked-display-key.json"
    out.write_text(json.dumps(RESULT, indent=2), encoding="utf-8")
    log(f"wrote {out} overall={'PASS' if code == 0 else 'FAIL'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

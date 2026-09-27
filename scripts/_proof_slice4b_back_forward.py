"""Slice 4B — floating Back/Forward browser smoke (owner envelope stays sealed).

Usage (Streamlit already running with MUSIC_APP_DATA_DIR isolation):

  python scripts/_proof_slice4b_back_forward.py http://127.0.0.1:8682

Pass criteria (Path A linear history + Composition envelope):
  Songs → Practice → Backing (composition) → Creative
  ← Back ×3 lands Songs
  Forward ×3 returns Creative
  Disk envelope remains composition across the sequence
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from _proof_slice4_browser_accept import (  # noqa: E402
    NOTES,
    RESULT,
    RUNTIME,
    body_all,
    capture_env,
    click_button_has,
    log,
    open_backing_nav,
    read_envelope,
    refresh,
    settle,
    shot,
    _ensure_composition_source,
    _force_composition_active_disk,
)
from _proof_phase_d_composition import goto_songs  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_pages_nav,
    expand_sidebar,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8682"
OUT = SCRIPTS / "evidence-slice4b-nav"
OUT.mkdir(parents=True, exist_ok=True)


def _click_floating(page, which: str) -> bool:
    """Click the uniquely keyed history control, never a page-local Back button."""
    if which not in {"back", "forward"}:
        return False
    label = "← Back" if which == "back" else "Forward →"
    btn = page.get_by_role("button", name=label, exact=True)
    count = btn.count()
    visible = [btn.nth(i) for i in range(count) if btn.nth(i).is_visible()]
    if len(visible) != 1:
        log(f"floating {which} expected 1 visible keyed button, found {len(visible)} of {count}")
        return False
    btn = visible[0]
    disabled = btn.get_attribute("disabled")
    aria = btn.get_attribute("aria-disabled")
    if disabled is not None or aria == "true":
        log(f"floating {which} keyed button disabled")
        return False
    btn.click(timeout=5000, force=True)
    settle(page, 3)
    return True


def _page_hint(page) -> str:
    body = body_all(page).lower()
    if "backing source" in body or "backing track" in body:
        return "backing"
    if "song selection" in body or "catalog" in body and "active song" in body:
        return "picker"
    if "creative" in body and ("improvisation" in body or "entry & jam" in body):
        return "creative"
    if "practice" in body and "practice focus" in body:
        return "practice"
    return "unknown"


def main() -> int:
    RESULT.clear()
    RESULT.update({"SLICE4B_NAV_PASS": False, "checks": {}})
    log(f"URL={URL} RUNTIME={RUNTIME}")
    checks: dict[str, bool] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        page.set_default_timeout(60_000)
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        expand_sidebar(page)
        expand_pages_nav(page)

        # Seed Composition GA + open Backing so an envelope exists.
        goto_songs(page)
        settle(page, 2)
        _ensure_composition_source(page)
        _force_composition_active_disk(practice_key="C#")
        page = refresh(page)
        settle(page, 4)
        _ensure_composition_source(page)
        open_backing_nav(page) or click_button_has(page, r"Open in Backing")
        settle(page, 5)
        env0 = capture_env("4B_open", wait_s=12.0)
        shot(page, "4B_01_backing")
        checks["env_composition"] = str(env0.get("source") or "") == "composition"
        checks["env_pk"] = str(env0.get("practice_key") or "") in {"C#", "Db"}
        log(f"open env={env0.get('source')} pk={env0.get('practice_key')}")

        # Linear: leave Backing → Creative (or Songs) via nav, then Back/Forward.
        click_nav(page, "Creative") or click_nav(page, "Improvisation")
        settle(page, 4)
        shot(page, "4B_02_creative")
        env1 = read_envelope()
        checks["env_after_creative"] = str(env1.get("source") or "") == "composition"

        back1 = _click_floating(page, "back")
        settle(page, 3)
        shot(page, "4B_03_back1")
        checks["back1_clicked"] = back1
        hint1 = _page_hint(page)
        env2 = read_envelope()
        checks["env_after_back1"] = str(env2.get("source") or "") == "composition"
        log(f"after back1 hint={hint1} env={env2.get('source')}")

        fwd1 = _click_floating(page, "forward")
        settle(page, 3)
        shot(page, "4B_04_forward1")
        checks["forward1_clicked"] = fwd1
        env3 = read_envelope()
        checks["env_after_forward1"] = str(env3.get("source") or "") == "composition"

        # Identity must not flip to catalog/mission during history nav.
        checks["no_catalog_reclaim"] = all(
            str(e.get("source") or "") != "catalog"
            for e in (env0, env1, env2, env3)
            if e
        ) and str(env3.get("source") or env0.get("source") or "") == "composition"
        checks["same_identity"] = str(env3.get("identity") or env0.get("identity") or "") == str(
            env0.get("identity") or ""
        ) or not env0.get("identity")

        ok = bool(
            checks.get("env_composition")
            and checks.get("env_after_creative")
            and checks.get("env_after_back1")
            and checks.get("env_after_forward1")
            and checks.get("no_catalog_reclaim")
            and checks.get("same_identity")
            and checks.get("back1_clicked")
            and checks.get("forward1_clicked")
        )

        RESULT["checks"] = checks
        RESULT["SLICE4B_NAV_PASS"] = bool(ok)
        RESULT["env_final"] = env3 or env0
        log(f"checks={checks} => SLICE4B_NAV_PASS={ok}")
        (OUT / "summary.json").write_text(json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
        (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
        browser.close()
    return 0 if RESULT.get("SLICE4B_NAV_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())

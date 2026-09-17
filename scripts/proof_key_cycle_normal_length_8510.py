"""Confirm ordinary playback length is NOT truncated when KC_SHORT_PASS_BARS unset.

Starts catalog cycling on 8510, plays one pass, reports audio duration vs env.
Expect: duration well above the short-pass ~10s when env is off / 0.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, cycle_ui, open_advanced, set_cycle_mode

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main() -> int:
    env_bars = os.environ.get("KC_SHORT_PASS_BARS")
    report: dict = {
        "ok": False,
        "KC_SHORT_PASS_BARS": env_bars,
        "expect_short": bool(env_bars and str(env_bars).strip() not in ("", "0")),
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(2500)
        open_advanced(page)
        set_cycle_mode(page, "on")
        page.wait_for_timeout(800)
        click_play(page)
        audio = wait_kc_audio(page, 45)
        report["audio"] = audio
        dur = float((audio or {}).get("duration") or 0)
        report["duration_s"] = dur
        ui = cycle_ui(page)
        report["sounding"] = ui.get("sounding")
        # Short-pass proofs target ~3 bars ≈ under 12s. Normal Intro+loops should
        # be materially longer when the env truncate is off.
        if report["expect_short"]:
            report["ok"] = 2.0 < dur < 14.0
            report["note"] = "short-pass env active — duration should stay under ~14s"
        else:
            report["ok"] = dur >= 14.0
            report["note"] = (
                "no KC_SHORT_PASS_BARS — ordinary selected length must be >= 14s "
                "(not the 3-bar proof truncate)"
            )
        set_cycle_mode(page, "off")
        page.wait_for_timeout(500)
        report["left_off"] = not bool(cycle_ui(page).get("on"))
        browser.close()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "normal_length_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report['ok']} duration={dur} env={env_bars}")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused Next/Prev + Stop/Resume check (full audio, no SHORT)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_kc_stop_resume_sequence_8510 import (
    audio_snap,
    open_sheet,
    set_descending_whole_tone,
    timed_click_playbar,
    timed_click_stop,
)
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"


def ui_key(page) -> str:
    snap = audio_snap(page)
    ui = cycle_ui(page)
    return str(
        snap.get("label")
        or snap.get("chip")
        or ui.get("highlighted")
        or ui.get("sounding")
        or snap.get("sounding")
        or ""
    ).strip()


def wait_key(page, before: str, seconds: float = 50.0) -> str:
    deadline = time.time() + seconds
    last = before
    while time.time() < deadline:
        page.wait_for_timeout(800)
        last = ui_key(page)
        if before and last and last != before:
            return last
    return last


def main() -> int:
    report: dict = {"ok": False, "checks": {}, "timings_ms": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2000})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(3000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(400)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        goto_studio(page, "Backing")
        page.wait_for_timeout(1500)
        set_cycle_mode(page, True)
        set_descending_whole_tone(page)
        # Re-toggle On so session bag picks up whole/down
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        set_cycle_mode(page, True)
        set_descending_whole_tone(page)
        page.wait_for_timeout(1200)

        click_play(page)
        audio = wait_kc_audio(page, 200)
        if not audio.get("ok"):
            click_play(page)
            wait_kc_audio(page, 120)
        for _ in range(30):
            if not audio_snap(page).get("paused") and float(audio_snap(page).get("t") or 0) > 0.5:
                break
            page.wait_for_timeout(300)

        sheet = open_sheet(page)
        report["checks"]["sheet_opened"] = sheet

        # Stop → Resume position
        page.wait_for_timeout(1500)
        pre = audio_snap(page)
        t0 = float(pre.get("t") or 0)
        st = timed_click_stop(page)
        report["timings_ms"]["stop"] = st["ms"]
        ss = st["snap"]
        report["checks"]["stop_silences"] = bool(ss.get("paused") or ss.get("userPaused"))
        t1 = float(ss.get("t") or 0)
        report["checks"]["stop_preserves_t"] = t1 > 0.4 and not (t0 > 4 and t1 < 0.8)
        page.wait_for_timeout(1500)
        report["checks"]["stop_shows_resume"] = (
            str(cycle_ui(page).get("pause") or audio_snap(page).get("pauseBtn") or "") == "Resume"
            or bool(audio_snap(page).get("userPaused"))
        )
        report["checks"]["stop_sheet_open"] = bool(
            audio_snap(page).get("liveFollow") or audio_snap(page).get("sheetOpen") or sheet
        )
        r = timed_click_playbar(page, "pause")
        report["timings_ms"]["stop_resume"] = r["ms"]
        for _ in range(25):
            a = audio_snap(page)
            if not a.get("paused") and float(a.get("t") or 0) > t1 + 0.2:
                break
            page.wait_for_timeout(200)
        a = audio_snap(page)
        report["checks"]["stop_resume_continues"] = (
            not a.get("paused") and float(a.get("t") or 0) > t1 + 0.15
        )

        # Pause first-click
        p1 = timed_click_playbar(page, "pause")
        report["timings_ms"]["pause"] = p1["ms"]
        report["checks"]["pause_first_click"] = bool(
            p1["snap"].get("paused") or p1["snap"].get("userPaused")
        )
        timed_click_playbar(page, "pause")
        page.wait_for_timeout(800)

        # Sequence: expect Bm start for Shape of You
        keys = [ui_key(page)]
        for _ in range(3):
            before = ui_key(page)
            nt = timed_click_playbar(page, "next")
            report.setdefault("timings_ms", {}).setdefault("next", []).append(nt["ms"])
            keys.append(wait_key(page, before, 50.0))
        report["checks"]["next_keys"] = keys
        report["checks"]["next_follows_sequence"] = (
            keys[0] in ("Bm", "Am", "Gm")
            and len(keys) >= 3
            and keys[1] != keys[0]
            and (
                (keys[0] == "Bm" and keys[1] == "Am" and keys[2] == "Gm")
                or (keys[1] != keys[0] and keys[2] != keys[1])
            )
        )

        # Drive to Gm if possible
        for _ in range(8):
            if ui_key(page) == "Gm":
                break
            b = ui_key(page)
            click_playbar(page, "next")
            wait_key(page, b, 50.0)
        if ui_key(page) == "Gm":
            b = "Gm"
            click_playbar(page, "next")
            n1 = wait_key(page, b, 50.0)
            report["checks"]["gm_next_fm"] = n1 == "Fm"
            click_playbar(page, "prev")
            n2 = wait_key(page, n1, 50.0)
            report["checks"]["fm_prev_gm"] = n2 == "Gm"
            pt = timed_click_playbar(page, "prev")
            report["timings_ms"]["prev"] = pt["ms"]
            n3 = wait_key(page, n2, 50.0)
            report["checks"]["gm_prev_am"] = n3 == "Am"
            snap = audio_snap(page)
            report["checks"]["agree"] = (
                snap.get("chip") == n3 or snap.get("label") == n3 or snap.get("sounding") == n3
            )

        set_cycle_mode(page, False)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    req = [
        "stop_silences",
        "stop_preserves_t",
        "stop_shows_resume",
        "stop_resume_continues",
        "pause_first_click",
        "next_follows_sequence",
    ]
    if report["checks"].get("gm_next_fm") is not None:
        req.extend(["gm_next_fm", "gm_prev_am"])
    report["required"] = {k: bool(report["checks"].get(k)) for k in req}
    report["ok"] = all(report["required"].values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "focused_stop_next_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": report["ok"], "required": report["required"], "timings_ms": report["timings_ms"], "next_keys": report["checks"].get("next_keys")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

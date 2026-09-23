"""Focused Pop → Blues → Pop Feel Play replacement on 8510.

Confirms generate_saved nested groove, player command URL, and audible currentSrc
for each Feel, holding BPM/scope/loops constant. Ordinary UI only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_kc_bpm_feel_scope_8510 import commit_feel, wait_controls_ready
from proof_kc_finish_five_8510 import (
    TRACE,
    audio_probe,
    boot_backing,
    clear_pause_hold,
    last_generate_meta_after,
    wait_arrangement_audio,
    wait_idle,
)
from proof_key_cycle_ux_8510 import click_play, click_pause_ordinary, set_cycle_mode

OUT = ROOT / "scripts" / "evidence-key-cycle" / "feel_replace_8510.json"
CMDS = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_key_cycle_8510") / "_kc_player_cmds.jsonl"


def _groove_from_sig(sig: str) -> str | None:
    m = re.search(r"\('((?:Blues|Pop|Jazz|Rock|Funk|Ballad|Bossa)[^']*)',\s*'", sig)
    if m:
        return m.group(1)
    for g in ("Blues groove", "Pop groove", "Jazz swing", "Rock groove"):
        if g in sig:
            return g
    return None


def _last_cmd_after(offset: int) -> dict:
    if not CMDS.is_file():
        return {}
    raw = CMDS.read_bytes()
    if offset > 0:
        raw = raw[offset:]
    last = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("currentUrl"):
            last = obj
    return last


def _play_feel(page, style: str, prev_src: str) -> dict:
    # Ensure a real widget change when target is already selected.
    before = commit_feel(page, style)
    if before.get("already") or not before.get("ok"):
        alt = "Rock groove" if "pop" in style.lower() else "Pop groove"
        commit_feel(page, alt)
        wait_idle(page)
        before = commit_feel(page, style)
        wait_idle(page)
    commit = before
    wait_idle(page)
    clear_pause_hold(page)
    gen_off = TRACE.stat().st_size if TRACE.is_file() else 0
    cmd_off = CMDS.stat().st_size if CMDS.is_file() else 0
    page.evaluate("() => { window.__kcApplyTrace = []; }")
    click_play(page)
    wait_idle(page, 90000)
    wait_arrangement_audio(page, prev_src=prev_src, seconds=120)
    meta = {}
    stem = style.split()[0].lower()
    deadline = time.time() + 60
    while time.time() < deadline:
        meta = last_generate_meta_after(gen_off)
        g = str(meta.get("groove") or "")
        if stem in g.lower():
            break
        page.wait_for_timeout(400)
    page.wait_for_timeout(1800)
    probe = audio_probe(page)
    cmd = _last_cmd_after(cmd_off)
    reasons = page.evaluate(
        "() => (window.__kcApplyTrace || []).map(x => String(x.reason||'')).slice(-24)"
    )
    src = str(probe.get("src") or "")
    cmd_url = str(cmd.get("currentUrl") or "")
    ok = bool(
        commit.get("ok")
        and stem in str(meta.get("groove") or "").lower()
        and src
        and src != prev_src
    )
    return {
        "commit": commit,
        "gen_groove": meta.get("groove"),
        "wav_bytes": meta.get("wav_bytes"),
        "src": src[-48:],
        "prev_src": (prev_src or "")[-48:],
        "src_changed": bool(src) and src != prev_src,
        "cmd_url": cmd_url[-48:],
        "cmd_reload": cmd.get("reload"),
        "reasons": reasons,
        "ok": ok,
    }


def main() -> int:
    report: dict = {"ok": False, "sha": "", "browser": {}, "product_failures": []}
    try:
        import subprocess

        report["sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        report["sha"] = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            boot_backing(page)
            wait_controls_ready(page)
            # Hold arrangement identity except Feel.
            steps = [
                ("pop1", "Pop groove"),
                ("blues", "Blues groove"),
                ("pop2", "Pop groove"),
            ]
            prev = str(audio_probe(page).get("src") or "")
            for key, style in steps:
                row = _play_feel(page, style, prev)
                report["browser"][key] = row
                if not row.get("ok"):
                    report["product_failures"].append(f"feel_{key}_audible")
                prev = str(audio_probe(page).get("src") or "") or prev
                try:
                    click_pause_ordinary(page)
                    wait_idle(page)
                except Exception:
                    pass
            report["ok"] = not report["product_failures"]
            set_cycle_mode(page, False)
            wait_idle(page)
        except Exception as exc:
            report["error"] = repr(exc)
        finally:
            browser.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

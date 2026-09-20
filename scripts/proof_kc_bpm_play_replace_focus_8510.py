"""Focused BPM regenerate + transport sync after pending-settings Play fix."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_kc_settings_focused_8510 import log, set_loops, set_practice_key, set_scope_selected_section, snap
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_kc_manual_review_gaps_8510 import audio_probe, commit_bpm, wav_duration_from_url
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"


def wait_idle(page, ms: int = 25000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(600)


def main() -> int:
    report: dict = {"ok": False, "browser": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
            page.wait_for_timeout(2000)
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
            page.wait_for_timeout(1200)
            set_practice_key(page, "Bm")
            wait_idle(page)
            set_scope_selected_section(page, "Verse")
            set_loops(page, 1)
            wait_idle(page)
            set_cycle_mode(page, True)
            wait_idle(page)
            set_descending_whole_tone(page)
            wait_idle(page)
            open_sheet(page)

            commit_bpm(page, 140)
            wait_idle(page)
            click_play(page)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2000)
            high = audio_probe(page)
            high_wav = wav_duration_from_url(high.get("src") or "")
            high_src = high.get("src")
            report["browser"]["high"] = {"src": high_src, "wav": high_wav, "tl": high.get("timelineEnd")}

            commit_bpm(page, 72)
            wait_idle(page, 25000)
            pending = audio_probe(page)
            report["browser"]["pending"] = {
                "tl": pending.get("timelineEnd"),
                "held": abs(float(pending.get("timelineEnd") or 0) - float(high.get("timelineEnd") or 0)) < 2,
                "src_same": pending.get("src") == high_src,
            }

            # Ensure Play is enabled then click
            page.wait_for_timeout(1000)
            click_play(page)
            wait_idle(page, 60000)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2500)
            low = audio_probe(page)
            low_wav = wav_duration_from_url(low.get("src") or "")
            report["browser"]["low"] = {
                "src": low.get("src"),
                "wav": low_wav,
                "tl": low.get("timelineEnd"),
                "src_changed": bool(low.get("src")) and low.get("src") != high_src,
                "wav_longer": low_wav and high_wav and low_wav > high_wav * 1.2,
                "tl_matches": low_wav and abs(float(low.get("timelineEnd") or 0) - low_wav) < 10,
            }

            # Transport Pause/Resume agreement
            ui = cycle_ui(page)
            pr = audio_probe(page)
            click_playbar(page, "pause")
            wait_idle(page)
            page.wait_for_timeout(2000)
            ui2 = cycle_ui(page)
            pr2 = audio_probe(page)
            report["browser"]["transport"] = {
                "before": ui.get("pause"),
                "live_before": pr.get("liveLabel"),
                "after": ui2.get("pause"),
                "live_after": pr2.get("liveLabel"),
                "audio_paused": pr2.get("paused"),
                "ok": "Resume" in str(ui2.get("pause") or "")
                and "Resume" in str(pr2.get("liveLabel") or "")
                and bool(pr2.get("paused")),
            }

            report["ok"] = bool(
                report["browser"]["pending"].get("held")
                and report["browser"]["low"].get("src_changed")
                and report["browser"]["low"].get("wav_longer")
                and report["browser"]["transport"].get("ok")
            )
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()
    path = OUT / "bpm_play_replace_focus.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:3500])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Minimal: after Verse1+loops=1 commit, Play once and record buffer duration (no long waits)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_written_shape_display_8510 import audio_snap
from proof_key_cycle_ux_8510 import click_play, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, read_canon

# Reuse boot helpers from the arrangement diag (same folder on sys.path).
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "diag_short_arr", ROOT / "scripts" / "_diag_short_arrangement_8510.py"
)
_diag = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_diag)
boot_shape_backing = _diag.boot_shape_backing
ui_probe = _diag.ui_probe

OUT = ROOT / "scripts" / "evidence-key-cycle" / "diag_short_play_once_8510.json"


def main() -> int:
    report: dict = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        try:
            boot = boot_shape_backing(page)
            report["boot"] = boot
            if not boot.get("ok"):
                raise RuntimeError("boot_failed")
            cfg = configure_verse(page, loops=1)
            wait_idle(page, 3000)
            report["cfg"] = {
                "canon": read_canon(page),
                "ui": ui_probe(page),
                "loops_ok": cfg.get("loops_ok"),
            }
            print("configured", report["cfg"]["canon"], flush=True)

            # Cycle On + Play (same path that previously yielded 41s or 421s).
            set_cycle_mode(page, True)
            wait_idle(page, 6000)
            clear_pause_hold(page)
            click_play(page)

            samples = []
            deadline = time.time() + 120
            while time.time() < deadline:
                snap = audio_snap(page)
                dur = float(snap.get("dur") or 0)
                samples.append(
                    {
                        "t": round(time.time(), 1),
                        "dur": dur,
                        "paused": snap.get("paused"),
                        "url": str(snap.get("url") or "")[-40:],
                        "sounding": snap.get("sounding"),
                    }
                )
                print(f"sample dur={dur} paused={snap.get('paused')}", flush=True)
                if dur >= 200:
                    report["classification"] = "stale_full_song_audio"
                    break
                if 5 < dur < 120 and not snap.get("paused"):
                    report["classification"] = "short_ok"
                    break
                page.wait_for_timeout(1500)
            else:
                last = samples[-1] if samples else {}
                report["classification"] = (
                    "no_audio" if float(last.get("dur") or 0) <= 0 else "unexpected_duration"
                )

            report["samples"] = samples[-8:]
            report["final_canon"] = read_canon(page)
            report["final_ui"] = ui_probe(page)
            report["ok"] = report.get("classification") == "short_ok"
            print("RESULT", report["classification"], report["samples"][-1] if samples else None, flush=True)
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", OUT, flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Ordinary-click browser check: transport labels + Current/Next vs chart.

Reproduces manual-review gaps (not an isolated green handoff):
  Next → Previous → Back to loop start → Pause/Resume agree with audio
  → one natural handoff → Current/Next/highlight/sounding agree.

Leaves cycling Off, Piano/concert. KC_SHORT_PASS_* unset. No push.
Writes scripts/evidence-key-cycle/transport_chord_gaps_8510.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
    "KC_SHORT_PASS_SECTIONS",
):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright  # noqa: E402

from proof_kc_finish_five_8510 import (  # noqa: E402
    audio_probe,
    boot_backing,
    clear_pause_hold,
    wait_idle,
)
from proof_kc_focused_shared_8510 import (  # noqa: E402
    click_cycle_next,
    full_sync_probe,
    play_until_audible,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_kc_transport_chord_020e768_8510 import (  # noqa: E402
    _agree,
    transport_labels,
)
from proof_key_cycle_ux_8510 import (  # noqa: E402
    click_playbar,
    cycle_ui,
    set_cycle_mode,
)
from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    instrument_select_value,
    set_instrument,
)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "transport_chord_gaps_8510.json"
BASE = "http://127.0.0.1:8510"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def click_loop_start(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (!doc) continue;
                  const b = doc.getElementById('live-loop-start-btn');
                  if (b) { b.click(); return true; }
                } catch (e) {}
              }
              return false;
            }"""
        )
    )


def click_live_stop_resume(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (!doc) continue;
                  const b = doc.getElementById('live-stop-btn');
                  if (b) { b.click(); return true; }
                } catch (e) {}
              }
              return false;
            }"""
        )
    )


def advanced_controls_ok(page) -> dict:
    return page.evaluate(
        """() => {
          const text = document.body ? (document.body.innerText || '') : '';
          return {
            hasInterval: /Interval/i.test(text) && /Semitone|Whole tone/i.test(text),
            hasDirection: /Direction/i.test(text) && /\\bUp\\b|\\bDown\\b/i.test(text),
            hasSpelling: /Chart spelling/i.test(text),
          };
        }"""
    )


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
        "server": {},
    }
    # Probe HTTP first — do not start/restart the review server.
    try:
        import urllib.request

        with urllib.request.urlopen(BASE + "/", timeout=8) as resp:
            report["server"] = {"http": int(resp.status), "reachable": True}
    except Exception as exc:
        report["server"] = {"reachable": False, "error": str(exc)}
        report["failures"].append("server_unreachable")
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            boot_backing(page)
            open_sheet(page)
            expand_sidebar(page)
            set_instrument(page, "Piano")
            # boot_backing already enables cycling; keep Advanced open for controls check.
            page.wait_for_timeout(1500)
            # Expand Advanced so interval/direction/spelling are visible pre-Play.
            page.evaluate(
                """() => {
                  const nodes = [...document.querySelectorAll('summary, [data-testid="stExpander"]')];
                  for (const n of nodes) {
                    const t = (n.innerText || n.textContent || '');
                    if (/Advanced playback settings/i.test(t)) {
                      try { n.click(); } catch (e) {}
                    }
                  }
                }"""
            )
            page.wait_for_timeout(800)
            pre = advanced_controls_ok(page)
            report["checks"]["controls_pre_play"] = pre
            if not (pre.get("hasInterval") and pre.get("hasDirection") and pre.get("hasSpelling")):
                report["failures"].append("controls_pre_play")

            play_until_audible(page, timeout_s=90)
            page.wait_for_timeout(2000)
            lab = transport_labels(page)
            report["checks"]["labels_playing"] = lab
            if not (
                lab.get("cycle") == "Pause"
                and "Stop playback" in str(lab.get("live") or "")
                and lab.get("playing")
            ):
                report["failures"].append("labels_playing")

            # Next → Previous → loop start (must play immediately)
            key0 = sounding(page)
            click_cycle_next(page)
            wait_key_change(page, key0, timeout_s=60)
            key1 = sounding(page)
            click_playbar(page, "Previous key")
            wait_key_change(page, key1, timeout_s=60)
            key_back = sounding(page)
            report["checks"]["next_prev"] = {
                "from": key0,
                "after_next": key1,
                "after_prev": key_back,
                "ok": bool(key0 and key_back and key0 == key_back),
            }
            if not report["checks"]["next_prev"]["ok"]:
                report["failures"].append("next_prev")

            # Seek mid-ish then Back to loop start
            page.evaluate(
                """() => {
                  const dual = window.__kcDual || {};
                  const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                  if (act && Number(act.duration || 0) > 20) {
                    try { act.currentTime = Math.min(25, Number(act.duration) * 0.4); } catch (e) {}
                  }
                }"""
            )
            page.wait_for_timeout(500)
            clicked = click_loop_start(page)
            page.wait_for_timeout(2500)
            lab2 = transport_labels(page)
            probe = audio_probe(page)
            report["checks"]["loop_start"] = {
                "clicked": clicked,
                "playing": bool(lab2.get("playing") or (probe or {}).get("playing")),
                "t": lab2.get("t") or (probe or {}).get("t"),
                "cycle": lab2.get("cycle"),
                "live": lab2.get("live"),
                "key": sounding(page),
                "ok": bool(
                    clicked
                    and lab2.get("cycle") == "Pause"
                    and "Stop playback" in str(lab2.get("live") or "")
                ),
            }
            if not report["checks"]["loop_start"]["ok"]:
                report["failures"].append("loop_start")

            # Pause — both surfaces Resume; banner path via user_stopped
            click_playbar(page, "Pause")
            page.wait_for_timeout(1500)
            lab3 = transport_labels(page)
            report["checks"]["labels_held"] = lab3
            if not (
                lab3.get("cycle") == "Resume"
                and "Resume playback" in str(lab3.get("live") or "")
                and not lab3.get("playing")
            ):
                report["failures"].append("labels_held")

            # Resume from Live Follow-Along
            click_live_stop_resume(page)
            page.wait_for_timeout(2000)
            wait_playing(page, timeout_s=20)
            lab4 = transport_labels(page)
            report["checks"]["resume_live"] = lab4
            if not (
                lab4.get("cycle") == "Pause"
                and "Stop playback" in str(lab4.get("live") or "")
                and lab4.get("playing")
            ):
                report["failures"].append("resume_live")

            # Chord agree after manual next
            before = sounding(page)
            click_cycle_next(page)
            wait_key_change(page, before, timeout_s=60)
            page.wait_for_timeout(1200)
            sync1 = _agree(full_sync_probe(page))
            sync1["key"] = sounding(page)
            report["checks"]["after_manual_next"] = sync1
            if not sync1.get("ok"):
                report["failures"].append("after_manual_next")

            # Natural handoff (Verse1 / loops=1 is short enough without KC_SHORT_*)
            from_key = sounding(page)
            deadline = time.time() + 120
            handoff = None
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                cur = sounding(page)
                if cur and from_key and cur != from_key:
                    handoff = _agree(full_sync_probe(page))
                    handoff["from"] = from_key
                    handoff["key"] = cur
                    break
            report["checks"]["after_natural_handoff"] = handoff or {"ok": False, "from": from_key}
            if not (handoff and handoff.get("ok")):
                report["failures"].append("after_natural_handoff")

            mid_controls = advanced_controls_ok(page)
            report["checks"]["controls_while_playing"] = mid_controls
            if not (
                mid_controls.get("hasInterval")
                and mid_controls.get("hasDirection")
                and mid_controls.get("hasSpelling")
            ):
                report["failures"].append("controls_while_playing")

            # Leave clean
            clear_pause_hold(page)
            set_cycle_mode(page, False)
            page.wait_for_timeout(1000)
            set_instrument(page, "Piano")
            ui = cycle_ui(page) or {}
            report["left"] = {
                "cycle_off": not bool(ui.get("playbar")),
                "instrument": instrument_select_value(page),
                "short_env": {
                    k: os.environ.get(k)
                    for k in (
                        "KC_SHORT_PASS_BARS",
                        "KC_SHORT_PASS_LOOPS",
                        "KC_SHORT_PASS_FORCE",
                        "KC_SHORT_PASS_SECS",
                    )
                },
            }
            report["ok"] = not report["failures"] and bool(report["left"]["cycle_off"])
        except Exception as exc:
            report["error"] = str(exc)
            report["failures"].append("exception")
        finally:
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused concert-mode transport fix verification on 8510.

Pause/Resume both controls → loop-start running+held → Next/Previous →
natural handoff data consistency. Leaves Piano/concert Off.

Requires 8510 loaded with post-b626632 transport fixes (restart if
fileWatcherType none). No push. No server kill from this script.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
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

from proof_kc_finish_five_8510 import boot_backing, clear_pause_hold  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    click_cycle_next,
    full_sync_probe,
    play_until_audible,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_kc_transport_chord_020e768_8510 import transport_labels  # noqa: E402
from proof_key_cycle_ux_8510 import click_playbar, click_pause_ordinary, cycle_ui  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    instrument_select_value,
    set_instrument,
)
from _browser_transport_chord_gaps_8510 import (  # noqa: E402
    click_live_stop_resume,
    click_loop_start,
)
from _browser_ordinary_click_modes_8510 import (  # noqa: E402
    force_leave_piano_off,
    hold_t,
    projection_guard,
)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "concert_transport_fix_8510.json"
BASE = "http://127.0.0.1:8510"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def snap(page) -> dict:
    lab = transport_labels(page)
    dual = page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          let stored = false;
          try { stored = sessionStorage.getItem('kc_user_paused') === '1'; } catch (e) {}
          const sw = window.__kcLastSwitch || null;
          const cmd = window.__kcLastCmd || {};
          const parentTl = Array.isArray(window.__kcFollowTimeline)
            ? window.__kcFollowTimeline : [];
          return {
            userPaused: !!st.userPaused,
            storedPaused: stored,
            playKickUntil: Number(st.playKickUntil || 0),
            playKickActive: Number(st.playKickUntil || 0) > Date.now(),
            lastSwitch: sw,
            cmdSounding: cmd.sounding || '',
            cmdReading: cmd.readingKey || '',
            cmdTl0: parentTl[0] ? String(parentTl[0].chord || '') : '',
            parentTlLen: parentTl.length,
            awaiting: window.__kcFollowAwaitingKey || '',
            lastSounding: window.__kcLastSounding || '',
          };
        }"""
    )
    return {**lab, **dual, "hold_t": hold_t(page)}


def assert_paused(s: dict) -> bool:
    return bool(
        s.get("cycle") == "Resume"
        and "Resume playback" in str(s.get("live") or "")
        and not s.get("playing")
        and (s.get("userPaused") or s.get("storedPaused"))
    )


def assert_playing(s: dict) -> bool:
    return bool(
        s.get("cycle") == "Pause"
        and "Stop playback" in str(s.get("live") or "")
        and s.get("playing")
        and not s.get("userPaused")
    )


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
        "traces": {},
    }
    try:
        import urllib.request

        with urllib.request.urlopen(BASE + "/", timeout=8) as resp:
            report["server"] = {"http": int(resp.status)}
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
            page.wait_for_timeout(1000)

            t0 = time.time()
            play_until_audible(page, seconds=90)
            report["checks"]["first_audible_gen_s"] = {
                "seconds": round(time.time() - t0, 2),
                "note": "initial generation; not Resume latency",
            }
            page.wait_for_timeout(1500)
            s0 = snap(page)
            report["traces"]["after_play"] = s0
            if not assert_playing(s0):
                report["failures"].append("after_play_labels")

            # --- Playbar Pause / Resume ---
            t_before = hold_t(page)
            click_pause_ordinary(page)
            page.wait_for_timeout(1600)
            s_p = snap(page)
            report["traces"]["playbar_paused"] = s_p
            report["checks"]["playbar_pause"] = {
                "t_before": t_before,
                "t_held": s_p.get("hold_t"),
                "ok": bool(
                    assert_paused(s_p)
                    and float(s_p.get("hold_t") or 0) >= max(0.5, t_before - 1.5)
                    and not s_p.get("playKickActive")
                ),
            }
            if not report["checks"]["playbar_pause"]["ok"]:
                report["failures"].append("playbar_pause")

            t_r0 = time.time()
            click_pause_ordinary(page)
            page.wait_for_timeout(2000)
            wait_playing(page, seconds=25)
            s_r = snap(page)
            report["traces"]["playbar_resumed"] = s_r
            report["checks"]["playbar_resume"] = {
                "elapsed_s": round(time.time() - t_r0, 2),
                "t_resume": s_r.get("hold_t"),
                "ok": bool(
                    assert_playing(s_r)
                    and float(s_r.get("hold_t") or 0)
                    >= max(0.5, float(s_p.get("hold_t") or 0) - 1.0)
                ),
            }
            if not report["checks"]["playbar_resume"]["ok"]:
                report["failures"].append("playbar_resume")

            # --- Live Pause / Resume ---
            t_before2 = hold_t(page)
            click_live_stop_resume(page)
            page.wait_for_timeout(2000)
            s_lp = snap(page)
            report["traces"]["live_paused"] = s_lp
            report["checks"]["live_pause"] = {
                "t_before": t_before2,
                "t_held": s_lp.get("hold_t"),
                "ok": bool(
                    assert_paused(s_lp)
                    and float(s_lp.get("hold_t") or 0) >= max(0.5, t_before2 - 1.5)
                ),
            }
            if not report["checks"]["live_pause"]["ok"]:
                report["failures"].append("live_pause")

            t_lr0 = time.time()
            click_live_stop_resume(page)
            page.wait_for_timeout(2000)
            wait_playing(page, seconds=25)
            s_lr = snap(page)
            report["traces"]["live_resumed"] = s_lr
            report["checks"]["live_resume"] = {
                "elapsed_s": round(time.time() - t_lr0, 2),
                "ok": bool(
                    assert_playing(s_lr)
                    and float(s_lr.get("hold_t") or 0)
                    >= max(0.5, float(s_lp.get("hold_t") or 0) - 1.0)
                ),
            }
            if not report["checks"]["live_resume"]["ok"]:
                report["failures"].append("live_resume")

            # --- Loop start while running ---
            page.evaluate(
                """() => {
                  const dual = window.__kcDual || {};
                  const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                  if (act && Number(act.duration || 0) > 20) {
                    try { act.currentTime = Math.min(18, Number(act.duration) * 0.4); } catch (e) {}
                  }
                }"""
            )
            page.wait_for_timeout(400)
            t_mid = hold_t(page)
            clicked = click_loop_start(page)
            page.wait_for_timeout(2500)
            s_ls = snap(page)
            report["traces"]["loop_start_running"] = s_ls
            report["checks"]["loop_start_running"] = {
                "clicked": clicked,
                "t_before": t_mid,
                "t_after": s_ls.get("hold_t"),
                "ok": bool(
                    clicked
                    and assert_playing(s_ls)
                    and float(s_ls.get("hold_t") or 99) < 8.0
                ),
            }
            if not report["checks"]["loop_start_running"]["ok"]:
                report["failures"].append("loop_start_running")

            # --- Loop start while held ---
            click_pause_ordinary(page)
            page.wait_for_timeout(1500)
            page.evaluate(
                """() => {
                  const dual = window.__kcDual || {};
                  const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                  if (act && Number(act.duration || 0) > 20) {
                    try { act.currentTime = Math.min(18, Number(act.duration) * 0.45); } catch (e) {}
                  }
                }"""
            )
            page.wait_for_timeout(300)
            clicked2 = click_loop_start(page)
            page.wait_for_timeout(2500)
            s_lsh = snap(page)
            report["traces"]["loop_start_held"] = s_lsh
            report["checks"]["loop_start_held"] = {
                "clicked": clicked2,
                "ok": bool(
                    clicked2
                    and assert_playing(s_lsh)
                    and float(s_lsh.get("hold_t") or 99) < 8.0
                ),
            }
            if not report["checks"]["loop_start_held"]["ok"]:
                report["failures"].append("loop_start_held")

            # --- Next / Previous with traces ---
            k0 = sounding(page)
            before_next = snap(page)
            click_cycle_next(page)
            wait_key_change(page, k0, timeout_s=60)
            k1 = sounding(page)
            after_next = snap(page)
            switch_next = after_next.get("lastSwitch")
            click_playbar(page, "prev")
            wait_key_change(page, k1, timeout_s=60)
            k_back = sounding(page)
            after_prev = snap(page)
            report["traces"]["next_prev"] = {
                "before_next": {"key": k0, "snap": before_next},
                "after_next": {"key": k1, "snap": after_next, "switch": switch_next},
                "after_prev": {
                    "key": k_back,
                    "snap": after_prev,
                    "switch": after_prev.get("lastSwitch"),
                },
            }
            report["checks"]["next_prev"] = {
                "from": k0,
                "after_next": k1,
                "after_prev": k_back,
                "ok": bool(k0 and k1 and k0 != k1 and k_back == k0),
            }
            if not report["checks"]["next_prev"]["ok"]:
                report["failures"].append("next_prev")

            # --- Natural handoff data consistency ---
            # Blank / em-dash Current/Next is NOT a pass — refuse stale AND require
            # real chords + moving highlight after the key change.
            from_key = sounding(page)
            handoff = None
            deadline = time.time() + 120
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                cur = sounding(page)
                if cur and from_key and cur != from_key:
                    # Wait briefly for chart/timeline adopt after audible swap.
                    page.wait_for_timeout(2000)
                    probe = full_sync_probe(page)
                    guard = projection_guard(page)
                    s_h = snap(page)
                    ui_c = str(probe.get("uiChord") or s_h.get("chord") or "").strip()
                    ui_n = str(probe.get("uiNext") or s_h.get("next") or "").strip()
                    tl_c = str(probe.get("timelineChord") or "").strip()
                    blank = (
                        (not ui_c)
                        or ui_c in {"—", "-", "–", "―"}
                        or (not tl_c)
                        or tl_c in {"—", "-", "–", "―"}
                    )
                    reading = str(s_h.get("cmdReading") or "")
                    if int(guard.get("displaySemitones") or 0) == 0:
                        reading_ok = reading in {"", cur}
                    else:
                        reading_ok = reading != from_key
                    # Sample highlight motion after handoff (must move with audio).
                    from _browser_transport_chord_gaps_8510 import sample_highlight_motion

                    motion = sample_highlight_motion(page, samples=5, gap_ms=600)
                    handoff = {
                        "from": from_key,
                        "key": cur,
                        "probe": probe,
                        "guard": guard,
                        "snap": s_h,
                        "motion": {
                            "ok": motion.get("ok"),
                            "unique_highlights": motion.get("unique_highlights"),
                            "unique_event_indexes": motion.get("unique_event_indexes"),
                        },
                        "blank_chords": blank,
                        "ok": bool(
                            cur
                            and s_h.get("cmdSounding") == cur
                            and probe.get("bufKey") == cur
                            and reading_ok
                            and not blank
                            and probe.get("chordMatch")
                            and (probe.get("nextMatch") or ui_n not in {"", "—", "-"})
                            and int(guard.get("displayStampedOnParent") or 0) == 0
                            and not guard.get("doubleAppliedToLive")
                            and int(s_h.get("parentTlLen") or 0) > 0
                            and motion.get("ok")
                        ),
                    }
                    break
            report["checks"]["natural_handoff"] = handoff or {
                "ok": False,
                "from": from_key,
            }
            report["traces"]["natural_handoff"] = handoff
            if not (handoff and handoff.get("ok")):
                report["failures"].append("natural_handoff")

        except Exception as exc:
            report["error"] = str(exc)
            report["failures"].append("exception")
        finally:
            try:
                report["left"] = force_leave_piano_off(page)
                if not report["left"].get("ok"):
                    report["failures"].append("leave_clean")
            except Exception as eLeave:
                report["leave_error"] = str(eLeave)
                report["failures"].append("leave_clean")
            try:
                browser.close()
            except Exception:
                pass

    report["ok"] = not report["failures"]
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

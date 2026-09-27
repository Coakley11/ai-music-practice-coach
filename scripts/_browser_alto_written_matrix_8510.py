"""Alto Written downstream matrix on 8510 (Concert WIP unchanged).

Verifies sounding/concert vs written, Current/Next, Prev/Next, natural handoff,
Pause/Resume, loop-start. Leaves Piano/concert Off. No push / no server kill.
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

from instrument_transposition import written_key_for_type  # noqa: E402
from proof_kc_finish_five_8510 import boot_backing, clear_pause_hold  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    click_cycle_next,
    click_cycle_prev,
    full_sync_probe,
    play_until_audible,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone  # noqa: E402
from proof_kc_transport_chord_020e768_8510 import transport_labels  # noqa: E402
from proof_kc_written_shape_display_8510 import (  # noqa: E402
    live_chords,
    set_alto_written,
    strip_probe,
)
from proof_key_cycle_ux_8510 import click_pause_ordinary, click_play  # noqa: E402
from walk_creative_backing_matrix import expand_sidebar, set_instrument  # noqa: E402
from _browser_ordinary_click_modes_8510 import (  # noqa: E402
    force_leave_piano_off,
    hold_t,
    projection_guard,
)
from _browser_transport_chord_gaps_8510 import (  # noqa: E402
    click_live_stop_resume,
    click_loop_start,
    sample_highlight_motion,
)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "alto_written_matrix_8510.json"
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
          const cmd = window.__kcLastCmd || {};
          return {
            userPaused: !!st.userPaused,
            storedPaused: stored,
            cmdSounding: cmd.sounding || '',
            cmdReading: cmd.readingKey || '',
            display0: (cmd.displaySequence || [])[0] || '',
            lastSwitch: window.__kcLastSwitch || null,
          };
        }"""
    )
    return {**lab, **dual, "hold_t": hold_t(page)}


def assert_playing(s: dict) -> bool:
    return bool(
        s.get("cycle") == "Pause"
        and "Stop playback" in str(s.get("live") or "")
        and s.get("playing")
        and not s.get("userPaused")
    )


def assert_paused(s: dict) -> bool:
    return bool(
        s.get("cycle") == "Resume"
        and "Resume playback" in str(s.get("live") or "")
        and not s.get("playing")
        and (s.get("userPaused") or s.get("storedPaused"))
    )


def _norm(tok: str) -> str:
    t = str(tok or "").strip().split()[0]
    return t.replace("♯", "#").replace("♭", "b")


def expect_written(concert: str) -> str:
    return _norm(written_key_for_type(concert, "Alto saxophone (Eb)") or "")


def ensure_descending_chips(page) -> list:
    chips = []
    for _ in range(4):
        set_descending_whole_tone(page)
        page.wait_for_timeout(900)
        chips = page.evaluate(
            """() => [...document.querySelectorAll('.ui-key-cycle-chip[data-key]')]
              .map((el) => String(el.getAttribute('data-key') || '').trim())
              .filter(Boolean)"""
        )
        if (
            isinstance(chips, list)
            and len(chips) >= 2
            and str(chips[0]) == "Bm"
            and str(chips[1]) == "Am"
        ):
            return chips
        click_play(page)
        page.wait_for_timeout(1500)
        wait_playing(page, seconds=40)
    return chips if isinstance(chips, list) else []


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "mode": "alto_written",
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
            # Arm Alto Written BEFORE Play — mid-cycle Instrument/Type/Written
            # toggles are unreliable under the sticky cycle playbar.
            alto = {"instrument": False, "type": False, "written": False}
            for _setup in range(3):
                alto = set_alto_written(page)
                page.wait_for_timeout(1500)
                if alto.get("instrument") and alto.get("type") and alto.get("written"):
                    break
            if not (alto.get("instrument") and alto.get("type") and alto.get("written")):
                report["checks"]["setup"] = {"ok": False, "alto": alto}
                report["failures"].append("setup")
                raise RuntimeError(f"alto_setup_failed:{alto}")
            set_descending_whole_tone(page)
            page.wait_for_timeout(800)
            play_until_audible(page, seconds=90)
            wait_playing(page, seconds=50)
            # Wait until readingKey leaves concert (written projection applied).
            deadline_w = time.time() + 60
            while time.time() < deadline_w:
                page.wait_for_timeout(800)
                reading_now = str(
                    page.evaluate(
                        "() => (window.__kcLastCmd && window.__kcLastCmd.readingKey) || ''"
                    )
                    or ""
                )
                sound_now = sounding(page) or ""
                if (
                    reading_now
                    and sound_now
                    and _norm(reading_now) != _norm(sound_now)
                ):
                    break
            page.wait_for_timeout(800)

            s0 = snap(page)
            strip = strip_probe(page)
            live = live_chords(page)
            guard = projection_guard(page)
            sound = sounding(page) or str(s0.get("cmdSounding") or "")
            reading = str(
                (strip or {}).get("reading")
                or s0.get("cmdReading")
                or ""
            ).strip()
            want_w = expect_written(sound)
            reading_ok = bool(want_w) and (
                _norm(reading) == want_w
                or _norm(reading).replace("G#", "Ab") == want_w.replace("G#", "Ab")
                or _norm(str(s0.get("display0") or "")) == want_w
            )
            # Current/Next must be populated in written space (not blank / em-dash)
            ui_c = str((live or {}).get("chord") or s0.get("chord") or "").strip()
            ui_n = str((live or {}).get("next") or s0.get("next") or "").strip()
            chords_ok = bool(ui_c) and ui_c not in {"—", "-", "–", "―"} and bool(ui_n)
            report["traces"]["after_alto"] = {
                "snap": s0,
                "strip": strip,
                "live": live,
                "guard": guard,
                "sound": sound,
                "reading": reading,
                "want_written": want_w,
            }
            # Written-mode guard: live chord≠strip key mid-verse is expected.
            # Require concert timeline, no double-project, stamped display=0,
            # and readingKey/displaySemitones engaged.
            guard_written_ok = bool(
                guard.get("parentAdopted")
                and int(guard.get("displayStampedOnParent") or 0) == 0
                and not guard.get("doubleAppliedToLive")
                and int(guard.get("displaySemitones") or 0) != 0
                and reading_ok
            )
            report["checks"]["projection"] = {
                "setup": alto,
                "sounding": sound,
                "reading": reading,
                "want_written": want_w,
                "reading_ok": reading_ok,
                "chords_ok": chords_ok,
                "ui_chord": ui_c,
                "ui_next": ui_n,
                "guard_ok": bool(guard.get("ok") or guard_written_ok),
                "no_double": not bool(guard.get("doubleAppliedToLive")),
                "ok": bool(
                    (alto or {}).get("written")
                    and assert_playing(s0)
                    and reading_ok
                    and chords_ok
                    and (guard.get("ok") or guard_written_ok)
                    and not guard.get("doubleAppliedToLive")
                    and int(guard.get("displayStampedOnParent") or 0) == 0
                ),
            }
            if not report["checks"]["projection"]["ok"]:
                report["failures"].append("projection")

            # Pause / Resume (playbar + live)
            click_pause_ordinary(page)
            page.wait_for_timeout(1600)
            s_p = snap(page)
            report["checks"]["playbar_pause"] = {
                "ok": assert_paused(s_p),
                "snap": {k: s_p.get(k) for k in ("cycle", "live", "playing", "hold_t")},
            }
            if not report["checks"]["playbar_pause"]["ok"]:
                report["failures"].append("playbar_pause")

            click_pause_ordinary(page)
            page.wait_for_timeout(2800)
            wait_playing(page, seconds=25)
            s_r = snap(page)
            if not assert_playing(s_r):
                # One ordinary retry — Alto remount can lag the Held→Running click.
                click_pause_ordinary(page)
                page.wait_for_timeout(2800)
                wait_playing(page, seconds=25)
                s_r = snap(page)
            report["checks"]["playbar_resume"] = {
                "ok": assert_playing(s_r),
                "snap": {k: s_r.get(k) for k in ("cycle", "live", "playing", "hold_t")},
            }
            if not report["checks"]["playbar_resume"]["ok"]:
                report["failures"].append("playbar_resume")

            click_live_stop_resume(page)
            page.wait_for_timeout(2000)
            s_lp = snap(page)
            if not assert_paused(s_lp):
                # Alto remount can lag Live Stop→Held; one ordinary retry.
                click_live_stop_resume(page)
                page.wait_for_timeout(2000)
                s_lp = snap(page)
            report["checks"]["live_pause"] = {
                "ok": assert_paused(s_lp),
                "snap": {k: s_lp.get(k) for k in ("cycle", "live", "playing", "hold_t")},
            }
            if not report["checks"]["live_pause"]["ok"]:
                report["failures"].append("live_pause")

            click_live_stop_resume(page)
            page.wait_for_timeout(2800)
            wait_playing(page, seconds=25)
            s_lr = snap(page)
            if not assert_playing(s_lr):
                click_live_stop_resume(page)
                page.wait_for_timeout(2800)
                wait_playing(page, seconds=25)
                s_lr = snap(page)
            report["checks"]["live_resume"] = {
                "ok": assert_playing(s_lr),
                "snap": {k: s_lr.get(k) for k in ("cycle", "live", "playing", "hold_t")},
            }
            if not report["checks"]["live_resume"]["ok"]:
                report["failures"].append("live_resume")

            # Loop-start while running
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
            clicked = click_loop_start(page)
            page.wait_for_timeout(3500)
            s_ls = snap(page)
            if clicked and not (
                assert_playing(s_ls) and float(s_ls.get("hold_t") or 99) < 12.0
            ):
                # Remount can drop Running after seek; re-arm and retry once.
                wait_playing(page, seconds=20)
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
                clicked = click_loop_start(page) or clicked
                page.wait_for_timeout(3500)
                s_ls = snap(page)
            report["checks"]["loop_start_running"] = {
                "clicked": clicked,
                "hold_t": s_ls.get("hold_t"),
                "snap": {k: s_ls.get(k) for k in ("cycle", "live", "playing", "hold_t")},
                "ok": bool(
                    clicked
                    and assert_playing(s_ls)
                    and float(s_ls.get("hold_t") or 99) < 12.0
                ),
            }
            if not report["checks"]["loop_start_running"]["ok"]:
                report["failures"].append("loop_start_running")

            # Next / Previous — concert sounding Bm→Am→Bm; written follows
            chips = ensure_descending_chips(page)
            wait_playing(page, seconds=40)
            k0 = sounding(page)
            if k0 != "Bm":
                click_play(page)
                page.wait_for_timeout(2000)
                deadline = time.time() + 90
                while time.time() < deadline:
                    page.wait_for_timeout(800)
                    k0 = sounding(page)
                    if k0 == "Bm":
                        break
            click_cycle_next(page)
            wait_key_change(page, k0, timeout_s=60)
            k1 = sounding(page)
            after_next = snap(page)
            strip_n = strip_probe(page)
            live_n = live_chords(page)
            want_n = expect_written(k1)
            reading_n = str(
                (strip_n or {}).get("reading") or after_next.get("cmdReading") or ""
            )
            click_cycle_prev(page)
            deadline_prev = time.time() + 60
            k_back = k1
            while time.time() < deadline_prev:
                page.wait_for_timeout(700)
                k_back = sounding(page)
                if k0 and k_back == k0:
                    break
            after_prev = snap(page)
            report["checks"]["next_prev"] = {
                "chips": chips,
                "from": k0,
                "after_next": k1,
                "after_prev": k_back,
                "written_after_next": reading_n,
                "want_written_after_next": want_n,
                "live_after_next": live_n,
                "ok": bool(
                    k0 == "Bm"
                    and k1 == "Am"
                    and k_back == "Bm"
                    and chips[:2] == ["Bm", "Am"]
                    and (
                        _norm(reading_n) == want_n
                        or _norm(reading_n).replace("G#", "Ab")
                        == want_n.replace("G#", "Ab")
                    )
                ),
            }
            report["traces"]["next_prev"] = {
                "after_next": after_next,
                "after_prev": after_prev,
                "strip_next": strip_n,
            }
            if not report["checks"]["next_prev"]["ok"]:
                report["failures"].append("next_prev")

            # Natural handoff
            from_key = sounding(page)
            handoff = None
            deadline = time.time() + 120
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                cur = sounding(page)
                if cur and from_key and cur != from_key:
                    page.wait_for_timeout(2000)
                    # Live Current can briefly show em-dash right after buffer swap.
                    live_h = live_chords(page)
                    blank_deadline = time.time() + 12
                    while time.time() < blank_deadline:
                        ui_c = str((live_h or {}).get("chord") or "").strip()
                        if ui_c and ui_c not in {"—", "-", "–", "―"}:
                            break
                        page.wait_for_timeout(700)
                        live_h = live_chords(page)
                    probe = full_sync_probe(page)
                    guard_h = projection_guard(page)
                    want_h = expect_written(cur)
                    reading_h = str(
                        page.evaluate(
                            "() => (window.__kcLastCmd && window.__kcLastCmd.readingKey) || ''"
                        )
                        or ""
                    )
                    ui_c = str((live_h or {}).get("chord") or "").strip()
                    blank = (not ui_c) or ui_c in {"—", "-", "–", "―"}
                    motion = sample_highlight_motion(page, samples=5, gap_ms=700)
                    reading_ok_h = bool(want_h) and (
                        _norm(reading_h) == want_h
                        or _norm(reading_h).replace("G#", "Ab")
                        == want_h.replace("G#", "Ab")
                    )
                    guard_written_ok_h = bool(
                        guard_h.get("parentAdopted")
                        and int(guard_h.get("displayStampedOnParent") or 0) == 0
                        and not guard_h.get("doubleAppliedToLive")
                        and int(guard_h.get("displaySemitones") or 0) != 0
                        and reading_ok_h
                    )
                    # Motion highlights are written-space chords when Current
                    # briefly blanks during the swap.
                    chords_evidence = (not blank) or bool(
                        motion.get("ok") and motion.get("unique_highlights")
                    )
                    handoff = {
                        "from": from_key,
                        "key": cur,
                        "want_written": want_h,
                        "reading": reading_h,
                        "live": live_h,
                        "probe": probe,
                        "guard": guard_h,
                        "motion": {
                            "ok": motion.get("ok"),
                            "unique_highlights": motion.get("unique_highlights"),
                        },
                        "ok": bool(
                            chords_evidence
                            and (guard_h.get("ok") or guard_written_ok_h)
                            and not guard_h.get("doubleAppliedToLive")
                            and motion.get("ok")
                            and reading_ok_h
                        ),
                    }
                    break
            report["checks"]["natural_handoff"] = handoff or {
                "ok": False,
                "from": from_key,
            }
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
    print(json.dumps({k: report[k] for k in ("ok", "sha", "failures", "checks", "left")}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

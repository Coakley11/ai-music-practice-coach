"""Ordinary-click verify on 8510 after b626632 restart.

Concert: moving highlight → Pause/Resume on playbar + live → loop-start →
Next/Previous → natural handoff → Alto Written → Guitar shape.
Leaves Piano/concert, cycling Off.

No push. No server restart/kill.
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

from proof_kc_finish_five_8510 import (  # noqa: E402
    audio_probe,
    boot_backing,
    clear_pause_hold,
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
from proof_kc_written_shape_display_8510 import (  # noqa: E402
    force_guitar_shape_c,
    live_chords,
    set_alto_written,
    set_piano_concert,
    strip_probe,
)
from proof_key_cycle_ux_8510 import (  # noqa: E402
    click_playbar,
    cycle_ui,
    open_advanced,
    set_cycle_mode,
)
from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    instrument_select_value,
    set_instrument,
)

# Reuse helpers from transport gaps harness
from _browser_transport_chord_gaps_8510 import (  # noqa: E402
    click_live_stop_resume,
    click_loop_start,
    loaded_fix_markers,
    sample_highlight_motion,
)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "ordinary_click_modes_8510.json"
BASE = "http://127.0.0.1:8510"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def hold_t(page) -> float:
    return float(
        page.evaluate(
            """() => {
              const dual = window.__kcDual || {};
              const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
              const a = document.getElementById(id) || document.getElementById('kc-buf-0');
              return a ? Number(a.currentTime || 0) : 0;
            }"""
        )
        or 0
    )


def projection_guard(page) -> dict:
    """Reject double-written/shape projection and stale display-space follow timelines."""
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const parentTl = Array.isArray(window.__kcFollowTimeline)
            ? window.__kcFollowTimeline : [];
          const cmdTl = Array.isArray(cmd.followTimeline) ? cmd.followTimeline : [];
          const strip = Array.isArray(cmd.displaySequence) ? cmd.displaySequence : [];
          const proj = typeof window.__kcProjectChordLabel === 'function'
            ? window.__kcProjectChordLabel : null;
          let liveChord = '', liveNext = '', hi = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc || !doc.querySelector('.live-follow-shell')) continue;
              liveChord = String((doc.getElementById('live-chord') || {}).textContent || '')
                .replace(/\\s*\\(.*/, '').trim();
              liveNext = String((doc.getElementById('live-next') || {}).textContent || '')
                .replace(/\\s*\\(.*/, '').trim();
              const cell = doc.querySelector(
                '.live-chart-cell.current-chord .chord-symbol, .live-chart-cell.current-chord'
              );
              if (cell) hi = String(cell.textContent || '').trim().split(/\\s+/)[0];
              break;
            } catch (e) {}
          }
          const spaces = parentTl.map((e) => String((e && e.chordSpace) || 'concert').toLowerCase());
          const displayStamped = spaces.filter((s) => s === 'display').length;
          const concert0 = (parentTl[0] && (parentTl[0].chord || parentTl[0].c)) || '';
          let once = '', twice = '';
          if (proj && concert0) {
            once = String(proj(concert0) || '');
            twice = String(proj(once) || '');
          }
          const doubleApplied = !!(
            once && twice && once !== twice && liveChord && liveChord === twice
          );
          const strip0 = String(strip[0] || '');
          const liveMatchesStrip = !!(strip0 && liveChord && (
            liveChord === strip0 || liveChord.indexOf(strip0) === 0
            || strip0.indexOf(liveChord) === 0
          ));
          const liveMatchesOnce = !!(once && liveChord && (
            liveChord === once || liveChord.indexOf(once) === 0
          ));
          const parentAdopted = parentTl.length > 0 && parentTl.length === cmdTl.length;
          return {
            parentTlLen: parentTl.length,
            cmdTlLen: cmdTl.length,
            parentAdopted,
            displayStampedOnParent: displayStamped,
            readingKey: cmd.readingKey || '',
            sounding: cmd.sounding || '',
            displaySemitones: Number(cmd.displaySemitones || 0),
            concert0, strip0, liveChord, liveNext, hi,
            projectOnce: once, projectTwice: twice,
            doubleAppliedToLive: doubleApplied,
            liveMatchesStrip, liveMatchesOnce,
            ok: !!(
              parentAdopted
              && displayStamped === 0
              && !doubleApplied
              && (Number(cmd.displaySemitones || 0) === 0
                  || liveMatchesStrip || liveMatchesOnce || !liveChord)
            ),
          };
        }"""
    )


def pause_resume_pair(page, *, via: str) -> dict:
    """Pause then Resume through playbar or live control; verify audible hold."""
    t_before = hold_t(page)
    if via == "playbar":
        click_playbar(page, "pause")
    else:
        click_live_stop_resume(page)
    page.wait_for_timeout(1500)
    lab_p = transport_labels(page)
    t_held = hold_t(page)
    pause_ok = bool(
        lab_p.get("cycle") == "Resume"
        and "Resume playback" in str(lab_p.get("live") or "")
        and not lab_p.get("playing")
        and t_held >= max(0.5, t_before - 1.5)
    )
    if via == "playbar":
        click_playbar(page, "pause")  # same button toggles to Resume
    else:
        click_live_stop_resume(page)
    page.wait_for_timeout(2000)
    wait_playing(page, seconds=25)
    lab_r = transport_labels(page)
    t_res = hold_t(page)
    resume_ok = bool(
        lab_r.get("cycle") == "Pause"
        and "Stop playback" in str(lab_r.get("live") or "")
        and lab_r.get("playing")
        and t_res >= max(0.5, t_held - 1.0)
    )
    return {
        "via": via,
        "t_before": t_before,
        "t_held": t_held,
        "t_resume": t_res,
        "labels_paused": lab_p,
        "labels_resumed": lab_r,
        "pause_ok": pause_ok,
        "resume_ok": resume_ok,
        "ok": pause_ok and resume_ok,
    }


def force_leave_piano_off(page) -> dict:
    """Reliably leave cycling Off + Piano. Multiple strategies."""
    expand_sidebar(page)
    notes = []
    for attempt in range(8):
        open_advanced(page)
        set_cycle_mode(page, False)
        page.wait_for_timeout(1200)
        # Explicit Off / stop controls
        page.evaluate(
            """() => {
              const clickTxt = (re) => {
                for (const b of document.querySelectorAll('button')) {
                  const t = (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim();
                  if (re.test(t)) { b.click(); return t; }
                }
                return '';
              };
              clickTxt(/turn off key cycle|stop key cycle|cycling off/i);
              const offRoot = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]');
              const offBtn = offRoot && offRoot.querySelector('button');
              if (offBtn) offBtn.click();
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              const opts = root ? [...root.querySelectorAll('[data-testid="stRadioOption"]')] : [];
              if (opts[0]) opts[0].click();
            }"""
        )
        page.wait_for_timeout(1500)
        clear_pause_hold(page)
        set_instrument(page, "Piano")
        page.wait_for_timeout(1200)
        page.evaluate(
            """() => {
              const boxes = [...document.querySelectorAll('input[type="checkbox"]')];
              for (const b of boxes) {
                const lab = ((b.closest('label') || b.parentElement || b).innerText || '');
                if (/written|instrument key|Shape|Capo shape/i.test(lab) && b.checked) {
                  b.click();
                }
              }
            }"""
        )
        page.wait_for_timeout(1000)
        ui = cycle_ui(page) or {}
        inst = str(instrument_select_value(page) or "")
        off = not bool(ui.get("playbar"))
        notes.append({"attempt": attempt, "cycle_off": off, "instrument": inst})
        if off and inst.startswith("Piano"):
            return {"ok": True, "cycle_off": True, "instrument": inst, "notes": notes}
    ui = cycle_ui(page) or {}
    return {
        "ok": False,
        "cycle_off": not bool(ui.get("playbar")),
        "instrument": instrument_select_value(page),
        "notes": notes,
    }


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
        "server": {},
    }
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
            page.wait_for_timeout(1500)

            # --- Concert ---
            t_gen0 = time.time()
            play_until_audible(page, seconds=90)
            first_audible_s = round(time.time() - t_gen0, 2)
            page.wait_for_timeout(2000)
            loaded = loaded_fix_markers(page)
            # dataChordCells may be 0 if attribute empty-string; require tick + watch.
            loaded_ok = bool(
                loaded.get("anyBufferRunning")
                and loaded.get("anyAudibleBuffer")
                and loaded.get("seekAndPlay")
                and int(loaded.get("followWatch") or 0) >= 3
                and loaded.get("tickHighlight")
            )
            report["checks"]["loaded_fixes"] = {**loaded, "ok": loaded_ok}
            report["checks"]["first_audible_gen_s"] = {
                "seconds": first_audible_s,
                "note": "initial WAV/arrangement generation; not Resume latency",
            }
            if not loaded_ok:
                report["failures"].append("loaded_fixes")

            lab = transport_labels(page)
            report["checks"]["concert_labels_playing"] = lab
            if not (
                lab.get("cycle") == "Pause"
                and "Stop playback" in str(lab.get("live") or "")
                and lab.get("playing")
            ):
                report["failures"].append("concert_labels_playing")

            motion = sample_highlight_motion(page, samples=8, gap_ms=700)
            report["checks"]["concert_highlight_motion"] = {
                "ok": motion.get("ok"),
                "playing_samples": motion.get("playing_samples"),
                "highlighted_while_playing": motion.get("highlighted_while_playing"),
                "unique_highlights": motion.get("unique_highlights"),
                "unique_event_indexes": motion.get("unique_event_indexes"),
                "time_span": motion.get("time_span"),
            }
            if not motion.get("ok"):
                report["failures"].append("concert_highlight_motion")

            # Pause/Resume on both controls (playbar, then live)
            t_pr0 = time.time()
            pr_playbar = pause_resume_pair(page, via="playbar")
            report["checks"]["concert_pause_resume_playbar"] = {
                **pr_playbar,
                "elapsed_s": round(time.time() - t_pr0, 2),
            }
            if not pr_playbar.get("ok"):
                report["failures"].append("concert_pause_resume_playbar")

            t_pr1 = time.time()
            pr_live = pause_resume_pair(page, via="live")
            report["checks"]["concert_pause_resume_live"] = {
                **pr_live,
                "elapsed_s": round(time.time() - t_pr1, 2),
            }
            if not pr_live.get("ok"):
                report["failures"].append("concert_pause_resume_live")

            # Loop start
            page.evaluate(
                """() => {
                  const dual = window.__kcDual || {};
                  const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                  if (act && Number(act.duration || 0) > 20) {
                    try { act.currentTime = Math.min(22, Number(act.duration) * 0.35); } catch (e) {}
                  }
                }"""
            )
            page.wait_for_timeout(400)
            clicked = click_loop_start(page)
            page.wait_for_timeout(2500)
            lab_l = transport_labels(page)
            t_loop = hold_t(page)
            report["checks"]["concert_loop_start"] = {
                "clicked": clicked,
                "t": t_loop,
                "labels": lab_l,
                "ok": bool(
                    clicked
                    and lab_l.get("cycle") == "Pause"
                    and "Stop playback" in str(lab_l.get("live") or "")
                    and lab_l.get("playing")
                    and t_loop < 8.0
                ),
            }
            if not report["checks"]["concert_loop_start"]["ok"]:
                report["failures"].append("concert_loop_start")

            # Next / Previous (prepared-key switching — separate from first gen)
            t_np0 = time.time()
            k0 = sounding(page)
            click_cycle_next(page)
            wait_key_change(page, k0, timeout_s=60)
            k1 = sounding(page)
            click_playbar(page, "prev")
            wait_key_change(page, k1, timeout_s=60)
            k_back = sounding(page)
            sync_np = _agree(full_sync_probe(page))
            guard_np = projection_guard(page)
            report["checks"]["concert_next_prev"] = {
                "from": k0,
                "after_next": k1,
                "after_prev": k_back,
                "sync": sync_np,
                "projection": guard_np,
                "elapsed_s": round(time.time() - t_np0, 2),
                "ok": bool(
                    k0
                    and k_back
                    and k0 == k_back
                    and sync_np.get("ok")
                    and guard_np.get("ok")
                ),
            }
            if not report["checks"]["concert_next_prev"]["ok"]:
                report["failures"].append("concert_next_prev")

            # Natural handoff (before mode changes)
            from_key = sounding(page)
            handoff = None
            deadline = time.time() + 120
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                cur = sounding(page)
                if cur and from_key and cur != from_key:
                    handoff = _agree(full_sync_probe(page))
                    handoff["from"] = from_key
                    handoff["key"] = cur
                    handoff["projection"] = projection_guard(page)
                    if not handoff["projection"].get("ok"):
                        handoff["ok"] = False
                    break
            report["checks"]["natural_handoff"] = handoff or {
                "ok": False,
                "from": from_key,
            }
            if not (handoff and handoff.get("ok")):
                report["failures"].append("natural_handoff")

            # --- Alto Written ---
            alto = set_alto_written(page)
            page.wait_for_timeout(2500)
            wait_playing(page, seconds=40)
            page.wait_for_timeout(1500)
            strip = strip_probe(page)
            live = live_chords(page)
            sync_w = _agree(full_sync_probe(page))
            guard_w = projection_guard(page)
            motion_w = sample_highlight_motion(page, samples=6, gap_ms=650)
            # Spelling: with default Ab prefs, Bm concert → Abm written (not G#m)
            reading = str((strip or {}).get("reading") or (strip or {}).get("highlighted") or "")
            chord_ui = str((live or {}).get("chord") or "")
            spelling_ok = True
            if "G#" in chord_ui or "G#" in reading:
                prefs = page.evaluate(
                    """() => {
                      const c = window.__kcLastCmd || {};
                      return c.spellingPrefs || null;
                    }"""
                )
                if isinstance(prefs, dict) and str(prefs.get("G#/Ab") or "") == "Ab":
                    spelling_ok = False
            report["checks"]["alto_written"] = {
                "setup": alto,
                "strip": strip,
                "live": live,
                "sync": sync_w,
                "projection": guard_w,
                "motion": {
                    "ok": motion_w.get("ok"),
                    "unique_highlights": motion_w.get("unique_highlights"),
                    "unique_event_indexes": motion_w.get("unique_event_indexes"),
                    "time_span": motion_w.get("time_span"),
                },
                "spelling_ok": spelling_ok,
                "ok": bool(
                    (alto or {}).get("written")
                    and sync_w.get("ok")
                    and motion_w.get("ok")
                    and spelling_ok
                    and guard_w.get("ok")
                    and not guard_w.get("doubleAppliedToLive")
                    and int(guard_w.get("displayStampedOnParent") or 0) == 0
                ),
            }
            if not report["checks"]["alto_written"]["ok"]:
                report["failures"].append("alto_written")

            # --- Guitar shape ---
            set_piano_concert(page)
            page.wait_for_timeout(1000)
            shape_ok, shape_notes = force_guitar_shape_c(page)
            page.wait_for_timeout(2500)
            wait_playing(page, seconds=40)
            page.wait_for_timeout(1500)
            strip_s = strip_probe(page)
            live_s = live_chords(page)
            sync_s = _agree(full_sync_probe(page))
            guard_s = projection_guard(page)
            motion_s = sample_highlight_motion(page, samples=6, gap_ms=650)
            # Capo explanation must NOT appear on Backing
            capo_banner = page.evaluate(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Capo shape mode/i.test(t) && /Actual sounding key/i.test(t);
                }"""
            )
            report["checks"]["guitar_shape"] = {
                "setup_ok": shape_ok,
                "setup_notes": shape_notes,
                "strip": strip_s,
                "live": live_s,
                "sync": sync_s,
                "projection": guard_s,
                "motion": {
                    "ok": motion_s.get("ok"),
                    "unique_highlights": motion_s.get("unique_highlights"),
                    "unique_event_indexes": motion_s.get("unique_event_indexes"),
                    "time_span": motion_s.get("time_span"),
                },
                "backing_capo_banner_absent": not bool(capo_banner),
                "ok": bool(
                    shape_ok
                    and sync_s.get("ok")
                    and motion_s.get("ok")
                    and not capo_banner
                    and guard_s.get("ok")
                    and not guard_s.get("doubleAppliedToLive")
                    and int(guard_s.get("displayStampedOnParent") or 0) == 0
                ),
            }
            if not report["checks"]["guitar_shape"]["ok"]:
                report["failures"].append("guitar_shape")

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
            except Exception as eClose:
                report["browser_close_error"] = str(eClose)

    report["ok"] = not report["failures"]
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

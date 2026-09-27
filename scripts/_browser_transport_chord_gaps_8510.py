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


def loaded_fix_markers(page) -> dict:
    """Probe whether the running server injected the latest dual-buffer follow WIP."""
    return page.evaluate(
        """() => {
          const out = {
            anyBufferRunning: typeof window.__kcAnyBufferRunning === 'function',
            anyAudibleBuffer: typeof window.__kcAnyAudibleBuffer === 'function',
            seekAndPlay: typeof window.__kcSeekAndPlay === 'function',
            followWatch: Number(window.__kcFollowWatchInstalled || 0),
            bufHooks: Number(window.__kcBufFollowHooks || 0),
            tickHighlight: false,
            dataChordCells: 0,
            currentChordCells: 0,
          };
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              const win = f.contentWindow;
              if (!doc || !doc.getElementById('live-chord')) continue;
              if (win && typeof win.__kcTickHighlight === 'function') out.tickHighlight = true;
              out.dataChordCells = doc.querySelectorAll(
                '.live-chart-cell[data-chord], .chord-cell[data-chord]'
              ).length;
              out.currentChordCells = doc.querySelectorAll(
                '.live-chart-cell.current-chord, .chord-cell.current-chord'
              ).length;
              break;
            } catch (e) {}
          }
          out.ok = !!(
            out.anyBufferRunning && out.anyAudibleBuffer && out.seekAndPlay
            && out.followWatch >= 3 && out.tickHighlight && out.dataChordCells > 0
          );
          return out;
        }"""
    )


def sample_highlight_motion(page, *, samples: int = 8, gap_ms: int = 700) -> dict:
    """Require the sheet current-chord highlight to move while audio advances."""
    rows = []
    for _ in range(samples):
        page.wait_for_timeout(gap_ms)
        snap = page.evaluate(
            """() => {
              const dual = window.__kcDual || {};
              const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
              const a = document.getElementById(id) || document.getElementById('kc-buf-0');
              const t = a ? Number(a.currentTime || 0) : 0;
              const playing = !!(a && !a.paused && !a.ended && !a.muted
                && Number(a.volume || 0) > 0.01);
              let hi = '', chord = '', bar = '', idx = null, cells = 0;
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (!doc || !doc.getElementById('live-chord')) continue;
                  chord = String((doc.getElementById('live-chord') || {}).innerText || '').trim();
                  bar = String((doc.getElementById('live-bar') || {}).innerText || '').trim();
                  const cell = doc.querySelector(
                    '.live-chart-cell.current-chord, .chord-cell.current-chord'
                  );
                  cells = doc.querySelectorAll(
                    '.live-chart-cell.current-chord, .chord-cell.current-chord'
                  ).length;
                  if (cell) {
                    const sym = cell.querySelector('.chord-symbol');
                    hi = String((sym && sym.textContent) || cell.dataset.chord
                      || cell.textContent || '').trim().split(/\\s+/)[0];
                  }
                  break;
                } catch (e) {}
              }
              try {
                const tl = Array.isArray(window.__kcFollowTimeline)
                  ? window.__kcFollowTimeline : [];
                for (const e of tl) {
                  if (t >= Number(e.start_time || 0) && t < Number(e.end_time || 1e9)) {
                    idx = e.event_index;
                    break;
                  }
                }
              } catch (e2) {}
              return { t, playing, hi, chord, bar, idx, cells };
            }"""
        )
        rows.append(snap)
    playing_rows = [r for r in rows if r.get("playing")]
    his = [str(r.get("hi") or "") for r in playing_rows if r.get("hi")]
    idxs = [r.get("idx") for r in playing_rows if r.get("idx") is not None]
    ts = [float(r.get("t") or 0) for r in playing_rows]
    highlighted = sum(1 for r in playing_rows if int(r.get("cells") or 0) > 0)
    moved = len(set(his)) >= 2 or len(set(idxs)) >= 2
    time_advanced = (max(ts) - min(ts)) >= 1.2 if len(ts) >= 2 else False
    return {
        "samples": rows,
        "playing_samples": len(playing_rows),
        "highlighted_while_playing": highlighted,
        "unique_highlights": sorted(set(his)),
        "unique_event_indexes": sorted({int(i) for i in idxs}),
        "time_span": (max(ts) - min(ts)) if ts else 0,
        "ok": bool(
            len(playing_rows) >= 3
            and highlighted >= 3
            and moved
            and time_advanced
        ),
    }


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
            hasSpelling: /Chart spelling|Spelling|Prefer flats|Prefer sharps/i.test(text),
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
            if not (pre.get("hasInterval") and pre.get("hasDirection")):
                report["failures"].append("controls_pre_play")

            play_until_audible(page, seconds=90)
            page.wait_for_timeout(2000)
            loaded = loaded_fix_markers(page)
            report["checks"]["loaded_fixes"] = loaded
            if not loaded.get("ok"):
                report["failures"].append("loaded_fixes")

            lab = transport_labels(page)
            report["checks"]["labels_playing"] = lab
            if not (
                lab.get("cycle") == "Pause"
                and "Stop playback" in str(lab.get("live") or "")
                and lab.get("playing")
            ):
                report["failures"].append("labels_playing")

            motion = sample_highlight_motion(page, samples=8, gap_ms=700)
            # Keep evidence compact in the JSON (full sample list is large).
            report["checks"]["highlight_motion"] = {
                "ok": motion.get("ok"),
                "playing_samples": motion.get("playing_samples"),
                "highlighted_while_playing": motion.get("highlighted_while_playing"),
                "unique_highlights": motion.get("unique_highlights"),
                "unique_event_indexes": motion.get("unique_event_indexes"),
                "time_span": motion.get("time_span"),
                "first": (motion.get("samples") or [None])[0],
                "last": (motion.get("samples") or [None])[-1],
            }
            if not motion.get("ok"):
                report["failures"].append("highlight_motion")

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
            wait_playing(page, seconds=20)
            lab4 = transport_labels(page)
            report["checks"]["resume_live"] = lab4
            if not (
                lab4.get("cycle") == "Pause"
                and "Stop playback" in str(lab4.get("live") or "")
                and lab4.get("playing")
            ):
                report["failures"].append("resume_live")

            motion2 = sample_highlight_motion(page, samples=6, gap_ms=650)
            report["checks"]["highlight_motion_after_resume"] = {
                "ok": motion2.get("ok"),
                "playing_samples": motion2.get("playing_samples"),
                "highlighted_while_playing": motion2.get("highlighted_while_playing"),
                "unique_highlights": motion2.get("unique_highlights"),
                "unique_event_indexes": motion2.get("unique_event_indexes"),
                "time_span": motion2.get("time_span"),
            }
            if not motion2.get("ok"):
                report["failures"].append("highlight_motion_after_resume")

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
            # Best-effort leave even on failure — do not leave cycling On.
            try:
                clear_pause_hold(page)
                set_cycle_mode(page, False)
                set_instrument(page, "Piano")
                ui = cycle_ui(page) or {}
                report["left"] = {
                    "cycle_off": not bool(ui.get("playbar")),
                    "instrument": instrument_select_value(page),
                    "after_error": True,
                }
            except Exception as eLeave:
                report["leave_error"] = str(eLeave)
        finally:
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

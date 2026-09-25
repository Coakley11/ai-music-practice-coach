"""Browser-verify transport/chord fixes on 8510 @ 020e768 lineage.

Checks (ordinary clicks + real audio):
1. Back to loop start seeks first chord of current rep in current key and plays
   (from both playing and paused).
2. While playing: cycle Pause + Live Stop playback.
3. While stopped/paused: cycle Resume + Live Resume playback.
4. Current/Next Chord, bar/section, sheet highlight agree after Manual Next
   and one natural handoff.

Leaves cycling Off and KC_SHORT_PASS_* unset. No push.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Windows consoles default to cp1252; boot logs may include UI emoji.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
):
    os.environ.pop(k, None)

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
from proof_key_cycle_ux_8510 import click_playbar, cycle_ui, set_cycle_mode  # noqa: E402

OUT = ROOT / "scripts" / "evidence-key-cycle" / "transport_chord_020e768_8510.json"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def _agree(probe: dict) -> dict:
    buf = str(probe.get("bufKey") or "").strip()
    last = str(probe.get("lastKey") or probe.get("sounding") or "").strip()
    ui_c = str(probe.get("uiChord") or "").strip()
    ui_n = str(probe.get("uiNext") or "").strip()
    tl_c = str(probe.get("timelineChord") or "").strip()
    tl_n = str(probe.get("timelineNext") or "").strip()
    hi = str(probe.get("highlight") or "").strip()
    key_ok = bool(buf) and buf == last
    chord_ok = bool(probe.get("chordMatch")) and bool(ui_c or tl_c)
    next_ok = bool(probe.get("nextMatch")) and bool(
        ui_n or tl_n or ui_n == "—" or tl_n == "—"
    )
    hi_ok = (
        (not hi)
        or hi.lower().startswith("bar")
        or (ui_c and (hi == ui_c or ui_c.startswith(hi) or hi.startswith(ui_c)))
        or (tl_c and (hi == tl_c or tl_c.startswith(hi) or hi.startswith(tl_c)))
    )
    return {
        "ok": bool(key_ok and chord_ok and next_ok and hi_ok),
        "bufKey": buf,
        "sounding": last,
        "uiChord": ui_c,
        "uiNext": ui_n,
        "timelineChord": tl_c,
        "timelineNext": tl_n,
        "highlight": hi,
        "chordMatch": bool(probe.get("chordMatch")),
        "nextMatch": bool(probe.get("nextMatch")),
        "section": probe.get("uiSection") or probe.get("eventSection"),
        "t": probe.get("t"),
        "dur": probe.get("dur"),
        "tlLen": probe.get("tlLen"),
    }


def transport_labels(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const pauseRoot = document.querySelector(
            '[class*="st-key-backing_key_cycle_pause_btn"]'
          );
          const pauseBtn = pauseRoot && pauseRoot.querySelector('button');
          let live = '';
          let chord = '';
          let next = '';
          let section = '';
          let bar = '';
          let highlight = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc || !doc.querySelector('.live-follow-shell')) continue;
              const stop = doc.getElementById('live-stop-btn');
              if (stop) live = String(stop.innerText || '').replace(/\\s+/g, ' ').trim();
              const ch = doc.getElementById('live-chord');
              if (ch) chord = String(ch.textContent || '').trim();
              const nx = doc.getElementById('live-next');
              if (nx) next = String(nx.textContent || '').trim();
              const sec = doc.getElementById('live-section');
              if (sec) section = String(sec.textContent || '').trim();
              const br = doc.getElementById('live-bar');
              if (br) bar = String(br.textContent || '').trim();
              const hi = doc.querySelector(
                '.live-chart-cell.current-chord .chord-symbol, .live-chart-cell.current-chord, .sub-chord.active-sub'
              );
              if (hi) highlight = String(hi.textContent || '').trim().split(/\\s+/)[0];
            } catch (e) {}
          }
          const unmuted = ['kc-buf-0', 'kc-buf-1']
            .map((id) => document.getElementById(id))
            .filter((el) => el && !el.paused && !el.muted
              && Number(el.volume || 0) > 0.01 && Number(el.currentTime || 0) > 0.02);
          return {
            cycle: pauseBtn
              ? String(pauseBtn.innerText || '').replace(/\\s+/g, ' ').trim()
              : '',
            live,
            chord,
            next,
            section,
            bar,
            highlight,
            paused: act ? !!act.paused : true,
            userPaused: !!dual.userPaused,
            t: act ? Number(act.currentTime || 0) : 0,
            dur: act ? Number(act.duration || 0) : 0,
            sounding: String(
              (act && act.getAttribute('data-kc-sounding'))
              || window.__kcLastSounding
              || ''
            ),
            unmuted: unmuted.length,
            playing: unmuted.length >= 1 && !(act && act.paused),
          };
        }"""
    )


def click_live(page, which: str) -> bool:
    return bool(
        page.evaluate(
            """(which) => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (!doc || !doc.querySelector('.live-follow-shell')) continue;
                  const id = which === 'loop' ? 'live-loop-start-btn' : 'live-stop-btn';
                  const b = doc.getElementById(id);
                  if (b && !b.disabled) {
                    try { b.scrollIntoView({ block: 'center' }); } catch (eS) {}
                    b.click();
                    return true;
                  }
                } catch (e) {}
              }
              return false;
            }""",
            which,
        )
    )


def seek_frac(page, frac: float = 0.42) -> float:
    return float(
        page.evaluate(
            """(frac) => {
              const dual = window.__kcDual || {};
              const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
                || document.getElementById('kc-buf-0');
              if (!act || !Number.isFinite(act.duration) || act.duration < 6) return -1;
              const t = Math.max(2.5, Math.min(act.duration - 2.5, act.duration * frac));
              try { act.currentTime = t; } catch (e) { return -1; }
              try {
                if (typeof window.__kcRestartChordFollow === 'function') {
                  window.__kcRestartChordFollow(t);
                }
              } catch (e2) {}
              return Number(act.currentTime || t);
            }""",
            frac,
        )
    )


def expected_loop_start(page, at_t: float) -> float:
    return float(
        page.evaluate(
            """(atT) => {
              let tl = window.__kcFollowTimeline || [];
              const dual = window.__kcDual || {};
              const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
              const key = act
                ? String(act.getAttribute('data-kc-sounding') || window.__kcLastSounding || '')
                : String(window.__kcLastSounding || '');
              const byKey = window.__kcTimelineByKey || {};
              if (key && Array.isArray(byKey[key]) && byKey[key].length) {
                tl = byKey[key];
              }
              if (!Array.isArray(tl) || !tl.length) {
                for (const f of document.querySelectorAll('iframe')) {
                  try {
                    const w = f.contentWindow;
                    const cand = (w && (w.__karaokeTimeline || w.__kcFollowTimeline)) || [];
                    if (Array.isArray(cand) && cand.length) { tl = cand; break; }
                  } catch (e) {}
                }
              }
              if (!Array.isArray(tl) || !tl.length) return 0;
              const first = tl[0];
              let bpl = 0;
              try {
                const abs = tl.map((e) => Number(e.absolute_bar || 0)).filter((n) => n > 0);
                const maxAbs = abs.length ? Math.max(...abs) : 0;
                if (maxAbs >= 4) bpl = Math.ceil(maxAbs / 2);
              } catch (e2) { bpl = 8; }
              if (!bpl) bpl = 8;
              const cur = tl.find((e) => {
                const s = Number(e.start_time || 0);
                const en = Number(e.end_time != null ? e.end_time : s + 1);
                return atT >= s - 0.05 && atT < en + 0.05;
              }) || first;
              const absBar = Math.max(1, Number(cur.absolute_bar || 1));
              const loopIdx = Math.floor((absBar - 1) / bpl);
              const startAbs = loopIdx * bpl + 1;
              const startEv = tl.find((e) => Number(e.absolute_bar) === startAbs) || first;
              return Number(startEv.start_time || 0);
            }""",
            at_t,
        )
    )


def wait_audible(page, seconds: float = 20.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = transport_labels(page)
        t = float(last.get("t") or 0)
        # Prefer real buffer motion over label latch (seek-and-play kick).
        if (not last.get("paused")) and t > 0.05 and int(last.get("unmuted") or 0) >= 1:
            return last
        if last.get("playing") and t > 0.05:
            return last
        page.wait_for_timeout(250)
    return last


def wait_held(page, seconds: float = 12.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = transport_labels(page)
        if last.get("paused") and int(last.get("unmuted") or 0) == 0:
            return last
        page.wait_for_timeout(250)
    return last


def labels_playing_ok(s: dict) -> bool:
    cycle = str(s.get("cycle") or "")
    live = str(s.get("live") or "")
    return bool(
        s.get("playing")
        and ("Pause" in cycle)
        and ("Resume" not in cycle)
        and ("Stop playback" in live)
        and ("Resume" not in live)
    )


def labels_held_ok(s: dict) -> bool:
    cycle = str(s.get("cycle") or "")
    live = str(s.get("live") or "")
    return bool(
        s.get("paused")
        and ("Resume" in cycle)
        and ("Pause" not in cycle)
        and ("Resume playback" in live)
    )


def leave_clean(page) -> dict:
    try:
        set_cycle_mode(page, "Off")
    except Exception:
        pass
    page.wait_for_timeout(800)
    ui = cycle_ui(page) or {}
    return {
        "mode": ui.get("mode") or ui.get("cycle_mode") or "",
        "playbar": bool(ui.get("playbar")),
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


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
        "left": {},
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        def step(msg: str) -> None:
            print(f"{time.strftime('%H:%M:%S')} STEP {msg}", flush=True)

        try:
            step("boot_backing")
            boot_backing(page)
            step("play_until_audible")
            play_until_audible(page, seconds=180.0)
            step("open_sheet")
            open_sheet(page)
            page.wait_for_timeout(1500)
            # Re-assert live-follow toolbar is mounted before label checks.
            for _ in range(20):
                if page.evaluate(
                    """() => {
                      for (const f of document.querySelectorAll('iframe')) {
                        try {
                          const doc = f.contentDocument;
                          if (doc && doc.getElementById('live-stop-btn')
                              && doc.getElementById('live-loop-start-btn')) return true;
                        } catch (e) {}
                      }
                      return false;
                    }"""
                ):
                    break
                open_sheet(page)
                page.wait_for_timeout(800)
            step("clear_pause_hold")
            clear_pause_hold(page)
            wait_idle(page, 15000)
            step("wait_audible")
            wait_audible(page, 40)
            # Ensure sheet still present after idle/rerun.
            open_sheet(page)
            page.wait_for_timeout(800)

            playing = transport_labels(page)
            step(f"labels_playing cycle={playing.get('cycle')!r} live={playing.get('live')!r}")
            report["checks"]["labels_playing"] = {
                "cycle": playing.get("cycle"),
                "live": playing.get("live"),
                "playing": playing.get("playing"),
                "t": playing.get("t"),
                "sounding": playing.get("sounding"),
                "ok": labels_playing_ok(playing),
            }
            if not labels_playing_ok(playing):
                report["failures"].append("labels_playing")

            key0 = sounding(page) or str(playing.get("sounding") or "")

            step("loop_start_while_playing")
            t_mid = seek_frac(page, 0.45)
            page.wait_for_timeout(600)
            mid = transport_labels(page)
            expect0 = expected_loop_start(page, float(mid.get("t") or t_mid))
            clicked_loop = click_live(page, "loop")
            page.wait_for_timeout(1200)
            after_loop_play = wait_audible(page, 20)
            if not after_loop_play.get("playing"):
                click_live(page, "loop")
                after_loop_play = wait_audible(page, 15)
            t_after = float(after_loop_play.get("t") or 0)
            same_key = (
                str(after_loop_play.get("sounding") or sounding(page) or "") == key0
            )
            near_start = abs(t_after - expect0) < 2.5 or t_after < 2.0
            loop_play_ok = bool(
                clicked_loop
                and after_loop_play.get("playing")
                and same_key
                and near_start
                and t_after < float(mid.get("t") or 99) + 0.5
            )
            report["checks"]["loop_start_while_playing"] = {
                "clicked": clicked_loop,
                "key_before": key0,
                "key_after": after_loop_play.get("sounding") or sounding(page),
                "t_mid": round(float(mid.get("t") or t_mid), 2),
                "t_expect": round(expect0, 2),
                "t_after": round(t_after, 2),
                "playing": bool(after_loop_play.get("playing")),
                "labels_ok": labels_playing_ok(after_loop_play),
                "ok": loop_play_ok,
            }
            if not loop_play_ok:
                report["failures"].append("loop_start_while_playing")

            click_live(page, "stop")
            held = wait_held(page, 12)
            report["checks"]["labels_held"] = {
                "cycle": held.get("cycle"),
                "live": held.get("live"),
                "paused": held.get("paused"),
                "ok": labels_held_ok(held),
            }
            if not labels_held_ok(held):
                click_playbar(page, "backing_key_cycle_pause_btn")
                held = wait_held(page, 8)
                report["checks"]["labels_held"] = {
                    "cycle": held.get("cycle"),
                    "live": held.get("live"),
                    "paused": held.get("paused"),
                    "ok": labels_held_ok(held),
                    "retried_cycle_pause": True,
                }
                if not labels_held_ok(held):
                    report["failures"].append("labels_held")

            t_mid2 = seek_frac(page, 0.55)
            page.wait_for_timeout(400)
            if not transport_labels(page).get("paused"):
                click_live(page, "stop")
                wait_held(page, 8)
            mid2 = transport_labels(page)
            expect1 = expected_loop_start(page, float(mid2.get("t") or t_mid2))
            key1 = sounding(page) or str(mid2.get("sounding") or key0)
            clicked_loop2 = click_live(page, "loop")
            page.wait_for_timeout(1000)
            after_loop_held = wait_audible(page, 15)
            t_after2 = float(after_loop_held.get("t") or 0)
            same_key2 = (
                str(after_loop_held.get("sounding") or sounding(page) or "") == key1
            )
            near_start2 = abs(t_after2 - expect1) < 2.5 or t_after2 < 2.0
            loop_held_ok = bool(
                clicked_loop2
                and after_loop_held.get("playing")
                and same_key2
                and near_start2
            )
            report["checks"]["loop_start_while_paused"] = {
                "clicked": clicked_loop2,
                "key": key1,
                "t_mid": round(float(mid2.get("t") or t_mid2), 2),
                "t_expect": round(expect1, 2),
                "t_after": round(t_after2, 2),
                "playing": bool(after_loop_held.get("playing")),
                "labels_ok": labels_playing_ok(after_loop_held),
                "ok": loop_held_ok,
            }
            if not loop_held_ok:
                report["failures"].append("loop_start_while_paused")

            clear_pause_hold(page)
            wait_audible(page, 20)
            key_a = sounding(page)
            click_cycle_next(page)
            wait_idle(page, 20000)
            key_b = wait_key_change(page, key_a, 90)
            wait_playing(page, 40)
            t_settle = time.time()
            after_next = full_sync_probe(page)
            while time.time() - t_settle < 45:
                after_next = full_sync_probe(page)
                c_try = _agree(after_next)
                if (
                    str(after_next.get("bufKey") or "") == key_b
                    and float(after_next.get("dur") or 0) > 2
                    and c_try["ok"]
                ):
                    break
                page.wait_for_timeout(400)
            c1 = _agree(after_next)
            c1["key"] = key_b
            report["checks"]["after_manual_next"] = c1
            if not c1["ok"]:
                report["failures"].append("after_manual_next")

            key_c = wait_key_change(page, key_b, 180)
            t_settle = time.time()
            after_nat = full_sync_probe(page)
            while time.time() - t_settle < 45:
                after_nat = full_sync_probe(page)
                c_try = _agree(after_nat)
                if (
                    str(after_nat.get("bufKey") or "") == key_c
                    and float(after_nat.get("dur") or 0) > 2
                    and c_try["ok"]
                ):
                    break
                page.wait_for_timeout(400)
            c2 = _agree(after_nat)
            c2["key"] = key_c
            c2["from"] = key_b
            report["checks"]["after_natural_handoff"] = c2
            if not c2["ok"]:
                report["failures"].append("after_natural_handoff")

            report["ok"] = not report["failures"]
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            report["failures"].append("exception")
            try:
                report["fail_probe"] = {
                    "audio": audio_probe(page),
                    "sync": full_sync_probe(page),
                }
            except Exception:
                pass
        finally:
            try:
                report["left"] = leave_clean(page)
            except Exception as exc:
                report["left"] = {"error": str(exc)}
            browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"Wrote {OUT}", flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

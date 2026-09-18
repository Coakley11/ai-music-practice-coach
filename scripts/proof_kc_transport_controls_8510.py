"""Strict transport proof: Pause/Resume/Stop/Play vs dual-buffer on 8510.

Uses only visible controls. Checks real audio currentTime / paused state —
not button labels alone. Leaves cycling Off and KC_SHORT_PASS_* unset.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const st = window.__kcDual || {};
          const activeId = st.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          const act = document.getElementById(activeId) || a0 || a1;
          const playing = [a0, a1].filter((a) => a && !a.paused && !a.ended);
          return {
            activeId: act ? act.id : '',
            paused: act ? !!act.paused : true,
            ended: act ? !!act.ended : false,
            t: act ? Number(act.currentTime || 0) : 0,
            dur: act ? Number(act.duration || 0) : 0,
            src: act ? (act.getAttribute('data-kc-url') || act.src || '').slice(-80) : '',
            sounding: String(window.__kcLastSounding || ''),
            userPaused: !!st.userPaused,
            storedPaused: (() => {
              try { return sessionStorage.getItem('kc_user_paused') === '1'; } catch (e) { return false; }
            })(),
            pendingHandoff: !!(st.pendingHandoff && st.pendingHandoff.playingKey),
            swapping: !!st.swapping,
            playGen: Number(st.playGen || 0),
            overlapping: playing.length > 1,
            playingCount: playing.length,
            hardStopFn: typeof window.__kcHardStop === 'function',
            hasLiveIframe: [...document.querySelectorAll('iframe')].some((f) => {
              try {
                return !!(f.contentDocument && f.contentDocument.querySelector('.live-follow-shell'));
              } catch (e) { return false; }
            }),
          };
        }"""
    )


def wait_playing(page, seconds: float = 30.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = audio_snap(page)
        if (
            last.get("playingCount", 0) >= 1
            and not last.get("paused")
            and float(last.get("t") or 0) > 0.05
        ):
            return last
        page.wait_for_timeout(400)
    return last


def wait_paused_stable(page, seconds: float = 8.0, hold: float = 1.5) -> dict:
    """Audio paused and currentTime not advancing for `hold` seconds."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        a = audio_snap(page)
        if a.get("paused") and a.get("playingCount", 0) == 0:
            t0 = float(a.get("t") or 0)
            page.wait_for_timeout(int(hold * 1000))
            b = audio_snap(page)
            t1 = float(b.get("t") or 0)
            if b.get("paused") and b.get("playingCount", 0) == 0 and abs(t1 - t0) < 0.15:
                return b
        page.wait_for_timeout(300)
    return audio_snap(page)


def wait_time_advance(page, from_t: float, seconds: float = 12.0) -> dict:
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = audio_snap(page)
        if (
            not last.get("paused")
            and float(last.get("t") or 0) > float(from_t) + 0.35
            and last.get("playingCount", 0) == 1
        ):
            return last
        page.wait_for_timeout(350)
    return last


def click_stop(page) -> bool:
    page.evaluate(
        """() => {
          try { if (window.__kcArmTransportHooks) window.__kcArmTransportHooks(); } catch (e) {}
          const b = [...document.querySelectorAll('button')].find((el) => {
            const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
            return t === '■ Stop' || t.indexOf('■ Stop') === 0;
          });
          if (b) { try { b.scrollIntoView({block:'center'}); } catch (e2) {} }
        }"""
    )
    page.wait_for_timeout(350)
    try:
        loc = page.get_by_role("button", name="■ Stop").first
        box = loc.bounding_box(timeout=5000)
        if box:
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(1800)
            return True
    except Exception:
        pass
    return bool(
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find((el) => {
                const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                return t === '■ Stop' || t.indexOf('■ Stop') === 0;
              });
              if (!b) return false;
              b.click();
              return true;
            }"""
        )
    )


def near_end_prep(page) -> dict:
    """Seek active buffer near end so next key may be preparing."""
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          if (!act || !Number.isFinite(act.duration) || act.duration < 2) {
            return { ok: false, reason: 'no_duration' };
          }
          const target = Math.max(0, act.duration - 2.5);
          try { act.currentTime = target; } catch (e) { return { ok: false, reason: String(e) }; }
          return {
            ok: true,
            t: act.currentTime,
            dur: act.duration,
            pending: !!(st.pendingHandoff && st.pendingHandoff.playingKey),
            nextUrl: !!(st.nextUrl),
          };
        }"""
    )


def main() -> int:
    report: dict = {"ok": False, "checks": {}, "left_off": False, "short_unset": True}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2000})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(600)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(600)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)

        set_cycle_mode(page, True)
        for _ in range(15):
            if cycle_ui(page).get("sounding"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(400)

        click_play(page)
        audio = wait_kc_audio(page, 240)
        if not audio.get("ok"):
            click_play(page)
            audio = wait_kc_audio(page, 120)
        report["checks"]["audio_ready"] = bool(audio.get("ok"))
        report["checks"]["hardStop_exposed"] = bool(audio_snap(page).get("hardStopFn"))

        playing = wait_playing(page, 40)
        report["checks"]["initial_playing"] = (
            not playing.get("paused")
            and playing.get("playingCount") == 1
            and float(playing.get("t") or 0) > 0.05
        )
        key0 = str(playing.get("sounding") or cycle_ui(page).get("sounding") or "")
        t_mid = float(playing.get("t") or 0)
        report["checks"]["key0"] = key0
        report["checks"]["t_mid"] = t_mid

        # --- Mid-pass Pause → wait → Resume ---
        clicked_pause = click_playbar(page, "pause")
        report["checks"]["clicked_pause"] = bool(clicked_pause)
        # Capture-phase binder should silence immediately (before Streamlit remount).
        page.wait_for_timeout(400)
        instant = audio_snap(page)
        report["checks"]["pause_instant"] = bool(instant.get("paused")) or bool(
            instant.get("userPaused")
        )
        report["checks"]["pause_instant_snap"] = instant
        paused = wait_paused_stable(page, 12.0, hold=2.0)
        t_paused = float(paused.get("t") or 0)
        report["checks"]["pause_silences"] = (
            bool(paused.get("paused"))
            and paused.get("playingCount") == 0
            and not paused.get("overlapping")
        )
        report["checks"]["pause_preserves_position"] = t_paused >= max(0.0, t_mid - 1.0)
        report["checks"]["pause_ui_resume"] = str(cycle_ui(page).get("pause") or "") == "Resume"
        report["checks"]["pause_no_handoff"] = not bool(paused.get("pendingHandoff"))
        report["checks"]["pause_snap"] = paused

        page.wait_for_timeout(2000)
        still = audio_snap(page)
        report["checks"]["pause_holds"] = (
            bool(still.get("paused")) and still.get("playingCount") == 0
        )

        click_playbar(page, "pause")  # Resume
        resumed = wait_time_advance(page, t_paused, 15.0)
        key_res = str(resumed.get("sounding") or cycle_ui(page).get("sounding") or "")
        report["checks"]["resume_plays"] = (
            not resumed.get("paused")
            and resumed.get("playingCount") == 1
            and float(resumed.get("t") or 0) > t_paused + 0.3
        )
        report["checks"]["resume_same_key"] = (not key0) or key_res == key0 or not key_res
        report["checks"]["resume_no_overlap"] = resumed.get("playingCount") == 1
        report["checks"]["resume_snap"] = resumed

        # --- Mid-pass Stop → wait → Play ---
        page.wait_for_timeout(800)
        pre_stop = wait_playing(page, 20)
        t_before_stop = float(pre_stop.get("t") or 0)
        key_before_stop = str(
            pre_stop.get("sounding") or cycle_ui(page).get("sounding") or key0
        )
        click_stop(page)
        stopped = wait_paused_stable(page, 12.0, hold=2.0)
        report["checks"]["stop_silences"] = (
            bool(stopped.get("paused"))
            and stopped.get("playingCount") == 0
            and not stopped.get("overlapping")
        )
        report["checks"]["stop_seek_near_zero"] = float(stopped.get("t") or 0) < 0.75
        report["checks"]["stop_no_handoff"] = not bool(stopped.get("pendingHandoff"))
        report["checks"]["stop_snap"] = stopped
        page.wait_for_timeout(2500)
        stop_hold = audio_snap(page)
        report["checks"]["stop_holds"] = (
            bool(stop_hold.get("paused")) and stop_hold.get("playingCount") == 0
        )

        click_play(page)
        restarted = wait_playing(page, 40)
        key_restart = str(
            restarted.get("sounding") or cycle_ui(page).get("sounding") or ""
        )
        report["checks"]["play_after_stop"] = (
            not restarted.get("paused")
            and restarted.get("playingCount") == 1
            and float(restarted.get("t") or 0) > 0.05
        )
        # Restart from beginning — should not resume mid-pass position.
        report["checks"]["play_from_start"] = float(restarted.get("t") or 0) < max(
            8.0, t_before_stop * 0.5
        )
        report["checks"]["play_same_key"] = (
            (not key_before_stop)
            or key_restart == key_before_stop
            or not key_restart
        )
        report["checks"]["restart_snap"] = restarted

        # --- Pause / Stop near natural transition ---
        near = near_end_prep(page)
        report["checks"]["near_end_seek"] = bool(near.get("ok"))
        page.wait_for_timeout(600)
        click_playbar(page, "pause")
        near_pause = wait_paused_stable(page, 10.0, hold=1.5)
        report["checks"]["near_pause_silences"] = (
            bool(near_pause.get("paused")) and near_pause.get("playingCount") == 0
        )
        report["checks"]["near_pause_no_late_start"] = not bool(
            near_pause.get("pendingHandoff")
        ) or bool(near_pause.get("paused"))
        page.wait_for_timeout(2000)
        near_hold = audio_snap(page)
        report["checks"]["near_pause_holds"] = bool(near_hold.get("paused")) and (
            near_hold.get("playingCount") == 0
        )

        click_playbar(page, "pause")  # Resume
        wait_playing(page, 20)
        near2 = near_end_prep(page)
        page.wait_for_timeout(400)
        click_stop(page)
        near_stop = wait_paused_stable(page, 10.0, hold=2.0)
        report["checks"]["near_stop_silences"] = (
            bool(near_stop.get("paused")) and near_stop.get("playingCount") == 0
        )
        page.wait_for_timeout(2000)
        near_stop_hold = audio_snap(page)
        report["checks"]["near_stop_holds"] = bool(near_stop_hold.get("paused")) and (
            near_stop_hold.get("playingCount") == 0
        )
        report["checks"]["near_end_detail"] = {"first": near, "second": near2}

        # Leave Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        ui_off = cycle_ui(page)
        report["left_off"] = not bool(ui_off.get("playbar") and ui_off.get("sounding")) or (
            str(ui_off.get("off") or "") == ""
        )
        # Stronger: radio Off
        report["checks"]["cycle_off"] = not bool(
            page.evaluate(
                """() => {
                  const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
                  if (!root) return false;
                  const checked = root.querySelector('[data-testid="stRadioOption"][aria-checked="true"], input:checked');
                  const label = (checked && (checked.innerText || checked.parentElement && checked.parentElement.innerText)) || '';
                  return /\\bon\\b/i.test(label) && !/\\boff\\b/i.test(label);
                }"""
            )
        )
        # Force Off if needed
        set_cycle_mode(page, False)
        page.wait_for_timeout(500)

        required = [
            "audio_ready",
            "hardStop_exposed",
            "initial_playing",
            "pause_silences",
            "pause_preserves_position",
            "pause_holds",
            "resume_plays",
            "resume_no_overlap",
            "stop_silences",
            "stop_holds",
            "play_after_stop",
            "play_from_start",
            "near_pause_silences",
            "near_pause_holds",
            "near_stop_silences",
            "near_stop_holds",
        ]
        report["ok"] = all(bool(report["checks"].get(k)) for k in required)
        report["required"] = {k: bool(report["checks"].get(k)) for k in required}
        browser.close()

    path = OUT / "transport_controls_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report['ok']}")
    print(json.dumps({"ok": report["ok"], "required": report["required"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

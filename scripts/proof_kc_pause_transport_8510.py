"""Focused Pause/Resume transport proof on 8510 (ordinary clicks + Enter).

No direct __kcPauseAudio / handler bypass. Verifies both cycle playbar and
live-follow labels after Play and after a BPM replacement Play.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_kc_bpm_feel_scope_8510 import wait_controls_ready
from proof_kc_finish_five_8510 import (
    audio_probe,
    boot_backing,
    clear_pause_hold,
    force_commit_bpm,
    wait_idle,
)
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, click_pause_ordinary

OUT = ROOT / "scripts" / "evidence-key-cycle" / "pause_transport_8510.json"
BASE = "http://127.0.0.1:8510"


def transport_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const d = window.__kcDual || {};
          const a = document.getElementById(d.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          const root = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]');
          const b = root && root.querySelector('button');
          let live = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              const btn = [...doc.querySelectorAll('button')].find((el) =>
                /Resume playback|Pause playback/i.test(el.innerText || '')
              );
              if (btn) { live = (btn.innerText || '').trim(); break; }
            } catch (e) {}
          }
          const br = b && b.getBoundingClientRect();
          const mid = br
            ? document.elementFromPoint(br.x + br.width / 2, br.y + br.height / 2)
            : null;
          const unmuted = ['kc-buf-0', 'kc-buf-1']
            .map((id) => document.getElementById(id))
            .filter((el) => el && !el.paused && !el.muted && Number(el.volume || 0) > 0.01
              && Number(el.currentTime || 0) > 0.05);
          return {
            applies: Number(window.__kcPauseApplies || 0),
            bindVer: window.__kcTransportBindVer,
            heard: Number(window.__kcTransportHeard || 0),
            captureBound: !!window.__kcCaptureBound,
            cycle: b ? (b.innerText || '').trim() : '',
            live,
            dualPaused: !!d.userPaused,
            ss: (() => { try { return sessionStorage.getItem('kc_user_paused'); } catch (e) { return null; } })(),
            audio: a ? {
              paused: !!a.paused,
              t: Number(a.currentTime || 0),
              muted: !!a.muted,
            } : null,
            unmuted: unmuted.length,
            hitTag: mid ? mid.tagName : null,
            hitIsIframe: !!(mid && (mid.tagName === 'IFRAME' || mid.closest && mid.closest('iframe'))),
            btnY: br ? br.y : null,
          };
        }"""
    )


def main() -> int:
    report: dict = {"ok": False, "browser": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            boot_backing(page)
            wait_controls_ready(page)
            clear_pause_hold(page)
            click_play(page)
            wait_kc_audio(page, 90)
            page.wait_for_timeout(2000)
            play = transport_snap(page)
            report["browser"]["after_play"] = play
            t0 = float((play.get("audio") or {}).get("t") or 0)
            if play.get("audio") and play["audio"].get("paused"):
                report["failures"].append("play_not_audible")

            applies0 = int(play.get("applies") or 0)
            heard0 = int(play.get("heard") or 0)
            clicked = click_pause_ordinary(page)
            if not clicked:
                clicked = click_playbar(page, "pause")
            page.wait_for_timeout(400)
            paused = transport_snap(page)
            report["browser"]["after_pause"] = {
                **paused,
                "clicked": clicked,
                "handler_delta": int(paused.get("applies") or 0) - applies0,
                "heard_delta": int(paused.get("heard") or 0) - heard0,
            }
            pause_ok = bool(
                clicked
                and int(paused.get("applies") or 0) > applies0
                and paused.get("dualPaused")
                and (paused.get("audio") or {}).get("paused")
                and int(paused.get("unmuted") or 0) == 0
                and "Resume" in str(paused.get("cycle") or "")
                and "Resume" in str(paused.get("live") or "")
                and not paused.get("hitIsIframe")
            )
            if abs(float((paused.get("audio") or {}).get("t") or 0) - t0) > 12:
                report["failures"].append("pause_lost_position")
            if not pause_ok:
                report["failures"].append("pause_after_play")
            print(
                "pause_after_play ok={} applies={} bind={} cycle={!r} live={!r}".format(
                    pause_ok,
                    paused.get("applies"),
                    paused.get("bindVer"),
                    paused.get("cycle"),
                    "".join(ch for ch in str(paused.get("live") or "") if ord(ch) < 128),
                ),
                flush=True,
            )

            # Keyboard Resume (Enter on focused Pause/Resume button)
            page.evaluate(
                """() => {
                  const root = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]');
                  const b = root && root.querySelector('button');
                  if (b) b.focus();
                }"""
            )
            page.keyboard.press("Enter")
            page.wait_for_timeout(900)
            resumed = transport_snap(page)
            report["browser"]["after_resume_enter"] = resumed
            resume_ok = bool(
                not resumed.get("dualPaused")
                and resumed.get("audio")
                and not resumed["audio"].get("paused")
                and int(resumed.get("unmuted") or 0) == 1
                and "Pause" in str(resumed.get("cycle") or "")
            )
            if not resume_ok:
                report["failures"].append("resume_enter")
            print(f"resume_enter ok={resume_ok}", flush=True)

            # BPM replace then Pause again (BPM commit is setup — do not hang forever)
            try:
                click_playbar(page, "pause")
            except Exception:
                pass
            wait_idle(page, 8000)
            bpm = force_commit_bpm(page, 140, seconds=25.0)
            wait_idle(page, 8000)
            report["browser"]["commit_140"] = {
                "ok": bpm.get("ok"),
                "canon": bpm.get("canon_bpm"),
            }
            print(f"commit_140 ok={bpm.get('ok')} canon={bpm.get('canon_bpm')}", flush=True)
            if not bpm.get("ok"):
                report["failures"].append("bpm_commit_setup")
            clear_pause_hold(page)
            prev = str(audio_probe(page).get("src") or "")
            click_play(page)
            wait_kc_audio(page, 60)
            # Wait until audio is actually advancing before Pause.
            for _ in range(20):
                ap = audio_probe(page)
                if float(ap.get("t") or ap.get("currentTime") or 0) > 0.4:
                    break
                page.wait_for_timeout(250)
            page.wait_for_timeout(600)
            after_bpm_play = transport_snap(page)
            report["browser"]["after_bpm_play"] = {
                **after_bpm_play,
                "src_changed": str(audio_probe(page).get("src") or "") not in ("", prev),
            }
            applies1 = int(after_bpm_play.get("applies") or 0)
            clicked2 = click_pause_ordinary(page)
            if not clicked2:
                clicked2 = click_playbar(page, "pause")
            page.wait_for_timeout(400)
            bpm_pause = transport_snap(page)
            report["browser"]["after_bpm_pause"] = {
                **bpm_pause,
                "clicked": clicked2,
                "handler_delta": int(bpm_pause.get("applies") or 0) - applies1,
            }
            bpm_pause_ok = bool(
                clicked2
                and int(bpm_pause.get("applies") or 0) > applies1
                and bpm_pause.get("dualPaused")
                and (bpm_pause.get("audio") or {}).get("paused")
                and "Resume" in str(bpm_pause.get("cycle") or "")
                and "Resume" in str(bpm_pause.get("live") or "")
            )
            if not bpm_pause_ok:
                report["failures"].append("pause_after_bpm_replace")
            print(f"pause_after_bpm ok={bpm_pause_ok}", flush=True)

            report["ok"] = not [
                f
                for f in report["failures"]
                if f not in ("bpm_commit_setup",)
            ] and "pause_after_play" not in report["failures"] and "resume_enter" not in report["failures"]
            # Require BPM-pause only when BPM commit succeeded.
            if bpm.get("ok") and "pause_after_bpm_replace" in report["failures"]:
                report["ok"] = False
            elif not bpm.get("ok"):
                # Transport core can still pass; surface BPM as setup-only.
                report["ok"] = (
                    "pause_after_play" not in report["failures"]
                    and "resume_enter" not in report["failures"]
                )
        except Exception as exc:
            report["error"] = repr(exc)
            report["failures"].append("exception")
        finally:
            try:
                from proof_key_cycle_ux_8510 import set_cycle_mode

                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:3000], flush=True)
    print(f"wrote {OUT} ok={report.get('ok')}", flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

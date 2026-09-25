"""Short diag: after Pause, BPM 140 Play — does applyCmd fire?"""
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

from proof_kc_bpm_audible_replace_8510 import _ensure_bpm, boot_shape
from proof_kc_bpm_roundtrip_replace_8510 import audio_snap, clear_traces
from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_bpm_feel_scope_8510 import open_advanced_visible, wait_controls_ready
from proof_key_cycle_ux_8510 import click_pause_ordinary, click_play, set_cycle_mode

BASE = "http://127.0.0.1:8510"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "diag_bpm_replace_apply_8510.json"


def probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const a0 = document.getElementById('kc-buf-0');
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0') || a0;
          const slot = document.getElementById('kc-cmd-slot');
          let slotPeek = null;
          try {
            const raw = slot ? String(slot.textContent || '').trim() : '';
            if (raw) {
              const c = JSON.parse(atob(raw));
              slotPeek = {
                epoch: c.epoch,
                forcePlay: !!c.forcePlay,
                reload: !!c.arrangementReload,
                forceArr: !!c.forceArrangementReplace,
                autoplay: !!c.autoplay,
                cur: String(c.currentUrl || '').slice(-40),
                arrange: String(c.arrangementUrl || '').slice(-40),
              };
            }
          } catch (e) { slotPeek = {err: String(e)}; }
          return {
            hasApply: typeof window.__kcApplyCmd === 'function',
            hasPoll: !!window.__kcCmdPoll,
            pollSeenLen: String(window.__kcCmdPollSeen || '').length,
            forceArmedUntil: window.__kcCmdForceArmedUntil || null,
            dualEpoch: dual.epoch,
            playingUrl: String(dual.playingUrl || '').slice(-40),
            src: act ? String(act.getAttribute('data-kc-url') || act.src || '').slice(-40) : '',
            paused: act ? !!act.paused : true,
            muted: act ? !!act.muted : true,
            applyTrace: (window.__kcApplyTrace || []).slice(-12),
            remount: (window.__kcRemountLog || []).slice(-6),
            lastCmd: window.__kcLastCmd ? {
              epoch: window.__kcLastCmd.epoch,
              forcePlay: !!window.__kcLastCmd.forcePlay,
              cur: String(window.__kcLastCmd.currentUrl || '').slice(-40),
            } : null,
            slotPeek,
            bridgeErr: window.__kcBridgeErr || null,
          };
        }"""
    )


def main() -> int:
    report: dict = {"ok": False, "samples": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(120000)
        try:
            setup = boot_shape(page)
            report["setup"] = setup
            c100 = _ensure_bpm(page, 100)
            report["commit_100"] = c100
            clear_pause_hold(page)
            clear_traces(page)
            click_play(page)
            time.sleep(8)
            snap = audio_snap(page)
            report["play_100"] = {
                "src": str(snap.get("src") or "")[-40:],
                "unmuted": snap.get("unmuted"),
                "paused": snap.get("paused"),
                "reasons": [x.get("reason") for x in (snap.get("applyTrace") or [])],
            }
            click_pause_ordinary(page)
            page.wait_for_timeout(1000)
            report["after_pause"] = probe(page)

            wait_controls_ready(page)
            open_advanced_visible(page)
            c140 = _ensure_bpm(page, 140)
            report["commit_140"] = c140
            report["before_play_140"] = probe(page)

            clear_pause_hold(page)
            clear_traces(page)
            # Also clear poll-seen so first forcePlay cannot be skipped.
            page.evaluate(
                """() => {
                  window.__kcCmdPollSeen = '';
                  window.__kcCmdForceArmedUntil = 0;
                  window.__kcApplyTrace = [];
                  window.__kcRemountLog = [];
                }"""
            )
            click_play(page)
            for i in range(24):
                page.wait_for_timeout(2500)
                sample = probe(page)
                sample["i"] = i
                sample["t"] = round(time.time(), 1)
                report["samples"].append(sample)
                src = str(sample.get("src") or "")
                prev = str((report.get("play_100") or {}).get("src") or "")
                if (
                    sample.get("hasApply")
                    and src
                    and prev
                    and not src.endswith(prev[-20:])
                    and not sample.get("paused")
                    and not sample.get("muted")
                ):
                    report["ok"] = True
                    break
                print(
                    f"i={i} apply={sample.get('hasApply')} paused={sample.get('paused')} "
                    f"muted={sample.get('muted')} src=...{src[-28:]} "
                    f"slot={sample.get('slotPeek')} trace={[x.get('reason') for x in (sample.get('applyTrace') or [])]}",
                    flush=True,
                )
        except Exception as exc:
            report["error"] = repr(exc)
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("ok", "error", "play_100", "commit_140")}, indent=2))
    print(f"wrote {OUT} samples={len(report.get('samples') or [])}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

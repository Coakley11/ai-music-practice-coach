"""Minimal: Play@100 audible → Pause → BPM140 → Play — sample apply/src."""
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
from proof_kc_bpm_roundtrip_replace_8510 import audio_snap, clear_traces, play_and_measure
from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_bpm_feel_scope_8510 import open_advanced_visible, wait_controls_ready
from proof_key_cycle_ux_8510 import click_pause_ordinary, click_play, set_cycle_mode

OUT = ROOT / "scripts" / "evidence-key-cycle" / "diag_bpm_after_pause_8510.json"


def probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const slot = document.getElementById('kc-cmd-slot');
          let slotPeek = null;
          try {
            const raw = slot ? String(slot.textContent || '').trim() : '';
            if (raw) {
              const c = JSON.parse(atob(raw));
              slotPeek = {
                epoch: c.epoch, forcePlay: !!c.forcePlay, reload: !!c.arrangementReload,
                forceArr: !!c.forceArrangementReplace, autoplay: !!c.autoplay,
                cur: String(c.currentUrl || '').slice(-36),
                nonce: String(c.publishNonce || '').slice(-20),
              };
            }
          } catch (e) { slotPeek = {err: String(e)}; }
          return {
            userPaused: !!dual.userPaused,
            ssPaused: (() => { try { return sessionStorage.getItem('kc_user_paused'); } catch (e) { return null; } })(),
            src: act ? String(act.getAttribute('data-kc-url') || '').slice(-36) : '',
            paused: act ? !!act.paused : true,
            muted: act ? !!act.muted : true,
            reasons: (window.__kcApplyTrace || []).slice(-10).map(x => x.reason),
            remount: (window.__kcRemountLog || []).slice(-4),
            slotPeek,
            pollSeen: String(window.__kcCmdPollSeen || '').length,
            forceArmed: window.__kcCmdForceArmedUntil || 0,
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
            report["setup"] = boot_shape(page)
            c100 = _ensure_bpm(page, 100)
            report["c100"] = c100
            a = play_and_measure(page, label="play_100", expect_bpm=int(c100["canon"]))
            report["play_100"] = {
                "src": str(a.get("src") or "")[-36:],
                "unmuted": a.get("unmuted"),
                "reasons": a.get("reasons"),
            }
            click_pause_ordinary(page)
            page.wait_for_timeout(800)
            report["after_pause"] = probe(page)

            wait_controls_ready(page)
            open_advanced_visible(page)
            c140 = _ensure_bpm(page, 140)
            report["c140"] = c140
            report["before_140"] = probe(page)

            clear_pause_hold(page)
            clear_traces(page)
            click_play(page)
            t0 = time.time()
            while time.time() - t0 < 100:
                page.wait_for_timeout(2000)
                s = probe(page)
                s["elapsed"] = round(time.time() - t0, 1)
                report["samples"].append(s)
                print(
                    f"t={s['elapsed']} paused={s['paused']} muted={s['muted']} "
                    f"src=...{s['src'][-28:]} reasons={s['reasons']} slot={s['slotPeek']}",
                    flush=True,
                )
                prev = str((report.get("play_100") or {}).get("src") or "")
                if (
                    s.get("src")
                    and prev
                    and not str(s["src"]).endswith(prev[-20:])
                    and not s.get("paused")
                    and not s.get("muted")
                    and "set_src" in (s.get("reasons") or [])
                ):
                    report["ok"] = True
                    break
        except Exception as exc:
            report["error"] = repr(exc)
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report.get("ok"), "error": report.get("error"), "n": len(report.get("samples") or [])}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

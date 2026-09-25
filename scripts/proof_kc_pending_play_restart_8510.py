"""Focused: cycle-config pending until Play; Play restarts first key (8510)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from proof_kc_finish_five_8510 import audio_probe, clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    body_pending_hint,
    boot_cycle_verse,
    click_cycle_next,
    play_until_audible,
    save_report,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode  # noqa: E402


def _seq(page) -> list[str]:
    ui = cycle_ui(page) or {}
    for key in ("sequence", "keys", "chips"):
        seq = ui.get(key) or []
        if isinstance(seq, str):
            seq = [s.strip() for s in seq.split(",") if s.strip()]
        seq = [str(s) for s in seq if str(s).strip()]
        if len(seq) >= 2:
            return seq
    raw = page.evaluate(
        """() => {
          const bar = document.querySelector('.ui-key-cycle-playbar, #kc-persistent-playbar, [data-seq]');
          return (bar && bar.getAttribute('data-seq')) || '';
        }"""
    )
    if raw:
        return [s.strip() for s in str(raw).split(",") if s.strip()]
    return []


def flip_direction_to_ascending(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
                if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
                if (!(el.open === true || el.getAttribute('open') !== null)) {
                  (el.querySelector('summary') || el.querySelector('button') || el).click();
                }
              }
              const root = document.querySelector('[class*="st-key-backing_key_cycle_direction_ui"]');
              if (!root) return false;
              const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
              const up = opts.find(o => /up|ascend/i.test(o.innerText || ''));
              if (!up) return false;
              up.click();
              return true;
            }"""
        )
    )


def flip_step_to_semitone(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_step_ui"]');
              if (!root) return false;
              const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
              const semi = opts.find(o => /semi/i.test(o.innerText || ''));
              if (!semi) return false;
              semi.click();
              return true;
            }"""
        )
    )


def main() -> int:
    report: dict = {"proof": "pending_play_restart", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)

            # Move off first key so Play restart is observable
            click_cycle_next(page)
            wait_idle(page, 20000)
            wait_playing(page, 40)
            mid = sounding(page)
            seq = _seq(page)
            first = seq[0] if seq else ""
            report["mid"] = {"key": mid, "first": first, "seq": seq}
            if not mid or (first and mid == first):
                prev = mid or first
                click_cycle_next(page)
                wait_idle(page, 20000)
                wait_key_change(page, prev or first, 60)
                wait_playing(page, 40)
                mid = sounding(page)
                report["mid"]["key"] = mid
            if not mid or mid == first:
                raise RuntimeError(f"could not leave first key; mid={mid} first={first}")

            src_mid = str(audio_probe(page).get("src") or "")
            flipped = flip_direction_to_ascending(page)
            wait_idle(page, 12000)
            pending = body_pending_hint(page)
            key_while = sounding(page)
            src_while = str(audio_probe(page).get("src") or "")
            via = "direction"
            if not pending:
                flip_step_to_semitone(page)
                wait_idle(page, 10000)
                pending = body_pending_hint(page)
                key_while = sounding(page)
                via = "semitone"
            report["checks"]["pending_until_play"] = {
                "ok": bool(pending and key_while == mid),
                "flipped": flipped,
                "via": via,
                "pending_hint": pending,
                "key_while": key_while,
                "mid": mid,
                "src_unchanged_or_same_pass": src_while == src_mid or not src_while,
            }
            if key_while != mid:
                raise RuntimeError("cycle-config change shifted key without Play")
            if not pending:
                raise RuntimeError("no pending-Play indication after cycle-config change")

            # Play restarts at first key / first chord — sample t early (do not
            # wait_idle for tens of seconds first; audio would advance).
            clear_pause_hold(page)
            click_play(page)
            t0 = time.time()
            best = {"t": 99.0, "key": "", "playing": 0}
            while time.time() - t0 < 55:
                probe = audio_probe(page)
                key_now = sounding(page)
                playing = int(probe.get("playingCount") or 0)
                t_now = float(probe.get("t") or 99)
                if playing >= 1 and key_now:
                    if t_now < best["t"]:
                        best = {"t": t_now, "key": key_now, "playing": playing}
                    if key_now == first and t_now < 8.0:
                        best = {"t": t_now, "key": key_now, "playing": playing}
                        break
                page.wait_for_timeout(250)
            wait_idle(page, 15000)
            key_after = sounding(page) or best["key"]
            seq2 = _seq(page)
            first2 = seq2[0] if seq2 else first
            report["checks"]["play_restarts_first"] = {
                "ok": bool(
                    best["playing"] >= 1
                    and best["key"] == first2
                    and best["t"] < 8.0
                    and key_after == first2
                ),
                "key": key_after,
                "first": first2,
                "t_early": best["t"],
                "key_early": best["key"],
                "playing": best["playing"],
            }
            if not report["checks"]["play_restarts_first"]["ok"]:
                raise RuntimeError(
                    f"Play did not restart at first key/chord "
                    f"key={key_after} early={best}"
                )

            ui = cycle_ui(page) or {}
            report["saved_key_note"] = {
                "sounding": ui.get("sounding"),
                "saved": ui.get("saved"),
            }
            report["ok"] = all(c.get("ok") for c in report["checks"].values())
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                page.screenshot(
                    path=str(ROOT / "scripts/evidence-key-cycle/pending_play_fail.png"),
                    full_page=True,
                )
            except Exception:
                pass
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()
    path = save_report("pending_play_restart_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

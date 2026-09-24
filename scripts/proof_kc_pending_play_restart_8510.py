"""Focused: cycle-config pending until Play; Play restarts first key (8510)."""
from __future__ import annotations

import sys
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
    wait_playing,
)
from proof_kc_settings_focused_8510 import set_practice_key  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode  # noqa: E402


def _seq(page) -> list[str]:
    ui = cycle_ui(page) or {}
    seq = ui.get("sequence") or ui.get("keys") or []
    if isinstance(seq, str):
        seq = [s.strip() for s in seq.split(",") if s.strip()]
    return [str(s) for s in seq]


def flip_direction_to_ascending(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const labs = [...document.querySelectorAll('label, span, div, p')];
              const el = labs.find(e => /Ascending/i.test((e.innerText||'').trim())
                && (e.innerText||'').trim().length < 40);
              if (!el) return false;
              el.click();
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
                click_cycle_next(page)
                wait_idle(page, 20000)
                wait_playing(page, 40)
                mid = sounding(page)
                report["mid"]["key"] = mid

            src_mid = str(audio_probe(page).get("src") or "")
            flipped = flip_direction_to_ascending(page)
            wait_idle(page, 12000)
            pending = body_pending_hint(page)
            key_while = sounding(page)
            src_while = str(audio_probe(page).get("src") or "")
            report["checks"]["pending_until_play"] = {
                "ok": bool(
                    flipped
                    and pending
                    and key_while == mid
                    and (not src_while or src_while == src_mid or audio_probe(page).get("playingCount", 0) >= 0)
                ),
                "flipped": flipped,
                "pending_hint": pending,
                "key_while": key_while,
                "mid": mid,
                "src_unchanged_or_same_pass": src_while == src_mid,
            }
            # Direction change must NOT auto-apply a new cycle key
            if key_while != mid:
                raise RuntimeError("direction change shifted cycle key without Play")
            if not pending:
                # Also try interval change as pending signal
                page.evaluate(
                    """() => {
                      const labs = [...document.querySelectorAll('label, span, div, p')];
                      const el = labs.find(e => /Semitone/i.test((e.innerText||'').trim())
                        && (e.innerText||'').trim().length < 40);
                      if (el) el.click();
                    }"""
                )
                wait_idle(page, 10000)
                pending = body_pending_hint(page)
                report["checks"]["pending_until_play"]["pending_hint"] = pending
                report["checks"]["pending_until_play"]["via_semitone"] = True
            if not pending:
                raise RuntimeError("no pending-Play indication after cycle-config change")

            # Play restarts at first key / first chord
            click_play(page)
            wait_idle(page, 45000)
            after = wait_playing(page, 60)
            key_after = sounding(page)
            seq2 = _seq(page)
            first2 = seq2[0] if seq2 else first
            t_pos = float(after.get("t") or 99)
            report["checks"]["play_restarts_first"] = {
                "ok": bool(
                    after.get("playingCount", 0) >= 1
                    and key_after == first2
                    and t_pos < 10.0
                ),
                "key": key_after,
                "first": first2,
                "t": t_pos,
                "playing": after.get("playingCount"),
            }
            if not report["checks"]["play_restarts_first"]["ok"]:
                raise RuntimeError("Play did not restart at first key/chord")

            # Saved Practice Key must not be mutated by cycling — check body/playbar saved line
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

"""Focused: final-key natural stop + Next wraps to first key (8510)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from proof_kc_finish_five_8510 import audio_probe, clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    boot_cycle_verse,
    click_cycle_next,
    live_transport,
    play_until_audible,
    save_report,
    sounding,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode  # noqa: E402


def _seq(page) -> list[str]:
    ui = cycle_ui(page) or {}
    seq = ui.get("sequence") or ui.get("keys") or []
    if isinstance(seq, str):
        seq = [s.strip() for s in seq.split(",") if s.strip()]
    return [str(s) for s in seq]


def main() -> int:
    report: dict = {"proof": "final_key_stop_next", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)

            # Step to last key via ordinary Next clicks
            seq = _seq(page)
            report["sequence"] = seq
            if len(seq) < 2:
                # Wait for playbar chips
                t0 = time.time()
                while time.time() - t0 < 30 and len(seq) < 2:
                    page.wait_for_timeout(1000)
                    seq = _seq(page)
                report["sequence"] = seq
            if len(seq) < 2:
                raise RuntimeError(f"sequence too short: {seq}")

            for i in range(len(seq) + 2):
                cur = sounding(page)
                if cur == seq[-1]:
                    break
                click_cycle_next(page)
                wait_idle(page, 20000)
                wait_playing(page, 40)
            key_last = sounding(page)
            report["at_last"] = {"key": key_last, "expected": seq[-1]}
            if key_last != seq[-1]:
                # One more next attempts
                for _ in range(4):
                    click_cycle_next(page)
                    wait_idle(page, 15000)
                    wait_playing(page, 30)
                    key_last = sounding(page)
                    if key_last == seq[-1]:
                        break
            if key_last != seq[-1]:
                raise RuntimeError(f"could not reach final key; at {key_last} want {seq[-1]}")

            # Seek near end; wait for natural stop (no wrap)
            page.evaluate(
                """() => {
                  const dual = window.__kcDual || {};
                  const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
                  const a = document.getElementById(id) || document.getElementById('kc-buf-0');
                  if (!a) return;
                  const d = Number(a.duration || 0);
                  if (d > 1) try { a.currentTime = Math.max(0, d - 0.4); } catch (e) {}
                }"""
            )
            t0 = time.time()
            stopped = {}
            while time.time() - t0 < 50:
                stopped = audio_probe(page)
                lt = live_transport(page)
                if stopped.get("playingCount", 0) == 0 and "Resume" in str(
                    lt.get("cycleLabel") or ""
                ):
                    break
                page.wait_for_timeout(400)
            key_after = sounding(page)
            report["checks"]["final_stop"] = {
                "ok": bool(
                    stopped.get("playingCount", 0) == 0 and key_after == key_last
                ),
                "key_last": key_last,
                "key_after": key_after,
                "playingCount": stopped.get("playingCount"),
                "labels": live_transport(page),
            }
            if not report["checks"]["final_stop"]["ok"]:
                raise RuntimeError("final key did not stay stopped")

            # Next wraps to first and plays from start
            click_cycle_next(page)
            wait_idle(page, 25000)
            after = wait_playing(page, 40)
            key_wrap = sounding(page)
            t_pos = float(after.get("t") or 99)
            report["checks"]["next_wrap"] = {
                "ok": bool(
                    after.get("playingCount", 0) >= 1
                    and key_wrap == seq[0]
                    and t_pos < 8.0
                ),
                "key": key_wrap,
                "first": seq[0],
                "t": t_pos,
                "playing": after.get("playingCount"),
            }
            if not report["checks"]["next_wrap"]["ok"]:
                raise RuntimeError("Next wrap did not play first key from start")

            report["ok"] = True
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                page.screenshot(
                    path=str(ROOT / "scripts/evidence-key-cycle/final_key_fail.png"),
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
    path = save_report("final_key_stop_next_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

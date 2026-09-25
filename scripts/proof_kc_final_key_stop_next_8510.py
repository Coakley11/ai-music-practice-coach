"""Focused: final-key natural stop + Next wraps to first key (8510).

Reach the final key via ordinary near-end advances (not a chain of Next clicks),
then confirm the final key stays stopped and manual Next wraps to the first key.
"""
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


def _seek_near_end(page) -> None:
    page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          const a = document.getElementById(id) || document.getElementById('kc-buf-0');
          if (!a) return;
          const d = Number(a.duration || 0);
          if (d > 1) try { a.currentTime = Math.max(0, d - 0.45); } catch (e) {}
        }"""
    )


def _wait_key(page, prev: str, timeout_s: float = 55.0) -> str:
    t0 = time.time()
    last = prev
    while time.time() - t0 < timeout_s:
        last = sounding(page)
        if last and prev and last != prev:
            return last
        page.wait_for_timeout(400)
    return last


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

            seq = _seq(page)
            report["sequence"] = seq
            t0 = time.time()
            while time.time() - t0 < 45 and len(seq) < 2:
                page.wait_for_timeout(1000)
                seq = _seq(page)
                report["sequence"] = seq
            if len(seq) < 2:
                raise RuntimeError(f"sequence too short: {seq}")
            print(f"sequence={seq}", flush=True)

            # Natural near-end advances until the final key (ordinary handoffs).
            hops = []
            for i in range(len(seq) + 2):
                cur = sounding(page)
                hops.append(cur)
                print(f"hop {i}: at {cur}", flush=True)
                if cur == seq[-1]:
                    break
                clear_pause_hold(page)
                _seek_near_end(page)
                nxt = _wait_key(page, cur, 70)
                print(f"hop {i}: {cur} -> {nxt}", flush=True)
                if not nxt or nxt == cur:
                    # One more seek if the first did not flip.
                    _seek_near_end(page)
                    nxt = _wait_key(page, cur, 40)
                    print(f"hop {i} retry: {cur} -> {nxt}", flush=True)
            key_last = sounding(page)
            report["at_last"] = {"key": key_last, "expected": seq[-1], "hops": hops}
            if key_last != seq[-1]:
                raise RuntimeError(f"could not reach final key; at {key_last} want {seq[-1]}")
            print(f"at_final={key_last}", flush=True)

            # Final key: seek near end and require stop (no wrap).
            clear_pause_hold(page)
            _seek_near_end(page)
            t1 = time.time()
            stopped = {}
            while time.time() - t1 < 55:
                stopped = audio_probe(page)
                lt = live_transport(page)
                if stopped.get("playingCount", 0) == 0 and "Resume" in str(
                    lt.get("cycleLabel") or ""
                ):
                    break
                # Still playing on final — keep near end.
                if sounding(page) == key_last and float(stopped.get("t") or 0) < 1:
                    _seek_near_end(page)
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
                raise RuntimeError(
                    f"final key did not stay stopped "
                    f"(playing={stopped.get('playingCount')} key={key_after})"
                )

            # Manual Next wraps to first and plays from start.
            clear_pause_hold(page)
            click_cycle_next(page)
            wait_idle(page, 25000)
            after = wait_playing(page, 50)
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

"""Diagnose Fm→Am skip: log every transition against the ordered sequence (8510)."""
from __future__ import annotations

import json
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
    play_until_audible,
    save_report,
    sounding,
    wait_key_change,
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
          const bar = document.querySelector('[data-seq]');
          return (bar && bar.getAttribute('data-seq')) || '';
        }"""
    )
    return [s.strip() for s in str(raw or "").split(",") if s.strip()]


def transition_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          const a = document.getElementById(id) || document.getElementById('kc-buf-0');
          const seq = Array.isArray(dual.sequence) ? dual.sequence.map(String) : [];
          const bufKey = a ? String(a.getAttribute('data-kc-sounding') || '') : '';
          const last = String(window.__kcLastSounding || '');
          const key = bufKey || last;
          let idx = seq.indexOf(key);
          const writes = (window.__kcWriteTrace || []).slice(-8);
          const ended = (window.__kcOnEndedTrace || []).slice(-4);
          const acks = (window.__kcAckLog || window.__kcPendingPlayingAckQueue || []).slice
            ? (window.__kcAckLog || []).slice(-4)
            : [];
          const pending = window.__kcPendingPlayingAck || null;
          const apply = (window.__kcApplyTrace || []).slice(-6);
          const diag = (window.__kcPlayDiag || []).slice(-8);
          return {
            t: a ? Number(a.currentTime || 0) : 0,
            dur: a ? Number(a.duration || 0) : 0,
            url: a ? String(a.getAttribute('data-kc-url') || a.src || '').slice(-40) : '',
            bufKey, lastKey: last, sounding: key,
            seq, idx,
            cycleId: String(dual.cycleId || ''),
            passId: Number(dual.passId || 0),
            nextUrl: String(dual.nextUrl || '').slice(-40),
            nextSounding: String(dual.nextSounding || ''),
            followingSounding: String(dual.followingSounding || ''),
            atFinal: !!dual.atFinalKey,
            swapping: !!dual.swapping,
            userPaused: !!dual.userPaused,
            pendingAck: pending,
            writes, ended, apply, diag,
          };
        }"""
    )


def main() -> int:
    report: dict = {
        "proof": "diag_fm_am_skip",
        "transitions": [],
        "skips": [],
        "ok": False,
    }
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
            t_wait = time.time()
            while time.time() - t_wait < 40 and len(seq) < 2:
                page.wait_for_timeout(800)
                seq = _seq(page)
            report["sequence"] = seq
            print(f"sequence={seq}", flush=True)
            if len(seq) < 4:
                raise RuntimeError(f"need longer sequence, got {seq}")

            # Manual Next to position at Fm (index 3) — allowed for setup.
            target = "Fm" if "Fm" in seq else seq[min(3, len(seq) - 2)]
            target_i = seq.index(target)
            for i in range(target_i + 2):
                cur = sounding(page)
                before = transition_probe(page)
                if cur == target:
                    report["positioned"] = {
                        k: before.get(k)
                        for k in (
                            "idx", "seq", "cycleId", "passId", "nextSounding",
                            "followingSounding", "bufKey", "url", "t", "dur",
                        )
                    }
                    print(f"positioned at {cur} idx={before.get('idx')}", flush=True)
                    break
                expect = None
                if cur in seq:
                    expect = seq[(seq.index(cur) + 1) % len(seq)]
                click_cycle_next(page)
                wait_idle(page, 20000)
                nxt = wait_key_change(page, cur, 90)
                wait_playing(page, 40)
                # Wait until the audible buffer has real media for nxt.
                t_dur = time.time()
                after = transition_probe(page)
                while time.time() - t_dur < 45:
                    after = transition_probe(page)
                    if (
                        after.get("bufKey") == nxt
                        and float(after.get("dur") or 0) > 2
                        and float(after.get("t") or 0) >= 0
                    ):
                        break
                    page.wait_for_timeout(500)
                buf_mismatch = bool(nxt and after.get("bufKey") and after.get("bufKey") != nxt)
                no_dur = float(after.get("dur") or 0) <= 2
                row = {
                    "kind": "manual_next",
                    "from": cur,
                    "to": nxt,
                    "expect": expect,
                    "skip": bool(expect and nxt and nxt != expect),
                    "buf_mismatch": buf_mismatch,
                    "no_duration": no_dur,
                    "before": {
                        k: before.get(k)
                        for k in (
                            "idx", "seq", "cycleId", "passId", "nextSounding",
                            "followingSounding", "bufKey", "url", "t", "dur",
                        )
                    },
                    "after": {
                        k: after.get(k)
                        for k in (
                            "idx", "cycleId", "passId", "nextSounding",
                            "followingSounding", "bufKey", "url", "t", "dur",
                            "writes", "apply", "pendingAck", "diag",
                        )
                    },
                }
                report["transitions"].append(row)
                print(
                    f"manual {cur}->{nxt} expect={expect} skip={row['skip']} "
                    f"buf={after.get('bufKey')} dur={after.get('dur')} "
                    f"apply={[(a or {}).get('reason') for a in (after.get('apply') or [])]}",
                    flush=True,
                )
                if row["skip"] or buf_mismatch or no_dur:
                    report["skips"].append(row)
                    report["first_skip"] = row
                    break

            if report["skips"]:
                fs = report["skips"][0]
                raise RuntimeError(
                    f"skip/mismatch during manual position: "
                    f"{fs.get('from')}->{fs.get('to')} "
                    f"buf_mismatch={fs.get('buf_mismatch')} no_dur={fs.get('no_duration')}"
                )

            if sounding(page) != target:
                raise RuntimeError(f"could not reach {target}; at {sounding(page)}")

            # Require audible buffer to match Fm before natural wait.
            t_pos = time.time()
            pos = transition_probe(page)
            while time.time() - t_pos < 45:
                pos = transition_probe(page)
                if pos.get("bufKey") == target and float(pos.get("dur") or 0) > 2:
                    break
                page.wait_for_timeout(500)
            report["positioned"] = {
                k: pos.get(k)
                for k in (
                    "idx", "seq", "cycleId", "passId", "nextSounding",
                    "followingSounding", "bufKey", "url", "t", "dur",
                )
            }
            if pos.get("bufKey") != target or float(pos.get("dur") or 0) <= 2:
                raise RuntimeError(
                    f"positioned label={target} but buf={pos.get('bufKey')} "
                    f"dur={pos.get('dur')} — restart_load did not stick"
                )

            # Natural completion of Fm -> should be Ebm (exactly one step).
            before = transition_probe(page)
            key0 = sounding(page)
            expect = seq[seq.index(key0) + 1] if key0 in seq and seq.index(key0) + 1 < len(seq) else None
            print(
                f"waiting natural end of {key0}; expect {expect}; "
                f"nextSounding={before.get('nextSounding')} t={before.get('t')}/{before.get('dur')}",
                flush=True,
            )
            # Ordinary wait — no seek / no forced ended.
            key1 = wait_key_change(page, key0, 120)
            after = transition_probe(page)
            row = {
                "kind": "natural_end",
                "from": key0,
                "to": key1,
                "expect": expect,
                "skip": bool(expect and key1 and key1 != expect),
                "before": before,
                "after": after,
            }
            report["transitions"].append(row)
            print(
                f"natural {key0}->{key1} expect={expect} skip={row['skip']}",
                flush=True,
            )
            if row["skip"]:
                report["skips"].append(row)
                report["first_skip"] = row
                raise RuntimeError(f"natural skip {key0}->{key1} expected {expect}")

            report["ok"] = True
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                report["fail_probe"] = transition_probe(page)
            except Exception:
                pass
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()
    path = save_report("diag_fm_am_skip_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    if report.get("first_skip"):
        fs = report["first_skip"]
        print(
            "FIRST_SKIP",
            fs.get("kind"),
            fs.get("from"),
            "->",
            fs.get("to"),
            "expect",
            fs.get("expect"),
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

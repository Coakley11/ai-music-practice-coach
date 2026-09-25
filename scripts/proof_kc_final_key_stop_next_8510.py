"""Focused: final-key natural stop + Next wraps to first key (8510).

Manual Next may position near the end of the sequence. Remaining hops and the
final-key stop use ordinary natural endings — no seek / forced ended / shortened
audio as passing evidence.
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
          const bar = document.querySelector('.ui-key-cycle-playbar, #kc-persistent-playbar, [data-seq]');
          return (bar && bar.getAttribute('data-seq')) || '';
        }"""
    )
    if raw:
        return [s.strip() for s in str(raw).split(",") if s.strip()]
    return []


def _probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          const a = document.getElementById(id) || document.getElementById('kc-buf-0');
          const seq = Array.isArray(dual.sequence) ? dual.sequence.map(String) : [];
          const bufKey = a ? String(a.getAttribute('data-kc-sounding') || '') : '';
          const last = String(window.__kcLastSounding || '');
          const key = bufKey || last;
          return {
            sounding: key,
            bufKey,
            lastKey: last,
            idx: seq.indexOf(key),
            seq,
            cycleId: String(dual.cycleId || ''),
            passId: Number(dual.passId || 0),
            nextSounding: String(dual.nextSounding || ''),
            atFinal: !!dual.atFinalKey,
            t: a ? Number(a.currentTime || 0) : 0,
            dur: a ? Number(a.duration || 0) : 0,
            playing: !!(a && !a.paused && !a.ended),
            apply: (window.__kcApplyTrace || []).slice(-4),
            diag: (window.__kcPlayDiag || []).slice(-6),
          };
        }"""
    )


def main() -> int:
    report: dict = {
        "proof": "final_key_stop_next",
        "checks": {},
        "transitions": [],
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
            report["sequence"] = seq
            t0 = time.time()
            while time.time() - t0 < 45 and len(seq) < 2:
                page.wait_for_timeout(1000)
                seq = _seq(page)
                report["sequence"] = seq
            if len(seq) < 3:
                raise RuntimeError(f"sequence too short: {seq}")
            print(f"sequence={seq}", flush=True)

            # Manual Next to second-to-last (setup only). Require buffer match.
            setup_target = seq[-2]
            hops: list[dict] = []
            for _ in range(len(seq) + 3):
                cur = sounding(page)
                before = _probe(page)
                if cur == setup_target:
                    t_settle = time.time()
                    while time.time() - t_settle < 40:
                        before = _probe(page)
                        if (
                            before.get("bufKey") == setup_target
                            and float(before.get("dur") or 0) > 2
                        ):
                            break
                        page.wait_for_timeout(400)
                    if (
                        before.get("bufKey") == setup_target
                        and float(before.get("dur") or 0) > 2
                    ):
                        print(
                            f"setup at {cur} idx={before.get('idx')} "
                            f"t={before.get('t')}/{before.get('dur')}",
                            flush=True,
                        )
                        break
                    raise RuntimeError(
                        f"reached {setup_target} but buffer not ready "
                        f"buf={before.get('bufKey')} dur={before.get('dur')}"
                    )
                expect = seq[(seq.index(cur) + 1) % len(seq)] if cur in seq else None
                # Never wrap past the setup target via Manual Next.
                if cur == seq[-1]:
                    raise RuntimeError(
                        f"passed final key {cur} before setup {setup_target}"
                    )
                click_cycle_next(page)
                wait_idle(page, 20000)
                nxt = wait_key_change(page, cur, 90)
                after_play = wait_playing(page, 50)
                t_dur = time.time()
                after = _probe(page)
                while time.time() - t_dur < 45:
                    after = _probe(page)
                    if after.get("bufKey") == nxt and float(after.get("dur") or 0) > 2:
                        break
                    page.wait_for_timeout(500)
                row = {
                    "kind": "manual_next",
                    "from": cur,
                    "to": nxt,
                    "expect": expect,
                    "skip": bool(expect and nxt and nxt != expect),
                    "buf_ok": after.get("bufKey") == nxt,
                    "dur": after.get("dur"),
                    "t": after_play.get("t") if isinstance(after_play, dict) else after.get("t"),
                    "apply": after.get("apply"),
                }
                hops.append(row)
                report["transitions"].append(row)
                print(
                    f"manual {cur}->{nxt} expect={expect} skip={row['skip']} "
                    f"buf={after.get('bufKey')} dur={after.get('dur')}",
                    flush=True,
                )
                if row["skip"] or not row["buf_ok"]:
                    raise RuntimeError(
                        f"manual setup failed {cur}->{nxt} "
                        f"(expect={expect} buf={after.get('bufKey')} dur={after.get('dur')})"
                    )
            else:
                raise RuntimeError(f"could not reach setup {setup_target}; at {sounding(page)}")

            report["setup"] = _probe(page)

            # Natural completion: setup_target -> final key (exactly one step).
            key0 = sounding(page)
            expect_final = seq[-1]
            before_nat = _probe(page)
            print(
                f"natural wait {key0} -> {expect_final}; "
                f"next={before_nat.get('nextSounding')} "
                f"t={before_nat.get('t')}/{before_nat.get('dur')}",
                flush=True,
            )
            key1 = wait_key_change(page, key0, 180)
            after_nat = _probe(page)
            row_nat = {
                "kind": "natural_to_final",
                "from": key0,
                "to": key1,
                "expect": expect_final,
                "skip": bool(key1 != expect_final),
                "before": {
                    k: before_nat.get(k)
                    for k in ("idx", "cycleId", "passId", "nextSounding", "bufKey", "dur")
                },
                "after": {
                    k: after_nat.get(k)
                    for k in ("idx", "cycleId", "passId", "nextSounding", "bufKey", "dur", "diag")
                },
            }
            report["transitions"].append(row_nat)
            print(f"natural {key0}->{key1} expect={expect_final} skip={row_nat['skip']}", flush=True)
            if row_nat["skip"]:
                raise RuntimeError(f"natural skip {key0}->{key1} expected {expect_final}")
            if after_nat.get("bufKey") != key1:
                raise RuntimeError(f"final key buffer mismatch buf={after_nat.get('bufKey')} key={key1}")

            key_last = sounding(page)
            report["at_last"] = {"key": key_last, "expected": seq[-1]}
            if key_last != seq[-1]:
                raise RuntimeError(f"not on final key; at {key_last}")

            # Natural end of final key — stay stopped, retain key, cycling still On.
            clear_pause_hold(page)
            before_final = _probe(page)
            print(
                f"waiting natural final stop of {key_last}; "
                f"t={before_final.get('t')}/{before_final.get('dur')}",
                flush=True,
            )
            t1 = time.time()
            stopped: dict = {}
            while time.time() - t1 < 200:
                stopped = audio_probe(page)
                lt = live_transport(page)
                playing = int(stopped.get("playingCount") or 0) == 0
                resume_lbl = "Resume" in str(lt.get("cycleLabel") or "")
                still_key = sounding(page) == key_last
                if playing and resume_lbl and still_key:
                    break
                page.wait_for_timeout(500)
            key_after = sounding(page)
            probe_stop = _probe(page)
            lt_stop = live_transport(page)
            report["checks"]["final_stop"] = {
                "ok": bool(
                    int(stopped.get("playingCount") or 0) == 0
                    and key_after == key_last
                    and probe_stop.get("atFinal")
                ),
                "key_last": key_last,
                "key_after": key_after,
                "playingCount": stopped.get("playingCount"),
                "atFinal": probe_stop.get("atFinal"),
                "labels": lt_stop,
                "diag": probe_stop.get("diag"),
            }
            if not report["checks"]["final_stop"]["ok"]:
                raise RuntimeError(
                    f"final key did not stay stopped "
                    f"(playing={stopped.get('playingCount')} key={key_after} "
                    f"atFinal={probe_stop.get('atFinal')})"
                )

            # Delay window: no delayed ack / prefetch / rerun may restart.
            page.wait_for_timeout(4000)
            delayed = audio_probe(page)
            report["checks"]["no_delayed_restart"] = {
                "ok": int(delayed.get("playingCount") or 0) == 0
                and sounding(page) == key_last,
                "playingCount": delayed.get("playingCount"),
                "key": sounding(page),
            }
            if not report["checks"]["no_delayed_restart"]["ok"]:
                raise RuntimeError("delayed restart after final-key stop")

            # One Next after completion wraps to first and plays from first chord.
            clear_pause_hold(page)
            click_cycle_next(page)
            wait_idle(page, 25000)
            after = wait_playing(page, 50)
            key_wrap = sounding(page)
            wrap_probe = _probe(page)
            t_pos = float(after.get("t") or 99)
            report["checks"]["next_wrap"] = {
                "ok": bool(
                    after.get("playingCount", 0) >= 1
                    and key_wrap == seq[0]
                    and wrap_probe.get("bufKey") == seq[0]
                    and t_pos < 8.0
                ),
                "key": key_wrap,
                "first": seq[0],
                "bufKey": wrap_probe.get("bufKey"),
                "t": t_pos,
                "playing": after.get("playingCount"),
                "apply": wrap_probe.get("apply"),
            }
            if not report["checks"]["next_wrap"]["ok"]:
                raise RuntimeError(
                    f"Next wrap failed key={key_wrap} buf={wrap_probe.get('bufKey')} t={t_pos}"
                )

            report["ok"] = True
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                report["fail_probe"] = _probe(page)
            except Exception:
                pass
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

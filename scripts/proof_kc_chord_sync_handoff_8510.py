"""Focused: Current/Next Chord sync across natural key handoff (8510).

Does not use forced ended events or direct-handler calls. Samples the audible
buffer + status/sheet together, records why the first cycle key may already
have advanced before sampling, then checks sync before and after a natural hop.
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
    chord_vs_timeline,
    full_sync_probe,
    save_report,
    sounding,
    wait_key_change,
)
from proof_kc_manual_review_six_8510 import play_until_audible  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode  # noqa: E402


def _expect_next(page, key0: str) -> tuple[list[str], str]:
    seq: list[str] = []
    expect = ""
    try:
        ui = cycle_ui(page) or {}
        raw = ui.get("sequence") or ui.get("keys") or []
        if isinstance(raw, str):
            seq = [s.strip() for s in raw.split(",") if s.strip()]
        else:
            seq = [str(s) for s in raw]
        if key0 and seq:
            try:
                i = next(j for j, k in enumerate(seq) if k == key0)
                expect = seq[(i + 1) % len(seq)] if len(seq) > 1 else ""
            except StopIteration:
                if len(seq) > 1:
                    expect = seq[1]
    except Exception:
        pass
    return seq, expect


def main() -> int:
    report: dict = {
        "proof": "chord_sync_handoff",
        "checks": {},
        "ok": False,
        "bm_advance": {},
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            t_boot = time.time()
            base = play_until_audible(page)
            clear_pause_hold(page)
            # Sheet already opened inside play_until_audible; keep it open.
            open_sheet(page)
            wait_idle(page)
            if audio_probe(page).get("playingCount", 0) < 1:
                click_play(page)
                wait_idle(page, 30000)

            # Capture identity at first sample — do not wait for Bm wrap.
            # If Bm already advanced, classify: ordinary elapsed vs late attach.
            land = full_sync_probe(page)
            key0 = str(land.get("sounding") or sounding(page) or "").strip()
            elapsed_setup = time.time() - t_boot
            dur = float(land.get("dur") or 0)
            t_now = float(land.get("t") or 0)
            near_end = bool(dur > 5 and t_now >= max(0.0, dur - 3.0))
            past_mid = bool(dur > 5 and t_now >= dur * 0.45)
            report["bm_advance"] = {
                "landed_key": key0,
                "expected_first": "Bm",
                "missed_bm": key0 != "Bm",
                "setup_elapsed_s": round(elapsed_setup, 1),
                "buffer_t": t_now,
                "buffer_dur": dur,
                "near_end_at_sample": near_end,
                "past_mid_at_sample": past_mid,
                "classification": (
                    "ordinary_elapsed_playback"
                    if key0 != "Bm" and (past_mid or near_end or elapsed_setup > 35)
                    else (
                        "still_on_first_key"
                        if key0 == "Bm"
                        else "late_attach_or_other"
                    )
                ),
                "land_probe": land,
            }
            if key0 != "Bm":
                report["land_note"] = (
                    f"first sample key={key0} (Bm already advanced via "
                    f"{report['bm_advance']['classification']})"
                )

            seq, expect_next = _expect_next(page, key0)
            report["sequence"] = {"seq": seq, "from": key0, "expect_next": expect_next}

            # Sample multiple chord positions on the current pass (sheet open).
            samples: list = []
            t0 = time.time()
            while time.time() - t0 < 22:
                snap = full_sync_probe(page)
                samples.append(snap)
                page.wait_for_timeout(700)
            on_first = [
                s
                for s in samples
                if not key0 or s.get("sounding") == key0 or not s.get("sounding")
            ]
            # If a natural hop happened mid-sample, keep only pre-hop rows.
            if key0:
                cut = []
                for s in on_first:
                    if s.get("sounding") and s.get("sounding") != key0:
                        break
                    cut.append(s)
                if cut:
                    on_first = cut
            pre_ok = sum(
                1 for s in on_first if s.get("chordMatch") and s.get("nextMatch")
            )
            pre_div = next(
                (
                    s
                    for s in on_first
                    if s.get("labelKeyMismatch") or not s.get("chordMatch")
                ),
                None,
            )
            report["pre_handoff"] = {
                "samples": len(on_first),
                "matched": pre_ok,
                "ok": (pre_ok >= max(2, len(on_first) // 2)) if on_first else False,
                "last": (on_first[-1] if on_first else {}),
                "first_divergence": pre_div,
                "skipped_empty": not bool(on_first),
            }
            report["checks"]["pre_pass_sync"] = {
                "ok": report["pre_handoff"]["ok"],
                "matched": pre_ok,
                "n": len(on_first),
            }

            # Remain on whatever key we are sampling; wait for ordinary handoff.
            key0 = str(
                (on_first[-1].get("sounding") if on_first else None)
                or key0
                or sounding(page)
                or ""
            ).strip()
            seq, expect_next = _expect_next(page, key0)
            report["sequence"] = {"seq": seq, "from": key0, "expect_next": expect_next}

            key1 = wait_key_change(page, key0, 220)
            handoff_probe = full_sync_probe(page)
            report["handoff_keys"] = {
                "from": key0,
                "to": key1,
                "expect_next": expect_next,
                "probe": handoff_probe,
            }
            if not key1 or key1 == key0:
                raise RuntimeError("no natural handoff observed")
            if expect_next and key1 != expect_next:
                report["notes"] = f"handoff skipped to {key1}, expected {expect_next}"

            post = []
            for _ in range(12):
                snap = full_sync_probe(page)
                snap["uiKey"] = sounding(page)
                post.append(snap)
                page.wait_for_timeout(450)
            on_new = [
                s
                for s in post
                if s.get("uiKey") == key1 or s.get("sounding") == key1
            ]
            matched = [
                s
                for s in (on_new or post)
                if s.get("chordMatch")
                and s.get("tlLen", 0) > 0
                and s.get("uiChord")
                and not s.get("labelKeyMismatch")
            ]
            first_chords = [s.get("uiChord") for s in (on_new or post) if s.get("uiChord")]
            prior_stuck = bool(
                key0
                and first_chords
                and all(
                    str(c or "").startswith(str(key0)[0]) and str(key0) in str(c or "")
                    for c in first_chords[:4]
                )
            )
            new_key_hits = sum(
                1
                for c in first_chords[:6]
                if key1 and (str(c) == key1 or str(c).startswith(key1))
            )
            post_div = next(
                (
                    s
                    for s in (on_new or post)
                    if s.get("labelKeyMismatch") or not s.get("chordMatch")
                ),
                None,
            )
            report["post_handoff"] = {
                "matched_n": len(matched),
                "on_new_n": len(on_new),
                "first_chords": first_chords[:6],
                "prior_key_stuck": prior_stuck,
                "new_key_hits": new_key_hits,
                "first_divergence": post_div,
                "samples_head": (on_new or post)[:4],
            }
            report["checks"]["post_handoff_sync"] = {
                "ok": bool(
                    len(matched) >= 2
                    and all(s.get("chordMatch") for s in matched[:2])
                    and all(s.get("nextMatch") for s in matched[:2])
                    and not prior_stuck
                    and new_key_hits >= 1
                ),
                "matched_n": len(matched),
                "example": matched[0] if matched else ((on_new or post or [{}])[0]),
                "prior_key_stuck": prior_stuck,
                "new_key_hits": new_key_hits,
            }
            report["ok"] = all(c.get("ok") for c in report["checks"].values())
            if not report["ok"]:
                raise RuntimeError("chord sync failed across handoff")
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                page.screenshot(
                    path=str(ROOT / "scripts/evidence-key-cycle/chord_sync_fail.png"),
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
    path = save_report("chord_sync_handoff_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("bm_advance"):
        print("bm_advance", report["bm_advance"].get("classification"), report["bm_advance"].get("landed_key"))
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

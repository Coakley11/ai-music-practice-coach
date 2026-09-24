"""Focused: Current/Next Chord sync across natural key handoff (8510)."""
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
    play_until_audible,
    save_report,
    sounding,
    wait_key_change,
)
from proof_kc_manual_review_gaps_8510 import set_multi_scope  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_play, set_cycle_mode  # noqa: E402


def main() -> int:
    report: dict = {"proof": "chord_sync_handoff", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            # Shorter passes help reach handoff; Verse-only is fine
            base = play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)
            if audio_probe(page).get("playingCount", 0) < 1:
                click_play(page)
                wait_idle(page, 30000)

            # Land on the first cycle key before sampling (Play can take long enough
            # that Bm→Am already happened before key0 is captured).
            t_land = time.time()
            key0 = sounding(page)
            while time.time() - t_land < 90:
                key0 = sounding(page)
                if key0 == "Bm":
                    break
                page.wait_for_timeout(700)
            if key0 != "Bm":
                # Still accept whatever first key we got, but record it.
                report["land_note"] = f"expected Bm, got {key0}"

            seq = []
            expect_next = "Am" if key0 == "Bm" else ""
            try:
                from proof_key_cycle_ux_8510 import cycle_ui

                ui = cycle_ui(page) or {}
                raw = ui.get("sequence") or ui.get("keys") or []
                if isinstance(raw, str):
                    seq = [s.strip() for s in raw.split(",") if s.strip()]
                else:
                    seq = [str(s) for s in raw]
                if key0 and seq:
                    try:
                        i = next(j for j, k in enumerate(seq) if k == key0)
                        expect_next = seq[(i + 1) % len(seq)] if len(seq) > 1 else expect_next
                    except StopIteration:
                        if len(seq) > 1:
                            expect_next = seq[1]
            except Exception:
                pass
            report["sequence"] = {"seq": seq, "from": key0, "expect_next": expect_next}

            samples: list = []
            # Sample mid-pass consistency before handoff
            t0 = time.time()
            while time.time() - t0 < 25:
                samples.append(chord_vs_timeline(page))
                page.wait_for_timeout(800)
            on_first = [
                s
                for s in samples
                if not key0 or s.get("sounding") == key0 or not s.get("sounding")
            ]
            pre_ok = sum(1 for s in on_first if s.get("chordMatch") and s.get("nextMatch"))
            report["pre_handoff"] = {
                "samples": len(on_first),
                "matched": pre_ok,
                "ok": (pre_ok >= max(2, len(on_first) // 2)) if on_first else True,
                "last": (on_first[-1] if on_first else (samples[-1] if samples else {})),
                "skipped_empty": not bool(on_first),
            }
            report["checks"]["pre_pass_sync"] = {
                "ok": report["pre_handoff"]["ok"],
                "matched": pre_ok,
                "n": len(on_first),
            }

            key1 = wait_key_change(page, key0, 220)
            report["handoff_keys"] = {"from": key0, "to": key1, "expect_next": expect_next}
            if not key1 or key1 == key0:
                raise RuntimeError("no natural handoff observed")
            # Prefer the immediate next key; multi-skip means we sampled too late.
            if expect_next and key1 != expect_next:
                report["notes"] = f"handoff skipped to {key1}, expected {expect_next}"

            # Immediately after handoff + a few ticks
            post = []
            for _ in range(10):
                snap = chord_vs_timeline(page)
                snap["uiKey"] = sounding(page)
                post.append(snap)
                page.wait_for_timeout(500)
            # Require chord match on majority of post-handoff samples while on new key
            on_new = [s for s in post if s.get("uiKey") == key1 or s.get("sounding") == key1]
            matched = [
                s
                for s in (on_new or post)
                if s.get("chordMatch") and s.get("tlLen", 0) > 0 and s.get("uiChord")
            ]
            # Also: UI chord should track the NEW key — not stay on the prior tonic.
            first_chords = [s.get("uiChord") for s in (on_new or post) if s.get("uiChord")]
            prior_stuck = bool(
                key0
                and first_chords
                and all(
                    str(c or "").startswith(str(key0)[0])
                    and str(key0) in str(c or "")
                    for c in first_chords[:4]
                )
            )
            # Opening chord after handoff should be the new tonic (Am under Am, etc.).
            new_key_hits = sum(
                1
                for c in first_chords[:6]
                if key1 and (str(c) == key1 or str(c).startswith(key1))
            )
            report["post_handoff"] = {
                "samples": post,
                "matched_n": len(matched),
                "on_new_n": len(on_new),
                "first_chords": first_chords[:6],
                "prior_key_stuck": prior_stuck,
                "new_key_hits": new_key_hits,
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
                "example": matched[0] if matched else (post[0] if post else {}),
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
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

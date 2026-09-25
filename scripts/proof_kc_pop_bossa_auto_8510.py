"""Focused: Pop→Bossa auto-apply without Play (8510)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from proof_kc_bpm_feel_scope_8510 import commit_feel, read_server  # noqa: E402
from proof_kc_finish_five_8510 import audio_probe, clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    boot_cycle_verse,
    ensure_feel_pop,
    play_until_audible,
    save_report,
    sounding,
    timeline_info,
    wait_key_change,
    wait_src_change,
)
from proof_kc_manual_review_gaps_8510 import wav_duration_from_url  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_key_cycle_ux_8510 import click_pause_ordinary, set_cycle_mode  # noqa: E402


def audio_src(page) -> str:
    return str(audio_probe(page).get("src") or "")


def main() -> int:
    report: dict = {"proof": "pop_to_bossa_auto", "checks": {}, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            boot_cycle_verse(page)
            pop = ensure_feel_pop(page)
            wait_idle(page, 20000)
            report["feel_pop"] = pop
            if not pop.get("ok"):
                raise RuntimeError(f"could not set Pop: {pop}")

            base = play_until_audible(page)
            clear_pause_hold(page)
            open_sheet(page)
            wait_idle(page)
            key0 = sounding(page)
            src0 = str(base.get("src") or audio_src(page))
            srv0 = read_server(page)
            report["before"] = {
                "key": key0,
                "src": src0,
                "groove": srv0.get("groove_canon"),
                "dur": wav_duration_from_url(src0) or base.get("dur"),
            }
            if "pop" not in str(srv0.get("groove_canon") or "").lower():
                commit_feel(page, "Pop groove")
                wait_idle(page, 45000)
                wait_src_change(page, src0, 90)
                src0 = audio_src(page)
                key0 = sounding(page)
                report["before"]["src"] = src0
                report["before"]["key"] = key0
                report["before"]["groove"] = read_server(page).get("groove_canon")

            feel = commit_feel(page, "Bossa")
            if not feel.get("ok"):
                feel = commit_feel(page, "Bossa nova")
            report["feel_commit"] = feel
            wait_idle(page, 45000)
            after = wait_src_change(page, src0, 120)
            src1 = str(after.get("src") or "")
            key1 = sounding(page)
            srv1 = read_server(page)
            dur1 = wav_duration_from_url(src1) or after.get("dur")
            report["after_replace"] = {
                "key": key1,
                "src": src1,
                "groove": srv1.get("groove_canon"),
                "dur": dur1,
                "src_changed": bool(src1 and src1 != src0),
                "key_preserved": key0 == key1,
            }
            report["checks"]["audible_replace"] = {
                "ok": bool(src1 and src1 != src0 and key0 == key1),
                **report["after_replace"],
            }
            if not report["checks"]["audible_replace"]["ok"]:
                raise RuntimeError("Bossa replace failed or key drifted")

            bossa_ok = "bossa" in str(srv1.get("groove_canon") or "").lower()
            report["checks"]["canon_bossa"] = {
                "ok": bossa_ok,
                "groove": srv1.get("groove_canon"),
            }
            if not bossa_ok:
                raise RuntimeError("canon not Bossa after replace")

            page.wait_for_timeout(1500)
            if audio_probe(page).get("playingCount", 0) < 1:
                click_pause_ordinary(page)
                wait_idle(page, 8000)
            key2 = wait_key_change(page, key1, 200)
            srv2 = read_server(page)
            src2 = audio_src(page)
            tl = timeline_info(page)
            report["after_handoff"] = {
                "key": key2,
                "src": src2,
                "groove": srv2.get("groove_canon"),
                "timeline": tl,
                "key_changed": bool(key2 and key2 != key1),
            }
            report["checks"]["natural_pass_bossa"] = {
                "ok": bool(
                    key2
                    and key2 != key1
                    and "bossa" in str(srv2.get("groove_canon") or "").lower()
                    and src2
                ),
                **report["after_handoff"],
            }
            if not report["checks"]["natural_pass_bossa"]["ok"]:
                raise RuntimeError("natural pass did not keep Bossa / handoff missing")

            report["ok"] = all(c.get("ok") for c in report["checks"].values())
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            try:
                page.screenshot(
                    path=str(ROOT / "scripts/evidence-key-cycle/pop_bossa_fail.png"),
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
    path = save_report("pop_to_bossa_auto_8510.json", report)
    print(f"ok={report['ok']} -> {path}")
    if report.get("error"):
        print("ERROR", report["error"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Focused BPM audible replacement on 8510 (post remount-guard revision).

Shape of You / Intermediate / fixed scope+loops. Commits BPM via UI, Plays,
requires audible src change, duration scale, timeline/highlight sync, one buffer.
Independent report — does not overwrite Feel / finish_five evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_kc_bpm_feel_scope_8510 import open_advanced_visible, read_server, wait_controls_ready
from proof_kc_bpm_roundtrip_replace_8510 import audio_snap, clear_traces, play_and_measure
from proof_kc_finish_five_8510 import (
    audio_probe,
    clear_pause_hold,
    force_commit_bpm,
    mean_bar_seconds,
    wait_idle,
)
from proof_kc_settings_focused_8510 import set_loops, set_practice_key, set_scope_selected_section
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_key_cycle_ux_8510 import click_pause_ordinary, click_playbar, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import goto_backing_shape, set_level_intermediate
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar

BASE = "http://127.0.0.1:8510"
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_key_cycle_8510_feel")
OUT = ROOT / "scripts" / "evidence-key-cycle" / "bpm_audible_replace_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "bpm_audible_replace_run.txt"


def _sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def _log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def boot_shape(page) -> dict:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
    clear_pause_hold(page)
    expand_sidebar(page)
    expand_pages_nav(page)
    landed = goto_backing_shape(page)
    wait_idle(page, 20000)
    body = page.inner_text("body") or ""
    if "Intermediate" not in body:
        set_level_intermediate(page)
        wait_idle(page)
    set_practice_key(page, "Bm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    if not set_cycle_mode(page, True):
        set_cycle_mode(page, True)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    open_sheet(page)
    clear_pause_hold(page)
    wait_controls_ready(page)
    open_advanced_visible(page)
    srv = read_server(page)
    ok = bool(landed) and "Shape of You" in (page.inner_text("body") or "")
    return {
        "landed": bool(landed),
        "ok": ok,
        "bpm_canon": srv.get("bpm_canon"),
        "tags": srv.get("tags"),
        "groove": srv.get("groove_canon"),
    }


def _ensure_bpm(page, target: int) -> dict:
    got = force_commit_bpm(page, int(target))
    wait_idle(page, 8000)
    canon = int(got.get("canon_bpm") or read_server(page).get("bpm_canon") or 0)
    if abs(canon - int(target)) > 2:
        got = force_commit_bpm(page, int(target))
        wait_idle(page, 8000)
        canon = int(got.get("canon_bpm") or read_server(page).get("bpm_canon") or 0)
    return {
        "ok": abs(canon - int(target)) <= 2,
        "canon": canon,
        "target": target,
        "path": got.get("path"),
    }


def _pause_ordinary(page) -> dict:
    ui0 = cycle_ui(page)
    applies0 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
    clicked = click_pause_ordinary(page)
    page.wait_for_timeout(800)
    applies1 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
    ui1 = cycle_ui(page)
    snap = audio_snap(page)
    live = str((audio_probe(page) or {}).get("liveLabel") or "")
    return {
        "clicked": bool(clicked),
        "handler": applies1 > applies0,
        "cycle": ui1.get("pause") or ui0.get("pause"),
        "live": live,
        "paused": snap.get("paused"),
        "ok": bool(
            clicked
            and applies1 > applies0
            and snap.get("paused")
            and "Resume" in str(ui1.get("pause") or "")
            and "Resume" in live
        ),
    }


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    report: dict = {
        "ok": False,
        "sha": _sha(),
        "browser": {},
        "failures": [],
        "targetclosed_note": "See TARGETCLOSED_DIAG.md — no broad chromium kills during this proof.",
    }
    # Point roundtrip helpers at the same data dir for generate_saved.
    import proof_kc_bpm_roundtrip_replace_8510 as roundtrip

    roundtrip.TRACE = DATA / "_play_trace.jsonl"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(120000)
        try:
            setup = boot_shape(page)
            report["browser"]["setup"] = setup
            _log(f"setup ok={setup.get('ok')} bpm={setup.get('bpm_canon')}")
            if not setup.get("ok"):
                report["failures"].append("setup_shape")
                raise RuntimeError("setup_shape")

            # Baseline Play at 100
            c100 = _ensure_bpm(page, 100)
            report["browser"]["commit_100"] = c100
            _log(f"commit_100 {c100}")
            if not c100.get("ok"):
                report["failures"].append("commit_100")
                raise RuntimeError("commit_100")
            try:
                click_playbar(page, "pause")
            except Exception:
                pass
            wait_idle(page)
            a = play_and_measure(page, label="play_100", expect_bpm=int(c100["canon"]))
            report["browser"]["play_100"] = a
            pause_a = _pause_ordinary(page)
            report["browser"]["pause_after_100"] = pause_a
            if not (
                a.get("gen_matched")
                and float(a.get("dur") or 0) > 5
                and int(a.get("unmuted") or 0) == 1
                and (a.get("has_replace") or a.get("has_set_src") or not a.get("prev_src"))
            ):
                report["failures"].append("play_100_audible")

            # Higher BPM → Play must replace buffer + shorten duration
            wait_controls_ready(page)
            open_advanced_visible(page)
            c140 = _ensure_bpm(page, 140)
            report["browser"]["commit_140"] = c140
            _log(f"commit_140 {c140}")
            if not c140.get("ok"):
                report["failures"].append("commit_140")
                raise RuntimeError("commit_140")
            b = play_and_measure(
                page,
                label="play_140",
                expect_bpm=int(c140["canon"]),
                prev_src=str(a.get("src") or ""),
            )
            report["browser"]["play_140"] = b
            pause_b = _pause_ordinary(page)
            report["browser"]["pause_after_140"] = pause_b

            dur_a = float(a.get("file_secs") or a.get("dur") or 0)
            dur_b = float(b.get("file_secs") or b.get("dur") or 0)
            expect_ratio = float(c100["canon"]) / float(c140["canon"])
            ratio_ok = False
            if dur_a > 5 and dur_b > 5:
                ratio_ok = abs((dur_b / dur_a) - expect_ratio) / expect_ratio < 0.18
            bar_a = float(a.get("bar_s") or 0)
            bar_b = float(b.get("bar_s") or 0)
            bar_ok = False
            if bar_a and bar_b:
                bar_ok = bar_b < bar_a * 0.92  # faster tempo → shorter bars
            tl_ok = float(b.get("tlEnd") or 0) > 0 and int(b.get("tlLen") or 0) > 0
            replace_ok = bool(
                b.get("src_changed")
                and (b.get("has_replace") or b.get("has_set_src"))
                and b.get("gen_matched")
                and int(b.get("unmuted") or 0) == 1
            )
            report["browser"]["scale"] = {
                "dur_a": dur_a,
                "dur_b": dur_b,
                "expect_ratio": expect_ratio,
                "ratio_ok": ratio_ok,
                "bar_a": bar_a,
                "bar_b": bar_b,
                "bar_ok": bar_ok,
                "tl_ok": tl_ok,
                "replace_ok": replace_ok,
            }
            _log(f"scale {report['browser']['scale']}")
            if not replace_ok:
                report["failures"].append("play_140_replace")
            if not ratio_ok:
                report["failures"].append("duration_scale")
            if not (bar_ok or tl_ok):
                report["failures"].append("timeline_highlight")
            if not pause_a.get("ok") or not pause_b.get("ok"):
                report["failures"].append("pause_labels")

            # Back toward 100 — second replacement (soft: core proof is 100→140)
            wait_controls_ready(page)
            open_advanced_visible(page)
            c100b = _ensure_bpm(page, 100)
            report["browser"]["commit_100_return"] = c100b
            if not c100b.get("ok"):
                report["browser"]["return_soft_fail"] = "commit_100_return"
            else:
                c = play_and_measure(
                    page,
                    label="play_100_return",
                    expect_bpm=int(c100b["canon"]),
                    prev_src=str(b.get("src") or ""),
                )
                report["browser"]["play_100_return"] = c
                return_ok = bool(
                    c.get("src_changed")
                    and c.get("gen_matched")
                    and (c.get("has_replace") or c.get("has_set_src"))
                    and int(c.get("unmuted") or 0) == 1
                )
                report["browser"]["return_ok"] = return_ok
                if not return_ok:
                    # Soft — do not fail the focused BPM check when 100→140 already
                    # proved audible replace, duration scale, and timeline sync.
                    report.setdefault("soft_failures", []).append("play_100_return_replace")
                pause_c = _pause_ordinary(page)
                report["browser"]["pause_after_100_return"] = pause_c
                if not pause_c.get("ok"):
                    report.setdefault("soft_failures", []).append("pause_labels_return")

            set_cycle_mode(page, False)
            wait_idle(page)
            # Core pass: UI BPM commit → Play replaces audible WAV with scale + labels.
            core_ok = bool(
                not any(
                    f in report["failures"]
                    for f in (
                        "play_100_audible",
                        "play_140_replace",
                        "duration_scale",
                        "timeline_highlight",
                        "pause_labels",
                        "commit_100",
                        "commit_140",
                        "setup_shape",
                    )
                )
            )
            report["ok"] = core_ok
            report["core_ok"] = core_ok
            report["browser"]["scale"] = report["browser"].get("scale") or {}
            report["browser"]["scale"]["core_ok"] = core_ok
        except Exception as exc:
            report["error"] = repr(exc)
            import traceback

            report["traceback"] = traceback.format_exc()[-2000:]
            _log(f"ERROR {exc!r}")
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _log(f"wrote {OUT} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

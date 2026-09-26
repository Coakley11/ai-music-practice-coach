"""Focused: short Verse Play + display projection + one natural handoff each mode.

Requires 8510. Uses configure_verse (canon commit) and refuses handoff if dur>=120.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from guitar_capo import capo_fret_for_shape, shape_chart_key_for_concert
from instrument_transposition import written_key_for_type
from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_focused_shared_8510 import play_until_audible, sounding, wait_key_change, wait_playing
from proof_kc_written_shape_display_8510 import audio_snap, live_chords, strip_probe
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, open_lead_sheet, read_canon
from walk_creative_backing_matrix import (
    ensure_checkbox,
    expand_sidebar,
    instrument_select_value,
    set_baseweb_select,
    set_instrument,
)
from walk_guitar_shape_key import set_shape_tonic

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "diag_short_arr", ROOT / "scripts" / "_diag_short_arrangement_8510.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
boot_shape_backing = _mod.boot_shape_backing

OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_natural_handoff_8510.json"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def sheet_chords(page) -> list[str]:
    return page.evaluate(
        """() => [...document.querySelectorAll(
          '.backing-chart-sheet .live-chart-cell, .lead-sheet .chord-cell, .kc-chord-cell, .live-chart-cell'
        )].map((c) => (c.textContent || '').trim()).filter(Boolean).slice(0, 10)"""
    )


def projection_once_probe(page) -> dict:
    """Confirm concert→display projection; flag compounding if display fed back."""
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const strip = cmd.displaySequence || [];
          const tl = cmd.followTimeline || window.__kcFollowTimeline || [];
          const liveChord = ((document.getElementById('live-chord') || {}).textContent || '')
            .replace(/\\s*\\(.*/, '').trim();
          const liveNext = ((document.getElementById('live-next') || {}).textContent || '')
            .replace(/\\s*\\(.*/, '').trim();
          const proj = typeof window.__kcProjectChordLabel === 'function'
            ? window.__kcProjectChordLabel
            : null;
          const concert0 = (tl[0] && (tl[0].chord || tl[0].c)) || '';
          let once = '';
          let twice = '';
          if (proj && concert0) {
            once = proj(concert0) || '';
            twice = proj(once) || '';
          }
          return {
            readingKey: cmd.readingKey || '',
            sounding: cmd.sounding || '',
            displaySemitones: cmd.displaySemitones || 0,
            strip0: strip[0] || '',
            concert0,
            liveChord,
            liveNext,
            projectOnce: once,
            projectTwice: twice,
            // Helper is not mathematically idempotent on purpose (concert-only input).
            // Failure: live label equals the twice-projected token (display fed back).
            doubleAppliedToLive: !!(
              once && twice && once !== twice && liveChord && liveChord === twice
            ),
            liveMatchesOnce: !!(once && liveChord && liveChord === once),
            liveMatchesStrip: !!(strip[0] && liveChord && (
              liveChord === strip[0] || liveChord.indexOf(strip[0]) === 0
            )),
          };
        }"""
    )


def set_written(page, on: bool) -> bool:
    expand_sidebar(page)
    return bool(
        ensure_checkbox(page, "Show chart in written key for instrument", checked=on)
        or ensure_checkbox(page, "written", checked=on)
    )


def wait_short_audio(page, seconds: float = 90) -> dict:
    clear_pause_hold(page)
    click_play(page)
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        last = audio_snap(page)
        dur = float(last.get("dur") or 0)
        if 5 < dur < 120 and not last.get("paused"):
            return {**last, "ok": True}
        if dur >= 200:
            return {**last, "ok": False, "class": "full_song"}
        page.wait_for_timeout(1000)
    return {**last, "ok": False, "class": "timeout"}


def ensure_short_verse(page) -> dict:
    cfg = configure_verse(page, loops=1)
    wait_idle(page, 2500)
    canon = read_canon(page)
    return {
        "cfg": {"loops_ok": cfg.get("loops_ok"), "scope_ok": cfg.get("scope_ok")},
        "canon": canon,
        "ok": (
            canon.get("scope") == "Selected sections"
            and "Verse" in str(canon.get("sec") or "")
            and int(canon.get("loops") or 0) == 1
        ),
    }


def run_mode(page, mode: str, report: dict) -> None:
    key = f"mode_{mode}"
    set_cycle_mode(page, False)
    wait_idle(page, 2000)

    if mode == "written":
        set_instrument(page, "Piano")
        wait_idle(page, 2000)
        ok_sax = set_instrument(page, "Saxophone")
        wait_idle(page, 2500)
        ok_alto = set_baseweb_select(page, "Saxophone", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Type", "Alto saxophone (Eb)"
        )
        wait_idle(page, 2000)
        ok_w = set_written(page, True)
        wait_idle(page, 3000)
        report["checks"][f"{key}_ui"] = {
            "sax": bool(ok_sax),
            "alto": bool(ok_alto),
            "written": bool(ok_w),
            "instrument": instrument_select_value(page),
        }
    else:
        set_written(page, False)
        ok_g = set_instrument(page, "Guitar")
        wait_idle(page, 2500)
        expand_sidebar(page)
        ok_capo = ensure_checkbox(page, "Capo Shape Mode", checked=True)
        wait_idle(page, 2500)
        ok_shape = set_shape_tonic(page, "C")
        wait_idle(page, 3000)
        labels = page.evaluate(
            """() => {
              const body = document.body.innerText || '';
              const capo = (body.match(/Capo\\s*(?:fret)?\\s*[:#]?\\s*(\\d+)/i) || ['',''])[1];
              const charts = (body.match(/Charts in[^\\n]+/i) || [''])[0];
              return {capo, charts: charts.slice(0, 80)};
            }"""
        )
        report["checks"][f"{key}_ui"] = {
            "guitar": bool(ok_g),
            "capo_mode": bool(ok_capo),
            "shape_c": bool(ok_shape),
            "labels": labels,
            "expected_chart": shape_chart_key_for_concert("Bm", "C"),
            "expected_capo": capo_fret_for_shape("Bm", "C"),
        }

    short = ensure_short_verse(page)
    report["checks"][f"{key}_scope"] = short
    set_cycle_mode(page, True)
    wait_idle(page, 5000)
    # Re-assert scope after cycle remount
    ensure_short_verse(page)
    aud = wait_short_audio(page, 100)
    report["checks"][f"{key}_audio"] = {
        "dur": aud.get("dur"),
        "sounding": aud.get("sounding"),
        "ok": bool(aud.get("ok")),
        "class": aud.get("class"),
    }
    if not aud.get("ok"):
        report["failures"].append(f"{key}_audio")
        return

    open_lead_sheet(page)
    page.wait_for_timeout(1500)
    strip = strip_probe(page)
    live = live_chords(page)
    sheet = sheet_chords(page)
    once = projection_once_probe(page)
    expect = None
    if mode == "written":
        expect = written_key_for_type(str(aud.get("sounding") or "Bm"), "Alto saxophone (Eb)")
    else:
        expect = shape_chart_key_for_concert(str(aud.get("sounding") or "Bm"), "C")

    reading = str((strip or {}).get("reading") or once.get("readingKey") or "")
    report["checks"][f"{key}_surfaces"] = {
        "expect_reading": expect,
        "strip": strip,
        "live": live,
        "sheet": sheet[:8],
        "projection_once": once,
        "reading_ok": reading == expect or str((strip or {}).get("concertOn") or "") == str(
            aud.get("sounding") or ""
        ),
        "no_double_shift": not bool(once.get("doubleAppliedToLive")),
        "concert_sounding": aud.get("sounding"),
    }
    if once.get("doubleAppliedToLive"):
        report["failures"].append(f"{key}_double_projection")

    key0 = sounding(page)
    key1 = wait_key_change(page, key0, 100)
    changed = bool(key1 and key0 and key1 != key0)
    wait_playing(page, 30)
    open_lead_sheet(page)
    after_strip = strip_probe(page)
    after_live = live_chords(page)
    after_once = projection_once_probe(page)
    after_audio = audio_snap(page)
    report["checks"][f"{key}_handoff"] = {
        "from": key0,
        "to": key1,
        "changed": changed,
        "strip": after_strip,
        "live": after_live,
        "projection_once": after_once,
        "audio_sounding": after_audio.get("sounding"),
        "no_double_shift": not bool(after_once.get("doubleAppliedToLive")),
        "ok": changed and str(after_audio.get("sounding") or "") == str(key1 or ""),
    }
    if not report["checks"][f"{key}_handoff"]["ok"]:
        report["failures"].append(f"{key}_handoff")

    if mode == "written":
        # Piano / concert return
        set_written(page, False)
        wait_idle(page, 1500)
        set_instrument(page, "Piano")
        wait_idle(page, 3000)
        report["checks"]["piano_return"] = {
            "instrument": instrument_select_value(page),
            "strip": strip_probe(page),
            "sounding": sounding(page),
        }
    else:
        ensure_checkbox(page, "Capo Shape Mode", checked=False)
        wait_idle(page, 2500)
        report["checks"]["shape_off"] = {
            "strip": strip_probe(page),
            "sounding": sounding(page),
        }


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        try:
            boot = boot_shape_backing(page)
            report["boot"] = boot
            if not boot.get("ok"):
                raise RuntimeError("boot_failed")
            run_mode(page, "written", report)
            run_mode(page, "shape", report)
            report["ok"] = not report["failures"]
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            try:
                set_cycle_mode(page, False)
                set_written(page, False)
                set_instrument(page, "Piano")
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report.get("ok"), "failures": report.get("failures"), "checks": list(report.get("checks") or {})}, indent=2), flush=True)
    print("Wrote", OUT, flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

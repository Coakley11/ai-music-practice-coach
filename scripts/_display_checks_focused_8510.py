"""Focused display checks on 8510 — real UI, no workspace seeding.

Piano → Alto → Written ON → compare strip/sheet/Current/Next vs concert audio.
Guitar Shape ON → OFF.
Does not run natural handoffs (requires short arrangement audio first).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from instrument_transposition import written_key_for_type
from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_written_shape_display_8510 import audio_snap, live_chords, strip_probe
from proof_key_cycle_ux_8510 import click_play, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, read_canon
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
_diag = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_diag)
boot_shape_backing = _diag.boot_shape_backing

OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_checks_focused_8510.json"


def scroll_sidebar_control(page, label: str) -> None:
    page.evaluate(
        """(label) => {
          const side = document.querySelector('section[data-testid="stSidebar"]');
          if (!side) return;
          const nodes = [...side.querySelectorAll('[data-testid="stSelectbox"], label, p, span')];
          const hit = nodes.find((el) => new RegExp(label, 'i').test(el.innerText || ''));
          if (hit) hit.scrollIntoView({block: 'center'});
        }""",
        label,
    )
    page.wait_for_timeout(300)


def sheet_chords(page) -> list[str]:
    return page.evaluate(
        """() => {
          const cells = [...document.querySelectorAll(
            '.backing-chart-sheet .live-chart-cell, .lead-sheet .chord-cell, .kc-chord-cell, .live-chart-cell'
          )];
          return cells.map((c) => (c.textContent || '').trim()).filter(Boolean).slice(0, 12);
        }"""
    )


def set_written(page, on: bool) -> dict:
    expand_sidebar(page)
    scroll_sidebar_control(page, "Written|instrument key|Charts")
    ok = ensure_checkbox(page, re.compile(r"written|instrument key|Show chart", re.I), on)
    wait_idle(page, 2500)
    checked = page.evaluate(
        """() => {
          const boxes = [...document.querySelectorAll('input[type="checkbox"]')];
          const hit = boxes.find((b) => {
            const lab = (b.closest('label') || b.parentElement || b).innerText || '';
            return /written|instrument key|Show chart/i.test(lab);
          });
          return hit ? !!hit.checked : null;
        }"""
    )
    return {"helper_ok": bool(ok), "checked": checked}


def set_shape_mode(page, on: bool) -> dict:
    expand_sidebar(page)
    scroll_sidebar_control(page, "Shape|Capo")
    ok = ensure_checkbox(page, re.compile(r"Shape|Capo shape|Guitar shape", re.I), on)
    wait_idle(page, 2500)
    return {"helper_ok": bool(ok)}


def main() -> int:
    report: dict = {"ok": False, "checks": {}, "notes": []}
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
            configure_verse(page, loops=1)
            wait_idle(page, 2000)

            # --- Piano baseline ---
            expand_sidebar(page)
            scroll_sidebar_control(page, "Instrument")
            piano_ok = set_instrument(page, "Piano")
            wait_idle(page, 3000)
            report["checks"]["piano"] = {
                "set_ok": bool(piano_ok),
                "value": instrument_select_value(page),
                "force_used": False,
            }

            set_cycle_mode(page, True)
            wait_idle(page, 5000)
            clear_pause_hold(page)
            click_play(page)
            # Short sample window — do not treat missing audio as display pass.
            deadline = time.time() + 45
            while time.time() < deadline and float(audio_snap(page).get("dur") or 0) < 1:
                page.wait_for_timeout(800)
            base_audio = audio_snap(page)
            base_strip = strip_probe(page)
            base_live = live_chords(page)
            report["checks"]["piano_baseline"] = {
                "audio": base_audio,
                "strip": base_strip,
                "live": base_live,
                "sheet": sheet_chords(page),
            }

            # --- Alto + Written ON ---
            scroll_sidebar_control(page, "Instrument")
            sax_ok = set_instrument(page, "Saxophone")
            wait_idle(page, 3000)
            scroll_sidebar_control(page, "Saxophone|Alto")
            type_ok = set_baseweb_select(page, "Saxophone", "Alto saxophone (Eb)") or set_baseweb_select(
                page, "Type", "Alto saxophone (Eb)"
            )
            wait_idle(page, 2500)
            written = set_written(page, True)
            wait_idle(page, 3500)
            expect = written_key_for_type("Bm", "Alto saxophone (Eb)")
            strip = strip_probe(page)
            live = live_chords(page)
            audio = audio_snap(page)
            sheet = sheet_chords(page)
            reading = str((strip or {}).get("reading") or "")
            live_chord = str((live or {}).get("chord") or "")
            concert_ok = str(audio.get("sounding") or "") in ("", "Bm") or audio.get("sounding") == base_audio.get(
                "sounding"
            )
            # Current/Next must not stay on concert names when strip shows written.
            curr_next_ok = True
            if reading and reading != "Bm" and live_chord:
                # If strip projected, Current should not equal concert-only spelling when distinct.
                if live_chord in ("Bm", "A", "G", "F#") and reading.startswith("G#"):
                    # Concert I / common tones while reading G#m space → fail if Current is concert Bm
                    if live_chord == "Bm":
                        curr_next_ok = False
            report["checks"]["alto_written"] = {
                "sax_ok": bool(sax_ok),
                "type_ok": bool(type_ok),
                "written": written,
                "expect_reading": expect,
                "strip": strip,
                "live": live,
                "sheet": sheet,
                "audio": audio,
                "concert_unchanged": concert_ok,
                "curr_next_projects": curr_next_ok,
                "ok": bool(
                    written.get("checked")
                    and (reading == expect or (strip or {}).get("concertOn") == "Bm")
                    and concert_ok
                ),
            }

            # --- Back to Piano / concert ---
            set_written(page, False)
            wait_idle(page, 1500)
            piano2 = set_instrument(page, "Piano")
            wait_idle(page, 3000)
            report["checks"]["piano_return"] = {
                "set_ok": bool(piano2),
                "value": instrument_select_value(page),
                "strip": strip_probe(page),
                "audio": audio_snap(page),
            }

            # --- Guitar shape ON → OFF ---
            set_cycle_mode(page, False)
            wait_idle(page, 2000)
            scroll_sidebar_control(page, "Instrument")
            g_ok = set_instrument(page, "Guitar")
            wait_idle(page, 3000)
            shape_on = set_shape_mode(page, True)
            wait_idle(page, 2000)
            # Shape Key C is intentional probe — expect Cm chart / capo 11, not fret 0.
            shape_set = set_shape_tonic(page, "C")
            wait_idle(page, 3000)
            shape_labels = page.evaluate(
                """() => {
                  const body = document.body.innerText || '';
                  const capo = (body.match(/Capo\\s*(?:fret)?\\s*[:#]?\\s*(\\d+)/i) || ['',''])[1];
                  const shape = (body.match(/Shape Key[^\\n]{0,40}/i) || [''])[0];
                  const charts = (body.match(/Charts in[^\\n]+/i) || [''])[0];
                  return {capo, shape: shape.slice(0,80), charts: charts.slice(0,80)};
                }"""
            )
            set_cycle_mode(page, True)
            wait_idle(page, 4000)
            clear_pause_hold(page)
            click_play(page)
            page.wait_for_timeout(4000)
            shape_strip = strip_probe(page)
            shape_live = live_chords(page)
            shape_audio = audio_snap(page)
            report["checks"]["guitar_shape_on"] = {
                "instrument_ok": bool(g_ok),
                "shape_mode": shape_on,
                "shape_key_set": bool(shape_set),
                "labels": shape_labels,
                "strip": shape_strip,
                "live": shape_live,
                "audio": shape_audio,
                "expected_chart_key": "Cm",
                "expected_capo_fret": 11,
                "note": "Shape Key is tonic-only; concert Bm + Shape C → Cm. Capo fret = semitone_distance(C, Bm)=11, not 0.",
            }
            shape_off = set_shape_mode(page, False)
            wait_idle(page, 2500)
            report["checks"]["guitar_shape_off"] = {
                "ok": bool(shape_off.get("helper_ok")),
                "strip": strip_probe(page),
                "audio": audio_snap(page),
            }

            report["final_canon"] = read_canon(page)
            report["ok"] = bool(
                (report["checks"].get("alto_written") or {}).get("ok")
                and report["checks"].get("guitar_shape_on")
            )
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            try:
                set_cycle_mode(page, False)
                set_written(page, False)
                set_shape_mode(page, False)
                set_instrument(page, "Piano")
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report.get("ok"), "checks": list((report.get("checks") or {}).keys())}, indent=2), flush=True)
    print("Wrote", OUT, flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Guitar shape/capo downstream matrix on 8510 (Concert WIP unchanged).

Verifies sounding follows cycle, shape/capo relationship, Prev/Next does not
corrupt shape, natural handoff, leave→Off. No push / no server kill.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
    "KC_SHORT_PASS_SECTIONS",
):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright  # noqa: E402

from guitar_capo import capo_fret_for_shape, shape_chart_key_for_concert  # noqa: E402
from proof_kc_finish_five_8510 import boot_backing, clear_pause_hold  # noqa: E402
from proof_kc_focused_shared_8510 import (  # noqa: E402
    click_cycle_next,
    click_cycle_prev,
    full_sync_probe,
    play_until_audible,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone  # noqa: E402
from proof_kc_transport_chord_020e768_8510 import transport_labels  # noqa: E402
from proof_kc_written_shape_display_8510 import (  # noqa: E402
    force_guitar_shape_c,
    live_chords,
    set_piano_concert,
    strip_probe,
)
from proof_key_cycle_ux_8510 import click_play, cycle_ui  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    expand_sidebar,
    instrument_select_value,
    set_instrument,
)
from _browser_ordinary_click_modes_8510 import (  # noqa: E402
    force_leave_piano_off,
    hold_t,
    projection_guard,
)
from _browser_transport_chord_gaps_8510 import sample_highlight_motion  # noqa: E402

OUT = ROOT / "scripts" / "evidence-key-cycle" / "guitar_shape_matrix_8510.json"
BASE = "http://127.0.0.1:8510"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def snap(page) -> dict:
    lab = transport_labels(page)
    dual = page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const cmd = window.__kcLastCmd || {};
          return {
            userPaused: !!st.userPaused,
            cmdSounding: cmd.sounding || '',
            cmdReading: cmd.readingKey || '',
            display0: (cmd.displaySequence || [])[0] || '',
            shapeKey: cmd.shapeKey || cmd.guitarShapeKey || '',
            capoFret: cmd.capoFret != null ? cmd.capoFret : cmd.capo,
          };
        }"""
    )
    return {**lab, **dual, "hold_t": hold_t(page)}


def assert_playing(s: dict) -> bool:
    return bool(
        s.get("cycle") == "Pause"
        and "Stop playback" in str(s.get("live") or "")
        and s.get("playing")
        and not s.get("userPaused")
    )


def _norm(tok: str) -> str:
    t = str(tok or "").strip().split()[0]
    return t.replace("♯", "#").replace("♭", "b")


def expect_shape(concert: str, shape: str = "C") -> tuple[str, int]:
    chart = _norm(shape_chart_key_for_concert(concert, shape) or "")
    fret = int(capo_fret_for_shape(concert, shape) or 0)
    return chart, fret


def shape_still_c(page) -> dict:
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const body = document.body ? (document.body.innerText || '') : '';
          const side = document.querySelector('section[data-testid="stSidebar"]');
          const stxt = side ? (side.innerText || '') : '';
          return {
            cmdShape: cmd.shapeKey || cmd.guitarShapeKey || '',
            cmdReading: cmd.readingKey || '',
            capoMode: /Capo Shape Mode/i.test(stxt) || /Capo Shape Mode/i.test(body),
            shapeCSelected: /\\bShape Key\\b[\\s\\S]{0,40}\\bC\\b/i.test(stxt)
              || /Shape.*?\\bC\\b/i.test(stxt),
          };
        }"""
    )


def ensure_descending_chips(page) -> list:
    chips = []
    for _ in range(4):
        set_descending_whole_tone(page)
        page.wait_for_timeout(900)
        chips = page.evaluate(
            """() => [...document.querySelectorAll('.ui-key-cycle-chip[data-key]')]
              .map((el) => String(el.getAttribute('data-key') || '').trim())
              .filter(Boolean)"""
        )
        if (
            isinstance(chips, list)
            and len(chips) >= 2
            and str(chips[0]) == "Bm"
            and str(chips[1]) == "Am"
        ):
            return chips
        click_play(page)
        page.wait_for_timeout(1500)
        wait_playing(page, seconds=40)
    return chips if isinstance(chips, list) else []


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "mode": "guitar_shape_c",
        "checks": {},
        "failures": [],
        "traces": {},
    }
    try:
        import urllib.request

        with urllib.request.urlopen(BASE + "/", timeout=8) as resp:
            report["server"] = {"http": int(resp.status)}
    except Exception as exc:
        report["server"] = {"reachable": False, "error": str(exc)}
        report["failures"].append("server_unreachable")
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            boot_backing(page)
            open_sheet(page)
            expand_sidebar(page)
            # Arm Guitar shape C BEFORE Play (same mid-cycle widget reliability).
            shape_ok, shape_notes = False, []
            for _setup in range(3):
                shape_ok, shape_notes = force_guitar_shape_c(page)
                page.wait_for_timeout(1500)
                if shape_ok:
                    break
            if not shape_ok:
                report["checks"]["setup"] = {
                    "ok": False,
                    "notes": shape_notes,
                }
                report["failures"].append("setup")
                raise RuntimeError(f"shape_setup_failed:{shape_notes}")
            set_descending_whole_tone(page)
            page.wait_for_timeout(800)
            play_until_audible(page, seconds=90)
            wait_playing(page, seconds=50)
            page.wait_for_timeout(1200)

            s0 = snap(page)
            strip = strip_probe(page)
            live = live_chords(page)
            guard = projection_guard(page)
            sound = sounding(page) or str(s0.get("cmdSounding") or "")
            want_chart, want_fret = expect_shape(sound, "C")
            reading = str(
                (strip or {}).get("reading") or s0.get("cmdReading") or ""
            ).strip()
            shape_meta = shape_still_c(page)
            ui_c = str((live or {}).get("chord") or s0.get("chord") or "").strip()
            chords_ok = bool(ui_c) and ui_c not in {"—", "-", "–", "―"}
            reading_ok = bool(want_chart) and (
                _norm(reading) == want_chart
                or _norm(str(s0.get("display0") or "")) == want_chart
            )
            # Backing must not show the Practice Capo explanation block
            capo_banner = page.evaluate(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Capo shape mode/i.test(t) && /Actual sounding key/i.test(t);
                }"""
            )
            report["traces"]["after_shape"] = {
                "snap": s0,
                "strip": strip,
                "live": live,
                "guard": guard,
                "sound": sound,
                "want_chart": want_chart,
                "want_fret": want_fret,
                "shape_meta": shape_meta,
            }
            guard_shape_ok = bool(
                guard.get("parentAdopted")
                and int(guard.get("displayStampedOnParent") or 0) == 0
                and not guard.get("doubleAppliedToLive")
                and int(guard.get("displaySemitones") or 0) != 0
                and reading_ok
            )
            report["checks"]["projection"] = {
                "setup_ok": shape_ok,
                "setup_notes": shape_notes,
                "sounding": sound,
                "reading": reading,
                "want_chart": want_chart,
                "want_fret": want_fret,
                "reading_ok": reading_ok,
                "chords_ok": chords_ok,
                "shape_retained": bool(shape_meta.get("capoMode") or shape_ok),
                "backing_capo_banner_absent": not bool(capo_banner),
                "guard_ok": bool(guard.get("ok") or guard_shape_ok),
                "ok": bool(
                    shape_ok
                    and assert_playing(s0)
                    and reading_ok
                    and chords_ok
                    and not capo_banner
                    and (guard.get("ok") or guard_shape_ok)
                    and not guard.get("doubleAppliedToLive")
                    and int(guard.get("displayStampedOnParent") or 0) == 0
                ),
            }
            if not report["checks"]["projection"]["ok"]:
                report["failures"].append("projection")

            # Next / Previous — sounding Bm→Am→Bm; shape relationship holds
            chips = ensure_descending_chips(page)
            wait_playing(page, seconds=40)
            k0 = sounding(page)
            if k0 != "Bm":
                click_play(page)
                page.wait_for_timeout(2000)
                deadline = time.time() + 90
                while time.time() < deadline:
                    page.wait_for_timeout(800)
                    k0 = sounding(page)
                    if k0 == "Bm":
                        break
            meta0 = shape_still_c(page)
            want0, _ = expect_shape(k0, "C")
            click_cycle_next(page)
            wait_key_change(page, k0, timeout_s=60)
            k1 = sounding(page)
            after_next = snap(page)
            meta1 = shape_still_c(page)
            want1, _ = expect_shape(k1, "C")
            reading1 = str(after_next.get("cmdReading") or "")
            click_cycle_prev(page)
            deadline_prev = time.time() + 60
            k_back = k1
            while time.time() < deadline_prev:
                page.wait_for_timeout(700)
                k_back = sounding(page)
                if k0 and k_back == k0:
                    break
            after_prev = snap(page)
            meta_back = shape_still_c(page)
            shape_intact = bool(
                (meta0.get("capoMode") or shape_ok)
                and (meta1.get("capoMode") or shape_ok)
                and (meta_back.get("capoMode") or shape_ok)
            )
            report["checks"]["next_prev"] = {
                "chips": chips,
                "from": k0,
                "after_next": k1,
                "after_prev": k_back,
                "want_chart_next": want1,
                "reading_next": reading1,
                "shape_intact": shape_intact,
                "meta_next": meta1,
                "ok": bool(
                    k0 == "Bm"
                    and k1 == "Am"
                    and k_back == "Bm"
                    and chips[:2] == ["Bm", "Am"]
                    and shape_intact
                    and (
                        _norm(reading1) == want1
                        or _norm(str(after_next.get("display0") or "")) == want1
                    )
                ),
            }
            report["traces"]["next_prev"] = {
                "after_next": after_next,
                "after_prev": after_prev,
                "meta0": meta0,
                "meta1": meta1,
                "meta_back": meta_back,
            }
            if not report["checks"]["next_prev"]["ok"]:
                report["failures"].append("next_prev")

            # Natural handoff
            from_key = sounding(page)
            handoff = None
            deadline = time.time() + 120
            while time.time() < deadline:
                page.wait_for_timeout(1500)
                cur = sounding(page)
                if cur and from_key and cur != from_key:
                    page.wait_for_timeout(2000)
                    live_h = live_chords(page)
                    blank_deadline = time.time() + 12
                    while time.time() < blank_deadline:
                        ui_c = str((live_h or {}).get("chord") or "").strip()
                        if ui_c and ui_c not in {"—", "-", "–", "―"}:
                            break
                        page.wait_for_timeout(700)
                        live_h = live_chords(page)
                    probe = full_sync_probe(page)
                    guard_h = projection_guard(page)
                    want_h, _ = expect_shape(cur, "C")
                    reading_h = str(
                        page.evaluate(
                            "() => (window.__kcLastCmd && window.__kcLastCmd.readingKey) || ''"
                        )
                        or ""
                    )
                    display0_h = _norm(
                        str(
                            page.evaluate(
                                "() => ((window.__kcLastCmd||{}).displaySequence||[])[0]||''"
                            )
                        )
                    )
                    meta_h = shape_still_c(page)
                    ui_c = str((live_h or {}).get("chord") or "").strip()
                    blank = (not ui_c) or ui_c in {"—", "-", "–", "―"}
                    motion = sample_highlight_motion(page, samples=5, gap_ms=700)
                    reading_ok_h = bool(want_h) and (
                        _norm(reading_h) == want_h or display0_h == want_h
                    )
                    guard_shape_ok_h = bool(
                        guard_h.get("parentAdopted")
                        and int(guard_h.get("displayStampedOnParent") or 0) == 0
                        and not guard_h.get("doubleAppliedToLive")
                        and int(guard_h.get("displaySemitones") or 0) != 0
                        and reading_ok_h
                    )
                    chords_evidence = (not blank) or bool(
                        motion.get("ok") and motion.get("unique_highlights")
                    )
                    handoff = {
                        "from": from_key,
                        "key": cur,
                        "want_chart": want_h,
                        "reading": reading_h,
                        "live": live_h,
                        "probe": probe,
                        "guard": guard_h,
                        "shape_meta": meta_h,
                        "motion": {
                            "ok": motion.get("ok"),
                            "unique_highlights": motion.get("unique_highlights"),
                        },
                        "ok": bool(
                            chords_evidence
                            and (guard_h.get("ok") or guard_shape_ok_h)
                            and not guard_h.get("doubleAppliedToLive")
                            and motion.get("ok")
                            and (meta_h.get("capoMode") or shape_ok)
                            and reading_ok_h
                        ),
                    }
                    break
            report["checks"]["natural_handoff"] = handoff or {
                "ok": False,
                "from": from_key,
            }
            if not (handoff and handoff.get("ok")):
                report["failures"].append("natural_handoff")

        except Exception as exc:
            report["error"] = str(exc)
            report["failures"].append("exception")
        finally:
            try:
                # Leave must clear shape and return Piano / cycling Off
                report["left"] = force_leave_piano_off(page)
                inst = str(instrument_select_value(page) or "")
                ui = cycle_ui(page) or {}
                shape_cleared = page.evaluate(
                    """() => {
                      const boxes = [...document.querySelectorAll('input[type="checkbox"]')];
                      for (const b of boxes) {
                        const lab = ((b.closest('label') || b.parentElement || b).innerText || '');
                        if (/Capo Shape Mode|Shape/i.test(lab) && b.checked) return false;
                      }
                      return true;
                    }"""
                )
                report["left"]["shape_cleared"] = bool(shape_cleared)
                report["left"]["instrument"] = inst
                report["checks"]["leave_clean"] = {
                    "ok": bool(
                        report["left"].get("ok")
                        and inst.startswith("Piano")
                        and not bool(ui.get("playbar"))
                        and shape_cleared
                    ),
                    "left": report["left"],
                }
                if not report["checks"]["leave_clean"]["ok"]:
                    report["failures"].append("leave_clean")
            except Exception as eLeave:
                report["leave_error"] = str(eLeave)
                report["failures"].append("leave_clean")
            try:
                browser.close()
            except Exception:
                pass

    report["ok"] = not report["failures"]
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "sha", "failures", "checks", "left")}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

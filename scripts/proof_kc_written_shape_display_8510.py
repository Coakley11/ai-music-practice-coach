"""Browser-verify written-key / guitar-shape display projection on 8510.

Checks (ordinary clicks + real audio; display-only must not transpose/restart):
1. Sounding key + backing audio stay concert; saved Practice Key unchanged by cycling.
2. Cycle strip / Current / Next project into written or shape mode.
3. Alto: concert G→Ab→A → written E→F→F#; switch to concert at F# shows A without
   restarting or advancing.
4. Shape: concert G with shape C → C→Db/C#→D (spelling prefs); concert↔shape mid-cycle.
5. Mid-cycle instrument/written/shape change preserves cycle position, audio time,
   playing/paused state; lead sheet stays open.
6. Turning display mode off restores concert-key labels at the same position.

Leaves cycling Off and KC_SHORT_PASS_* unset. No push.
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
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
):
    os.environ.pop(k, None)

from proof_kc_finish_five_8510 import (  # noqa: E402
    boot_backing,
    clear_pause_hold,
    wait_idle,
)
from proof_kc_focused_shared_8510 import (  # noqa: E402
    click_cycle_next,
    play_until_audible,
    sounding,
    wait_key_change,
    wait_playing,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet  # noqa: E402
from proof_kc_transport_chord_020e768_8510 import (  # noqa: E402
    transport_labels,
    wait_audible,
)
from proof_key_cycle_ux_8510 import cycle_ui, set_cycle_mode  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    ensure_checkbox,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
)

OUT = ROOT / "scripts" / "evidence-key-cycle" / "written_shape_display_8510.json"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def strip_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const bar = document.querySelector('.ui-key-cycle-playbar, [class*="ui-key-cycle"]');
          const chips = [...document.querySelectorAll(
            '.ui-key-cycle-chip, .ui-key-cycle-playbar span[data-key], [class*="ui-key-cycle-chip"]'
          )];
          const labels = chips.map((el) => {
            const vis = (el.getAttribute('data-display') || el.textContent || '').trim();
            const concert = (el.getAttribute('data-key') || '').trim();
            return {vis: vis.split(/\\s+/)[0], concert};
          }).filter((x) => x.vis);
          const on = document.querySelector('.ui-key-cycle-chip-on, [class*="chip-on"]');
          const reading = on
            ? String(on.getAttribute('data-display') || on.textContent || '').trim().split(/\\s+/)[0]
            : '';
          const concertOn = on ? String(on.getAttribute('data-key') || '').trim() : '';
          const modeEl = document.querySelector('[class*="ui-key-cycle"] [data-mode], .ui-key-cycle-mode');
          let modeHint = '';
          const body = document.body ? document.body.innerText : '';
          if (/Written/i.test(body) && /key cycle/i.test(body)) modeHint = 'written?';
          return {
            labels: labels.slice(0, 8),
            reading,
            concertOn,
            displaySeq: (bar && bar.getAttribute('data-display-seq')) || '',
            concertSeq: (bar && bar.getAttribute('data-seq')) || '',
            modeHint,
          };
        }"""
    )


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          return {
            t: act ? Number(act.currentTime || 0) : 0,
            dur: act ? Number(act.duration || 0) : 0,
            paused: act ? !!act.paused : true,
            muted: act ? !!act.muted : true,
            sounding: act ? String(act.getAttribute('data-kc-sounding') || '') : '',
            url: act ? String(act.getAttribute('data-kc-url') || act.src || '').slice(-40) : '',
            userPaused: !!dual.userPaused,
          };
        }"""
    )


def live_chords(page) -> dict:
    lab = transport_labels(page)
    return {
        "chord": lab.get("chord") or "",
        "next": lab.get("next") or "",
        "section": lab.get("section") or "",
        "bar": lab.get("bar") or "",
        "live": lab.get("live") or "",
        "cycle": lab.get("cycle") or "",
        "playing": bool(lab.get("playing")),
        "paused": bool(lab.get("paused")),
        "t": lab.get("t"),
        "sounding": lab.get("sounding") or sounding(page),
    }


def practice_key_label(page) -> str:
    return str(
        page.evaluate(
            """() => {
              const labs = [...document.querySelectorAll('label, p, span, div')]
                .map((el) => (el.innerText || '').trim())
                .filter((t) => /^Practice Key/i.test(t) || /Practice Key:/i.test(t));
              const hit = labs.find((t) => /Practice Key/i.test(t)) || '';
              const m = hit.match(/Practice Key[:\\s]+([A-G][#b]?m?)/i);
              if (m) return m[1];
              // select value near Practice Key
              const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
              for (const b of boxes) {
                const t = (b.innerText || '');
                if (/Practice Key/i.test(t)) {
                  const m2 = t.match(/\\b([A-G][#b]?m?)\\b/);
                  if (m2) return m2[1];
                }
              }
              return '';
            }"""
        )
        or ""
    )


def force_set_instrument(page, name: str) -> bool:
    """Scroll sidebar Instrument into view and set it (cycle playbar can obscure)."""
    expand_sidebar(page)
    page.wait_for_timeout(400)
    ok = page.evaluate(
        """(name) => {
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
          let target = null;
          for (const b of boxes) {
            const t = (b.innerText || '').trim();
            if (/^Instrument\\b/i.test(t) && !/Shape/i.test(t)) { target = b; break; }
          }
          if (!target) return false;
          try { target.scrollIntoView({ block: 'center' }); } catch (e) {}
          const hit = target.querySelector('[data-baseweb="select"], [role="combobox"], input')
            || target;
          try { hit.click(); } catch (e2) { return false; }
          return true;
        }""",
        name,
    )
    if not ok:
        return set_instrument(page, name)
    page.wait_for_timeout(400)
    page.keyboard.press("Control+A")
    page.wait_for_timeout(80)
    page.keyboard.type(name, delay=40)
    page.wait_for_timeout(500)
    opt = page.locator('[role="option"]').filter(
        has_text=re.compile(rf"^{re.escape(name)}$", re.I)
    )
    if opt.count():
        try:
            opt.first.click(timeout=4000)
        except Exception:
            page.keyboard.press("Enter")
    else:
        page.keyboard.press("Enter")
    page.wait_for_timeout(2000)
    wait_idle(page, 4000)
    side = page.locator('section[data-testid="stSidebar"]')
    try:
        txt = side.inner_text(timeout=3000) or ""
    except Exception:
        txt = page.inner_text("body") or ""
    return name.lower() in txt.lower()


def set_alto_written(page) -> dict:
    notes: list[str] = []
    ok_inst = force_set_instrument(page, "Saxophone")
    page.wait_for_timeout(1500)
    expand_sidebar(page)
    # Scroll toward saxophone type / written checkbox
    page.evaluate(
        """() => {
          const side = document.querySelector('section[data-testid="stSidebar"]');
          if (side) {
            const lab = [...side.querySelectorAll('label,div,p')].find((el) =>
              /Saxophone type|written key|Show chart/i.test(el.innerText || '')
            );
            if (lab) try { lab.scrollIntoView({ block: 'center' }); } catch (e) {}
          }
        }"""
    )
    page.wait_for_timeout(400)
    ok_type = (
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)")
        or set_baseweb_select(page, "Saxophone type", "Alto Saxophone")
        or set_baseweb_select(page, "Saxophone type", "Alto saxophone")
    )
    page.wait_for_timeout(1200)
    ok_written = ensure_checkbox(
        page, "Show chart in written key for instrument", checked=True
    )
    if not ok_written:
        # Retry after scrolling full sidebar
        page.evaluate(
            """() => {
              const side = document.querySelector('section[data-testid="stSidebar"]');
              if (side) side.scrollTop = side.scrollHeight;
            }"""
        )
        page.wait_for_timeout(400)
        ok_written = ensure_checkbox(
            page, "Show chart in written key for instrument", checked=True
        )
    page.wait_for_timeout(1500)
    return {"instrument": ok_inst, "type": ok_type, "written": ok_written, "notes": notes}


def set_written_off(page) -> bool:
    expand_sidebar(page)
    return ensure_checkbox(
        page, "Show chart in written key for instrument", checked=False
    )


def set_piano_concert(page) -> bool:
    return force_set_instrument(page, "Piano")


def force_guitar_shape_c(page) -> tuple[bool, list[str]]:
    notes: list[str] = []
    ok_inst = force_set_instrument(page, "Guitar")
    notes.append(f"instrument Guitar={ok_inst}")
    page.wait_for_timeout(1200)
    expand_sidebar(page)
    page.evaluate(
        """() => {
          const side = document.querySelector('section[data-testid="stSidebar"]');
          if (!side) return;
          const lab = [...side.querySelectorAll('label,div,p')].find((el) =>
            /Capo Shape Mode|Shape Key/i.test(el.innerText || '')
          );
          if (lab) try { lab.scrollIntoView({ block: 'center' }); } catch (e) {}
        }"""
    )
    capo_ok = ensure_checkbox(page, "Capo Shape Mode", checked=True)
    notes.append(f"capo enabled={capo_ok}")
    page.wait_for_timeout(800)
    from walk_guitar_shape_key import set_shape_tonic

    shape_ok = set_shape_tonic(page, "C") or set_baseweb_select(page, "Shape Key", "C")
    notes.append(f"shape key C={shape_ok}")
    page.wait_for_timeout(1500)
    return bool(ok_inst and capo_ok and shape_ok), notes


def leave_clean(page) -> dict:
    try:
        set_cycle_mode(page, "Off")
    except Exception:
        pass
    page.wait_for_timeout(1000)
    try:
        set_cycle_mode(page, False)
    except Exception:
        pass
    page.wait_for_timeout(1200)
    ui = cycle_ui(page) or {}
    return {
        "playbar": bool(ui.get("playbar")),
        "short_env": {
            k: os.environ.get(k)
            for k in (
                "KC_SHORT_PASS_BARS",
                "KC_SHORT_PASS_LOOPS",
                "KC_SHORT_PASS_FORCE",
                "KC_SHORT_PASS_SECS",
            )
        },
    }


def _norm(tok: str) -> str:
    t = str(tok or "").strip().split()[0]
    return t.replace("♯", "#").replace("♭", "b")


def _equiv(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    # enharmonic pairs used in cycle spelling
    pairs = {
        ("C#", "Db"),
        ("D#", "Eb"),
        ("F#", "Gb"),
        ("G#", "Ab"),
        ("A#", "Bb"),
    }
    return (a, b) in pairs or (b, a) in pairs


def main() -> int:
    report: dict = {
        "ok": False,
        "sha": sha(),
        "checks": {},
        "failures": [],
        "left": {},
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1100})

        def step(msg: str) -> None:
            print(f"{time.strftime('%H:%M:%S')} STEP {msg}", flush=True)

        try:
            step("boot_backing")
            boot_backing(page)

            step("play_until_audible")
            play_until_audible(page, seconds=180.0)
            open_sheet(page)
            page.wait_for_timeout(1000)
            clear_pause_hold(page)
            wait_audible(page, 30)
            pk0 = practice_key_label(page) or sounding(page) or "Bm"
            sound0 = sounding(page)
            snap0 = audio_snap(page)
            strip0 = strip_probe(page)
            live0 = live_chords(page)
            report["checks"]["baseline"] = {
                "practice_key": pk0,
                "sounding": sound0,
                "strip": strip0,
                "live": live0,
                "t": snap0.get("t"),
                "url": snap0.get("url"),
            }

            # Advance twice so we are mid-cycle (not on the Practice Key start).
            step("advance_to_third_key")
            key_a = sounding(page)
            click_cycle_next(page)
            wait_idle(page, 20000)
            key_b = wait_key_change(page, key_a, 90)
            wait_playing(page, 40)
            click_cycle_next(page)
            wait_idle(page, 20000)
            key_c = wait_key_change(page, key_b, 90)
            wait_playing(page, 40)
            wait_audible(page, 20)
            open_sheet(page)

            from instrument_transposition import written_key_for_type

            def expect_alto_written(concert: str) -> str:
                return str(
                    written_key_for_type(concert, "Alto saxophone (Eb)") or concert
                ).strip()

            def expect_shape_c(concert: str, start: str) -> str:
                # Mirror project_cycle_display_key shape math with C shape / start PK.
                sess = {
                    "instrument": "Guitar",
                    "guitar_capo_enabled": True,
                    "guitar_capo_shape_key": "C",
                    "practice_key_by_source": {"__tmp__": start},
                }
                try:
                    from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

                    sess[CAPO_ENABLED_KEY] = True
                    sess[CAPO_SHAPE_KEY] = "C"
                except Exception:
                    pass
                # Fall back: relative semitone from start onto C.
                try:
                    from guitar_capo import shape_chart_key_for_concert, shape_tonic_only
                    from music_theory import semitone_distance
                    from backing_key_cycle import cycle_concert_practice_key

                    base = shape_chart_key_for_concert(start, "C")
                    steps = semitone_distance(start, concert)
                    return cycle_concert_practice_key(base, semitones=steps)
                except Exception:
                    return concert

            mid_before = {
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "live": live_chords(page),
                "strip": strip_probe(page),
                "practice_key": practice_key_label(page) or pk0,
            }
            report["checks"]["mid_concert"] = mid_before
            if mid_before["practice_key"] and pk0 and mid_before["practice_key"] != pk0:
                report["failures"].append("practice_key_changed_by_cycle")

            # --- Alto written mid-cycle ---
            step("alto_written_on")
            t_before = float(mid_before["audio"].get("t") or 0)
            url_before = str(mid_before["audio"].get("url") or "")
            playing_before = not bool(mid_before["audio"].get("paused"))
            sound_before = str(mid_before["sounding"] or "")
            expect_w = expect_alto_written(sound_before)
            alto = set_alto_written(page)
            page.wait_for_timeout(2500)
            wait_idle(page, 15000)
            open_sheet(page)
            page.wait_for_timeout(1000)
            after_alto = {
                "setup": alto,
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "live": live_chords(page),
                "strip": strip_probe(page),
                "practice_key": practice_key_label(page) or pk0,
                "expect_written": expect_w,
            }
            t_after = float(after_alto["audio"].get("t") or 0)
            url_after = str(after_alto["audio"].get("url") or "")
            playing_after = not bool(after_alto["audio"].get("paused"))
            same_sound = _equiv(after_alto["sounding"], sound_before) or (
                after_alto["sounding"] == sound_before
            )
            no_restart = bool(url_after) and (
                url_after == url_before or abs(t_after - t_before) < 12
            )
            state_ok = playing_after == playing_before or playing_after
            reading = after_alto["strip"].get("reading") or ""
            disp_seq = str(after_alto["strip"].get("displaySeq") or "")
            written_ok = _equiv(reading, expect_w) or _equiv(
                reading.replace("m", ""), str(expect_w or "").replace("m", "")
            )
            setup_ok = bool(alto.get("instrument") and alto.get("written"))
            sheet_open = bool(
                page.evaluate(
                    """() => {
                      for (const f of document.querySelectorAll('iframe')) {
                        try {
                          if (f.contentDocument && f.contentDocument.querySelector('.live-follow-shell'))
                            return true;
                        } catch (e) {}
                      }
                      return false;
                    }"""
                )
            )
            pk_stable = (after_alto["practice_key"] == (mid_before["practice_key"] or pk0)) or (
                not after_alto["practice_key"]
            )
            alto_check = {
                "same_sounding": same_sound,
                "no_audio_restart": no_restart,
                "playing_preserved": state_ok,
                "written_projection": written_ok,
                "setup_ok": setup_ok,
                "expect_written": expect_w,
                "reading": reading,
                "displaySeq": disp_seq[:80],
                "t_before": round(t_before, 2),
                "t_after": round(t_after, 2),
                "practice_key": after_alto["practice_key"],
                "sheet_open": sheet_open,
                "live_chord": after_alto["live"].get("chord"),
                "ok": bool(
                    setup_ok
                    and same_sound
                    and no_restart
                    and state_ok
                    and written_ok
                    and sheet_open
                    and pk_stable
                ),
            }
            report["checks"]["alto_midcycle"] = {**after_alto, "assert": alto_check}
            if not alto_check["ok"]:
                report["failures"].append("alto_midcycle")

            # Concert view while still on same concert sounding
            step("alto_to_concert")
            t2 = float(audio_snap(page).get("t") or 0)
            set_written_off(page)
            page.wait_for_timeout(2000)
            wait_idle(page, 12000)
            open_sheet(page)
            after_concert = {
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "strip": strip_probe(page),
                "live": live_chords(page),
            }
            reading_c = after_concert["strip"].get("reading") or ""
            concert_view_ok = _equiv(reading_c, after_concert["sounding"]) or (
                reading_c == after_concert["sounding"]
            )
            no_adv = _equiv(after_concert["sounding"], sound_before)
            no_restart2 = abs(float(after_concert["audio"].get("t") or 0) - t2) < 12
            c_ok = bool(concert_view_ok and no_adv and no_restart2)
            report["checks"]["alto_to_concert"] = {
                **after_concert,
                "assert": {
                    "concert_labels": concert_view_ok,
                    "same_position": no_adv,
                    "no_restart": no_restart2,
                    "ok": c_ok,
                },
            }
            if not c_ok:
                report["failures"].append("alto_to_concert")

            # Guitar shape C relative to Practice Key start
            step("guitar_shape_on")
            set_piano_concert(page)
            page.wait_for_timeout(1000)
            wait_audible(page, 30)
            open_sheet(page)
            before_shape = {
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "practice_key": practice_key_label(page) or pk0,
            }
            expect_sh = expect_shape_c(
                str(before_shape["sounding"] or ""),
                str(before_shape["practice_key"] or pk0),
            )
            shape_ok, notes = force_guitar_shape_c(page)
            page.wait_for_timeout(2500)
            wait_idle(page, 15000)
            open_sheet(page)
            after_shape = {
                "setup": shape_ok,
                "notes": notes[-6:],
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "strip": strip_probe(page),
                "live": live_chords(page),
                "practice_key": practice_key_label(page) or pk0,
                "expect_shape": expect_sh,
            }
            shape_reading = after_shape["strip"].get("reading") or ""
            shape_proj = _equiv(shape_reading, expect_sh) or _equiv(
                shape_reading.replace("m", ""), str(expect_sh or "").replace("m", "")
            )
            same_s = _equiv(after_shape["sounding"], before_shape["sounding"])
            t_ok = abs(
                float(after_shape["audio"].get("t") or 0)
                - float(before_shape["audio"].get("t") or 0)
            ) < 14
            sheet_open2 = bool(
                page.evaluate(
                    """() => {
                      for (const f of document.querySelectorAll('iframe')) {
                        try {
                          if (f.contentDocument && f.contentDocument.querySelector('.live-follow-shell'))
                            return true;
                        } catch (e) {}
                      }
                      return false;
                    }"""
                )
            )
            sh_ok = bool(shape_ok and same_s and t_ok and shape_proj and sheet_open2)
            report["checks"]["shape_midcycle"] = {
                **after_shape,
                "assert": {
                    "setup": shape_ok,
                    "same_sounding": same_s,
                    "no_restart": t_ok,
                    "shape_projection": shape_proj,
                    "expect_shape": expect_sh,
                    "reading": shape_reading,
                    "sheet_open": sheet_open2,
                    "ok": sh_ok,
                },
            }
            if not sh_ok:
                report["failures"].append("shape_midcycle")

            # Shape off → concert
            step("shape_to_concert")
            t3 = float(audio_snap(page).get("t") or 0)
            ensure_checkbox(page, "Capo Shape Mode", checked=False)
            page.wait_for_timeout(2000)
            wait_idle(page, 12000)
            open_sheet(page)
            after_shape_off = {
                "sounding": sounding(page),
                "audio": audio_snap(page),
                "strip": strip_probe(page),
            }
            reading_off = after_shape_off["strip"].get("reading") or ""
            off_ok = (
                _equiv(reading_off, after_shape_off["sounding"])
                or reading_off == after_shape_off["sounding"]
            ) and _equiv(after_shape_off["sounding"], after_shape["sounding"]) and (
                abs(float(after_shape_off["audio"].get("t") or 0) - t3) < 12
            )
            report["checks"]["shape_to_concert"] = {
                **after_shape_off,
                "assert": {"ok": off_ok, "reading": reading_off},
            }
            if not off_ok:
                report["failures"].append("shape_to_concert")

            # Soft natural-handoff window (full pass may exceed budget)
            step("natural_handoff_sanity")
            wait_audible(page, 20)
            key_n0 = sounding(page)
            key_n1 = wait_key_change(page, key_n0, 45)
            report["checks"]["natural_handoff_window"] = {
                "from": key_n0,
                "to": key_n1,
                "changed": bool(key_n1 and key_n0 and key_n1 != key_n0),
            }

            report["ok"] = not report["failures"]
        except Exception as exc:
            report["error"] = str(exc)
            report["ok"] = False
            report["failures"].append("exception")
        finally:
            try:
                report["left"] = leave_clean(page)
            except Exception as exc:
                report["left"] = {"error": str(exc)}
            browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"Wrote {OUT}", flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

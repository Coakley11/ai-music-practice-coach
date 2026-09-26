"""Single-mode written natural handoff: short Verse play, surfaces, one handoff.

Keeps Chromium lighter (no heavy boot_shape). Requires 8510. Clears KC_SHORT_*.
"""
from __future__ import annotations

import json
import os
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
from proof_kc_focused_shared_8510 import sounding, wait_key_change
from proof_kc_written_shape_display_8510 import audio_snap, live_chords, strip_probe
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, open_lead_sheet, read_canon
from walk_creative_backing_matrix import (
    ensure_checkbox,
    expand_pages_nav,
    expand_sidebar,
    instrument_select_value,
    set_baseweb_select,
    set_instrument,
)
from walk_practice_loop_backing import goto_studio

OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_written_handoff_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "display_written_handoff_8510.run.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def projection_once(page) -> dict:
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const tl = cmd.followTimeline || [];
          const live = ((document.getElementById('live-chord')||{}).textContent||'')
            .replace(/\\s*\\(.*/,'').trim();
          const c0 = (tl[0] && (tl[0].chord || tl[0].c)) || '';
          const proj = window.__kcProjectChordLabel;
          const once = (typeof proj === 'function' && c0) ? (proj(c0) || '') : '';
          const twice = (typeof proj === 'function' && once) ? (proj(once) || '') : '';
          return {
            readingKey: cmd.readingKey || '',
            sounding: cmd.sounding || '',
            displaySemitones: cmd.displaySemitones || 0,
            concert0: c0,
            live,
            once,
            twice,
            doubleApplied: !!(once && twice && once !== twice && live === twice),
            strip0: (cmd.displaySequence || [])[0] || '',
          };
        }"""
    )


def force_loops1(page) -> dict:
    cfg = {}
    for _ in range(5):
        cfg = configure_verse(page, loops=1)
        wait_idle(page, 1500)
        canon = read_canon(page)
        widget = int(cfg.get("widget_loops") or canon.get("loops_slider") or 0)
        # Widget/slider is authoritative for Play; canon caption can lag one edit.
        if (
            canon.get("scope") == "Selected sections"
            and "Verse" in str(canon.get("sec") or "")
            and widget == 1
        ):
            return {"ok": True, "canon": canon, "cfg": cfg, "widget_loops": widget}
    canon = read_canon(page)
    return {
        "ok": False,
        "canon": canon,
        "cfg": cfg,
        "widget_loops": int((cfg or {}).get("widget_loops") or canon.get("loops_slider") or 0),
    }


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    report: dict = {"ok": False, "checks": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
                "--autoplay-policy=no-user-gesture-required",
            ],
            ignore_default_args=["--mute-audio"],
        )
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(90000)
        try:
            log("goto")
            page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)
            expand_sidebar(page)
            expand_pages_nav(page)
            goto_studio(page, "Backing")
            wait_idle(page, 4000)
            set_cycle_mode(page, False)

            log("written ui")
            set_instrument(page, "Saxophone")
            wait_idle(page, 3500)
            set_baseweb_select(page, "Saxophone", "Alto saxophone (Eb)") or set_baseweb_select(
                page, "Type", "Alto saxophone (Eb)"
            )
            wait_idle(page, 2500)
            ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
            wait_idle(page, 3000)
            report["checks"]["ui"] = {
                "instrument": instrument_select_value(page),
                "ok": instrument_select_value(page) == "Saxophone",
            }
            if not report["checks"]["ui"]["ok"]:
                report["failures"].append("ui")

            log("scope")
            scope = force_loops1(page)
            report["checks"]["scope"] = scope
            log(f"canon {scope.get('canon')}")
            if not scope.get("ok"):
                report["failures"].append("scope")

            log("cycle on + rescope")
            set_cycle_mode(page, True)
            wait_idle(page, 5000)
            scope2 = force_loops1(page)
            report["checks"]["scope_after_cycle"] = scope2
            if not scope2.get("ok"):
                report["failures"].append("scope_after_cycle")

            log("play")
            clear_pause_hold(page)
            click_play(page)
            aud = {}
            deadline = time.time() + 100
            while time.time() < deadline:
                aud = audio_snap(page)
                dur = float(aud.get("dur") or 0)
                log(f"dur={dur} sounding={aud.get('sounding')} paused={aud.get('paused')}")
                if 5 < dur < 120:
                    break
                if dur >= 200:
                    break
                page.wait_for_timeout(1200)
            report["checks"]["audio"] = {
                "dur": aud.get("dur"),
                "sounding": aud.get("sounding"),
                "ok": 5 < float(aud.get("dur") or 0) < 120,
            }
            if not report["checks"]["audio"]["ok"]:
                report["failures"].append("audio")
                raise RuntimeError(f"bad_dur {aud.get('dur')}")

            log("surfaces")
            open_lead_sheet(page)
            page.wait_for_timeout(1200)
            expect = written_key_for_type(str(aud.get("sounding") or "Bm"), "Alto saxophone (Eb)")
            strip = strip_probe(page)
            live = live_chords(page)
            proj = projection_once(page)
            reading = str((strip or {}).get("reading") or proj.get("readingKey") or "")
            surfaces_ok = (
                reading == expect
                and not proj.get("doubleApplied")
                and str(aud.get("sounding") or "") in ("Bm", str(proj.get("sounding") or ""))
            )
            report["checks"]["surfaces"] = {
                "expect": expect,
                "strip": strip,
                "live": live,
                "proj": proj,
                "ok": surfaces_ok,
            }
            log(f"surfaces ok={surfaces_ok} expect={expect} proj={proj}")
            if not surfaces_ok:
                report["failures"].append("surfaces")

            key0 = sounding(page)
            log(f"handoff wait from {key0}")
            key1 = wait_key_change(page, key0, 95)
            after = audio_snap(page)
            after_strip = strip_probe(page)
            after_live = live_chords(page)
            after_proj = projection_once(page)
            changed = bool(key1 and key0 and key1 != key0)
            handoff_ok = changed and str(after.get("sounding") or "") == str(key1 or "")
            report["checks"]["handoff"] = {
                "from": key0,
                "to": key1,
                "changed": changed,
                "sounding": after.get("sounding"),
                "strip": after_strip,
                "live": after_live,
                "proj": after_proj,
                "no_double": not bool(after_proj.get("doubleApplied")),
                "ok": handoff_ok and not after_proj.get("doubleApplied"),
            }
            log(f"handoff {report['checks']['handoff']}")
            if not report["checks"]["handoff"]["ok"]:
                report["failures"].append("handoff")

            ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
            set_instrument(page, "Piano")
            wait_idle(page, 3000)
            set_cycle_mode(page, False)
            ui = cycle_ui(page) or {}
            report["checks"]["leave"] = {
                "instrument": instrument_select_value(page),
                "playbar": ui.get("playbar"),
                "ok": instrument_select_value(page) == "Piano" and not ui.get("playbar"),
            }
            if not report["checks"]["leave"]["ok"]:
                report["failures"].append("leave")

            report["ok"] = not report["failures"]
        except Exception as exc:
            report["error"] = str(exc)
            log(f"ERROR {exc}")
            report["failures"].append("exception")
        finally:
            try:
                set_cycle_mode(page, False)
                set_instrument(page, "Piano")
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"RESULT ok={report.get('ok')} failures={report.get('failures')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

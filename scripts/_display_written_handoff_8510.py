"""Short focused written-mode proof: short audio + surfaces + one natural handoff."""
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
LOG = ROOT / "scripts" / "evidence-key-cycle" / "display_written_handoff_8510.run.log"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_written_handoff_8510.json"


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    # Import after path setup
    from playwright.sync_api import sync_playwright

    from instrument_transposition import written_key_for_type
    from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
    from proof_kc_focused_shared_8510 import sounding, wait_key_change
    from proof_kc_written_shape_display_8510 import audio_snap, live_chords, strip_probe
    from proof_key_cycle_ux_8510 import click_play, set_cycle_mode
    from proof_verse_verify_8510 import configure_verse, open_lead_sheet, read_canon
    from walk_creative_backing_matrix import (
        ensure_checkbox,
        expand_sidebar,
        instrument_select_value,
        set_baseweb_select,
        set_instrument,
    )
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "diag_short_arr", ROOT / "scripts" / "_diag_short_arrangement_8510.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    report: dict = {"ok": False, "checks": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        try:
            log("boot")
            boot = mod.boot_shape_backing(page)
            report["boot"] = boot
            if not boot.get("ok"):
                raise RuntimeError("boot_failed")

            log("piano")
            expand_sidebar(page)
            set_instrument(page, "Piano")
            wait_idle(page, 2000)

            log("sax+alto+written")
            set_instrument(page, "Saxophone")
            wait_idle(page, 2500)
            set_baseweb_select(page, "Saxophone", "Alto saxophone (Eb)") or set_baseweb_select(
                page, "Type", "Alto saxophone (Eb)"
            )
            wait_idle(page, 2000)
            ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
            wait_idle(page, 3000)

            log("configure verse")
            cfg = configure_verse(page, loops=1)
            canon = read_canon(page)
            report["checks"]["scope"] = {"canon": canon, "loops_ok": cfg.get("loops_ok")}
            log(f"canon {canon}")

            set_cycle_mode(page, True)
            wait_idle(page, 5000)
            configure_verse(page, loops=1)
            clear_pause_hold(page)
            click_play(page)
            log("waiting short audio")
            aud = {}
            deadline = time.time() + 90
            while time.time() < deadline:
                aud = audio_snap(page)
                dur = float(aud.get("dur") or 0)
                log(f"dur={dur} sounding={aud.get('sounding')} paused={aud.get('paused')}")
                if 5 < dur < 120:
                    break
                if dur >= 200:
                    break
                page.wait_for_timeout(1500)
            report["checks"]["audio"] = {
                "dur": aud.get("dur"),
                "sounding": aud.get("sounding"),
                "ok": 5 < float(aud.get("dur") or 0) < 120,
            }
            if not report["checks"]["audio"]["ok"]:
                report["failures"].append("audio")
                raise RuntimeError(f"bad_dur {aud.get('dur')}")

            open_lead_sheet(page)
            page.wait_for_timeout(1200)
            expect = written_key_for_type(str(aud.get("sounding") or "Bm"), "Alto saxophone (Eb)")
            strip = strip_probe(page)
            live = live_chords(page)
            proj = page.evaluate(
                """() => {
                  const cmd = window.__kcLastCmd || {};
                  const tl = cmd.followTimeline || [];
                  const c0 = (tl[0] && tl[0].chord) || '';
                  const live = ((document.getElementById('live-chord')||{}).textContent||'').replace(/\\s*\\(.*/,'').trim();
                  const once = (typeof window.__kcProjectChordLabel==='function' && c0)
                    ? window.__kcProjectChordLabel(c0) : '';
                  const twice = (typeof window.__kcProjectChordLabel==='function' && once)
                    ? window.__kcProjectChordLabel(once) : '';
                  return {
                    readingKey: cmd.readingKey||'', sounding: cmd.sounding||'',
                    displaySemitones: cmd.displaySemitones||0, concert0: c0,
                    live, once, twice,
                    doubleApplied: !!(once && twice && once!==twice && live===twice),
                    strip0: (cmd.displaySequence||[])[0]||'',
                  };
                }"""
            )
            report["checks"]["surfaces"] = {
                "expect": expect,
                "strip": strip,
                "live": live,
                "proj": proj,
                "instrument": instrument_select_value(page),
                "ok": (
                    str((strip or {}).get("reading") or proj.get("readingKey") or "") == expect
                    and not proj.get("doubleApplied")
                    and str(aud.get("sounding") or "") in ("Bm", str(proj.get("sounding") or ""))
                ),
            }
            log(f"surfaces {report['checks']['surfaces']['ok']} expect={expect} proj={proj}")
            if not report["checks"]["surfaces"]["ok"]:
                report["failures"].append("surfaces")

            key0 = sounding(page)
            log(f"wait natural handoff from {key0}")
            key1 = wait_key_change(page, key0, 100)
            changed = bool(key1 and key0 and key1 != key0)
            after = audio_snap(page)
            after_strip = strip_probe(page)
            after_live = live_chords(page)
            report["checks"]["handoff"] = {
                "from": key0,
                "to": key1,
                "changed": changed,
                "sounding": after.get("sounding"),
                "strip": after_strip,
                "live": after_live,
                "ok": changed and str(after.get("sounding") or "") == str(key1 or ""),
            }
            log(f"handoff {report['checks']['handoff']}")
            if not report["checks"]["handoff"]["ok"]:
                report["failures"].append("handoff")

            # Piano/concert return
            ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
            set_instrument(page, "Piano")
            wait_idle(page, 2500)
            report["checks"]["piano_return"] = {
                "instrument": instrument_select_value(page),
                "strip": strip_probe(page),
            }

            report["ok"] = not report["failures"]
        except Exception as exc:
            report["error"] = str(exc)
            log(f"ERROR {exc}")
        finally:
            try:
                set_cycle_mode(page, False)
                set_instrument(page, "Piano")
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"RESULT ok={report.get('ok')} failures={report.get('failures')}")
    log(f"Wrote {OUT}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

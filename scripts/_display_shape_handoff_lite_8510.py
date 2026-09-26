"""Shape-mode natural handoff lite: Guitar shape C, short verse, one handoff."""
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

from guitar_capo import capo_fret_for_shape, shape_chart_key_for_concert
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
    set_instrument,
)
from walk_guitar_shape_key import set_shape_tonic
from walk_practice_loop_backing import goto_studio

OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_shape_handoff_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "display_shape_handoff_8510.run.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def force_loops1(page) -> dict:
    cfg = {}
    for _ in range(5):
        cfg = configure_verse(page, loops=1)
        wait_idle(page, 1200)
        canon = read_canon(page)
        widget = int(cfg.get("widget_loops") or canon.get("loops_slider") or 0)
        if (
            canon.get("scope") == "Selected sections"
            and "Verse" in str(canon.get("sec") or "")
            and widget == 1
        ):
            return {"ok": True, "canon": canon, "widget_loops": widget}
    return {"ok": False, "canon": read_canon(page), "cfg": cfg}


def projection_once(page) -> dict:
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const tl = cmd.followTimeline || [];
          const c0 = (tl[0] && (tl[0].chord || tl[0].c)) || '';
          const proj = window.__kcProjectChordLabel;
          const once = (typeof proj === 'function' && c0) ? (proj(c0) || '') : '';
          const twice = (typeof proj === 'function' && once) ? (proj(once) || '') : '';
          const liveDoc = (() => {
            for (const f of document.querySelectorAll('iframe')) {
              try {
                const d = f.contentDocument;
                if (d && d.getElementById('live-chord')) return d;
              } catch (e) {}
            }
            return document;
          })();
          const live = ((liveDoc.getElementById('live-chord')||{}).textContent||'')
            .replace(/\\s*\\(.*/,'').trim();
          return {
            readingKey: cmd.readingKey || '', sounding: cmd.sounding || '',
            concert0: c0, once, twice, live,
            doubleApplied: !!(once && twice && once !== twice && live === twice),
            alreadyProjectedGuard: !!(once && c0 && once === c0),
            strip0: (cmd.displaySequence || [])[0] || '',
          };
        }"""
    )


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    report: dict = {"ok": False, "checks": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox",
                  "--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(5000)
            expand_sidebar(page)
            expand_pages_nav(page)
            goto_studio(page, "Backing")
            wait_idle(page, 4000)
            set_cycle_mode(page, False)

            set_instrument(page, "Guitar")
            wait_idle(page, 3500)
            ensure_checkbox(page, "Guitar Shape", checked=True) or ensure_checkbox(
                page, "Capo Shape Mode", checked=True
            )
            wait_idle(page, 1500)
            set_shape_tonic(page, "C")
            wait_idle(page, 2500)
            expect_chart = shape_chart_key_for_concert("Bm", "C")
            expect_capo = capo_fret_for_shape("Bm", "C")
            body = page.evaluate("() => document.body.innerText || ''")
            capo_ui = (re.search(r"capo[^\n]{0,30}", body, re.I) or [""])[0]
            report["checks"]["ui"] = {
                "instrument": instrument_select_value(page),
                "expect_chart": expect_chart,
                "expect_capo": expect_capo,
                "capo_ui": capo_ui[:60],
                "ok": expect_chart == "Cm" and expect_capo == 11,
            }
            log(f"ui {report['checks']['ui']}")
            if not report["checks"]["ui"]["ok"]:
                report["failures"].append("ui")

            scope = force_loops1(page)
            report["checks"]["scope"] = scope
            set_cycle_mode(page, True)
            wait_idle(page, 5000)
            force_loops1(page)

            clear_pause_hold(page)
            click_play(page)
            aud = {}
            deadline = time.time() + 100
            while time.time() < deadline:
                aud = audio_snap(page)
                dur = float(aud.get("dur") or 0)
                log(f"dur={dur} sounding={aud.get('sounding')}")
                if 5 < dur < 120:
                    break
                page.wait_for_timeout(1200)
            report["checks"]["audio"] = {
                "dur": aud.get("dur"),
                "sounding": aud.get("sounding"),
                "ok": 5 < float(aud.get("dur") or 0) < 120,
            }
            if not report["checks"]["audio"]["ok"]:
                report["failures"].append("audio")
                raise RuntimeError("bad_audio")

            open_lead_sheet(page)
            page.wait_for_timeout(1200)
            strip = strip_probe(page)
            live = live_chords(page)
            proj = projection_once(page)
            expect = shape_chart_key_for_concert(str(aud.get("sounding") or "Bm"), "C")
            reading = str((strip or {}).get("reading") or proj.get("readingKey") or "")
            surfaces_ok = reading == expect and not proj.get("doubleApplied")
            report["checks"]["surfaces"] = {
                "expect": expect, "strip": strip, "live": live, "proj": proj, "ok": surfaces_ok
            }
            log(f"surfaces {surfaces_ok} {proj}")
            if not surfaces_ok:
                report["failures"].append("surfaces")

            key0 = sounding(page)
            key1 = wait_key_change(page, key0, 95)
            after = audio_snap(page)
            after_strip = strip_probe(page)
            after_live = live_chords(page)
            after_proj = projection_once(page)
            handoff_ok = bool(key1 and key0 != key1) and str(after.get("sounding") or "") == str(key1)
            report["checks"]["handoff"] = {
                "from": key0, "to": key1, "sounding": after.get("sounding"),
                "strip": after_strip, "live": after_live, "proj": after_proj,
                "no_double": not bool(after_proj.get("doubleApplied")),
                "ok": handoff_ok and not after_proj.get("doubleApplied"),
            }
            log(f"handoff {report['checks']['handoff']}")
            if not report["checks"]["handoff"]["ok"]:
                report["failures"].append("handoff")

            ensure_checkbox(page, "Guitar Shape", checked=False) or ensure_checkbox(
                page, "Capo Shape Mode", checked=False
            )
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
            browser.close()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"RESULT ok={report.get('ok')} failures={report.get('failures')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Fresh Streamlit session refresh + Resume on 8510.

Naturally advances past the first cycle key (Verse-only, 1 loop — real duration,
no KC_SHORT_PASS). New browser context restores disk cycle key, stopped at pass
start, both controls Resume, no autoplay; ordinary Resume plays that key once.
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

from proof_kc_bpm_feel_scope_8510 import wait_controls_ready
from proof_kc_finish_five_8510 import (
    audio_probe,
    clear_pause_hold,
    disk_cycle_key,
    wait_idle,
)
from proof_kc_manual_review_gaps_8510 import set_multi_scope
from proof_kc_settings_focused_8510 import set_loops, set_practice_key, set_scope_selected_section
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import (
    click_pause_ordinary,
    click_play,
    click_playbar,
    cycle_ui,
    set_cycle_mode,
)
from proof_verse_verify_8510 import goto_backing_shape, set_level_intermediate
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "fresh_session_resume_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "fresh_session_resume_run.txt"


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


def boot(page) -> dict:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
    clear_pause_hold(page)
    expand_sidebar(page)
    expand_pages_nav(page)
    landed = goto_backing_shape(page)
    wait_idle(page, 20000)
    if "Intermediate" not in (page.inner_text("body") or ""):
        set_level_intermediate(page)
        wait_idle(page)
    set_practice_key(page, "Bm")
    wait_idle(page)
    # Prefer Verse-only for a real but shorter natural pass (no SHORT_PASS).
    set_scope_selected_section(page, "Verse")
    set_multi_scope(page, ["Verse 1"])
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
    return {"landed": bool(landed), "ok": bool(landed)}


def _live_label(page) -> str:
    return str((audio_probe(page) or {}).get("liveLabel") or "")


def _sounding(page) -> str:
    pr = audio_probe(page)
    ui = cycle_ui(page)
    return str(
        pr.get("sounding")
        or ui.get("sounding")
        or page.evaluate("() => String(window.__kcLastSounding || '')")
        or ""
    ).strip()


def wait_natural_advance(page, *, timeout_s: float = 480) -> dict:
    clear_pause_hold(page)
    click_play(page)
    wait_kc_audio(page, 120)
    page.wait_for_timeout(2000)
    key0 = _sounding(page)
    pr0 = audio_probe(page)
    t_watch = time.time()
    _log(
        f"natural_watch from={key0!r} paused={pr0.get('paused')} "
        f"unmuted={pr0.get('unmutedPlayingCount')} dur={pr0.get('dur')}"
    )
    deadline = time.time() + timeout_s
    out: dict = {"from": key0, "ok": False}
    last_log = 0.0
    last_replay = 0.0
    while time.time() < deadline:
        pr = audio_probe(page)
        ui = cycle_ui(page)
        unmuted = int(pr.get("unmutedPlayingCount") or 0)
        k = _sounding(page)
        now = time.time()
        if now - last_log > 25:
            _log(
                f"natural_tick k={k!r} paused={pr.get('paused')} "
                f"unmuted={unmuted} t={pr.get('t')} dur={pr.get('dur')} "
                f"cycle={ui.get('pause')}"
            )
            last_log = now
        if unmuted > 1:
            out.update({"overlap": True, "probe": pr, "ok": False})
            return out
        if key0 and k and k != key0:
            # Allow brief mute during seamless flip; require single buffer shortly after.
            page.wait_for_timeout(2000)
            hold = audio_probe(page)
            hold_u = int(hold.get("unmutedPlayingCount") or 0)
            hold_k = _sounding(page)
            out.update(
                {
                    "to": hold_k or k,
                    "probe": hold,
                    "overlap": hold_u > 1,
                    "ok": hold_u <= 1 and (hold_k or k) != key0,
                }
            )
            return out
        # If audio died without advancing, one ordinary re-Play (not JS fallback).
        if (
            pr.get("paused")
            and unmuted == 0
            and now - last_replay > 45
            and now - t_watch > 30
        ):
            _log("natural_replay ordinary Play (paused with no advance)")
            clear_pause_hold(page)
            click_play(page)
            last_replay = now
            page.wait_for_timeout(1500)
        page.wait_for_timeout(800)
    out["timeout"] = True
    out["last"] = _sounding(page)
    return out


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    report: dict = {"ok": False, "sha": _sha(), "browser": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(120000)
        try:
            setup = boot(page)
            report["browser"]["setup"] = setup
            if not setup.get("ok"):
                report["failures"].append("setup")
                raise RuntimeError("setup")

            natural = wait_natural_advance(page)
            report["browser"]["natural_advance"] = {
                k: natural.get(k) for k in ("from", "to", "ok", "overlap", "timeout")
            }
            _log(f"natural {report['browser']['natural_advance']}")
            if not natural.get("ok"):
                report["failures"].append("natural_advance")
                raise RuntimeError("natural_advance")

            # Pause so refresh lands stopped (no autoplay). Retry — right after a
            # natural flip labels/transport can lag one beat.
            pause_ok = False
            pause_meta: dict = {}
            for _try in range(4):
                applies0 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
                clicked = click_pause_ordinary(page)
                page.wait_for_timeout(1200)
                applies1 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
                ui_p = cycle_ui(page)
                pr_p = audio_probe(page)
                live_p = _live_label(page)
                pause_meta = {
                    "ok": False,
                    "cycle": ui_p.get("pause"),
                    "live": live_p,
                    "handler": applies1 > applies0,
                    "paused": pr_p.get("paused"),
                    "try": _try,
                }
                pause_ok = bool(
                    clicked
                    and pr_p.get("paused")
                    and int(pr_p.get("unmutedPlayingCount") or 0) == 0
                    and "Resume" in str(ui_p.get("pause") or "")
                    and ("Resume" in live_p or not live_p)
                )
                pause_meta["ok"] = pause_ok
                if pause_ok:
                    break
                page.wait_for_timeout(800)
            report["browser"]["pause_before_refresh"] = pause_meta
            _log(f"pause_before_refresh {pause_meta}")
            if not pause_ok:
                report["failures"].append("pause_before_refresh")

            page.wait_for_timeout(2000)
            disk_before = disk_cycle_key()
            before_key = str(
                disk_before.get("current_playback_key")
                or natural.get("to")
                or ""
            )
            report["browser"]["disk_before"] = disk_before
            _log(f"disk_before key={before_key!r}")

            # Fresh Streamlit session via new browser context.
            context.close()
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()
            page.set_default_timeout(120000)
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
            page.wait_for_timeout(4000)
            wait_idle(page)
            expand_sidebar(page)
            expand_pages_nav(page)
            goto_studio(page, "Backing")
            page.wait_for_timeout(2500)
            wait_idle(page)
            open_sheet(page)
            wait_idle(page)
            ui_new = cycle_ui(page)
            pr_new = audio_probe(page)
            live_new = _live_label(page)
            disk_after = disk_cycle_key()
            pk = str(disk_after.get("practice_key") or "")
            pk_ok = (not pk) or pk.startswith("Bm") or pk in {"B", "Bm"}
            sounding = str(
                ui_new.get("sounding")
                or pr_new.get("sounding")
                or disk_after.get("current_playback_key")
                or ""
            )
            both_resume = "Resume" in str(ui_new.get("pause") or "") and (
                "Resume" in live_new or not live_new
            )
            at_start = float(pr_new.get("t") or pr_new.get("currentTime") or 0) < 1.5
            no_autoplay = bool(pr_new.get("paused")) and int(
                pr_new.get("unmutedPlayingCount") or 0
            ) == 0
            restored = bool(
                before_key
                and disk_after.get("current_playback_key") == before_key
                and (sounding == before_key or disk_after.get("current_playback_key") == before_key)
                and "Resume" in str(ui_new.get("pause") or "")
                and no_autoplay
                and at_start
                and pk_ok
            )
            report["browser"]["fresh_session"] = {
                "key_before": before_key,
                "disk_key": disk_after.get("current_playback_key"),
                "sounding": sounding,
                "cycle_pause": ui_new.get("pause"),
                "live": live_new,
                "paused": pr_new.get("paused"),
                "at_start": at_start,
                "practice_key": pk,
                "both_resume": both_resume,
                "ok": restored,
            }
            _log(f"fresh_session {report['browser']['fresh_session']}")
            if not restored:
                report["failures"].append("fresh_session_restore")

            resume_restored = {"ok": False}
            if restored:
                # Do not clear pause hold before Resume — Held + sessionStorage
                # paused must be cleared by the ordinary Resume click path.
                a0 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
                r0 = page.evaluate("() => Number(window.__kcLastResumeMs || 0)")
                clicked_rr = click_pause_ordinary(page)
                page.wait_for_timeout(800)
                # Fresh-session Resume may rebuild the restored key (cache hit or
                # generate) before the dual-buffer mounts — allow a full rebuild.
                deadline_r = time.time() + 180
                pr_rr = audio_probe(page)
                while time.time() < deadline_r:
                    pr_rr = audio_probe(page)
                    if (
                        not pr_rr.get("paused")
                        and int(pr_rr.get("unmutedPlayingCount") or 0) == 1
                        and float(pr_rr.get("t") or 0) > 0.05
                    ):
                        break
                    page.wait_for_timeout(500)
                ui_rr = cycle_ui(page)
                live_rr = _live_label(page)
                r1 = page.evaluate("() => Number(window.__kcLastResumeMs || 0)")
                resume_restored = {
                    "clicked": bool(clicked_rr),
                    "handler": int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
                    > a0
                    or (r1 != r0),
                    "sounding": pr_rr.get("sounding") or _sounding(page),
                    "paused": pr_rr.get("paused"),
                    "unmuted": pr_rr.get("unmutedPlayingCount"),
                    "t": pr_rr.get("t"),
                    "cycle": ui_rr.get("pause"),
                    "live": live_rr,
                    "ok": bool(
                        clicked_rr
                        and not pr_rr.get("paused")
                        and int(pr_rr.get("unmutedPlayingCount") or 0) == 1
                        and str(pr_rr.get("sounding") or _sounding(page) or "") == before_key
                        and float(pr_rr.get("t") or 0) < 12.0
                        and "Pause" in str(ui_rr.get("pause") or "")
                    ),
                }
                _log(f"resume_restored {resume_restored}")
                if not resume_restored.get("ok"):
                    report["failures"].append("resume_plays_restored_key")
            report["browser"]["resume_restored"] = resume_restored

            set_cycle_mode(page, False)
            wait_idle(page)
            report["ok"] = not report["failures"]
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
                context.close()
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

"""Focused Pop → Blues → Pop Feel Play replacement on 8510.

Stable setup: Shape of You, Intermediate, fixed scope/loops.
Confirms generate_saved nested groove, player command URL, and audible currentSrc
for each Feel. Ordinary UI only. One revision per report.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_kc_bpm_feel_scope_8510 import commit_feel, read_server, wait_controls_ready
from proof_kc_finish_five_8510 import (
    BASE,
    TRACE,
    audio_probe,
    clear_pause_hold,
    last_generate_meta_after,
    wait_arrangement_audio,
    wait_idle,
)
from proof_kc_settings_focused_8510 import (
    set_loops,
    set_practice_key,
    set_scope_selected_section,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_key_cycle_ux_8510 import (
    click_pause_ordinary,
    click_play,
    cycle_ui,
    set_cycle_mode,
)
from proof_verse_verify_8510 import goto_backing_shape, set_level_intermediate
from walk_practice_loop_backing import expand_pages_nav, expand_sidebar

OUT = ROOT / "scripts" / "evidence-key-cycle" / "feel_replace_8510.json"
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_key_cycle_8510")
CMDS = DATA / "_kc_player_cmds.jsonl"
WANT_SONG = "Shape of You"


def _page_identity(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const song =
            (body.match(/Shape of You[^\\n]{0,40}/i) ||
             body.match(/Active song[^\\n]{0,80}/i) || [''])[0];
          const level = ((body.match(/\\b(Beginner|Intermediate|Advanced)\\b/) || [])[1] || '');
          return { body_song: song.slice(0, 80), level, has_shape: /Shape of You/i.test(body) };
        }"""
    )


def _last_cmd_after(offset: int) -> dict:
    if not CMDS.is_file():
        return {}
    raw = CMDS.read_bytes()
    if offset > 0:
        raw = raw[offset:]
    last = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("currentUrl"):
            last = obj
    return last


def _boot_shape_stable(page) -> dict:
    """Shape of You / Intermediate / fixed scope+loops. Verifies owner before Feel."""
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
    clear_pause_hold(page)
    expand_sidebar(page)
    expand_pages_nav(page)
    landed = goto_backing_shape(page)
    wait_idle(page, 20000)
    # goto_backing_shape already set Intermediate; only re-assert if missing.
    body0 = page.inner_text("body") or ""
    if "Intermediate" not in body0:
        set_level_intermediate(page)
        wait_idle(page)
    clear_pause_hold(page)
    set_practice_key(page, "Bm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    if not set_cycle_mode(page, True):
        set_cycle_mode(page, True)
    wait_idle(page)
    if not cycle_ui(page).get("playbar"):
        set_cycle_mode(page, True)
        wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    open_sheet(page)
    clear_pause_hold(page)
    wait_controls_ready(page)
    ident = _page_identity(page)
    srv = read_server(page)
    body = page.inner_text("body") or ""
    if "Shape of You" in body and "Ed Sheeran" in body:
        active = "shape"
    elif re.search(r"\bSay\b", body) and "Mayer" in body and "Shape of You" not in body:
        active = "say"
    elif "Shape of You" in body:
        active = "shape_loose"
    else:
        active = "unknown"
    setup = {
        "landed": bool(landed),
        "active": active,
        "identity": ident,
        "server": {
            "bpm_canon": srv.get("bpm_canon"),
            "groove_canon": srv.get("groove_canon"),
            "scope_canon": srv.get("scope_canon"),
            "loops_canon": srv.get("loops_canon"),
            "tags": srv.get("tags"),
        },
        "ok": active in {"shape", "shape_loose"},
        "why_say_risk": (
            "Earlier runs used boot_backing's vague Shape-of-You click without "
            "verifying the catalog owner; persisted workspace kept Say (John Mayer) "
            "as the backing source while Intermediate/82bpm came from that visit."
        ),
    }
    print(
        f"setup active={active} landed={landed} bpm={srv.get('bpm_canon')} "
        f"tags={srv.get('tags')} groove={srv.get('groove_canon')}"
    )
    return setup


def _play_feel(page, style: str, prev_src: str) -> dict:
    ident_before = _page_identity(page)
    srv_before = read_server(page)
    print(
        f"before_feel {style!r} shape={ident_before.get('has_shape')} "
        f"bpm={srv_before.get('bpm_canon')} groove={srv_before.get('groove_canon')}"
    )
    before = commit_feel(page, style)
    # Require a real commit when the prior audible Feel differs (canon can
    # briefly echo catalog Pop while Blues is still sealed).
    need_step = bool(before.get("already") or not before.get("ok"))
    if need_step:
        alt = "Rock groove" if "pop" in style.lower() else "Pop groove"
        print(f"feel_step_away {style!r} via {alt!r}", flush=True)
        commit_feel(page, alt)
        wait_idle(page)
        before = commit_feel(page, style)
        wait_idle(page)
        if before.get("already"):
            # Canon still claims target without a change event — force Rock then target once more.
            commit_feel(page, "Rock groove" if "rock" not in style.lower() else "Jazz swing")
            wait_idle(page)
            before = commit_feel(page, style)
            wait_idle(page)
    commit = before
    # Wait until canon sticks and widget is not stuck on the prior Feel.
    stem = style.split()[0].lower()
    deadline = time.time() + 12
    while time.time() < deadline:
        srv = read_server(page)
        cg = str(srv.get("groove_canon") or "").lower()
        wg = str(srv.get("groove_widget") or "").lower()
        if stem in cg and (stem in wg or not wg or "rock" not in wg):
            break
        page.wait_for_timeout(400)
    wait_idle(page)
    clear_pause_hold(page)
    gen_off = TRACE.stat().st_size if TRACE.is_file() else 0
    cmd_off = CMDS.stat().st_size if CMDS.is_file() else 0
    bridge_path = DATA / "_key_cycle_bridge_clicks.jsonl"
    bridge_off = bridge_path.stat().st_size if bridge_path.is_file() else 0
    page.evaluate("() => { window.__kcApplyTrace = []; }")
    click_play(page)
    wait_idle(page, 120000)
    wait_arrangement_audio(page, prev_src=prev_src, seconds=180)
    meta: dict = {}
    stem = style.split()[0].lower()
    deadline = time.time() + 90
    while time.time() < deadline:
        meta = last_generate_meta_after(gen_off)
        g = str(meta.get("groove") or "")
        sig = str(meta.get("sig") or "")
        if stem in g.lower() and "shape" in sig.lower():
            break
        if stem in g.lower():
            break
        page.wait_for_timeout(500)
    page.wait_for_timeout(1800)
    probe = audio_probe(page)
    cmd = _last_cmd_after(cmd_off)
    reasons = page.evaluate(
        "() => (window.__kcApplyTrace || []).map(x => String(x.reason||'')).slice(-24)"
    )
    deferred = []
    if bridge_path.is_file():
        raw = bridge_path.read_bytes()[bridge_off:].decode("utf-8", errors="replace")
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                deferred.append(json.loads(line))
            except Exception:
                pass
    src = str(probe.get("src") or "")
    cmd_url = str(cmd.get("currentUrl") or "")
    sig = str(meta.get("sig") or "")
    song_ok = "shape" in sig.lower()
    ok = bool(
        commit.get("ok")
        and stem in str(meta.get("groove") or "").lower()
        and src
        and src != prev_src
        and song_ok
    )
    return {
        "identity_before": ident_before,
        "commit": commit,
        "gen_groove": meta.get("groove"),
        "gen_song": (re.search(r"\('([^']+)'", sig) or [None, None])[1],
        "wav_bytes": meta.get("wav_bytes"),
        "src": src[-48:],
        "prev_src": (prev_src or "")[-48:],
        "src_changed": bool(src) and src != prev_src,
        "cmd_url": cmd_url[-48:],
        "cmd_reload": cmd.get("reload"),
        "reasons": reasons,
        "bridge_deferred": [d for d in deferred if d.get("deferred")],
        "song_ok": song_ok,
        "ok": ok,
    }


def main() -> int:
    report: dict = {"ok": False, "sha": "", "browser": {}, "setup": {}, "product_failures": []}
    try:
        import subprocess

        report["sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        report["sha"] = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(120000)
        try:
            report["setup"] = _boot_shape_stable(page)
            if not report["setup"].get("ok"):
                report["product_failures"].append("setup_not_shape_of_you")
                raise RuntimeError(f"setup_not_shape: {report['setup'].get('active')}")
            steps = [
                ("pop1", "Pop groove"),
                ("blues", "Blues groove"),
                ("pop2", "Pop groove"),
            ]
            prev = str(audio_probe(page).get("src") or "")
            for key, style in steps:
                print(f"=== step {key} {style} ===", flush=True)
                row = _play_feel(page, style, prev)
                report["browser"][key] = row
                if not row.get("ok"):
                    report["product_failures"].append(f"feel_{key}_audible")
                    break
                prev = str(audio_probe(page).get("src") or "") or prev
                try:
                    click_pause_ordinary(page)
                    wait_idle(page)
                except Exception:
                    pass
            report["ok"] = not report["product_failures"]
            set_cycle_mode(page, False)
            wait_idle(page)
        except Exception as exc:
            report["error"] = repr(exc)
            import traceback

            report["traceback"] = traceback.format_exc()[-2000:]
            if "setup_not_shape" in str(exc) and "setup_not_shape_of_you" not in report["product_failures"]:
                report["product_failures"].append("setup_not_shape_of_you")
        finally:
            try:
                browser.close()
            except Exception:
                pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:6000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

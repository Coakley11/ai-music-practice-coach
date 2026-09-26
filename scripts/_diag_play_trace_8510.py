"""Trace one Play from committed Verse1/loops=1 through buffer mount on 8510.

Captures: canon, generation markers, __kcLastCmd, dual buffers, applyTrace,
and page/status text. Identifies the first missing step when audio stays silent.
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

from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, read_canon

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "diag_short_arr", ROOT / "scripts" / "_diag_short_arrangement_8510.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
boot_shape_backing = _mod.boot_shape_backing

OUT = ROOT / "scripts" / "evidence-key-cycle" / "diag_play_trace_8510.json"
RUNTIME = ROOT / "_runtime_key_cycle_8510"


def snap(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const dual = window.__kcDual || {};
          const cmd = window.__kcLastCmd || {};
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const pick = (a) => a ? {
            id: a.id,
            src: (a.getAttribute('data-kc-url') || a.src || '').slice(-80),
            paused: !!a.paused,
            t: Number(a.currentTime || 0),
            dur: Number(a.duration || 0),
            ready: Number(a.readyState || 0),
            sounding: a.getAttribute('data-kc-sounding') || '',
            muted: !!a.muted,
          } : null;
          const statusLine = (body.match(/(Audio ready|Press Play|Generating|generating|Held|pending|WAV|error|Error|failed|Failed)[^\\n]{0,120}/) || [''])[0];
          const alerts = [...document.querySelectorAll('[data-testid="stAlert"], .stAlert, [role="alert"]')]
            .map((el) => (el.innerText || '').trim().slice(0, 200))
            .filter(Boolean)
            .slice(0, 6);
          const hasDualEls = !!(a0 || a1);
          const hasBridge = typeof window.__kcApplyCmd === 'function' || typeof window.__kcApplyPlayerCmd === 'function';
          return {
            dualEnabled: !!dual.enabled,
            dualUserPaused: !!dual.userPaused,
            dualActive: dual.active,
            a0: pick(a0),
            a1: pick(a1),
            hasDualEls,
            hasBridge,
            cmd: {
              sounding: cmd.sounding || '',
              currentUrl: (cmd.currentUrl || '').slice(-80),
              nextUrl: (cmd.nextUrl || '').slice(-80),
              forcePlay: !!cmd.forcePlay,
              pauseAudio: !!cmd.pauseAudio,
              epoch: cmd.epoch != null ? cmd.epoch : null,
              passToken: cmd.passToken || '',
              readingKey: cmd.readingKey || '',
            },
            applyTrace: (window.__kcApplyTrace || []).slice(-12),
            lastSounding: window.__kcLastSounding || '',
            statusLine: statusLine.slice(0, 160),
            alerts,
            hasPlayBtn: !![...document.querySelectorAll('button')].find(
              (b) => /Play Backing Track/i.test(b.innerText || '')
            ),
            spinner: !![...document.querySelectorAll('[data-testid="stSpinner"], .stSpinner')].length,
          };
        }"""
    )


def classify_first_fail(before: dict, after: dict, samples: list) -> str:
    """Name the first missing/rejected stage in the Play chain."""
    if not after.get("hasPlayBtn") and before.get("hasPlayBtn"):
        return "play_button_gone_after_click"
    # Generation / URL publication
    last = samples[-1] if samples else after
    cmd = (last.get("cmd") or {})
    if not str(cmd.get("currentUrl") or "").strip():
        if last.get("spinner") or "enerat" in str(last.get("statusLine") or "").lower():
            return "stuck_generating_no_url"
        if last.get("alerts"):
            return "generate_alert_no_url:" + str(last["alerts"][0])[:80]
        return "no_currentUrl_published"
    if not last.get("hasDualEls"):
        return "player_bridge_elements_missing"
    if not last.get("dualEnabled"):
        # URL published but dual never enabled — applyCmd reject or bridge not mounted
        trace = last.get("applyTrace") or []
        if any("reject" in str(t.get("reason") or t) for t in trace if isinstance(t, dict)):
            return "applyCmd_rejected:" + str(trace[-1])
        if not trace:
            return "dual_never_enabled_empty_applyTrace"
        return "dual_never_enabled"
    a0 = last.get("a0") or {}
    a1 = last.get("a1") or {}
    src = str(a0.get("src") or a1.get("src") or "")
    if not src:
        return "dual_enabled_but_no_buffer_src"
    dur = float(a0.get("dur") or 0) or float(a1.get("dur") or 0)
    if dur <= 0:
        return "buffer_src_set_but_duration_zero"
    if float(a0.get("ready") or 0) < 2 and float(a1.get("ready") or 0) < 2:
        return "buffer_not_ready"
    paused = bool(a0.get("paused", True) and a1.get("paused", True))
    if paused and not last.get("dualUserPaused"):
        return "buffer_ready_but_not_playing"
    if dur >= 200:
        return "stale_full_song_audio"
    if 5 < dur < 120:
        return "short_ok"
    return "unexpected_duration"


def runtime_tail() -> dict:
    out: dict = {}
    if not RUNTIME.exists():
        return {"missing": True}
    for name in ("_kc_player_cmds.jsonl", "_key_cycle_pass_gaps.jsonl", "_kc_generate_meta.jsonl"):
        path = RUNTIME / name
        if not path.exists():
            out[name] = None
            continue
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        out[name] = lines[-3:] if lines else []
    return out


def main() -> int:
    report: dict = {"ok": False, "samples": [], "short_env": "unset"}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        console: list[str] = []
        page.on("console", lambda msg: console.append(f"{msg.type}:{msg.text}"[:200]))
        try:
            boot = boot_shape_backing(page)
            report["boot"] = boot
            print("boot", boot.get("ok"), flush=True)
            if not boot.get("ok"):
                raise RuntimeError("boot_failed")

            cfg = configure_verse(page, loops=1)
            wait_idle(page, 3000)
            report["canon"] = read_canon(page)
            report["cfg_ok"] = bool(cfg.get("loops_ok")) and report["canon"].get("sec") == "Verse 1"
            print("canon", report["canon"], flush=True)

            set_cycle_mode(page, True)
            wait_idle(page, 8000)
            clear_pause_hold(page)
            # Leave Held if Resume showing
            ui = cycle_ui(page) or {}
            if "Resume" in str(ui.get("pause") or ""):
                page.evaluate(
                    """() => {
                      const b = [...document.querySelectorAll('button')].find(
                        (el) => /^Resume$/i.test((el.innerText||'').trim())
                      );
                      if (b) b.click();
                    }"""
                )
                wait_idle(page, 3000)
                clear_pause_hold(page)

            before = snap(page)
            report["before"] = {"ui": ui, "snap": before}
            print("before", json.dumps(before)[:500], flush=True)

            clicked = click_play(page)
            report["clicked"] = clicked
            print("clicked", clicked, flush=True)

            deadline = time.time() + 90
            while time.time() < deadline:
                s = snap(page)
                report["samples"].append({"t": round(time.time(), 1), **s})
                dur = float((s.get("a0") or {}).get("dur") or 0) or float((s.get("a1") or {}).get("dur") or 0)
                url = str((s.get("cmd") or {}).get("currentUrl") or "")
                print(
                    f"t+{90-(deadline-time.time()):.0f}s dual={s.get('dualEnabled')} "
                    f"url={bool(url)} dur={dur} status={s.get('statusLine')!r}",
                    flush=True,
                )
                if 5 < dur < 120 and s.get("dualEnabled"):
                    break
                if dur >= 200:
                    break
                page.wait_for_timeout(2000)

            after = report["samples"][-1] if report["samples"] else snap(page)
            report["after"] = after
            report["ui_after"] = cycle_ui(page)
            report["canon_after"] = read_canon(page)
            report["first_fail"] = classify_first_fail(before, after, report["samples"])
            report["runtime_tail"] = runtime_tail()
            report["console_tail"] = console[-20:]
            report["ok"] = report["first_fail"] == "short_ok"
            print("RESULT", report["first_fail"], flush=True)
        except Exception as exc:
            report["error"] = str(exc)
            print("ERROR", exc, flush=True)
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", OUT, flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

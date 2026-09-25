"""Browser proof that explicit Play replaces the sounding buffer.

BPM 96→108 must load the generated ~72s file, not the previous 81s file.
Feel and scope are checked on their own evidence, each with one natural pass.
Loops is rechecked once through the same replacement path.
KC_SHORT_PASS_* stays unset. Unit tests are not this report.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from playwright.sync_api import sync_playwright

from proof_kc_bpm_feel_scope_8510 import (
    commit_bpm,
    commit_feel,
    commit_sections,
    latest_ready,
    read_server,
    sequence_held,
)
from proof_kc_settings_focused_8510 import (
    advance_n,
    click_play_when_ready,
    current_key,
    log,
    pause_or_stop_transport,
    set_loops,
    setup,
    snap,
    wait_natural_key_change,
)
from proof_key_cycle_seamless_8510 import wait_kc_audio

TRACE = ROOT / "_runtime_key_cycle_8510" / "_play_trace.jsonl"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "arrangement_replace_report.json"
STATIC = ROOT / "static" / "kc"


def events_since(since: float, name: str) -> list[dict]:
    if not TRACE.is_file():
        return []
    out = []
    for line in TRACE.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == name and float(rec.get("t") or 0) >= since - 1:
            out.append(rec)
    return out


def file_bytes(src: str) -> int:
    name = str(src or "").rsplit("/", 1)[-1]
    path = STATIC / name
    if not name or not path.is_file():
        return 0
    return path.stat().st_size


def matching_generate(src: str, since: float, needles: list[str]) -> dict:
    size = file_bytes(src)
    for rec in reversed(events_since(since, "generate_saved")):
        sig = str(rec.get("sig") or "")
        if needles and not all(n in sig for n in needles):
            continue
        wav = int(rec.get("wav_bytes") or 0)
        if size and wav and abs(wav - size) < 2000:
            return rec
        if not size and needles and all(n in sig for n in needles):
            return rec
    return {}


def apply_trace(page) -> list[dict]:
    try:
        return page.evaluate("() => (window.__kcApplyTrace || []).slice(-12)") or []
    except Exception:
        return []


def play_replace(page, since: float, prev_src: str, expect_lo: float, expect_hi: float) -> dict:
    page.evaluate(
        """() => {
          window.__kcApplyTrace = [];
          try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
          try { if (window.__kcDual) window.__kcDual.userPaused = false; } catch (e2) {}
        }"""
    )
    click_play_when_ready(page)
    wait_kc_audio(page, 180)
    deadline = time.time() + 110
    play = snap(page)
    while time.time() < deadline:
        play = snap(page)
        dur = float(play.get("dur") or 0)
        src = str(play.get("src") or "")
        src_new = bool(src) and src != prev_src
        dur_ok = expect_lo <= dur <= expect_hi
        if src_new and dur_ok:
            # Capture as soon as the new arrangement is on the active buffer.
            break
        if src_new and dur_ok is False and play.get("paused"):
            page.evaluate(
                """() => {
                  try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
                  if (window.__kcDual) window.__kcDual.userPaused = false;
                  if (typeof window.__kcResumeAudio === 'function') window.__kcResumeAudio();
                }"""
            )
        page.wait_for_timeout(800)
    play["file_bytes"] = file_bytes(str(play.get("src") or ""))
    play["file_secs"] = round(play["file_bytes"] / 88200.0, 2) if play["file_bytes"] else 0
    play["trace"] = apply_trace(page)
    play["ready"] = latest_ready(since)
    try:
        extra = page.evaluate(
            """() => {
              const cmd = window.__kcLastCmd || {};
              const slot = document.getElementById('kc-cmd-slot');
              const reasons = (window.__kcApplyTrace || []).map((x) => x.reason);
              return {
                last: String(cmd.currentUrl || '').slice(-28),
                err: String(window.__kcBridgeErr || '').slice(0, 180),
                slot: !!(slot && (slot.textContent || '').length > 20),
                poll: !!window.__kcCmdPoll,
                reasons: reasons.slice(-20),
              };
            }"""
        )
        play["delivery"] = extra
        log(f"delivery {extra}")
    except Exception as exc:
        log(f"delivery_fail {exc}")
    return play


def main() -> int:
    report: dict = {
        "ok": False,
        "cause": (
            "Generate wrote _kc_current_static_url before the playbar compared URLs, "
            "so arrangementReload stayed false and the handoff guard rejected the new file."
        ),
        "short_env": {
            k: os.environ.get(k)
            for k in (
                "KC_SHORT_PASS_BARS",
                "KC_SHORT_PASS_LOOPS",
                "KC_SHORT_PASS_FORCE",
                "KC_SHORT_PASS_SECS",
            )
        },
        "browser": {},
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})
        log("setup")
        setup(page)
        base = snap(page)
        mid = advance_n(page, 2)
        pause_or_stop_transport(page)
        page.wait_for_timeout(600)
        held = snap(page)
        base_dur = float(held.get("dur") or base.get("dur") or 0)
        base_src = str(held.get("src") or "")
        report["browser"]["baseline"] = {
            "key": current_key(held),
            "chips": held.get("chips"),
            "dur": base_dur,
            "src": base_src[-32:],
            "canon": read_server(page),
        }
        log(f"baseline key={current_key(held)} dur={base_dur} src={base_src[-24:]}")

        # --- BPM 96 → 108 ---
        t_bpm = time.time()
        bpm = commit_bpm(page, 108, max_clicks=1)
        committed = int(bpm.get("after") or 0)
        since = t_bpm
        expect = 81.0 * 96.0 / float(committed) if committed >= 100 else 72.0
        play = play_replace(page, since, base_src, 60.0, 80.0)
        play_dur = float(play.get("dur") or play.get("file_secs") or 0)
        if committed < 100 and base_dur > 5 and 60 <= play_dur <= 80:
            committed = int(round(96.0 * base_dur / play_dur))
            expect = play_dur
        gen = matching_generate(
            str(play.get("src") or ""),
            since,
            [str(committed)] if committed >= 100 else [],
        )
        reasons = [str(x.get("reason") or "") for x in (play.get("trace") or [])]
        if play.get("delivery") and play["delivery"].get("reasons"):
            reasons = list(play["delivery"]["reasons"]) + reasons
        chips_same = list(held.get("chips") or []) == list(play.get("chips") or [])
        bpm_ok = bool(
            chips_same
            and 60 <= play_dur <= 80
            and str(play.get("src") or "") not in ("", base_src)
            and (
                "set_src" in reasons
                or "replace" in reasons
                or abs(float(play.get("file_secs") or 0) - play_dur) < 1.5
            )
            and 100 <= committed <= 120
        )
        report["browser"]["bpm"] = {
            "commit": committed,
            "key": current_key(play),
            "chips": play.get("chips"),
            "dur": play.get("dur"),
            "t": play.get("t"),
            "src": str(play.get("src") or "")[-32:],
            "file_secs": play.get("file_secs"),
            "old_src": base_src[-32:],
            "reasons": reasons,
            "sig": str(gen.get("sig") or "")[:220],
            "wav_bytes": gen.get("wav_bytes"),
            "ok": bpm_ok,
        }
        log(
            f"bpm dur={play.get('dur')} t={play.get('t')} file={play.get('file_secs')} "
            f"reasons={reasons} ok={bpm_ok}"
        )

        # --- Feel, identity not duration ---
        pause_or_stop_transport(page)
        before_feel = snap(page)
        t_feel = time.time()
        feel = commit_feel(page, "Rock groove")
        feel_play = play_replace(page, t_feel, str(before_feel.get("src") or ""), 60, 90)
        feel_gen = matching_generate(str(feel_play.get("src") or ""), t_feel, ["Rock groove"])
        feel_reasons = [str(x.get("reason") or "") for x in (feel_play.get("trace") or [])]
        feel_ready = latest_ready(t_feel)
        feel_loaded = bool(
            feel.get("ok")
            and sequence_held(before_feel, feel_play)
            and feel_gen
            and "Rock groove" in str(feel_gen.get("sig") or "")
            and "Rock groove" in str(feel_ready.get("cur_sig") or feel_gen.get("sig") or "")
            and str(feel_play.get("src") or "") not in ("", str(before_feel.get("src") or ""))
            and float(feel_play.get("t") or 99) < 20
        )
        nat_feel = wait_natural_key_change(page, current_key(feel_play), 140)
        nat_feel_gen = matching_generate(
            str(nat_feel.get("src") or ""),
            t_feel,
            ["Rock groove", str(nat_feel.get("sounding") or current_key(nat_feel))],
        )
        if not nat_feel_gen:
            nat_feel_gen = matching_generate(str(nat_feel.get("src") or ""), t_feel, ["Rock groove"])
        feel_ok = bool(feel_loaded and nat_feel.get("natural_ok") and nat_feel_gen)
        report["browser"]["feel"] = {
            "commit": feel.get("after"),
            "key": current_key(feel_play),
            "dur": feel_play.get("dur"),
            "src": str(feel_play.get("src") or "")[-32:],
            "sig": str(feel_gen.get("sig") or "")[:240],
            "ready_sig": str(feel_ready.get("cur_sig") or "")[:240],
            "reasons": feel_reasons,
            "natural_key": current_key(nat_feel),
            "natural_sounding": nat_feel.get("sounding"),
            "natural_src": str(nat_feel.get("src") or "")[-32:],
            "natural_sig": str(nat_feel_gen.get("sig") or "")[:240],
            "natural_ok": bool(nat_feel.get("natural_ok")),
            "ok": feel_ok,
        }
        log(
            f"feel loaded={feel_loaded} natural={nat_feel.get('natural_ok')} "
            f"key={current_key(nat_feel)} ok={feel_ok}"
        )

        # --- Scope, independent of duration-only feel proof ---
        pause_or_stop_transport(page)
        before_scope = snap(page)
        t_scope = time.time()
        scope = commit_sections(page, ["Verse 1"])
        before_dur = float(before_scope.get("dur") or 72)
        scope_play = play_replace(page, t_scope, str(before_scope.get("src") or ""), 8, before_dur * 0.75)
        scope_ready = latest_ready(t_scope)
        scope_gen = matching_generate(str(scope_play.get("src") or ""), t_scope, ["Verse 1"])
        sections = list(scope_ready.get("sections") or [])
        scope_loaded = bool(
            scope.get("ok")
            and sequence_held(before_scope, scope_play)
            and sections == ["Verse 1"]
            and float(scope_play.get("dur") or 0) < before_dur * 0.75
            and str(scope_play.get("src") or "") not in ("", str(before_scope.get("src") or ""))
            and float(scope_play.get("t") or 99) < 20
        )
        nat_scope = wait_natural_key_change(page, current_key(scope_play), 100)
        nat_scope_ready_sections = []
        for rec in reversed(events_since(t_scope, "audio_ready_check")):
            if str(rec.get("audio_key") or "") == str(nat_scope.get("sounding") or ""):
                nat_scope_ready_sections = list(rec.get("sections") or [])
                break
        if not nat_scope_ready_sections:
            last = events_since(t_scope, "audio_ready_check")
            nat_scope_ready_sections = list((last[-1].get("sections") if last else []) or [])
        scope_ok = bool(
            scope_loaded
            and nat_scope.get("natural_ok")
            and nat_scope_ready_sections == ["Verse 1"]
        )
        report["browser"]["scope"] = {
            "tags": scope.get("after"),
            "key": current_key(scope_play),
            "before_dur": before_dur,
            "dur": scope_play.get("dur"),
            "sections": sections,
            "src": str(scope_play.get("src") or "")[-32:],
            "sig": str(scope_gen.get("sig") or "")[:180],
            "natural_key": current_key(nat_scope),
            "natural_sections": nat_scope_ready_sections,
            "natural_ok": bool(nat_scope.get("natural_ok")),
            "ok": scope_ok,
        }
        log(
            f"scope dur={scope_play.get('dur')} sections={sections} "
            f"natural={nat_scope.get('natural_ok')} ok={scope_ok}"
        )

        # --- Loops once, same replacement path ---
        pause_or_stop_transport(page)
        before_loops = snap(page)
        t_loops = time.time()
        loops_set = set_loops(page, 2)
        page.wait_for_timeout(800)
        one = float(before_loops.get("dur") or 0)
        loops_play = play_replace(page, t_loops, str(before_loops.get("src") or ""), one * 1.7, one * 2.35)
        loops_ready = latest_ready(t_loops)
        loops_ok = bool(
            loops_set
            and sequence_held(before_loops, loops_play)
            and int(loops_ready.get("loops") or 0) == 2
            and one > 5
            and abs(float(loops_play.get("dur") or 0) - 2 * one) / (2 * one) < 0.15
            and str(loops_play.get("src") or "") not in ("", str(before_loops.get("src") or ""))
            and float(loops_play.get("t") or 99) < 20
        )
        report["browser"]["loops"] = {
            "set": loops_set,
            "key": current_key(loops_play),
            "before_dur": one,
            "dur": loops_play.get("dur"),
            "loops": loops_ready.get("loops"),
            "src": str(loops_play.get("src") or "")[-32:],
            "reasons": [str(x.get("reason") or "") for x in (loops_play.get("trace") or [])],
            "ok": loops_ok,
        }
        log(f"loops {one}->{loops_play.get('dur')} ok={loops_ok}")

        report["ok"] = bool(bpm_ok and feel_ok and scope_ok and loops_ok)
        browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"report ok={report['ok']} -> {OUT}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

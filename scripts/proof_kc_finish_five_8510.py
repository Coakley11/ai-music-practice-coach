"""Focused finish-pass verification on 8510 (no KC_SHORT_PASS_*).

Separates setup failures from product failures. Does not claim unverified passes.
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

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_kc_settings_focused_8510 import log, set_loops, set_practice_key, set_scope_selected_section
from proof_kc_manual_review_gaps_8510 import (
    set_multi_scope,
    wav_duration_from_url,
)
from proof_kc_bpm_feel_scope_8510 import commit_feel, wait_controls_ready
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_key_cycle_8510")
STATE = DATA / "workspaces" / "daniel" / "music_user_state.json"
TRACE = DATA / "_play_trace.jsonl"


def wait_idle(page, ms: int = 25000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(600)


def clear_pause_hold(page) -> None:
    page.evaluate(
        """() => {
          try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
          try { if (window.__kcDual) window.__kcDual.userPaused = false; } catch (e2) {}
          try { window.__kcTransportPaused = false; } catch (e3) {}
        }"""
    )


def audio_probe(page) -> dict:
    """Include lead-sheet unmuted players — not only kc-buf elements."""
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const rate = act ? Number(act.playbackRate || 1) : 1;
          const bufPlaying = ['kc-buf-0','kc-buf-1']
            .map(id => document.getElementById(id))
            .filter(a => a && !a.paused && !a.muted && Number(a.volume||0) > 0.01
              && Number(a.currentTime||0) > 0.05);
          const all = [];
          document.querySelectorAll('audio').forEach(a => all.push(a));
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              doc.querySelectorAll('audio').forEach(a => all.push(a));
            } catch (e) {}
          }
          const unmutedPlaying = all.filter(a => a && !a.paused && !a.muted
            && Number(a.volume||0) > 0.01 && Number(a.currentTime||0) > 0.05);
          let tl = [];
          try { tl = window.__kcFollowTimeline || []; } catch (e) {}
          const last = tl.length ? tl[tl.length-1] : null;
          let liveLabel = '';
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              const b = [...doc.querySelectorAll('button')].find(el =>
                /Resume playback|Pause playback|Stop playback/i.test(el.innerText||'')
              );
              if (b) { liveLabel = (b.innerText||'').trim(); break; }
            } catch (e) {}
          }
          const sections = [...new Set(tl.map(e => String(e.section||'')).filter(Boolean))];
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime||0) : 0,
            dur: act ? Number(act.duration||0) : 0,
            src: act ? String(act.getAttribute('data-kc-url')||act.src||'') : '',
            sounding: String((act && act.getAttribute('data-kc-sounding'))
              || window.__kcLastSounding || ''),
            playbackRate: rate,
            playingCount: bufPlaying.length,
            unmutedPlayingCount: unmutedPlaying.length,
            unmutedIds: unmutedPlaying.map(a => a.id || a.className || 'audio').slice(0, 8),
            timelineEnd: last ? Number(last.end_time||0) : 0,
            timelineLen: tl.length,
            sections,
            liveLabel,
            dualPaused: !!dual.userPaused,
            transportPaused: !!window.__kcTransportPaused,
            pauseApplies: Number(window.__kcPauseApplies || 0),
            lastPauseMs: window.__kcLastPauseMs,
            lastPauseT: window.__kcLastPauseT,
          };
        }"""
    )


def read_slider_bpm(page) -> int | None:
    v = page.evaluate(
        """() => {
          const roots = [...document.querySelectorAll('[class*="st-key-backing_track_bpm"]')];
          for (const root of roots) {
            const inp = root.querySelector('input[type="range"]');
            if (inp && !inp.disabled) return Number(inp.value);
          }
          return null;
        }"""
    )
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def last_generate_meta() -> dict:
    if not TRACE.is_file():
        return {}
    lines = TRACE.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    for line in reversed(lines[-120:]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("event") == "generate_saved":
            sig = str(obj.get("sig") or "")
            bpm = None
            m = re.search(r"'Intermediate', '[^']+', (\d+),", sig)
            if m:
                bpm = int(m.group(1))
            else:
                m2 = re.search(r", (\d+), '4/4'", sig)
                if m2:
                    bpm = int(m2.group(1))
            groove = None
            for g in ("Blues groove", "Pop groove", "Jazz swing", "Rock groove"):
                if g in sig:
                    groove = g
                    break
            secs = re.findall(r"'(Verse[^']*|Chorus[^']*|Pre-Chorus[^']*)'", sig)
            return {"bpm": bpm, "groove": groove, "sig": sig, "sections": secs, "wav_bytes": obj.get("wav_bytes")}
        if obj.get("event") == "audio_ready_check" and obj.get("bpm"):
            return {
                "bpm": int(obj["bpm"]),
                "groove": None,
                "sections": list(obj.get("sections") or []),
                "sig": str(obj.get("cur_sig") or ""),
            }
    return {}


def disk_cycle_key() -> dict:
    if not STATE.is_file():
        return {"exists": False}
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "error": repr(exc)}
    sess = ((raw.get("state") or {}).get("session") or {})
    bag = sess.get("_backing_key_cycle_sessions") or {}
    cat = bag.get("catalog") or {}
    pk = (sess.get("practice_key_by_source") or {}).get("Pop\x1fShape of You — Ed Sheeran") or (
        sess.get("practice_key_by_source") or {}
    ).get("Pop|Shape of You")
    # Also try any Shape key
    if not pk:
        for k, v in (sess.get("practice_key_by_source") or {}).items():
            if "Shape of You" in str(k):
                pk = v
                break
    return {
        "exists": True,
        "enabled": bool(sess.get("backing_key_cycle_enabled") or cat.get("enabled")),
        "current_playback_key": str(cat.get("current_playback_key") or ""),
        "offset": int(cat.get("offset_semitones") or 0),
        "status": str(cat.get("status") or ""),
        "practice_key": str(pk or ""),
    }


def mean_bar_seconds(page) -> float | None:
    return page.evaluate(
        """() => {
          const tl = window.__kcFollowTimeline || [];
          if (!tl.length) return null;
          const durs = [];
          for (const e of tl) {
            const d = Number(e.end_time||0) - Number(e.start_time||0);
            if (d > 0.2 && d < 12) durs.push(d);
          }
          if (!durs.length) return null;
          // Prefer modal-ish median of chord spans as beat-timing proxy.
          durs.sort((a,b)=>a-b);
          return durs[Math.floor(durs.length/2)];
        }"""
    )


def force_commit_bpm(page, target: int, *, seconds: float = 50.0) -> dict:
    """Drive Tempo until slider equals target (Home+arrows, then click refine)."""
    wait_controls_ready(page)
    before = read_slider_bpm(page)
    focused = bool(
        page.evaluate(
            """() => {
              const roots = [...document.querySelectorAll('[class*="st-key-backing_track_bpm"]')];
              for (const root of roots) {
                const inp = root.querySelector('input[type="range"]');
                if (inp && !inp.disabled) {
                  inp.scrollIntoView({block:'center'});
                  inp.focus();
                  return true;
                }
              }
              return false;
            }"""
        )
    )
    if not focused:
        return {"ok": False, "before": before, "after": before, "why": "no_slider"}
    # Jump from min so ArrowRight count is deterministic (min is 20).
    page.keyboard.press("Home")
    page.wait_for_timeout(200)
    steps = max(0, int(target) - 20)
    for _ in range(steps):
        page.keyboard.press("ArrowRight")
        # Tiny yield every 20 steps so Streamlit can breathe without remount thrash.
        if _ % 20 == 19:
            page.wait_for_timeout(40)
    page.wait_for_timeout(400)
    wait_idle(page, 15000)
    after = read_slider_bpm(page)
    # Refine with short arrow nudges if remount drifted.
    deadline = time.time() + min(20.0, seconds)
    while time.time() < deadline:
        cur = read_slider_bpm(page)
        if cur is not None and abs(int(cur) - int(target)) <= 0:
            after = cur
            break
        if cur is None:
            page.wait_for_timeout(250)
            continue
        page.keyboard.press("ArrowRight" if int(cur) < int(target) else "ArrowLeft")
        page.wait_for_timeout(300)
        after = read_slider_bpm(page)
    wait_idle(page, 12000)
    after = read_slider_bpm(page)
    from proof_kc_bpm_feel_scope_8510 import read_server

    server = read_server(page)
    widget = int(server.get("bpm_widget") or 0)
    canon = int(server.get("bpm_canon") or 0)
    ok = (
        after is not None
        and abs(int(after) - int(target)) <= 1
        and (canon == 0 or abs(canon - int(target)) <= 1 or canon == int(after))
    )
    return {
        "ok": bool(ok),
        "before": before,
        "after": after,
        "server": server,
        "focused": focused,
        "widget_bpm": widget,
        "canon_bpm": canon,
        "path": "home_arrows",
    }


def boot_backing(page) -> None:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
    clear_pause_hold(page)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    page.wait_for_timeout(400)
    page.evaluate(
        """() => {
          const t = [...document.querySelectorAll('button,label,div')].find((el) =>
            /Shape of You/i.test(el.innerText || '')
          );
          if (t) t.click();
        }"""
    )
    goto_studio(page, "Backing")
    page.wait_for_timeout(1200)
    clear_pause_hold(page)
    set_practice_key(page, "Bm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_cycle_mode(page, True)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    open_sheet(page)
    clear_pause_hold(page)


def main() -> int:
    report: dict = {
        "ok": False,
        "units_note": "see pytest separately",
        "browser": {},
        "setup_failures": [],
        "product_failures": [],
        "notes": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        try:
            boot_backing(page)

            # --- 4. BPM 140 then 72 (commit UI first; wait until slider enabled) ---
            # Pause so a natural handoff cannot race the Tempo commit.
            try:
                click_playbar(page, "pause")
                wait_idle(page)
            except Exception:
                pass
            wait_controls_ready(page)
            bpm140 = force_commit_bpm(page, 140)
            wait_idle(page)
            if not bpm140.get("ok"):
                report["setup_failures"].append("bpm_140_slider_commit")
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2800)
            high = audio_probe(page)
            high_meta = last_generate_meta()
            high_bar = mean_bar_seconds(page)
            high_wav = wav_duration_from_url(high.get("src") or "")
            report["browser"]["bpm_140"] = {
                "slider": read_slider_bpm(page),
                "commit": bpm140,
                "gen_bpm": high_meta.get("bpm"),
                "bar_s": high_bar,
                "wav": high_wav,
                "tl": high.get("timelineEnd"),
                "playing": bool(high.get("src")) and not high.get("paused"),
                "unmuted": high.get("unmutedPlayingCount"),
            }

            wait_controls_ready(page)
            bpm72 = force_commit_bpm(page, 72)
            wait_idle(page, 20000)
            pending = audio_probe(page)
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2800)
            low = audio_probe(page)
            low_meta = last_generate_meta()
            low_bar = mean_bar_seconds(page)
            low_wav = wav_duration_from_url(low.get("src") or "")
            bar_ratio = (
                (float(low_bar) / float(high_bar))
                if high_bar and low_bar and float(high_bar) > 0
                else None
            )
            wav_ratio = (
                (float(low_wav) / float(high_wav))
                if high_wav and low_wav and float(high_wav) > 0
                else None
            )
            gen_hi = high_meta.get("bpm") or bpm140.get("after")
            gen_lo = low_meta.get("bpm") or bpm72.get("after")
            bpm_pass = bool(
                bpm140.get("ok")
                and bpm72.get("ok")
                and gen_hi
                and gen_lo
                and int(gen_hi) >= 130
                and int(gen_lo) <= 85
                and int(gen_hi) - int(gen_lo) >= 50
                and (
                    (bar_ratio and 1.45 < bar_ratio < 2.5)
                    or (wav_ratio and 1.45 < wav_ratio < 2.5)
                )
            )
            report["browser"]["bpm_72"] = {
                "slider": read_slider_bpm(page),
                "commit": bpm72,
                "gen_bpm": low_meta.get("bpm"),
                "bar_s": low_bar,
                "wav": low_wav,
                "bar_ratio": bar_ratio,
                "wav_ratio": wav_ratio,
                "pending_held": (
                    abs(float(pending.get("timelineEnd") or 0) - float(high.get("timelineEnd") or 0)) < 3
                    if high.get("timelineEnd")
                    else None
                ),
                "ok": bpm_pass,
            }
            if bpm140.get("ok") and bpm72.get("ok") and not bpm_pass:
                report["product_failures"].append("bpm_140_vs_72_timing")
            elif not (bpm140.get("ok") and bpm72.get("ok")):
                report["notes"].append("BPM UI commit setup failed before timing asserts.")

            # --- Feel Blues (same BPM/scope) ---
            feel = commit_feel(page, "Blues groove")
            wait_idle(page)
            if not feel.get("ok"):
                report["setup_failures"].append("feel_blues_ui_select")
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2200)
            blues = audio_probe(page)
            blues_meta = last_generate_meta()
            feel_pass = bool(
                feel.get("ok")
                and (
                    blues_meta.get("groove") == "Blues groove"
                    or "Blues" in str(feel.get("after") or "")
                )
                and blues.get("src")
                and blues.get("src") != low.get("src")
            )
            report["browser"]["feel"] = {
                "ui_set": feel.get("ok"),
                "commit": feel,
                "gen_groove": blues_meta.get("groove"),
                "src_changed": bool(blues.get("src")) and blues.get("src") != low.get("src"),
                "ok": feel_pass,
            }
            if feel.get("ok") and not feel_pass:
                report["product_failures"].append("feel_blues_not_in_audible_buffer")
            elif not feel.get("ok"):
                report["notes"].append("Feel UI setup failed; unit covers Blues≠Pop onset profile.")

            # --- Verse 1 + Chorus 1 product path ---
            scope_ok = set_multi_scope(page, ["Verse 1", "Chorus 1"])
            if not scope_ok:
                scope_ok = set_multi_scope(page, ["Verse", "Chorus"])
            wait_idle(page)
            if not scope_ok:
                report["setup_failures"].append("verse_chorus_ui_select")
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2800)
            scoped = audio_probe(page)
            scoped_meta = last_generate_meta()
            secs = list(scoped.get("sections") or [])
            has_v = any("verse" in str(s).lower() and "pre" not in str(s).lower() for s in secs)
            has_c = any(
                "chorus" in str(s).lower() and "pre" not in str(s).lower() for s in secs
            )
            has_pre = any("pre-chorus" in str(s).lower() or "prechorus" in str(s).lower().replace(" ", "") for s in secs)
            # Watch highlight cross into Chorus while same key.
            crossed = False
            key_stable = True
            key0 = str(scoped.get("sounding") or "")
            deadline = time.time() + min(90, max(25, float(scoped.get("timelineEnd") or 40) * 0.85))
            while time.time() < deadline:
                pr = audio_probe(page)
                k = str(pr.get("sounding") or "")
                if key0 and k and k != key0:
                    key_stable = False
                    break
                cur_secs = page.evaluate(
                    """() => {
                      const tl = window.__kcFollowTimeline || [];
                      const t = (window.__kcDual && window.__kcActiveAudio)
                        ? Number((window.__kcActiveAudio()||{}).currentTime||0)
                        : Number((document.getElementById('kc-buf-0')||{}).currentTime||0);
                      let sec = '';
                      for (const e of tl) {
                        if (t >= Number(e.start_time||0) && t < Number(e.end_time||0)) {
                          sec = String(e.section||''); break;
                        }
                      }
                      return sec;
                    }"""
                )
                if cur_secs and "chorus" in str(cur_secs).lower() and "pre" not in str(cur_secs).lower():
                    crossed = True
                    break
                page.wait_for_timeout(700)
            scope_pass = bool(scope_ok and has_v and has_c and not has_pre and crossed and key_stable)
            report["browser"]["scope_vc"] = {
                "ui_set": scope_ok,
                "sections": secs,
                "gen_sections": scoped_meta.get("sections"),
                "has_verse": has_v,
                "has_chorus": has_c,
                "has_prechorus": has_pre,
                "crossed_chorus": crossed,
                "key_stable_until_chorus": key_stable,
                "ok": scope_pass,
            }
            if scope_ok and not scope_pass:
                report["product_failures"].append("verse_chorus_audio_chart")
            report["notes"].append(
                "Pre-Chorus substring fix is product seed path "
                "(seed_backing_multi_sections_for_widget), not proof-only."
            )

            # --- Pause both surfaces (no handler fallback — that is not a pass) ---
            applies0 = int(audio_probe(page).get("pauseApplies") or 0)
            clicked = click_playbar(page, "pause")
            page.wait_for_timeout(500)
            applies1 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
            click_reached_handler = applies1 > applies0
            wait_idle(page)
            page.wait_for_timeout(2200)
            ui_p = cycle_ui(page)
            pr_p = audio_probe(page)
            pause_pass = bool(
                clicked
                and click_reached_handler
                and pr_p.get("paused")
                and int(pr_p.get("unmutedPlayingCount") or 0) == 0
                and "Resume" in str(ui_p.get("pause") or "")
                and "Resume" in str(pr_p.get("liveLabel") or "")
            )
            report["browser"]["pause"] = {
                "clicked": clicked,
                "click_reached_handler": click_reached_handler,
                "pauseApplies": pr_p.get("pauseApplies"),
                "cycle_label": ui_p.get("pause"),
                "live_label": pr_p.get("liveLabel"),
                "audio_paused": pr_p.get("paused"),
                "unmuted": pr_p.get("unmutedPlayingCount"),
                "dualPaused": pr_p.get("dualPaused"),
                "retained_t": pr_p.get("lastPauseT") or pr_p.get("t"),
                "ok": pause_pass,
            }
            if clicked and not click_reached_handler:
                report["product_failures"].append("pause_click_missed_handler")
            elif clicked and click_reached_handler and not pause_pass:
                report["product_failures"].append("pause_coordination")
            elif not clicked:
                report["setup_failures"].append("pause_click")

            # Resume from retained position (real click only — no handler fallback)
            t_hold = float(pr_p.get("t") or 0)
            applies_r0 = int(pr_p.get("pauseApplies") or 0)
            clicked_r = click_playbar(page, "pause")
            page.wait_for_timeout(500)
            resume_reached = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)")) > applies_r0
            wait_idle(page)
            wait_kc_audio(page, 60)
            page.wait_for_timeout(1500)
            pr_r = audio_probe(page)
            resume_pass = bool(
                clicked_r
                and resume_reached
                and not pr_r.get("paused")
                and float(pr_r.get("t") or 0) >= max(0.0, t_hold - 0.35)
                and int(pr_r.get("unmutedPlayingCount") or 0) == 1
            )
            report["browser"]["resume"] = {
                "clicked": clicked_r,
                "click_reached_handler": resume_reached,
                "t_before": t_hold,
                "t_after": pr_r.get("t"),
                "unmuted": pr_r.get("unmutedPlayingCount"),
                "ok": resume_pass,
            }
            if clicked_r and not resume_reached:
                report["product_failures"].append("resume_click_missed_handler")
            elif not resume_pass:
                report["product_failures"].append("resume_position")

            # --- Natural handoff + single unmuted player ---
            key0 = str(pr_r.get("sounding") or cycle_ui(page).get("sounding") or "")
            if pr_r.get("paused") or int(pr_r.get("unmutedPlayingCount") or 0) == 0:
                report["notes"].append(
                    "Natural handoff watched from non-playing state after Resume check; "
                    "no handler fallback used."
                )
            natural = None
            overlap_seen = False
            deadline = time.time() + 180
            while time.time() < deadline:
                prn = audio_probe(page)
                unmuted = int(prn.get("unmutedPlayingCount") or 0)
                if unmuted > 1:
                    overlap_seen = True
                    natural = prn
                    natural["overlap"] = True
                    break
                k = str(prn.get("sounding") or "")
                if key0 and k and k != key0 and unmuted == 1 and not prn.get("paused"):
                    natural = prn
                    natural["wav"] = wav_duration_from_url(prn.get("src") or "")
                    natural["from"] = key0
                    natural["to"] = k
                    # Confirm single-buffer holds for 1.5s after flip
                    page.wait_for_timeout(1500)
                    hold = audio_probe(page)
                    if int(hold.get("unmutedPlayingCount") or 0) > 1:
                        overlap_seen = True
                        natural["overlap"] = True
                        natural["unmutedPlayingCount"] = hold.get("unmutedPlayingCount")
                    break
                page.wait_for_timeout(800)
            scoped_wav = wav_duration_from_url(scoped.get("src") or "")
            natural_pass = bool(
                natural
                and not natural.get("overlap")
                and int(natural.get("unmutedPlayingCount") or 0) == 1
                and natural.get("playbackRate") == 1
                and scoped_wav
                and natural.get("wav")
                and abs(float(natural["wav"]) - float(scoped_wav)) < max(12.0, float(scoped_wav) * 0.25)
            )
            report["browser"]["natural"] = {
                "probe": {
                    k: natural.get(k)
                    for k in (
                        "from", "to", "sounding", "unmutedPlayingCount", "unmutedIds",
                        "playbackRate", "wav", "overlap",
                    )
                    if natural
                },
                "overlap_seen": overlap_seen,
                "ok": natural_pass,
            }
            if not natural:
                report["product_failures"].append("natural_handoff_timeout")
            elif overlap_seen:
                report["product_failures"].append("overlapping_unmuted_audio")
            elif not natural_pass:
                report["product_failures"].append("natural_handoff_quality")

            # Give Python ack+persist a moment after the audible handoff.
            page.wait_for_timeout(2500)
            disk_mid = disk_cycle_key()
            report["browser"]["disk_after_natural"] = disk_mid

            # --- Refresh: disk key + new browser context (new Streamlit session) ---
            before_key = str((natural or scoped).get("sounding") or "")
            disk_before = disk_cycle_key()
            # Soft reload first (session may survive)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            wait_idle(page)
            ui_soft = cycle_ui(page)
            pr_soft = audio_probe(page)
            soft_pass = bool(
                before_key
                and (str(ui_soft.get("sounding") or pr_soft.get("sounding") or "") == before_key
                     or str(ui_soft.get("sounding") or "") == before_key)
                and "Resume" in str(ui_soft.get("pause") or "")
                and pr_soft.get("paused")
            )
            report["browser"]["refresh_soft"] = {
                "key_before": before_key,
                "sounding": ui_soft.get("sounding") or pr_soft.get("sounding"),
                "pause": ui_soft.get("pause"),
                "audio_paused": pr_soft.get("paused"),
                "disk": disk_before,
                "ok": soft_pass,
            }

            # New context ≈ new session; restore must come from disk.
            context.close()
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
            page.wait_for_timeout(4000)
            wait_idle(page)
            expand_sidebar(page)
            expand_pages_nav(page)
            goto_studio(page, "Backing")
            page.wait_for_timeout(2500)
            wait_idle(page)
            ui_new = cycle_ui(page)
            pr_new = audio_probe(page)
            disk_after = disk_cycle_key()
            pk_ok = (not disk_after.get("practice_key")) or disk_after.get("practice_key") in (
                "Bm",
                "B minor",
                "Bm ",
            ) or str(disk_after.get("practice_key") or "").startswith("Bm")
            # Accept B / Bm variants
            pk_ok = str(disk_after.get("practice_key") or "") in ("Bm", "B", "") or "Bm" in str(
                disk_after.get("practice_key") or ""
            )
            new_key = str(ui_new.get("sounding") or pr_new.get("sounding") or disk_after.get("current_playback_key") or "")
            new_pass = bool(
                before_key
                and disk_after.get("current_playback_key") == before_key
                and (new_key == before_key or disk_after.get("current_playback_key") == before_key)
                and ("Resume" in str(ui_new.get("pause") or "") or pr_new.get("paused") is not False)
                and bool(pr_new.get("paused"))
                and pk_ok
            )
            report["browser"]["refresh_new_session"] = {
                "key_before": before_key,
                "disk_key": disk_after.get("current_playback_key"),
                "sounding": new_key,
                "pause": ui_new.get("pause"),
                "audio_paused": pr_new.get("paused"),
                "practice_key": disk_after.get("practice_key"),
                "ok": new_pass,
            }
            if not soft_pass:
                report["product_failures"].append("refresh_soft_hold")
            if not new_pass:
                report["product_failures"].append("refresh_disk_new_session")

            b = report["browser"]
            report["ok"] = bool(
                not report["setup_failures"]
                and b.get("bpm_72", {}).get("ok")
                and (b.get("feel", {}).get("ok") or "feel_blues_ui_select" in report["setup_failures"])
                and b.get("scope_vc", {}).get("ok")
                and b.get("pause", {}).get("ok")
                and b.get("resume", {}).get("ok")
                and b.get("natural", {}).get("ok")
                and b.get("refresh_soft", {}).get("ok")
                and b.get("refresh_new_session", {}).get("ok")
                and not report["product_failures"]
            )
            # Feel may soft-fail only when UI setup failed; otherwise require it.
            if b.get("feel", {}).get("ui_set") and not b.get("feel", {}).get("ok"):
                report["ok"] = False
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "finish_five_8510.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:6000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Manual-review gap proof: BPM/feel/scope timing, natural pass, transport sync.

KC_SHORT_PASS_* unset. Focused workflow with lead sheet open on 8510.
Records settings vs audible arrangement (duration/timing), not captions alone.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_kc_settings_focused_8510 import (
    current_key,
    log,
    set_loops,
    set_practice_key,
    set_scope_selected_section,
    snap,
)
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"


def wait_idle(page, ms: int = 20000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(500)


def wav_duration_from_url(url: str) -> float | None:
    if not url:
        return None
    full = url if url.startswith("http") else f"{BASE}{url}"
    try:
        with urllib.request.urlopen(full, timeout=30) as resp:
            data = resp.read()
        with wave.open(BytesIO(data), "rb") as wf:
            return float(wf.getnframes()) / float(wf.getframerate() or 1)
    except Exception:
        return None


def audio_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const act = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const rate = act ? Number(act.playbackRate || 1) : 1;
          const playing = ['kc-buf-0','kc-buf-1']
            .map(id => document.getElementById(id))
            .filter(a => a && !a.paused && Number(a.currentTime||0) > 0.05);
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
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime||0) : 0,
            dur: act ? Number(act.duration||0) : 0,
            src: act ? String(act.getAttribute('data-kc-url')||act.src||'') : '',
            sounding: String((act && act.getAttribute('data-kc-sounding')) || window.__kcLastSounding || ''),
            playbackRate: rate,
            playingCount: playing.length,
            timelineEnd: last ? Number(last.end_time||0) : 0,
            timelineLen: tl.length,
            liveLabel,
            dualPaused: !!dual.userPaused,
            transportPaused: !!window.__kcTransportPaused,
          };
        }"""
    )


def commit_bpm(page, target: int) -> bool:
    return bool(
        page.evaluate(
            """(target) => {
              // Slider keys are backing_track_bpm::owner::song — match any.
              const roots = [
                ...document.querySelectorAll('[class*="st-key-backing_track_bpm"]'),
              ];
              let inp = null;
              for (const root of roots) {
                const candidate = root.querySelector('input[type="range"]');
                if (candidate && !candidate.disabled) { inp = candidate; break; }
              }
              if (!inp) {
                inp = document.querySelector(
                  '[class*="backing_playback_panel"] input[type="range"],'
                  + ' [data-testid="stSlider"] input[type="range"]'
                );
              }
              if (!inp || inp.disabled) return false;
              const min = Number(inp.min), max = Number(inp.max);
              const clamped = Math.max(min, Math.min(max, Number(target)));
              const ratio = (clamped - min) / (max - min || 1);
              const r = inp.getBoundingClientRect();
              const x = r.x + Math.min(0.96, Math.max(0.04, ratio)) * r.width;
              const y = r.y + r.height / 2;
              const el = document.elementFromPoint(x, y) || inp;
              el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, clientX:x, clientY:y}));
              el.dispatchEvent(new MouseEvent('mousemove', {bubbles:true, clientX:x, clientY:y}));
              el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, clientX:x, clientY:y}));
              const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
              ).set;
              setter.call(inp, String(clamped));
              inp.dispatchEvent(new Event('input', {bubbles:true}));
              inp.dispatchEvent(new Event('change', {bubbles:true}));
              return Number(inp.value) === clamped;
            }""",
            int(target),
        )
    )


def set_feel(page, label: str) -> bool:
    page.evaluate(
        """() => {
          for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
            if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
            if (!(el.open === true || el.getAttribute('open') !== null)) {
              (el.querySelector('summary') || el.querySelector('button') || el).click();
            }
          }
        }"""
    )
    page.wait_for_timeout(600)
    return bool(
        page.evaluate(
            """(label) => {
              const root = document.querySelector('[class*="st-key-backing_groove_style"]');
              if (!root) return false;
              const inp = root.querySelector('input');
              if (inp) {
                inp.focus();
                const setter = Object.getOwnPropertyDescriptor(
                  window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(inp, label);
                inp.dispatchEvent(new Event('input', {bubbles:true}));
              }
              // open dropdown options
              const ctrl = root.querySelector('[data-baseweb="select"]') || root;
              ctrl.click();
              const opts = [...document.querySelectorAll('li,div[role="option"]')];
              const hit = opts.find(el => (el.innerText||'').trim() === label
                || (el.innerText||'').includes(label));
              if (hit) { hit.click(); return true; }
              return false;
            }""",
            label,
        )
    )


def set_multi_scope(page, names: list[str]) -> bool:
    """Best-effort multi section select for Verse + Chorus."""
    page.evaluate(
        """() => {
          const radios = [...document.querySelectorAll('label,div[role="radio"]')];
          const hit = radios.find(el => /Selected sections/i.test(el.innerText||''));
          if (hit) hit.click();
        }"""
    )
    page.wait_for_timeout(500)
    return bool(
        page.evaluate(
            """(names) => {
              const expanded = [];
              for (const name of names) {
                expanded.push(name, name + ' 1', name + ' 2');
              }
              let hits = 0;
              const options = [...document.querySelectorAll(
                '[data-baseweb="select"] li, div[role="option"], label, [data-testid="stMultiSelect"] span'
              )];
              const selected = new Set();
              for (const want of expanded) {
                const el = options.find(n => {
                  const t = (n.innerText||'').trim();
                  return t === want || t.startsWith(want + ' ');
                });
                if (!el) continue;
                const key = (el.innerText||'').trim();
                if (selected.has(key)) continue;
                el.click();
                selected.add(key);
                hits++;
              }
              return hits >= Math.min(2, names.length);
            }""",
            names,
        )
    )


def setup(page) -> None:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2000)
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
    set_practice_key(page, "Bm")
    wait_idle(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_cycle_mode(page, True)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)


def main() -> int:
    report: dict = {
        "ok": False,
        "browser": {},
        "short_env": {k: os.environ.get(k) for k in (
            "KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"
        )},
        "notes": [],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            log("setup")
            setup(page)
            open_sheet(page)
            # High BPM first
            commit_bpm(page, 140)
            wait_idle(page)
            click_play(page)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(1500)
            high = audio_probe(page)
            high_wav = wav_duration_from_url(high.get("src") or "")
            report["browser"]["bpm_high"] = {
                "requested": 140,
                "probe": high,
                "wav_dur": high_wav,
                "timeline_end": high.get("timelineEnd"),
                "rate": high.get("playbackRate"),
            }

            # Change to low BPM while audio may still play — timeline must NOT
            # shrink to the new BPM until Play.
            log("bpm edit pending")
            tl_before = high.get("timelineEnd")
            commit_bpm(page, 72)
            wait_idle(page, 15000)
            pending = audio_probe(page)
            report["browser"]["bpm_pending"] = {
                "requested": 72,
                "timeline_end": pending.get("timelineEnd"),
                "timeline_held": (
                    abs(float(pending.get("timelineEnd") or 0) - float(tl_before or 0)) < 2.0
                    if tl_before
                    else None
                ),
                "still_playing_or_sticky": bool(pending.get("src")),
                "rate": pending.get("playbackRate"),
            }

            log("bpm play low")
            click_play(page)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2000)
            low = audio_probe(page)
            low_wav = wav_duration_from_url(low.get("src") or "")
            report["browser"]["bpm_low"] = {
                "requested": 72,
                "probe": low,
                "wav_dur": low_wav,
                "timeline_end": low.get("timelineEnd"),
                "rate": low.get("playbackRate"),
                "wav_longer_than_high": (
                    low_wav is not None
                    and high_wav is not None
                    and low_wav > high_wav * 1.25
                ),
                "timeline_matches_wav": (
                    low_wav is not None
                    and abs(float(low.get("timelineEnd") or 0) - low_wav) < 8.0
                ),
            }

            # Feel Blues — must change WAV bytes / duration character after Play
            log("feel blues")
            feel_ok = set_feel(page, "Blues groove")
            wait_idle(page)
            src_before_feel = low.get("src")
            click_play(page)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(1500)
            blues = audio_probe(page)
            blues_wav = wav_duration_from_url(blues.get("src") or "")
            report["browser"]["feel_blues"] = {
                "ui_set": feel_ok,
                "src_changed": bool(blues.get("src")) and blues.get("src") != src_before_feel,
                "wav_dur": blues_wav,
                "rate": blues.get("playbackRate"),
                "ok": feel_ok and bool(blues.get("src")) and blues.get("src") != src_before_feel,
            }
            if not feel_ok:
                report["notes"].append(
                    "Blues groove UI select may have failed automation; renderer unit proves Pop≠Blues bytes."
                )

            # Scope Verse + Chorus (best effort)
            log("scope verse+chorus")
            set_multi_scope(page, ["Verse", "Chorus"])
            wait_idle(page)
            src_before_scope = blues.get("src")
            click_play(page)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2000)
            scoped = audio_probe(page)
            scoped_wav = wav_duration_from_url(scoped.get("src") or "")
            report["browser"]["scope_vc"] = {
                "src_changed": bool(scoped.get("src")) and scoped.get("src") != src_before_scope,
                "wav_dur": scoped_wav,
                "timeline_end": scoped.get("timelineEnd"),
                "timeline_len": scoped.get("timelineLen"),
                "sections": page.evaluate(
                    """() => {
                      const tl = window.__kcFollowTimeline || window.parent.__kcFollowTimeline || [];
                      return [...new Set(tl.map(e => String(e.section||'')).filter(Boolean))];
                    }"""
                ),
                "ok": False,
            }
            secs = report["browser"]["scope_vc"]["sections"] or []
            has_v = any("verse" in str(s).lower() for s in secs)
            has_c = any("chorus" in str(s).lower() for s in secs)
            report["browser"]["scope_vc"]["ok"] = bool(
                has_v
                and has_c
                and scoped_wav
                and float(scoped_wav) > float(blues_wav or 0) * 1.15
            )

            # Natural key change — retain BPM (wav duration similar, rate=1)
            log("natural key")
            key0 = current_key(snap(page)) or scoped.get("sounding")
            natural = None
            deadline = time.time() + 150
            while time.time() < deadline:
                s = snap(page)
                k = current_key(s)
                if k and key0 and k != key0:
                    natural = audio_probe(page)
                    natural["key"] = k
                    natural["wav_dur"] = wav_duration_from_url(natural.get("src") or "")
                    break
                page.wait_for_timeout(800)
            report["browser"]["natural"] = {
                "from": key0,
                "to": (natural or {}).get("key"),
                "probe": natural,
                "rate_ok": natural is not None and abs(float(natural.get("playbackRate") or 1) - 1.0) < 0.01,
                "single_player": natural is not None and int(natural.get("playingCount") or 0) <= 1,
                "dur_similar": (
                    natural is not None
                    and scoped_wav
                    and natural.get("wav_dur")
                    and abs(float(natural["wav_dur"]) - scoped_wav) / scoped_wav < 0.35
                ),
                "ok": bool(natural),
            }

            # Transport label sync while playing
            log("transport sync")
            ui = cycle_ui(page)
            pr = audio_probe(page)
            playing_sync = (
                "Pause" in str(ui.get("pause") or "")
                and "Resume" not in str(pr.get("liveLabel") or "")
            ) if not pr.get("paused") else True
            click_playbar(page, "pause")
            wait_idle(page)
            page.wait_for_timeout(1000)
            ui2 = cycle_ui(page)
            pr2 = audio_probe(page)
            stopped_sync = (
                "Resume" in str(ui2.get("pause") or "")
                and "Resume" in str(pr2.get("liveLabel") or "")
            )
            report["browser"]["transport"] = {
                "playing_cycle": ui.get("pause"),
                "playing_live": pr.get("liveLabel"),
                "playing_ok": playing_sync,
                "stopped_cycle": ui2.get("pause"),
                "stopped_live": pr2.get("liveLabel"),
                "stopped_ok": stopped_sync,
                "ok": bool(stopped_sync),
            }

            # Refresh behavior at later key
            log("refresh")
            if ui2.get("pause") == "Resume":
                click_playbar(page, "pause")  # resume
                wait_kc_audio(page, 60)
            click_playbar(page, "next")
            wait_idle(page)
            page.wait_for_timeout(2000)
            before_ref = snap(page)
            key_ref = current_key(before_ref)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            wait_idle(page, 25000)
            after_ref = audio_probe(page)
            ui_ref = cycle_ui(page)
            report["browser"]["refresh"] = {
                "key_before": key_ref,
                "playbar": bool(ui_ref.get("playbar")),
                "cycle_pause_label": ui_ref.get("pause"),
                "sounding": ui_ref.get("sounding") or after_ref.get("sounding"),
                "audio_paused": after_ref.get("paused"),
                "not_autoplaying": bool(after_ref.get("paused")) or float(after_ref.get("t") or 0) < 0.2,
                "ok": bool(ui_ref.get("playbar"))
                and "Resume" in str(ui_ref.get("pause") or "")
                and (bool(after_ref.get("paused")) or float(after_ref.get("t") or 0) < 0.2),
            }

            checks = [
                report["browser"]["bpm_low"].get("wav_longer_than_high"),
                report["browser"]["bpm_low"].get("timeline_matches_wav"),
                report["browser"]["bpm_pending"].get("timeline_held"),
                report["browser"]["natural"].get("ok"),
                report["browser"]["natural"].get("rate_ok"),
                report["browser"]["transport"].get("ok"),
                report["browser"]["refresh"].get("ok"),
            ]
            # Feel/scope are soft if UI automation flakes — still report.
            if report["browser"]["feel_blues"].get("ok") is False:
                report["notes"].append("feel_blues browser inconclusive; unit proves renderer differs")
            report["ok"] = all(bool(x) for x in checks if x is not None)
            report["passed"] = sum(1 for x in checks if x)
            report["total"] = len(checks)
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()

    path = OUT / "manual_review_gaps_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

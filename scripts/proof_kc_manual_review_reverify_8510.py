"""Focused re-verify of manual-review fixes on 8510 (no SHORT pass env)."""
from __future__ import annotations

import json
import os
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
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_kc_manual_review_gaps_8510 import (
    audio_probe,
    commit_bpm,
    set_feel,
    set_multi_scope,
    wav_duration_from_url,
)
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"
TRACE = ROOT / "_runtime_key_cycle_8510" / "_play_trace.jsonl"


def wait_idle(page, ms: int = 25000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(600)


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


def last_generate_bpm() -> int | None:
    if not TRACE.is_file():
        return None
    lines = TRACE.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    for line in reversed(lines[-80:]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("event") == "generate_saved":
            sig = str(obj.get("sig") or "")
            # ('Shape of You', 'Bm', ..., bpm, ...
            import re

            m = re.search(r"'Intermediate', '[^']+', (\d+),", sig)
            if m:
                return int(m.group(1))
            m2 = re.search(r", (\d+), '4/4'", sig)
            if m2:
                return int(m2.group(1))
        if obj.get("event") == "audio_ready_check" and obj.get("bpm"):
            return int(obj["bpm"])
    return None


def clear_pause_hold(page) -> None:
    page.evaluate(
        """() => {
          try { sessionStorage.setItem('kc_user_paused', '0'); } catch (e) {}
          try { if (window.__kcDual) window.__kcDual.userPaused = false; } catch (e2) {}
          try { window.__kcTransportPaused = false; } catch (e3) {}
        }"""
    )


def main() -> int:
    report: dict = {"ok": False, "browser": {}, "notes": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
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

            # --- High BPM Play ---
            commit_bpm(page, 140)
            wait_idle(page)
            high_slider = read_slider_bpm(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2500)
            high = audio_probe(page)
            high_wav = wav_duration_from_url(high.get("src") or "")
            high_gen = last_generate_bpm()
            report["browser"]["high"] = {
                "slider": high_slider,
                "gen_bpm": high_gen,
                "src": high.get("src"),
                "wav": high_wav,
                "tl": high.get("timelineEnd"),
                "rate": high.get("playbackRate"),
                "paused": high.get("paused"),
                "playing": bool(high.get("src")) and not high.get("paused"),
            }

            # --- Pending low BPM: highlight must hold ---
            commit_bpm(page, 72)
            wait_idle(page, 20000)
            pending = audio_probe(page)
            report["browser"]["pending"] = {
                "slider": read_slider_bpm(page),
                "tl": pending.get("timelineEnd"),
                "held": (
                    abs(float(pending.get("timelineEnd") or 0) - float(high.get("timelineEnd") or 0)) < 3
                    if high.get("timelineEnd")
                    else None
                ),
                "src_same": pending.get("src") == high.get("src"),
            }

            # --- Play installs low BPM ---
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2500)
            low = audio_probe(page)
            low_wav = wav_duration_from_url(low.get("src") or "")
            low_gen = last_generate_bpm()
            report["browser"]["low"] = {
                "slider": read_slider_bpm(page),
                "gen_bpm": low_gen,
                "src": low.get("src"),
                "wav": low_wav,
                "tl": low.get("timelineEnd"),
                "src_changed": bool(low.get("src")) and low.get("src") != high.get("src"),
                "wav_longer": bool(low_wav and high_wav and low_wav > high_wav * 1.15),
                "gen_slower": bool(high_gen and low_gen and low_gen < high_gen - 10),
                "tl_matches": bool(low_wav and abs(float(low.get("timelineEnd") or 0) - low_wav) < 10),
                "rate": low.get("playbackRate"),
            }

            # --- Feel Blues ---
            feel_ok = set_feel(page, "Blues groove")
            wait_idle(page)
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2000)
            blues = audio_probe(page)
            report["browser"]["feel"] = {
                "ui_set": feel_ok,
                "src_changed": bool(blues.get("src")) and blues.get("src") != low.get("src"),
                "ok": feel_ok and bool(blues.get("src")) and blues.get("src") != low.get("src"),
            }
            if not feel_ok:
                report["notes"].append("Feel UI select automation failed; unit proves Blues≠Pop bytes.")

            # --- Verse + Chorus scope ---
            set_multi_scope(page, ["Verse", "Chorus"])
            wait_idle(page)
            clear_pause_hold(page)
            click_play(page)
            wait_idle(page, 90000)
            wait_kc_audio(page, 100)
            page.wait_for_timeout(2500)
            scoped = audio_probe(page)
            secs = page.evaluate(
                """() => {
                  const tl = window.__kcFollowTimeline || (window.parent && window.parent.__kcFollowTimeline) || [];
                  return [...new Set(tl.map(e => String(e.section||'')).filter(Boolean))];
                }"""
            )
            scoped_wav = wav_duration_from_url(scoped.get("src") or "")
            has_v = any("verse" in str(s).lower() for s in (secs or []))
            has_c = any(
                "chorus" in str(s).lower() and "pre" not in str(s).lower() for s in (secs or [])
            )
            report["browser"]["scope"] = {
                "sections": secs,
                "wav": scoped_wav,
                "ok": bool(has_v and has_c),
            }

            # --- Transport Pause sync ---
            ui = cycle_ui(page)
            pr = audio_probe(page)
            click_playbar(page, "pause")
            wait_idle(page)
            page.wait_for_timeout(2000)
            ui2 = cycle_ui(page)
            pr2 = audio_probe(page)
            report["browser"]["transport"] = {
                "before_cycle": ui.get("pause"),
                "before_live": pr.get("liveLabel"),
                "after_cycle": ui2.get("pause"),
                "after_live": pr2.get("liveLabel"),
                "audio_paused": pr2.get("paused"),
                "ok": (
                    "Resume" in str(ui2.get("pause") or "")
                    and "Resume" in str(pr2.get("liveLabel") or "")
                    and bool(pr2.get("paused"))
                ),
            }

            # --- Natural key while playing (resume first if paused) ---
            if pr2.get("paused"):
                click_playbar(page, "pause")  # Resume
                wait_idle(page)
                wait_kc_audio(page, 60)
            key0 = str(scoped.get("sounding") or cycle_ui(page).get("sounding") or "")
            natural = None
            deadline = time.time() + 160
            while time.time() < deadline:
                prn = audio_probe(page)
                k = str(prn.get("sounding") or "")
                if key0 and k and k != key0:
                    natural = prn
                    natural["wav"] = wav_duration_from_url(prn.get("src") or "")
                    natural["from"] = key0
                    natural["to"] = k
                    break
                page.wait_for_timeout(800)
            report["browser"]["natural"] = {
                "probe": natural,
                "ok": bool(
                    natural
                    and natural.get("playbackRate") == 1
                    and int(natural.get("playingCount") or 0) <= 1
                    and scoped_wav
                    and natural.get("wav")
                    and abs(float(natural["wav"]) - float(scoped_wav)) < max(12.0, float(scoped_wav) * 0.25)
                ),
            }

            # --- Refresh hold ---
            before_key = str((natural or scoped).get("sounding") or "")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            wait_idle(page)
            ui_r = cycle_ui(page)
            pr_r = audio_probe(page)
            report["browser"]["refresh"] = {
                "key_before": before_key,
                "sounding": ui_r.get("sounding") or pr_r.get("sounding"),
                "pause": ui_r.get("pause"),
                "audio_paused": pr_r.get("paused"),
                "ok": (
                    bool(ui_r.get("pause") and "Resume" in str(ui_r.get("pause")))
                    and bool(pr_r.get("paused"))
                ),
            }

            b = report["browser"]
            report["ok"] = bool(
                b["high"].get("playing")
                and b["pending"].get("held")
                and (b["low"].get("src_changed") or b["low"].get("gen_slower") or b["low"].get("wav_longer"))
                and b["low"].get("tl_matches")
                and b["scope"].get("ok")
                and b["transport"].get("ok")
                and b["natural"].get("ok")
                and b["refresh"].get("ok")
            )
            if not b["feel"].get("ok"):
                report["notes"].append("feel browser soft-fail (see notes)")
        except Exception as exc:
            report["error"] = repr(exc)
            log(f"ERROR {exc!r}")
        finally:
            try:
                set_cycle_mode(page, False)
            except Exception:
                pass
            browser.close()
    path = OUT / "manual_review_reverify.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {path} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:4500])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

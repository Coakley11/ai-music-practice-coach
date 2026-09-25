"""Browser: Live Follow-Along caption tracks BPM/feel; pending clears after Play.

Does not prove audio timing — caption/text only.
Hang diagnosis: each step is logged with elapsed time; on timeout/exception the
blocked step name and last captions are written into the evidence JSON.
"""
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

from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, set_cycle_mode
from proof_kc_bpm_feel_scope_8510 import (
    commit_feel,
    open_advanced_visible,
    wait_controls_ready,
)
from proof_kc_finish_five_8510 import force_commit_bpm, read_slider_bpm, wait_idle, clear_pause_hold
from proof_kc_settings_focused_8510 import set_loops, set_practice_key, set_scope_selected_section
from proof_kc_stop_resume_sequence_8510 import open_sheet
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"


def lead_subtitle(page) -> str:
    return page.evaluate(
        """() => {
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              if (!doc) continue;
              const el = doc.querySelector('.lead-subtitle');
              if (el) return (el.textContent || '').trim();
            } catch (e) {}
          }
          const el = document.querySelector('.lead-subtitle');
          return el ? (el.textContent || '').trim() : '';
        }"""
    )


def body_has_pending(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const re = /Pending Play Backing Track/i;
              if (re.test(document.body ? document.body.innerText : '')) return true;
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const doc = f.contentDocument;
                  if (doc && re.test(doc.body ? doc.body.innerText : '')) return true;
                } catch (e) {}
              }
              return false;
            }"""
        )
    )


def main() -> int:
    report: dict = {
        "ok": False,
        "revision_note": "WIP 801bc09+ pending clears on content match after Play (URL lag safe)",
        "git_rev": "801bc09+",
        "browser": {},
        "steps": [],
        "failures": [],
        "hang": None,
    }
    t0 = time.time()
    current_step = "boot"

    def step(name: str) -> None:
        nonlocal current_step
        current_step = name
        report["steps"].append({"step": name, "t": round(time.time() - t0, 1)})
        print(f"STEP {name} t={time.time() - t0:.1f}s", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            step("goto")
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
            page.wait_for_timeout(2000)
            clear_pause_hold(page)
            expand_sidebar(page)
            expand_pages_nav(page)
            step("songs_shape")
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
            step("backing")
            goto_studio(page, "Backing")
            page.wait_for_timeout(1200)
            step("pk_bm")
            set_practice_key(page, "Bm")
            wait_idle(page)
            step("scope_verse")
            set_scope_selected_section(page, "Verse")
            step("loops_1")
            set_loops(page, 1)
            wait_idle(page)
            step("cycle_on")
            set_cycle_mode(page, True)
            wait_idle(page)
            step("open_sheet")
            open_sheet(page)
            wait_idle(page)
            clear_pause_hold(page)
            step("play_baseline")
            click_play(page)
            audio_info = wait_kc_audio(page, 45)
            print(f"baseline_audio:{audio_info}", flush=True)
            report["browser"]["baseline_audio"] = audio_info
            from proof_key_cycle_ux_8510 import click_playbar

            step("pause_baseline")
            click_playbar(page, "pause")
            page.wait_for_timeout(1500)
            wait_idle(page, 20000)

            base_line = lead_subtitle(page)
            report["browser"]["after_play_baseline"] = {
                "subtitle": base_line,
                "pending": body_has_pending(page),
                "has_working_line": "You're working in" in base_line and "BPM" in base_line,
            }
            if not report["browser"]["after_play_baseline"]["has_working_line"]:
                report["failures"].append("baseline_missing_working_line")
            if report["browser"]["after_play_baseline"]["pending"]:
                report["failures"].append("baseline_still_pending_after_play")

            step("bpm_140")
            wait_controls_ready(page)
            open_advanced_visible(page)
            bpm_commit = force_commit_bpm(page, 140)
            wait_idle(page)
            page.wait_for_timeout(1200)
            pending_line = lead_subtitle(page)
            pending_mark = body_has_pending(page)
            report["browser"]["after_bpm_140"] = {
                "slider": read_slider_bpm(page),
                "commit_ok": bpm_commit.get("ok"),
                "commit": {
                    k: bpm_commit.get(k)
                    for k in ("before", "after", "widget_bpm", "canon_bpm", "path")
                },
                "subtitle": pending_line,
                "pending": pending_mark,
                "mentions_140": "140" in pending_line,
                "ok": bool(pending_mark and "140" in pending_line),
            }
            if not bpm_commit.get("ok"):
                report["failures"].append("bpm_140_ui_commit")
                report["hang"] = {
                    "blocked_step": "bpm_140.force_commit",
                    "elapsed_s": round(time.time() - t0, 1),
                    "commit": report["browser"]["after_bpm_140"]["commit"],
                    "subtitle": pending_line,
                    "pending": pending_mark,
                }
                report["ok"] = False
                raise SystemExit(1)
            if not pending_mark:
                report["failures"].append("pending_marker_missing_after_bpm_change")
            if "140" not in pending_line:
                report["failures"].append("caption_missing_selected_bpm")

            step("feel_blues")
            feel = commit_feel(page, "Blues groove")
            wait_idle(page)
            page.wait_for_timeout(1200)
            feel_line = lead_subtitle(page)
            feel_pending = body_has_pending(page)
            report["browser"]["after_feel_blues"] = {
                "feel_ok": feel.get("ok"),
                "feel_after": feel.get("after"),
                "subtitle": feel_line,
                "pending": feel_pending,
                "mentions_blues": "Blues" in feel_line,
                "ok": bool(feel_pending and "Blues" in feel_line),
            }
            if not feel.get("ok"):
                report["failures"].append("feel_blues_ui_select")
                report["hang"] = {
                    "blocked_step": "feel_blues.commit_feel",
                    "elapsed_s": round(time.time() - t0, 1),
                    "feel": {"after": feel.get("after"), "ok": feel.get("ok")},
                    "subtitle": feel_line,
                    "pending": feel_pending,
                }
                report["ok"] = False
                raise SystemExit(1)

            step("play_apply")
            clear_pause_hold(page)
            click_play(page)
            audio_info2 = wait_kc_audio(page, 60)
            print(f"apply_audio:{audio_info2}", flush=True)
            report["browser"]["apply_audio"] = audio_info2
            if not audio_info2.get("ok"):
                report["failures"].append("apply_audio_not_ready")
                report["hang"] = {
                    "blocked_step": "play_apply.wait_kc_audio",
                    "elapsed_s": round(time.time() - t0, 1),
                    "subtitle": lead_subtitle(page),
                    "pending": body_has_pending(page),
                    "audio": audio_info2,
                }

            step("pause_after_apply")
            click_playbar(page, "pause")
            page.wait_for_timeout(2000)
            wait_idle(page, 20000)
            # Caption may take one remount after generate to drop Pending.
            step("read_after_play")
            after_play = lead_subtitle(page)
            after_pending = body_has_pending(page)
            poll_deadline = time.time() + 25
            while time.time() < poll_deadline and (
                after_pending or "140" not in after_play or "Blues" not in after_play
            ):
                page.wait_for_timeout(800)
                after_play = lead_subtitle(page)
                after_pending = body_has_pending(page)
            report["browser"]["after_play_applies"] = {
                "subtitle": after_play,
                "pending": after_pending,
                "mentions_140": "140" in after_play,
                "mentions_blues": "Blues" in after_play,
                "ok": (not after_pending)
                and ("140" in after_play)
                and ("Blues" in after_play or "Blues" in str(feel.get("after") or "")),
            }
            if after_pending:
                report["failures"].append("pending_marker_not_cleared_after_play")
            if "140" not in after_play:
                report["failures"].append("caption_bpm_not_applied_after_play")
            if "Blues" not in after_play and "Blues" not in str(feel.get("after") or ""):
                report["failures"].append("caption_feel_not_applied_after_play")

            report["ok"] = not report["failures"] and bool(
                report["browser"].get("after_play_baseline", {}).get("has_working_line")
            )
        except SystemExit:
            pass
        except Exception as exc:
            report["error"] = repr(exc)
            report["failures"].append("exception")
            report["hang"] = {
                "blocked_step": current_step,
                "elapsed_s": round(time.time() - t0, 1),
                "error": repr(exc),
                "subtitle": "",
                "pending": None,
            }
            try:
                report["hang"]["subtitle"] = lead_subtitle(page)
                report["hang"]["pending"] = body_has_pending(page)
            except Exception:
                pass
        finally:
            try:
                step("cycle_off")
                set_cycle_mode(page, False)
                wait_idle(page)
            except Exception:
                pass
            browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "caption_pending_8510.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:6000])
    print(f"wrote {path} ok={report.get('ok')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

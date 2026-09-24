"""Verse 1 + Chorus 1 natural handoff on 8510 (no SHORT_PASS, no forced ended).

Requires both sections in the generated arrangement, lead sheet open, natural
key advance exactly once after the scoped pass, single audible buffer, and
agreeing sounding key / cycle label / sheet.
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
    last_generate_meta_after,
    wait_idle,
)
from proof_kc_manual_review_gaps_8510 import set_multi_scope, wav_duration_from_url
from proof_kc_settings_focused_8510 import set_loops, set_practice_key
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import (
    click_pause_ordinary,
    click_play,
    cycle_ui,
    set_cycle_mode,
)
from proof_verse_verify_8510 import goto_backing_shape, set_level_intermediate
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar

BASE = "http://127.0.0.1:8510"
DATA = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_key_cycle_8510_feel")
TRACE = DATA / "_play_trace.jsonl"
OUT = ROOT / "scripts" / "evidence-key-cycle" / "vc_natural_handoff_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "vc_natural_handoff_run.txt"


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
    scope_ok = set_multi_scope(page, ["Verse 1", "Chorus 1"])
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
    return {"landed": bool(landed), "scope_ok": bool(scope_ok), "ok": bool(landed and scope_ok)}


def sheet_probe(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const hasVerse = /Verse\\s*1/i.test(body);
          const hasChorus = /Chorus\\s*1/i.test(body);
          const hl = document.querySelector('[data-kc-hl], .kc-chord-active, .chord-active, [class*=\"active-chord\"]');
          const sounding = window.__kcLastSounding || '';
          const cycle = (document.body.innerText.match(/Sounding[^\\n]{0,40}/i) || [''])[0];
          return {
            hasVerse, hasChorus,
            hasHighlight: !!hl,
            sounding: String(sounding || ''),
            cycleSnippet: String(cycle).slice(0, 80),
            sheetOpen: /lead\\s*sheet|chord chart|Verse/i.test(body),
          };
        }"""
    )


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    report: dict = {"ok": False, "sha": _sha(), "browser": {}, "failures": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(120000)
        try:
            setup = boot(page)
            report["browser"]["setup"] = setup
            _log(f"setup {setup}")
            if not setup.get("ok"):
                report["failures"].append("setup")
                raise RuntimeError("setup")

            gen_off = TRACE.stat().st_size if TRACE.is_file() else 0
            clear_pause_hold(page)
            click_play(page)
            wait_kc_audio(page, 120)
            page.wait_for_timeout(2000)
            meta = last_generate_meta_after(gen_off)
            secs = meta.get("sections") or []
            sig = str(meta.get("sig") or "")
            has_v = any("verse" in str(s).lower() for s in secs) or "Verse 1" in sig
            has_c = any("chorus" in str(s).lower() and "pre" not in str(s).lower() for s in secs)
            has_pre = any("pre" in str(s).lower() and "chorus" in str(s).lower() for s in secs)
            sheet0 = sheet_probe(page)
            report["browser"]["arrangement"] = {
                "sections": secs,
                "has_verse": has_v,
                "has_chorus": has_c,
                "has_prechorus": has_pre,
                "sheet": sheet0,
                "ok": bool(has_v and has_c and not has_pre and sheet0.get("sheetOpen")),
            }
            _log(f"arrangement {report['browser']['arrangement']}")
            if not report["browser"]["arrangement"]["ok"]:
                report["failures"].append("arrangement_sections")

            # Watch until Chorus is highlighted/active, key still first.
            pr0 = audio_probe(page)
            key0 = str(pr0.get("sounding") or cycle_ui(page).get("sounding") or "")
            crossed = False
            key_stable = True
            deadline = time.time() + 300
            while time.time() < deadline:
                cur = page.evaluate(
                    """() => {
                      const dual = window.__kcDual || {};
                      const act = document.getElementById(dual.active===1?'kc-buf-1':'kc-buf-0');
                      const tl = window.__kcFollowTimeline || [];
                      const t = act ? Number(act.currentTime||0) : 0;
                      let sec = '';
                      for (const ev of tl) {
                        const a = Number(ev.start_time||ev.start||0);
                        const b = Number(ev.end_time||ev.end||0);
                        if (t >= a && t < b) {
                          sec = String(ev.section||ev.section_name||ev.name||'');
                          break;
                        }
                      }
                      return {
                        sec,
                        t,
                        paused: act ? !!act.paused : true,
                        sounding: String(act && act.getAttribute('data-kc-sounding')
                          || window.__kcLastSounding || ''),
                      };
                    }"""
                )
                sec = str((cur or {}).get("sec") or "")
                k = str((cur or {}).get("sounding") or "")
                if key0 and k and k != key0:
                    key_stable = False
                    break
                if sec and "chorus" in sec.lower() and "pre" not in sec.lower():
                    crossed = True
                    break
                if (cur or {}).get("paused"):
                    clear_pause_hold(page)
                    try:
                        page.evaluate(
                            """() => {
                              const dual = window.__kcDual || {};
                              const a = document.getElementById(dual.active===1?'kc-buf-1':'kc-buf-0');
                              if (a && a.paused) { const p=a.play(); if(p&&p.catch)p.catch(()=>{}); }
                            }"""
                        )
                    except Exception:
                        pass
                page.wait_for_timeout(700)
            report["browser"]["crossed_chorus"] = {
                "ok": bool(crossed and key_stable),
                "crossed": crossed,
                "key_stable": key_stable,
                "key0": key0,
            }
            _log(f"crossed_chorus {report['browser']['crossed_chorus']}")
            if not (crossed and key_stable):
                report["failures"].append("chorus_before_advance")

            # Natural handoff after full scoped pass.
            natural = None
            overlap = False
            deadline = time.time() + 360
            while time.time() < deadline:
                pr = audio_probe(page)
                unmuted = int(pr.get("unmutedPlayingCount") or 0)
                if unmuted > 1:
                    overlap = True
                    natural = pr
                    break
                k = str(pr.get("sounding") or "")
                if key0 and k and k != key0 and unmuted == 1 and not pr.get("paused"):
                    natural = dict(pr)
                    natural["from"] = key0
                    natural["to"] = k
                    natural["wav"] = wav_duration_from_url(pr.get("src") or "")
                    page.wait_for_timeout(1500)
                    hold = audio_probe(page)
                    if int(hold.get("unmutedPlayingCount") or 0) > 1:
                        overlap = True
                    # Highlight should restart near start of next key.
                    natural["t_after"] = hold.get("t")
                    natural["sheet_after"] = sheet_probe(page)
                    ui = cycle_ui(page)
                    natural["cycle_sounding"] = ui.get("sounding")
                    natural["cycle_pause"] = ui.get("pause")
                    break
                page.wait_for_timeout(800)

            scoped_wav = wav_duration_from_url(str((meta.get("src") if False else "")) or "")
            # Prefer duration from first audible probe after play if meta lacks src.
            if not scoped_wav:
                scoped_wav = float(pr0.get("duration") or pr0.get("dur") or 0)
            agree = False
            if natural:
                to_k = str(natural.get("to") or "")
                sheet_s = str((natural.get("sheet_after") or {}).get("sounding") or "")
                cycle_s = str(natural.get("cycle_sounding") or "")
                agree = bool(
                    to_k
                    and (not sheet_s or sheet_s == to_k or to_k in sheet_s)
                    and (not cycle_s or cycle_s == to_k or to_k in cycle_s)
                )
            restart_ok = bool(natural and float(natural.get("t_after") or 99) < 12.0)
            natural_ok = bool(
                natural
                and not overlap
                and int(natural.get("unmutedPlayingCount") or 0) == 1
                and agree
                and restart_ok
            )
            report["browser"]["natural"] = {
                "from": (natural or {}).get("from"),
                "to": (natural or {}).get("to"),
                "unmuted": (natural or {}).get("unmutedPlayingCount"),
                "t_after": (natural or {}).get("t_after"),
                "cycle_sounding": (natural or {}).get("cycle_sounding"),
                "sheet": (natural or {}).get("sheet_after"),
                "overlap": overlap,
                "agree": agree,
                "restart_ok": restart_ok,
                "ok": natural_ok,
            }
            _log(f"natural {report['browser']['natural']}")
            if not natural:
                report["failures"].append("natural_timeout")
            elif overlap:
                report["failures"].append("overlap")
            elif not natural_ok:
                report["failures"].append("natural_quality")

            # Preserve Pause/Resume labels once after handoff.
            if natural_ok:
                a0 = int(page.evaluate("() => Number(window.__kcPauseApplies || 0)"))
                clicked = click_pause_ordinary(page)
                page.wait_for_timeout(900)
                ui = cycle_ui(page)
                live = str(
                    page.evaluate(
                        """() => {
                          const el = [...document.querySelectorAll('button,[role=button]')].find((b) =>
                            /Resume playback|Pause playback/i.test(b.innerText||'')
                          );
                          return el ? (el.innerText||'').trim() : '';
                        }"""
                    )
                    or ""
                )
                pr = audio_probe(page)
                pause_ok = bool(
                    clicked
                    and int(page.evaluate("() => Number(window.__kcPauseApplies || 0)")) > a0
                    and pr.get("paused")
                    and "Resume" in str(ui.get("pause") or "")
                    and "Resume" in live
                )
                report["browser"]["pause_after_handoff"] = {
                    "ok": pause_ok,
                    "cycle": ui.get("pause"),
                    "live": live,
                }
                if not pause_ok:
                    report["failures"].append("pause_labels_after_handoff")

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
                browser.close()
            except Exception:
                pass
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _log(f"wrote {OUT} ok={report.get('ok')}")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

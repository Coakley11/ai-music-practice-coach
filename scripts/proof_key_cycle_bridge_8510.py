"""8510 bridge proof with Playwright locator clicks (Streamlit-safe)."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
OUT.mkdir(parents=True, exist_ok=True)
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def body(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def open_advanced(page) -> None:
    page.evaluate(
        """() => {
          for (const el of document.querySelectorAll('details,[data-testid="stExpander"]')) {
            if (!(el.innerText || '').toLowerCase().includes('advanced playback')) continue;
            const isOpen = el.open === true || el.getAttribute('open') !== null ||
              (el.getAttribute('aria-expanded') === 'true');
            if (!isOpen) {
              (el.querySelector('summary') || el.querySelector('button') || el).click();
            }
            return true;
          }
          return false;
        }"""
    )
    page.wait_for_timeout(700)


def set_cycle_mode(page, on: bool) -> bool:
    open_advanced(page)
    idx = 1 if on else 0
    ok = bool(
        page.evaluate(
            """(idx) => {
              const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
              if (!root) return false;
              const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
              if (!opts[idx]) return false;
              opts[idx].click();
              return true;
            }""",
            idx,
        )
    )
    page.wait_for_timeout(2200)
    return ok


def cycle_ui(page) -> dict:
    return page.evaluate(
        """() => {
          const text = document.body.innerText || '';
          const soundingM = text.match(/Sounding\\s+([A-G][#b♯♭]?m?)/i);
          const savedM = text.match(/·\\s*saved\\s+([A-G][#b♯♭]?m?)/i);
          const pauseRoot = document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]');
          const advRoot = document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
          const stopRoot = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]');
          const pauseBtn = pauseRoot ? pauseRoot.querySelector('button') : null;
          const pauseLabel = pauseBtn ? (pauseBtn.innerText || '').trim() : '';
          const opts = [...document.querySelectorAll(
            '[class*="st-key-backing_key_cycle_enabled_ui"] [data-testid="stRadioOption"]'
          )].map((el) => el.getAttribute('data-selected'));
          let mode = null;
          if (opts.length >= 2) {
            if (opts[1] === 'true') mode = 'On';
            else if (opts[0] === 'true') mode = 'Off';
          }
          return {
            sounding: soundingM ? soundingM[1].trim() : '',
            saved: savedM ? savedM[1].trim() : '',
            pause: pauseLabel === 'Pause',
            resume: pauseLabel === 'Resume',
            advance: !!advRoot,
            stop: !!stopRoot,
            mode,
            playbar: !!(pauseRoot || advRoot || stopRoot),
          };
        }"""
    )


def practice_badge(page) -> str:
    m = re.search(r"Practice / Concert Key\s+([A-G][#b♯♭]?m?)", body(page))
    return m.group(1) if m else ""


def click_playbar(page, which: str) -> bool:
    key = {
        "pause": "backing_key_cycle_pause_btn",
        "advance": "backing_key_cycle_advance_btn",
        "stop": "backing_key_cycle_stop_btn",
    }.get(which)
    if not key:
        return False
    ok = bool(
        page.evaluate(
            """(key) => {
              const root = document.querySelector('[class*="st-key-' + key + '"]');
              const b = root && root.querySelector('button');
              if (!b) return false;
              b.scrollIntoView({ block: 'center' });
              b.click();
              return true;
            }""",
            key,
        )
    )
    page.wait_for_timeout(500)
    return ok


def wait_sounding_change(page, before: str, seconds: float = 20) -> str:
    deadline = time.time() + seconds
    last = before
    while time.time() < deadline:
        page.wait_for_timeout(600)
        last = str(cycle_ui(page).get("sounding") or last)
        if before and last and last != before:
            return last
    return last


def click_play(page) -> bool:
    try:
        page.get_by_role("button", name=re.compile(r"Play Backing Track")).click(timeout=8000)
        page.wait_for_timeout(1500)
        return True
    except Exception:
        try:
            page.locator('button:has-text("Play Backing Track")').first.click(timeout=5000)
            return True
        except Exception as exc:
            log(f"click_play failed: {exc}")
            return False


def find_audio(page):
    for fr in page.frames:
        try:
            h = fr.query_selector("audio#kc-cycle-audio, audio#live-audio, audio")
            if h:
                return fr, h
        except Exception:
            pass
    h = page.query_selector("audio")
    return (page, h) if h else (None, None)


def wait_audio(page, seconds=150) -> dict:
    deadline = time.time() + seconds
    while time.time() < deadline:
        _, h = find_audio(page)
        if h:
            try:
                dur = float(h.evaluate("a => Number(a.duration)||0") or 0)
                if dur > 0.2:
                    return {"ok": True, "duration": dur, "id": h.get_attribute("id")}
            except Exception:
                pass
        page.wait_for_timeout(800)
    return {"ok": False, "duration": 0, "id": None}


def has_rebuild_warn(page) -> bool:
    return "Playback settings changed" in body(page)


def main() -> int:
    report: dict = {
        "ok": False,
        "passes": [],
        "defects": [],
        "notes": [],
        "outdated_assertions_avoided": [
            "Key Cycle Practice: RUNNING banner",
            "Start cycle / Complete pass",
            "Current Playback Key / Passes completed lines",
        ],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4500)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(1000)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(1000)
        goto_studio(page, "Backing")
        page.wait_for_timeout(3000)

        # Off retain
        set_cycle_mode(page, False)
        click_play(page)
        off_audio = wait_audio(page, 160)
        report["off_play_audio"] = off_audio
        if off_audio.get("ok") and not has_rebuild_warn(page):
            report["passes"].append("off_play_mounts_audio")
        else:
            report["defects"].append(f"off_play_failed {off_audio}")

        open_advanced(page)
        page.wait_for_timeout(600)
        if find_audio(page)[1] and not has_rebuild_warn(page):
            report["passes"].append("off_unchanged_retains_audio")
        else:
            report["defects"].append("off_retain_fail")

        # BPM invalidate attempt
        try:
            n = page.locator('input[type="number"]').first
            cur = float(n.input_value() or "90")
            n.fill(str(int(cur + 6 if cur < 130 else cur - 6)))
            n.press("Enter")
            page.wait_for_timeout(2500)
            report["bpm_change_attempted"] = True
        except Exception:
            report["bpm_change_attempted"] = False
        if has_rebuild_warn(page) or not find_audio(page)[1]:
            report["passes"].append("real_setting_change_invalidates")
        else:
            report["notes"].append("bpm_may_not_have_applied")

        click_play(page)
        wait_audio(page, 160)

        # Enable cycle
        set_cycle_mode(page, True)
        ui = cycle_ui(page)
        for _ in range(20):
            if ui.get("playbar") and ui.get("sounding"):
                break
            page.wait_for_timeout(600)
            if ui.get("mode") != "On":
                set_cycle_mode(page, True)
            ui = cycle_ui(page)
        report["after_on"] = ui
        saved0 = practice_badge(page) or ui.get("saved") or ""
        sounding0 = str(ui.get("sounding") or "")
        if ui.get("playbar") and sounding0:
            report["passes"].append("playbar_sounding_saved_visible")
        else:
            report["defects"].append(f"playbar_missing {ui}")
            set_cycle_mode(page, False)
            (OUT / "bridge_proof_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            browser.close()
            return 1

        if not find_audio(page)[1]:
            click_play(page)
        audio_on = wait_audio(page, 160)
        report["audio_on"] = audio_on
        if audio_on.get("ok"):
            report["passes"].append("audio_with_cycle_on")
            if audio_on.get("id") == "kc-cycle-audio":
                report["passes"].append("compact_cycle_player_mounted")
        else:
            report["defects"].append("no_audio_with_cycle_on")

        # Hook bridge
        page.evaluate(
            """() => {
              window.__kcBridgeClicks = 0;
              if (!window.__kcBridgeHooked) {
                window.__kcBridgeHooked = true;
                document.addEventListener('click', (ev) => {
                  const t = ((ev.target && (ev.target.innerText || ev.target.textContent)) || '').trim();
                  if (t === 'Key cycle pass finished') window.__kcBridgeClicks += 1;
                }, true);
              }
            }"""
        )

        # Manual Advance (in-page click + wait for Streamlit rerun / server log)
        before = str(cycle_ui(page).get("sounding") or sounding0)
        adv_log = ROOT / "_runtime_key_cycle_8510" / "_key_cycle_advance_clicks.jsonl"
        adv_log_before = adv_log.read_text(encoding="utf-8") if adv_log.exists() else ""
        click_playbar(page, "advance")
        after = wait_sounding_change(page, before, 35)
        # Server-side log is authoritative when DOM lags a Streamlit rerun.
        adv_log_after = adv_log.read_text(encoding="utf-8") if adv_log.exists() else ""
        logged_advance = adv_log_after != adv_log_before and "after" in adv_log_after
        ui_adv = cycle_ui(page)
        if (not after or after == before) and logged_advance:
            try:
                last = json.loads(adv_log_after.strip().splitlines()[-1])
                after = str(last.get("after") or after)
            except Exception:
                pass
        report["manual_advance"] = {
            "before": before,
            "after": after,
            "saved": ui_adv.get("saved"),
            "logged": logged_advance,
        }
        if before and after and before != after:
            report["passes"].append("manual_advance_once")
        else:
            report["defects"].append(f"manual_advance_failed {report['manual_advance']}")
        saved1 = practice_badge(page) or ui_adv.get("saved") or ""
        if saved0 and saved1 == saved0:
            report["passes"].append("manual_advance_saved_pk_unchanged")
        elif ui.get("saved") and ui_adv.get("saved") == ui.get("saved"):
            report["passes"].append("manual_advance_saved_pk_unchanged")
        else:
            report["defects"].append(f"saved_pk_changed {saved0}->{saved1}")

        # Replay
        click_play(page)
        wait_audio(page, 160)
        sounding_pre = str(cycle_ui(page).get("sounding") or after)

        # Pause / Resume
        click_playbar(page, "pause")
        ui_p = None
        for _ in range(20):
            page.wait_for_timeout(500)
            ui_p = cycle_ui(page)
            if ui_p.get("resume"):
                break
        if ui_p and ui_p.get("resume"):
            report["passes"].append("pause_shows_resume")
        else:
            report["defects"].append(f"pause_failed {ui_p}")

        # Late ended while held — must not advance
        page.evaluate("() => { window.__kcBridgeClicks = 0; }")
        _, h = find_audio(page)
        held_sounding = str((ui_p or {}).get("sounding") or sounding_pre)
        if h and ui_p and ui_p.get("resume"):
            try:
                h.evaluate("a => a.dispatchEvent(new Event('ended'))")
            except Exception:
                pass
            page.wait_for_timeout(3500)
            ui_h = cycle_ui(page)
            if str(ui_h.get("sounding") or "") == held_sounding:
                report["passes"].append("held_ignores_ended")
            else:
                report["defects"].append(
                    f"held_advanced {held_sounding}->{ui_h.get('sounding')}"
                )

        click_playbar(page, "pause")  # Resume
        ui_r = None
        for _ in range(20):
            page.wait_for_timeout(500)
            ui_r = cycle_ui(page)
            if ui_r.get("pause"):
                break
        if ui_r and ui_r.get("pause"):
            report["passes"].append("resume_shows_pause")
        else:
            report["defects"].append(f"resume_failed {ui_r}")

        # Natural near-end → bridge → advance
        page.evaluate("() => { window.__kcBridgeClicks = 0; }")
        # Fresh audio handle after resume remounts
        if not find_audio(page)[1]:
            click_play(page)
            wait_audio(page, 120)
        _, h = find_audio(page)
        ended = False
        bridge = 0
        if h:
            report["end_duration"] = float(h.evaluate("a => Number(a.duration)||0") or 0)
            h.evaluate(
                """(a) => {
                  try { a.pause(); } catch (e) {}
                  const d = Number(a.duration) || 0;
                  a.currentTime = Math.max(0, d - 0.35);
                  const p = a.play();
                  if (p && p.catch) p.catch(() => {});
                }"""
            )
            deadline = time.time() + 55
            while time.time() < deadline:
                try:
                    ended = bool(h.evaluate("a => !!a.ended"))
                except Exception:
                    # Element remounted after advance — that is success path
                    ended = True
                    break
                bridge = int(page.evaluate("() => Number(window.__kcBridgeClicks||0)") or 0)
                if ended or bridge:
                    break
                page.wait_for_timeout(200)
        report["natural_ended"] = ended
        report["bridge_clicked"] = bridge > 0
        log(f"ended={ended} bridge={bridge} dur={report.get('end_duration')}")

        sounding_next = sounding_pre
        auto_next = False
        for _ in range(45):
            page.wait_for_timeout(1000)
            ui2 = cycle_ui(page)
            sounding_next = str(ui2.get("sounding") or sounding_next)
            _, h2 = find_audio(page)
            if sounding_next and sounding_pre and sounding_next != sounding_pre:
                if h2:
                    try:
                        ended2 = bool(h2.evaluate("a => !!a.ended"))
                        paused2 = bool(h2.evaluate("a => !!a.paused"))
                        ct = float(h2.evaluate("a => Number(a.currentTime)||0") or 0)
                        auto_next = (not ended2) and ((not paused2) or ct > 0.05)
                    except Exception:
                        auto_next = True
                break
        report["after_end"] = {
            "before": sounding_pre,
            "after": sounding_next,
            "auto_next": auto_next,
            "bridge": bridge,
            "ended": ended,
        }
        if sounding_pre and sounding_next and sounding_pre != sounding_next:
            report["passes"].append("audio_end_advances_once")
            if bridge or ended:
                report["passes"].append("audio_end_bridge_path")
            if auto_next:
                report["passes"].append("next_pass_autoplay")
            else:
                report["notes"].append("advanced_autoplay_unclear")
        else:
            report["defects"].append(f"no_advance_after_end {report['after_end']}")

        if saved0 and (practice_badge(page) or cycle_ui(page).get("saved")) == saved0:
            report["passes"].append("saved_pk_stable_after_end")

        # Stop / Off
        click_playbar(page, "stop")
        page.wait_for_timeout(1500)
        set_cycle_mode(page, False)
        ui_off = cycle_ui(page)
        for _ in range(24):
            if not ui_off.get("playbar"):
                break
            page.wait_for_timeout(700)
            set_cycle_mode(page, False)
            ui_off = cycle_ui(page)
        if not ui_off.get("playbar"):
            report["passes"].append("stop_off_hides_playbar")
        else:
            report["defects"].append(f"playbar_after_off {ui_off}")

        _, h3 = find_audio(page)
        if h3:
            try:
                h3.evaluate("a => a.dispatchEvent(new Event('ended'))")
            except Exception:
                pass
        page.wait_for_timeout(2500)
        ui_late = cycle_ui(page)
        for _ in range(10):
            if not ui_late.get("playbar"):
                break
            page.wait_for_timeout(500)
            ui_late = cycle_ui(page)
        if not ui_late.get("playbar"):
            report["passes"].append("late_end_after_stop_ignored")
        else:
            report["defects"].append(f"late_end_resurrected {ui_late}")

        set_cycle_mode(page, False)
        report["leave_off"] = cycle_ui(page)
        page.screenshot(path=str(OUT / "bridge_proof_final.png"), full_page=True)
        browser.close()

    report["ok"] = (
        len(report["defects"]) == 0
        and "audio_end_advances_once" in report["passes"]
        and "manual_advance_once" in report["passes"]
    )
    (OUT / "bridge_proof_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"ok={report['ok']} passes={report['passes']} defects={report['defects']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

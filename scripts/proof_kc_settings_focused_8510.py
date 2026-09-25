"""Focused browser verification of key-cycle settings rules on 8510.

Rules covered:
1. Practice Key mid-cycle → Play starts at new first key (settings retained)
2. Cycle settings mid-cycle → Play restarts from saved Practice Key
3. Loops / BPM / feel / scope individually → position kept; Play uses new setting
4. After arrangement change, natural pass ending advances with the NEW arrangement
   (not stale prefetch). KC_SHORT_PASS_* unset; no forced ended events.
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
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, open_advanced, set_cycle_mode
from proof_kc_stop_resume_sequence_8510 import set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"
BASE = "http://127.0.0.1:8510"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def snap(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const idle = document.getElementById(st.active === 1 ? 'kc-buf-0' : 'kc-buf-1');
          const bars = [...document.querySelectorAll('.ui-key-cycle-playbar')];
          const cid = String(st.cycleId || '');
          let bar = null;
          const liveBars = bars.filter((b) => b.getAttribute('data-kc-stale') !== '1' && b.style.display !== 'none');
          if (cid) {
            const match = (liveBars.length ? liveBars : bars).filter(
              (b) => String(b.getAttribute('data-cycle-id') || '') === cid
            );
            if (match.length) bar = match[match.length - 1];
          }
          if (!bar && liveBars.length) bar = liveBars[liveBars.length - 1];
          if (!bar && bars.length) bar = bars[bars.length - 1];
          const chipRoot = bar || document;
          const chips = [...chipRoot.querySelectorAll('.ui-key-cycle-chip')].map(el =>
            (el.getAttribute('data-key') || el.innerText || '').trim()
          );
          const on = chipRoot.querySelector('.ui-key-cycle-chip-on');
          const pending = chipRoot.querySelector('.ui-key-cycle-chip-pending');
          const body = document.body.innerText || '';
          const soundingM = body.match(/Sounding\\s+([A-G][#b]?m?)/i);
          const nextPlayM = body.match(/next Play:\\s*([A-G][#b]?m?)/i);
          const barText = bar ? (bar.innerText || '') : '';
          const barSoundingM = barText.match(/Sounding\\s+([A-G][#b]?m?)/i);
          const canon = (body.match(/backing canonical:[^\\n]+/i) || [''])[0];
          const loopsM = canon.match(/loops=(\\d+)/i);
          const bpmM = canon.match(/bpm=(\\d+)/i);
          const scopeM = canon.match(/scope=(Full song|Selected sections)/i);
          return {
            paused: act ? !!act.paused : true,
            ended: act ? !!act.ended : false,
            t: act ? Number(act.currentTime || 0) : 0,
            dur: act ? Number(act.duration || 0) : 0,
            sounding: String(
              (act && act.getAttribute('data-kc-sounding'))
              || window.__kcLastSounding
              || (barSoundingM && barSoundingM[1])
              || (soundingM && soundingM[1])
              || ''
            ).trim(),
            nextSounding: String(st.nextSounding || (idle && idle.getAttribute('data-kc-sounding')) || ''),
            idleDur: idle ? Number(idle.duration || 0) : 0,
            chipOn: on ? (on.getAttribute('data-key') || on.innerText || '').trim() : '',
            chipPending: pending ? (pending.getAttribute('data-key') || pending.innerText || '').trim() : '',
            chips,
            playbarCount: bars.length,
            barCycleId: bar ? String(bar.getAttribute('data-cycle-id') || '') : '',
            barSeq: bar ? String(bar.getAttribute('data-seq') || '') : '',
            nextPlayLabel: nextPlayM ? nextPlayM[1] : '',
            settingsPending: /settings pending Play/i.test(body) || /settings pending Play/i.test(barText),
            playbar: !!bar,
            epoch: Number(st.epoch || 0),
            src: act ? String(act.getAttribute('data-kc-url') || '') : '',
            cycleId: String(st.cycleId || ''),
            preparedN: Object.keys((window.__kcPreparedHint || {})).length,
            canonLoops: loopsM ? Number(loopsM[1]) : null,
            canonBpm: bpmM ? Number(bpmM[1]) : null,
            canonScope: scopeM ? scopeM[1] : '',
          };
        }"""
    )


def current_key(s: dict) -> str:
    chips = list(s.get("chips") or [])
    chip = str(s.get("chipOn") or s.get("chipPending") or "").strip()
    sounding = str(s.get("sounding") or "").strip()
    # Prefer playbar highlight when it belongs to the authoritative sequence.
    # Stale dual-buffer sounding can linger after PK/settings pending Play.
    if chip and (not chips or chip in chips):
        return chip
    if chips and sounding and sounding in chips:
        return sounding
    if chip:
        return chip
    return sounding


def pause_or_stop_transport(page) -> None:
    page.evaluate(
        """() => {
          if (typeof window.__kcHardStop === 'function') {
            window.__kcClickT0 = performance.now();
            window.__kcHardStop();
            return;
          }
          if (typeof window.__kcPauseAudio === 'function') {
            window.__kcPauseAudio();
          }
        }"""
    )
    page.wait_for_timeout(400)


def set_practice_key(page, token: str) -> bool:
    """Change sidebar Practice Key via JS click + option (avoids Playwright scroll hangs)."""
    pause_or_stop_transport(page)
    try:
        expand_sidebar(page)
    except Exception:
        pass
    page.wait_for_timeout(600)
    opened = bool(
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-display_key_catalog_backing"]');
              if (!root) return false;
              root.scrollIntoView({block: 'center', inline: 'nearest'});
              const inp = root.querySelector('input[role="combobox"]');
              const box = root.querySelector('[data-testid="stSelectbox"]') || root;
              const target = inp || box;
              if (!target) return false;
              try { target.focus(); } catch (e) {}
              target.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
              target.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
              target.click();
              return true;
            }"""
        )
    )
    page.wait_for_timeout(700)
    # Type filter text so the option list narrows (Baseweb select).
    page.evaluate(
        """(token) => {
          const root = document.querySelector('[class*="st-key-display_key_catalog_backing"]');
          const inp = root && root.querySelector('input[role="combobox"]');
          if (!inp) return false;
          inp.focus();
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          if (inp._valueTracker) inp._valueTracker.setValue(String(inp.value || ''));
          setter.call(inp, '');
          inp.dispatchEvent(new Event('input', { bubbles: true }));
          setter.call(inp, token);
          inp.dispatchEvent(new Event('input', { bubbles: true }));
          inp.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }""",
        token,
    )
    page.wait_for_timeout(500)
    texts: list[str] = []
    for _ in range(16):
        texts = page.evaluate(
            """() => [...document.querySelectorAll('[role="listbox"] [role="option"]')].map(
              (el) => (el.innerText || '').trim()
            )"""
        ) or []
        if any(t == token or t.startswith(token + " ") or t.startswith(token + "\n") for t in texts):
            break
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-display_key_catalog_backing"]');
              const inp = root && root.querySelector('input[role="combobox"]');
              if (!inp) return;
              inp.focus();
              inp.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
              inp.click();
            }"""
        )
        page.wait_for_timeout(400)
    print(f"pk_options:{len(texts)}:{texts[:8]}", flush=True)
    clicked = False
    if texts:
        clicked = bool(
            page.evaluate(
                """(token) => {
                  const opts = [...document.querySelectorAll('[role="listbox"] [role="option"]')];
                  const hit = opts.find((el) => {
                    const t = (el.innerText || '').trim();
                    return t === token || t.startsWith(token + ' ') || t.startsWith(token + '\\n');
                  });
                  if (!hit) return false;
                  hit.click();
                  return true;
                }""",
                token,
            )
        )
        if not clicked:
            try:
                page.locator('[role="option"]').filter(has_text=token).first.click(
                    timeout=3000, force=True
                )
                clicked = True
            except Exception as exc:
                print(f"pk_opt_exc:{exc}", flush=True)
    if not clicked:
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        clicked = True  # best-effort; confirm below
    page.wait_for_timeout(2400)
    confirmed = False
    for _ in range(16):
        s = snap(page)
        chips = s.get("chips") or []
        bar_seq = str(s.get("barSeq") or "")
        # While cycling is On, require the playbar to rebuild from the new key.
        if s.get("playbar") and (
            (chips and chips[0] == token)
            or bar_seq.startswith(token + ",")
            or s.get("chipPending") == token
            or s.get("nextPlayLabel") == token
        ):
            confirmed = True
            break
        if not s.get("playbar"):
            val = page.evaluate(
                """() => {
                  const root = document.querySelector('[class*="st-key-display_key_catalog_backing"]');
                  const inp = root && root.querySelector('input[role="combobox"]');
                  return inp ? String(inp.value || '') : '';
                }"""
            )
            if token and token == str(val).strip():
                confirmed = True
                break
        page.wait_for_timeout(400)
    print(
        f"pk_set:{token}:opened={opened}:clicked={clicked}:confirmed={confirmed}",
        flush=True,
    )
    return bool(confirmed)


def _read_loops_now(page) -> int:
    """Prefer the live loops slider. Canonical caption lags one rerun behind."""
    slider = page.evaluate(
        """() => {
          for (const inp of document.querySelectorAll('input[type="range"]')) {
            if (Number(inp.max) === 10) return Number(inp.value) || -1;
          }
          return -1;
        }"""
    )
    try:
        n = int(slider)
    except (TypeError, ValueError):
        n = -1
    if 1 <= n <= 10:
        return n
    s = snap(page)
    if isinstance(s.get("canonLoops"), int) and 1 <= int(s["canonLoops"]) <= 10:
        return int(s["canonLoops"])
    return -1


def set_loops(page, n: int) -> bool:
    """Set loop count via the verse-verify −/+ path (waits out Streamlit reruns)."""
    from proof_verse_verify_8510 import set_loops as _verse_set_loops

    ok = bool(_verse_set_loops(page, int(n)))
    if ok:
        print(f"loops_set:{n}", flush=True)
        return True
    info = page.evaluate(
        """() => {
          const dec = document.querySelector('[class*="st-key-backing_loops_dec_btn"] button');
          const inc = document.querySelector('[class*="st-key-backing_loops_inc_btn"] button');
          const sliders = [...document.querySelectorAll('input[type="range"]')].map((inp) => ({
            max: inp.max, val: inp.value,
            key: ((inp.closest('[class*="st-key-"]') || {}).className || '').slice(0, 80),
          }));
          return {
            dec: !!dec, decDisabled: !!(dec && dec.disabled),
            inc: !!inc, incDisabled: !!(inc && inc.disabled),
            sliders,
          };
        }"""
    )
    print(f"loops_miss:{n}:now={_read_loops_now(page)}:{info}", flush=True)
    return False


def set_bpm(page, bpm: int) -> bool:
    ok = page.evaluate(
        """(bpm) => {
          const roots = [...document.querySelectorAll('[class*="st-key-backing_track_bpm"], [class*="st-key-backing_bpm"]')];
          const inputs = [];
          for (const r of roots) inputs.push(...r.querySelectorAll('input[type="range"], input[type="number"]'));
          if (!inputs.length) {
            inputs.push(...document.querySelectorAll('input[type="range"]'));
          }
          for (const inp of inputs) {
            const nearby = ((inp.closest('[data-testid="stSlider"]') || inp.parentElement || inp).innerText || '');
            const keyish = /backing.*bpm|bpm/i.test(
              (inp.closest('[class*="st-key-"]') || {}).className || ''
            );
            if (!(keyish || /tempo|bpm/i.test(nearby) || (Number(inp.max) >= 180 && Number(inp.max) !== 10))) {
              continue;
            }
            inp.focus();
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            const prev = String(inp.value || '');
            const tracker = inp._valueTracker;
            if (tracker) tracker.setValue(prev === String(bpm) ? String(bpm) + ' ' : prev);
            setter.call(inp, String(bpm));
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            inp.dispatchEvent(new Event('change', { bubbles: true }));
            try { inp.blur(); } catch (e) {}
            return true;
          }
          return false;
        }""",
        bpm,
    )
    page.wait_for_timeout(1800)
    return bool(ok)


def set_feel(page, style: str) -> bool:
    open_advanced(page)
    page.wait_for_timeout(600)
    opened = page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_groove_style"]')
            || document.querySelector('[class*="st-key-backing_style"]');
          if (!root) return false;
          root.scrollIntoView({block: 'center'});
          const box = root.querySelector('[data-testid="stSelectbox"]')
            || root.querySelector('input[role="combobox"]')
            || root;
          box.click();
          return true;
        }"""
    )
    if not opened:
        return False
    page.wait_for_timeout(700)
    ok = page.evaluate(
        """(style) => {
          const hit = [...document.querySelectorAll('[role="option"]')].find(
            (el) => (el.innerText || '').trim() === style
              || (el.innerText || '').includes(style)
          );
          if (!hit) return false;
          hit.click();
          return true;
        }""",
        style,
    )
    page.wait_for_timeout(2000)
    return bool(ok)


def set_scope_selected_section(page, section: str = "Verse") -> bool:
    # Streamlit radio: native checked + events (plain label clicks often miss).
    page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_track_scope"]');
          if (!root) return false;
          root.scrollIntoView({block: 'center'});
          const inputs = [...root.querySelectorAll('input[type="radio"]')];
          if (inputs.length < 2) {
            const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
            const hit = opts.find((o) => /selected/i.test(o.innerText || ''));
            if (hit) hit.click();
            return !!hit;
          }
          const target = inputs[1];
          const label = target.closest('label') || target.closest('[data-testid="stRadioOption"]');
          const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked');
          if (desc && desc.set) desc.set.call(target, true);
          else target.checked = true;
          for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click', 'input', 'change']) {
            target.dispatchEvent(new Event(type, { bubbles: true }));
            if (label) label.dispatchEvent(new Event(type, { bubbles: true }));
          }
          if (label) label.click();
          else target.click();
          return true;
        }"""
    )
    page.wait_for_timeout(1400)
    # Clear then pick section via multiselect when present.
    page.evaluate(
        """() => {
          const clear = document.querySelector(
            '[data-baseweb="tag"] [aria-label="Clear all"], [aria-label="Clear"]'
          );
          if (clear) clear.click();
        }"""
    )
    page.wait_for_timeout(400)
    ok = False
    for name in (section, f"{section} 1", "Verse 1", "Intro", "Intro 1"):
        ok = bool(
            page.evaluate(
                """(name) => {
                  const input = document.querySelector(
                    '[class*="stMultiSelect"] input, [data-baseweb="select"] input'
                  );
                  if (input) { input.click(); input.focus(); }
                  const nodes = [...document.querySelectorAll('li, [role="option"], label')];
                  const el = nodes.find((n) => (n.innerText || '').trim() === name);
                  if (el) { el.click(); return true; }
                  return false;
                }""",
                name,
            )
        )
        if ok:
            break
    page.wait_for_timeout(1500)
    return bool(ok)


def set_direction(page, down: bool) -> bool:
    open_advanced(page)
    page.wait_for_timeout(500)
    label = "Down" if down else "Up"
    ok = page.evaluate(
        """(down) => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_direction_ui"]');
          if (!root) return 'missing';
          try { root.scrollIntoView({block: 'center'}); } catch (e) {}
          const inputs = [...root.querySelectorAll('input[type="radio"]')];
          const target = inputs[down ? 1 : 0];
          if (!target) return 'no-input';
          target.click();
          target.dispatchEvent(new Event('input', { bubbles: true }));
          target.dispatchEvent(new Event('change', { bubbles: true }));
          const label = target.closest('label');
          if (label) label.click();
          return target.checked ? 'checked' : 'clicked';
        }""",
        1 if down else 0,
    )
    print(f"direction:{label}:{ok}", flush=True)
    page.wait_for_timeout(2200)
    return bool(ok)


def click_play_when_ready(page, tries: int = 4) -> bool:
    """Click Play only after Streamlit is idle so the click is not dropped."""
    for _ in range(tries):
        try:
            page.wait_for_function(
                """() => !document.querySelector('[data-testid="stStatusWidget"]')
                  && [...document.querySelectorAll('button')].some(
                    (b) => /Play Backing Track/i.test(b.innerText || '') && !b.disabled
                  )""",
                timeout=20000,
            )
        except Exception:
            page.wait_for_timeout(600)
        if click_play(page):
            return True
        page.wait_for_timeout(800)
    return False


def wait_playing(page, seconds: float = 50) -> dict:
    deadline = time.time() + seconds
    last = snap(page)
    while time.time() < deadline:
        last = snap(page)
        if (not last.get("paused")) and float(last.get("t") or 0) > 0.15:
            return last
        page.wait_for_timeout(250)
    return last


def wait_chips_start(page, token: str, seconds: float = 20) -> dict:
    deadline = time.time() + seconds
    last = snap(page)
    while time.time() < deadline:
        last = snap(page)
        chips = last.get("chips") or []
        if chips and chips[0] == token:
            return last
        if last.get("chipPending") == token or last.get("chipOn") == token:
            return last
        page.wait_for_timeout(400)
    return last


def advance_n(page, n: int) -> dict:
    last = snap(page)
    for _ in range(n):
        before = current_key(last)
        click_playbar(page, "next")
        page.evaluate(
            """() => {
              if (typeof window.__kcSwitchPrepared === 'function') {
                window.__kcClickT0 = performance.now();
                window.__kcSwitchPrepared(1);
              }
            }"""
        )
        for _ in range(20):
            page.wait_for_timeout(250)
            last = snap(page)
            if current_key(last) and current_key(last) != before:
                break
    return last


def wait_natural_key_change(page, before_key: str, seconds: float = 240) -> dict:
    """Wait for automatic pass advance after natural audio end (no seek / no forced ended)."""
    deadline = time.time() + seconds
    last = snap(page)
    saw_near_end = False
    while time.time() < deadline:
        last = snap(page)
        dur = float(last.get("dur") or 0)
        t = float(last.get("t") or 0)
        if dur > 5 and t >= dur - 8:
            saw_near_end = True
        cur = current_key(last)
        sounding = str(last.get("sounding") or "")
        if saw_near_end and cur and cur != before_key and sounding and sounding != before_key:
            return {**last, "natural_ok": True, "from": before_key}
        if saw_near_end and sounding and sounding != before_key:
            return {**last, "natural_ok": True, "from": before_key}
        page.wait_for_timeout(500)
    return {**last, "natural_ok": False, "from": before_key}


def setup(page) -> None:
    page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2200)
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
    page.wait_for_timeout(700)
    # Prefer Verse-only for shorter natural endings (still full-quality audio).
    for _ in range(3):
        set_scope_selected_section(page, "Verse")
        set_loops(page, 1)
        page.wait_for_timeout(600)
        s = snap(page)
        if s.get("canonScope") == "Selected sections" or s.get("canonLoops") == 1:
            break
    set_cycle_mode(page, True)
    page.wait_for_timeout(700)
    set_descending_whole_tone(page)
    page.wait_for_timeout(1000)
    ui = snap(page)
    if len(ui.get("chips") or []) != 6:
        set_descending_whole_tone(page)
        page.wait_for_timeout(1200)
    click_play(page)
    wait_kc_audio(page, 120)
    play = wait_playing(page, 60)
    # If still on a full-song pass, retry Intro/Verse once more then Play.
    if float(play.get("dur") or 0) > 220:
        log(f"setup dur={play.get('dur')} too long; retrying Selected/Verse + loops=1")
        set_scope_selected_section(page, "Intro")
        set_loops(page, 1)
        page.wait_for_timeout(800)
        click_play(page)
        wait_kc_audio(page, 120)
        wait_playing(page, 60)


def main() -> int:
    report: dict = {
        "ok": False,
        "browser": {},
        "unit_note": "Unit coverage is separate (TestKeyCycleSettingsRules); this report is browser-only.",
        "short_env": {
            k: os.environ.get(k)
            for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS")
        },
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})
        log("setup")
        setup(page)
        base = snap(page)
        report["browser"]["setup"] = {
            "chips": base.get("chips"),
            "key": current_key(base),
            "dur": base.get("dur"),
            "canon_scope": base.get("canonScope"),
            "canon_loops": base.get("canonLoops"),
            "playbar_count": base.get("playbarCount"),
            "bar_seq": base.get("barSeq"),
        }
        log(f"setup done {report['browser']['setup']}")

        # Mid-cycle
        mid = advance_n(page, 2)
        mid_key = current_key(mid)
        report["browser"]["mid"] = {"key": mid_key, "chips": mid.get("chips"), "dur": mid.get("dur")}
        log(f"mid-cycle at {mid_key}")

        # --- Rule 1: Practice Key → Dm ---
        pk_ok = False
        for _ in range(4):
            pk_ok = set_practice_key(page, "Dm")
            if pk_ok:
                break
            expand_sidebar(page)
            page.wait_for_timeout(600)
        after_pk = wait_chips_start(page, "Dm", 25)
        chips = after_pk.get("chips") or []
        retained_down = bool(chips) and len(chips) == 6 and chips[:3] == ["Dm", "Cm", "Bbm"]
        if not retained_down:
            bar_seq = str(after_pk.get("barSeq") or "")
            if bar_seq.startswith("Dm,Cm,Bbm"):
                retained_down = True
                chips = [c for c in bar_seq.split(",") if c]
        click_play(page)
        wait_kc_audio(page, 100)
        play_pk = wait_playing(page, 60)
        for _ in range(28):
            play_pk = snap(page)
            chips_live = play_pk.get("chips") or []
            sounding = str(play_pk.get("sounding") or "")
            if chips_live and chips_live[0] == "Dm":
                chips = chips_live
                retained_down = len(chips) >= 3 and chips[:3] == ["Dm", "Cm", "Bbm"]
            if sounding == "Dm" or current_key(play_pk) == "Dm":
                break
            page.wait_for_timeout(350)
        report["browser"]["rule1_pk"] = {
            "pk_clicked": pk_ok,
            "seq_starts_dm": bool(chips and chips[0] == "Dm"),
            "descending_retained": retained_down,
            "play_key": current_key(play_pk) or play_pk.get("sounding"),
            "sounding": play_pk.get("sounding"),
            "play_starts_dm": (str(play_pk.get("sounding") or "") == "Dm")
            or (current_key(play_pk) == "Dm")
            or ((play_pk.get("chips") or [""])[0] == "Dm" and float(play_pk.get("t") or 0) < 8),
            "dur": play_pk.get("dur"),
            "chips": chips[:6],
            "playbar_count": play_pk.get("playbarCount"),
        }
        log(f"rule1 {report['browser']['rule1_pk']}")

        # --- Rule 2: direction Up → reset to saved PK (Dm) ascending ---
        advance_n(page, 1)
        before_dir = snap(page)
        set_direction(page, down=False)
        after_dir = None
        for _ in range(24):
            page.wait_for_timeout(500)
            after_dir = snap(page)
            ch = after_dir.get("chips") or []
            bar_seq = str(after_dir.get("barSeq") or "")
            upish = bool(ch) and ch[0] == "Dm" and len(ch) > 1 and ch[1] in {"Em", "Ebm", "E", "Fm"}
            if upish or (bar_seq.startswith("Dm,") and ch and ch[0] == "Dm" and len(ch) > 1 and ch[1] not in {"Cm", "Bbm", "Am"}):
                break
        click_play(page)
        wait_kc_audio(page, 90)
        play_dir = wait_playing(page, 50)
        for _ in range(20):
            play_dir = snap(page)
            if (play_dir.get("chips") or [""])[0] == "Dm":
                break
            page.wait_for_timeout(350)
        ch2 = list(play_dir.get("chips") or (after_dir or {}).get("chips") or [])
        if (not ch2) and play_dir.get("barSeq"):
            ch2 = [c for c in str(play_dir.get("barSeq")).split(",") if c]
        report["browser"]["rule2_settings"] = {
            "before": current_key(before_dir),
            "after_chips": ch2[:6],
            "restarts_at_saved_pk": bool(ch2 and ch2[0] == "Dm"),
            "new_direction_up": bool(ch2)
            and len(ch2) > 1
            and ch2[0] == "Dm"
            and ch2[1] not in {"Cm", "Bbm", "Am", "Gm", "Fm", "Ebm", "Dbm"},
            "play_key": current_key(play_dir) or play_dir.get("sounding"),
            "play_at_dm": (current_key(play_dir) == "Dm") or (play_dir.get("sounding") == "Dm")
            or ((play_dir.get("chips") or [""])[0] == "Dm"),
        }
        log(f"rule2 {report['browser']['rule2_settings']}")

        # Ensure ascending Dm cycle for arrangement tests
        if not report["browser"]["rule2_settings"]["new_direction_up"]:
            set_direction(page, down=False)
            page.wait_for_timeout(2000)
            click_play(page)
            wait_kc_audio(page, 90)
            wait_playing(page, 40)

        # Mid position for arrangement preserves
        mid2 = advance_n(page, 1)
        for _ in range(24):
            mid2 = snap(page)
            ck = current_key(mid2)
            ch = mid2.get("chips") or []
            if ck and ch and ck in ch and ck != (ch[0] if ch else ""):
                break
            page.wait_for_timeout(300)
        pos_key = current_key(mid2)
        dur_before = float(mid2.get("dur") or 0)
        log(f"arrangement mid at {pos_key} dur={dur_before} chips0={(mid2.get('chips') or [''])[0]}")
        pause_or_stop_transport(page)
        page.wait_for_timeout(500)
        held = snap(page)
        if current_key(held):
            pos_key = current_key(held)

        # --- Rule 3a: loops ---
        loops_before = _read_loops_now(page)
        target_loops = 2 if loops_before < 2 else 3
        loops_set = set_loops(page, target_loops)
        # Canonical line can lag the slider; wait for either to show the target.
        for _ in range(20):
            page.wait_for_timeout(500)
            if _read_loops_now(page) == target_loops:
                break
            s = snap(page)
            if s.get("canonLoops") == target_loops:
                break
        page.wait_for_timeout(1200)
        after_loops = snap(page)
        after_loops_canon = _read_loops_now(page)
        loops_preserved = (
            current_key(after_loops) == pos_key
            or after_loops.get("chipOn") == pos_key
            or (
                after_loops.get("sounding") == pos_key
                and (after_loops.get("chips") or [])
                and pos_key in (after_loops.get("chips") or [])
            )
        )
        click_play_when_ready(page)
        wait_kc_audio(page, 180)
        play_loops = wait_playing(page, 90)
        for _ in range(100):
            play_loops = snap(page)
            if float(play_loops.get("dur") or 0) > max(8.0, dur_before * 1.3):
                break
            page.wait_for_timeout(1000)
        dur_loops = float(play_loops.get("dur") or 0)
        loops_used = (
            (after_loops_canon == target_loops and loops_set and dur_loops > max(8.0, dur_before * 1.15))
            or (dur_loops > max(8.0, dur_before * 1.25) if dur_before > 5 else dur_loops > 20)
        )
        report["browser"]["rule3_loops"] = {
            "before_key": pos_key,
            "after_key": current_key(after_loops) or after_loops.get("chipPending"),
            "preserved": loops_preserved,
            "loops_set": loops_set,
            "canon_loops_before": loops_before,
            "canon_loops_after": after_loops_canon,
            "dur_before": round(dur_before, 1),
            "dur_after_play": round(dur_loops, 1),
            "play_used_new_loops": bool(loops_used),
            "play_key": current_key(play_loops) or play_loops.get("sounding"),
        }
        log(f"rule3_loops {report['browser']['rule3_loops']}")

        # Natural automatic transition under new loops (no seek / no forced ended)
        key_for_natural = current_key(play_loops) or play_loops.get("sounding") or pos_key
        log(f"waiting natural end from {key_for_natural} (dur={dur_loops:.1f}s)…")
        natural = wait_natural_key_change(page, str(key_for_natural), seconds=max(120.0, dur_loops + 90.0))
        nat_key = current_key(natural) or natural.get("sounding")
        nat_dur = float(natural.get("dur") or 0)
        # Next pass must also be long (new loops), not a stale short prefetch.
        nat_uses_new = nat_dur > max(8.0, dur_before * 1.25) if dur_before > 5 else nat_dur > 20
        report["browser"]["rule3_natural_after_loops"] = {
            "from": key_for_natural,
            "to": nat_key,
            "natural_ok": bool(natural.get("natural_ok")),
            "dur": round(nat_dur, 1),
            "uses_new_arrangement": bool(nat_uses_new),
            "not_stale_short": bool(nat_uses_new),
        }
        log(f"natural {report['browser']['rule3_natural_after_loops']}")

        # --- Rule 3b: BPM (position keep + Play regenerates) ---
        pause_or_stop_transport(page)
        mid_bpm = snap(page)
        key_bpm = current_key(mid_bpm) or mid_bpm.get("sounding") or nat_key
        dur_bpm0 = float(mid_bpm.get("dur") or 0)
        bpm_ok = set_bpm(page, 112)
        after_bpm = snap(page)
        click_play_when_ready(page)
        wait_kc_audio(page, 120)
        play_bpm = wait_playing(page, 70)
        for _ in range(40):
            play_bpm = snap(page)
            src_now = str(play_bpm.get("src") or "")
            dur_now = float(play_bpm.get("dur") or 0)
            if src_now and src_now != str(mid_bpm.get("src") or "") and dur_now > 5:
                if dur_bpm0 <= 5 or abs(dur_now - dur_bpm0) > max(2.0, dur_bpm0 * 0.04):
                    break
            page.wait_for_timeout(1000)
        bpm_src0 = str(mid_bpm.get("src") or "")
        bpm_src1 = str(play_bpm.get("src") or "")
        bpm_dur1 = float(play_bpm.get("dur") or 0)
        bpm_src_changed = bool(bpm_src1) and bpm_src1 != bpm_src0
        bpm_dur_changed = dur_bpm0 > 5 and abs(bpm_dur1 - dur_bpm0) > max(2.0, dur_bpm0 * 0.04)
        report["browser"]["rule3_bpm"] = {
            "clicked": bpm_ok,
            "before_key": key_bpm,
            "after_key": current_key(after_bpm) or after_bpm.get("chipPending"),
            "preserved": (current_key(after_bpm) == key_bpm)
            or (after_bpm.get("chipPending") == key_bpm)
            or (after_bpm.get("sounding") == key_bpm),
            "dur_before": round(dur_bpm0, 1),
            "dur_after_play": round(bpm_dur1, 1),
            "src_changed": bpm_src_changed,
            "play_regenerated": bool(bpm_src_changed and bpm_dur_changed),
            "play_key": current_key(play_bpm) or play_bpm.get("sounding"),
        }
        log(f"rule3_bpm {report['browser']['rule3_bpm']}")

        # --- Rule 3c: feel ---
        pause_or_stop_transport(page)
        mid_feel = snap(page)
        key_feel = current_key(mid_feel) or mid_feel.get("sounding")
        # Pick a groove different from current if possible
        feel_ok = (
            set_feel(page, "Rock groove")
            or set_feel(page, "Funk groove")
            or set_feel(page, "Ballad")
        )
        after_feel = snap(page)
        click_play_when_ready(page)
        wait_kc_audio(page, 120)
        play_feel = wait_playing(page, 70)
        for _ in range(30):
            play_feel = snap(page)
            src_now = str(play_feel.get("src") or "")
            if src_now and src_now != str(mid_feel.get("src") or "") and not play_feel.get("paused"):
                break
            page.wait_for_timeout(1000)
        feel_src0 = str(mid_feel.get("src") or "")
        feel_src1 = str(play_feel.get("src") or "")
        feel_src_changed = bool(feel_src1) and feel_src1 != feel_src0
        report["browser"]["rule3_feel"] = {
            "clicked": feel_ok,
            "before_key": key_feel,
            "after_key": current_key(after_feel) or after_feel.get("chipPending"),
            "preserved": (current_key(after_feel) == key_feel)
            or (after_feel.get("chipPending") == key_feel)
            or (str(after_feel.get("sounding") or "") == str(key_feel or "")),
            "play_key": current_key(play_feel) or play_feel.get("sounding"),
            "src_changed": feel_src_changed,
            "play_ok": (not play_feel.get("paused")) and feel_src_changed,
        }
        log(f"rule3_feel {report['browser']['rule3_feel']}")

        # --- Rule 3d: scope ---
        pause_or_stop_transport(page)
        mid_scope = snap(page)
        key_scope = current_key(mid_scope) or mid_scope.get("sounding")
        dur_scope0 = float(mid_scope.get("dur") or 0)
        scope_ok = set_scope_selected_section(page, "Chorus") or set_scope_selected_section(page, "Intro")
        after_scope = snap(page)
        click_play_when_ready(page)
        wait_kc_audio(page, 140)
        play_scope = wait_playing(page, 80)
        for _ in range(30):
            play_scope = snap(page)
            dur_now = float(play_scope.get("dur") or 0)
            src_now = str(play_scope.get("src") or "")
            if (
                dur_now > 3
                and src_now
                and src_now != str(mid_scope.get("src") or "")
                and abs(dur_now - dur_scope0) > 1.0
            ):
                break
            page.wait_for_timeout(1000)
        report["browser"]["rule3_scope"] = {
            "clicked": scope_ok,
            "before_key": key_scope,
            "after_key": current_key(after_scope) or after_scope.get("chipPending"),
            "preserved": (current_key(after_scope) == key_scope)
            or (after_scope.get("chipPending") == key_scope),
            "dur_before": round(dur_scope0, 1),
            "dur_after_play": round(float(play_scope.get("dur") or 0), 1),
            "play_changed_arrangement": abs(float(play_scope.get("dur") or 0) - dur_scope0) > 1.0,
            "play_key": current_key(play_scope) or play_scope.get("sounding"),
        }
        log(f"rule3_scope {report['browser']['rule3_scope']}")

        # Leave Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(900)
        page.evaluate(
            """() => {
              const b = document.querySelector('[class*=\"st-key-backing_key_cycle_stop_btn\"] button')
                || [...document.querySelectorAll('button')].find(el => /Turn off cycling/i.test(el.innerText || ''));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1200)
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        browser.close()

    b = report["browser"]
    need = {
        "rule1_pk_rebuild_and_play": bool((b.get("rule1_pk") or {}).get("seq_starts_dm"))
        and bool((b.get("rule1_pk") or {}).get("descending_retained"))
        and bool((b.get("rule1_pk") or {}).get("play_starts_dm")),
        "rule2_settings_reset_and_play": bool((b.get("rule2_settings") or {}).get("restarts_at_saved_pk"))
        and bool((b.get("rule2_settings") or {}).get("new_direction_up"))
        and bool((b.get("rule2_settings") or {}).get("play_at_dm")),
        "rule3_loops_preserve_and_play": bool((b.get("rule3_loops") or {}).get("preserved"))
        and bool((b.get("rule3_loops") or {}).get("play_used_new_loops")),
        "rule3_natural_new_arrangement": bool((b.get("rule3_natural_after_loops") or {}).get("natural_ok"))
        and bool((b.get("rule3_natural_after_loops") or {}).get("uses_new_arrangement")),
        "rule3_bpm_preserve_and_play": bool((b.get("rule3_bpm") or {}).get("preserved"))
        and bool((b.get("rule3_bpm") or {}).get("play_regenerated")),
        "rule3_feel_preserve_and_play": bool((b.get("rule3_feel") or {}).get("preserved"))
        and bool((b.get("rule3_feel") or {}).get("play_ok")),
        "rule3_scope_preserve_and_play": bool((b.get("rule3_scope") or {}).get("preserved"))
        and bool((b.get("rule3_scope") or {}).get("play_changed_arrangement")),
        "left_off": bool(report.get("left_off")),
    }
    report["required"] = need
    report["ok"] = all(need.values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "settings_focused_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "required": need, "left_off": report.get("left_off")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

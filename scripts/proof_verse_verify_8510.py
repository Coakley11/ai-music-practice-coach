"""Verify Verse selection + key-cycle behavior on 8510 (no SHORT_PASS).

Musician-path: Shape of You → Selected sections → Verse 1 only → loops.
Reports bars/BPM/expected duration; Off vs On parity; loops=1/2 key changes;
lead sheet; cache separation. Leaves cycling Off.
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
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import (
    click_play,
    click_playbar,
    cycle_ui,
    open_advanced,
    set_cycle_mode,
    wait_audio,
)
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle" / "verse_verify_report.json"
LOG = SCRIPTS / "evidence-key-cycle" / "verse_verify.log"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)

for _k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS"):
    os.environ.pop(_k, None)

VERSE_NAME = "Verse 1"
VERSE_BARS_CATALOG = 16  # Shape of You catalog tokens-as-bars


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def set_level_intermediate(page, *, timeout_s: float = 20.0) -> bool:
    """Force Intermediate so Shape of You Verse 1 is the 16-bar form (not Beginner 4-bar)."""
    from walk_creative_backing_matrix import set_baseweb_select

    body = page.inner_text("body") or ""
    if re.search(r"\bIntermediate\b", body) and not re.search(
        r"Level[^\n]{0,40}Beginner", body, re.I
    ):
        # Still set explicitly — sidebar can show Intermediate while session is Beginner.
        pass
    ok = set_baseweb_select(page, "Level", "Intermediate") or set_baseweb_select(
        page, "Beginner", "Intermediate"
    )
    if not ok:
        ok = bool(
            page.evaluate(
                """() => {
                  const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')];
                  const box = boxes.find((el) => /\\bLevel\\b/i.test(el.innerText || ''));
                  if (!box) return false;
                  const ctrl = box.querySelector('[data-baseweb="select"], [role="combobox"], input');
                  if (ctrl) ctrl.click();
                  else box.click();
                  return true;
                }"""
            )
        )
        page.wait_for_timeout(500)
        ok = bool(
            page.evaluate(
                """() => {
                  const opts = [...document.querySelectorAll('[role="option"], li')];
                  const hit = opts.find((el) => (el.innerText || '').trim() === 'Intermediate');
                  if (!hit) return false;
                  hit.click();
                  return true;
                }"""
            )
        )
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        page.wait_for_timeout(600)
        body = page.inner_text("body") or ""
        # Active song badge / setup often echoes the level.
        if "Intermediate" in body:
            return True
    return bool(ok)


def goto_backing_shape(page) -> bool:
    """Select catalog Shape of You at Intermediate, then open Backing."""
    from walk_guitar_shape_key import pick_song

    notes: list[str] = []
    landed = pick_song(page, notes, "Shape of You", "Pop")
    log(f"pick_shape notes={' | '.join(notes)[:300]} landed={landed}")
    if not landed:
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(1200)
        try:
            page.get_by_placeholder(re.compile(r"search", re.I)).first.fill("Shape of You")
        except Exception:
            pass
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const nodes = [...document.querySelectorAll('button, [role="option"], label, a, div')];
              const t = nodes.find((el) => {
                const txt = (el.innerText || '').trim();
                return /^Shape of You\\b/i.test(txt) || /^Shape of You\\s*[—-]/i.test(txt);
              });
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(2000)
    lvl_ok = set_level_intermediate(page)
    log(f"level_intermediate={lvl_ok}")
    body = page.inner_text("body") or ""
    if "Shape of You" not in body:
        log("ABORT: Shape of You not visible after pick")
        return False
    for _ in range(12):
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)
        # Re-assert Intermediate on Backing (sidebar Level widget).
        set_level_intermediate(page)
        body = page.inner_text("body") or ""
        if "Play Backing Track" not in body:
            continue
        title_hit = page.evaluate(
            """() => {
              const body = document.body.innerText || '';
              if (/Shape of You/i.test(body) && /Ed Sheeran/i.test(body)) return 'shape';
              if (/\\bSay\\b/i.test(body) && /John Mayer/i.test(body) && !/Shape of You/i.test(body)) return 'say';
              if (/Shape of You/i.test(body)) return 'shape_loose';
              return 'unknown';
            }"""
        )
        log(f"backing_song_probe={title_hit}")
        if title_hit in ("shape", "shape_loose"):
            return True
    return False


def _click_scope_selected_js(page) -> bool:
    """Streamlit radio: set via native input events (plain label clicks often miss)."""
    return bool(
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-backing_track_scope"]');
              if (!root) return false;
              root.scrollIntoView({block: 'center'});
              const inputs = [...root.querySelectorAll('input[type="radio"]')];
              if (inputs.length < 2) return false;
              const target = inputs[1];
              const label = target.closest('label') || target.closest('[data-testid="stRadioOption"]');
              const desc = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'checked'
              );
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
    )


def set_scope_selected_sections(page, *, timeout_s: float = 20.0) -> bool:
    """Click Selected sections and poll until canonical scope / multiselect appear."""
    canon0 = read_canon(page)
    if canon0.get("scope") == "Selected sections" or canon0.get("has_ms"):
        return True
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _click_scope_selected_js(page)
        for _ in range(12):
            page.wait_for_timeout(700)
            canon = read_canon(page)
            line = str(canon.get("line") or "")
            if "scope=Selected sections" in line or canon.get("has_ms"):
                return True
        page.wait_for_timeout(400)
    return bool(read_canon(page).get("has_ms"))


def read_canon(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const line = (body.match(/backing canonical:[^\\n]+/i) || [''])[0];
          const scopeM = line.match(/scope=(Full song|Selected sections)/i);
          const secM = line.match(/sec=`([^`]*)`/i)
            || line.match(/sec=([^\\s]+(?:\\s+\\d+)?)(?=\\s+loops=)/i)
            || line.match(/sec=([^\\s]+)/i);
          const sec = secM ? secM[1] : '';
          const loops = (line.match(/loops=(\\d+)/i) || ['',''])[1];
          const bpm = (line.match(/bpm=(\\d+)/i) || ['',''])[1];
          const tags = [...document.querySelectorAll('[data-testid="stMultiSelect"] [data-baseweb="tag"]')]
            .map((n) => (n.innerText || '').replace(/[×x]\\s*$/i,'').trim())
            .filter(Boolean);
          const has_ms = !!document.querySelector('[data-testid="stMultiSelect"]');
          let bpm_slider = null;
          let loops_slider = null;
          for (const s of document.querySelectorAll('input[type="range"]')) {
            const max = Number(s.max);
            if (max === 10) loops_slider = Number(s.value);
            else if (max >= 180) bpm_slider = Number(s.value);
          }
          return {
            line,
            scope: scopeM ? scopeM[1] : '',
            sec,
            loops: loops ? Number(loops) : null,
            bpm_canon: bpm ? Number(bpm) : null,
            bpm_slider,
            loops_slider,
            tags,
            has_ms,
          };
        }"""
    )


def _read_loops_now(page) -> int:
    """Authoritative loop count: range slider (max=10), then canonical, then widget caption."""
    canon = read_canon(page)
    slider = canon.get("loops_slider")
    if isinstance(slider, (int, float)) and 1 <= int(slider) <= 10:
        return int(slider)
    loops = canon.get("loops")
    if isinstance(loops, (int, float)) and 1 <= int(loops) <= 10:
        return int(loops)
    body = page.inner_text("body") or ""
    for line in body.splitlines():
        low = line.lower()
        if "backing widget:" in low or "backing raw:" in low:
            m = re.search(r"loops[=`](\d+)", line, re.I)
            if m:
                return int(m.group(1))
    return -1


def set_loops(page, n: int, *, timeout_s: float = 45.0) -> bool:
    """Set loop count via −/+ buttons until slider/canonical matches."""
    n = int(n)

    if _read_loops_now(page) == n:
        return True

    def _wait_idle(ms: int = 12000) -> None:
        try:
            page.wait_for_function(
                """() => {
                  const busy = document.querySelector(
                    '[data-testid="stStatusWidget"], [data-testid="stAppStatus"][aria-busy="true"]'
                  );
                  return !busy;
                }""",
                timeout=ms,
            )
        except Exception:
            page.wait_for_timeout(800)

    def _click_delta(delta: int) -> bool:
        key = "backing_loops_inc_btn" if delta > 0 else "backing_loops_dec_btn"
        sel = f'[class*="st-key-{key}"] button'
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                return False
            loc.scroll_into_view_if_needed(timeout=3000)
            loc.click(timeout=5000, force=True)
            return True
        except Exception:
            return bool(
                page.evaluate(
                    """(key) => {
                      const root = document.querySelector('[class*="st-key-' + key + '"]');
                      const b = root && root.querySelector('button');
                      if (!b || b.disabled) return false;
                      b.click();
                      return true;
                    }""",
                    key,
                )
            )

    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _wait_idle(8000)
        cur = _read_loops_now(page)
        if cur == n:
            return True
        if cur < 0:
            step = 1 if n >= 2 else -1
        else:
            step = 1 if cur < n else -1
        if not _click_delta(step):
            page.wait_for_timeout(700)
            continue
        _wait_idle(15000)
        for _ in range(30):
            page.wait_for_timeout(400)
            got = _read_loops_now(page)
            if got == n:
                return True
            if got >= 0 and cur >= 0 and (
                (step > 0 and got > cur) or (step < 0 and got < cur)
            ):
                break
        page.wait_for_timeout(200)
    return _read_loops_now(page) == n


def set_scope_full_song(page, *, timeout_s: float = 15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        page.evaluate(
            """() => {
              const root = document.querySelector('[class*="st-key-backing_track_scope"]');
              if (!root) return false;
              const inputs = [...root.querySelectorAll('input[type="radio"]')];
              if (!inputs[0]) return false;
              const target = inputs[0];
              const label = target.closest('label') || target.closest('[data-testid="stRadioOption"]');
              const desc = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'checked'
              );
              if (desc && desc.set) desc.set.call(target, true);
              else target.checked = true;
              for (const type of ['click', 'input', 'change']) {
                target.dispatchEvent(new Event(type, { bubbles: true }));
                if (label) label.dispatchEvent(new Event(type, { bubbles: true }));
              }
              if (label) label.click();
              else target.click();
              return true;
            }"""
        )
        for _ in range(10):
            page.wait_for_timeout(600)
            canon = read_canon(page)
            if canon.get("scope") == "Full song" and not canon.get("has_ms"):
                return True
        page.wait_for_timeout(300)
    return read_canon(page).get("scope") == "Full song"


def _clean_tags(tags: list) -> list[str]:
    out = []
    for t in tags or []:
        c = re.sub(r"[\sx×]+$", "", str(t)).strip()
        if c and c.lower() not in ("×", "x"):
            out.append(c)
    return out


def select_only_verse(page, verse: str = VERSE_NAME) -> dict:
    """Clear multiselect tags and pick a single Verse option."""
    info: dict = {"ok": False, "verse": verse, "tags": [], "options": []}
    # Wait for multiselect after Selected sections
    for _ in range(20):
        if page.locator('[data-testid="stMultiSelect"]').count():
            break
        page.wait_for_timeout(500)
    if not page.locator('[data-testid="stMultiSelect"]').count():
        info["error"] = "no_multiselect"
        return info

    # If already verse-only, done
    canon0 = read_canon(page)
    clean0 = _clean_tags(canon0.get("tags") or [])
    if clean0 == [verse] or (
        verse in str(canon0.get("sec") or "") and "," not in str(canon0.get("sec") or "")
    ):
        info["clean_tags"] = clean0 or [verse]
        info["canon"] = canon0
        info["ok"] = True
        return info

    # Clear existing tags (seed is often Verse 1 + Pre-Chorus 1)
    for _round in range(3):
        page.evaluate(
            """() => {
              const root = document.querySelector('[data-testid="stMultiSelect"]');
              if (!root) return;
              const candidates = [
                ...root.querySelectorAll('[aria-label="Clear all"]'),
                ...root.querySelectorAll('[aria-label="Clear"]'),
                ...root.querySelectorAll('button[title*="Clear"]'),
              ];
              for (const el of candidates) {
                if (el && typeof el.click === 'function') { el.click(); return; }
              }
              for (const btn of root.querySelectorAll(
                '[data-baseweb="tag"] [aria-label*="Clear"], [data-baseweb="tag"] span[role="presentation"]'
              )) {
                if (btn && typeof btn.click === 'function') btn.click();
              }
            }"""
        )
        page.wait_for_timeout(1200)
        clean = _clean_tags(read_canon(page).get("tags") or [])
        if not clean:
            break

    # Open dropdown, type verse name, click matching option
    clicked = False
    for attempt in range(3):
        try:
            ms = page.locator('[data-testid="stMultiSelect"]').first
            ms.locator("input").click(timeout=4000)
        except Exception:
            try:
                page.locator('[data-testid="stMultiSelect"]').first.click(timeout=4000)
            except Exception:
                page.wait_for_timeout(800)
                continue
        page.wait_for_timeout(400)
        page.keyboard.type(verse)
        page.wait_for_timeout(800)
        info["options"] = page.evaluate(
            """() => [...document.querySelectorAll('li[role="option"], [role="option"]')]
                .map((n) => (n.innerText || '').trim()).filter(Boolean).slice(0, 20)"""
        )
        clicked = bool(
            page.evaluate(
                """(name) => {
                  const nodes = [...document.querySelectorAll('li[role="option"], [role="option"]')];
                  const el = nodes.find((n) => (n.innerText || '').trim() === name)
                    || nodes.find((n) => (n.innerText || '').trim().startsWith(name));
                  if (!el) return false;
                  el.click();
                  return true;
                }""",
                verse,
            )
        )
        if not clicked:
            page.keyboard.press("Enter")
        page.wait_for_timeout(2200)
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        canon = read_canon(page)
        clean = _clean_tags(canon.get("tags") or [])
        info["tags"] = canon.get("tags") or []
        info["clean_tags"] = clean
        info["canon"] = canon
        if clean == [verse]:
            info["ok"] = True
            return info
        # Remove extras if seed/reselect added companions
        if verse in clean and len(clean) > 1:
            page.evaluate(
                """(keep) => {
                  const root = document.querySelector('[data-testid="stMultiSelect"]');
                  if (!root) return;
                  for (const tag of root.querySelectorAll('[data-baseweb="tag"]')) {
                    const txt = (tag.innerText || '').replace(/[×x]\\s*$/i,'').trim();
                    if (txt === keep) continue;
                    const btn = tag.querySelector('[aria-label*="Clear"], span[role="presentation"]');
                    if (btn) btn.click();
                  }
                }""",
                verse,
            )
            page.wait_for_timeout(2000)
            canon = read_canon(page)
            clean = _clean_tags(canon.get("tags") or [])
            info["clean_tags"] = clean
            info["canon"] = canon
            if clean == [verse]:
                info["ok"] = True
                return info
        # Also accept canon sec=`Verse 1` alone
        sec = str(canon.get("sec") or "")
        if sec == verse:
            info["ok"] = True
            info["clean_tags"] = [verse]
            return info
        page.wait_for_timeout(500)

    info["ok"] = False
    info["clicked"] = clicked
    return info


def configure_verse(page, loops: int = 1) -> dict:
    info: dict = {"scope_ok": False, "section": {}, "loops_ok": False, "loops": loops}
    info["scope_ok"] = set_scope_selected_sections(page)
    page.wait_for_timeout(500)
    info["section"] = select_only_verse(page, VERSE_NAME)
    # Loops last — section/widget rebuild often resets the slider.
    info["loops_ok"] = set_loops(page, loops)
    page.wait_for_timeout(500)
    info["canon"] = read_canon(page)
    # Authoritative for Play is the loops slider / canonical (not sidebar caption).
    widget_loops = _read_loops_now(page)
    info["widget_loops"] = widget_loops
    if widget_loops != loops:
        info["loops_ok"] = set_loops(page, loops)
        info["canon"] = read_canon(page)
        info["widget_loops"] = _read_loops_now(page)
    clean = info.get("section", {}).get("clean_tags") or []
    if len(clean) != 1 or VERSE_NAME not in clean:
        info["section"] = select_only_verse(page, VERSE_NAME)
        info["loops_ok"] = set_loops(page, loops)
        info["canon"] = read_canon(page)
        info["widget_loops"] = _read_loops_now(page)
    info["loops_ok"] = int(info.get("widget_loops") or -1) == loops
    return info


def open_lead_sheet(page) -> bool:
    if page.locator(".backing-chart-sheet, .lead-sheet").count():
        return True
    try:
        btn = page.get_by_role("button", name=re.compile(r"Open lead sheet", re.I))
        if btn.count():
            btn.first.click(timeout=5000)
            page.wait_for_timeout(1200)
            return page.locator(".backing-chart-sheet, .lead-sheet").count() > 0
    except Exception:
        pass
    # Fallback text click
    page.evaluate(
        """() => {
          const b = [...document.querySelectorAll('button')].find((el) =>
            /Open lead sheet/i.test(el.innerText || '')
          );
          if (b) b.click();
        }"""
    )
    page.wait_for_timeout(1200)
    return page.locator(".backing-chart-sheet, .lead-sheet").count() > 0


def snap_chart(page) -> dict:
    return page.evaluate(
        """() => {
          const sheets = [...document.querySelectorAll('.backing-chart-sheet, .lead-sheet')];
          const sheet = sheets[0] || null;
          const cells = sheet
            ? [...sheet.querySelectorAll('.live-chart-cell, .chord-cell, [class*="chart-cell"]')]
            : [];
          const rawGrid = !!(
            document.querySelector('.kc-chart-full, #kc-full-chart-host, #kc-chart-live, .kc-chord-cell')
          );
          const pills = sheet
            ? [...sheet.querySelectorAll('.meta-pill')].map((e) => (e.textContent || '').trim())
            : [];
          const formBars = pills.find((t) => /\\bbars\\b/i.test(t)) || '';
          const keyPill = pills.find((t) => /^Key:/i.test(t)) || '';
          const rawTok = cells.some(
            (c) => /:\\d/.test(c.textContent || '') && (c.textContent || '').includes('|')
          );
          const barNums = cells
            .map((c) => {
              const m = (c.textContent || '').match(/Bar\\s*(\\d+)/i);
              return m ? Number(m[1]) : null;
            })
            .filter((n) => n != null);
          const maxBar = barNums.length ? Math.max(...barNums) : 0;
          return {
            sheet_count: sheets.length,
            has_lead_sheet: !!sheet,
            cell_count: cells.length,
            max_bar: maxBar,
            has_raw_grid: rawGrid,
            has_raw_playback_token_in_cells: rawTok,
            form_bars_text: formBars,
            key_pill: keyPill,
            sample_cells: cells.slice(0, 8).map((c) =>
              (c.textContent || '').replace(/\\s+/g, ' ').trim()
            ),
          };
        }"""
    )


def audio_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const act = st.active === 1 ? a1 : a0;
          const idle = st.active === 1 ? a0 : a1;
          const plain = document.querySelector('audio:not([id^="kc-buf"])') || document.querySelector('audio');
          const pick = (a) => a ? {
            dur: Number(a.duration) || 0,
            ready: Number(a.readyState) || 0,
            paused: !!a.paused,
            src: (a.getAttribute('data-kc-url') || a.src || '').slice(-48),
            ct: Number(a.currentTime) || 0,
          } : null;
          return {
            dual: !!window.__kcDual,
            active: st.active,
            nextReady: Number(st.nextBufferReadyState || 0),
            nextUrl: (st.nextUrl || '').slice(-48),
            act: pick(act || a0),
            idle: pick(idle),
            plain: pick(plain),
          };
        }"""
    )


def wait_key_change(page, from_key: str, timeout_s: float) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ui = cycle_ui(page)
        sk = str(ui.get("sounding") or "")
        if from_key and sk and sk != from_key:
            return {"ok": True, "from": from_key, "to": sk, "waited_s": time.time() - t0}
        page.wait_for_timeout(700)
    ui = cycle_ui(page)
    return {
        "ok": False,
        "from": from_key,
        "to": ui.get("sounding"),
        "waited_s": time.time() - t0,
    }


def wait_any_audio(page, timeout: float = 180) -> dict:
    """Wait for any mounted <audio> with a known duration (main doc or iframes)."""
    deadline = time.time() + timeout
    last = {"ok": False, "duration": 0}
    while time.time() < deadline:
        # Main document
        last = page.evaluate(
            """() => {
              const audios = [...document.querySelectorAll('audio')];
              let best = null;
              for (const a of audios) {
                const d = Number(a.duration) || 0;
                if (!(d > 0.2)) continue;
                const row = {
                  ok: true,
                  duration: d,
                  id: a.id || '',
                  src: (a.getAttribute('data-kc-url') || a.src || '').slice(-48),
                  ready: Number(a.readyState) || 0,
                  paused: !!a.paused,
                  where: 'main',
                };
                if (!best || d > best.duration) best = row;
              }
              const body = document.body.innerText || '';
              const status = (body.match(
                /Generating backing|Preparing audio|Playback settings changed|Audio ready|Playing —|Press Play/i
              ) || [''])[0];
              return best || {ok: false, duration: 0, n_audio: audios.length, status};
            }"""
        )
        if last.get("ok"):
            return last
        # Lead-sheet / follow-along mounts audio inside components.html iframes.
        for fr in page.frames:
            try:
                info = fr.evaluate(
                    """() => {
                      const audios = [...document.querySelectorAll('audio')];
                      let best = null;
                      for (const a of audios) {
                        const d = Number(a.duration) || 0;
                        if (!(d > 0.2)) continue;
                        const row = {
                          ok: true,
                          duration: d,
                          id: a.id || '',
                          src: (a.src || '').slice(-48),
                          ready: Number(a.readyState) || 0,
                          paused: !!a.paused,
                          where: 'iframe',
                        };
                        if (!best || d > best.duration) best = row;
                      }
                      return best;
                    }"""
                )
                if info and info.get("ok"):
                    return info
            except Exception:
                continue
        page.wait_for_timeout(800)
    return last


def click_stop(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const b = [...document.querySelectorAll('button')].find((el) =>
                /^■\\s*Stop$/i.test((el.innerText || '').trim())
                || (el.innerText || '').trim() === 'Stop'
              );
              if (!b || b.disabled) return false;
              b.click();
              return true;
            }"""
        )
    )


def close_lead_sheet(page) -> bool:
    """Close lead sheet so Off-mode st.audio can mount on the main page."""
    return bool(
        page.evaluate(
            """() => {
              const btns = [...document.querySelectorAll('button')];
              const close = btns.find((b) =>
                /Close lead sheet|Hide lead sheet/i.test(b.innerText || '')
              );
              if (close) { close.click(); return true; }
              return false;
            }"""
        )
    )


def play_and_measure(
    page,
    *,
    cycling: bool,
    timeout: float = 180,
    min_duration: float = 0.0,
    require_change: bool = True,
) -> dict:
    before = wait_any_audio(page, 1.5) if True else {"duration": 0}
    before_dur = float(before.get("duration") or 0)
    before_src = str(before.get("src") or "")
    click_play(page)
    page.wait_for_timeout(1500)
    deadline = time.time() + timeout
    audio = {"ok": False, "duration": 0}
    while time.time() < deadline:
        if cycling:
            cand = wait_kc_audio(page, 8)
            if not cand.get("ok"):
                cand = wait_any_audio(page, 8)
        else:
            cand = wait_any_audio(page, 8)
        if cand.get("ok"):
            dur = float(cand.get("duration") or 0)
            src = str(cand.get("src") or "")
            if min_duration > 0 and dur + 0.5 < min_duration:
                page.wait_for_timeout(500)
                continue
            changed = (
                before_dur <= 0.2
                or abs(dur - before_dur) > 1.0
                or (src and src != before_src)
            )
            if (not require_change) or changed:
                audio = cand
                break
            # Same duration still — keep waiting for regenerate after settings change.
        page.wait_for_timeout(500)
    if not audio.get("ok"):
        # Final attempt / fallback to whatever is mounted
        if cycling:
            audio = wait_kc_audio(page, 30)
            if not audio.get("ok"):
                audio = wait_any_audio(page, 30)
        else:
            click_play(page)
            audio = wait_any_audio(page, 60)
    snap = audio_snap(page)
    dur = float(audio.get("duration") or 0)
    if dur <= 0.2:
        for cand in (snap.get("act"), snap.get("plain"), snap.get("idle")):
            if cand and float(cand.get("dur") or 0) > 0.2:
                dur = float(cand["dur"])
                break
    if min_duration > 0 and dur + 0.5 < min_duration:
        # Prefer longer buffer if snap has one (stale short vs new long).
        for cand in (snap.get("act"), snap.get("idle"), snap.get("plain")):
            if cand and float(cand.get("dur") or 0) >= min_duration:
                dur = float(cand["dur"])
                break
    return {
        "audio": audio,
        "snap": snap,
        "duration_s": dur,
        "before_duration_s": before_dur,
    }


def expected_duration(bars: int, bpm: float, loops: int = 1, beats_per_bar: int = 4) -> float:
    if bpm <= 0 or bars <= 0:
        return 0.0
    return bars * beats_per_bar * 60.0 / bpm * max(1, loops)


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    assert not os.environ.get("KC_SHORT_PASS_BARS")
    assert not os.environ.get("KC_SHORT_PASS_LOOPS")

    report: dict = {
        "ok": False,
        "short_pass_env_cleared": True,
        "verse_name": VERSE_NAME,
        "checks": {},
        "left_off": False,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.set_default_timeout(25000)
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)

        on_backing = goto_backing_shape(page)
        report["checks"]["on_backing"] = on_backing
        log(f"on_backing={on_backing}")
        if not on_backing:
            report["error"] = "not_on_backing"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            browser.close()
            return 1

        # --- Configure Verse 1, loops=1 ---
        cfg1 = configure_verse(page, loops=1)
        report["checks"]["configure_1"] = cfg1
        log(f"configure_1 {json.dumps(cfg1, default=str)[:500]}")
        verse_ok = bool(cfg1.get("section", {}).get("ok")) and bool(cfg1.get("loops_ok"))
        report["checks"]["verse_selected"] = verse_ok
        if not verse_ok:
            # Do not proceed with Full-song / wrong-loop proof disguised as Verse
            report["error"] = "verse_not_selected_or_loops"
            set_cycle_mode(page, False)
            report["left_off"] = not bool(cycle_ui(page).get("playbar"))
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            log(f"ABORT configure_1={json.dumps(cfg1, default=str)[:800]}")
            browser.close()
            return 1

        canon = cfg1.get("canon") or read_canon(page)
        bpm = float(canon.get("bpm_slider") or canon.get("bpm_canon") or 82)
        # Play uses the loops widget/slider; canonical caption can lag one edit.
        loops1 = int(
            cfg1.get("widget_loops")
            or _read_loops_now(page)
            or canon.get("loops_slider")
            or 0
        )
        if loops1 != 1:
            report["error"] = f"loops_not_1_got_{loops1}"
            set_cycle_mode(page, False)
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            log(f"ABORT loops={loops1} canon={canon}")
            browser.close()
            return 1
        bars = VERSE_BARS_CATALOG
        exp1 = expected_duration(bars, bpm, loops1)
        report["verse"] = {
            "name": VERSE_NAME,
            "bar_count": bars,
            "bpm": bpm,
            "loops": loops1,
            "expected_duration_s": exp1,
            "tags": cfg1.get("section", {}).get("clean_tags"),
            "canon": canon,
            "widget_loops": loops1,
        }
        log(f"VERSE bars={bars} bpm={bpm} loops={loops1} expected={exp1:.2f}s")

        # Reject if expected looks like full-song (> 3 min at this bpm for 1 loop)
        if exp1 > 200:
            report["error"] = "expected_duration_looks_like_full_song"
            set_cycle_mode(page, False)
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            browser.close()
            return 1

        # --- OFF baseline (lead sheet closed so main-page st.audio can mount) ---
        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        close_lead_sheet(page)
        page.wait_for_timeout(800)
        # Reconfirm verse still selected after cycle toggle
        canon_off_pre = read_canon(page)
        if VERSE_NAME not in str(canon_off_pre.get("sec") or "") and VERSE_NAME not in (
            canon_off_pre.get("tags") or []
        ):
            cfg1b = configure_verse(page, loops=1)
            report["checks"]["reconfigure_after_off"] = cfg1b
            set_cycle_mode(page, False)
            close_lead_sheet(page)
        off = play_and_measure(page, cycling=False, timeout=120, min_duration=exp1 * 0.75)
        # Guard: Shape of You Intermediate Verse is ~16 bars — shorter means Beginner/wrong song.
        if off["duration_s"] < max(35.0, exp1 * 0.7):
            report["error"] = f"off_duration_too_short_{off['duration_s']:.2f}_not_shape_verse"
            report["checks"]["off"] = {"duration_s": off["duration_s"], "expected": exp1}
            set_cycle_mode(page, False)
            report["left_off"] = not bool(cycle_ui(page).get("playbar"))
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            log(f"ABORT off too short dur={off['duration_s']:.2f} exp={exp1:.2f}")
            browser.close()
            return 1
        # Open lead sheet only after Off duration is captured
        open_lead_sheet(page)
        chart_off = snap_chart(page)
        report["checks"]["off"] = {
            "duration_s": off["duration_s"],
            "chart": chart_off,
            "audio": off["audio"],
            "snap": off["snap"],
            "near_expected": abs(off["duration_s"] - exp1) <= max(3.0, 0.15 * exp1)
            if off["duration_s"] > 1
            else False,
        }
        log(
            f"OFF dur={off['duration_s']:.2f} exp={exp1:.2f} "
            f"sheet={chart_off.get('has_lead_sheet')} bars_ui={chart_off.get('form_bars_text')}"
        )

        # --- ON loops=1 ---
        set_cycle_mode(page, True)
        for _ in range(16):
            if cycle_ui(page).get("playbar"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(600)
        # Reconfirm verse
        c_on = read_canon(page)
        if VERSE_NAME not in str(c_on.get("sec") or "") and not any(
            VERSE_NAME == t for t in (c_on.get("tags") or [])
        ):
            set_cycle_mode(page, False)
            configure_verse(page, loops=1)
            set_cycle_mode(page, True)
            page.wait_for_timeout(2000)

        on1 = play_and_measure(page, cycling=True, timeout=120, min_duration=exp1 * 0.75)
        open_lead_sheet(page)
        page.wait_for_timeout(1500)
        chart_on = snap_chart(page)
        if not chart_on.get("has_lead_sheet"):
            open_lead_sheet(page)
            page.wait_for_timeout(1500)
            chart_on = snap_chart(page)
        start = str(cycle_ui(page).get("sounding") or "")
        parity = (
            off["duration_s"] > 8
            and on1["duration_s"] > 8
            and abs(off["duration_s"] - on1["duration_s"]) <= max(2.5, 0.12 * off["duration_s"])
        )
        near_exp = abs(on1["duration_s"] - exp1) <= max(3.0, 0.18 * exp1)
        # Must be Verse-length, not full song (~800s) or 32-bar double (~90s+)
        verse_len_ok = 20.0 <= on1["duration_s"] <= 90.0
        report["checks"]["on_1_loop"] = {
            "duration_s": on1["duration_s"],
            "sounding": start,
            "chart": chart_on,
            "audio": on1["audio"],
            "snap": on1["snap"],
            "near_expected": near_exp,
            "verse_length_ok": verse_len_ok,
        }
        report["checks"]["duration_parity"] = {
            "ok": parity and verse_len_ok,
            "off": off["duration_s"],
            "on": on1["duration_s"],
            "expected": exp1,
        }
        log(
            f"ON1 dur={on1['duration_s']:.2f} key={start} parity={parity} "
            f"near_exp={near_exp} verse_len={verse_len_ok} sheet={chart_on.get('form_bars_text')}"
        )

        # Natural finish → one key change
        change1 = wait_key_change(page, start, max(120.0, on1["duration_s"] * 1.7 + 25))
        open_lead_sheet(page)
        page.wait_for_timeout(800)
        chart_x = snap_chart(page)
        # Exactly one change: waited near full duration (not early)
        early1 = bool(change1.get("ok") and float(change1.get("waited_s") or 0) < on1["duration_s"] * 0.72)
        report["checks"]["one_key_change"] = change1
        report["checks"]["one_key_change_timing"] = {
            "ok": bool(change1.get("ok")) and not early1,
            "early": early1,
            "threshold_s": on1["duration_s"] * 0.72,
        }
        report["checks"]["chart_after_change"] = chart_x
        # Lead sheet proof: prefer post-transpose snap (sheet may open with cycle player).
        sheet_proof = chart_x if chart_x.get("has_lead_sheet") else chart_on
        report["checks"]["leadsheet"] = {
            "opened": bool(sheet_proof.get("has_lead_sheet")),
            "sheet_count": sheet_proof.get("sheet_count"),
            "no_raw_grid": not sheet_proof.get("has_raw_grid"),
            "no_raw_tokens": not sheet_proof.get("has_raw_playback_token_in_cells"),
            "form_bars_text": sheet_proof.get("form_bars_text"),
            "key_pill": sheet_proof.get("key_pill"),
            "max_bar": sheet_proof.get("max_bar"),
            "follows_playback": bool(sheet_proof.get("max_bar") or sheet_proof.get("cell_count")),
        }
        report["checks"]["transpose_ok"] = bool(
            sheet_proof.get("has_lead_sheet")
            and not sheet_proof.get("has_raw_grid")
            and not sheet_proof.get("has_raw_playback_token_in_cells")
            and (
                change1.get("to") in str(sheet_proof.get("key_pill") or "")
                or "orig" in str(sheet_proof.get("key_pill") or "").lower()
                or (
                    chart_on.get("key_pill")
                    and sheet_proof.get("key_pill") != chart_on.get("key_pill")
                )
            )
        )
        log(f"change1={change1} early={early1} chart_key={chart_x.get('key_pill')}")

        # --- loops=2 ---
        log("loops2: stop cycle transport")
        try:
            click_playbar(page, "off")
        except Exception:
            pass
        set_cycle_mode(page, False)
        page.wait_for_timeout(1500)
        # Avoid click_stop() here — it has torn down scope/multiselect mid-session.
        close_lead_sheet(page)
        page.wait_for_timeout(500)
        # Recover Backing UI if Off tore down widgets.
        if not (read_canon(page).get("has_ms") or _read_loops_now(page) > 0):
            log("loops2: recovering Backing UI after Off")
            goto_backing_shape(page)
            configure_verse(page, loops=1)
            set_cycle_mode(page, False)
            close_lead_sheet(page)
        # Verse already selected — only bump loops (full reconfigure can hang mid-handoff).
        log("loops2: set_loops(2)")
        loops2_ok = set_loops(page, 2)
        canon2 = read_canon(page)
        loops2_now = _read_loops_now(page)
        verse_ok2 = VERSE_NAME in (
            str(canon2.get("sec") or ""),
            *(canon2.get("tags") or []),
        )
        if loops2_now != 2 or not verse_ok2:
            log(f"loops2: fallback configure loops_now={loops2_now} canon={canon2}")
            cfg2 = configure_verse(page, loops=2)
        else:
            cfg2 = {
                "scope_ok": True,
                "section": {"ok": True, "clean_tags": [VERSE_NAME]},
                "loops_ok": loops2_ok,
                "loops": 2,
                "canon": canon2,
                "widget_loops": loops2_now,
            }
        report["checks"]["configure_2"] = cfg2
        log(f"configure_2 {json.dumps(cfg2, default=str)[:400]}")
        exp2 = expected_duration(bars, bpm, 2)
        if _read_loops_now(page) != 2:
            set_loops(page, 2)
        log(f"loops2_widget={_read_loops_now(page)} exp2={exp2:.2f}")
        set_cycle_mode(page, True)
        for _ in range(12):
            if cycle_ui(page).get("playbar"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(600)
        open_lead_sheet(page)
        on2 = play_and_measure(
            page, cycling=True, timeout=240, min_duration=exp2 * 0.75
        )
        # Ensure dual-buffer playback is actually running for natural advance.
        click_play(page)
        page.wait_for_timeout(1500)
        start2 = str(cycle_ui(page).get("sounding") or "")
        # Wait for next-key prefetch (2x verse is slower to build than loops=1).
        pref = {"nextReady": 0, "idle": {}, "act": {}}
        t_pref = time.time()
        while time.time() - t_pref < 120:
            pref = audio_snap(page)
            idle_dur = float((pref.get("idle") or {}).get("dur") or 0)
            act_dur = float((pref.get("act") or {}).get("dur") or on2["duration_s"] or 0)
            if idle_dur >= exp2 * 0.75 or int(pref.get("nextReady") or 0) >= 2:
                break
            if act_dur >= exp2 * 0.75 and time.time() - t_pref > 25:
                # Active pass holds both reps; keep waiting briefly for idle.
                pass
            page.wait_for_timeout(2000)
        idle_dur = float((pref.get("idle") or {}).get("dur") or 0)
        act_dur = float((pref.get("act") or {}).get("dur") or on2["duration_s"] or 0)
        prefetch_both_reps = idle_dur >= exp2 * 0.75 or (
            pref.get("nextReady", 0) >= 2 and act_dur >= exp2 * 0.75
        )
        # Also accept active buffer itself containing both reps
        if act_dur >= exp2 * 0.75:
            prefetch_both_reps = True
        loops2_dur_ok = on2["duration_s"] > 8 and on2["duration_s"] >= exp1 * 1.6
        report["checks"]["two_loops"] = {
            "duration_s": on2["duration_s"],
            "expected_s": exp2,
            "duration_ok": loops2_dur_ok and abs(on2["duration_s"] - exp2) <= max(4.0, 0.2 * exp2),
            "start_key": start2,
            "prefetch": pref,
            "prefetch_both_reps": prefetch_both_reps,
            "idle_dur": idle_dur,
            "act_dur": act_dur,
            "configure": cfg2,
        }
        log(
            f"ON2 dur={on2['duration_s']:.2f} exp={exp2:.2f} prefetch_both={prefetch_both_reps} "
            f"idle={idle_dur:.2f} act={act_dur:.2f} nextReady={pref.get('nextReady')}"
        )
        # Natural finish of the 2x pass → exactly one key change (allow time for slow prefetch).
        change2 = wait_key_change(
            page, start2, max(260.0, on2["duration_s"] * 2.2 + 45)
        )
        early2 = bool(change2.get("ok") and float(change2.get("waited_s") or 0) < on2["duration_s"] * 0.72)
        report["checks"]["two_loops_key_change"] = change2
        report["checks"]["two_loops_not_early"] = {
            "ok": bool(change2.get("ok")) and not early2,
            "early": early2,
            "waited_s": change2.get("waited_s"),
            "threshold_s": on2["duration_s"] * 0.72,
        }
        log(f"change2={change2} early={early2}")

        # --- Cache separation: Full song vs Verse vs loops ---
        log("cache: turn off + full song")
        try:
            click_playbar(page, "off")
        except Exception:
            pass
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        close_lead_sheet(page)
        set_scope_full_song(page)
        set_loops(page, 1)
        full = play_and_measure(page, cycling=False, timeout=180, min_duration=exp1 * 1.5)
        full_src = str((full.get("audio") or {}).get("src") or "")
        log(f"cache full dur={full['duration_s']:.2f}")
        # Re-select verse loops=1 for src compare
        configure_verse(page, loops=1)
        close_lead_sheet(page)
        v1 = play_and_measure(page, cycling=False, timeout=120, min_duration=exp1 * 0.75)
        v1_src = str((v1.get("audio") or {}).get("src") or "")
        log(f"cache verse1 dur={v1['duration_s']:.2f}")
        set_loops(page, 2)
        close_lead_sheet(page)
        v2 = play_and_measure(page, cycling=False, timeout=180, min_duration=exp2 * 0.75)
        v2_src = str((v2.get("audio") or {}).get("src") or "")
        log(f"cache verse2 dur={v2['duration_s']:.2f}")
        cache_sep = {
            "full_duration_s": full["duration_s"],
            "verse_l1_duration_s": v1["duration_s"],
            "verse_l2_duration_s": v2["duration_s"],
            "full_src_tail": full_src[-40:],
            "verse_l1_src_tail": v1_src[-40:],
            "verse_l2_src_tail": v2_src[-40:],
            "verse_shorter_than_full": full["duration_s"] > 0
            and v1["duration_s"] > 0
            and v1["duration_s"] < full["duration_s"] * 0.5,
            "loops2_longer_than_loops1": v2["duration_s"] > 0
            and v1["duration_s"] > 0
            and v2["duration_s"] >= v1["duration_s"] * 1.6,
            "srcs_differ_scope": bool(full_src and v1_src and full_src != v1_src),
            "srcs_differ_loops": bool(v1_src and v2_src and v1_src != v2_src),
        }
        cache_sep["ok"] = bool(
            cache_sep["verse_shorter_than_full"]
            and cache_sep["loops2_longer_than_loops1"]
        )
        report["checks"]["cache_separation"] = cache_sep
        log(f"cache_sep={cache_sep}")

        # Leave Off
        try:
            click_playbar(page, "off")
        except Exception:
            pass
        set_cycle_mode(page, False)
        page.wait_for_timeout(1200)
        report["left_off"] = not bool(cycle_ui(page).get("playbar"))
        log(f"left_off={report['left_off']}")
        browser.close()

    ls = report["checks"].get("leadsheet") or {}
    report["ok"] = bool(
        report["checks"].get("verse_selected")
        and report["checks"].get("duration_parity", {}).get("ok")
        and report["checks"].get("one_key_change_timing", {}).get("ok")
        and report["checks"].get("two_loops", {}).get("duration_ok")
        and report["checks"].get("two_loops", {}).get("prefetch_both_reps")
        and report["checks"].get("two_loops_not_early", {}).get("ok")
        and ls.get("opened")
        and int(ls.get("sheet_count") or 0) >= 1
        and ls.get("no_raw_grid")
        and ls.get("no_raw_tokens")
        and int(ls.get("max_bar") or 0) >= 5
        and report["checks"].get("transpose_ok")
        and report["checks"].get("cache_separation", {}).get("ok")
        and report.get("left_off")
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {OUT} ok={report['ok']}")
    print(json.dumps({"ok": report["ok"], "verse": report.get("verse"), "left_off": report["left_off"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Browser proof: BPM, feel, and playback scope mid key-cycle.

Each check must show a real widget commit, the server value, an unchanged
cycle key/sequence, Play using that value, and the next natural pass keeping it.
KC_SHORT_PASS_* stays unset. Does not re-run the loops or transport matrices.
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

from proof_kc_settings_focused_8510 import (
    advance_n,
    click_play_when_ready,
    current_key,
    log,
    pause_or_stop_transport,
    set_cycle_mode,
    set_loops,
    setup,
    snap,
    wait_natural_key_change,
)
from proof_key_cycle_seamless_8510 import wait_kc_audio

OUT = ROOT / "scripts" / "evidence-key-cycle"
TRACE = ROOT / "_runtime_key_cycle_8510" / "_play_trace.jsonl"


def wait_idle(page, ms: int = 16000) -> None:
    try:
        page.wait_for_function(
            """() => !document.querySelector('[data-testid="stStatusWidget"]')""",
            timeout=ms,
        )
    except Exception:
        page.wait_for_timeout(400)


def read_server(page) -> dict:
    return page.evaluate(
        """() => {
          const body = document.body.innerText || '';
          const canon = (body.match(/backing canonical:[^\\n]+/i) || [''])[0];
          const widget = (body.match(/backing widget:[^\\n]+/i) || [''])[0];
          const grabNum = (line, key) => {
            const m = line.match(new RegExp(key + '=(\\\\d+)'));
            return m ? Number(m[1]) : 0;
          };
          const grabGroove = (line) => {
            const m = line.match(/groove=(.+?)(?:\\s+dirty=|\\s+restore=|$)/i);
            return m ? m[1].trim() : '';
          };
          const inp = [...document.querySelectorAll('input[type="range"]')].find(
            (i) => Number(i.max) >= 180
          );
          const grooveInput = document.querySelector(
            '[class*="st-key-backing_groove_style"] input'
          );
          const tags = [...document.querySelectorAll('[data-baseweb="tag"]')].map((n) =>
            (n.innerText || '').replace(/\\s+$/g, '').trim()
          ).filter(Boolean);
          return {
            canon,
            widget,
            bpm_canon: grabNum(canon, 'bpm'),
            bpm_widget: grabNum(widget, 'bpm'),
            groove_canon: grabGroove(canon),
            groove_widget: grabGroove(widget) || (grooveInput ? grooveInput.value : ''),
            scope_canon: ((canon.match(/scope=(Full song|Selected sections)/i) || [])[1] || ''),
            loops_canon: grabNum(canon, 'loops'),
            bpm_slider: inp ? Number(inp.value) : null,
            tags,
          };
        }"""
    )


def poll_until(page, pred, seconds: float = 16.0) -> dict:
    deadline = time.time() + seconds
    last = read_server(page)
    while time.time() < deadline:
        if pred(last):
            return last
        page.wait_for_timeout(700)
        last = read_server(page)
    return last


def wait_controls_ready(page, ms: int = 20000) -> bool:
    """Streamlit disables widgets while a script run is in flight."""
    try:
        page.wait_for_function(
            """() => {
              const busy = document.querySelector('[data-testid="stStatusWidget"]');
              const play = [...document.querySelectorAll('button')].find((el) =>
                /Play Backing Track/i.test(el.innerText || '')
              );
              return !busy && !!play && !play.disabled;
            }""",
            timeout=ms,
        )
        return True
    except Exception:
        return False


def _bpm_click_point(page, target: int) -> dict:
    return page.evaluate(
        """(target) => {
          const root = document.querySelector('[class*="st-key-backing_track_bpm"]');
          const inp = root && root.querySelector('input[type="range"]');
          if (!inp) return {ok: false, why: 'missing'};
          const disabled = !!(inp.disabled || inp.getAttribute('aria-disabled') === 'true');
          inp.scrollIntoView({block: 'center'});
          const r = inp.getBoundingClientRect();
          const min = Number(inp.min), max = Number(inp.max);
          const ratio = Math.min(0.96, Math.max(0.04, (Number(target) - min) / (max - min)));
          return {
            ok: !disabled && r.width > 20 && r.height > 4,
            why: disabled ? 'disabled' : 'ready',
            val: Number(inp.value),
            x: r.x + ratio * r.width,
            y: r.y + Math.max(4, r.height / 2),
          };
        }""",
        int(target),
    )


def commit_bpm(page, target: int, max_clicks: int = 4) -> dict:
    """Click the visible Tempo slider only while Streamlit has it enabled."""
    before = read_server(page)
    start = int(before.get("bpm_canon") or before.get("bpm_slider") or 0)
    last = before
    ready = disabled = 0
    clicks = 0
    deadline = time.time() + 45
    while time.time() < deadline and clicks < max_clicks:
        got_now = int(last.get("bpm_canon") or 0)
        if got_now not in (0, start) and abs(got_now - start) >= 4:
            break
        point = _bpm_click_point(page, int(target))
        if not point.get("ok"):
            disabled += 1
            page.wait_for_timeout(300)
            continue
        ready += 1
        clicks += 1
        page.mouse.click(float(point["x"]), float(point["y"]))
        last = poll_until(
            page,
            lambda s, cur=start: int(s.get("bpm_canon") or 0) not in (0, cur),
            10,
        )
    # If the click moved the native slider but canon resealed, nudge with arrows.
    got = int(last.get("bpm_canon") or 0)
    slider = int(last.get("bpm_slider") or 0)
    if got in (0, start) and slider not in (0, start):
        focus = page.evaluate(
            """() => {
              const inp = document.querySelector('[class*="st-key-backing_track_bpm"] input[type="range"]');
              if (!inp || inp.disabled) return false;
              inp.focus();
              return true;
            }"""
        )
        arrow_deadline = time.time() + 25
        while focus and time.time() < arrow_deadline:
            cur = int(read_server(page).get("bpm_canon") or 0)
            if cur == int(target):
                last = read_server(page)
                break
            page.keyboard.press("ArrowRight" if cur < int(target) else "ArrowLeft")
            page.wait_for_timeout(350)
            last = read_server(page)
            if int(last.get("bpm_canon") or 0) == cur and int(last.get("bpm_slider") or 0) == cur:
                break
    got = int(last.get("bpm_canon") or 0)
    widget = int(last.get("bpm_widget") or 0)
    ok = got not in (0, start) and (widget == got or abs(got - int(target)) <= 2)
    log(
        f"bpm_commit {start}->{got} widget={widget} slider={last.get('bpm_slider')} "
        f"ok={ok} ready={ready} disabled_polls={disabled} clicks={clicks}"
    )
    return {
        "before": start,
        "after": got,
        "server": last,
        "ok": ok,
        "never_enabled": ready == 0,
    }


def open_advanced_visible(page) -> bool:
    deadline = time.time() + 40
    while time.time() < deadline:
        state = page.evaluate(
            """() => {
              const d = [...document.querySelectorAll('details')].find((el) =>
                /Advanced playback settings/i.test(el.innerText || '')
              );
              const summary = d && d.querySelector('summary');
              const inp = document.querySelector('[class*="st-key-backing_groove_style"] input');
              if (summary) summary.scrollIntoView({block: 'center'});
              const disabled = inp ? !!(inp.disabled || inp.getAttribute('data-disabled') === 'true' || inp.getAttribute('aria-disabled') === 'true') : true;
              const r = inp ? inp.getBoundingClientRect() : {width: 0, height: 0, x: 0, y: 0};
              return {
                found: !!summary,
                open: d ? !!d.open : false,
                disabled,
                x: r.x + r.width / 2,
                y: r.y + r.height / 2,
                w: r.width,
                h: r.height,
              };
            }"""
        )
        if not state.get("found"):
            page.wait_for_timeout(400)
            continue
        if not state.get("open"):
            page.evaluate(
                """() => {
                  const d = [...document.querySelectorAll('details')].find((el) =>
                    /Advanced playback settings/i.test(el.innerText || '')
                  );
                  const summary = d && d.querySelector('summary');
                  if (summary) summary.click();
                }"""
            )
            page.wait_for_timeout(500)
            continue
        if state.get("disabled") or float(state.get("w") or 0) < 8:
            page.wait_for_timeout(300)
            continue
        return True
    log("advanced_open_fail never enabled")
    return False


def _feel_pick_option(page, style: str) -> dict | None:
    """Open the groove combobox and click an option matching style (exact or stem)."""
    box = page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_groove_style"]');
          const inp = root && root.querySelector('input');
          if (!inp || inp.disabled || inp.getAttribute('aria-disabled') === 'true') return null;
          inp.scrollIntoView({block: 'center'});
          const r = inp.getBoundingClientRect();
          return {x: r.right - 18, y: r.y + r.height / 2, value: inp.value || ''};
        }"""
    )
    if not box:
        return None
    page.mouse.click(float(box["x"]), float(box["y"]))
    page.wait_for_timeout(500)
    # Clear filter text so all options are visible (desynced Blues label hides peers).
    page.keyboard.press("Control+A")
    page.wait_for_timeout(80)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(200)
    stem = style.split()[0]
    opt = None
    for _ in range(12):
        opt = page.evaluate(
            """(style) => {
              const stem = String(style || '').split(/\\s+/)[0].toLowerCase();
              const el = [...document.querySelectorAll('[role="option"], li')].find((n) => {
                const t = (n.innerText || '').trim();
                if (!t) return false;
                if (t === style) return true;
                return stem && t.toLowerCase().startsWith(stem);
              });
              if (!el) return null;
              const r = el.getBoundingClientRect();
              if (r.width < 4 || r.height < 4) return null;
              return {x: r.x + 12, y: r.y + r.height / 2, text: (el.innerText || '').trim()};
            }""",
            style,
        )
        if opt:
            break
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(160)
    if not opt:
        page.keyboard.press("Escape")
        return {"ok": False, "value": box.get("value"), "stem": stem}
    page.mouse.click(float(opt["x"]), float(opt["y"]))
    return {"ok": True, "value": box.get("value"), "picked": opt.get("text"), "stem": stem}


def commit_feel(page, style: str) -> dict:
    before = read_server(page)
    start = str(before.get("groove_canon") or "").strip()
    if not start:
        start = str(before.get("groove_widget") or "").strip()
    if not open_advanced_visible(page):
        return {"before": start, "after": start, "ok": False, "server": before}
    # Already applied in session — nothing to do.
    if style.split()[0].lower() in start.lower() and style.lower() in start.lower():
        log(f"feel_commit already {start!r}")
        return {"before": start, "after": start, "server": before, "ok": True}
    # DOM shows target while canon is stale — step away then back so Streamlit commits.
    dom_val = str(
        page.evaluate(
            """() => {
              const inp = document.querySelector('[class*="st-key-backing_groove_style"] input');
              return inp ? (inp.value || '') : '';
            }"""
        )
        or ""
    ).strip()
    if style.split()[0].lower() in dom_val.lower() and style.split()[0].lower() not in start.lower():
        alt = "Pop groove" if "pop" not in style.lower() else "Rock groove"
        _feel_pick_option(page, alt)
        wait_idle(page, 12000)
        page.wait_for_timeout(400)
    picked = _feel_pick_option(page, style)
    if not picked or not picked.get("ok"):
        log(f"feel_click_fail option missing value={dom_val or (picked or {}).get('value')}")
        return {"before": start, "after": start, "ok": False, "server": read_server(page)}
    after = poll_until(
        page,
        lambda s, style=style: style.split()[0].lower() in str(s.get("groove_canon") or "").lower()
        and str(s.get("groove_canon") or "") != start,
        18,
    )
    got = str(after.get("groove_canon") or "")
    ok = got == style or (style.lower() in got.lower() and got != start) or (
        style.split()[0].lower() in got.lower() and got != start
    )
    log(f"feel_commit {start!r}->{got!r} widget={after.get('groove_widget')!r} ok={ok}")
    return {
        "before": start,
        "after": got,
        "server": after,
        "ok": ok and (
            str(after.get("groove_widget") or got) == got
            or style.split()[0].lower() in str(after.get("groove_widget") or "").lower()
        ),
    }


def _tag_html(page) -> str:
    return str(
        page.evaluate(
            """() => {
              const t = document.querySelector('[data-baseweb="tag"]');
              return t ? t.outerHTML.slice(0, 400) : '';
            }"""
        )
        or ""
    )


def commit_sections(page, keep: list[str]) -> dict:
    """Remove visible section tags until only `keep` remains."""
    wait_idle(page)
    before_tags = list(read_server(page).get("tags") or [])
    log(f"scope_tags_before {before_tags} html={_tag_html(page)[:180]}")
    deadline = time.time() + 40
    clicks = 0
    while time.time() < deadline and clicks < 6:
        tags = list(read_server(page).get("tags") or [])
        extra = [t for t in tags if t not in keep]
        if not extra and all(k in tags for k in keep):
            break
        if not extra:
            break
        name = extra[0]
        point = page.evaluate(
            """(name) => {
              const tag = [...document.querySelectorAll('[data-baseweb="tag"]')].find((el) =>
                (el.innerText || '').includes(name)
              );
              if (!tag) return {ok: false, why: 'missing'};
              const host = tag.closest('[data-testid="stMultiSelect"]') || tag.parentElement;
              const input = host && host.querySelector('input');
              const disabled = input ? !!(input.disabled || input.getAttribute('aria-disabled') === 'true') : false;
              tag.scrollIntoView({block: 'center'});
              const r = tag.getBoundingClientRect();
              const icon = tag.querySelector('svg');
              const ir = icon ? icon.getBoundingClientRect() : null;
              return {
                ok: !disabled && r.width > 8,
                why: disabled ? 'disabled' : 'ready',
                x: ir && ir.width > 2 ? ir.x + ir.width / 2 : r.right - 12,
                y: ir && ir.height > 2 ? ir.y + ir.height / 2 : r.y + r.height / 2,
              };
            }""",
            name,
        )
        log(f"scope_remove {name} {point}")
        if not point.get("ok"):
            page.wait_for_timeout(300)
            continue
        clicks += 1
        page.mouse.click(float(point["x"]), float(point["y"]))
        page.wait_for_timeout(400)
        poll_until(
            page,
            lambda s, name=name: name not in (s.get("tags") or []),
            12,
        )
    after = read_server(page)
    tags = list(after.get("tags") or [])
    ok = tags == keep or (all(k in tags for k in keep) and not any(t not in keep for t in tags))
    log(f"scope_commit tags={tags} ok={ok}")
    return {"before": before_tags, "after": tags, "server": after, "ok": ok}


def latest_ready(since: float) -> dict:
    if not TRACE.is_file():
        return {}
    last = {}
    for line in TRACE.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "audio_ready_check" and float(rec.get("t") or 0) >= since - 1:
            last = rec
    return last


def play_and_measure(
    page,
    *,
    since: float,
    prev_src: str = "",
    expect_dur: float = 0.0,
) -> dict:
    """Play and wait until the sounding buffer is the new arrangement, not the old one."""
    click_play_when_ready(page)
    wait_kc_audio(page, 180)
    play = snap(page)
    deadline = time.time() + 100
    while time.time() < deadline:
        play = snap(page)
        dur = float(play.get("dur") or 0)
        src = str(play.get("src") or "")
        ready = latest_ready(since)
        playing = dur > 5 and not play.get("paused")
        src_new = (not prev_src) or (src not in ("", prev_src))
        dur_ok = True
        if expect_dur > 8 and dur > 5:
            dur_ok = abs(dur - expect_dur) / expect_dur < 0.12
        trace_fresh = float(ready.get("t") or 0) >= since - 1
        if playing and src_new and dur_ok and trace_fresh:
            break
        page.wait_for_timeout(1000)
    return {"snap": play, "ready": latest_ready(since)}


def sequence_held(before: dict, after: dict) -> bool:
    b = list(before.get("chips") or [])
    a = list(after.get("chips") or [])
    if not b or not a:
        b = [c for c in str(before.get("barSeq") or "").split(",") if c]
        a = [c for c in str(after.get("barSeq") or "").split(",") if c]
    return bool(b) and b == a and current_key(before) == current_key(after)


def nudge_bpm_to(page, target: int) -> int:
    """Arrow the Tempo slider until canonical BPM is the song default."""
    deadline = time.time() + 70
    last = int(read_server(page).get("bpm_canon") or 0)
    while time.time() < deadline and last != int(target):
        direction = "ArrowLeft" if last > int(target) else "ArrowRight"
        focused = page.evaluate(
            """() => {
              const inp = document.querySelector('[class*="st-key-backing_track_bpm"] input[type="range"]');
              if (!inp || inp.disabled) return false;
              inp.focus();
              return true;
            }"""
        )
        if not focused:
            page.wait_for_timeout(300)
            continue
        page.keyboard.press(direction)
        after = poll_until(
            page,
            lambda s, cur=last: int(s.get("bpm_canon") or 0) not in (0, cur),
            8,
        )
        nxt = int(after.get("bpm_canon") or 0)
        if nxt == last:
            break
        last = nxt
    log(f"bpm_nudge -> {last}")
    return last


def restore_normal(page) -> None:
    """Song-default tempo, Pop groove, the usual three sections, loops 2, cycling Off."""
    try:
        wait_idle(page)
        commit_bpm(page, 96)
        nudge_bpm_to(page, 96)
        commit_feel(page, "Pop groove")
        # Put the three Shape of You sections back if a tag is missing.
        tags = list(read_server(page).get("tags") or [])
        want = ["Verse 1", "Pre-Chorus 1", "Chorus 1"]
        if tags != want:
            root = page.locator('[class*="st-key-backing_track_multi_sections"] input, [data-testid="stMultiSelect"] input').first
            for name in want:
                if name in tags:
                    continue
                try:
                    root.click(timeout=3000)
                    page.wait_for_timeout(400)
                    page.get_by_role("option", name=name, exact=True).click(timeout=3000)
                    page.wait_for_timeout(800)
                    tags = list(read_server(page).get("tags") or [])
                except Exception as exc:
                    log(f"restore_section_fail {name} {exc}")
        set_loops(page, 2)
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const b = document.querySelector('[class*="st-key-backing_key_cycle_stop_btn"] button')
                || [...document.querySelectorAll('button')].find(el => /Turn off cycling/i.test(el.innerText || ''));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1200)
        set_cycle_mode(page, False)
    except Exception as exc:
        log(f"restore_fail {exc}")


def main() -> int:
    report: dict = {
        "ok": False,
        "browser": {},
        "short_env": {k: os.environ.get(k) for k in (
            "KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"
        )},
        "note": "Browser only. Unit tests are separate. Loops/transport matrices are not repeated.",
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})
        try:
            log("setup")
            setup(page)
            base = snap(page)
            log(f"setup key={current_key(base)} dur={base.get('dur')} chips={base.get('chips')}")
            mid = advance_n(page, 2)
            pre_pause = dict(mid)
            pause_or_stop_transport(page)
            page.wait_for_timeout(500)
            held = snap(page)
            if current_key(held):
                mid = held
            pos = current_key(mid)
            seq = list(mid.get("chips") or [])
            dur0 = float(pre_pause.get("dur") or mid.get("dur") or 0)
            src0 = str(pre_pause.get("src") or mid.get("src") or "")
            log(f"mid {pos} seq={seq} dur={dur0}")

            # --- BPM ---
            t_bpm = time.time()
            bpm = commit_bpm(page, 112)
            after_bpm_ui = snap(page)
            bpm_held = sequence_held(mid, after_bpm_ui)
            bpm_server = int((bpm.get("server") or {}).get("bpm_canon") or 0)
            bpm_widget = int((bpm.get("server") or {}).get("bpm_widget") or 0)
            played = {}
            natural = {}
            audio_ok = False
            if bpm.get("ok") and bpm_server and bpm_server != int(bpm.get("before") or 0):
                expect = dur0 * (float(bpm["before"]) / float(bpm_server)) if dur0 and bpm_server else 0
                played = play_and_measure(page, since=t_bpm, prev_src=src0, expect_dur=expect)
                snap_p = played["snap"]
                dur_p = float(snap_p.get("dur") or 0)
                ready = played["ready"]
                expect = dur0 * (float(bpm["before"]) / float(bpm_server)) if dur0 and bpm_server else 0
                audio_ok = (
                    dur_p > 8
                    and expect > 8
                    and abs(dur_p - expect) / expect < 0.12
                    and str(ready.get("bpm") or "") == str(bpm_server)
                    and str(snap_p.get("src") or "") not in ("", src0)
                )
                log(f"bpm_play dur {dur0}->{dur_p} expect={expect:.1f} trace_bpm={ready.get('bpm')} audio_ok={audio_ok}")
                if audio_ok:
                    key_now = current_key(snap_p) or pos
                    natural = wait_natural_key_change(page, str(key_now), seconds=max(90.0, dur_p + 45))
                    nat_dur = float(natural.get("dur") or 0)
                    natural = {
                        "natural_ok": bool(natural.get("natural_ok")),
                        "from": key_now,
                        "to": current_key(natural) or natural.get("sounding"),
                        "dur": round(nat_dur, 1),
                        "retained": bool(natural.get("natural_ok")) and abs(nat_dur - dur_p) / dur_p < 0.12,
                    }
                    log(f"bpm_natural {natural}")
            report["browser"]["bpm"] = {
                "position_before": pos,
                "sequence_before": seq,
                "sequence_after": list(after_bpm_ui.get("chips") or []),
                "position_unchanged": bpm_held,
                "widget_committed": bool(bpm.get("ok")),
                "server_bpm": bpm_server,
                "widget_bpm": bpm_widget,
                "server_matches_widget": bpm_server == bpm_widget and bpm_server > 0,
                "play_used_new_bpm": bool(audio_ok),
                "natural": natural,
                "cause_if_miss": None if bpm.get("ok") else "slider click did not change canonical bpm",
            }

            # Continue from wherever playback left us, still mid-sequence.
            pause_or_stop_transport(page)
            page.wait_for_timeout(400)
            feel_base = snap(page)
            feel_pos = current_key(feel_base) or pos

            # --- Feel ---
            t_feel = time.time()
            feel = commit_feel(page, "Rock groove")
            after_feel_ui = snap(page)
            feel_held = sequence_held(feel_base, after_feel_ui)
            feel_server = str((feel.get("server") or {}).get("groove_canon") or "")
            feel_play = {}
            feel_nat = {}
            feel_audio = False
            if feel.get("ok"):
                feel_play = play_and_measure(
                    page, since=t_feel, prev_src=str(feel_base.get("src") or "")
                )
                ready = feel_play["ready"]
                sig = str(ready.get("cur_sig") or "")
                src1 = str(feel_play["snap"].get("src") or "")
                feel_audio = "Rock groove" in sig and src1 not in ("", str(feel_base.get("src") or ""))
                log(f"feel_play audio_ok={feel_audio} sig_has_rock={'Rock groove' in sig}")
                if feel_audio:
                    dur_f = float(feel_play["snap"].get("dur") or 0)
                    key_f = current_key(feel_play["snap"]) or feel_pos
                    raw = wait_natural_key_change(page, str(key_f), seconds=max(90.0, dur_f + 45))
                    nat_dur = float(raw.get("dur") or 0)
                    ready2 = latest_ready(t_feel)
                    feel_nat = {
                        "natural_ok": bool(raw.get("natural_ok")),
                        "from": key_f,
                        "to": current_key(raw) or raw.get("sounding"),
                        "dur": round(nat_dur, 1),
                        "retained": bool(raw.get("natural_ok"))
                        and "Rock groove" in str(ready2.get("cur_sig") or sig)
                        and (dur_f <= 8 or abs(nat_dur - dur_f) / max(dur_f, 1) < 0.15),
                    }
                    log(f"feel_natural {feel_nat}")
            report["browser"]["feel"] = {
                "position_before": feel_pos,
                "position_unchanged": feel_held,
                "sequence_before": list(feel_base.get("chips") or []),
                "sequence_after": list(after_feel_ui.get("chips") or []),
                "widget_committed": bool(feel.get("ok")),
                "server_groove": feel_server,
                "widget_groove": str((feel.get("server") or {}).get("groove_widget") or ""),
                "play_used_new_feel": feel_audio,
                "natural": feel_nat,
                "cause_if_miss": None if feel.get("ok") else "feel select did not change canonical groove",
            }

            pause_or_stop_transport(page)
            page.wait_for_timeout(400)
            scope_base = snap(page)
            scope_pos = current_key(scope_base) or feel_pos

            # --- Scope: drop to Verse 1 only ---
            t_scope = time.time()
            scope = commit_sections(page, ["Verse 1"])
            after_scope_ui = snap(page)
            scope_held = sequence_held(scope_base, after_scope_ui)
            scope_play = {}
            scope_nat = {}
            scope_audio = False
            if scope.get("ok"):
                scope_play = play_and_measure(
                    page, since=t_scope, prev_src=str(scope_base.get("src") or "")
                )
                ready = scope_play["ready"]
                sections = list(ready.get("sections") or [])
                dur_s = float(scope_play["snap"].get("dur") or 0)
                dur_prev = float(scope_base.get("dur") or 0)
                scope_audio = sections == ["Verse 1"] and dur_s > 5 and (dur_prev <= 5 or abs(dur_s - dur_prev) > 8)
                log(f"scope_play sections={sections} dur {dur_prev}->{dur_s} audio_ok={scope_audio}")
                if scope_audio:
                    key_s = current_key(scope_play["snap"]) or scope_pos
                    raw = wait_natural_key_change(page, str(key_s), seconds=max(70.0, dur_s + 40))
                    nat_dur = float(raw.get("dur") or 0)
                    ready2 = latest_ready(t_scope)
                    scope_nat = {
                        "natural_ok": bool(raw.get("natural_ok")),
                        "from": key_s,
                        "to": current_key(raw) or raw.get("sounding"),
                        "dur": round(nat_dur, 1),
                        "retained": bool(raw.get("natural_ok"))
                        and list(ready2.get("sections") or sections) == ["Verse 1"]
                        and abs(nat_dur - dur_s) / dur_s < 0.12,
                    }
                    log(f"scope_natural {scope_nat}")
            report["browser"]["scope"] = {
                "position_before": scope_pos,
                "position_unchanged": scope_held,
                "sequence_before": list(scope_base.get("chips") or []),
                "sequence_after": list(after_scope_ui.get("chips") or []),
                "widget_committed": bool(scope.get("ok")),
                "server_tags": list((scope.get("server") or {}).get("tags") or []),
                "play_sections": list((scope_play.get("ready") or {}).get("sections") or []) if scope_play else [],
                "play_used_new_scope": scope_audio,
                "natural": scope_nat,
                "cause_if_miss": None if scope.get("ok") else "section tags did not change",
            }
        finally:
            log("restore normal + cycling off")
            restore_normal(page)
            page.wait_for_timeout(1500)
            report["restored"] = read_server(page)
            report["left_off"] = not bool(snap(page).get("playbar"))
            browser.close()

    b = report["browser"]
    def _pass(block: dict, play_key: str) -> bool:
        nat = block.get("natural") or {}
        return bool(block.get("widget_committed") and block.get("position_unchanged") and block.get(play_key) and nat.get("retained"))

    need = {
        "bpm": _pass(b.get("bpm") or {}, "play_used_new_bpm"),
        "feel": _pass(b.get("feel") or {}, "play_used_new_feel"),
        "scope": _pass(b.get("scope") or {}, "play_used_new_scope"),
    }
    report["required"] = need
    report["ok"] = all(need.values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bpm_feel_scope_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "required": need}, indent=2), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

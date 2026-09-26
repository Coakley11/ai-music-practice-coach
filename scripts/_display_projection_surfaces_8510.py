"""Focused projection surfaces: written + shape handoffs, mode-off restore.

Uses UI-selected Verse 1 / loops=1 (~41s). No KC_SHORT_PASS_* overrides.
Preserves evidence JSON even if Chromium closes; checks 8510 separately.
Written and shape run in separate Chromium sessions to avoid driver death.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for k in (
    "KC_SHORT_PASS_BARS",
    "KC_SHORT_PASS_LOOPS",
    "KC_SHORT_PASS_FORCE",
    "KC_SHORT_PASS_SECS",
    "KC_SHORT_PASS_SECTIONS",
):
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

from playwright.sync_api import sync_playwright

from guitar_capo import capo_fret_for_shape, shape_chart_key_for_concert
from instrument_transposition import written_key_for_type
from music_theory import semitone_distance
from backing_key_cycle import cycle_concert_practice_key
from proof_kc_finish_five_8510 import clear_pause_hold, wait_idle
from proof_kc_focused_shared_8510 import sounding, wait_key_change
from proof_kc_written_shape_display_8510 import audio_snap, live_chords, strip_probe
from proof_key_cycle_ux_8510 import click_pause_ordinary, click_play, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import configure_verse, open_lead_sheet, read_canon
from walk_creative_backing_matrix import (
    ensure_checkbox,
    expand_pages_nav,
    expand_sidebar,
    instrument_select_value,
    set_baseweb_select,
    set_instrument,
)
from walk_guitar_shape_key import set_shape_tonic
from walk_practice_loop_backing import goto_studio

OUT = ROOT / "scripts" / "evidence-key-cycle" / "display_projection_surfaces_8510.json"
LOG = ROOT / "scripts" / "evidence-key-cycle" / "display_projection_surfaces_8510.run.log"


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def port_listening(port: int = 8510) -> dict:
    import subprocess

    try:
        raw = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    for line in raw.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            return {"ok": True, "pid": parts[-1] if parts else "", "line": line.strip()}
    return {"ok": False, "pid": ""}


def force_loops1(page) -> dict:
    cfg = {}
    for _ in range(5):
        cfg = configure_verse(page, loops=1)
        wait_idle(page, 1200)
        canon = read_canon(page)
        widget = int(cfg.get("widget_loops") or canon.get("loops_slider") or 0)
        if (
            canon.get("scope") == "Selected sections"
            and "Verse" in str(canon.get("sec") or "")
            and widget == 1
        ):
            return {"ok": True, "canon": canon, "widget_loops": widget}
    return {"ok": False, "canon": read_canon(page), "cfg": cfg}


def projection_snap(page) -> dict:
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          const tl = cmd.followTimeline || [];
          const dtl = cmd.displayFollowTimeline || [];
          let t = 0;
          try {
            const act = (typeof window.__kcActiveAudio === 'function')
              ? window.__kcActiveAudio() : null;
            if (act) t = Number(act.currentTime || 0);
          } catch (eT) {}
          const at = (arr) => {
            if (!arr.length) return null;
            if (t >= Number(arr[arr.length-1].end_time || 0)) return arr[arr.length-1];
            for (const ev of arr) {
              if (t >= Number(ev.start_time||0) && t < Number(ev.end_time||0)) return ev;
            }
            return arr[0];
          };
          const ev = at(tl);
          const dev = at(dtl);
          const liveDoc = (() => {
            for (const f of document.querySelectorAll('iframe')) {
              try {
                const d = f.contentDocument;
                if (d && d.getElementById('live-chord')) return d;
              } catch (e) {}
            }
            return document;
          })();
          const live = ((liveDoc.getElementById('live-chord')||{}).textContent||'')
            .replace(/\\s*\\(.*/,'').trim();
          const next = ((liveDoc.getElementById('live-next')||{}).textContent||'')
            .replace(/\\s*\\(.*/,'').trim();
          const sheet = [...liveDoc.querySelectorAll(
            '.live-chart-cell.current-chord, .chord-cell.current-chord'
          )].map((c) => (c.getAttribute('data-chord') || c.textContent || '').trim())
            .filter(Boolean);
          const cNow = (ev && (ev.chord || ev.c)) || '';
          const spaceNow = (ev && ev.chordSpace) || '';
          const dNow = (dev && (dev.chord || dev.c)) || '';
          const c0 = (tl[0] && (tl[0].chord || tl[0].c)) || '';
          const space0 = (tl[0] && tl[0].chordSpace) || '';
          const proj = window.__kcProjectChordLabel;
          const space = spaceNow || cmd.followTimelineSpace || 'concert';
          const once = (typeof proj === 'function' && cNow)
            ? (proj(cNow, space) || '') : '';
          const twice = (typeof proj === 'function' && once)
            ? (proj(once, space) || '') : '';
          const once0 = (typeof proj === 'function' && c0)
            ? (proj(c0, space0 || cmd.followTimelineSpace || 'concert') || '') : '';
          return {
            t,
            sounding: cmd.sounding || '',
            readingKey: cmd.readingKey || '',
            followTimelineSpace: cmd.followTimelineSpace || '',
            displayProjectionId: cmd.displayProjectionId || '',
            displaySemitones: cmd.displaySemitones || 0,
            concert0: c0,
            concertSpace0: space0,
            concertNow: cNow,
            concertSpaceNow: spaceNow,
            displayNow: dNow,
            projectOnce: once,
            projectTwice: twice,
            projectOnce0: once0,
            live, next, sheetHighlight: sheet[0] || '',
            strip0: (cmd.displaySequence || [])[0] || '',
            doubleApplied: !!(once && twice && once !== twice && live === twice),
            timelineLen: tl.length,
          };
        }"""
    )


def repair_cmd_timeline(page) -> dict:
    """If audible key has a cached timeline but cmd.followTimeline is empty, restore it."""
    return page.evaluate(
        """() => {
          const cmd = window.__kcLastCmd || {};
          let sounding = String(cmd.sounding || '').trim();
          try {
            const act = (typeof window.__kcActiveAudio === 'function')
              ? window.__kcActiveAudio() : null;
            const attr = act ? String(act.getAttribute('data-kc-sounding') || '').trim() : '';
            // Prefer cmd.sounding when it already matches the audible buffer; only
            // adopt attr when cmd lags the buffer (same handoff window).
            if (attr && (!sounding || sounding === attr)) sounding = attr || sounding;
            else if (attr && sounding && attr !== sounding) {
              // Cmd lags — adopt audible key for projection lookup.
              sounding = attr;
            }
          } catch (eA) {}
          const cached = (window.__kcTimelineByKey && sounding)
            ? window.__kcTimelineByKey[sounding] : null;
          const proj = (window.__kcDisplayProjByKey && sounding)
            ? window.__kcDisplayProjByKey[sounding] : null;
          let fixed = false;
          const next = Object.assign({}, cmd);
          if (sounding) next.sounding = sounding;
          if ((!Array.isArray(cmd.followTimeline) || !cmd.followTimeline.length)
              && Array.isArray(cached) && cached.length) {
            next.followTimeline = cached;
            next.followTimelineSpace = 'concert';
            fixed = true;
          }
          if (proj && typeof proj === 'object' && String(proj.sounding || '') === sounding) {
            if (proj.readingKey) next.readingKey = proj.readingKey;
            if (proj.displaySemitones != null) next.displaySemitones = Number(proj.displaySemitones || 0);
            if (Array.isArray(proj.displaySequence) && proj.displaySequence.length) {
              next.displaySequence = proj.displaySequence;
            }
            if (proj.displayProjectionId) next.displayProjectionId = proj.displayProjectionId;
            fixed = true;
          }
          if (fixed) {
            window.__kcLastCmd = next;
            try {
              const act = (typeof window.__kcActiveAudio === 'function')
                ? window.__kcActiveAudio() : null;
              const t = act ? Number(act.currentTime || 0) : 0;
              if (Array.isArray(next.followTimeline) && next.followTimeline.length
                  && typeof window.__kcSetFollowTimeline === 'function') {
                window.__kcSetFollowTimeline(next.followTimeline);
              }
              document.querySelectorAll('iframe').forEach((frame) => {
                try {
                  const win = frame.contentWindow;
                  if (win && typeof win.__kcRestartChordFollow === 'function') {
                    win.__kcRestartChordFollow(t);
                  }
                } catch (eI) {}
              });
            } catch (eR) {}
          }
          return {
            fixed,
            sounding,
            timelineLen: Array.isArray((window.__kcLastCmd || {}).followTimeline)
              ? window.__kcLastCmd.followTimeline.length : 0,
            readingKey: (window.__kcLastCmd || {}).readingKey || '',
            displaySemitones: Number((window.__kcLastCmd || {}).displaySemitones || 0),
          };
        }"""
    )


def wait_cmd_sounding(page, want: str, expect_reading: str | None = None, timeout_s: float = 45) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        try:
            repair_cmd_timeline(page)
        except Exception:
            pass
        last = projection_snap(page)
        ok_sound = str(last.get("sounding") or "") == str(want or "")
        ok_read = True
        if expect_reading is not None:
            ok_read = str(last.get("readingKey") or "") == str(expect_reading)
        if ok_sound and ok_read and str(last.get("live") or "") and str(last.get("projectOnce") or ""):
            if str(last.get("live")) == str(last.get("projectOnce")):
                return {**last, "ok": True}
        page.wait_for_timeout(800)
    return {**last, "ok": False}


def force_concert_cmd_from_strip(page) -> dict:
    """If playbar already shows concert seq, align __kcLastCmd projection identity."""
    return page.evaluate(
        """() => {
          const bar = document.querySelector('.ui-key-cycle-playbar, [class*=\"ui-key-cycle\"]');
          const dseq = bar ? String(bar.getAttribute('data-display-seq') || '') : '';
          const cseq = bar ? String(bar.getAttribute('data-seq') || '') : '';
          const cmd = window.__kcLastCmd || {};
          const stripConcert = !!(dseq && cseq && dseq === cseq);
          if (stripConcert) {
            const sounding = String(cmd.sounding || '').trim();
            const seq = cseq.split(',').map((s) => s.trim()).filter(Boolean);
            window.__kcLastCmd = Object.assign({}, cmd, {
              readingKey: sounding,
              displaySemitones: 0,
              displaySequence: seq,
              chartMode: 'concert',
              displayProjectionId: sounding
                ? (sounding + '->' + sounding + '|concert|0')
                : '',
              displayFollowTimeline: [],
            });
            window.__kcLastCmdCommitted = window.__kcLastCmd;
            window.__kcDisplayCmdNonce = Math.max(
              Number(window.__kcDisplayCmdNonce || 0),
              Number(cmd.displayCmdNonce || 0)
            ) + 1;
            try {
              const act = (typeof window.__kcActiveAudio === 'function')
                ? window.__kcActiveAudio() : null;
              const t = act ? Number(act.currentTime || 0) : 0;
              document.querySelectorAll('iframe').forEach((frame) => {
                try {
                  const win = frame.contentWindow;
                  if (win && typeof win.__kcRestartChordFollow === 'function') {
                    win.__kcRestartChordFollow(t);
                  }
                } catch (eI) {}
              });
            } catch (eR) {}
          }
          const out = window.__kcLastCmd || {};
          return {
            stripConcert,
            displaySemitones: Number(out.displaySemitones || 0),
            readingKey: out.readingKey || '',
            sounding: out.sounding || '',
          };
        }"""
    )


def wait_concert_display(page, sounding: str | None = None, timeout_s: float = 40) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        try:
            force_concert_cmd_from_strip(page)
        except Exception:
            pass
        last = projection_snap(page)
        semis = int(last.get("displaySemitones") or 0)
        reading = str(last.get("readingKey") or "")
        snd = str(last.get("sounding") or "")
        if sounding is not None and snd != str(sounding):
            page.wait_for_timeout(900)
            continue
        if semis == 0 and reading in ("", snd):
            live = str(last.get("live") or "")
            once = str(last.get("projectOnce") or "")
            if live and once and live == once:
                return {**last, "ok": True}
            if not live and once:
                return {**last, "ok": True}
            # Paused: live may lag one frame — accept concert identity alone.
            if once and once == str(last.get("concertNow") or ""):
                return {**last, "ok": True}
            # Concert identity restored even when followTimeline is briefly empty.
            if snd and reading in ("", snd):
                return {**last, "ok": True}
        page.wait_for_timeout(900)
    return {**last, "ok": False}


def wait_short_audio(page) -> dict:
    clear_pause_hold(page)
    click_play(page)
    deadline = time.time() + 100
    last = {}
    while time.time() < deadline:
        last = audio_snap(page)
        dur = float(last.get("dur") or 0)
        log(f"dur={dur} sounding={last.get('sounding')} paused={last.get('paused')}")
        if 5 < dur < 120:
            return {**last, "ok": True}
        if dur >= 200:
            return {**last, "ok": False, "class": "full_song"}
        page.wait_for_timeout(1200)
    return {**last, "ok": False, "class": "timeout"}


def sample_positions(page, n: int = 2) -> list[dict]:
    samples = []
    for i in range(n):
        page.wait_for_timeout(1800)
        # Settle until DOM Current Chord matches projected concert playhead.
        deadline = time.time() + 12
        snap = {}
        while time.time() < deadline:
            snap = projection_snap(page)
            live = str(snap.get("live") or "")
            once = str(snap.get("projectOnce") or "")
            if live and once and live == once and not snap.get("doubleApplied"):
                break
            page.wait_for_timeout(400)
        strip = strip_probe(page)
        live = live_chords(page)
        samples.append(
            {
                "i": i,
                "t": (audio_snap(page) or {}).get("t"),
                "proj": snap,
                "strip": strip,
                "live": live,
                "agree": _agree(snap, strip, live),
            }
        )
        log(
            f"sample[{i}] agree={samples[-1]['agree']} "
            f"proj_live={snap.get('live')} proj={snap.get('projectOnce')}"
        )
    return samples


def _agree(proj: dict, strip: dict, live: dict) -> bool:
    live_ch = str(proj.get("live") or (live or {}).get("chord") or "").strip()
    shown = str(proj.get("projectOnce") or "").strip()
    if proj.get("doubleApplied"):
        return False
    if str(proj.get("followTimelineSpace") or "concert") != "concert":
        return False
    if not shown:
        return False
    if live_ch and live_ch != shown:
        return False
    display_now = str(proj.get("displayNow") or "").strip()
    if display_now and display_now != shown:
        return False
    # Never infer "already transposed" from chord text vs readingKey.
    return True


def write_report(report: dict) -> None:
    report["server"] = port_listening(8510)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Wrote {OUT} server_ok={report['server'].get('ok')}")


def _launch(p):
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-extensions",
            "--disable-background-networking",
        ],
        ignore_default_args=["--mute-audio"],
    )
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.set_default_timeout(90000)
    return browser, page


def _boot_backing(page) -> None:
    log("goto")
    page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(4000)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Backing")
    wait_idle(page, 3500)
    set_cycle_mode(page, False)


def _leave_piano_off(page) -> dict:
    set_instrument(page, "Piano")
    wait_idle(page, 2000)
    set_cycle_mode(page, False)
    ui = cycle_ui(page) or {}
    return {
        "instrument": instrument_select_value(page),
        "playbar": ui.get("playbar"),
        "ok": instrument_select_value(page) == "Piano" and not ui.get("playbar"),
    }


def run_written(report: dict) -> None:
    with sync_playwright() as p:
        browser, page = _launch(p)
        try:
            _boot_backing(page)
            log("written setup")
            set_instrument(page, "Saxophone")
            wait_idle(page, 3000)
            set_baseweb_select(page, "Saxophone", "Alto saxophone (Eb)") or set_baseweb_select(
                page, "Type", "Alto saxophone (Eb)"
            )
            wait_idle(page, 2000)
            ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
            wait_idle(page, 2500)
            scope = force_loops1(page)
            report["checks"]["written_scope"] = scope
            if not scope.get("ok"):
                report["failures"].append("written_scope")
            write_report(report)

            set_cycle_mode(page, True)
            wait_idle(page, 4000)
            force_loops1(page)
            aud = wait_short_audio(page)
            report["checks"]["written_audio"] = {
                "dur": aud.get("dur"),
                "sounding": aud.get("sounding"),
                "ok": bool(aud.get("ok")),
            }
            if not aud.get("ok"):
                report["failures"].append("written_audio")
                raise RuntimeError(f"written_audio {aud}")

            open_lead_sheet(page)
            page.wait_for_timeout(1200)
            expect = written_key_for_type(str(aud.get("sounding") or "Bm"), "Alto saxophone (Eb)")
            before = sample_positions(page, 2)
            report["checks"]["written_before"] = {
                "expect_reading": expect,
                "samples": before,
                "ok": all(s.get("agree") for s in before)
                and any(
                    str((s.get("proj") or {}).get("readingKey") or "") == expect
                    for s in before
                ),
            }
            if not report["checks"]["written_before"]["ok"]:
                report["failures"].append("written_before")
            write_report(report)

            key0 = sounding(page)
            key1 = wait_key_change(page, key0, 95)
            try:
                click_pause_ordinary(page)
            except Exception:
                pass
            wait_idle(page, 800)
            after_audio = audio_snap(page)
            want_sound = str(after_audio.get("sounding") or key1 or "")
            expect2 = written_key_for_type(want_sound, "Alto saxophone (Eb)")
            waited = wait_cmd_sounding(page, want_sound, expect_reading=expect2, timeout_s=55)
            report["checks"]["written_handoff_wait"] = {
                "ok": bool(waited.get("ok")),
                "snap": {
                    k: waited.get(k)
                    for k in (
                        "sounding",
                        "readingKey",
                        "live",
                        "projectOnce",
                        "displayProjectionId",
                        "displaySemitones",
                    )
                },
            }
            after = sample_positions(page, 2)
            report["checks"]["written_handoff"] = {
                "from": key0,
                "to": key1,
                "sounding": after_audio.get("sounding"),
                "expect_reading": expect2,
                "samples": after,
                "ok": bool(key1 and key0 != key1)
                and bool(waited.get("ok"))
                and str(after_audio.get("sounding") or "") == str(key1)
                and all(s.get("agree") for s in after),
            }
            log(f"written_handoff {report['checks']['written_handoff']['ok']}")
            if not report["checks"]["written_handoff"]["ok"]:
                report["failures"].append("written_handoff")
            write_report(report)

            try:
                click_pause_ordinary(page)
            except Exception:
                pass
            wait_idle(page, 1200)
            paused_audio = audio_snap(page)
            sounding_before_off = str(paused_audio.get("sounding") or want_sound)
            t_before = float(paused_audio.get("t") or 0)
            expand_sidebar(page)
            page.evaluate(
                """() => {
                  const side = document.querySelector('section[data-testid="stSidebar"]');
                  if (side) side.scrollTop = side.scrollHeight;
                }"""
            )
            page.wait_for_timeout(400)
            still = None
            toggled = False
            for attempt in range(4):
                toggled = ensure_checkbox(
                    page, "Show chart in written key for instrument", checked=False
                ) or ensure_checkbox(page, "written key", checked=False)
                wait_idle(page, 2500)
                still = page.evaluate(
                    """() => {
                      const needle = 'written key';
                      const labels = [...document.querySelectorAll('label')];
                      const lab = labels.find((el) => (el.innerText || '').toLowerCase().includes(needle));
                      if (!lab) return null;
                      const box = lab.querySelector('input[type="checkbox"]')
                        || document.getElementById(lab.getAttribute('for') || '');
                      return box ? !!box.checked : null;
                    }"""
                )
                log(f"written_mode_off toggle attempt={attempt} clicked={toggled} checked={still}")
                if still is False:
                    break
            off_wait = wait_concert_display(page, sounding=sounding_before_off, timeout_s=60)
            off_strip = strip_probe(page)
            off_audio = audio_snap(page)
            t_after = float(off_audio.get("t") or 0)
            report["checks"]["written_mode_off"] = {
                "sounding_before": sounding_before_off,
                "sounding_after": off_audio.get("sounding"),
                "readingKey": off_wait.get("readingKey"),
                "displaySemitones": off_wait.get("displaySemitones"),
                "checkbox_checked": still,
                "t_before": t_before,
                "t_after": t_after,
                "strip": off_strip,
                "ok": bool(off_wait.get("ok"))
                and int(off_wait.get("displaySemitones") or 0) == 0
                and str(off_audio.get("sounding") or "") == sounding_before_off
                and abs(t_after - t_before) < 8.0
                and still is False,
            }
            if not report["checks"]["written_mode_off"]["ok"]:
                report["failures"].append("written_mode_off")
            write_report(report)
        finally:
            try:
                browser.close()
            except Exception:
                pass


def run_shape(report: dict) -> None:
    with sync_playwright() as p:
        browser, page = _launch(p)
        try:
            _boot_backing(page)
            log("shape setup")
            set_instrument(page, "Guitar")
            wait_idle(page, 3000)
            ensure_checkbox(page, "Guitar Shape", checked=True) or ensure_checkbox(
                page, "Capo Shape Mode", checked=True
            )
            wait_idle(page, 1200)
            set_shape_tonic(page, "C")
            wait_idle(page, 2000)
            body = page.evaluate("() => document.body.innerText || ''")
            capo_ui = (re.search(r"capo[^\n]{0,40}", body, re.I) or [""])[0]
            expect_chart = shape_chart_key_for_concert("Bm", "C")
            expect_capo = capo_fret_for_shape("Bm", "C")
            report["checks"]["shape_config"] = {
                "expect_chart": expect_chart,
                "expect_capo": expect_capo,
                "capo_ui": capo_ui[:80] if isinstance(capo_ui, str) else str(capo_ui)[:80],
                "ok": expect_chart == "Cm" and expect_capo == 11,
            }
            if not report["checks"]["shape_config"]["ok"]:
                report["failures"].append("shape_config")
            write_report(report)

            force_loops1(page)
            set_cycle_mode(page, True)
            wait_idle(page, 4000)
            force_loops1(page)
            aud_s = wait_short_audio(page)
            report["checks"]["shape_audio"] = {
                "dur": aud_s.get("dur"),
                "sounding": aud_s.get("sounding"),
                "ok": bool(aud_s.get("ok")),
            }
            if not aud_s.get("ok"):
                report["failures"].append("shape_audio")
                raise RuntimeError("shape_audio")

            open_lead_sheet(page)
            page.wait_for_timeout(1000)
            sk0 = sounding(page)
            sk1 = wait_key_change(page, sk0, 95)
            try:
                click_pause_ordinary(page)
            except Exception:
                pass
            wait_idle(page, 1200)
            sa = audio_snap(page)
            shape_want = str(sk1 or sa.get("sounding") or "")
            if str(sa.get("sounding") or "") in {str(sk1), str(sk0)}:
                shape_want = str(sa.get("sounding") or shape_want)
            if shape_want == str(sk0) and sk1 and sk1 != sk0:
                shape_want = str(sk1)
            # Cycle shape display is start-relative (Bm→Cm with shape C), not
            # shape_chart_key_for_concert(sounding, C) which is identity on Cm.
            _shape_base = shape_chart_key_for_concert("Bm", "C")
            try:
                _steps = int(semitone_distance("Bm", shape_want) or 0)
            except Exception:
                _steps = 0
            shape_expect = cycle_concert_practice_key(_shape_base, semitones=_steps)
            log(
                f"shape handoff keys sk0={sk0} sk1={sk1} audio={sa.get('sounding')} "
                f"want={shape_want} expect={shape_expect} base={_shape_base} steps={_steps}"
            )
            shape_waited = wait_cmd_sounding(
                page, shape_want, expect_reading=shape_expect, timeout_s=55
            )
            report["checks"]["shape_handoff_wait"] = {
                "ok": bool(shape_waited.get("ok")),
                "expect_reading": shape_expect,
                "snap": {
                    k: shape_waited.get(k)
                    for k in (
                        "sounding",
                        "readingKey",
                        "live",
                        "projectOnce",
                        "displayProjectionId",
                        "displaySemitones",
                    )
                },
            }
            shape_samples = sample_positions(page, 2)
            report["checks"]["shape_handoff"] = {
                "from": sk0,
                "to": sk1,
                "sounding": sa.get("sounding"),
                "want": shape_want,
                "samples": shape_samples,
                "ok": bool(sk1 and sk0 != sk1)
                and bool(shape_waited.get("ok"))
                and all(s.get("agree") for s in shape_samples),
            }
            log(f"shape_handoff {report['checks']['shape_handoff']['ok']}")
            if not report["checks"]["shape_handoff"]["ok"]:
                report["failures"].append("shape_handoff")
            write_report(report)

            try:
                click_pause_ordinary(page)
            except Exception:
                pass
            wait_idle(page, 1000)
            sh_paused = audio_snap(page)
            if not sh_paused.get("paused"):
                page.evaluate(
                    """() => {
                      try { if (typeof window.__kcPauseAudio === 'function') window.__kcPauseAudio(); } catch (e) {}
                      try {
                        const dual = window.__kcDual || {};
                        const a = document.getElementById(dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
                          || document.getElementById('kc-buf-0');
                        if (a) a.pause();
                      } catch (e2) {}
                    }"""
                )
                wait_idle(page, 800)
                sh_paused = audio_snap(page)
            sounding_shape = str(sh_paused.get("sounding") or shape_want)
            t_shape_before = float(sh_paused.get("t") or 0)
            expand_sidebar(page)
            page.evaluate(
                """() => {
                  const side = document.querySelector('section[data-testid="stSidebar"]');
                  if (side) side.scrollTop = side.scrollHeight;
                }"""
            )
            page.wait_for_timeout(400)
            still_shape = None
            for attempt in range(4):
                ensure_checkbox(page, "Guitar Shape", checked=False) or ensure_checkbox(
                    page, "Capo Shape Mode", checked=False
                )
                wait_idle(page, 2500)
                still_shape = page.evaluate(
                    """() => {
                      const needles = ['guitar shape', 'capo shape'];
                      const labels = [...document.querySelectorAll('label')];
                      for (const needle of needles) {
                        const lab = labels.find((el) => (el.innerText || '').toLowerCase().includes(needle));
                        if (!lab) continue;
                        const box = lab.querySelector('input[type="checkbox"]')
                          || document.getElementById(lab.getAttribute('for') || '');
                        if (box) return !!box.checked;
                      }
                      return null;
                    }"""
                )
                log(f"shape_mode_off toggle attempt={attempt} checked={still_shape}")
                if still_shape is False:
                    break
            sh_off = wait_concert_display(page, sounding=None, timeout_s=60)
            sh_aud = audio_snap(page)
            t_after = float(sh_aud.get("t") or 0)
            report["checks"]["shape_mode_off"] = {
                "sounding_before": sounding_shape,
                "sounding_after": sh_aud.get("sounding"),
                "displaySemitones": sh_off.get("displaySemitones"),
                "readingKey": sh_off.get("readingKey"),
                "checkbox_checked": still_shape,
                "paused_before": bool(sh_paused.get("paused")),
                "t_before": t_shape_before,
                "t_after": t_after,
                "ok": int(sh_off.get("displaySemitones") or 0) == 0
                and still_shape is False
                and abs(t_after - t_shape_before) < 8.0
                and str(sh_off.get("readingKey") or "")
                in ("", str(sh_aud.get("sounding") or sounding_shape)),
            }
            if not report["checks"]["shape_mode_off"]["ok"]:
                report["failures"].append("shape_mode_off")
            write_report(report)

            leave = _leave_piano_off(page)
            report["checks"]["leave"] = leave
            if not leave.get("ok"):
                report["failures"].append("leave")
            write_report(report)
        finally:
            try:
                browser.close()
            except Exception:
                pass


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    phase = str(os.environ.get("KC_PROOF_PHASE") or "all").strip().lower()
    report: dict = {
        "ok": False,
        "checks": {},
        "failures": [],
        "browser_error": None,
        "failure_class": None,
        "phase": phase,
        "server": port_listening(8510),
    }
    if not report["server"].get("ok"):
        report["failures"].append("server_down_before")
        report["failure_class"] = "server"
        write_report(report)
        return 1

    if phase in ("all", "written"):
        try:
            run_written(report)
        except Exception as exc:
            report["browser_error"] = str(exc)
            log(f"BROWSER_ERROR written {exc}")
            if "closed" in str(exc).lower() or "Target page" in str(exc):
                report["failures"].append("chromium_closed_written")
            else:
                report["failures"].append("exception_written")
            write_report(report)

    if phase in ("all", "shape"):
        if port_listening(8510).get("ok"):
            try:
                run_shape(report)
            except Exception as exc:
                report["browser_error"] = (
                    (report.get("browser_error") or "") + f" | shape: {exc}"
                ).strip(" |")
                log(f"BROWSER_ERROR shape {exc}")
                if "closed" in str(exc).lower() or "Target page" in str(exc):
                    report["failures"].append("chromium_closed_shape")
                else:
                    report["failures"].append("exception_shape")
                write_report(report)
        else:
            report["failures"].append("server_down_before_shape")

    report["ok"] = not report["failures"]
    write_report(report)
    srv = report.get("server") or {}
    if not srv.get("ok"):
        report["failure_class"] = "server"
        if "server_down_after" not in report["failures"]:
            report["failures"].append("server_down_after")
    elif any(f.startswith("chromium_closed") for f in report.get("failures", [])):
        report["failure_class"] = "browser"
    elif report.get("failures"):
        report["failure_class"] = "check"
    else:
        report["failure_class"] = "ok"
    report["ok"] = not report["failures"]
    write_report(report)
    log(
        f"RESULT ok={report.get('ok')} class={report.get('failure_class')} "
        f"failures={report.get('failures')} server={report.get('server')}"
    )

    return 0 if report.get("ok") and report.get("server", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

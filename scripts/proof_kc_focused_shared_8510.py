"""Shared helpers for focused key-cycle browser proofs on 8510."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

from proof_kc_finish_five_8510 import audio_probe, clear_pause_hold, wait_idle  # noqa: E402
from proof_kc_manual_review_six_8510 import (  # noqa: E402
    boot_shape,
    live_transport,
    play_until_audible,
    wait_playing,
    wait_stopped,
)
from proof_kc_settings_focused_8510 import set_loops, set_practice_key, set_scope_selected_section  # noqa: E402
from proof_kc_stop_resume_sequence_8510 import open_sheet, set_descending_whole_tone  # noqa: E402
from proof_key_cycle_ux_8510 import click_play, cycle_ui, set_cycle_mode  # noqa: E402
from proof_verse_verify_8510 import set_level_intermediate  # noqa: E402

BASE = "http://127.0.0.1:8510"
EVIDENCE = ROOT / "scripts" / "evidence-key-cycle"


def sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        return ""


def sounding(page) -> str:
    return str((cycle_ui(page) or {}).get("sounding") or "").strip()


def wait_src_change(page, src0: str, timeout_s: float = 100.0) -> dict:
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout_s:
        last = audio_probe(page)
        src = str(last.get("src") or "")
        if src and src != src0:
            return last
        page.wait_for_timeout(800)
    return last


def wait_key_change(page, key0: str, timeout_s: float = 200.0) -> str:
    t0 = time.time()
    last = key0
    while time.time() - t0 < timeout_s:
        last = sounding(page)
        if last and key0 and last != key0:
            return last
        page.wait_for_timeout(700)
    return last


def timeline_info(page) -> dict:
    return page.evaluate(
        """() => {
          let tl = window.__kcFollowTimeline || [];
          if (!Array.isArray(tl) || !tl.length) {
            for (const f of document.querySelectorAll('iframe')) {
              try {
                const w = f.contentWindow;
                const cand = (w && (w.__karaokeTimeline || w.__kcFollowTimeline)) || [];
                if (Array.isArray(cand) && cand.length) { tl = cand; break; }
              } catch (e) {}
            }
          }
          const secs = [...new Set(tl.map(e => String(e.section||'').trim()).filter(Boolean))];
          const chords = tl.slice(0, 8).map(e => String(e.chord||''));
          const last = tl.length ? tl[tl.length-1] : null;
          return {
            len: tl.length,
            sections: secs,
            end: last ? Number(last.end_time||0) : 0,
            firstChords: chords,
          };
        }"""
    )


def full_sync_probe(page) -> dict:
    """Audible buffer identity + status/sheet vs follow timeline (divergence)."""
    return page.evaluate(
        """() => {
          const dual = window.__kcDual || {};
          const id = dual.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          const a = document.getElementById(id) || document.getElementById('kc-buf-0');
          const t = a ? Number(a.currentTime || 0) : 0;
          const dur = a ? Number(a.duration || 0) : 0;
          const url = a ? String(a.getAttribute('data-kc-url') || a.src || '') : '';
          const bufKey = a ? String(a.getAttribute('data-kc-sounding') || '') : '';
          const lastKey = String(window.__kcLastSounding || '');
          let parentTl = Array.isArray(window.__kcFollowTimeline) ? window.__kcFollowTimeline : [];
          let iframeTl = [];
          let cycleOwns = false;
          let chord='', nxt='', section='', bar='', hi='';
          let iframeFirst = [];
          let iframeCount = 0;
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const doc = f.contentDocument;
              const win = f.contentWindow;
              if (!doc || !doc.querySelector('.live-follow-shell')) continue;
              iframeCount += 1;
              const cand = (win && (win.__karaokeTimeline || win.__kcFollowTimeline)) || [];
              if (Array.isArray(cand) && cand.length && !iframeTl.length) {
                iframeTl = cand;
                iframeFirst = cand.slice(0, 4).map(e => String(e.chord||''));
              }
              try {
                const st = window.__kcDual;
                cycleOwns = !!(st && st.enabled);
              } catch (eO) {}
              chord = (doc.getElementById('live-chord')||{}).innerText||'';
              nxt = (doc.getElementById('live-next')||{}).innerText||'';
              section = (doc.getElementById('live-section')||{}).innerText||'';
              bar = (doc.getElementById('live-bar')||{}).innerText||'';
              const cell = doc.querySelector(
                '.live-chart-cell.current-chord .chord-symbol, .live-chart-cell.current-chord, .sub-chord.active-sub'
              );
              if (cell) hi = (cell.innerText||cell.textContent||'').trim().split(/\\s+/)[0];
              break;
            } catch (e) {}
          }
          let tl = parentTl.length ? parentTl : iframeTl;
          if ((!Array.isArray(tl) || !tl.length) && window.__kcTimelineByKey) {
            const sk = bufKey || lastKey;
            const cached = window.__kcTimelineByKey[sk];
            if (Array.isArray(cached) && cached.length) tl = cached;
          }
          let ev = null;
          for (const e of tl) {
            if (t >= Number(e.start_time||0) && t < Number(e.end_time||1e9)) { ev = e; break; }
          }
          if (!ev && tl.length) ev = tl[0];
          let next = null;
          if (ev && tl.length) {
            const idx = Number.isFinite(Number(ev.event_index))
              ? Number(ev.event_index) : tl.indexOf(ev);
            next = tl[(idx + 1) % tl.length] || null;
          }
          const strip = (s) => String(s||'').trim().split(/\\s+|\\(/)[0];
          const tc = strip(ev && ev.chord);
          const tn = strip(next && next.chord);
          const uc = strip(chord);
          const un = strip(nxt);
          const parentFirst = parentTl.slice(0, 4).map(e => String(e.chord||''));
          const byKey = {};
          try {
            const bag = window.__kcTimelineByKey || {};
            for (const k of Object.keys(bag)) {
              const arr = bag[k];
              byKey[k] = Array.isArray(arr) ? arr.slice(0, 3).map(e => String(e.chord||'')) : [];
            }
          } catch (eB) {}
          return {
            t, dur, url: url.slice(-48), bufKey, lastKey,
            cycleId: String(dual.cycleId || ''),
            passId: Number(dual.passId || 0),
            swapping: !!dual.swapping,
            tlLen: tl.length,
            parentTlLen: parentTl.length,
            iframeTlLen: iframeTl.length,
            iframeCount,
            cycleOwns,
            parentFirst, iframeFirst, byKey,
            timelineChord: tc, timelineNext: tn,
            uiChord: uc, uiNext: un,
            uiSection: section.trim(), uiBar: bar.trim(),
            highlight: strip(hi),
            eventIndex: ev ? ev.event_index : null,
            eventSection: ev ? String(ev.section||'') : '',
            eventBar: ev ? ev.bar_in_section : null,
            chordMatch: !!(tc && uc && (tc === uc || tc.startsWith(uc) || uc.startsWith(tc))),
            nextMatch: !!(tn && un && (tn === un || tn.startsWith(un) || un.startsWith(tn)))
              || ((!tn || tn === '—') && (!un || un === '—' || un === '-')),
            sectionMatch: !!(ev && section && String(ev.section||'').includes(String(section).split(' ')[0])),
            sounding: bufKey || lastKey,
            labelKeyMismatch: !!(parentFirst.length && iframeFirst.length
              && parentFirst[0] && iframeFirst[0]
              && parentFirst[0] !== iframeFirst[0]),
          };
        }"""
    )


def chord_vs_timeline(page) -> dict:
    return full_sync_probe(page)


def ensure_feel_pop(page) -> dict:
    from proof_kc_bpm_feel_scope_8510 import commit_feel, read_server

    srv = read_server(page)
    g = str(srv.get("groove_canon") or srv.get("groove_widget") or "")
    if "pop" in g.lower():
        return {"ok": True, "feel": g, "already": True}
    return commit_feel(page, "Pop groove")


def boot_cycle_verse(page) -> dict:
    boot = boot_shape(page)
    set_scope_selected_section(page, "Verse")
    set_loops(page, 1)
    wait_idle(page)
    set_descending_whole_tone(page)
    wait_idle(page)
    if not set_cycle_mode(page, True):
        set_cycle_mode(page, True)
    wait_idle(page)
    return boot


def save_report(name: str, report: dict) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / name
    report.setdefault("sha", sha())
    report.setdefault("finished", time.strftime("%Y-%m-%dT%H:%M:%S"))
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def click_cycle_next(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
              const b = document.querySelector('[class*="st-key-backing_key_cycle_next_btn"] button')
                || [...document.querySelectorAll('button')].find(el =>
                  /^(Next key|▶?\\s*Next)$/i.test((el.innerText||'').replace(/\\s+/g,' ').trim()));
              if (!b) return false;
              b.click();
              return true;
            }"""
        )
    )


def body_pending_hint(page) -> bool:
    body = page.inner_text("body") or ""
    return any(
        s in body
        for s in (
            "pending Play",
            "cycle settings pending",
            "settings pending",
            "Press Play",
            "press Play",
        )
    )
